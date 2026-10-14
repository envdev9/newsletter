#!/usr/bin/env python3
"""ctxsearch - jak dobrze wyszukiwarka narzedzi (tool search) znajduje narzedzie, gdy uzytkownik
nie uzywa slow z jego nazwy? BM25 vs n-gramy znakow vs slownik synonimow vs aliasy w opisie vs fuzja RRF
+ prior sesji (serwery, ktorych uzywasz).

Katalog: ten sam SYNTETYCZNY co w ctxlazy.py (264 narzedzia, 8 serwerow), skopiowany tu, zeby kod byl
samodzielny. Tokeny = bajty/4. Zadne API ani model nie sa wywolywane: mierzymy JAKOSC WYSZUKIWANIA
(czy narzedzie jest w top-k), nie zachowanie modelu. Stdlib only.

Uzycie:
  python3 -B ctxsearch.py eval          # recall@1/3/5 i MRR: dev, test, fresh x retrievery
  python3 -B ctxsearch.py failures      # ktore zapytania nie trafiaja (najlepszy retriever i bazowy)
  python3 -B ctxsearch.py overlap       # zapytania ze wspolnymi slowami vs bez
  python3 -B ctxsearch.py cost          # koszt: aliasy w opisach, tokeny przy k potrzebnym do recall
  python3 -B ctxsearch.py prior         # prior sesji na zapytaniach niejednoznacznych
  python3 -B ctxsearch.py peek          # co daje dopisanie slow po obejrzeniu bledow (przeuczenie)
  python3 -B ctxsearch.py query "tekst" [--session jira,github] [--k 5]
"""
import json
import math
import re
import sys

# ---------------------------------------------------------------- katalog syntetyczny (jak w ctxlazy.py)
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

PROPS = {"list": ["limit", "cursor", "status"], "get": None, "create": ["title", "description"],
         "update": None, "delete": None, "search": ["query", "limit"]}


def _schema(props):
    return {"type": "object",
            "properties": {p: {"type": "string", "description": f"The {p.replace('_', ' ')} to use."} for p in props},
            "required": props[:1]}


def build_catalog():
    tools = []
    for s, (nouns, special) in SERVERS.items():
        for n in nouns:
            for v, tmpl in VERBS.items():
                props = {"list": ["limit", "cursor", "status"], "get": [f"{n}_id"],
                         "create": ["title", "description"], "update": [f"{n}_id", "fields"],
                         "delete": [f"{n}_id"], "search": ["query", "limit"]}[v]
                tools.append({"name": f"{s}__{v}_{n}", "verb": v, "noun": n,
                              "description": tmpl.format(n=n.replace("_", " "), s=s),
                              "input_schema": _schema(props), "server": s})
        for name, desc in special.items():
            tools.append({"name": f"{s}__{name}", "verb": None, "noun": name, "description": desc,
                          "input_schema": _schema(["id", "options"]), "server": s})
    return tools


def tok(obj):
    s = obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return math.ceil(len(s.encode("utf-8")) / 4)


def full_cost(t):
    return tok({k: t[k] for k in ("name", "description", "input_schema")})


