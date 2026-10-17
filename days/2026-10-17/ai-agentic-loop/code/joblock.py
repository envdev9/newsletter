"""Blokady dziennika agenta (wydanie #19): trzy warianty, zeby je POROWNAC na prawdziwych procesach.

  FlockLock  - flock(2) na OSOBNYM pliku .lock. Jadro zwalnia blokade, gdy proces ginie (takze kill -9).
               To jest wariant docelowy.
  ExclLock   - klasyczny "plik-zamek" tworzony O_CREAT|O_EXCL. Po kill -9 zostaje na dysku (martwy lock).
               stale_check=True dodaje wykrywanie martwego wlasciciela (pid + czas startu z /proc);
               takeover_delay to haczyk TESTOWY: poszerza okno miedzy "sprawdzilem, ze martwy" a "usuwam".
  pid_alive  - czy proces zyje; z czasem startu odporny na ponowne uzycie PID-u.

Tylko stdlib, tylko Linux (/proc, fcntl.flock). Python 3.10.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from typing import Optional


class LockBusy(Exception):
    """Blokada zajeta przez zywego wlasciciela (info w .holder)."""

    def __init__(self, msg: str, holder: Optional[dict] = None) -> None:
        super().__init__(msg)
        self.holder = holder


def proc_start_ticks(pid: int) -> Optional[int]:
    """Pole 22 z /proc/<pid>/stat (starttime w tickach od startu systemu). None gdy procesu nie ma.
    Nazwa procesu (pole 2) moze zawierac spacje i nawiasy, wiec tniemy po OSTATNIM ')'."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            raw = f.read().decode("utf-8", "replace")
    except (FileNotFoundError, ProcessLookupError):
        return None
    rest = raw[raw.rindex(")") + 2:].split()
    return int(rest[19])          # pole 22 licząc od 1; po usunieciu pol 1-2 to indeks 19


def pid_alive(pid: int, start: Optional[int] = None) -> bool:
    """start=None: samo "czy taki PID istnieje" (naiwnie, podatne na ponowne uzycie PID).
    start=int: PID istnieje I ma ten sam czas startu. Zombie (Z) liczymy jako martwy."""
    ticks = proc_start_ticks(pid)
    if ticks is None:
        return False
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            raw = f.read().decode("utf-8", "replace")
        if raw[raw.rindex(")") + 2:].split()[0] == "Z":
            return False
    except FileNotFoundError:
        return False
    return start is None or ticks == start


def _meta() -> dict:
    return {"pid": os.getpid(), "start": proc_start_ticks(os.getpid()), "t": round(time.time(), 3)}


def read_meta(path: str) -> Optional[dict]:
    try:
        with open(path, "rb") as f:
            raw = f.read()
        return json.loads(raw) if raw.strip() else None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


class FlockLock:
    """Blokada przez flock(LOCK_EX) na pliku `path` (np. journal.jsonl.lock).

    WAZNE: to musi byc osobny plik. Dziennik jest podmieniany przez os.replace (compact), a flock
    siedzi na i-wezle, nie na nazwie. Pliku .lock NIE usuwamy po zwolnieniu (wyscig z unlink).
    Metadane (pid) sa tylko diagnostyczne - o wlasnosci decyduje jadro, nie ich tresc.
    """

    def __init__(self, path: str, timeout: float = 0.0, poll: float = 0.005) -> None:
        self.path, self.timeout, self.poll = path, timeout, poll
        self.fd: Optional[int] = None
        self.waited = 0.0

    def acquire(self) -> "FlockLock":
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)    # fd nieodziedziczalny (PEP 446)
        t0 = time.monotonic()
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    os.close(fd)
                    raise
                if time.monotonic() - t0 >= self.timeout:
                    os.close(fd)
                    holder = read_meta(self.path)
                    raise LockBusy(f"zajete (wlasciciel wg metadanych: {holder})", holder)
                time.sleep(self.poll)
        self.waited = time.monotonic() - t0
        os.ftruncate(fd, 0)
        os.pwrite(fd, json.dumps(_meta()).encode(), 0)
        self.fd = fd
        return self

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)          # zamkniecie ostatniego fd opisu pliku zwalnia flock
            self.fd = None

    def __enter__(self) -> "FlockLock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()


class ExclLock:
    """Plik-zamek O_CREAT|O_EXCL. Atomowe jest tylko TWORZENIE; reszta (czy wlasciciel zyje, usuniecie
    martwego zamka) to osobne kroki - i tam siedzi wyscig."""

    def __init__(self, path: str, stale_check: bool = False, takeover_delay: float = 0.0) -> None:
        self.path, self.stale_check, self.takeover_delay = path, stale_check, takeover_delay
        self.held = False
        self.took_over = False

    def _create(self) -> bool:
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        os.write(fd, json.dumps(_meta()).encode())
        os.close(fd)
        return True

    def try_acquire(self) -> bool:
        if self._create():
            self.held = True
            return True
        if not self.stale_check:
            return False
        meta = read_meta(self.path)
        if meta is None:                  # pusty/urwany plik: wlasciciel mogl dopiero co utworzyc - nie ruszamy
            return False
        if pid_alive(meta["pid"], meta.get("start")):
            return False
        time.sleep(self.takeover_delay)   # <- haczyk testowy: okno miedzy ocena a usunieciem
        try:
            os.unlink(self.path)          # <- usuwa DOWOLNY plik pod ta nazwa, tez swiezy zamek innego procesu
        except FileNotFoundError:
            pass
        if self._create():
            self.held = self.took_over = True
            return True
        return False

    def acquire(self, timeout: float = 0.0, poll: float = 0.005) -> "ExclLock":
        t0 = time.monotonic()
        while not self.try_acquire():
            if time.monotonic() - t0 >= timeout:
                raise LockBusy(f"zajete (wlasciciel wg metadanych: {read_meta(self.path)})", read_meta(self.path))
            time.sleep(poll)
        return self

    def release(self) -> None:
        if self.held:
            meta = read_meta(self.path)
            if meta and meta.get("pid") == os.getpid():
                try:
                    os.unlink(self.path)
                except FileNotFoundError:
                    pass
            self.held = False
