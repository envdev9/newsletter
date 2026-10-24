#!/usr/bin/env python3
"""Skaner planu wykonania SQL Server w formacie Showplan XML (.sqlplan / .xml).

Uzycie:  python3 scan_plan.py plan.sqlplan [plan2.sqlplan ...]
Wyjscie: plik | stmt N | POZIOM | REGULA | opis        (exit 1 gdy jest WARN)

Plan zapisujesz w SSMS/Azure Data Studio ("Save Execution Plan As") albo z T-SQL:
  SET STATISTICS XML ON;  <zapytanie>  SET STATISTICS XML OFF;
Skaner rozpoznaje: brakujace indeksy (i generuje CREATE INDEX), skany duzych tabel,
Key Lookup, PlanAffectingConvert (niejawna konwersja), spill do tempdb, brak predykatu
JOIN, kolumny bez statystyk, rozjazd estymat vs. rzeczywistosc (tylko plan "actual").

Wydanie #10 (2026-10-03): nazwy elementow/atrybutow (MissingIndexGroup@Impact,
MissingIndex@Schema/@Table, ColumnGroup@Usage, Column@Name, PlanAffectingConvert@ConvertIssue/
@Expression, IndexScan@Lookup) POTWIERDZONE na realnych planach z SQL Server 2022 (RTM-CU27,
Docker) - patrz code/samples/*.xml i code/README.md w wydaniu #10. Logika skryptu identyczna
jak w wydaniu #4 (wtedy bez SQL Servera, fixtury recznie pisane) - zero zmian bylo potrzebnych.
Wciaz niezweryfikowane na realnym planie: SPILL, NO-JOIN-PREDICATE, NO-STATISTICS, MEMORY-GRANT
(nie udalo sie w tej sesji wywolac tych warunkow na probkach danych - patrz README).
Tylko stdlib.
"""
import sys
import xml.etree.ElementTree as ET

WARN, INFO = "WARN", "INFO"
BIG_TABLE_ROWS = 10_000
SKEW_FACTOR = 10.0


def local(tag):
    return tag.rsplit("}", 1)[-1]


def descendants(el, name):
    return [e for e in el.iter() if local(e.tag) == name]


def children(el, name):
    return [e for e in el if local(e.tag) == name]


def f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def br(name):
    n = name or ""
    return n if n.startswith("[") else "[%s]" % n


def index_suggestion(mi):
    schema, table = mi.get("Schema", "[dbo]"), mi.get("Table", "[?]")
    groups = {}
    for cg in children(mi, "ColumnGroup"):
        groups[cg.get("Usage")] = [br(c.get("Name")) for c in children(cg, "Column")]
    key = groups.get("EQUALITY", []) + groups.get("INEQUALITY", [])
    inc = groups.get("INCLUDE", [])
    if not key:
        return None
    name = "IX_%s_%s" % (table.strip("[]"), "_".join(c.strip("[]") for c in key))
    sql = "CREATE NONCLUSTERED INDEX [%s] ON %s.%s (%s)" % (name, schema, table, ", ".join(key))
    if inc:
        sql += " INCLUDE (%s)" % ", ".join(inc)
    return sql + ";"


def actual_rows(relop):
    total, seen = 0, False
    # tylko wlasne RunTimeInformation operatora (nie dzieci - descendants zsumowaloby poddrzewo)
    rts = [rt for rti in children(relop, "RunTimeInformation")
           for rt in children(rti, "RunTimeCountersPerThread")]
    for rt in rts:
        if rt.get("ActualRows") is not None:
            total += int(f(rt.get("ActualRows"))); seen = True
    return total if seen else None