# ---------------------------------------------------------------- slowniki (reczne, jawne)
# Strona ZAPYTANIA: slownik synonimow rozwijajacy slowa uzytkownika. Zyje w wyszukiwarce, nie w kontekscie.
THESAURUS = {
    "close": ["resolve", "done", "transition", "status"], "closed": ["resolve", "done", "transition"],
    "bug": ["issue", "defect", "ticket"], "report": ["ticket", "issue"], "defect": ["issue", "ticket"],
    "pager": ["alert", "acknowledge", "paging", "page"], "paging": ["alert", "acknowledge", "page"],
    "page": ["alert", "paging"], "alarm": ["alert", "acknowledge"], "silence": ["acknowledge", "alert", "mute"],
    "mute": ["silence", "acknowledge", "alert"], "noisy": ["alert"],
    "bigger": ["scale", "replica", "replicas"], "instances": ["replica", "scale", "deployment"],
    "replicas": ["scale", "replica", "deployment"], "scale": ["replica", "deployment"],
    "slow": ["explain", "plan", "timings", "performance"], "tune": ["explain", "plan", "timings"],
    "chat": ["slack", "message", "post"], "team": ["slack", "channel", "message"],
    "tell": ["post", "message", "slack"], "send": ["post", "message"], "note": ["message", "post"],
    "meet": ["calendar", "free", "slot", "attendees"], "meeting": ["calendar", "event", "invitation", "invite"],
    "disk": ["file", "write", "text"], "save": ["write", "file", "text"], "store": ["write", "file"],
    "ship": ["merge", "release", "pull", "request"], "land": ["merge", "pull", "request"],
    "errors": ["logs", "log", "pod"], "crashed": ["logs", "pod"], "container": ["pod"],
    "pipeline": ["workflow", "run", "actions"], "ci": ["workflow", "run", "actions"],
    "build": ["workflow", "run", "actions"], "retry": ["rerun", "re", "runs", "workflow"],
    "again": ["rerun", "re", "runs"], "red": ["failed", "workflow"],
    "requests": ["metric", "query", "promql"], "cpu": ["metric", "query", "promql"],
    "graph": ["metric", "dashboard", "query", "promql"],
    "give": ["assign"], "reassign": ["assign"], "owner": ["assign"], "card": ["ticket", "workflow"],
    "board": ["sprint", "ticket"], "database": ["sql", "postgres", "statement"], "db": ["sql", "postgres"],
    "select": ["sql", "run", "statement"], "nudge": ["reminder"], "remind": ["reminder"],
    "reminders": ["reminder"], "tomorrow": ["reminder", "time"], "free": ["slot", "attendees"],
    "accept": ["invitation", "respond", "invite"], "folder": ["directory"], "source": ["file", "files", "directory"],
    "tree": ["directory"], "contents": ["read", "text", "file"], "grab": ["read", "get", "fetch"],
    "tag": ["release"], "bounce": ["restart", "rollout", "deployment"], "stale": ["branch"],
    "fire": ["alert"], "unassign": ["assign"], "undo": ["delete"],
}

# Strona DOKUMENTU: aliasy dopisane do opisu narzedzia przez jego autora (kosztuja tokeny przy zaladowaniu).
VERB_ALIASES = {"list": "show all browse enumerate", "get": "show read view fetch open details",
                "create": "add new make raise open file", "update": "edit change modify rename set",
                "delete": "remove drop erase", "search": "find lookup look for"}
NOUN_ALIASES = {"issue": "bug defect problem report", "ticket": "task story card bug report",
                "pull_request": "pr merge request change", "branch": "ref", "release": "version tag ship publish",
                "workflow_run": "ci pipeline build job action", "review_comment": "feedback note",
                "pod": "container instance", "deployment": "app service replicas workload",
                "message": "chat note text", "channel": "room", "alert": "page pager alarm notification",
                "incident": "outage", "dashboard": "graph chart panel", "metric": "measurement counter",
                "query_plan": "explain slow", "event": "meeting appointment", "room": "meeting space",
                "attendee": "participant invitee", "file": "document", "directory": "folder"}
SPECIAL_ALIASES = {
    "merge_pull_request": "land ship integrate squash main", "rerun_workflow": "retry restart ci pipeline build red",
    "transition_ticket": "close resolve done move workflow status reopen", "assign_ticket": "reassign owner give",
    "run_sql": "select query database execute", "explain_query": "slow performance tune optimize plan",
    "pod_logs": "errors output stdout crashed", "scale_deployment": "replicas bigger more instances autoscale",
    "rollout_restart": "bounce redeploy restart", "post_message": "send tell notify chat team",
    "set_reminder": "remind nudge later schedule", "read_text": "open cat load contents",
    "write_text": "save store disk create overwrite", "grep_files": "find search text code todo",
    "find_free_slot": "meet meeting availability schedule when", "respond_invite": "accept decline rsvp meeting",
    "query_metric": "graph cpu requests rate promql", "acknowledge_alert": "ack silence pager paging mute"}


def aliases_for(t):
    parts = []
    if t["verb"]:
        parts += [VERB_ALIASES[t["verb"]], NOUN_ALIASES.get(t["noun"], "")]
    else:
        parts.append(SPECIAL_ALIASES.get(t["noun"], ""))
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------- tokenizacja
_WORD = re.compile(r"[a-z0-9]+")


