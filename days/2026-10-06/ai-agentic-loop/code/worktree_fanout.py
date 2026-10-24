#!/usr/bin/env python3
"""Rownolegli "agenci" na osobnych git worktree - realny git, tymczasowe repo w /tmp.

ROLE AGENTOW GRAJA FUNKCJE PYTHONA (edytuja pliki i robia commit). Nie ma tu zadnego
modelu ani Claude Code. Realne jest wszystko, co robi git: worktree, branche, merge,
konflikt, odmowy usuniecia, sprzatanie.

Uruchomienie: python3 worktree_fanout.py   (exit 0 = wszystkie asercje przeszly)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

IDENT = ["-c", "user.name=demo", "-c", "user.email=demo@example.invalid"]
PASS = 0
FAIL = 0
TMP = ""


def git(cwd, *args, check=True):
    """Jedno wywolanie gita; zwraca (kod, stdout+stderr)."""
    p = subprocess.run(["git", *IDENT, *args], cwd=cwd, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    if check and p.returncode != 0:
        raise RuntimeError("git %s -> %d: %s" % (" ".join(args), p.returncode, out))
    return p.returncode, out


def show(text):
    print(text.replace(TMP, "<TMP>"))


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [OK]   " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name)


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


SEED = {
    "Pricing.cs": "class Pricing {\n    decimal Net(decimal gross) => gross / 1.23m;\n}\n",
    "Orders.cs": "class Orders {\n    int Count() => 0;\n}\n",
    "CHANGELOG.md": "# Changelog\n\n## Unreleased\n",
}


def make_repo(root):
    os.makedirs(root)
    git(root, "init", "-q", "-b", "main")
    for name, body in SEED.items():
        write(os.path.join(root, name), body)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")


# --- "agenci": deterministyczne skrypty zamiast modelu -------------------------------
def agent_a(wt):
    write(os.path.join(wt, "Pricing.cs"),
          "class Pricing {\n    decimal Net(decimal gross) => Math.Round(gross / 1.23m, 2);\n}\n")
    with open(os.path.join(wt, "CHANGELOG.md"), "a", encoding="utf-8") as f:
        f.write("- Pricing: zaokraglenie do groszy\n")


def agent_b(wt):
    write(os.path.join(wt, "Orders.cs"),
          "class Orders {\n    int Count() => items.Count;\n}\n")


def agent_c(wt):
    with open(os.path.join(wt, "CHANGELOG.md"), "a", encoding="utf-8") as f:
        f.write("- Orders: licznik z kolekcji\n")


def agent_d(wt):
    pass  # agent, ktory nic nie zmienil


def run_agent(fn, wt, branch, log):
    t0 = time.monotonic()
    time.sleep(0.4)  # "praca" - ma sie nakladac z innymi
    fn(wt)
    if git(wt, "status", "--porcelain")[1]:
        git(wt, "add", "-A")
        git(wt, "commit", "-q", "-m", "agent " + branch)
    log[branch] = (t0, time.monotonic())


def main():
    global TMP
    TMP = tempfile.mkdtemp(prefix="prasowka-wt-", dir="/tmp")
    repo = os.path.join(TMP, "repo")
    try:
        make_repo(repo)

        print("\n== 1. BEZ worktree: dwoch agentow w jednym katalogu ==")
        # agent A zapisal swoja wersje, agent B (ktory czytal plik PRZED zmiana A)
        # zapisuje cala swoja wersje -> zmiana A znika bez zadnego bledu.
        before = read(os.path.join(repo, "Pricing.cs"))
        agent_a(repo)
        write(os.path.join(repo, "Pricing.cs"),
              before.replace("gross / 1.23m", "gross / (1 + VatRate)"))
        res = read(os.path.join(repo, "Pricing.cs"))
        print(res.strip())
        check("lost update: zaokraglenie agenta A zniknelo, git nic nie zglosil", "Math.Round" not in res)
        git(repo, "checkout", "-q", "--", ".")
        git(repo, "clean", "-fdq")
        check("repo wrocilo do czystego stanu", git(repo, "status", "--porcelain")[1] == "")

        print("\n== 2. worktree: 4 agentow, osobne katalogi i branche ==")
        agents = {"agent-a": agent_a, "agent-b": agent_b, "agent-c": agent_c, "agent-d": agent_d}
        wts = {}
        for br in agents:
            wts[br] = os.path.join(TMP, "wt-" + br)
            git(repo, "worktree", "add", "-q", "-b", br, wts[br], "main")
        show(git(repo, "worktree", "list")[1])
        gitfile = read(os.path.join(wts["agent-a"], ".git")).strip()
        show("zawartosc wt-agent-a/.git (to PLIK, nie katalog): " + gitfile)
        check(".git w worktree jest plikiem 'gitdir: ...'", gitfile.startswith("gitdir:"))
        check("4 worktree + glowny = 5 wpisow", len(git(repo, "worktree", "list")[1].splitlines()) == 5)

        # ten sam branch w dwoch worktree - git odmawia
        code, out = git(repo, "worktree", "add", os.path.join(TMP, "wt-dup"), "agent-a", check=False)
        show("proba drugiego checkoutu agent-a -> kod %d: %s" % (code, out))
        check("ten sam branch w drugim worktree odrzucony", code != 0)

        log = {}
        threads = [threading.Thread(target=run_agent, args=(fn, wts[br], br, log)) for br, fn in agents.items()]
        t0 = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.monotonic() - t0
        busy = sum(e - s for s, e in log.values())
        print("czas sciany %.2fs, suma pracy agentow %.2fs" % (wall, busy))
        check("agenci pracowali rownolegle (czas sciany < 60% sumy)", wall < 0.6 * busy)
        check("glowny katalog nietkniety w trakcie pracy agentow", git(repo, "status", "--porcelain")[1] == "")
        check("agent-a nie widzi pliku agenta-b (Orders.cs bez zmian)",
              "items.Count" not in read(os.path.join(wts["agent-a"], "Orders.cs")))
        print(git(repo, "log", "--oneline", "--all", "--graph")[1])

        print("\n== 3. sprzatanie agenta bez zmian i odmowy gita ==")
        # d: zero commitow ponad main i czysty katalog -> mozna zdjac bez sladu
        ahead = git(repo, "rev-list", "--count", "main..agent-d")[1]
        check("agent-d: 0 commitow ponad main", ahead == "0")
        git(repo, "worktree", "remove", wts["agent-d"])
        git(repo, "branch", "-d", "agent-d")
        check("agent-d usuniety (worktree + branch)", not os.path.exists(wts["agent-d"]))
        # brudny worktree: remove odmawia bez --force
        write(os.path.join(wts["agent-b"], "scratch.txt"), "niezacommitowane\n")
        code, out = git(repo, "worktree", "remove", wts["agent-b"], check=False)
        show("remove na brudnym worktree -> kod %d: %s" % (code, out))
        check("brudny worktree: remove odmawia", code != 0 and os.path.exists(wts["agent-b"]))
        os.remove(os.path.join(wts["agent-b"], "scratch.txt"))
        # branch wciaz wystawiony w worktree: -d odmawia (inny powod niz ponizej)
        code, out = git(repo, "branch", "-d", "agent-b", check=False)
        show("branch -d agent-b (wystawiony w worktree) -> kod %d: %s" % (code, out))
        check("branch wystawiony w worktree: -d odmawia", code != 0)
        # zdejmujemy worktree (juz czysty), ale branch ma niezmergowany commit: -d znowu odmawia
        git(repo, "worktree", "remove", wts["agent-b"])
        code, out = git(repo, "branch", "-d", "agent-b", check=False)
        show("branch -d agent-b (niezmergowany) -> kod %d: %s" % (code, out))
        check("niezmergowany branch: -d odmawia, praca agenta nie ginie", code != 0 and "not fully merged" in out)

        print("\n== 4. merge: bez konfliktu, potem konflikt ==")
        for br in ("agent-a", "agent-b"):
            code, out = git(repo, "merge", "--no-ff", "-m", "merge " + br, br, check=False)
            show("merge %s -> kod %d" % (br, code))
            check("merge %s czysty" % br, code == 0)
        code, out = git(repo, "merge", "--no-ff", "-m", "merge agent-c", "agent-c", check=False)
        show("merge agent-c -> kod %d\n%s" % (code, out))
        check("merge agent-c: konflikt (obaj dopisali pod tym samym naglowkiem)", code != 0 and "CONFLICT" in out)
        unmerged = git(repo, "diff", "--name-only", "--diff-filter=U")[1]
        print("pliki w konflikcie:", unmerged)
        check("konflikt dotyczy tylko CHANGELOG.md", unmerged == "CHANGELOG.md")
        print(read(os.path.join(repo, "CHANGELOG.md")).strip())
        git(repo, "merge", "--abort")
        check("merge --abort przywraca czyste drzewo", git(repo, "status", "--porcelain")[1] == "")

        # rozwiazanie: "agent-integrator" rebase'uje c na main i laczy oba wpisy
        git(wts["agent-c"], "rebase", "main", check=False)
        write(os.path.join(wts["agent-c"], "CHANGELOG.md"),
              "# Changelog\n\n## Unreleased\n- Pricing: zaokraglenie do groszy\n- Orders: licznik z kolekcji\n")
        git(wts["agent-c"], "add", "CHANGELOG.md")
        env_cont = subprocess.run(["git", *IDENT, "rebase", "--continue"], cwd=wts["agent-c"],
                                  capture_output=True, text=True, env={**os.environ, "GIT_EDITOR": "true"})
        check("rebase --continue po recznym scaleniu OK", env_cont.returncode == 0)
        code, out = git(repo, "merge", "--ff-only", "agent-c", check=False)
        check("po rebase agent-c wchodzi fast-forward", code == 0)
        final = read(os.path.join(repo, "CHANGELOG.md"))
        check("CHANGELOG ma oba wpisy", "zaokraglenie" in final and "licznik" in final)

        print("\n== 5. sprzatanie koncowe ==")
        for br in ("agent-a", "agent-b", "agent-c"):
            if os.path.exists(wts[br]):
                git(repo, "worktree", "remove", wts[br])
            git(repo, "branch", "-d", br)  # teraz zmergowane, wiec -d przechodzi
        git(repo, "worktree", "prune")
        show(git(repo, "worktree", "list")[1])
        check("zostal tylko glowny worktree", len(git(repo, "worktree", "list")[1].splitlines()) == 1)
        check("zostal tylko branch main", git(repo, "branch", "--format=%(refname:short)")[1] == "main")
        check("katalog .git/worktrees pusty lub nieobecny",
              not os.path.isdir(os.path.join(repo, ".git", "worktrees"))
              or os.listdir(os.path.join(repo, ".git", "worktrees")) == [])
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
        check("tymczasowy katalog usuniety", not os.path.exists(TMP))
    print("\nWYNIK: %d/%d" % (PASS, PASS + FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
