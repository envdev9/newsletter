"""Swiat testowy: narzedzia z licznikami efektow ubocznych + deterministyczne 'modele' (policy)."""
from __future__ import annotations

from agentloop import Action, Done, Step, Tool, TransientError


class World:
    def __init__(self, fetch_failures: int = 0) -> None:
        self.files: dict[str, str] = {"Foo.cs": "class Foo { int X() => y; }"}
        self.outbox: dict[str, tuple[str, str]] = {}   # klucz -> (wiadomosc, ORYGINALNY wynik)
        self.notify_calls = 0
        self.charges: list[int] = []
        self.fetch_failures = fetch_failures
        self.fetch_calls = 0
        self.test_runs = 0

    def read_file(self, a, key):
        return self.files[a["path"]]

    def edit_file(self, a, key):
        self.files[a["path"]] = a["text"]
        return "ok"

    def run_tests(self, a, key):
        self.test_runs += 1
        if "fixed" in self.files["Foo.cs"]:
            return "PASS 12 tests"
        raise AssertionError(f"FAIL CS0103: name 'y' does not exist at Foo.cs:{10 + self.test_runs}")

    def notify(self, a, key):
        """Dedup po kluczu, ale (inaczej niz w #14) powtorka dostaje ORYGINALNY wynik."""
        self.notify_calls += 1
        if key in self.outbox:
            return self.outbox[key][1]
        self.outbox[key] = (a["msg"], "sent")
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


def policy_notify_then_finish(steps):
    seq = [Action("notify", {"msg": "start"}), Action("notify", {"msg": "koniec"})]
    return seq[len(steps)] if len(steps) < len(seq) else Done("ok")


def policy_charge_twice(steps):
    seq = [Action("fetch", {}), Action("charge", {"amount": 100})]
    return seq[len(steps)] if len(steps) < len(seq) else Done("ok")


def policy_fetch_forever(steps):
    return Action("fetch", {"n": len(steps)})   # zawsze inny odcisk; serwer ciagle 503


def policy_never_ends(steps):
    return Action("read_file", {"path": "Foo.cs", "n": len(steps)})


def policy_tripwire(steps):
    """'Model', ktory nie powinien byc wolany po zamknieciu biegu."""
    raise AssertionError("policy wolana na zamknietym biegu")


def policy_nondeterministic_after_done(steps):
    """Pierwszy raz konczy po 2 krokach (Done); zapytany PONOWNIE o ten sam stan proponuje
    jeszcze jedna, NOWA akcje (jak niedeterministyczny LLM, ktory 'zmienil zdanie')."""
    if len(steps) < 2:
        return policy_notify_then_finish(steps)
    policy_nondeterministic_after_done.asked += 1
    if policy_nondeterministic_after_done.asked == 1:
        return Done("ok")
    return Action("notify", {"msg": "dodatkowa"}) if len(steps) == 2 else Done("ok")


policy_nondeterministic_after_done.asked = 0