def words(text):
    return _WORD.findall(text.lower())


def stems(w):
    out = [w]
    if len(w) > 3 and w.endswith("s"):
        out.append(w[:-1])
    return out


def tokens(text):
    return [s for w in words(text) for s in stems(w)]


def lookup_forms(w):
    """Formy slowa do szukania w slowniku: bez -s, -ing, -ed, -d."""
    forms = [w]
    if w.endswith("s") and len(w) > 3:
        forms.append(w[:-1])
    if w.endswith("ing") and len(w) > 5:
        forms += [w[:-3], w[:-3] + "e"]
    if w.endswith("ed") and len(w) > 4:
        forms += [w[:-2], w[:-1]]
    return forms


def expand_query(query, thesaurus=None):
    th = THESAURUS if thesaurus is None else thesaurus
    ws = words(query)
    extra = []
    for w in ws:
        for f in lookup_forms(w):
            extra += th.get(f, [])
    return " ".join(ws + extra)


# ---------------------------------------------------------------- retrievery
class Bm25:
    def __init__(self, tools, doc_text, k1=1.5, b=0.75, name_boost=3):
        self.tools, self.k1, self.b = tools, k1, b
        self.docs = []
        for t in tools:
            nm = t["name"].replace("__", " ").replace("_", " ")
            self.docs.append(tokens(nm) * name_boost + tokens(doc_text(t)))
        self.counts = [self._count(d) for d in self.docs]
        self.avg = sum(map(len, self.docs)) / len(self.docs)
        self.df = {}
        for d in self.docs:
            for w in set(d):
                self.df[w] = self.df.get(w, 0) + 1

    @staticmethod
    def _count(d):
        c = {}
        for w in d:
            c[w] = c.get(w, 0) + 1
        return c

    def scores(self, query_text):
        q = set(tokens(query_text))
        n = len(self.docs)
        out = []
        for c, d in zip(self.counts, self.docs):
            s = 0.0
            for w in q:
                f = c.get(w, 0)
                if not f:
                    continue
                idf = math.log(1 + (n - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            out.append(s)
        return out


def ngrams(text, n=3):
    out = {}
    for w in words(text):
        p = f" {w} "
        for i in range(len(p) - n + 1):
            g = p[i:i + n]
            out[g] = out.get(g, 0) + 1
    return out


class NGram:
    """TF-IDF na trigramach znakow + cosinus. Lapie fleksje i literowki, NIE synonimy."""

    def __init__(self, tools, doc_text, name_boost=3):
        self.tools = tools
        self.vecs = []
        df = {}
        raw = []
        for t in tools:
            nm = t["name"].replace("__", " ").replace("_", " ")
            g = ngrams(nm)
            g = {k: v * name_boost for k, v in g.items()}
            for k, v in ngrams(doc_text(t)).items():
                g[k] = g.get(k, 0) + v
            raw.append(g)
            for k in g:
                df[k] = df.get(k, 0) + 1
        self.n = len(tools)
        self.idf = {k: math.log(1 + self.n / v) for k, v in df.items()}
        for g in raw:
            v = {k: (1 + math.log(c)) * self.idf[k] for k, c in g.items()}
            self.vecs.append((v, math.sqrt(sum(x * x for x in v.values()))))

    def scores(self, query_text):
        q = {k: (1 + math.log(c)) * self.idf.get(k, 0.0) for k, c in ngrams(query_text).items()}
        qn = math.sqrt(sum(x * x for x in q.values())) or 1.0
        out = []
        for v, vn in self.vecs:
            dot = sum(x * v.get(k, 0.0) for k, x in q.items())
            out.append(dot / (qn * vn) if vn else 0.0)
        return out


QSTOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "this", "that", "it", "by", "with",
         "from", "at", "be", "me", "we", "can", "what", "does", "when", "how", "why", "about", "my", "you",
         "your", "i", "do", "have", "has", "are", "was", "will", "should", "please", "all", "us", "our",
         "there", "any", "some", "one"}


def plain_doc(t):
    return t["description"]


def aliased_doc(t):
    return t["description"] + " Also known as: " + aliases_for(t) + "."


def _rank(tools, scores, session=None, boost=0.0):
    sc = []
    for t, s in zip(tools, scores):
        if s <= 0:
            continue
        if session and t["server"] in session:
            s *= 1 + boost
        sc.append((-s, t["name"]))
    sc.sort()
    return [n for _, n in sc]


def rrf(rank_lists, k=60):
    sc = {}
    for rl in rank_lists:
        for i, n in enumerate(rl):
            sc[n] = sc.get(n, 0.0) + 1.0 / (k + i + 1)
    return [n for n, _ in sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))]


