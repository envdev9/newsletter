#!/usr/bin/env python3
"""PostToolUse hook Claude Code: po edycji pliku .cs (1) formatuje go, (2) buduje projekt.

Wpinany pod PostToolUse z matcherem "Write|Edit|MultiEdit". Na stdin dostaje JSON
  {"tool_name": "Edit", "tool_input": {"file_path": "/abs/Order.cs", ...}, ...}

Kroki:
  1. `dotnet format whitespace <csproj> --include <plik>` - naprawia tylko biale znaki wg
     .editorconfig, tylko ten jeden plik (szybko, bez ruszania reszty repo).
  2. `dotnet build <csproj> --no-restore` - jesli sa bledy kompilacji, wypisuje je na
     stderr i konczy kodem 2 (bledy wracaja do Claude).

Kody wyjscia:
  0 - plik nie jest .cs / brak csproj / wszystko sie buduje (ewentualna notka o
      sformatowaniu idzie na stdout)
  2 - blad kompilacji, stderr = lista bledow (unikalne, bez duplikatow ostrzezen)

Swiadome ograniczenia:
  * hook NIE uruchamia testow (za wolne na kazda edycje) - to zadanie hooka Stop
  * przy pierwszym uruchomieniu w swiezym repo potrzebny `dotnet restore` (--no-restore)
  * brak dotnet w PATH -> exit 0 z ostrzezeniem na stdout (nie blokujemy pracy)
"""
import json
import os
import re
import shutil
import subprocess
import sys

TIMEOUT_S = 120
ERROR_RE = re.compile(r"^(?P<line>.*: error [A-Z]+\d+: .*?)(?: \[[^\]]+\])?$")


def find_csproj(path):
    """Idz w gore od pliku, az znajdziesz katalog z dokladnie jednym *.csproj."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        found = [f for f in os.listdir(d) if f.endswith(".csproj")]
        if len(found) == 1:
            return os.path.join(d, found[0])
        if len(found) > 1:
            return None  # niejednoznaczne - nie zgadujemy
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S)


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".cs") or not os.path.isfile(path):
        return 0
    norm = path.replace("\\", "/")
    if "/obj/" in norm or "/bin/" in norm:
        return 0
    if shutil.which("dotnet") is None:
        print("dotnet-post-edit: brak `dotnet` w PATH - pomijam format i build")
        return 0
    csproj = find_csproj(path)
    if csproj is None:
        return 0
    cwd = os.path.dirname(csproj)

    before = open(path, "rb").read()
    fmt = run(["dotnet", "format", "whitespace", csproj, "--include", os.path.relpath(path, cwd), "--no-restore"], cwd)
    after = open(path, "rb").read()
    if os.environ.get("POST_EDIT_DEBUG"):
        sys.stderr.write("[debug] format rc=%d\n%s\n%s\n" % (fmt.returncode, fmt.stdout, fmt.stderr))
    if fmt.returncode != 0:
        # format nie zadzialal (np. zle argumenty) - nie blokujemy, ale mowimy o tym
        print("dotnet-post-edit: dotnet format zwrocil kod %d: %s" % (fmt.returncode, fmt.stderr.strip()[:300]))
    elif before != after:
        print("dotnet-post-edit: sformatowano %s wg .editorconfig - wczytaj plik ponownie "
              "przed kolejna edycja" % os.path.basename(path))

    build = run(["dotnet", "build", csproj, "--no-restore", "-nologo", "-v", "q", "-clp:NoSummary"], cwd)
    if build.returncode == 0:
        return 0
    errors = []
    for raw in (build.stdout + "\n" + build.stderr).splitlines():
        m = ERROR_RE.match(raw.strip())
        if m and m.group("line") not in errors:
            errors.append(m.group("line"))
    if not errors:  # build padl, ale nie umiemy wyciagnac bledow - pokaz ogon
        errors = (build.stdout + build.stderr).strip().splitlines()[-10:]
    sys.stderr.write("BUILD NIE PRZECHODZI po edycji %s (%d bledow):\n" % (os.path.basename(path), len(errors)))
    for e in errors[:15]:
        sys.stderr.write("  " + e + "\n")
    sys.stderr.write("Napraw bledy kompilacji zanim przejdziesz dalej.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
