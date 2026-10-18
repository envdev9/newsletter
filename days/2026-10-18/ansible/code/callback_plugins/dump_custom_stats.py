# -*- coding: utf-8 -*-
# Minimalny callback: po zakonczeniu przebiegu wypisuje to, co set_stats zapisal w stats.custom.
# CALLBACK_NEEDS_ENABLED = False, wiec laduje sie sam (plugin lezy obok playbooka w callback_plugins/).
from __future__ import annotations

import json

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = """
    name: dump_custom_stats
    type: notification
    short_description: wypisuje stats.custom (dane z set_stats) jako JSON
    description:
      - Dydaktyczny callback; pokazuje strukture, w ktorej laduje set_stats.
"""


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "dump_custom_stats"
    CALLBACK_NEEDS_ENABLED = False

    def v2_playbook_on_stats(self, stats):
        custom = getattr(stats, "custom", {})
        for key in sorted(custom):
            self._display.display(
                "CUSTOM_STATS[%s]: %s" % (key, json.dumps(custom[key], sort_keys=True, ensure_ascii=False))
            )
