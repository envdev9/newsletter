#!/usr/bin/env python3
"""docs_check.py - walidator zgodnosci dokumentacji (XML-doc, README, ADR) z kodem C#.

Tylko stdlib. To NIE jest parser C# (Roslyn) - to heurystyki regexowe dobrane pod styl
kodu z tego repo (jedna deklaracja = jedna sygnatura, bez makr preprocesora, bez atrybutow
w srodku listy parametrow). Dwa tryby:

  docs_check.py facts --root KOD_DIR            # JSON z faktami z kodu (wejscie do promptu)
  docs_check.py check --root KOD_DIR --docs DIR # waliduje XML-doc w .cs oraz *.md w DIR

Kod wyjscia: 0 = zgodne, 1 = znaleziono rozjazdy, 2 = blad uzycia.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Typy spoza repo, ktore wolno wymieniac w dokumentacji w `backtickach` bez deklaracji w kodzie.
BCL_ALLOW = {
    "Task", "TimeSpan", "CancellationToken", "Exception", "ArgumentException",
    "ArgumentNullException", "ArgumentOutOfRangeException", "InvalidOperationException",
    "HttpClient", "HttpStatusCode", "Math", "DateTime", "Func", "Action", "TimeoutException",
    "OperationCanceledException", "AggregateException", "NullReferenceException", "NuGet", "ADR", "README", "XML",
    "HTTP", "TUnit", "Polly", "Stryker", "Roslyn",
}
ADR_STATUSES = {"Proponowany", "Przyjęty", "Odrzucony", "Zastąpiony"}
ADR_SECTIONS = ["Status", "Kontekst", "Decyzja", "Konsekwencje"]
MODIFIERS = r"(?:(?:public|internal|private|protected|static|async|sealed|override|virtual|abstract|readonly|extern|new|partial|unsafe)\s+)*"


@dataclass
class Finding:
    rule: str
    where: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.where}: {self.msg}"


@dataclass
class Method:
    file: str
    line: int
    type_name: str
    name: str
    ret: str | None
    params: list[str]
    typeparams: list[str]
    throws: list[str]
    doc: str | None  # surowy XML bloku ///


@dataclass
class Facts:
    types: set[str] = field(default_factory=set)
    members: dict[str, set[str]] = field(default_factory=dict)
    consts: dict[str, tuple[str, int]] = field(default_factory=dict)  # nazwa -> ("int"|"ms", wartosc)
    methods: list[Method] = field(default_factory=list)
    files: list[tuple[Path, str]] = field(default_factory=list)  # (sciezka, wzgledna)


# ---------------------------------------------------------------- parsowanie C#

def skip_string(s: str, i: int) -> int:
    """s[i] == '"'; zwraca indeks po zamknieciu literalu (obsluga \\" i $\"...\")."""
    i += 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == '"':
            return i + 1
        i += 1
    return i


def match_close(s: str, i: int, open_c: str, close_c: str) -> int:
    """s[i] == open_c; zwraca indeks zamykajacego znaku (z pominieciem literalow)."""
    depth = 0
    while i < len(s):
        c = s[i]
        if c == '"':
            i = skip_string(s, i)
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s) - 1


def split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for c in s:
        if c in "<([":
            depth += 1
        elif c in ">)]":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return parts


def param_name(p: str) -> str:
    p = p.split("=")[0].strip()
    return re.findall(r"\w+", p)[-1]


def body_after(text: str, pos: int) -> str:
    """Tresc ciala metody: od pozycji po ')' do konca '{...}' albo do ';' dla '=>'."""
    i = pos
    while i < len(text):
        c = text[i]
        if c == '"':
            i = skip_string(text, i)
            continue
        if text.startswith("=>", i):
            end = i
            while end < len(text) and text[end] != ";":
                end = skip_string(text, end) if text[end] == '"' else end + 1
            return text[i:end]
        if c == "{":
            return text[i : match_close(text, i, "{", "}") + 1]
        if c == ";":
            return ""
        i += 1
    return ""


THROW_NEW = re.compile(r"\bthrow\s+new\s+([\w.]+)")
THROW_HELPERS = [
    (re.compile(r"\bArgumentNullException\.ThrowIfNull\b"), "ArgumentNullException"),
    (re.compile(r"\bArgumentOutOfRangeException\.ThrowIf\w+\b"), "ArgumentOutOfRangeException"),
    (re.compile(r"\bArgumentException\.ThrowIf\w+\b"), "ArgumentException"),
    (re.compile(r"\bObjectDisposedException\.ThrowIf\b"), "ObjectDisposedException"),
]


