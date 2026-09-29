#!/usr/bin/env python3
"""
scan_signals.py - deterministyczny skaner antywzorcow Angular Signals.

Nie jest to parser TypeScript - to regex + rownowazenie nawiasow (stdlib,
zero zaleznosci), analogicznie do scan_sql.py z wydania #4 tej rubryki.
Wychwytuje KANDYDATOW do review, nie werdykt - patrz SKILL.md, krok 2.

Uzycie:
    python3 scan_signals.py <plik.ts> [<plik2.ts> ...]

Wyjscie: linie "plik:linia | WARN/INFO | REGULA | opis".
Exit code: 1 jesli w ktoryms pliku jest choc jeden WARN, inaczej 0.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass


@dataclass
class Finding:
    line: int
    level: str  # WARN | INFO
    rule: str
    message: str


# Deklaracja sygnalu/computed/input, np.:
#   count = signal(0);
#   private items = signal<Item[]>([]);
#   readonly total = computed(() => ...);
#   name = input<string>();
#   name = input.required<string>();
DECL_RE = re.compile(
    r"^\s*(?:public\s+|private\s+|protected\s+|readonly\s+)*(\w+)\s*"
    r"(?::\s*[^=;\n]+?)?\s*=\s*(?:signal|computed|input(?:\.required)?)\s*[(<]",
    re.MULTILINE,
)


def find_matching_paren(text: str, open_pos: int) -> int:
    """text[open_pos] to '(' - zwraca indeks odpowiadajacego ')' albo -1."""
    depth = 0
    i = open_pos
    in_str: str | None = None
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ("'", '"', "`"):
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def find_calls(text: str, name_pattern: str) -> list[tuple[int, int, int]]:
    """Zwraca (start_nazwy, idx_otw_nawiasu, idx_zam_nawiasu) dla wywolan name(...)."""
    calls = []
    for m in re.finditer(name_pattern + r"\s*(?:<[^>]*>)?\s*\(", text):
        open_idx = text.index("(", m.start())
        close_idx = find_matching_paren(text, open_idx)
        if close_idx != -1:
            calls.append((m.start(), open_idx, close_idx))
    return calls


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


MUTATING_METHODS = ("push", "pop", "shift", "unshift", "splice", "sort", "reverse", "fill")


def scan(text: str, path: str) -> list[Finding]:
    findings: list[Finding] = []

    signal_names = sorted(set(m.group(1) for m in DECL_RE.finditer(text)))
    uses_signals = bool(signal_names) or bool(
        re.search(r"\b(?:signal|computed|input(?:\.required)?)\s*[(<]", text)
    )

    # --- R: effect() ---------------------------------------------------
    for start, open_idx, close_idx in find_calls(text, r"\beffect"):
        body = text[open_idx + 1 : close_idx]
        ln = line_of(text, start)

        reads = set()
        writes = set()
        for name in signal_names:
            if re.search(rf"(?:this\.)?\b{re.escape(name)}\.(?:set|update)\s*\(", body):
                writes.add(name)
            if re.search(rf"(?:this\.)?\b{re.escape(name)}\s*\(", body):
                reads.add(name)
        sources = reads - writes
        if writes and sources:
            findings.append(
                Finding(
                    ln,
                    "WARN",
                    "EFFECT-STATE-SYNC",
                    f"effect() czyta {sorted(sources)} i ustawia {sorted(writes)} - to synchronizacja "
                    f"stanu wyliczanego z innych sygnalow, klasyczny przypadek dla computed(), nie effect()",
                )
            )

        self_write = writes & reads
        if self_write:
            findings.append(
                Finding(
                    ln,
                    "WARN",
                    "EFFECT-SELF-WRITE",
                    f"effect() odczytuje i w tym samym ciele zapisuje ten sam sygnal ({sorted(self_write)}) "
                    f"- ryzyko petli (kazdy set/update planuje kolejne wykonanie effect)",
                )
            )

        if len(reads) >= 2 and "untracked(" not in body:
            findings.append(
                Finding(
                    ln,
                    "INFO",
                    "UNTRACKED-CANDIDATE",
                    f"effect() czyta {len(reads)} sygnaly ({sorted(reads)}) bez untracked() - jesli "
                    f"niektore sluzą tylko jako wartosc do odczytania (nie mają wyzwalac ponownego "
                    f"uruchomienia), rozwaz untracked(() => ...) dla nich",
                )
            )

    # --- R: computed() ---------------------------------------------------
    for start, open_idx, close_idx in find_calls(text, r"\bcomputed"):
        body = text[open_idx + 1 : close_idx]
        ln = line_of(text, start)
        for name in signal_names:
            if re.search(rf"(?:this\.)?\b{re.escape(name)}\.(?:set|update)\s*\(", body):
                findings.append(
                    Finding(
                        ln,
                        "WARN",
                        "COMPUTED-SIDE-EFFECT",
                        f"computed() wywoluje {name}.set()/update() - computed() ma byc CZYSTA funkcja "
                        f"odczytu, mutacja innego sygnalu w środku to efekt uboczny (nieprzewidywalna "
                        f"liczba wywolan, zależna od tego kto i kiedy odczyta computed)",
                    )
                )

    # --- R: signal(...).update(callback) mutujący argument w miejscu -----
    for m in re.finditer(r"\.update\s*\(", text):
        open_idx = m.end() - 1
        close_idx = find_matching_paren(text, open_idx)
        if close_idx == -1:
            continue
        body = text[open_idx + 1 : close_idx]
        ln = line_of(text, m.start())
        param_m = re.match(r"\s*\(?\s*(\w+)\s*\)?\s*=>", body)
        if not param_m:
            continue
        param = param_m.group(1)
        mutating = [
            meth
            for meth in MUTATING_METHODS
            if re.search(rf"\b{re.escape(param)}\.{meth}\s*\(", body)
        ]
        index_assign = re.search(rf"\b{re.escape(param)}\s*\[[^\]]*\]\s*=(?!=)", body)
        if mutating or index_assign:
            what = ", ".join(mutating + (["indeks []="] if index_assign else []))
            findings.append(
                Finding(
                    ln,
                    "WARN",
                    "MUTATING-UPDATE",
                    f".update() mutuje parametr '{param}' w miejscu ({what}) zamiast zwrocic nowy "
                    f"obiekt/tablice - domyslna rownosc sygnalu to referencyjna (===); mutacja w miejscu "
                    f"psuje wykrywanie zmian, jesli ta sama referencja trafi gdzie indziej niezmieniona",
                )
            )

    # --- R: @Component bez OnPush, gdy plik uzywa signals ----------------
    if uses_signals:
        for start, open_idx, close_idx in find_calls(text, r"@Component"):
            body = text[open_idx + 1 : close_idx]
            ln = line_of(text, start)
            if "ChangeDetectionStrategy.OnPush" not in body and "changeDetection" not in body:
                findings.append(
                    Finding(
                        ln,
                        "WARN",
                        "ONPUSH-MISSING",
                        "komponent uzywa signal()/computed()/input(), ale @Component nie ma "
                        "changeDetection: ChangeDetectionStrategy.OnPush - bez OnPush Angular nadal "
                        "sprawdza caly poddrzewo przy kazdym cyklu zone.js, tracisz glowna zalete signals",
                    )
                )

    findings.sort(key=lambda f: f.line)
    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print("Uzycie: python3 scan_signals.py <plik.ts> [...]", file=sys.stderr)
        return 2

    any_warn = False
    for path in argv:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"{path} | ERROR | IO | {exc}", file=sys.stderr)
            any_warn = True
            continue

        findings = scan(text, path)
        if not findings:
            print(f"{path} | brak uwag")
            continue
        for f in findings:
            print(f"{path}:{f.line} | {f.level} | {f.rule} | {f.message}")
            if f.level == "WARN":
                any_warn = True

    return 1 if any_warn else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