class Retrievers:
    """Zestaw retrieverow nad jednym katalogiem. Kazdy: f(query, session=None, boost=0.0) -> lista nazw."""

    def __init__(self, tools, thesaurus=None):
        self.tools = tools
        self.thesaurus = thesaurus
        self.bm = Bm25(tools, plain_doc)
        self.bm_alias = Bm25(tools, aliased_doc)
        self.ng = NGram(tools, plain_doc)
        self.names = ["bm25", "ngram", "bm25+syn", "bm25+alias", "rrf(bm25,ngram)", "rrf(syn,alias,ngram)",
                      "bm25+stop", "rrf(syn,alias,ngram)+stop"]

    def rank(self, name, query, session=None, boost=0.0):
        if name.endswith("+stop"):
            # wariant dodany PO pierwszym przebiegu (obejrzalem bledy): usun spojniki/zaimki z zapytania
            query = " ".join(w for w in words(query) if w not in QSTOP)
            name = name[:-len("+stop")]
        T = self.tools
        if name == "bm25":
            return _rank(T, self.bm.scores(query), session, boost)
        if name == "ngram":
            return _rank(T, self.ng.scores(query), session, boost)
        if name == "bm25+syn":
            return _rank(T, self.bm.scores(expand_query(query, self.thesaurus)), session, boost)
        if name == "bm25+alias":
            return _rank(T, self.bm_alias.scores(query), session, boost)
        if name == "rrf(bm25,ngram)":
            return rrf([_rank(T, self.bm.scores(query), session, boost),
                        _rank(T, self.ng.scores(query), session, boost)])
        if name == "rrf(syn,alias,ngram)":
            q2 = expand_query(query, self.thesaurus)
            return rrf([_rank(T, self.bm.scores(q2), session, boost),
                        _rank(T, self.bm_alias.scores(query), session, boost),
                        _rank(T, self.ng.scores(q2), session, boost)])
        raise KeyError(name)


# ---------------------------------------------------------------- zestawy zapytan (reczne, jawne)
# DEV: 18 zapytan z wydania #14 (ctxlazy.py). Slownik budowalem WIEDZAC o nich, wiec to zestaw "obejrzany".
DEV = [
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
    ("create comment", "jira__create_comment"),
    ("list comments", "jira__list_comment"),
    ("delete message", "slack__delete_message"),
    ("get event", "calendar__get_event"),
    ("search issue", "github__search_issue"),
    ("list alerts", "monitoring__list_alert"),
]

# TEST: napisane po zamrozeniu slownika/aliasow, przed pierwszym uruchomieniem. Autor ten sam (ja) -
# to NIE jest niezalezny zbior; patrz sekcja "uczciwie" w artykule.
TEST = [
    ("stop the 3am paging noise", "monitoring__acknowledge_alert"),
    ("add more replicas before the sale", "kubernetes__scale_deployment"),
    ("bounce the service pods one by one", "kubernetes__rollout_restart"),
    ("send a note to the team", "slack__post_message"),
    ("nudge me about this tomorrow morning", "slack__set_reminder"),
    ("is anyone free on friday", "calendar__find_free_slot"),
    ("accept the meeting", "calendar__respond_invite"),
    ("look for TODO in the source tree", "files__grep_files"),
    ("show the cpu graph for the last hour", "monitoring__query_metric"),
    ("reassign this to Bob", "jira__assign_ticket"),
    ("move the card to review", "jira__transition_ticket"),
    ("what indexes does the database have", "postgres__list_index"),
    ("tune the slow SQL", "postgres__explain_query"),
    ("run a select on the database", "postgres__run_sql"),
    ("grab the contents of that file", "files__read_text"),
    ("retry the red pipeline", "github__rerun_workflow"),
    ("land the PR", "github__merge_pull_request"),
    ("logs from the crashed container", "kubernetes__pod_logs"),
    ("tag a release", "github__create_release"),
    ("remove the stale branch", "github__delete_branch"),
    ("mute this noisy alarm for an hour", "monitoring__create_silence"),
    ("restarting deployments one by one", "kubernetes__rollout_restart"),
    ("merged pull requests squashed", "github__merge_pull_request"),
    ("searching tickets", "jira__search_ticket"),
    ("deleted messages", "slack__delete_message"),
    ("creating epics", "jira__create_epic"),
    ("listing namespaces", "kubernetes__list_namespace"),
    ("slack list channel", "slack__list_channel"),
    ("jira get sprint", "jira__get_sprint"),
    ("postgres explain query", "postgres__explain_query"),
]

