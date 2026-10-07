#!/usr/bin/env python3
"""ctxlazy - koszt kontekstowy definicji narzedzi: eager vs leniwe ladowanie (tool search).

Dane SYNTETYCZNE (deterministyczne, bez losowosci). Tokeny = bajty/4 (szacunek, nie tokenizer).
Zadne API/model nie jest wywolywane. Mierzymy: co trafia do kontekstu i czy wyszukiwarka
znajduje potrzebne narzedzia - NIE zachowanie modelu.

Uzycie:
  python3 -B ctxlazy.py catalog          # statystyki katalogu
  python3 -B ctxlazy.py run [--k 5]      # strategie na scenariuszu 12 zadan
  python3 -B ctxlazy.py sweep            # wrazliwosc: k oraz rozmiar katalogu
  python3 -B ctxlazy.py breakeven        # ile narzedzi trzeba uzyc, zeby leniwe przestalo sie oplacac
"""
import json
import math
import re
import sys

# ---------------------------------------------------------------- katalog syntetyczny
VERBS = {
    "list": "Returns a paginated list of {n}s in {s}. Supports filtering by status, owner and creation date, "
            "ordering and cursor-based pagination. Results are limited to 100 items per page.",
    "get": "Fetches full details of a single {n} in {s} by its identifier, including metadata, "
           "timestamps and links to related objects. Returns an error if the {n} does not exist.",
    "create": "Creates a new {n} in {s}. Requires a title or name; optional fields can be supplied. "
              "Returns the created {n} with its generated identifier. Fails when a duplicate exists.",
    "update": "Updates selected fields of an existing {n} in {s}. Only supplied fields are changed; "
              "omitted fields keep their value. Returns the updated {n}.",
    "delete": "Permanently deletes a {n} from {s}. This action cannot be undone. "
              "Returns an empty body on success and an error if the {n} is in use.",
    "search": "Searches {n}s in {s} using a free text query and optional filters. "
              "Returns matching {n}s ranked by relevance, at most 50 results.",
}

# serwer -> (rzeczowniki, dodatkowe narzedzia specjalne {nazwa: opis})
SERVERS = {
    "github": (["issue", "pull_request", "branch", "release", "workflow_run", "review_comment", "label"],
               {"merge_pull_request": "Merges an open pull request in GitHub using merge, squash or rebase strategy. "
                                      "Fails if required status checks have not passed.",
                "rerun_workflow": "Re-runs a failed GitHub Actions workflow run, optionally only the failed jobs."}),
    "jira": (["ticket", "sprint", "epic", "comment", "worklog"],
             {"transition_ticket": "Moves a Jira ticket to another workflow status, for example from In Progress "
                                   "to Done. Lists available transitions when none is given.",
              "assign_ticket": "Assigns a Jira ticket to a user or unassigns it."}),
    "postgres": (["table", "index", "migration", "role", "query_plan"],
                 {"run_sql": "Executes a single read-only SQL statement against PostgreSQL and returns rows as JSON. "
                             "Statements that modify data are rejected.",
                  "explain_query": "Returns the execution plan (EXPLAIN ANALYZE) of a SQL statement in PostgreSQL, "
                                   "including actual timings and buffer usage."}),
    "kubernetes": (["pod", "deployment", "service", "configmap", "ingress", "namespace"],
                   {"pod_logs": "Streams or tails the container logs of a Kubernetes pod, with optional previous "
                                "container, since-time and line limit.",
                    "scale_deployment": "Changes the replica count of a Kubernetes deployment.",
                    "rollout_restart": "Triggers a rolling restart of a Kubernetes deployment."}),
    "slack": (["channel", "message", "user", "reaction", "thread"],
              {"post_message": "Posts a message to a Slack channel or thread, with optional blocks and attachments.",
               "set_reminder": "Creates a Slack reminder for the current user at a given time."}),
    "files": (["file", "directory", "symlink", "archive"],
              {"read_text": "Reads a UTF-8 text file from disk and returns its content with line numbers.",
               "write_text": "Writes text to a file on disk, creating parent directories if needed.",
               "grep_files": "Searches file contents with a regular expression across a directory tree."}),
    "calendar": (["event", "calendar", "attendee", "room"],
                 {"find_free_slot": "Finds a free time slot shared by several attendees within a date range.",
                  "respond_invite": "Accepts, declines or tentatively accepts a calendar invitation."}),
    "monitoring": (["alert", "dashboard", "silence", "metric", "incident"],
                   {"query_metric": "Runs a PromQL query against the monitoring backend and returns a time series.",
                    "acknowledge_alert": "Acknowledges a firing alert so that it stops paging the on-call engineer."}),
}


