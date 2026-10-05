from __future__ import annotations

import json
import os
import time

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = r"""
    callback: task_duration
    type: notification
    short_description: Loguje czas trwania kazdego taska (per host) do pliku JSON Lines.
    description:
        - Dla kazdego wyniku (ok/failed/unreachable/skipped) zapisuje jedna linie JSON z nazwa
          taska, hostem, statusem i czasem od momentu wystartowania taska (v2_playbook_on_task_start)
          do zakonczenia dla TEGO hosta.
        - Zademonstrowany punkt rozszerzenia Ansible, ktory nie wymaga ansible-galaxy/Molecule -
          sam plik w callback_plugins/ + wpis w ansible.cfg.
    options:
      log_path:
        description: Plik docelowy logu (JSON Lines, dopisywany).
        ini:
          - section: callback_task_duration
            key: log_path
        env:
          - name: TASK_DURATION_LOG_PATH
        default: /tmp/ansible-task-duration.log
    requirements:
      - brak (tylko standardowa biblioteka Pythona)
"""


class CallbackModule(CallbackBase):
    """
    Callback plugin typu 'notification' - mierzy i loguje czas trwania kazdego taska,
    per host, do pliku JSON Lines. Nie zmienia outputu stdout (to robi 'stdout' callback,
    inny typ) - dziala RÓWNOLEGLE do standardowego outputu ansible-playbook.
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "task_duration"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._task_start = {}
        self._task_name = {}
        self.log_path = "/tmp/ansible-task-duration.log"

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(
            task_keys=task_keys, var_options=var_options, direct=direct
        )
        self.log_path = self.get_option("log_path")

    def _write(self, record):
        # Bez tego: gdy katalog logu nie istnieje (np. ktos go wyczyscil miedzy
        # przebiegami), Ansible NIE wywala playbooka - po prostu wypisuje
        # [WARNING]: Failure using method (v2_runner_on_ok) in callback plugin
        # ... i kontynuuje tak, jakby nic sie nie stalo (patrz README/ARTICLE).
        log_dir = os.path.dirname(self.log_path)
        if log_dir and not os.path.isdir(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._task_start[task._uuid] = time.time()
        self._task_name[task._uuid] = task.get_name()

    # handlery startuja przez ten sam hook co zwykle tasky
    v2_playbook_on_handler_task_start = v2_playbook_on_task_start

    def _record(self, result, status):
        task = result._task
        host = result._host.get_name() if result._host else "localhost"
        start = self._task_start.get(task._uuid)
        duration_ms = round((time.time() - start) * 1000, 2) if start is not None else None
        self._write(
            {
                "task": self._task_name.get(task._uuid, task.get_name()),
                "host": host,
                "status": status,
                "duration_ms": duration_ms,
                "ts": time.strftime("%H:%M:%S", time.localtime()),
            }
        )

    def v2_runner_on_ok(self, result):
        self._record(result, "ok")

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._record(result, "failed")

    def v2_runner_on_unreachable(self, result):
        self._record(result, "unreachable")

    def v2_runner_on_skipped(self, result):
        self._record(result, "skipped")
