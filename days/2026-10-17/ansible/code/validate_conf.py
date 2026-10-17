#!/usr/bin/env python3
"""Walidator formatu key=value. Wywolywany przez Ansible jako: python3 validate_conf.py <plik-tymczasowy>

Zapisuje kopie tego, co zobaczyl, do $VALIDATOR_DUMP (domyslnie /tmp/ansible-demo-lvl24/validator_saw.txt),
zeby pokazac, ze validate dostaje CALY plik (z markerami), a nie sam blok.
"""
import os
import re
import shutil
import sys

path = sys.argv[1]
dump = os.environ.get("VALIDATOR_DUMP", "/tmp/ansible-demo-lvl24/validator_saw.txt")
os.makedirs(os.path.dirname(dump), exist_ok=True)
shutil.copyfile(path, dump)

bad = []
with open(path, encoding="utf-8") as fh:
    for no, line in enumerate(fh, 1):
        s = line.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        if not re.match(r"^[a-z_0-9]+=\S", s):
            bad.append("linia %d: %r" % (no, s))
if bad:
    sys.stderr.write("niepoprawny format key=value: " + "; ".join(bad) + "\n")
    sys.exit(1)
