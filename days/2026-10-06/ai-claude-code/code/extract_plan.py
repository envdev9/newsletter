#!/usr/bin/env python3
"""Wyciaga plan Showplan XML z wyjscia sqlcmd (-y 0) do osobnego pliku .xml.

Uzycie:  python3 extract_plan.py out05.txt samples/no_statistics_groupby.xml [N]
N (domyslnie 1) = ktory z kolejnych planow w pliku wyjsciowym (gdy skrypt ma kilka zapytan
pod SET STATISTICS XML ON, kazde daje osobny plan). Sprawdza, ze wynik sie parsuje jako XML.
"""
import sys
import xml.etree.ElementTree as ET

src, dst = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
text = open(src, encoding="utf-8", errors="replace").read()
pos = 0
for _ in range(n):
    start = text.index("<ShowPlanXML", pos)
    end = text.index("</ShowPlanXML>", start) + len("</ShowPlanXML>")
    pos = end
xml = text[start:end]
ET.fromstring(xml)  # rzuci wyjatek, jesli plan jest uszkodzony
open(dst, "w", encoding="utf-8").write(xml)
print("OK %s [#%d] -> %s (%d znakow)" % (src, n, dst, len(xml)))
