# -*- coding: utf-8 -*-
"""Analizator logów ASA — ręczny odczyt ogona ShooterGame.log każdej mapy.

V3.81:
  * log otwierany przez open_log_shared (FILE_SHARE_DELETE) — blizna nr 1:
    manager kasuje log przy restarcie, a zwykły open() mógł to zablokować,
  * wzorce CFCore z prawdziwego logu ASA (wcześniejsze „Updating|Installing”
    nie pasowały do żadnej linii, licznik zawsze pokazywał 0).
"""
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

from asaonly.jezyk import t
from asaonly.logtail import open_log_shared

LIMIT_B = 4 * 1024 * 1024

_FATAL = re.compile(r"Fatal error|Unhandled Exception", re.I)
_CF_UPDATE = re.compile(r"LogCFCore:.*(?:requires upgrade/downgrade|Request to Install mod|"
                        r"Successfully installed mod)", re.I)
_CF_DOWNLOAD = re.compile(r"LogCFCore:.*Starting download", re.I)
_START_DONE = re.compile(r"Server has completed startup and is now advertising", re.I)
_WARN_ERR = re.compile(r"\b(?:warning|error)\b", re.I)


def _wzorce():
    """(etykieta w języku interfejsu, wzorzec) — liczone przy każdym skanie."""
    return [
        ("Fatal/Exception", _FATAL),
        (t("CFCore: aktualizacja modów", "CFCore: mod update"), _CF_UPDATE),
        (t("CFCore: pobieranie", "CFCore: download"), _CF_DOWNLOAD),
        (t("Start zakończony", "Startup finished"), _START_DONE),
        ("Warning/Error", _WARN_ERR),
    ]


class Wtyczka:
    nazwa = "analizator_logow"
    API = 1
    TR = {}
    manager_visible = True
    version = "1.2.0"
    required = False

    @property
    def manager_name(self):
        return t("Analizator logów ASA", "ASA log analyzer")

    @property
    def manager_description(self):
        return t("Na żądanie czyta ogony logów serwerów i podsumowuje crashe, błędy, "
                 "zdarzenia CFCore oraz markery startu. Nie zmienia serwerów.",
                 "On demand, reads the tails of server logs and summarizes crashes, errors, "
                 "CFCore events and startup markers. Does not change the servers.")

    def __init__(self):
        self.core = None
        self.enabled = False
        self.text = None

    def prepare(self, core):
        self.core = core
        self.enabled = bool(core.plugin_config(self.nazwa).get("enabled", False))
        self._pub()

    def _pub(self):
        self.core.set_indicator(self.nazwa, t("ON — gotowy", "ON — ready") if self.enabled else "OFF",
                                "#207020" if self.enabled else "#555555")

    def start(self, core):
        self.prepare(core)

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, value):
        self.enabled = bool(value)
        self.core.save_plugin_config(self.nazwa, {"enabled": self.enabled})
        self._pub()
        self.core.set_plugin_toggle(self.nazwa, self.enabled)

    def self_test(self):
        return {"ok": True, "details": t("analiza tylko do odczytu; limit 4 MB na mapę; "
                                         "odczyt współdzielony z serwerem",
                                         "read-only analysis; 4 MB limit per map; "
                                         "reading shared with the server")}

    def panel(self, parent):
        if not self.enabled:
            messagebox.showwarning(t("Logi", "Logs"),
                                   t("Włącz plugin w Managerze.", "Turn the plugin on in the Manager."),
                                   parent=parent)
            return
        okno = tk.Toplevel(parent)
        okno.title(self.manager_name)
        okno.geometry("850x600")
        ramka = ttk.Frame(okno, padding=12)
        ramka.pack(fill="both", expand=True)
        ttk.Button(ramka, text=t("ANALIZUJ LOGI TERAZ", "ANALYZE LOGS NOW"),
                   command=self._scan).pack(anchor="w")
        self.text = tk.Text(ramka, wrap="word")
        self.text.pack(fill="both", expand=True, pady=8)
        self._scan()

    @staticmethod
    def _czytaj_ogon(path):
        fh = open_log_shared(path)
        if fh is None:
            raise OSError(t("nie można otworzyć logu", "cannot open the log"))
        try:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - LIMIT_B))
            return fh.read(), size
        finally:
            fh.close()

    def _scan(self):
        out = []
        problems = 0
        for name, tab in self.core.tabs().items():
            path = os.path.join(tab.log_path, "ShooterGame.log")
            if not os.path.isfile(path):
                out.append(t("%s: brak ShooterGame.log", "%s: no ShooterGame.log") % name)
                problems += 1
                continue
            try:
                data, size = self._czytaj_ogon(path)
                counts = [(etykieta, len(wz.findall(data))) for etykieta, wz in _wzorce()]
                if counts[0][1] > 0:
                    problems += 1
                out.append(t("%s — przeanalizowano %.1f MB\n%s", "%s — analyzed %.1f MB\n%s") % (
                    name, min(size, LIMIT_B) / 1048576.0,
                    "\n".join("  %s: %d" % pair for pair in counts)))
            except Exception as exc:
                out.append(t("%s: błąd %s", "%s: error %s") % (name, exc))
                problems += 1
        if self.text is not None:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", "\n\n".join(out))
        self.core.set_indicator(
            self.nazwa,
            (t("%d map z fatalem/błędem odczytu", "%d map(s) with a fatal/read error") % problems)
            if problems else t("Brak Fatal/Exception w ogonie 4 MB",
                               "No Fatal/Exception in the 4 MB tail"),
            "#b00020" if problems else "#207020")

    def konfiguracja(self):
        return {"enabled": self.enabled}

    def stop(self):
        pass