def _schema(props):
    return {"type": "object",
            "properties": {p: {"type": "string", "description": f"The {p.replace('_', ' ')} to use."} for p in props},
            "required": props[:1]}


def build_catalog(servers=None):
    """Lista narzedzi w formacie podobnym do definicji tool-use (name, description, input_schema)."""
    tools = []
    for s, (nouns, special) in SERVERS.items():
        if servers is not None and s not in servers:
            continue
        for n in nouns:
            for v, tmpl in VERBS.items():
                props = {"list": ["limit", "cursor", "status"], "get": [f"{n}_id"],
                         "create": ["title", "description"], "update": [f"{n}_id", "fields"],
                         "delete": [f"{n}_id"], "search": ["query", "limit"]}[v]
                tools.append({"name": f"{s}__{v}_{n}",
                              "description": tmpl.format(n=n.replace("_", " "), s=s),
                              "input_schema": _schema(props), "server": s})
        for name, desc in special.items():
            tools.append({"name": f"{s}__{name}", "description": desc,
                          "input_schema": _schema(["id", "options"]), "server": s})
    return tools


def tok(obj):
    """Szacunek tokenow: bajty/4 serializacji JSON (kompaktowej)."""
    s = obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return math.ceil(len(s.encode("utf-8")) / 4)


def full_cost(tool):
    return tok({k: tool[k] for k in ("name", "description", "input_schema")})


def name_cost(tool):
    return tok(tool["name"]) + 1  # +1 na separator linii


SEARCH_TOOL = {"name": "tool_search",
               "description": "Searches the catalog of deferred tools by keywords and loads the best matches "
                              "into the context so that they can be called.",
               "input_schema": _schema(["query", "max_results"])}

# ---------------------------------------------------------------- wyszukiwarka BM25 (stdlib)
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text):
    out = []
    for w in _WORD.findall(text.lower()):
        out.append(w)
        if len(w) > 3 and w.endswith("s"):  # prymitywny stemming liczby mnogiej
            out.append(w[:-1])
    return out


class Bm25:
    def __init__(self, tools, k1=1.5, b=0.75, name_boost=3):
        self.tools, self.k1, self.b = tools, k1, b
        self.docs = []
        for t in tools:
            nm = t["name"].replace("__", " ").replace("_", " ")
            self.docs.append(_tokens(nm) * name_boost + _tokens(t["description"]))
        self.avg = sum(map(len, self.docs)) / len(self.docs)
        self.df = {}
        for d in self.docs:
            for w in set(d):
                self.df[w] = self.df.get(w, 0) + 1

    def search(self, query, k):
        q = set(_tokens(query))
        n = len(self.docs)
        scored = []
        for t, d in zip(self.tools, self.docs):
            score = 0.0
            for w in q:
                f = d.count(w)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            if score > 0:
                scored.append((-score, t["name"]))
        scored.sort()
        return [name for _, name in scored[:k]]


# ---------------------------------------------------------------- scenariusz: 12 zadan w jednej sesji
# (zapytanie1, zapytanie2 na ponowienie, potrzebne narzedzia)
TASKS = [
    ("list open github issues", None, ["github__list_issue"]),
    ("fetch pull request details", None, ["github__get_pull_request"]),
    ("merge pull request squash", None, ["github__merge_pull_request"]),
    ("kubernetes pod logs tail", None, ["kubernetes__pod_logs"]),
    ("restart deployment rolling", None, ["kubernetes__rollout_restart"]),
    ("execute read-only sql postgres", None, ["postgres__run_sql"]),
    ("explain query plan timings", None, ["postgres__explain_query"]),
    ("post message slack channel", None, ["slack__post_message"]),
    ("read text file with line numbers", None, ["files__read_text"]),
    ("grep regular expression directory", None, ["files__grep_files"]),
    # niedopasowanie slownictwa: uzytkownik mowi "zamknij zgloszenie", narzedzie nazywa sie "transition_ticket"
    ("close the bug report", "move ticket to Done status workflow", ["jira__transition_ticket"]),
    # niedopasowanie: "kto jest na dyzurze / wycisz paging" vs acknowledge_alert
    ("silence the pager", "acknowledge firing alert on-call", ["monitoring__acknowledge_alert"]),
]
TURNS_PER_TASK = 5