def throws_in(body: str) -> list[str]:
    out = [m.group(1).split(".")[-1] for m in THROW_NEW.finditer(body)]
    for rx, name in THROW_HELPERS:
        if rx.search(body):
            out.append(name)
    return sorted(set(out))


def parse_cs(path: Path, rel: str, facts: Facts) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    offsets, off = [], 0
    for ln in lines:
        offsets.append(off)
        off += len(ln) + 1

    cur_type = ""
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        mt = re.match(rf"^{MODIFIERS}(?:class|struct|enum|interface|record)\s+(\w+)", s)
        if mt:
            cur_type = mt.group(1)
            facts.types.add(cur_type)
            facts.members.setdefault(cur_type, set())

        # stale/pola/wlasciwosci (jednoliniowe deklaracje)
        mc = re.match(r"^(?:public|internal)\s+const\s+int\s+(\w+)\s*=\s*(\d+)\s*;", s)
        if mc:
            facts.consts[mc.group(1)] = ("int", int(mc.group(2)))
        mtm = re.match(
            r"^(?:public|internal)\s+static\s+readonly\s+TimeSpan\s+(\w+)\s*=\s*TimeSpan\.From(Seconds|Milliseconds|Minutes)\((\d+)\)\s*;", s)
        if mtm:
            mult = {"Seconds": 1000, "Milliseconds": 1, "Minutes": 60000}[mtm.group(2)]
            facts.consts[mtm.group(1)] = ("ms", int(mtm.group(3)) * mult)

        if re.match(r"^(?:public|internal|protected)\b", s) and cur_type:
            md = re.match(r"^(?:public|internal|protected)\b[^=({;]*?(\w+)\s*(?:<[^>()]*>)?\s*(?:\(|=|\{|;|=>)", s)
            if md and not re.search(r"\b(?:class|struct|enum|interface|record)\b", s):
                facts.members[cur_type].add(md.group(1))

        # blok /// bezposrednio nad deklaracja
        if s.startswith("///"):
            j = i
            block = []
            while j < len(lines) and lines[j].strip().startswith("///"):
                block.append(lines[j].strip()[3:])
                j += 1
            # deklaracja zaczyna sie w linii j
            if j < len(lines):
                start = offsets[j]
                rest = text[start:]
                first_term = re.search(r"[({;]|=>", rest)
                if first_term and first_term.group(0) == "(" and not re.match(r"^\s*(?:\[|///)", rest):
                    open_i = first_term.start()
                    pre = rest[:open_i]
                    close_i = match_close(rest, open_i, "(", ")")
                    plist = rest[open_i + 1 : close_i]
                    pm = re.match(rf"^\s*{MODIFIERS}(?:(?P<ret>[\w<>\[\],.?\s]+?)\s+)?(?P<name>\w+)\s*(?:<(?P<tp>[^>]*)>)?\s*$", pre)
                    if pm:
                        decl_line = j + 1
                        body = body_after(rest, close_i + 1)
                        facts.methods.append(Method(
                            file=rel, line=decl_line, type_name=cur_type, name=pm.group("name"),
                            ret=(pm.group("ret") or "").strip() or None,
                            params=[param_name(p) for p in split_top(plist)],
                            typeparams=[t.strip() for t in (pm.group("tp") or "").split(",") if t.strip()],
                            throws=throws_in(body),
                            doc="\n".join(block)))
            i = j
            continue
        i += 1


def load_facts(root: Path, src_dirs: list[str]) -> Facts:
    facts = Facts()
    for d in src_dirs:
        for p in sorted((root / d).rglob("*.cs")):
            if set(p.relative_to(root).parts) & {"bin", "obj"}:
                continue
            rel = str(p.relative_to(root))
            facts.files.append((p, rel))
            parse_cs(p, rel, facts)
    return facts


# ---------------------------------------------------------------- walidacja XML-doc

