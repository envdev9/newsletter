#!/usr/bin/env python3
"""Lancuch promptow z kontraktem miedzy krokami (Python stdlib, bez modelu).

Kopia chain.py z wydania #18 (2026-10-11), bez zmian logiki - uzywana przez cost.py.

Trzy kroki: 1 triaz (JSON) -> 2 plan (JSON) -> 3 patch (unified diff).
Skrypt: buduje prompty z szablonow, waliduje KAZDY wynik kroku (kontrakt),
buduje prompt naprawczy z bledami walidatora i uruchamia bramke koncowa
(`git apply` + `dotnet run --project Billing.Check`).

Model jest wtyczka: `Model = Callable[[int, str], str]` (numer kroku, prompt -> tekst).
W tym repo jedyna implementacja to ReplayModel (czyta fixtures/<scenariusz>/stepN.txt)
- to NIE jest model, to nagrania pisane recznie.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Callable

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_CHANGED_LINES = 10
PROTECTED_PREFIX = "Billing.Check/"

Model = Callable[[int, str], str]


# --------------------------------------------------------------- indeks symboli
def build_index(root: str = HERE) -> dict[str, str]:
    """symbol ('Typ' albo 'Typ.Skladowa') -> plik wzgledem root. Regexy, nie Roslyn."""
    index: dict[str, str] = {}
    base = os.path.join(root, "Billing")
    for name in sorted(os.listdir(base)):
        if not name.endswith(".cs"):
            continue
        rel = f"Billing/{name}"
        current = None
        with open(os.path.join(base, name), encoding="utf-8") as fh:
            for line in fh:
                m = re.search(r"\b(?:class|record|struct|interface)\s+(\w+)", line)
                if m:
                    current = m.group(1)
                    index[current] = rel
                    continue
                m = re.search(r"\bpublic\s+(?:static\s+)?[\w<>\[\],? ]+?\s+(\w+)\s*(?:\(|=>)", line)
                if m and current:
                    index[f"{current}.{m.group(1)}"] = rel
    return index


def index_text(index: dict[str, str]) -> str:
    by_file: dict[str, list[str]] = {}
    for sym, f in index.items():
        by_file.setdefault(f, []).append(sym)
    return "\n".join(f"{f}: {', '.join(sorted(s))}" for f, s in sorted(by_file.items()))


def read_sources(files: list[str], root: str = HERE) -> str:
    parts = []
    for f in files:
        with open(os.path.join(root, f), encoding="utf-8") as fh:
            parts.append(f"=== {f} ===\n{fh.read().rstrip()}\n")
    return "\n".join(parts)


# ---------------------------------------------------------------------- prompty
def template(name: str) -> str:
    with open(os.path.join(HERE, "prompts", name), encoding="utf-8") as fh:
        return fh.read()


def fill(tpl: str, **kw: str) -> str:
    for k, v in kw.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    return tpl


def build_prompt(step: int, bug_report: str, index: dict[str, str],
                 step1: dict | None = None, step2: dict | None = None) -> str:
    if step == 1:
        return fill(template("step1_triage.txt"), bug_report=bug_report.strip(),
                    symbol_index=index_text(index))
    if step == 2:
        files = sorted({s["file"] for s in step1["suspects"]})
        return fill(template("step2_plan.txt"), step1_json=json.dumps(step1, ensure_ascii=False, indent=1),
                    sources=read_sources(files))
    files = sorted({c["file"] for c in step2["changes"]})
    return fill(template("step3_patch.txt"), step2_json=json.dumps(step2, ensure_ascii=False, indent=1),
                sources=read_sources(files))


def build_repair(step: int, errors: list[str], previous: str, attempt: int = 1, max_attempts: int = 2) -> str:
    return fill(template("repair.txt"), step=str(step), errors="\n".join(f"- {e}" for e in errors),
                previous=previous.strip(), attempt=str(attempt), max_attempts=str(max_attempts))


# -------------------------------------------------------------------- kontrakty
def strict_json(text: str) -> tuple[dict | None, list[str]]:
    t = text.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None, ["C01 odpowiedz nie jest czystym obiektem JSON (prosa albo ogrodzenie ``` wokol)"]
    try:
        obj = json.loads(t)
    except json.JSONDecodeError as e:
        return None, [f"C01 niepoprawny JSON: {e.msg} (linia {e.lineno})"]
    if not isinstance(obj, dict):
        return None, ["C01 JSON nie jest obiektem"]
    return obj, []


def lenient_json(text: str) -> dict | None:
    """Baseline: wyciaga {...} z prozy/ogrodzenia i nie sprawdza niczego wiecej."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        return None


