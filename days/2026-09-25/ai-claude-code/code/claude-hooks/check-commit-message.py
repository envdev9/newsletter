#!/usr/bin/env python3
"""PreToolUse hook Claude Code: wymusza Conventional Commits w `git commit`.

Wpinany pod PreToolUse z matcherem "Bash". Claude Code podaje na stdin JSON:
  {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"...\""}, ...}

Kody wyjscia:
  0 - komenda dozwolona (albo to w ogole nie jest `git commit`)
  2 - komenda ZABLOKOWANA, stderr wraca do Claude jako informacja zwrotna

Co jest sprawdzane (pierwsza linia wiadomosci = "subject"):
  * format  typ(scope)!: opis   gdzie typ in TYPES, scope opcjonalny
  * dlugosc subjectu <= 72 znaki
  * brak kropki na koncu subjectu
  * jesli jest body, druga linia musi byc pusta

Swiadome ograniczenia (hook NIE zgaduje, tylko przepuszcza):
  * `git commit` bez -m/-F (otworzy edytor)   -> przepuszczony
  * `git commit -F plik` / `--file`           -> przepuszczony (nie czytamy pliku)
  * `--amend --no-edit`                       -> przepuszczony
  * subject zaczynajacy sie od Merge/Revert/fixup!/squash! -> przepuszczony
  * wiadomosc budowana zmienna powloki ("$MSG") -> przepuszczona (nie znamy wartosci)
"""
import json
import re
import shlex
import sys

TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")
SUBJECT_RE = re.compile(r"^(?:%s)(?:\([a-z0-9][a-z0-9._/-]*\))?!?: \S.*$" % "|".join(TYPES))
MAX_SUBJECT = 72
SEPARATORS = {";", "&&", "||", "|", "&"}
# opcje globalne gita, ktore biora argument (git -C dir commit ...)
GLOBAL_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2\b", re.DOTALL)


def split_segments(tokens):
    seg = []
    for tok in tokens:
        if tok in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(tok)
    if seg:
        yield seg


def commit_args(segment):
    """Zwraca liste argumentow po `git ... commit`, albo None gdy to nie commit."""
    if not segment or segment[0] != "git":
        return None
    i = 1
    while i < len(segment):
        tok = segment[i]
        if tok in GLOBAL_OPTS_WITH_ARG:
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            break
    if i < len(segment) and segment[i] == "commit":
        return segment[i + 1:]
    return None


def extract_messages(args):
    """Zwraca (messages, opaque). opaque=True gdy nie da sie ustalic tresci."""
    messages, opaque, i = [], False, 0
    while i < len(args):
        a = args[i]
        if a in ("-F", "--file") or a.startswith("--file=") or (a.startswith("-F") and len(a) > 2):
            opaque = True
        elif a == "--message" or a == "-m":
            if i + 1 < len(args):
                messages.append(args[i + 1])
                i += 1
        elif a.startswith("--message="):
            messages.append(a.split("=", 1)[1])
        elif a.startswith("-") and not a.startswith("--") and "m" in a[1:]:
            # sklejone flagi: -am "msg"  albo  -m"msg"  albo  -amMSG
            head, _, tail = a[1:].partition("m")
            if tail:
                messages.append(tail)
            elif i + 1 < len(args):
                messages.append(args[i + 1])
                i += 1
        i += 1
    return messages, opaque


def resolve_heredoc(message, full_command):
    """Claude Code czesto pisze:  -m "$(cat <<'EOF' ... EOF )"  - wyciagamy body."""
    if "$(" not in message and "`" not in message:
        return message
    m = HEREDOC_RE.search(full_command)
    return m.group(3) if m else None  # None = nie umiemy ustalic


def validate(message):
    lines = message.split("\n")
    subject = lines[0].rstrip()
    problems = []
    if re.match(r"^(Merge |Revert |fixup! |squash! )", subject):
        return problems
    if not SUBJECT_RE.match(subject):
        problems.append("subject nie pasuje do formatu 'typ(scope)!: opis' "
                        "(typy: %s)" % ", ".join(TYPES))
    if len(subject) > MAX_SUBJECT:
        problems.append("subject ma %d znakow, limit to %d" % (len(subject), MAX_SUBJECT))
    if subject.endswith("."):
        problems.append("subject nie powinien konczyc sie kropka")
    if len(lines) > 1 and lines[1].strip() != "":
        problems.append("miedzy subjectem a body musi byc pusta linia")
    return problems


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print("check-commit-message: nie moge sparsowac JSON ze stdin: %s" % exc, file=sys.stderr)
        return 1

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "commit" not in command:
        return 0

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return 0  # niedomkniety cudzyslow itp. - niech powloka sama zglosi blad

    for segment in split_segments(tokens):
        args = commit_args(segment)
        if args is None:
            continue
        messages, opaque = extract_messages(args)
        if opaque or not messages:
            continue
        message = resolve_heredoc(messages[0], command)
        if message is None or message.lstrip().startswith("$"):
            continue
        problems = validate(message.strip("\n"))
        if problems:
            print(
                "BLOKADA: wiadomosc commita lamie konwencje (Conventional Commits):\n"
                + "".join("  - %s\n" % p for p in problems)
                + "Subject: %r\n" % message.strip("\n").split("\n")[0]
                + "Przyklad poprawnego: feat(orders): dodaj filtrowanie po statusie\n"
                "Popraw wiadomosc i ponow `git commit`.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
