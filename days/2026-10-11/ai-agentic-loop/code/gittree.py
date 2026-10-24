"""Hash drzewa robocze przez git: `git add -A` do OSOBNEGO indeksu + `git write-tree`.

Dlaczego osobny GIT_DIR: nie dotykamy indeksu ani bazy obiektow repo uzytkownika (write-tree na
prawdziwym indeksie tez nie zmienia HEAD, ale `add -A` zmieniloby staging uzytkownika).
Wynik to SHA-1 obiektu drzewa - ten sam, ktory git policzylby przy commicie tych plikow.
Tylko stdlib + binarka `git` (testowane: 2.34.1).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

# odpowiednik stalej listy `ignore` z tree_hash (w info/exclude tymczasowego GIT_DIR)
DEFAULT_EXCLUDE = ("bin/", "obj/", "node_modules/", "__pycache__/")


class GitError(RuntimeError):
    pass


class GitTreeObserver:
    """Callable () -> str (hash drzewa), do uzycia jako `observer` nadzorcy. Pamiec: osobny GIT_DIR
    w /tmp; `add -A` ZAPISUJE blob kazdej zmienionej tresci, wiec close() jest obowiazkowe."""

    def __init__(self, root: str, exclude: tuple[str, ...] = DEFAULT_EXCLUDE,
                 persistent_index: bool = True) -> None:
        self.root = os.path.abspath(root)
        self.persistent_index = persistent_index
        self.gitdir = tempfile.mkdtemp(prefix="prasowka-loop4-gitdir-")
        self.calls = 0
        env = {k: v for k, v in self._env().items() if k not in ("GIT_DIR", "GIT_WORK_TREE")}
        r = subprocess.run(["git", "init", "-q", "--bare", self.gitdir], env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise GitError(r.stderr.strip())
        info = os.path.join(self.gitdir, "info")
        os.makedirs(info, exist_ok=True)
        with open(os.path.join(info, "exclude"), "w", encoding="utf-8") as f:
            f.write("\n".join(exclude) + "\n")

    def _env(self) -> dict:
        env = dict(os.environ)
        env.update({"GIT_DIR": self.gitdir, "GIT_WORK_TREE": self.root,
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_TERMINAL_PROMPT": "0"})
        return env

    def _git(self, *args: str) -> str:
        # -c: bez konwersji konca linii (hash ma byc tresci, nie ustawien uzytkownika) i bez
        # globalnego core.excludesFile (nie powinien wplywac na wynik)
        cmd = ["git", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
               "-c", "core.excludesFile=", *args]
        r = subprocess.run(cmd, cwd=self.root, env=self._env(), capture_output=True, text=True)
        if r.returncode != 0:
            raise GitError(f"git {' '.join(args)}: {r.stderr.strip()}")
        return r.stdout.strip()

    def __call__(self) -> str:
        self.calls += 1
        if not self.persistent_index:
            idx = os.path.join(self.gitdir, "index")
            if os.path.exists(idx):
                os.remove(idx)
        self._git("add", "-A", "--", ".")
        return self._git("write-tree")

    def object_bytes(self) -> int:
        total = 0
        for dp, _dn, fns in os.walk(os.path.join(self.gitdir, "objects")):
            for fn in fns:
                total += os.path.getsize(os.path.join(dp, fn))
        return total

    def close(self) -> None:
        shutil.rmtree(self.gitdir, ignore_errors=True)

    def __enter__(self) -> "GitTreeObserver":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
