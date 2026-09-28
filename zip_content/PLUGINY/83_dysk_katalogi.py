# -*- coding: utf-8 -*-
import os
import shutil
import tkinter as tk
from tkinter import messagebox, ttk

from asaonly.jezyk import t


class Wtyczka:
    nazwa = "dysk_katalogi"
    API = 1
    TR = {}
    manager_visible = True
    version = "1.2.1"
    required = False

    @property
    def manager_name(self):
        return t("Dysk / Katalogi serwerów", "Disk / Server folders")

    @property
    def manager_description(self):
        return t(
            "Na żądanie, w workerze, sprawdza dostępność ścieżek logów, wolne miejsce "
            "oraz rozmiary katalogów. Nie skanuje automatycznie po otwarciu panelu "
            "i niczego nie usuwa ani nie przenosi.",
            "On demand, in a background worker, checks log path availability, free space "
            "and folder sizes. It does not scan automatically when the panel opens "
            "and never deletes or moves anything.")

    def __init__(self):
        self.core = None
        self.enabled = False
        self.text = None
        self.scan_button = None
        self.busy = False

    def prepare(self, core):
        self.core = core
        self.enabled = bool(core.plugin_config(self.nazwa).get("enabled", False))
        self._publish()

    def _publish(self):
        self.core.set_indicator(self.nazwa, t("ON — gotowy do ręcznego skanu", "ON — ready for a manual scan")
                                if self.enabled else "OFF",
                                "#207020" if self.enabled else "#555555")

    def start(self, core):
        self.prepare(core)

    def is_enabled(self): return self.enabled

    def set_enabled(self, value):
        self.enabled = bool(value)
        self.core.save_plugin_config(self.nazwa, {"enabled": self.enabled})
        self._publish(); self.core.set_plugin_toggle(self.nazwa, self.enabled)

    def self_test(self):
        return {"ok": True, "details": t("worker kontroli dysku dostępny; bez skanowania",
                                         "disk check worker available; no scanning")}

    @staticmethod
    def _size(path):
        total = 0
        for directory, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(directory, d))]
            for filename in files:
                try: total += os.path.getsize(os.path.join(directory, filename))
                except OSError: pass
        return total

    @staticmethod
    def _fmt(value):
        value = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024: return "%.1f %s" % (value, unit)
            value /= 1024
        return "%.1f PB" % value

    @classmethod
    def _collect(cls, entries):
        lines, bad = [], 0
        for name, path in entries:
            if not path or not os.path.isdir(path):
                lines.append(t("%s: BRAK/NIEDOSTĘPNY — %s", "%s: MISSING/UNAVAILABLE — %s") %
                             (name, path or t("brak ścieżki", "no path"))); bad += 1
                continue
            try:
                usage = shutil.disk_usage(path); size = cls._size(path)
                free_pct = 100.0 * usage.free / usage.total
                lines.append(t("%s\n  logi: %s\n  rozmiar katalogu: %s\n  wolne na dysku: %s (%.1f%%)",
                               "%s\n  logs: %s\n  folder size: %s\n  free disk space: %s (%.1f%%)") %
                             (name, path, cls._fmt(size), cls._fmt(usage.free), free_pct))
                if free_pct < 10:
                    bad += 1; lines.append(t("  OSTRZEŻENIE: mniej niż 10% wolnego miejsca",
                                             "  WARNING: free space below 10%"))
            except Exception as exc:
                lines.append(t("%s: BŁĄD %s", "%s: ERROR %s") % (name, exc)); bad += 1
        return lines, bad

    def panel(self, parent):
        if not self.enabled:
            messagebox.showwarning(t("Dysk", "Disk"),
                                   t("Włącz plugin w Managerze.", "Turn the plugin on in the Manager."),
                                   parent=parent); return
        win = tk.Toplevel(parent); win.title(self.manager_name); win.geometry("800x520")
        frame = ttk.Frame(win, padding=12); frame.pack(fill="both", expand=True)
        self.scan_button = ttk.Button(frame, text=t("SKANUJ TERAZ (TYLKO ODCZYT)", "SCAN NOW (READ-ONLY)"),
                                      command=self._scan)
        self.scan_button.pack(anchor="w")
        self.text = tk.Text(frame, wrap="word"); self.text.pack(fill="both", expand=True, pady=8)
        self.text.insert("1.0", t("Skan nie uruchamia się automatycznie. Kliknij SKANUJ TERAZ.",
                                  "The scan does not start automatically. Click SCAN NOW."))

    def _scan(self):
        if self.busy: return
        self.busy = True
        if self.scan_button: self.scan_button.configure(state="disabled")
        entries = [(name, tab.log_path) for name, tab in self.core.tabs().items()]
        self.core.set_indicator(self.nazwa, t("SKANOWANIE…", "SCANNING…"), "#005a9c")

        def worker():
            lines, bad = self._collect(entries)
            self.core.post_ui(lambda: self._scan_done(lines, bad))
        self.core.run_async(worker)

    @staticmethod
    def _zyje(widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    def _scan_done(self, lines, bad):
        self.busy = False
        # V3.84: okno mogło zostać zamknięte w trakcie skanu — wynik trafia wtedy
        # tylko na wskaźnik (wcześniej błąd Tk zostawiał wskaźnik na „SKANOWANIE…”).
        if self._zyje(self.scan_button): self.scan_button.configure(state="normal")
        if self._zyje(self.text):
            self.text.delete("1.0", "end"); self.text.insert("1.0", "\n\n".join(lines) or t("Brak map.", "No maps."))
        self.core.set_indicator(self.nazwa, (t("%d problemów", "%d problem(s)") % bad) if bad
                                else t("ODCZYT OK", "READ OK"),
                                "#b00020" if bad else "#207020")

    def konfiguracja(self): return {"enabled": self.enabled}
    def stop(self): pass
