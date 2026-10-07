"""Swiat testowy: narzedzia z licznikami efektow ubocznych + deterministyczne 'modele' (policy)."""
from __future__ import annotations

from agentloop import Action, Done, Step, Tool, TransientError


class World:
    def __init__(self, fetch_failures: int = 0) -> None:
        self.files: dict[str, str] = {"Foo.cs": "class Foo { int X() => y; }"}
        self.outbox: dict[str, str] = {}       # klucz idempotencji -> wiadomosc (dedup)
        self.notify_calls = 0                  # ile razy FAKTYCZNIE wywolano notify
        self.charges: list[int] = []           # narzedzie bez dedupu
        self.fetch_failures = fetch_failures
        self.fetch_calls = 0
        self.test_runs = 0

    # -- narzedzia (fn(args, key) -> str)
    def read_file(self, a, key):
        return self.files[a["path"]]

    def edit_file(self, a, key):               # "ustaw zawartosc" = naturalnie idempotentne
        self.files[a["path"]] = a["text"]
        return "ok"

    def run_tests(self, a, key):
        self.test_runs += 1
        if "fixed" in self.files["Foo.cs"]:
            return "PASS 12 tests"
        line = 10 + self.test_runs             # numer linii sie zmienia - sygnatura ma go ignorowac
        raise AssertionError(f"FAIL CS0103: name 'y' does not exist at Foo.cs:{line}")

    def notify(self, a, key):
        self.notify_calls += 1
        if key in self.outbox:                 # ten sam klucz -> efekt raz
            return "dedup (already sent)"
        self.outbox[key] = a["msg"]
        return "sent"

    def charge(self, a, key):                  # nie umie dedupowac
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
            "run_tests": Tool("run_tests", self.run_tests),
            "notify": Tool("notify", self.notify, honors_key=True, side_effect=True),
            "charge": Tool("charge", self.charge, honors_key=False, side_effect=True),
            "fetch": Tool("fetch", self.fetch),
        }


# ---------------------------------------------------------------- 'modele'
def policy_happy(steps: list[Step]):
    seq = [Action("run_tests", {}),
           Action("edit_file", {"path": "Foo.cs", "text": "class Foo { int X() => 1; /* fixed */ }"}),
           Action("run_tests", {})]
    return seq[len(steps)] if len(steps) < len(seq) else Done("testy zielone")


def policy_same_action(steps):
    return Action("run_tests", {})              # ciagle to samo


def policy_ping_pong(steps):
    # edytuje ten sam tekst (nie naprawia), potem testuje - cykl okresu 2
    return Action("edit_file", {"path": "Foo.cs", "text": "x"}) if len(steps) % 2 == 0 else Action("run_tests", {})


def policy_varied_but_stuck(steps):
    # kazda edycja ma inna tresc (inny odcisk), ale nigdy nie naprawia - test pada tak samo
    n = len(steps)
    if n % 2 == 0:
        return Action("edit_file", {"path": "Foo.cs", "text": f"// proba {n}\nclass Foo {{ int X() => y; }}"})
    return Action("run_tests", {})


def policy_notify_then_finish(steps):
    seq = [Action("notify", {"msg": "start"}), Action("notify", {"msg": "koniec"})]
    return seq[len(steps)] if len(steps) < len(seq) else Done("ok")


def policy_charge_twice(steps):
    seq = [Action("fetch", {}), Action("charge", {"amount": 100})]
    return seq[len(steps)] if len(steps) < len(seq) else Done("ok")


def policy_fetch_once(steps):
    return Action("fetch", {}) if not steps else Done("ok")


def policy_never_ends(steps):
    return Action("read_file", {"path": "Foo.cs", "n": len(steps)})   # zawsze inny odcisk