# FRESH: zapytania dopisane PO obejrzeniu bledow TEST i po dopisaniu PEEK_EXTRA (komenda `peek`).
FRESH = [
    ("page the on-call person", "monitoring__acknowledge_alert"),
    ("spin up extra copies of the api", "kubernetes__scale_deployment"),
    ("what is the plan for this statement", "postgres__explain_query"),
    ("post to the engineering room", "slack__post_message"),
    ("book a time for everyone", "calendar__find_free_slot"),
    ("write the config to disk", "files__write_text"),
    ("read that document", "files__read_text"),
    ("kick off the build again", "github__rerun_workflow"),
    ("close out the story", "jira__transition_ticket"),
    ("hand the task over to Carol", "jira__assign_ticket"),
    ("fetch container output", "kubernetes__pod_logs"),
    ("graph the error rate", "monitoring__query_metric"),
    ("restarting pods", "kubernetes__rollout_restart"),
    ("deleting channels", "slack__delete_channel"),
    ("what changed in the schema migrations", "postgres__list_migration"),
]

# Niejednoznacznosc: "comment" istnieje w jira (comment) i github (review_comment).
# (zapytanie, sesja, oczekiwane)
AMBIG = [
    ("create comment", ["jira"], "jira__create_comment"),
    ("list comments", ["jira"], "jira__list_comment"),
    ("delete comment", ["jira"], "jira__delete_comment"),
    ("get comment", ["jira"], "jira__get_comment"),
    ("create comment", ["github"], "github__create_review_comment"),
    ("list comments", ["github"], "github__list_review_comment"),
    ("delete comment", ["github"], "github__delete_review_comment"),
    ("get comment", ["github"], "github__get_review_comment"),
    # prior nie moze przeslaniac wprost nazwanego serwera
    ("slack list channel", ["jira"], "slack__list_channel"),
    ("kubernetes pod logs", ["github"], "kubernetes__pod_logs"),
    ("postgres run sql", ["jira", "github"], "postgres__run_sql"),
    ("github merge pull request", ["jira"], "github__merge_pull_request"),
]

# Slowa dopisane PO obejrzeniu bledow na TEST (komenda peek).
PEEK_EXTRA = {  # po obejrzeniu bledow TEST (komenda failures): dokladnie to, co brakowalo
    "indexes": ["index"], "restart": ["rollout", "rolling"], "mute": ["create"], "alarm": ["silence"],
}


# ---------------------------------------------------------------- ewaluacja
def evaluate(R, name, qset, thesaurus_note=None):
    pos = []
    for q, want in qset:
        rl = R.rank(name, q)
        pos.append(rl.index(want) + 1 if want in rl else None)
    n = len(qset)
    r = {k: sum(1 for p in pos if p and p <= k) for k in (1, 3, 5, 10)}
    mrr = sum(1.0 / p for p in pos if p) / n
    return pos, r, mrr


def table_eval(R, sets, names=None):
    names = names or R.names
    head = "| retriever | " + " | ".join(f"{s}: @1 / @3 / @5 / MRR" for s, _ in sets) + " |"
    print(head)
    print("|---|" + "---|" * len(sets))
    for nm in names:
        cells = []
        for _, qs in sets:
            _, r, mrr = evaluate(R, nm, qs)
            n = len(qs)
            cells.append(f"{r[1]}/{n} / {r[3]}/{n} / {r[5]}/{n} / {mrr:.2f}")
        print(f"| {nm} | " + " | ".join(cells) + " |")


