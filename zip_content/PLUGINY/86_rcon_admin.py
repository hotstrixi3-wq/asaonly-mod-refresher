# -*- coding: utf-8 -*-
"""Required RCON workspace: connection, per-map procedures and manual console."""
import copy
import os
import queue
import shutil
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from asaonly.jezyk import t
from asaonly.server_tab import (MAX_RCON_LINES, duplicate_enabled_ports,
                                normalize_rcon_lines, validate_rcon_line_values)
from asaonly.siec import rcon_send


class Wtyczka:
    nazwa = "rcon_admin"
    API = 1
    TR = {}
    manager_visible = True
    version = "2.3.3"
    required = True
    main_action_text = "RCON"
    main_action_hook = "panel"

    @property
    def manager_name(self):
        return t("RCON — procedury serwerów", "RCON — server procedures")

    @property
    def manager_description(self):
        return t("Wymagany moduł przejmujący z zakładek map konfigurację połączeń RCON, "
                 "lokalne procedury czasowe i ręczne komendy administratora.",
                 "Required module that takes over RCON connection settings, "
                 "local timed procedures and manual admin commands from the map tabs.")

    def __init__(self):
        self.core = None
        self.window = None
        self.book = None
        self.empty_page = None
        self.editors = {}
        self.busy = set()
        self.queues = {}
        self.workers = {}
        self.inflight = set()
        self.inflight_owner = {}
        self.state_lock = threading.Lock()
        self.dispatch_lock = threading.Lock()
        self.cancel_generation = {}
        self.stopping = False

    def start(self, core):
        self.core = core
        self.stopping = False
        self.core.set_indicator(self.nazwa,
                                t("AKTYWNY — procedury RCON", "ACTIVE — RCON procedures"),
                                "#207020")

    def is_enabled(self):
        return True

    def self_test(self):
        app = self.core.application()
        invalid = []
        for name, tab in app.tabs.items():
            _rows, err = self.validate(tab)
            if err:
                invalid.append(name)
        if invalid:
            return {"ok": False,
                    "details": t("błędne procedury map: %s",
                                 "invalid map procedures: %s") % ", ".join(invalid)}
        return {"ok": True,
                "details": t("konfiguracje procedur dają się odczytać; bez wysyłania RCON",
                             "procedure configurations can be read; nothing sent over RCON")}

    @staticmethod
    def _valid_port(value):
        value = str(value or "").strip()
        return int(value) if value.isdecimal() and 1 <= int(value) <= 65535 else None

    @staticmethod
    def line_data(tab):
        if not tab.var_map_on.get():
            return []
        return [(row.get("time", ""), row.get("cmd", ""))
                for row in getattr(tab, "rows", ()) if bool(row.get("on", True))]

    @classmethod
    def validate(cls, tab):
        if not str(tab.var_ip.get() or "").strip():
            return None, "host"
        if cls._valid_port(tab.var_port.get()) is None:
            return None, "port"
        return validate_rcon_line_values(cls.line_data(tab))

    @staticmethod
    def set_lines(tab, lines):
        tab.rows = normalize_rcon_lines(lines)
        tab._rcon_original_lines = [dict(row) for row in tab.rows]
        tab._rcon_migration_issues = []
        tab._rcon_rows_replaced = True

    def panel(self, parent):
        try:
            if self.window and self.window.winfo_exists():
                self.window.deiconify()
                self.window.lift()
                return
        except Exception:
            pass
        app = self.core.application()
        win = tk.Toplevel(parent)
        self.window = win
        win.title(t("RCON — połączenia i procedury serwerów",
                    "RCON — server connections and procedures"))
        win.geometry("1040x760")
        win.minsize(820, 580)
        win.protocol("WM_DELETE_WINDOW", self._request_close)
        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=t("RCON — KONFIGURACJA I PROCEDURY",
                                "RCON — CONFIGURATION AND PROCEDURES"),
                  font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(outer, text=t(
            "Każda mapa ma własne połączenie i własne czasy lokalne. Procedura automatyczna "
            "uruchamia się tylko dla map zakwalifikowanych przez kontrolę wersji.",
            "Each map has its own connection and its own local times. The automatic procedure "
            "runs only for maps qualified by the version check."),
            wraplength=960).pack(anchor="w", pady=(2, 8))
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(footer, text=t("ZAPISZ WSZYSTKIE", "SAVE ALL"),
                   command=self._save_all).pack(side="right")
        ttk.Button(footer, text=t("ZAMKNIJ", "CLOSE"),
                   command=self._request_close).pack(side="right", padx=6)
        book = ttk.Notebook(outer)
        self.book = book
        book.pack(fill="both", expand=True)
        self.editors = {}
        for name, tab in app.tabs.items():
            page = ttk.Frame(book, padding=8)
            book.add(page, text=name)
            self._build_map(page, name, tab)
            self.editors[name]["page"] = page
        if not app.tabs:
            self.empty_page = ttk.Frame(book, padding=20)
            book.add(self.empty_page, text=t("Brak map", "No maps"))
            ttk.Label(self.empty_page,
                      text=t("Najpierw dodaj mapę w głównym oknie.",
                             "Add a map in the main window first.")).pack()

    def _build_map(self, page, name, tab):
        conn = ttk.LabelFrame(page, text=t("Połączenie RCON", "RCON connection"))
        conn.pack(fill="x")
        host = tk.StringVar(value=tab.var_ip.get())
        port = tk.StringVar(value=tab.var_port.get())
        password = tk.StringVar(value=tab.var_pass.get())
        ttk.Label(conn, text=t("Adres:", "Address:")).grid(row=0, column=0, padx=5, pady=6, sticky="e")
        ttk.Entry(conn, textvariable=host, width=18).grid(row=0, column=1, sticky="w")
        ttk.Label(conn, text="Port:").grid(row=0, column=2, padx=5, sticky="e")
        ttk.Entry(conn, textvariable=port, width=9).grid(row=0, column=3, sticky="w")
        ttk.Label(conn, text=t("Hasło:", "Password:")).grid(row=0, column=4, padx=5, sticky="e")
        ttk.Entry(conn, textvariable=password, width=22, show="*").grid(row=0, column=5, sticky="we")
        test_btn = ttk.Button(conn, text="TEST LISTPLAYERS", command=lambda n=name: self._send(n, True))
        test_btn.grid(row=0, column=6, padx=8)
        conn.columnconfigure(5, weight=1)

        proc = ttk.LabelFrame(page, text=t("Lokalna procedura tej mapy — maksymalnie 20 linii",
                                           "This map's local procedure — up to 20 lines"))
        proc.pack(fill="both", expand=True, pady=8)
        issues = list(getattr(tab, "_rcon_migration_issues", ()))
        if issues:
            ttk.Label(
                proc,
                text=(t("UWAGA: zapis zawiera %d nierozpoznanych lub nadmiarowych rekordów. "
                        "Oryginał pozostaje zachowany do czasu świadomego zapisu tego panelu.",
                        "WARNING: the saved data contains %d unrecognized or excess records. "
                        "The original is kept until you deliberately save this panel.")
                      % len(issues)),
                foreground="#b00020", wraplength=780, justify="left").pack(
                    fill="x", padx=6, pady=(5, 0))
        ttk.Label(
            proc,
            text=t("Czas = sekundy od początku odliczania TEJ mapy (V3.81). Pusta mapa: "
                   "komunikaty i czekanie pomijane. Odstępy między mapami robi kolejka "
                   "(jeden start naraz).",
                   "Time = seconds from the start of THIS map's countdown (V3.81). Empty map: "
                   "messages and waiting are skipped. The queue handles the spacing between maps "
                   "(one start at a time)."),
            foreground="#555555", wraplength=780, justify="left").pack(
                fill="x", padx=6, pady=(5, 0))
        head = ttk.Frame(proc)
        head.pack(fill="x", padx=6, pady=(5, 2))
        ttk.Label(head, text="ON", width=4).pack(side="left")
        ttk.Label(head, text=t("Czas [s]", "Time [s]"), width=10).pack(side="left")
        ttk.Label(head, text=t("Komenda RCON", "RCON command")).pack(side="left", padx=5)
        rows_box = ttk.Frame(proc)
        rows_box.pack(fill="both", expand=True, padx=6)
        rows_canvas = tk.Canvas(rows_box, highlightthickness=0, height=300)
        rows_scroll = ttk.Scrollbar(rows_box, orient="vertical", command=rows_canvas.yview)
        rows_canvas.configure(yscrollcommand=rows_scroll.set)
        rows_scroll.pack(side="right", fill="y")
        rows_canvas.pack(side="left", fill="both", expand=True)
        rows_frame = ttk.Frame(rows_canvas)
        rows_window = rows_canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        rows_frame.bind("<Configure>",
                        lambda _e: rows_canvas.configure(scrollregion=rows_canvas.bbox("all")))
        rows_canvas.bind("<Configure>",
                         lambda e: rows_canvas.itemconfigure(rows_window, width=e.width))
        rows = []

        def add_row(time_val="", cmd_val="", on=True):
            if len(rows) >= MAX_RCON_LINES:
                messagebox.showwarning("RCON", t("Można dodać maksymalnie 20 linii.",
                                                 "You can add at most 20 lines."),
                                       parent=self.window)
                return
            line = ttk.Frame(rows_frame)
            line.pack(fill="x", pady=1)
            enabled = tk.BooleanVar(value=bool(on))
            time_var = tk.StringVar(value=str(time_val))
            cmd_var = tk.StringVar(value=str(cmd_val))
            ttk.Checkbutton(line, variable=enabled).pack(side="left", padx=(4, 9))
            ttk.Entry(line, textvariable=time_var, width=10).pack(side="left")
            ttk.Entry(line, textvariable=cmd_var).pack(side="left", fill="x", expand=True, padx=6)
            record = {"frame": line, "on": enabled, "time": time_var, "cmd": cmd_var}
            rows.append(record)
            ttk.Button(line, text=t("USUŃ", "DELETE"), width=7,
                       command=lambda r=record: remove_row(r)).pack(side="right")

        def remove_row(record):
            if record in rows:
                rows.remove(record)
                record["frame"].destroy()

        for row in tab.rows:
            add_row(row.get("time", ""), row.get("cmd", ""), row.get("on", True))
        ttk.Button(head, text=t("+ DODAJ LINIĘ", "+ ADD LINE"), command=add_row).pack(side="right")

        manual = ttk.LabelFrame(page, text=t("Ręczna konsola administratora", "Manual admin console"))
        manual.pack(fill="x")
        command = tk.StringVar(value=tab.var_admin.get())
        ttk.Entry(manual, textvariable=command).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        send_btn = ttk.Button(manual, text=t("WYŚLIJ PO POTWIERDZENIU", "SEND AFTER CONFIRMATION"),
                              command=lambda n=name: self._send(n, False))
        send_btn.pack(side="left", padx=6)
        presets = list(getattr(tab, "stash", ()))
        preset_var = tk.StringVar()
        preset_row = ttk.Frame(page)
        preset_row.pack(fill="x", pady=(0, 4))
        ttk.Label(preset_row, text=t("Zapisane komendy:", "Saved commands:")).pack(side="left")
        preset_box = ttk.Combobox(preset_row, textvariable=preset_var,
                                  values=presets, state="readonly")
        preset_box.pack(side="left", fill="x", expand=True, padx=6)
        preset_box.bind("<<ComboboxSelected>>",
                        lambda _e: command.set(preset_var.get()))

        def add_preset():
            value = command.get().strip()
            if value and value not in presets:
                presets.append(value)
                preset_box.configure(values=presets)
                preset_var.set(value)

        def delete_preset():
            value = preset_var.get()
            if value in presets:
                presets.remove(value)
                preset_box.configure(values=presets)
                preset_var.set("")

        ttk.Button(preset_row, text=t("DODAJ", "ADD"), command=add_preset).pack(side="left")
        ttk.Button(preset_row, text=t("USUŃ", "DELETE"),
                   command=delete_preset).pack(side="left", padx=4)
        output = tk.Text(page, height=6, wrap="word", state="disabled")
        output.pack(fill="x", pady=(6, 0))
        self.editors[name] = {"tab": tab, "host": host, "port": port,
                              "password": password, "rows": rows,
                              "command": command, "presets": presets,
                              "output": output, "test_button": test_btn,
                              "send_button": send_btn}
        self.editors[name]["saved_state"] = self._editor_state(self.editors[name])

    @staticmethod
    def _editor_state(editor):
        return (editor["host"].get(), editor["port"].get(), editor["password"].get(),
                editor["command"].get(), tuple(editor.get("presets", ())),
                tuple((row["time"].get(), row["cmd"].get(), bool(row["on"].get()))
                      for row in editor["rows"]))

    def has_unsaved_editor(self):
        return any(self._editor_state(editor) != editor.get("saved_state")
                   for editor in self.editors.values())

    def _has_unsaved(self):
        return self.has_unsaved_editor()

    def save_open_editor(self):
        return self._save_all(show_success=False)

    def _collect(self, name):
        editor = self.editors[name]
        if not editor["host"].get().strip():
            raise ValueError(t("Brak adresu RCON mapy %s.", "No RCON address for map %s.") % name)
        port = self._valid_port(editor["port"].get())
        if port is None:
            raise ValueError(t("Nieprawidłowy port RCON mapy %s.",
                               "Invalid RCON port for map %s.") % name)
        values = [{"time": row["time"].get().strip(),
                   "cmd": row["cmd"].get().strip(),
                   "on": bool(row["on"].get())} for row in editor["rows"]]
        enabled = [(r["time"], r["cmd"]) for r in values if r["on"]]
        _valid, err = validate_rcon_line_values(enabled)
        if err == "time":
            raise ValueError(t("Mapa %s: brak lub nieprawidłowy czas linii RCON.",
                               "Map %s: missing or invalid RCON line time.") % name)
        if err == "command":
            raise ValueError(t("Mapa %s: brak komendy RCON.", "Map %s: missing RCON command.") % name)
        return port, values

    def _apply(self, name, persist=True):
        editor = self.editors[name]
        port, values = self._collect(name)
        tab = editor["tab"]
        tab.var_ip.set(editor["host"].get().strip())
        tab.var_port.set(str(port))
        tab.var_pass.set(editor["password"].get())
        tab.var_admin.set(editor["command"].get())
        tab.stash = list(editor.get("presets", ()))
        self.set_lines(tab, values)
        if persist:
            app = self.core.application()
            config_ok = app.save_tab(tab, silent=True)
            secret_ok = app.save_tab_secrets(tab, silent=True)
            if config_ok is False or secret_ok is False:
                raise OSError(t("Nie udało się trwale zapisać RCON mapy %s.",
                                "Could not save RCON settings of map %s to disk.") % name)
        return tab

    @staticmethod
    def _tab_snapshot(tab):
        return {
            "ip": tab.var_ip.get(), "port": tab.var_port.get(),
            "password": tab.var_pass.get(), "admin": tab.var_admin.get(),
            "stash": copy.deepcopy(tab.stash), "rows": copy.deepcopy(tab.rows),
            "original": copy.deepcopy(getattr(tab, "_rcon_original_lines", [])),
            "issues": copy.deepcopy(getattr(tab, "_rcon_migration_issues", [])),
            "replaced": bool(getattr(tab, "_rcon_rows_replaced", False)),
        }

    @staticmethod
    def _restore_tab(tab, snapshot):
        tab.var_ip.set(snapshot["ip"]); tab.var_port.set(snapshot["port"])
        tab.var_pass.set(snapshot["password"]); tab.var_admin.set(snapshot["admin"])
        tab.stash = copy.deepcopy(snapshot["stash"])
        tab.rows = copy.deepcopy(snapshot["rows"])
        tab._rcon_original_lines = copy.deepcopy(snapshot["original"])
        tab._rcon_migration_issues = copy.deepcopy(snapshot["issues"])
        tab._rcon_rows_replaced = snapshot["replaced"]

    def _save_all(self, show_success=True):
        app = self.core.application()
        if app.restart_active or app.watch_active:
            messagebox.showerror(
                "RCON", t("Nie można zmieniać RCON podczas procedury ani oczekiwania na powrót.",
                          "RCON cannot be changed during a procedure or while waiting for "
                          "the servers to come back."),
                parent=self.window)
            return False
        try:
            # Validate every map before changing memory or disk.
            checked = {name: self._collect(name) for name in self.editors}
            specs = [(name, bool(editor["tab"].var_map_on.get()), str(checked[name][0]))
                     for name, editor in self.editors.items()]
            duplicates = duplicate_enabled_ports(specs)
            if duplicates:
                details = "; ".join("%s: %s" % (port, ", ".join(names))
                                    for port, names in sorted(duplicates.items()))
                raise ValueError(t("Aktywne mapy mają wspólne porty RCON — %s",
                                   "Active maps share RCON ports — %s") % details)

            migration_maps = [name for name, editor in self.editors.items()
                              if getattr(editor["tab"], "_rcon_migration_issues", ())]
            if migration_maps:
                details = ", ".join(t("%s (%d rekordów)", "%s (%d records)") %
                                    (name, len(self.editors[name]["tab"]._rcon_migration_issues))
                                    for name in migration_maps)
                if not messagebox.askyesno(
                        t("RCON — świadoma migracja", "RCON — deliberate migration"),
                        t("Stary zapis zawiera rekordy, których nie można bezpiecznie użyć: %s.\n\n"
                          "Automatyczne zapisy zachowują je bez zmian. Kontynuacja zastąpi je "
                          "dokładnie zawartością widoczną w panelu. Oryginalne wersjonowane pliki "
                          "pozostaną w katalogu mapy. Czy świadomie zastąpić te rekordy?",
                          "The old saved data contains records that cannot be used safely: %s.\n\n"
                          "Automatic saves keep them unchanged. Continuing will replace them with "
                          "exactly what is shown in the panel. The original versioned files "
                          "will stay in the map directory. Do you want to deliberately replace "
                          "these records?") % details,
                        parent=self.window):
                    return False

            snapshots = {name: self._tab_snapshot(editor["tab"])
                         for name, editor in self.editors.items()}
            old_server_files = dict(app.server_files)
            with tempfile.TemporaryDirectory(prefix="asaonly-rcon-save-") as txn:
                disk = {}
                for index, (name, editor) in enumerate(self.editors.items()):
                    path = app.server_files.get(name)
                    existed = bool(path and os.path.isdir(path))
                    backup = os.path.join(txn, str(index))
                    if existed:
                        shutil.copytree(path, backup)
                    disk[name] = (path, existed, backup)
                try:
                    for name in self.editors:
                        self._apply(name, persist=False)
                    for name, editor in self.editors.items():
                        tab = editor["tab"]
                        if not app.save_tab(tab, silent=True):
                            raise OSError(t("Nie udało się zapisać konfiguracji RCON mapy %s.",
                                            "Could not save the RCON configuration of map %s.") % name)
                        if not app.save_tab_secrets(tab, silent=True):
                            raise OSError(t("Nie udało się zapisać sekretu RCON mapy %s.",
                                            "Could not save the RCON secret of map %s.") % name)
                except Exception as original_exc:
                    rollback_errors = []
                    for name, editor in self.editors.items():
                        try:
                            self._restore_tab(editor["tab"], snapshots[name])
                        except Exception as exc:
                            rollback_errors.append(t("%s pamięć: %s", "%s memory: %s") % (name, exc))
                        old_path, existed, backup = disk[name]
                        current_path = app.server_files.get(name) or old_path
                        try:
                            if current_path and os.path.isdir(current_path):
                                shutil.rmtree(current_path)
                            if existed:
                                shutil.copytree(backup, old_path)
                        except Exception as exc:
                            rollback_errors.append(t("%s dysk: %s", "%s disk: %s") % (name, exc))
                    app.server_files.clear()
                    app.server_files.update(old_server_files)
                    if rollback_errors:
                        raise RuntimeError(
                            t("Zapis RCON nieudany: %s. Rollback częściowo nieudany: %s",
                              "RCON save failed: %s. Rollback partly failed: %s") %
                            (original_exc, "; ".join(rollback_errors))) from original_exc
                    raise
            for editor in self.editors.values():
                editor["saved_state"] = self._editor_state(editor)
        except Exception as exc:
            # Every failure path returns a controlled False to Tk. Programming,
            # Tcl and third-party exceptions must not escape the button callback.
            try:
                messagebox.showerror("RCON", str(exc), parent=self.window)
            except Exception as ui_exc:
                self.core.post_ui(lambda e=str(exc), u=str(ui_exc): self.core.log(
                    t("[RCON] zapis nieudany: %s; nie udało się pokazać okna: %s",
                      "[RCON] save failed: %s; could not show the window: %s") % (e, u),
                    "warn"))
            return False
        if show_success:
            messagebox.showinfo("RCON", t("Zapisano połączenia i procedury RCON.",
                                          "RCON connections and procedures saved."),
                                parent=self.window)
        return True

    def _set_busy(self, name, value):
        if value:
            self.busy.add(name)
        else:
            self.busy.discard(name)
        editor = self.editors.get(name)
        if editor:
            state = "disabled" if value else "normal"
            editor["test_button"].configure(state=state)
            editor["send_button"].configure(state=state)

    def _send(self, name, probe):
        if name in self.busy:
            return
        app = self.core.application()
        if app.restart_active or app.watch_active:
            messagebox.showwarning(
                "RCON", t("Ręczne polecenia są zablokowane do zakończenia procedury "
                          "i powrotu serwera.",
                          "Manual commands are blocked until the procedure ends "
                          "and the server is back."),
                parent=self.window)
            return
        editor = self.editors[name]
        host = editor["host"].get().strip()
        if not host:
            messagebox.showerror("RCON", t("Brak adresu RCON mapy %s.",
                                           "No RCON address for map %s.") % name,
                                 parent=self.window)
            return
        port = self._valid_port(editor["port"].get())
        if port is None:
            messagebox.showerror("RCON", t("Nieprawidłowy port RCON mapy %s.",
                                           "Invalid RCON port for map %s.") % name,
                                 parent=self.window)
            return
        password = editor["password"].get()
        command = "ListPlayers" if probe else editor["command"].get().strip()
        if not command:
            messagebox.showerror("RCON", t("Komenda jest pusta.", "The command is empty."),
                                 parent=self.window)
            return
        warning = t("UWAGA: DoExit wyłączy proces tej mapy.\n\n",
                    "WARNING: DoExit will shut down this map's process.\n\n") if command.split()[0].lower() == "doexit" else ""
        if not probe and not messagebox.askyesno(
                t("Potwierdź RCON", "Confirm RCON"),
                warning + t("Mapa: %s\nKomenda: %s\n\nWysłać?",
                  "Map: %s\nCommand: %s\n\nSend?") % (name, command),
                parent=self.window):
            return
        self._append(name, "> " + command)
        self._set_busy(name, True)

        def finished(error, response):
            text = t("BŁĄD: ", "ERROR: ") + str(error) if error else str(response or "OK")
            self.core.post_ui(lambda: self._result(name, text))
        # Ręczne i automatyczne polecenia tej samej mapy muszą przechodzić
        # przez jedną kolejkę. Inaczej konsola może wejść pomiędzy komunikat
        # procedury i DoExit.
        try:
            self.enqueue_values(name, host, port, password, command, finished, owner="manual")
        except Exception as exc:
            # V3.84: bez tego mapa zostawała „zajęta” z wyłączonymi przyciskami.
            self._result(name, t("BŁĄD: ", "ERROR: ") + str(exc))

    def _queue_for(self, name):
        if self.stopping:
            raise RuntimeError(t("plugin RCON jest zatrzymywany", "RCON plugin is stopping"))
        name = str(name)
        work_queue = self.queues.get(name)
        worker = self.workers.get(name)
        if work_queue is None or worker is None or not worker.is_alive():
            work_queue = queue.Queue()
            self.queues[name] = work_queue
            worker = threading.Thread(target=self._worker, args=(name, work_queue),
                                      daemon=True, name="RCON-%s" % name)
            self.workers[name] = worker
            worker.start()
        return work_queue

    def enqueue_values(self, name, host, port, password, command, callback=None,
                       owner="manual"):
        name, owner = str(name), str(owner)
        work_queue = self._queue_for(name)
        with self.dispatch_lock:
            key = (name, owner)
            generation = self.cancel_generation.get(key, 0)
            work_queue.put((owner, generation, str(command), str(host).strip(),
                            str(port).strip(), str(password), callback))

    def enqueue(self, tab, command, callback=None, owner="automatic"):
        """Queue one command for a map with an explicit operational owner."""
        wrapped = (lambda error, _response: callback(error)) if callback else None
        self.enqueue_values(tab.name, tab.var_ip.get(), tab.var_port.get(),
                            tab.var_pass.get(), command, wrapped, owner=owner)

    def enqueue_raw(self, tab, command, callback=None, owner="automatic"):
        """V3.81: jak enqueue, ale callback dostaje (błąd, odpowiedź serwera).

        Potrzebne do ListPlayers przed restartem (pusta mapa = bez ogłoszeń).
        Ta sama kolejka mapy co procedura — komendy nie mogą się przeplatać.
        """
        self.enqueue_values(tab.name, tab.var_ip.get(), tab.var_port.get(),
                            tab.var_pass.get(), command, callback, owner=owner)

    def _claim_dispatch(self, name, owner, generation):
        with self.dispatch_lock:
            if generation != self.cancel_generation.get((name, owner), 0):
                return False
            with self.state_lock:
                self.inflight.add(name)
                self.inflight_owner[name] = owner
            return True

    def _worker(self, name, work_queue):
        while True:
            item = work_queue.get()
            if item is None:
                return
            owner, generation, command, host, port, password, callback = item
            error = None
            response = None
            start = time.monotonic()
            # This hand-off is atomic against cancel_pending(). If cancellation
            # wins, a dequeued-but-not-started automatic item is rejected.
            if not self._claim_dispatch(name, owner, generation):
                continue
            try:
                for attempt in range(3):
                    try:
                        response = rcon_send(host, port, password, command)
                        error = None
                        break
                    except Exception as exc:
                        error = exc if not getattr(exc, "retry_safe", True) else str(exc)
                        if not getattr(exc, "retry_safe", True):
                            break
                        if attempt < 2:
                            time.sleep(2.0)
            finally:
                with self.state_lock:
                    self.inflight.discard(name)
                    self.inflight_owner.pop(name, None)
            # Bez hasła i parametrów komendy. Odpowiedź ograniczona do 500 znaków.
            verb = command.strip().split(" ", 1)[0].lower()
            if self.core is not None and verb in ("doexit", "saveworld", "listplayers"):
                elapsed = time.monotonic() - start
                reply = repr(str(response)[:500]) if response is not None else "—"
                status = str(error) if error else "OK"
                self.core.post_ui(lambda n=name, c=verb, s=elapsed, r=reply, e=status:
                                  self.core.log("[RCON %s] %s: %.3f s; %s; response=%s" % (n, c, s, e, r)))
            if callback is not None:
                try:
                    callback(error, response)
                except Exception as exc:
                    self.core.post_ui(lambda e=str(exc), n=name:
                                      self.core.log(t("[RCON %s] błąd callbacku: %s",
                                                      "[RCON %s] callback error: %s") % (n, e),
                                                    "warn"))

    def cancel_pending(self, tab_names, owner="automatic"):
        """Atomically cancel one owner's work without eating manual/probe jobs."""
        names = tuple(dict.fromkeys(str(name) for name in tab_names))
        owner = str(owner)
        with self.dispatch_lock:
            with self.state_lock:
                active = tuple(sorted(name for name in names
                                      if self.inflight_owner.get(name) == owner))
            if active:
                return {"ok": False, "inflight": active, "removed": 0}
            for name in names:
                key = (name, owner)
                self.cancel_generation[key] = self.cancel_generation.get(key, 0) + 1
            removed = 0
            for name in names:
                work_queue = self.queues.get(name)
                if work_queue is None:
                    continue
                preserved = []
                try:
                    while True:
                        item = work_queue.get_nowait()
                        if item is None or item[0] != owner:
                            preserved.append(item)
                        else:
                            removed += 1
                except queue.Empty:
                    pass
                for item in preserved:
                    work_queue.put(item)
            return {"ok": True, "inflight": (), "removed": removed}

    def is_idle(self, tab_or_name):
        name = str(getattr(tab_or_name, "name", tab_or_name))
        with self.state_lock:
            active = name in self.inflight
        work_queue = self.queues.get(name)
        return not active and (work_queue is None or work_queue.empty())

    def all_idle(self):
        names = set(self.queues)
        with self.state_lock:
            names.update(self.inflight)
        return all(self.is_idle(name) for name in names)

    def flush(self, tab_or_name):
        """Remove only queued commands; an in-flight socket call is not cancellable."""
        name = str(getattr(tab_or_name, "name", tab_or_name))
        work_queue = self.queues.get(name)
        removed = 0
        if work_queue is not None:
            try:
                while True:
                    item = work_queue.get_nowait()
                    if item is not None:
                        removed += 1
            except queue.Empty:
                pass
        with self.state_lock:
            inflight = name in self.inflight
        return {"removed": removed, "inflight": inflight}

    def _append(self, name, text):
        output = self.editors[name]["output"]
        output.configure(state="normal")
        output.insert("end", text + "\n")
        output.see("end")
        output.configure(state="disabled")

    def _result(self, name, text):
        self._set_busy(name, False)
        if name in self.editors:
            self._append(name, text + "\n")

    def _request_close(self):
        if self._has_unsaved():
            decision = messagebox.askyesnocancel(
                "RCON", t("Zapisać zmiany RCON przed zamknięciem?",
                          "Save RCON changes before closing?"), parent=self.window)
            if decision is None:
                return
            if decision and not self._save_all():
                return
        self._close()

    def on_tab_added(self, name, tab):
        """Keep an already open RCON workspace synchronized with manual/imported maps."""
        if not self.window or not self.book or str(name) in self.editors:
            return
        if self.empty_page is not None:
            try:
                self.empty_page.destroy()
            except tk.TclError:
                pass
            self.empty_page = None
        page = ttk.Frame(self.book, padding=8)
        self.book.add(page, text=str(name))
        self._build_map(page, str(name), tab)
        self.editors[str(name)]["page"] = page

    def prepare_tab_rename(self, tab):
        """Prevent identity changes while old-name RCON work exists."""
        if not self.is_idle(tab.name):
            messagebox.showwarning(
                "RCON", t("Nie można zmienić nazwy mapy, gdy jej komenda RCON jest w kolejce "
                          "lub w trakcie wysyłania.",
                          "Cannot rename the map while its RCON command is queued "
                          "or being sent."),
                parent=self.window)
            return False
        if not self.window:
            return True
        if self._has_unsaved():
            decision = messagebox.askyesnocancel(
                "RCON", t("Przed zmianą nazwy mapy zapisać zmiany RCON?",
                          "Save RCON changes before renaming the map?"),
                parent=self.window)
            if decision is None:
                return False
            if decision and not self._save_all():
                return False
        self._close()
        return True

    def on_tab_renamed(self, old_name, new_name, tab):
        """Retire the old queue identity and force a fresh panel snapshot."""
        old_name, new_name = str(old_name), str(new_name)
        self.flush(old_name)
        old_queue = self.queues.pop(old_name, None)
        self.workers.pop(old_name, None)
        if old_queue is not None:
            old_queue.put(None)
        # An open editor contains bindings keyed by the former map name.
        # Closing it is safer than saving those stale bindings over the rename.
        self._close()

    def _close(self):
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.book = None
        self.empty_page = None
        self.editors = {}

    def konfiguracja(self):
        return {}

    def stop(self):
        self.stopping = True
        for name, work_queue in tuple(self.queues.items()):
            self.flush(name)
            work_queue.put(None)
        self.queues.clear()
        self.workers.clear()
        with self.state_lock:
            self.inflight.clear()
            self.inflight_owner.clear()
        self.cancel_generation.clear()
        self.busy.clear()
        self._close()