def scan_statement(stmt):
    out = []
    plans = descendants(stmt, "QueryPlan")
    if not plans:
        return out
    plan = plans[0]

    for mig in descendants(plan, "MissingIndexGroup"):
        impact = f(mig.get("Impact"))
        for mi in children(mig, "MissingIndex"):
            sql = index_suggestion(mi)
            out.append((WARN if impact >= 50 else INFO, "MISSING-INDEX",
                        "optymalizator sugeruje indeks (szacowany zysk %.1f%%): %s  <- to PODPOWIEDZ, nie gotowiec: "
                        "sprawdz istniejace indeksy, zloz z innymi sugestiami, policz koszt zapisu" % (impact, sql or "?")))

    for op in descendants(plan, "RelOp"):
        node = "NodeId=%s %s" % (op.get("NodeId"), op.get("PhysicalOp"))
        phys, logi = op.get("PhysicalOp", ""), op.get("LogicalOp", "")
        est, card = f(op.get("EstimateRows")), f(op.get("TableCardinality"))
        objs = [o for o in descendants(op, "Object") if o.get("Table")]
        obj = ("%s.%s" % (objs[0].get("Table"), objs[0].get("Index", ""))) if objs else "?"

        is_lookup = logi == "Key Lookup" or logi == "RID Lookup" or any(
            local(c.tag) == "IndexScan" and c.get("Lookup") in ("1", "true") for c in op)
        if is_lookup:
            out.append((WARN if est >= 1000 else INFO, "KEY-LOOKUP",
                        "%s na %s (~%d wierszy) - dla kazdego wiersza dodatkowy odczyt z klastrowego; rozwaz INCLUDE brakujacych kolumn" % (node, obj, est)))
        elif phys in ("Table Scan", "Clustered Index Scan", "Index Scan"):
            level = WARN if card >= BIG_TABLE_ROWS else INFO
            out.append((level, "SCAN",
                        "%s na %s (tabela ~%d wierszy, odczyt ~%d) - sprawdz, czy to zamierzone; jesli jest predykat, moze byc non-sargable" % (node, obj, card, est)))

        warn_el = [c for c in op if local(c.tag) == "Warnings"]
        for w in warn_el:
            if w.get("NoJoinPredicate") in ("1", "true"):
                out.append((WARN, "NO-JOIN-PREDICATE", "%s: brak predykatu JOIN - iloczyn kartezjanski?" % node))
            for s in descendants(w, "SpillToTempDb"):
                out.append((WARN, "SPILL", "%s: spill do tempdb (poziom %s) - za maly memory grant / zle estymaty" % (node, s.get("SpillLevel", "?"))))
            for s in descendants(w, "SortSpillDetails") + descendants(w, "HashSpillDetails"):
                out.append((WARN, "SPILL", "%s: %s - dane nie zmiescily sie w pamieci" % (node, local(s.tag))))
            for c in descendants(w, "ColumnsWithNoStatistics"):
                cols = ", ".join(x.get("Column", "?") for x in children(c, "ColumnReference"))
                out.append((WARN, "NO-STATISTICS", "%s: kolumny bez statystyk: %s" % (node, cols)))

        act = actual_rows(op)
        if act is not None and est > 0:
            ratio = max(act / est, est / act) if act > 0 else (est if est >= SKEW_FACTOR else 1.0)
            if ratio >= SKEW_FACTOR:
                out.append((WARN, "ESTIMATE-SKEW",
                            "%s: estymowano %d, rzeczywiscie %d (rozjazd x%.0f) - nieaktualne statystyki, parameter sniffing lub zla kardynalnosc" % (node, est, act, ratio)))

    # PlanAffectingConvert siedzi w Warnings na poziomie QueryPlan
    for w in descendants(plan, "PlanAffectingConvert"):
        issue = w.get("ConvertIssue", "?")
        out.append((WARN if issue == "Seek Plan" else INFO, "IMPLICIT-CONVERT",
                    "%s: %s - niezgodnosc typow, SQL Server konwertuje po stronie kolumny; ujednolic typ parametru/literalu z typem kolumny" % (issue, w.get("Expression", "?"))))

    mg = descendants(plan, "MemoryGrantInfo")
    if mg:
        g, u = f(mg[0].get("GrantedMemory")), f(mg[0].get("MaxUsedMemory"))
        if g >= 10_000 and u > 0 and g / u >= 10:
            out.append((INFO, "MEMORY-GRANT", "przyznano %d KB pamieci, uzyto %d KB (x%.0f) - przewymiarowany grant blokuje wspolbieznosc" % (g, u, g / u)))
    return out


def scan(path):
    root = ET.parse(path).getroot()
    res = []
    stmts = [s for s in root.iter() if local(s.tag) == "StmtSimple"]
    for i, s in enumerate(stmts, 1):
        for level, rule, msg in scan_statement(s):
            res.append((i, level, rule, msg))
    return res, len(stmts)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    bad = False
    for p in argv[1:]:
        try:
            res, n = scan(p)
        except ET.ParseError as e:
            print("%s | BLAD | XML | nie da sie sparsowac: %s" % (p, e)); bad = True; continue
        if n == 0:
            print("%s | INFO | EMPTY | brak StmtSimple - to na pewno Showplan XML?" % p)
        for i, level, rule, msg in res:
            print("%s | stmt %d | %s | %s | %s" % (p, i, level, rule, msg))
            bad = bad or level == WARN
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
