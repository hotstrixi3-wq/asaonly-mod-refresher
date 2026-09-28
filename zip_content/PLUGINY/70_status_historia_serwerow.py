# -*- coding: utf-8 -*-
"""Current status export and bounded server-state history in one plugin."""
from collections import deque
import json
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

from asaonly.jezyk import t


class Wtyczka:
    nazwa = "status_historia_serwerow"
    API = 1
    TR = {}
    manager_visible = True
    version = "2.1.0"
    required = False
    # Podfunkcje status/historia konfiguruje się przed włączeniem pluginu.
    panel_available_when_off = True

    @property
    def manager_name(self):
        return t("Status i historia serwerów", "Server status and history")

    @property
    def manager_description(self):
        return t(
            "Jeden obserwacyjny plugin dla dwóch wariantów tego samego stanu: "
            "aktualna migawka status.json dla zewnętrznych narzędzi oraz historia "
            "zmian statusu/PID w JSONL. Nie steruje serwerami i nie zawiera sekretów.",
            "One observation-only plugin for two variants of the same state: "
            "the current status.json snapshot for external tools and a JSONL history "
            "of status/PID changes. It does not control the servers and holds no secrets."
        )

    def __init__(self):
        self.core = None
        self.enabled = False
        self.export_enabled = True
        self.history_enabled = True
        self.interval = 30
        self.next_write = 0.0
        self.last = {}
        self.status_path = ""
        self.history_path = ""
        self.max_history_bytes = 2 * 1024 * 1024
        self.history_rotations = 5

    def prepare(self, core):
        self.core = core
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "WIEDZA_O_PROGRAMIE"))
        self.status_path = os.path.join(base, "status.json")
        self.history_path = os.path.join(base, "historia-serwerow.jsonl")
        cfg = core.plugin_config(self.nazwa)
        if cfg:
            self.enabled = bool(cfg.get("enabled", False))
            self.export_enabled = bool(cfg.get("export_enabled", True))
            self.history_enabled = bool(cfg.get("history_enabled", True))
            self.interval = max(5, int(cfg.get("interval_s", 30)))
        else:
            # Jednorazowa migracja wyborów dwóch poprzednich pluginów.
            app_cfg = getattr(core.application(), "config_data", {})
            plugins = app_cfg.get("plugins", {}) if isinstance(app_cfg, dict) else {}
            old_status = plugins.get("status_json", {}) if isinstance(plugins, dict) else {}
            old_history = plugins.get("historia_serwerow", {}) if isinstance(plugins, dict) else {}
            had_legacy = bool(old_status or old_history)
            self.export_enabled = bool(old_status.get("enabled", False)) if had_legacy else True
            self.history_enabled = bool(old_history.get("enabled", False)) if had_legacy else True
            self.enabled = self.export_enabled or self.history_enabled if had_legacy else False
            self.interval = max(5, int(old_status.get("interval_s", 30)))
            if had_legacy:
                core.save_plugin_config(self.nazwa, self.konfiguracja())
        self._publish()

    def _publish(self):
        if not self.enabled:
            text, color = "OFF", "#555555"
        else:
            active = []
            if self.export_enabled:
                active.append("status.json")
            if self.history_enabled:
                active.append(t("historia", "history"))
            text = "ON — " + (" + ".join(active) if active else
                              t("brak wybranych zapisów", "no outputs selected"))
            color = "#207020" if active else "#b07000"
        self.core.set_indicator(self.nazwa, text, color)

    def start(self, core):
        self.prepare(core)

    def is_enabled(self):
        return bool(self.enabled)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.core.save_plugin_config(self.nazwa, self.konfiguracja())
        self._publish()
        self.core.set_plugin_toggle(self.nazwa, self.enabled)
        self.core.log(t("[STATUS/HISTORIA] %s", "[STATUS/HISTORY] %s") % ("ON" if self.enabled else "OFF"),
                      "cpu_ok" if self.enabled else "cpu_off")

    def _snapshot(self):
        tabs = self.core.tabs()
        mods = self.core.mods()
        return {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "maps": {
                name: {"enabled": tab.enabled, "rcon_port": tab.rcon_port,
                       "status": tab.status, "mod_ids": list(tab.mod_ids)}
                for name, tab in tabs.items()
            },
            "mods": {"known": mods["known"], "latest": mods["latest"],
                     "pending": mods["pending"],
                     "server_observed": mods["server_observed"]},
        }

    def tik(self, now):
        if not self.enabled or not self.export_enabled or now < self.next_write:
            return
        self.next_write = now + self.interval
        doc = self._snapshot()
        os.makedirs(os.path.dirname(self.status_path), exist_ok=True)
        tmp = self.status_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.status_path)

    def _rotate_history(self):
        try:
            if not os.path.isfile(self.history_path) or os.path.getsize(self.history_path) < self.max_history_bytes:
                return
            oldest = self.history_path + ".%d" % self.history_rotations
            if os.path.exists(oldest):
                os.remove(oldest)
            for index in range(self.history_rotations - 1, 0, -1):
                source = self.history_path + ".%d" % index
                if os.path.exists(source):
                    os.replace(source, self.history_path + ".%d" % (index + 1))
            os.replace(self.history_path, self.history_path + ".1")
        except OSError as exc:
            self.core.warn(t("[STATUS/HISTORIA] rotacja historii: %s",
                             "[STATUS/HISTORY] history rotation: %s") % exc)

    def dane_monitora(self, data):
        if not self.enabled or not self.history_enabled:
            return
        pids = data.get("pid", {})
        tabs = self.core.tabs()
        for name, tab in tabs.items():
            state = {"status": tab.status, "pid": pids.get(tab.rcon_port)}
            if self.last.get(name) == state:
                continue
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            self._rotate_history()
            with open(self.history_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                         "map": name, **state}, ensure_ascii=False) + "\n")
            self.last[name] = state

    @staticmethod
    def _tail(path, count=500):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return list(deque(handle, maxlen=count))

    def panel(self, parent):
        win = tk.Toplevel(parent)
        win.title(self.manager_name)
        win.geometry("900x620")
        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        export_var = tk.BooleanVar(value=self.export_enabled)
        history_var = tk.BooleanVar(value=self.history_enabled)
        interval_var = tk.StringVar(value=str(self.interval))
        settings = ttk.LabelFrame(outer, text=t("Funkcje", "Features"), padding=10)
        settings.pack(fill="x")
        ttk.Checkbutton(settings, text=t("Eksportuj aktualny status.json", "Export current status.json"),
                        variable=export_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(settings, text=t("Zapisuj historię zmian statusu i PID",
                                         "Record history of status and PID changes"),
                        variable=history_var).grid(row=1, column=0, sticky="w")
        ttk.Label(settings, text=t("Interwał status.json (s):", "status.json interval (s):")).grid(
            row=0, column=1, padx=(20, 4))
        ttk.Entry(settings, textvariable=interval_var, width=8).grid(row=0, column=2)

        def save():
            try:
                interval = max(5, int(interval_var.get().strip()))
            except ValueError:
                messagebox.showerror(t("Status i historia", "Status and history"),
                                     t("Interwał musi być liczbą całkowitą.",
                                       "The interval must be a whole number."), parent=win)
                return
            self.export_enabled = bool(export_var.get())
            self.history_enabled = bool(history_var.get())
            self.interval = interval
            self.next_write = 0.0
            self.core.save_plugin_config(self.nazwa, self.konfiguracja())
            self._publish()
            messagebox.showinfo(t("Status i historia", "Status and history"),
                                t("Ustawienia zapisane.", "Settings saved."), parent=win)

        ttk.Button(settings, text=t("ZAPISZ USTAWIENIA", "SAVE SETTINGS"), command=save).grid(
            row=1, column=1, columnspan=2, padx=(20, 0), sticky="ew")
        ttk.Label(outer, text=t("Ostatnie 500 zdarzeń historii:", "Last 500 history events:")).pack(
            anchor="w", pady=(10, 3))
        text = tk.Text(outer, wrap="none")
        text.pack(fill="both", expand=True)
        try:
            lines = self._tail(self.history_path)
            text.insert("1.0", "".join(lines) if lines else t("Historia jest pusta.", "History is empty."))
        except FileNotFoundError:
            text.insert("1.0", t("Historia jest pusta. Zdarzenia pojawią się po włączeniu zapisu historii.",
                                 "History is empty. Events will appear once history recording is turned on."))
        text.configure(state="disabled")

    def self_test(self):
        folder = os.path.dirname(self.status_path)
        try:
            os.makedirs(folder, exist_ok=True)
            ok = os.access(folder, os.W_OK)
        except Exception:
            ok = False
        return {"ok": ok,
                "details": t("katalog statusu/historii dostępny; bez zapisu testowego",
                             "status/history folder available; no test write")}

    def konfiguracja(self):
        return {"enabled": self.enabled, "export_enabled": self.export_enabled,
                "history_enabled": self.history_enabled, "interval_s": self.interval}

    def stop(self):
        pass