def overlap_split(tools, qset):
    by = {t["name"]: t for t in tools}
    with_o, without = [], []
    for q, want in qset:
        t = by[want]
        doc = set(tokens(t["name"].replace("__", " ").replace("_", " ") + " " + t["description"]))
        (with_o if set(tokens(q)) & doc - STOP else without).append((q, want))
    return with_o, without


STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "this", "that", "it", "by", "with",
        "from", "at", "all", "be", "me", "we", "can", "what", "does", "when", "how", "why", "one", "last",
        "new", "up", "out", "into"}


def check_targets(tools, *sets):
    names = {t["name"] for t in tools}
    bad = [w for s in sets for _, w in s if w not in names]
    return bad


# ---------------------------------------------------------------- polecenia
def cmd_eval(R):
    sets = [("dev", DEV), ("test", TEST), ("fresh", FRESH)]
    print(f"katalog: {len(R.tools)} narzedzi; dev={len(DEV)}, test={len(TEST)}, fresh={len(FRESH)} zapytan")
    table_eval(R, sets)


def cmd_failures(R):
    for nm in ("bm25", "rrf(syn,alias,ngram)"):
        print(f"== {nm}: zapytania poza top-5 (TEST+FRESH)")
        for label, qs in (("test", TEST), ("fresh", FRESH)):
            for q, want in qs:
                rl = R.rank(nm, q)
                p = rl.index(want) + 1 if want in rl else None
                if not p or p > 5:
                    print(f"  [{label}] {q!r} -> {want}: pozycja {p if p else 'brak'}; top-3: {rl[:3]}")


def cmd_overlap(R):
    for label, qs in (("dev", DEV), ("test", TEST), ("fresh", FRESH)):
        w, wo = overlap_split(R.tools, qs)
        print(f"{label}: ze wspolnym slowem (nie-stop) z nazwa/opisem celu: {len(w)}, bez: {len(wo)}")
    allq = DEV + TEST + FRESH
    w, wo = overlap_split(R.tools, allq)
    print()
    print("| podzbior | n | " + " | ".join(R.names) + " |")
    print("|---|---:|" + "---:|" * len(R.names))
    for label, qs in (("ze wspolnym slowem", w), ("bez wspolnego slowa", wo)):
        cells = []
        for nm in R.names:
            _, r, _ = evaluate(R, nm, qs)
            cells.append(f"{r[5]}/{len(qs)}")
        print(f"| {label} (recall@5) | {len(qs)} | " + " | ".join(cells) + " |")


