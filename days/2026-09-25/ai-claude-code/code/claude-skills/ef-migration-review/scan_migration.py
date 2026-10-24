#!/usr/bin/env python3
"""Deterministyczny skaner migracji EF Core (plik *.cs, NIE *.Designer.cs).

Skill wywoluje go jako pierwszy krok, zeby model nie musial "zgadywac" grepem, gdzie
sa ryzykowne operacje. Skaner jest celowo prosty (regex po liniach) - znajduje
KANDYDATÓW; ocena, czy to realny problem, nalezy do modelu/czlowieka.

Uzycie:  python3 scan_migration.py Migrations/20260925_Foo.cs [...]
Exit code: 0 = brak znalezisk, 1 = sa znaleziska (tez ostrzezenia), 2 = blad uzycia.
"""
import re
import sys

# (regex, poziom, opis)
RULES = [
    (r"\.DropTable\(", "HIGH", "DropTable - nieodwracalna utrata danych; upewnij sie, ze Down() je odtworzy i ze jest backup/etap dwuetapowy"),
    (r"\.DropColumn\(", "HIGH", "DropColumn - utrata danych; rozważ najpierw wdrozenie kodu, ktory kolumny nie uzywa (expand/contract)"),
    (r"\.AlterColumn<", "MEDIUM", "AlterColumn - sprawdz zawezenie typu/dlugosci/nullability; na duzych tabelach moze blokowac"),
    (r"\.RenameColumn\(|\.RenameTable\(", "INFO", "Rename - OK, ale stary kod na starej wersji aplikacji (rolling deploy) przestanie dzialac"),
    (r"\.CreateIndex\(", "MEDIUM", "CreateIndex - na duzej tabeli SQL Server blokuje zapisy; rozwaz .Annotation(\"SqlServer:Online\", true) (edycje z online index)"),
    (r"migrationBuilder\.Sql\(", "MEDIUM", "Surowy SQL - sprawdz idempotencje, kolejnosc wzgledem zmian schematu i czy Down() go odwraca"),
]
NOT_NULL_ADD = re.compile(r"\.AddColumn<[^>]+>\(")
DOWN_RE = re.compile(r"protected override void Down\(MigrationBuilder migrationBuilder\)\s*\{(.*?)^\s{4}\}", re.DOTALL | re.MULTILINE)


def scan(path):
    findings = []
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    # Reguly dotycza Up(); DropColumn w Down() to prawidlowe cofniecie AddColumn.
    down_start = next((i for i, l in enumerate(lines) if "void Down(" in l), len(lines))
    for no, line in enumerate(lines[:down_start], 1):
        for rx, level, why in RULES:
            if re.search(rx, line):
                findings.append((no, level, why))
        if NOT_NULL_ADD.search(line):
            # patrzymy na kilka kolejnych linii wywolania AddColumn (do zamykajacego ");")
            block = "\n".join(lines[no - 1:no + 8]).split(");")[0]
            if "nullable: true" not in block:
                default = re.search(r"defaultValue(Sql)?:", block)
                why = ("AddColumn NOT NULL" + (" z defaultValue" if default else " BEZ jawnej wartosci domyslnej")
                       + " - istniejace wiersze dostana wartosc domyslna (scaffolder daje 0/\"\"/false); czy to poprawne biznesowo?")
                findings.append((no, "MEDIUM" if default else "HIGH", why))
    m = DOWN_RE.search(text)
    if not m:
        findings.append((1, "HIGH", "Nie znaleziono metody Down() - brak sciezki wycofania"))
    elif not re.search(r"migrationBuilder\.", m.group(1)):
        line_no = text[:m.start(1)].count("\n") + 1
        findings.append((line_no, "HIGH", "Down() jest pusta - migracji nie da sie wycofac"))
    return findings


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    total = 0
    for path in argv[1:]:
        for no, level, why in sorted(scan(path)):
            total += 1
            print("%s:%d | %-6s | %s" % (path, no, level, why))
    print("\nZnalezisk: %d" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