def check_step1(text: str, index: dict[str, str], bug_report: str) -> tuple[dict | None, list[str]]:
    obj, errs = strict_json(text)
    if errs:
        return None, errs
    if set(obj) != {"symptom", "suspects", "unknowns"}:
        errs.append(f"C02 klucze {sorted(obj)} != ['suspects', 'symptom', 'unknowns']")
        return None, errs
    sym = obj["symptom"]
    if not isinstance(sym, str) or not sym or len(sym) > 200:
        errs.append("C03 symptom: niepusty string do 200 znakow")
    else:
        nums = set(re.findall(r"\d+\.\d+", bug_report))
        if nums and not any(n in sym for n in nums):
            errs.append("C04 symptom nie cytuje zadnej liczby ze zgloszenia")
    sus = obj["suspects"]
    if not isinstance(sus, list) or not 1 <= len(sus) <= 3:
        errs.append("C05 suspects: lista 1-3 elementow")
    else:
        for s in sus:
            if not isinstance(s, dict) or set(s) != {"symbol", "file"}:
                errs.append(f"C05 podejrzany o zlym ksztalcie: {s!r}")
            elif s["symbol"] not in index:
                errs.append(f"C06 symbol `{s['symbol']}` nie istnieje w indeksie")
            elif index[s["symbol"]] != s["file"]:
                errs.append(f"C07 symbol `{s['symbol']}` jest w {index[s['symbol']]}, nie w {s['file']}")
    if not isinstance(obj["unknowns"], list) or not all(isinstance(u, str) for u in obj["unknowns"]):
        errs.append("C08 unknowns: lista stringow")
    return (obj if not errs else None), errs


def check_step2(text: str, step1: dict, index: dict[str, str]) -> tuple[dict | None, list[str]]:
    obj, errs = strict_json(text)
    if errs:
        return None, errs
    if set(obj) != {"changes", "test", "out_of_scope"}:
        return None, [f"C02 klucze {sorted(obj)} != ['changes', 'out_of_scope', 'test']"]
    allowed = {s["file"] for s in step1["suspects"]}
    ch = obj["changes"]
    if not isinstance(ch, list) or not 1 <= len(ch) <= 2:
        errs.append("C09 changes: lista 1-2 elementow")
    else:
        for c in ch:
            if not isinstance(c, dict) or set(c) != {"file", "symbol", "edit"}:
                errs.append(f"C09 zmiana o zlym ksztalcie: {c!r}")
                continue
            if c["file"].startswith(PROTECTED_PREFIX):
                errs.append(f"C10 plan zmienia {c['file']} - kryterium akceptacji jest tylko do odczytu")
            elif c["file"] not in allowed:
                errs.append(f"C11 plik {c['file']} poza zakresem triazu {sorted(allowed)}")
            if c["symbol"] not in index:
                errs.append(f"C06 symbol `{c['symbol']}` nie istnieje w indeksie")
    if not isinstance(obj["test"], str) or not obj["test"].strip():
        errs.append("C12 test: niepusty string")
    if not isinstance(obj["out_of_scope"], list):
        errs.append("C08 out_of_scope: lista")
    return (obj if not errs else None), errs


def diff_files(diff: str) -> list[str]:
    return re.findall(r"^\+\+\+ b/(\S+)", diff, flags=re.M)


def changed_lines(diff: str) -> int:
    n = 0
    for line in diff.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            n += 1
    return n