def cmd_cost(R):
    tools = R.tools
    plain = sum(full_cost(t) for t in tools)
    ali_tools = [dict(t, description=aliased_doc(t)) for t in tools]
    ali = sum(full_cost(t) for t in ali_tools)
    print(f"definicje pelne: {plain} tok.; z aliasami: {ali} tok. (+{ali - plain}, +{(ali / plain - 1) * 100:.1f}%)")
    avg = plain / len(tools)
    avg_a = ali / len(tools)
    print(f"srednia definicja: {avg:.1f} tok.; z aliasami: {avg_a:.1f} tok.")
    print()
    print("koszt zaladowania top-k wynikow (k * srednia definicja) vs recall@k na TEST+FRESH+DEV (n=%d)"
          % len(DEV + TEST + FRESH))
    allq = DEV + TEST + FRESH
    print("| retriever | recall@1 | @3 | @5 | @10 | k dla recall>=90% | tok. przy tym k |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for nm in R.names:
        pos, r, _ = evaluate(R, nm, allq)
        need = None
        for k in range(1, 265):
            if sum(1 for p in pos if p and p <= k) / len(allq) >= 0.9:
                need = k
                break
        a = avg_a if nm in ("bm25+alias", "rrf(syn,alias,ngram)") else avg
        n = len(allq)
        print(f"| {nm} | {r[1]}/{n} | {r[3]} | {r[5]} | {r[10]} | {need if need else '>264'} | "
              f"{round(need * a) if need else '-'} |")


def cmd_prior(R):
    print(f"zapytania niejednoznaczne: {len(AMBIG)}; boost = mnoznik wyniku narzedzi z serwerow sesji")
    print("| boost | " + " | ".join(["bm25", "rrf(syn,alias,ngram)"]) + " |")
    print("|---:|---:|---:|")
    for boost in (0.0, 0.1, 0.25, 0.5, 1.0, 3.0):
        cells = []
        for nm in ("bm25", "rrf(syn,alias,ngram)"):
            ok1 = sum(1 for q, ses, want in AMBIG if (R.rank(nm, q, ses, boost) or [None])[0] == want)
            cells.append(f"{ok1}/{len(AMBIG)} @1")
        print(f"| {boost} | " + " | ".join(cells) + " |")
    print()
    for boost in (0.0, 3.0):
        for q, ses, want in AMBIG:
            top = (R.rank("bm25", q, ses, boost) or [None])[0]
            if top != want:
                print(f"  boost={boost}: {q!r} sesja={ses}: top-1 = {top}, oczekiwane {want}")
    print()
    print("szczegoly dla boost=0.25 / 0.0, retriever bm25:")
    for q, ses, want in AMBIG:
        a = R.rank("bm25", q, ses, 0.0)
        b = R.rank("bm25", q, ses, 0.25)
        pa = a.index(want) + 1 if want in a else None
        pb = b.index(want) + 1 if want in b else None
        print(f"  {q!r} sesja={ses} -> {want}: pozycja {pa} -> {pb}")


def cmd_peek(R):
    # Po obejrzeniu bledow na TEST dopisujemy slowa. Mierzymy: TEST (obejrzany) vs FRESH (swiezy).
    extra = dict(THESAURUS)
    for k, v in PEEK_EXTRA.items():
        extra[k] = list(extra.get(k, [])) + v
    R2 = Retrievers(R.tools, extra)
    print(f"PEEK_EXTRA: {len(PEEK_EXTRA)} dopisanych hasel: {sorted(PEEK_EXTRA)}")
    print("| zestaw | bm25+syn przed (@5) | po dopisaniu (@5) | zmiana |")
    print("|---|---:|---:|---:|")
    for label, qs in (("test (OBEJRZANY)", TEST), ("fresh (swiezy)", FRESH)):
        _, a, _ = evaluate(R, "bm25+syn", qs)
        _, b, _ = evaluate(R2, "bm25+syn", qs)
        print(f"| {label} | {a[5]}/{len(qs)} | {b[5]}/{len(qs)} | {b[5] - a[5]:+d} |")
    print("| zestaw | rrf(syn,alias,ngram) przed (@5) | po (@5) | zmiana |")
    for label, qs in (("test (OBEJRZANY)", TEST), ("fresh (swiezy)", FRESH)):
        _, a, _ = evaluate(R, "rrf(syn,alias,ngram)", qs)
        _, b, _ = evaluate(R2, "rrf(syn,alias,ngram)", qs)
        print(f"| {label} | {a[5]}/{len(qs)} | {b[5]}/{len(qs)} | {b[5] - a[5]:+d} |")


def cmd_query(R, args):
    q = args[0]
    ses = args[args.index("--session") + 1].split(",") if "--session" in args else None
    k = int(args[args.index("--k") + 1]) if "--k" in args else 5
    for nm in R.names:
        print(f"{nm:22s} {R.rank(nm, q, ses, 0.25 if ses else 0.0)[:k]}")


def main(argv):
    tools = build_catalog()
    bad = check_targets(tools, DEV, TEST, FRESH, [(q, w) for q, _, w in AMBIG])
    if bad:
        print("BLAD: nieistniejace cele:", bad)
        return 3
    R = Retrievers(tools)
    cmds = {"eval": cmd_eval, "failures": cmd_failures, "overlap": cmd_overlap, "cost": cmd_cost,
            "prior": cmd_prior, "peek": cmd_peek}
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "query" and len(argv) > 2:
        cmd_query(R, argv[2:])
        return 0
    if argv[1] not in cmds:
        print(__doc__)
        return 2
    cmds[argv[1]](R)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