def check_claim(name: str, value: int, unit: str | None, where: str, facts: Facts) -> Finding | None:
    key = name.split(".")[-1]
    if key not in facts.consts:
        return None  # nie wiemy, co to jest - nie zgadujemy
    kind, actual = facts.consts[key]
    if kind == "int":
        if unit:
            return Finding("CLAIM", where, f"`{name}` jest liczba calkowita, a dokument podaje jednostke '{unit}'")
        return None if actual == value else Finding("CLAIM", where, f"`{name}` = {value}, a w kodzie {actual}")
    if not unit:
        return Finding("CLAIM", where, f"`{name}` to czas ({actual} ms) - dokument nie podaje jednostki")
    claimed = value * (1000 if unit == "s" else 1)
    return None if claimed == actual else Finding("CLAIM", where, f"`{name}` = {value} {unit}, a w kodzie {actual} ms")


CLAIM_RX = re.compile(r"\b([A-Z]\w*(?:\.[A-Z]\w*)*)\s*(?:=|==|wynosi|równa się)\s*(\d+)(?:\s*(ms|s)\b)?")


def check_xmldoc(facts: Facts) -> list[Finding]:
    out: list[Finding] = []
    for m in facts.methods:
        where = f"{m.file}:{m.line} {m.type_name}.{m.name}"
        try:
            root = ET.fromstring(f"<root>{m.doc}</root>")
        except ET.ParseError as e:
            out.append(Finding("XD07", where, f"niepoprawny XML w komentarzu: {e}"))
            continue
        doc_params = [e.get("name") for e in root.findall("param")]
        for p in m.params:
            if p not in doc_params:
                out.append(Finding("XD01", where, f"parametr `{p}` nie ma <param>"))
        for p in doc_params:
            if p not in m.params:
                out.append(Finding("XD02", where, f"<param name=\"{p}\"> - w kodzie nie ma takiego parametru"))
        doc_tp = [e.get("name") for e in root.findall("typeparam")]
        if sorted(doc_tp) != sorted(m.typeparams):
            out.append(Finding("XD06", where, f"typeparam w doc {doc_tp} != w kodzie {m.typeparams}"))
        doc_exc = sorted({(e.get("cref") or "").split(".")[-1] for e in root.findall("exception")})
        for t in m.throws:
            if t not in doc_exc:
                out.append(Finding("XD03", where, f"kod rzuca {t}, brak <exception cref=\"{t}\">"))
        for t in doc_exc:
            if t not in m.throws:
                out.append(Finding("XD04", where, f"doc deklaruje {t}, ale kod go nie rzuca"))
        has_ret = root.find("returns") is not None
        returns_value = m.ret is not None and m.ret not in ("void", "Task", "ValueTask")
        if returns_value and not has_ret:
            out.append(Finding("XD05", where, f"metoda zwraca {m.ret}, brak <returns>"))
        if not returns_value and has_ret:
            out.append(Finding("XD05", where, "<returns> przy metodzie bez wartosci"))
    # liczby w <c>...</c> w dowolnym bloku XML-doc (rowniez na typach)
    for p, rel in facts.files:
        for n, ln in enumerate(p.read_text(encoding="utf-8").split("\n"), 1):
            if ln.strip().startswith("///"):
                for c in re.findall(r"<c>([^<]*)</c>", ln):
                    for mm in CLAIM_RX.finditer(c):
                        f = check_claim(mm.group(1), int(mm.group(2)), mm.group(3), f"{rel}:{n}", facts)
                        if f:
                            out.append(Finding("XD08", f.where, f.msg))
    return out


# ---------------------------------------------------------------- walidacja Markdown (README, ADR)

IDENT_RX = re.compile(r"^([A-Z]\w*(?:\.[A-Z]\w*)*)(?:\(.*\))?$")
PATH_EXT = (".cs", ".csproj", ".md", ".json", ".py", ".txt")


def path_exists(root: Path, md_dir: Path, token: str) -> bool:
    return (root / token).exists() or (md_dir / token).exists()


