#!/usr/bin/env python3
"""SKRYPTOWY zastepnik agenta (NIE model!) do demonstracji petli z weryfikacja.

Zachowuje sie jak leniwy agent: bez feedbacku naprawia tylko to, co widzi od razu (add);
dopiero gdy dostanie tekst porazki testow (plik z env FEEDBACK_FILE), naprawia to, co w nim
wymienione (test_sub). Chodzi o mechanike petli, nie o inteligencje.
Uzycie: scripted_worker.py <katalog_projektu>
"""
import os
import sys
from pathlib import Path

project = Path(sys.argv[1])
calc = project / "calc.py"
src = calc.read_text(encoding="utf-8")
fb_path = os.environ.get("FEEDBACK_FILE")
feedback = Path(fb_path).read_text(encoding="utf-8") if fb_path and Path(fb_path).exists() else ""

if not feedback:
    print("worker: brak feedbacku -> naprawiam add (pierwsze co widze)")
    src = src.replace("return a - b  # BUG 1", "return a + b")
elif "test_sub" in feedback:
    print("worker: feedback wspomina test_sub -> naprawiam sub")
    src = src.replace("return a + b  # BUG 2", "return a - b")
else:
    print("worker: feedback bez znanego testu -> nic nie robie")
calc.write_text(src, encoding="utf-8")
