#!/usr/bin/env python3
"""Demo hooka PostToolUse: kopiuje sample-app do katalogu tymczasowego, nadpisuje Order.cs
roznymi wersjami i wola hook z payloadem takim, jak wysylalby Edit/Write.
Wymaga: python3, dotnet SDK (net10.0). Pierwsze uruchomienie robi `dotnet restore`."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(ROOT, "claude-hooks", "dotnet-post-edit.py")

GOOD = """namespace Orders.App;

public record Order(int Id, string Customer, decimal NetAmount);

public static class OrderPricing
{
    public static decimal WithVat(Order order) => Math.Round(order.NetAmount * 1.23m, 2);
}
"""

# poprawne skladniowo, ale brzydko sformatowane (tab, brak wciec, klamry w tej samej linii)
UGLY = """namespace Orders.App;

public record Order(int Id, string Customer, decimal NetAmount);

public static class OrderPricing {
\tpublic static decimal WithVat(Order order)
  {
        return Math.Round(order.NetAmount * 1.23m, 2);
    }
}
"""

# nie kompiluje sie: nieistniejaca wlasciwosc + niezgodny typ
BROKEN = GOOD.replace("order.NetAmount * 1.23m", "order.GrossAmount * 1.23m").replace(
    "public static decimal WithVat", "public static string WithVat")


def call_hook(payload):
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def main():
    if "--debug" in sys.argv:  # hook wypisze wyjscie `dotnet format` na stderr
        os.environ["POST_EDIT_DEBUG"] = "1"
    tmp = tempfile.mkdtemp(prefix="post-edit-demo-")
    app = os.path.join(tmp, "sample-app")
    shutil.copytree(os.path.join(ROOT, "sample-app"), app,
                    ignore=shutil.ignore_patterns("bin", "obj"))
    order = os.path.join(app, "Orders.App", "Order.cs")
    csproj = os.path.join(app, "Orders.App", "Orders.App.csproj")
    subprocess.run(["dotnet", "restore", csproj, "-nologo", "-v", "q"], check=True)

    def edit(path, tool="Edit"):
        return {"tool_name": tool, "tool_input": {"file_path": path}}

    cases = [
        ("czysty plik, buduje sie", GOOD, edit(order), 0),
        ("brzydkie formatowanie -> auto-format", UGLY, edit(order, "Write"), 0),
        ("blad kompilacji -> blokada", BROKEN, edit(order), 2),
        ("inne narzedzie niz edycja", GOOD, {"tool_name": "Bash", "tool_input": {"command": "ls"}}, 0),
        ("plik nie-.cs", GOOD, edit(os.path.join(app, ".editorconfig")), 0),
    ]
    bad = 0
    for name, content, payload, expected in cases:
        with open(order, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        code, out, err = call_hook(payload)
        changed = open(order, encoding="utf-8").read() != content
        # regresja: cichy no-op formatera (zla sciezka w --include) nie moze przejsc
        ok = code == expected and (changed == name.startswith("brzydkie"))
        bad += 0 if ok else 1
        print("%s exit=%d (oczekiwano %d)  %s" % ("OK  " if ok else "FAIL", code, expected, name))
        print("     plik zmieniony przez hook: %s" % ("tak" if changed else "nie"))
        for label, text in (("stdout", out), ("stderr", err)):
            for line in text.splitlines():
                print("     %s| %s" % (label, line))
        if name.startswith("brzydkie"):
            print("     --- plik po formatowaniu ---")
            for line in open(order, encoding="utf-8").read().splitlines():
                print("     | " + line)
    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("WYNIK: %d/%d przypadkow zgodnych" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