def simulate(tools, strategy, k=5, tasks=TASKS, turns=TURNS_PER_TASK):
    """Zwraca dict: stale_tok (kazda tura), token_tury, zaladowane, trafienia, ponowienia.
    strategy: eager | deferred_names | deferred_blind | oracle"""
    by_name = {t["name"]: t for t in tools}
    eager = sum(full_cost(t) for t in tools)
    if strategy == "eager":
        total = len(tasks) * turns
        return {"stale_tok": eager, "token_tury": eager * total, "zaladowane": len(tools),
                "trafienia": len(tasks), "ponowienia": 0, "tur": total}
    index = Bm25(tools)
    base = tok(SEARCH_TOOL) + (sum(name_cost(t) for t in tools) if strategy == "deferred_names" else 0)
    loaded, hits, retries = set(), 0, 0
    token_turns = 0
    search_results_tok = 0  # wyniki wyszukiwania to tez tokeny w historii (zostaja do konca sesji)
    history_extra = 0
    for q1, q2, need in tasks:
        if strategy == "oracle":
            found = set(need)
        else:
            found = set(index.search(q1, k))
            if not set(need) <= found and q2:
                retries += 1
                found |= set(index.search(q2, k))
        new = found - loaded
        loaded |= found
        history_extra += sum(full_cost(by_name[n]) for n in new)
        if set(need) <= found:
            hits += 1
        token_turns += (base + history_extra) * turns
    return {"stale_tok": base, "token_tury": token_turns, "zaladowane": len(loaded),
            "trafienia": hits, "ponowienia": retries, "tur": len(tasks) * turns,
            "koniec_sesji_tok": base + history_extra}


# ---------------------------------------------------------------- polecenia
def cmd_catalog(_):
    tools = build_catalog()
    costs = [full_cost(t) for t in tools]
    print(f"narzedzi: {len(tools)}, serwerow: {len(SERVERS)}")
    print(f"pelne definicje: {sum(costs)} tok. (srednio {sum(costs)/len(costs):.1f}, min {min(costs)}, max {max(costs)})")
    print(f"same nazwy:      {sum(name_cost(t) for t in tools)} tok.")
    print(f"tool_search:     {tok(SEARCH_TOOL)} tok.")
    print("| serwer | narzedzi | tok. (pelne) |")
    print("|---|---:|---:|")
    for s in SERVERS:
        ts = [t for t in tools if t["server"] == s]
        print(f"| {s} | {len(ts)} | {sum(full_cost(t) for t in ts)} |")