def git_apply_check(diff: str, workdir: str) -> list[str]:
    p = os.path.join(workdir, "_patch.diff")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(diff if diff.endswith("\n") else diff + "\n")
    r = subprocess.run(["git", "-C", workdir, "apply", "--check", "_patch.diff"],
                       capture_output=True, text=True)
    os.remove(p)
    if r.returncode != 0:
        first = (r.stderr.strip().splitlines() or ["?"])[0]
        return [f"C16 git apply --check: {first}"]
    return []


def check_step3(text: str, plan: dict, workdir: str) -> list[str]:
    errs: list[str] = []
    t = text.strip()
    if "```" in t or not t.startswith(("--- ", "diff --git")):
        errs.append("C13 odpowiedz nie jest czystym diffem unified (prosa albo ogrodzenie ```)")
        return errs
    planned = {c["file"] for c in plan["changes"]}
    for f in diff_files(t):
        if f.startswith(PROTECTED_PREFIX):
            errs.append(f"C14 diff zmienia {f} - Billing.Check jest tylko do odczytu")
        elif f not in planned:
            errs.append(f"C15 diff zmienia {f}, ktorego nie ma w planie {sorted(planned)}")
    n = changed_lines(t)
    if n > MAX_CHANGED_LINES:
        errs.append(f"C17 {n} zmienionych linii > limit {MAX_CHANGED_LINES}")
    errs += git_apply_check(t, workdir)
    return errs


# ------------------------------------------------------------- bramka koncowa
def make_workdir() -> str:
    wd = tempfile.mkdtemp(prefix="prompt-chain-")
    for d in ("Billing", "Billing.Check"):
        shutil.copytree(os.path.join(HERE, d), os.path.join(wd, d),
                        ignore=shutil.ignore_patterns("bin", "obj"))
    return wd


def final_gate(diff: str, workdir_template: str) -> tuple[bool, str]:
    """Kopia drzewa -> git apply -> dotnet run Billing.Check. Zwraca (zielone, ostatnie linie)."""
    wd = tempfile.mkdtemp(prefix="prompt-gate-")
    try:
        for d in ("Billing", "Billing.Check"):
            shutil.copytree(os.path.join(workdir_template, d), os.path.join(wd, d))
        errs = git_apply_check(diff, wd)
        if errs:
            return False, errs[0]
        p = os.path.join(wd, "_patch.diff")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(diff if diff.endswith("\n") else diff + "\n")
        subprocess.run(["git", "-C", wd, "apply", "_patch.diff"], check=True, capture_output=True)
        os.remove(p)
        r = subprocess.run(["dotnet", "run", "--project", os.path.join(wd, "Billing.Check", "Billing.Check.csproj")],
                           capture_output=True, text=True, timeout=600)
        tail = (r.stdout.strip().splitlines() or [r.stderr.strip()[:200]])[-1]
        return r.returncode == 0, tail
    finally:
        shutil.rmtree(wd, ignore_errors=True)


# ------------------------------------------------------------------- lancuch
@dataclass
class Result:
    accepted: bool
    stage: str                      # gdzie zatrzymano / "gate" / "-"
    calls: int                      # ile wywolan modelu poszlo
    detail: str = ""
    errors: list[str] = field(default_factory=list)


class ReplayModel:
    """Nagrania pisane recznie (fixtures/<scenariusz>/stepN.txt). NIE jest modelem."""

    def __init__(self, scenario: str):
        self.dir = os.path.join(HERE, "fixtures", scenario)
        self.prompts: dict[int, str] = {}

    def __call__(self, step: int, prompt: str) -> str:
        self.prompts[step] = prompt
        with open(os.path.join(self.dir, f"step{step}.txt"), encoding="utf-8") as fh:
            return fh.read()


def strip_fence(text: str) -> str:
    m = re.search(r"```(?:diff)?\n(.*?)```", text, flags=re.S)
    return m.group(1) if m else text