def check_markdown(md: Path, root: Path, facts: Facts) -> list[Finding]:
    out: list[Finding] = []
    text = md.read_text(encoding="utf-8")
    lines = text.split("\n")
    name = md.name
    for n, ln in enumerate(lines, 1):
        where = f"{name}:{n}"
        for tok in re.findall(r"`([^`\n]+)`", ln):
            tok = tok.strip()
            if "://" in tok or tok.startswith(("dotnet ", "python", "-")) or "*" in tok:
                continue
            if (("/" in tok or tok.endswith(PATH_EXT)) and " " not in tok and not IDENT_RX.match(tok)):
                if not path_exists(root, md.parent, tok):
                    out.append(Finding("MD03", where, f"sciezka `{tok}` nie istnieje"))
                continue
            mi = IDENT_RX.match(tok)
            if mi:
                parts = mi.group(1).split(".")
                head = parts[0]
                if head in facts.types:
                    if len(parts) > 1 and parts[1] not in facts.members.get(head, set()):
                        out.append(Finding("MD02", where, f"`{tok}` - typ {head} nie ma skladowej `{parts[1]}`"))
                elif head in BCL_ALLOW or path_exists(root, md.parent, tok):
                    pass  # typ BCL albo nazwa katalogu/projektu w repo (np. `Retry.Demo`)
                else:
                    out.append(Finding("MD01", where, f"`{tok}` - brak takiego typu w kodzie (ani na liscie BCL_ALLOW)"))
        for cm in re.finditer(r"`([A-Z][\w.]*)`\s*(?:=|==|wynosi|równa się)\s*`?(\d+)(?:\s*(ms|s)\b)?", ln):
            f = check_claim(cm.group(1), int(cm.group(2)), cm.group(3), where, facts)
            if f:
                out.append(Finding("MD05", f.where, f.msg))
        for cmd in re.finditer(r"dotnet\s+(?:run|build|test)\s+(?:--project\s+)?([^\s`-][^\s`]*)", ln):
            target = cmd.group(1)
            if not path_exists(root, md.parent, target):
                out.append(Finding("MD04", where, f"komenda wskazuje `{target}`, ktorego nie ma"))
    if name.startswith("ADR"):
        out += check_adr(md, text)
    return out


def check_adr(md: Path, text: str) -> list[Finding]:
    out: list[Finding] = []
    name = md.name
    headings = {m.group(1).strip(): m.end() for m in re.finditer(r"^##\s+(.+)$", text, re.M)}
    for sec in ADR_SECTIONS:
        if sec not in headings:
            out.append(Finding("AD01", name, f"brak sekcji `## {sec}`"))
    if "Status" in headings:
        body = text[headings["Status"]:].strip().split("\n", 1)[0].strip()
        if body not in ADR_STATUSES:
            out.append(Finding("AD02", name, f"status '{body}' spoza {sorted(ADR_STATUSES)}"))
    md_ = re.search(r"^Data:\s*(\d{4})-(\d{2})-(\d{2})\s*$", text, re.M)
    try:
        if not md_:
            raise ValueError
        date(int(md_.group(1)), int(md_.group(2)), int(md_.group(3)))
    except ValueError:
        out.append(Finding("AD03", name, "brak linii `Data: RRRR-MM-DD` z poprawna data"))
    if not re.search(r"`[^`\n]+\.cs`", text):
        out.append(Finding("AD04", name, "ADR nie wskazuje zadnego pliku `.cs`, ktorego dotyczy"))
    if "Konsekwencje" in headings:
        cons = text[headings["Konsekwencje"]:]
        if not re.search(r"^\s*[-*]\s*Negatywne:", cons, re.M):
            out.append(Finding("AD05", name, "Konsekwencje bez punktu `Negatywne:` (ADR bez kosztow to reklama)"))
    return out


# ---------------------------------------------------------------- CLI

def facts_json(facts: Facts) -> str:
    data = {
        "types": sorted(facts.types),
        "constants": {k: {"kind": v[0], "value": v[1]} for k, v in sorted(facts.consts.items())},
        "methods": [
            {"where": f"{m.file}:{m.line}", "type": m.type_name, "name": m.name, "returns": m.ret,
             "params": m.params, "typeparams": m.typeparams, "throws": m.throws}
            for m in facts.methods
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["facts", "check"])
    ap.add_argument("--root", required=True, help="katalog z kodem (zawiera Retry/ itd.)")
    ap.add_argument("--src", action="append", help="podkatalog z kodem (powtarzalny); domyslnie caly --root")
    ap.add_argument("--docs", help="katalog z README.md / ADR-*.md (tryb check)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    facts = load_facts(root, a.src or ["."])
    if a.mode == "facts":
        print(facts_json(facts))
        return 0
    if not a.docs:
        ap.error("check wymaga --docs")
    findings = check_xmldoc(facts)
    docs = Path(a.docs).resolve()
    mds = sorted(docs.glob("*.md"))
    for md in mds:
        findings += check_markdown(md, root, facts)
    print(f"sprawdzono: {len(facts.methods)} metod z XML-doc, {len(mds)} plikow .md")
    for f in findings:
        print(f)
    print(f"WYNIK: {'OK' if not findings else 'ROZJAZDY: ' + str(len(findings))}")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
