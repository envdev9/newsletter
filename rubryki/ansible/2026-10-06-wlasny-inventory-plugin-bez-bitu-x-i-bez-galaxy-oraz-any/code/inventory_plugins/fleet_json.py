# -*- coding: utf-8 -*-
# Wlasny inventory plugin: czyta fleet.json i buduje hosty/grupy/zmienne.
# Nie wymaga ansible-galaxy ani kolekcji, ani bitu wykonywalnego (inaczej niz skrypt).
from __future__ import annotations

DOCUMENTATION = r"""
    name: fleet_json
    short_description: Inventory z pliku JSON (flota demo)
    description:
      - Czyta liste hostow z pliku JSON i tworzy grupy wg pol C(group) oraz C(zone).
    options:
      plugin:
        description: Nazwa pluginu, musi byc C(fleet_json).
        required: true
        choices: ['fleet_json']
      source:
        description: Sciezka do pliku JSON, wzgledem pliku konfiguracyjnego inventory.
        required: true
        type: str
      zone_groups:
        description: Czy tworzyc grupy C(zone_<x>).
        type: bool
        default: true
"""

import json
import os

from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin


class InventoryModule(BaseInventoryPlugin):
    NAME = "fleet_json"

    def verify_file(self, path):
        # Plugin zajmuje sie tylko plikami *.fleet.yml / *.fleet.yaml
        valid = super().verify_file(path)
        return valid and path.endswith((".fleet.yml", ".fleet.yaml"))

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache)
        config = self._read_config_data(path)

        src = os.path.join(os.path.dirname(os.path.abspath(path)), config["source"])
        try:
            with open(src, encoding="utf-8") as fh:
                hosts = json.load(fh)["hosts"]
        except (OSError, ValueError, KeyError) as exc:
            raise AnsibleParserError("fleet_json: nie moge wczytac %s: %s" % (src, exc))

        for h in hosts:
            self.inventory.add_group(h["group"])
            self.inventory.add_host(h["name"], group=h["group"])
            self.inventory.set_variable(h["name"], "ansible_connection", "local")
            self.inventory.set_variable(h["name"], "healthy", h["healthy"])
            self.inventory.set_variable(h["name"], "zone", h["zone"])
            if self.get_option("zone_groups"):
                zg = "zone_" + h["zone"]
                self.inventory.add_group(zg)
                self.inventory.add_child(zg, h["name"])
