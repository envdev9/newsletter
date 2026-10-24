#!/usr/bin/env python3
"""Wariant A: dynamic inventory jako zwykly skrypt. `--list` -> JSON, `--host X` -> JSON.

Zrodlem prawdy jest fleet.json obok skryptu (w prawdziwym zyciu: API chmury, CMDB).
UWAGA: aby uzyc przez `-i`, skrypt MUSI miec bit wykonywalny (chmod +x).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_fleet():
    with open(os.path.join(HERE, "fleet.json"), encoding="utf-8") as fh:
        return json.load(fh)["hosts"]


def hostvars_of(h):
    return {"ansible_connection": "local", "healthy": h["healthy"], "zone": h["zone"]}


def build_list():
    inv = {}
    for h in load_fleet():
        inv.setdefault(h["group"], {"hosts": []})["hosts"].append(h["name"])
        inv.setdefault("zone_" + h["zone"], {"hosts": []})["hosts"].append(h["name"])
    # _meta.hostvars: dzieki temu Ansible nie wola `--host` osobno dla kazdego hosta
    inv["_meta"] = {"hostvars": {h["name"]: hostvars_of(h) for h in load_fleet()}}
    return inv


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--list"]:
        print(json.dumps(build_list()))
    elif argv[:1] == ["--host"] and len(argv) == 2:
        found = [hostvars_of(h) for h in load_fleet() if h["name"] == argv[1]]
        print(json.dumps(found[0] if found else {}))
    else:
        sys.stderr.write("uzycie: --list | --host <nazwa>\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
