"""Swiat testowy: PRAWDZIWY katalog na dysku (repo) + narzedzia z licznikami efektow ubocznych
+ deterministyczne 'modele' (policy). Policy dostaje History (lista kroków z polem .total)."""
from __future__ import annotations

import hashlib
import os

from agentloop import Action, Done, History, Tool, TransientError

FOO_BROKEN = "class Foo { int X() => y; }\n"
NOTES = ("Notatki z analizy: modul Foo odwoluje sie do zmiennej y, ktora nie istnieje. "
         "Podejrzewany commit: refaktor nazw. Sprawdzic Foo.cs oraz testy FooTests. ") * 3


def letters(seed: str, n: int = 6) -> str:
    """Deterministyczny 'identyfikator uruchomienia' z samych liter (cyfry zjadlaby normalizacja)."""
    d = hashlib.sha256(seed.encode()).digest()
    return "".join(chr(97 + b % 26) for b in d[:n])


class World:
    def __init__(self, root: str, fetch_failures: int = 0) -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.write("Foo.cs", FOO_BROKEN)
        self.write("notes.txt", NOTES)
        self.outbox: dict[str, str] = {}
        self.notify_calls = 0
        self.charges: list[int] = []
        self.fetch_failures = fetch_failures
        self.fetch_calls = 0
        self.test_runs = 0

    # --- pomocnicze
    def write(self, rel: str, text: str) -> None:
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as f:
            return f.read()

    # --- narzedzia
    def read_file(self, a, key):
        return self.read(a["path"])

    def edit_file(self, a, key):
        self.write(a["path"], a["text"])
        return "ok"

    def run_tests(self, a, key):
        """Padajacy test wypisuje identyfikator uruchomienia (jak sciezka pliku .trx z timestampem w
        `dotnet test`) - dlatego pierwsza linia bledu jest ZA KAZDYM razem inna."""
        self.test_runs += 1
        if "fixed" in self.read("Foo.cs"):
            return "PASS 12 tests"
        raise AssertionError(f"FAIL CS0103: name 'y' does not exist at Foo.cs:{10 + self.test_runs} "
                             f"(run-{letters(str(self.test_runs))})")

    def notify(self, a, key):
        self.notify_calls += 1
        if key in self.outbox:
            return self.outbox[key]
        self.outbox[key] = "sent"
        return "sent"

    def charge(self, a, key):
        self.charges.append(a["amount"])
        return f"charged {a['amount']}"

    def fetch(self, a, key):
        self.fetch_calls += 1
        if self.fetch_calls <= self.fetch_failures:
            raise TransientError("503 Service Unavailable")
        return "payload"

    def tools(self) -> dict[str, Tool]:
        return {
            "read_file": Tool("read_file", self.read_file),
            "edit_file": Tool("edit_file", self.edit_file, honors_key=True, side_effect=True),
            "run_tests": Tool("run_tests", self.run_tests, verifies=True),
            "notify": Tool("notify", self.notify, honors_key=True, side_effect=True),
            "charge": Tool("charge", self.charge, honors_key=False, side_effect=True),
            "fetch": Tool("fetch", self.fetch),
        }


FIXED = "class Foo { int X() => 1; /* fixed */ }\n"


def _seq(h: History, seq: list[Action], done: str = "ok"):
    return seq[h.total] if h.total < len(seq) else Done(done)


# ---------------------------------------------------------------- 'modele'
def policy_progress(h: History):
    """Dwie nieudane proby naprawy (kazda zmienia drzewo), trzecia dziala."""
    return _seq(h, [Action("run_tests", {}),
                    Action("edit_file", {"path": "Foo.cs", "text": "class Foo { int X() => 0; }\n"}),
                    Action("run_tests", {}),
                    Action("edit_file", {"path": "Foo.cs", "text": "class Foo { int X() => 2; }\n"}),
                    Action("run_tests", {}),
                    Action("edit_file", {"path": "Foo.cs", "text": FIXED}),
                    Action("run_tests", {})], "testy zielone")


def policy_explore_then_fix(h: History):
    """8 odczytow (drzewo stale, zadnej weryfikacji) i dopiero naprawa. Nie wolno tego uznac za zastoj."""
    seq = [Action("read_file", {"path": "notes.txt", "pass": i}) for i in range(8)]
    seq += [Action("edit_file", {"path": "Foo.cs", "text": FIXED}), Action("run_tests", {})]
    return _seq(h, seq, "naprawione po rozeznaniu")


def policy_spin_same_tree(h: History):
    """Model 'kreci sie': testy, czytanie z nowym numerem, testy... Odciski akcji rozne (pole n),
    tresci bledow rozne (run-xxx), a kod NIGDY sie nie zmienia."""
    if h.total % 2 == 0:
        return Action("run_tests", {})
    return Action("read_file", {"path": "Foo.cs", "n": h.total})


def policy_oscillate(h: History):
    """Przelacza Foo.cs miedzy dwiema wersjami, ktore obie nie dzialaja. Notatka 'note' rozni
    odciski akcji, wiec LOOP_CYCLE nie widzi cyklu - a DRZEWO wraca do znanego stanu."""
    k = h.total // 2
    if h.total % 2 == 1:
        return Action("run_tests", {})
    version = "v1" if k % 2 == 0 else "v2"
    return Action("edit_file", {"path": "Foo.cs", "note": f"proba {k}",
                                "text": f"class Foo {{ int X() => /* {version} */ y; }}\n"})


def policy_long_task(h: History, total: int = 30):
    """Dlugie zadanie, ktorego decyzja zalezy TYLKO od licznika (nie od starej historii):
    nieparzyste kroki czytaja notatki (duzy wynik), parzyste wysylaja powiadomienie."""
    if h.total >= total:
        return Done(f"{total} krokow")
    if h.total % 2 == 0:
        return Action("read_file", {"path": "notes.txt", "i": h.total})
    return Action("notify", {"msg": f"krok {h.total}"})


def policy_needs_old_history(h: History):
    """ZLY model: decyzja zalezy od KROKU 1, ktory po kompaktowaniu wypada z okna."""
    if h.total < 6:
        return Action("read_file", {"path": "notes.txt", "i": h.total})
    first = h[0].n if h else None          # po kompaktowaniu to NIE jest krok 1
    return Done(f"pierwszy widoczny krok: {first}")


def policy_notify_then_finish(h: History):
    return _seq(h, [Action("notify", {"msg": "start"}), Action("notify", {"msg": "koniec"})])


def policy_charge_twice(h: History):
    return _seq(h, [Action("fetch", {}), Action("charge", {"amount": 100})])