def cmd_run(args):
    k = int(args[args.index("--k") + 1]) if "--k" in args else 5
    tools = build_catalog()
    print(f"katalog: {len(tools)} narzedzi, {len(TASKS)} zadan x {TURNS_PER_TASK} tur = {len(TASKS)*TURNS_PER_TASK} tur, k={k}")
    print("| strategia | stale tok/ture | koniec sesji tok/ture | token-tury | vs eager | zadan znalezionych | ponowien |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    base = simulate(tools, "eager", k)["token_tury"]
    for st in ("eager", "deferred_names", "deferred_blind", "oracle"):
        r = simulate(tools, st, k)
        end = r.get("koniec_sesji_tok", r["stale_tok"])
        print(f"| {st} | {r['stale_tok']} | {end} | {r['token_tury']} | {base / r['token_tury']:.1f}x | "
              f"{r['trafienia']}/{len(TASKS)} | {r['ponowienia']} |")


def cmd_sweep(_):
    tools = build_catalog()
    print("A) wplyw k (liczba wynikow wyszukiwania ladowanych do kontekstu), strategia deferred_names")
    print("| k | token-tury | zadan znalezionych | narzedzi zaladowanych |")
    print("|---:|---:|---:|---:|")
    for k in (1, 2, 3, 5, 8, 12, 20):
        r = simulate(tools, "deferred_names", k)
        print(f"| {k} | {r['token_tury']} | {r['trafienia']}/{len(TASKS)} | {r['zaladowane']} |")
    print()
    print("B) rozmiar katalogu (kolejne serwery), k=5: eager vs deferred_names (zadania 1-10 wymagaja github,k8s,postgres,slack,files)")
    print("| serwerow | narzedzi | eager tok/ture | deferred_names tok/ture (start) | trafione z 10 |")
    print("|---:|---:|---:|---:|---:|")
    order = ["github", "kubernetes", "postgres", "slack", "files", "jira", "calendar", "monitoring"]
    t10 = TASKS[:10]
    for n in range(5, 9):
        ts = build_catalog(order[:n])
        e = simulate(ts, "eager", 5, t10)
        d = simulate(ts, "deferred_names", 5, t10)
        print(f"| {n} | {len(ts)} | {e['stale_tok']} | {d['stale_tok']} | {d['trafienia']}/10 |")


def cmd_breakeven(_):
    tools = build_catalog()
    eager = sum(full_cost(t) for t in tools)
    names = sum(name_cost(t) for t in tools) + tok(SEARCH_TOOL)
    avg = sum(full_cost(t) for t in tools) / len(tools)
    print(f"eager: {eager} tok/ture; deferred_names baza: {names} tok/ture; srednia definicja: {avg:.1f} tok.")
    print("Zalozenie: m unikalnych narzedzi zaladowanych na poczatku sesji (najgorszy przypadek dla leniwego).")
    print("| m zaladowanych | deferred tok/ture | oszczednosc vs eager |")
    print("|---:|---:|---:|")
    for m in (0, 5, 10, 20, 40, 60, 80, len(tools)):
        d = names + m * avg
        print(f"| {m} | {d:.0f} | {(1 - d / eager) * 100:+.0f}% |")
    be = (eager - names) / avg
    print(f"punkt rownowagi: m = {be:.0f} narzedzi z {len(tools)} ({be / len(tools) * 100:.0f}% katalogu)")


# (zapytanie, narzedzie) - parafrazy bez slow z nazwy narzedzia + niejednoznaczne (ten sam rzeczownik na wielu serwerach)
RECALL_SET = [
    ("close the bug report", "jira__transition_ticket"),
    ("silence the pager", "monitoring__acknowledge_alert"),
    ("make the app bigger, more instances", "kubernetes__scale_deployment"),
    ("why is this query slow", "postgres__explain_query"),
    ("tell the team in chat", "slack__post_message"),
    ("when can we all meet", "calendar__find_free_slot"),
    ("save this to disk", "files__write_text"),
    ("ship the change into main", "github__merge_pull_request"),
    ("show me the last errors from the container", "kubernetes__pod_logs"),
    ("run the failed ci again", "github__rerun_workflow"),
    ("how many requests per second", "monitoring__query_metric"),
    ("give this to Anna", "jira__assign_ticket"),
    # niejednoznaczne: ten sam rzeczownik w kilku serwerach
    ("create comment", "jira__create_comment"),
    ("list comments", "jira__list_comment"),
    ("delete message", "slack__delete_message"),
    ("get event", "calendar__get_event"),
    ("search issue", "github__search_issue"),
    ("list alerts", "monitoring__list_alert"),
]


def cmd_recall(_):
    tools = build_catalog()
    index = Bm25(tools)
    ks = (1, 3, 5, 10)
    print(f"recall@k wyszukiwarki BM25 po name+description, katalog {len(tools)} narzedzi, {len(RECALL_SET)} zapytan")
    print("| zapytanie | oczekiwane | pozycja |")
    print("|---|---|---:|")
    hits = {k: 0 for k in ks}
    for q, want in RECALL_SET:
        ranked = index.search(q, 50)
        pos = ranked.index(want) + 1 if want in ranked else None
        for k in ks:
            if pos and pos <= k:
                hits[k] += 1
        print(f"| {q} | {want} | {pos if pos else 'brak'} |")
    print("| k | recall@k |")
    print("|---:|---:|")
    for k in ks:
        print(f"| {k} | {hits[k]}/{len(RECALL_SET)} |")


def main(argv):
    cmds = {"catalog": cmd_catalog, "run": cmd_run, "sweep": cmd_sweep, "breakeven": cmd_breakeven,
            "recall": cmd_recall}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 2
    cmds[argv[1]](argv[2:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
