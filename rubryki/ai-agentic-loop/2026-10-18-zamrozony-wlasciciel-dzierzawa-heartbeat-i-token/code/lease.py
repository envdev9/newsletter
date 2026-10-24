"""Dzierzawa (lease) z heartbeatem i tokenem ogrodzeniowym (fencing token) - wydanie #20.

LeaseStore  - stan dzierzawy w pliku JSON {owner, token, expires}; kazda zmiana to transakcja pod
              krotkim flock(2) na osobnym pliku .mx (flock sluzy tu tylko jako mutex CAS, NIE jako dzierzawa).
              token rosnie o 1 przy KAZDYM przejeciu dzierzawy (takze po wygasnieciu).
Heartbeat   - watek odnawiajacy dzierzawe co ttl/3; po nieudanym odnowieniu ustawia .lost.
FencedLog   - zasob, ktory sam pilnuje tokenu: odrzuca zapis z tokenem mniejszym niz najwyzszy widziany.

Czas: time.monotonic() (CLOCK_MONOTONIC jest wspolny dla procesow na jednym hoscie Linux; po restarcie
maszyny zeruje sie - to ograniczenie tej wersji). Tylko stdlib, tylko Linux. Python 3.10.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Iterator, Optional


@dataclass(frozen=True)
class Lease:
    owner: str
    token: int
    expires: float


class StaleToken(Exception):
    """Zasob odrzucil zapis: token starszy niz najwyzszy widziany."""


class LeaseStore:
    def __init__(self, path: str, ttl: float) -> None:
        self.path, self.ttl = path, ttl
        self.mx = path + ".mx"

    @contextlib.contextmanager
    def _txn(self) -> Iterator[dict]:
        fd = os.open(self.mx, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)                     # blokujaco, sekcja krytyczna ~mikrosekundy
            try:
                with open(self.path) as f:
                    st = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                st = {"owner": None, "token": 0, "expires": 0.0}
            before = dict(st)
            yield st
            if st != before:
                tmp = f"{self.path}.tmp.{os.getpid()}"          # unikalna nazwa (lekcja z #19)
                with open(tmp, "w") as f:
                    json.dump(st, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
        finally:
            os.close(fd)

    def try_acquire(self, owner: str) -> Optional[Lease]:
        with self._txn() as st:
            now = time.monotonic()
            if st["owner"] is not None and st["expires"] > now:
                return None                                     # zywa dzierzawa cudza (albo wlasna)
            st["owner"], st["token"], st["expires"] = owner, st["token"] + 1, now + self.ttl
            return Lease(owner, st["token"], st["expires"])

    def acquire_wait(self, owner: str, timeout: float, poll: float = 0.02) -> Optional[Lease]:
        t0 = time.monotonic()
        while True:
            lease = self.try_acquire(owner)
            if lease or time.monotonic() - t0 >= timeout:
                return lease
            time.sleep(poll)

    def renew(self, owner: str, token: int) -> bool:
        with self._txn() as st:
            now = time.monotonic()
            if st["owner"] != owner or st["token"] != token or st["expires"] <= now:
                return False                                    # wygasla albo przejeta -> utrata
            st["expires"] = now + self.ttl
            return True

    def is_valid(self, owner: str, token: int) -> bool:
        with self._txn() as st:
            return st["owner"] == owner and st["token"] == token and st["expires"] > time.monotonic()

    def release(self, owner: str, token: int) -> None:
        with self._txn() as st:
            if st["owner"] == owner and st["token"] == token:
                st["owner"], st["expires"] = None, 0.0          # token ZOSTAJE (nie cofamy licznika)

    def peek(self) -> dict:
        with self._txn() as st:
            return dict(st)


class Heartbeat:
    def __init__(self, store: LeaseStore, lease: Lease, interval: Optional[float] = None) -> None:
        self.store, self.lease = store, lease
        self.interval = interval or store.ttl / 3
        self.lost = threading.Event()
        self.renewals = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            if self.store.renew(self.lease.owner, self.lease.token):
                self.renewals += 1
            else:
                self.lost.set()
                return

    def start(self) -> "Heartbeat":
        self._t.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._t.join(timeout=2)


class FencedLog:
    """Dziennik-zasob. Test tokenu i dopisanie wiersza sa atomowe wzgledem siebie (flock na .fence)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.fence = path + ".fence"

    def append(self, token: int, line: str) -> None:
        fd = os.open(self.fence, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            raw = os.pread(fd, 32, 0).strip()
            seen = int(raw) if raw else 0
            if token < seen:
                raise StaleToken(f"token {token} < {seen}")
            os.ftruncate(fd, 0)
            os.pwrite(fd, str(token).encode(), 0)
            self.append_unfenced(line)
        finally:
            os.close(fd)

    def append_unfenced(self, line: str) -> None:
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (line + "\n").encode())
        finally:
            os.close(fd)