def run_chain(model: Model, contracts: bool, bug_report: str, index: dict[str, str],
              workdir: str, gate=final_gate) -> Result:
    # krok 1
    out1 = model(1, build_prompt(1, bug_report, index))
    if contracts:
        s1, errs = check_step1(out1, index, bug_report)
        if errs:
            return Result(False, "krok 1", 1, errors=errs)
    else:
        s1 = lenient_json(out1)
        if s1 is None:
            return Result(False, "krok 1", 1, "nie da sie sparsowac", [])
    # krok 2
    out2 = model(2, build_prompt(2, bug_report, index, step1=s1))
    if contracts:
        s2, errs = check_step2(out2, s1, index)
        if errs:
            return Result(False, "krok 2", 2, errors=errs)
    else:
        s2 = lenient_json(out2)
        if s2 is None:
            return Result(False, "krok 2", 2, "nie da sie sparsowac", [])
    # krok 3
    out3 = model(3, build_prompt(3, bug_report, index, step1=s1, step2=s2))
    if contracts:
        errs = check_step3(out3, s2, workdir)
        if errs:
            return Result(False, "krok 3", 3, errors=errs)
        diff = out3.strip()
    else:
        diff = strip_fence(out3).strip()
    ok, tail = gate(diff, workdir)
    return Result(ok, "-" if ok else "bramka", 3, tail)


# ------------------------------------------------------------------------ CLI
def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index", help="wypisz indeks symboli")
    p = sub.add_parser("prompt", help="zbuduj prompt kroku z nagran scenariusza")
    p.add_argument("step", type=int, choices=[1, 2, 3])
    p.add_argument("--scenario", default="s0_good")
    p = sub.add_parser("check-step", help="zwaliduj plik z wynikiem kroku")
    p.add_argument("step", type=int, choices=[1, 2, 3])
    p.add_argument("file")
    p.add_argument("--triage", help="plik JSON z wynikiem kroku 1 (dla kroku 2)")
    p.add_argument("--plan", help="plik JSON z wynikiem kroku 2 (dla kroku 3)")
    p = sub.add_parser("repair", help="zbuduj prompt naprawczy z bledow walidatora")
    p.add_argument("step", type=int, choices=[1, 2, 3])
    p.add_argument("file")
    p.add_argument("--triage")
    p.add_argument("--plan")
    p = sub.add_parser("run", help="uruchom lancuch na nagraniach scenariusza")
    p.add_argument("scenario")
    p.add_argument("--no-contracts", action="store_true")
    a = ap.parse_args(argv)

    index = build_index()
    bug = _read(os.path.join(HERE, "bug_report.txt"))

    if a.cmd == "index":
        print(index_text(index))
        return 0
    if a.cmd == "prompt":
        fx = os.path.join(HERE, "fixtures", a.scenario)
        s1 = json.loads(_read(os.path.join(fx, "step1.txt"))) if a.step >= 2 else None
        s2 = json.loads(_read(os.path.join(fx, "step2.txt"))) if a.step >= 3 else None
        print(build_prompt(a.step, bug, index, s1, s2))
        return 0
    if a.cmd in ("check-step", "repair"):
        text = _read(a.file)
        wd = make_workdir()
        try:
            if a.step == 1:
                _, errs = check_step1(text, index, bug)
            elif a.step == 2:
                _, errs = check_step2(text, json.loads(_read(a.triage)), index)
            else:
                errs = check_step3(text, json.loads(_read(a.plan)), wd)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
        if a.cmd == "repair":
            print(build_repair(a.step, errs or ["(brak naruszen)"], text))
            return 0
        for e in errs:
            print(f"[{e.split()[0]}] {e.split(' ', 1)[1]}")
        print("WYNIK: OK" if not errs else f"WYNIK: NARUSZENIA: {len(errs)}")
        return 0 if not errs else 1
    if a.cmd == "run":
        wd = make_workdir()
        try:
            r = run_chain(ReplayModel(a.scenario), not a.no_contracts, bug, index, wd)
        finally:
            shutil.rmtree(wd, ignore_errors=True)
        print(f"accepted={r.accepted} stage={r.stage} calls={r.calls} detail={r.detail}")
        for e in r.errors:
            print(f"  [{e.split()[0]}] {e.split(' ', 1)[1]}")
        return 0 if r.accepted else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
