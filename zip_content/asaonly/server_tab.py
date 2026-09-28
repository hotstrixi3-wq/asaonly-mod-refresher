# -*- coding: utf-8 -*-
"""One map tab: map data, widgets and log tail; RCON belongs to its plugin."""
import copy
import os
import time
import tkinter as tk
from tkinter import filedialog, ttk

from .jezyk import t
from .logtail import LogTail, mods_dir_candidates
from .widgety import BadgeFlow, ModBadge, ToolTip

MAX_RCON_LINES=20
CRASHLOOP_WINDOW_S=15*60
CRASHLOOP_COUNT=3

def analyze_rcon_lines(lines):
    """Return the safe runtime model and an explicit lossless migration report."""
    source = copy.deepcopy(list(lines or ()))
    result, issues = [], []
    for index, line in enumerate(source):
        if not isinstance(line, dict):
            issues.append({"index": index, "reason": t("rekord nie jest obiektem", "record is not an object"),
                           "value": line})
            continue
        if len(result) >= MAX_RCON_LINES:
            issues.append({"index": index, "reason": t("rekord ponad limitem 20",
                                                       "record over the limit of 20"), "value": line})
            continue
        result.append({"time": str(line.get("time", "")),
                       "cmd": str(line.get("cmd", "")),
                       "on": bool(line.get("on", True))})
    return result, issues, source


def normalize_rcon_lines(lines):
    """Compatibility helper returning only the bounded runtime model."""
    return analyze_rcon_lines(lines)[0]

def validate_rcon_line_values(lines):
    """Validate enabled RCON rows without Tk.

    A completely empty enabled row is a harmless placeholder.  A half-filled
    row remains an error, because silently dropping a time or command would
    hide an operator typo.
    """
    result = []
    for czas, c in lines:
        czas = str(czas or "").strip()
        c = str(c or "").strip()
        if not czas and not c:
            continue
        # V3.82: isdecimal, nie isdigit — "²".isdigit() jest True, a int("²")
        # rzuca wyjątek i wywracał całą procedurę zamiast odrzucić jeden wiersz.
        if not czas or not czas.isdecimal():
            return None, "time"
        if not c:
            return None, "command"
        result.append((int(czas), c))
    return result, None

def duplicate_enabled_ports(tab_specs):
    """Return {port: [map names]} for enabled maps sharing an RCON port."""
    by_port = {}
    for name, enabled, port in tab_specs:
        port = str(port or "").strip()
        if enabled and port:
            by_port.setdefault(port, []).append(name)
    return {port: names for port, names in by_port.items() if len(names) > 1}

class ServerTab(ttk.Frame):
    def __init__(self, master, app, name, config=None):
        super().__init__(master)
        self.app = app
        self.name = name
        if config is None:
            config = {}

        self.var_ip = tk.StringVar(value=config.get("ip", "127.0.0.1"))
        self.var_port = tk.StringVar(value=str(config.get("port", "27020")))
        self.var_pass = tk.StringVar(value=config.get("password", ""))
        self.var_log = tk.StringVar(value=config.get("log_path", ""))
        self.var_tail = tk.BooleanVar(value=config.get("tail_log", False))
        # 3.50: lista modow z importu niezweryfikowana (serwer nie dzialal)
        self._mods_unverified = bool(config.get("mods_unverified", False))
        self.var_tab_mods = tk.StringVar(value=config.get("mod_ids", ""))
        self.var_admin = tk.StringVar(value=config.get("admin_cmd", ""))
        self.stash = list(config.get("stash", []))
        self.var_map_on = tk.BooleanVar(value=bool(config.get("map_on", True)))

        self.rows, self._rcon_migration_issues, self._rcon_original_lines = \
            analyze_rcon_lines(config.get("lines", []))
        self._rcon_rows_replaced = False
        self._tail_thread = None
        self._tail_status = "unknown"
        self._tail_last = ""
        self._boot_seq = 0  # lifecycle changes / a replaced log file
        self._log_source = None
        self._ready_proof = None
        self._ready_observed_at = 0.0
        self._crash_times = []
        self._crashloop_alarm = False
        # 3.71.1 FIX "EN/PL zabijalo monitor": stan monitora 3.71 (WISI/
        # sondy/Downloading/pad) zyje na SAMYM tabie OD URODZENIA. Wczesniej
        # nadawal go tylko _monitor_init - RAZ, dla tabow istniejacych
        # w chwili startu programu; taby postawione pozniej (zmiana jezyka,
        # "+ Dodaj mape", import z backupu) nie mialy _wisi_st i
        # _monitor_apply sypal AttributeError co cykl 10 s.
        self._last_log_t = time.time()
        self._wisi_st = 0     # 0=ok, 1=sonda poszla, 2=alarm wisi
        self._sonda_t = 0.0
        self._dl_last = 0.0
        self._dl_alarm = False
        self._server_versions = {}  # versions observed in this process lifetime

        self._build()

        if self._rcon_migration_issues:
            self.app.log_warn(t(
                "[%s] RCON: zachowano %d nierozpoznanych/nadmiarowych rekordów; "
                "nie zostaną utracone przy automatycznym zapisie. Otwórz panel RCON, "
                "aby świadomie zastąpić je poprawną procedurą.",
                "[%s] RCON: kept %d unrecognized/excess records; they will not be lost "
                "on automatic saves. Open the RCON panel to replace them deliberately "
                "with a valid procedure.") % (self.name, len(self._rcon_migration_issues)))

        if self.var_tail.get():
            self.after(500, self._start_tail)

    def _build(self):
        pad = {"padx": 8, "pady": 4}

        # Dane połączenia oraz cała procedura RCON są konfigurowane w
        # wymaganym pluginie RCON, nie w zakładce mapy.
        frm_map = ttk.Frame(self)
        frm_map.pack(fill="x", **pad)
        self.ck_map = ttk.Checkbutton(frm_map, text=self.app.tr("map_active"),
                                      variable=self.var_map_on,
                                      command=self._on_map_toggle)
        self.ck_map.pack(side="left")
        b_ren = ttk.Button(frm_map, text=self.app.tr("rename_server"), command=self._rename)
        b_ren.pack(side="right", padx=(6, 0))

        frm_log = ttk.LabelFrame(self, text=self.app.tr("log_path"))
        frm_log.pack(fill="x", **pad)
        ttk.Entry(frm_log, textvariable=self.var_log).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(frm_log, text=self.app.tr("browse"), command=self._browse).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(frm_log, text=self.app.tr("enable_log_tail"),
                        variable=self.var_tail,
                        command=self._toggle_tail).pack(side="left", padx=8)
        self.lbl_log_warning = ttk.Label(self, text="", foreground="#b00020", wraplength=800)
        self.lbl_log_warning.pack(fill="x", padx=8)

        frm_tmods = ttk.LabelFrame(self, text=self.app.tr("tab_mods"))
        frm_tmods.pack(fill="x", **pad)
        # 3.44: dwa PEŁNE wiersze (kiedyś diody lądowały w smudze obok
        # pola wpisow - pack side=left zabieral caly pasek, stad ciasnota)
        mods_row = ttk.Frame(frm_tmods)
        mods_row.pack(fill="x")
        self.ent_tmods = ttk.Entry(mods_row, textvariable=self.var_tab_mods)
        self.ent_tmods.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        ttk.Button(mods_row, text=self.app.tr("sync_btn"),
                   command=self.mods_from_server).pack(side="left", padx=(0, 8))
        self.frm_badges = BadgeFlow(frm_tmods)  # 3.44: zawija sie do linii
        self.frm_badges.pack(fill="x", padx=8, pady=(0, 6))
        self._badges = {}
        self.ent_tmods.bind("<KeyRelease>", self._on_mods_edited)
        self.after_idle(self._refresh_badges)

        # V3.85.3: „Zapisz tab” pod polami, które zapisuje — widać, że dotyczy
        # tylko TEJ mapy; obok znacznik niezapisanych zmian tej mapy.
        frm_zapis = ttk.Frame(self)
        frm_zapis.pack(fill="x", **pad)
        self.btn_zapisz = ttk.Button(frm_zapis, text=self.app.tr("tab_save"), command=self._zapisz)
        self.btn_zapisz.pack(side="right")
        ToolTip(self.btn_zapisz, t("Zapisuje ustawienia tylko tej mapy. Dane RCON (IP, port, hasło, "
                                   "harmonogram) zapisuje panel RCON — przycisk ZAPISZ WSZYSTKIE.",
                                   "Saves the settings of this map only. RCON data (IP, port, password, "
                                   "schedule) is saved by the RCON panel — the SAVE ALL button."))
        self.lbl_zapis = ttk.Label(frm_zapis, text="", foreground="#b06000")
        self.lbl_zapis.pack(side="right", padx=(0, 10))
        self.after_idle(self._odswiez_zapis)

        frm_st = ttk.Frame(self)
        frm_st.pack(fill="x", **pad)
        self.lbl_status = ttk.Label(frm_st, text=self.app.tr("tab_status") + "---",
                                    font=("TkDefaultFont", 10, "bold"))
        self.lbl_status.pack(side="left")
        self.lbl_last = ttk.Label(frm_st, text="", foreground="#555")
        self.lbl_last.pack(side="right")

        # RCON UI intentionally lives only in PLUGINY/86_rcon_admin.py.

    def _on_map_toggle(self):
        self.app.request_save()
        self.app._update_leds_frame()
        self._odswiez_zapis()

    def _zapisz(self):
        self.app.save_tab(self)
        self._odswiez_zapis()

    def _odswiez_zapis(self):
        """V3.85.3: znacznik niezapisanych zmian TEJ mapy (porównanie z ostatnim zapisem)."""
        try:
            niezapisany = self.app._tab_niezapisany(self)
            tekst = t("● niezapisane zmiany", "● unsaved changes") if niezapisany else ""
            if self.lbl_zapis.cget("text") != tekst:
                self.lbl_zapis.configure(text=tekst)
        except Exception:
            pass

    def _rename(self):
        self.app.rename_server(self)

    def get_effective_mod_ids(self):
        own = self.var_tab_mods.get().strip()
        if own:
            return [p.strip() for p in own.split(",") if p.strip().isdecimal()]
        return []

    def _on_mods_edited(self, _e=None):
        # 3.50: reczna edycja listy modow = wylacza jednorazowa autokorekcje
        self._mods_unverified = False
        self._refresh_badges()
        self._odswiez_zapis()

    def _verify_mods_after_boot(self):
        """3.50: jednorazowa weryfikacja listy modow po starcie serwera
        (dla tabow zaimportowanych z backupu, gdy log wczesniej milczal)."""
        try:
            log_ids = self.app._loaded_mods_from_log(self.var_log.get().strip())
            if not log_ids:
                self._mods_unverified = True  # nastepny status sprobuje znowu
                return
            cur = self.get_effective_mod_ids()
            if sorted(cur) != sorted(log_ids):
                self.var_tab_mods.set(",".join(log_ids))
                self._refresh_badges()
                self.app._update_mods_panel()
                self.app.log(self.app.tr("boot_mods_fixed", name=self.name,
                                         n=len(log_ids), ids=", ".join(log_ids)))
            else:
                self.app.log(self.app.tr("boot_mods_ok", name=self.name,
                                         n=len(log_ids)))
            self.app.request_save()
        except Exception:
            pass

    def mods_from_server(self):
        """3.49: pole dostaje mody, ktore serwer NAPRAWDE ladowal (z logu),
        nie caly bajzel z katalogu Mods. Katalog to fallback, gdy log nie
        mowi nic. Rozbieznice sa jasno logowane."""
        md = self.app._mods_dir_for_tab(self)
        if not md:
            # 3.54: mowimy DOKLADNIE gdzie szukalismy (wczesniej ogolne
            # 'nie znaleziono' - admin nie wiedzial, co program oglada).
            cands = mods_dir_candidates(self.var_log.get().strip())
            self.app.log(self.app.tr("sync_none_log", name=self.name,
                                     paths="; ".join(cands) if cands else "-"))
            return
        folder_ids = sorted({mid for mid, _ in self.app._installed_file_ids(md)},
                            key=lambda x: int(x))
        if not folder_ids:
            self.app.log(self.app.tr("sync_empty_log", path=md))
            return

        log_ids = self.app._loaded_mods_from_log(self.var_log.get().strip())
        if log_ids is None:
            use = folder_ids
            self.app.log(self.app.tr("sync_log_fallback", n=len(use)))
        else:
            use = [m for m in log_ids if m.isdigit()]
            self._mods_unverified = False  # 3.50: wlasnie zweryfikowano
            fset, uset = set(folder_ids), set(use)
            skip = [m for m in folder_ids if m not in uset]
            extra = [m for m in use if m not in fset]
            self.app.log(self.app.tr("sync_log", n=len(folder_ids),
                                     ids=", ".join(folder_ids)))
            if skip:
                self.app.log(self.app.tr("sync_log_skip", n=len(skip),
                                         ids=", ".join(skip)))
            if extra:
                self.app.log(self.app.tr("sync_log_extra",
                                         ids=", ".join(extra)))
            self.app.log(self.app.tr("sync_log_used", n=len(use),
                                     ids=", ".join(use)))

        self.var_tab_mods.set(",".join(use))
        self.app.request_save()
        self._refresh_badges()
        self.app._update_mods_panel()

    def _refresh_badges(self):
        """3.42: diody odswiezane NA ZYWO. Rebuild tylko gdy zmieni sie lista
        ID w polu; przy kazdej zmianie stanu wystarczy soft-refresh kolorow
        (stare diody czytaly kolor raz przy tworzeniu - wygladaly na martwe).
        """
        try:
            ids = [p.strip() for p in self.var_tab_mods.get().split(",")
                   if p.strip().isdigit()]
            children = self.frm_badges.winfo_children()
            if (getattr(self, "_badge_ids", None) != ids
                    or len(children) != len(ids)):
                for w in children:
                    w.destroy()
                self._badges = {}
                badges = []
                for mid in ids:
                    badges.append(ModBadge(self.frm_badges, self.app, mid, map_name=self.name))
                    self._badges[mid] = badges[-1]
                self.frm_badges.set_badges(badges)
                self._badge_ids = ids
            else:
                for b in self._badges.values():
                    b.refresh()
        except Exception:
            pass

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.var_log.get() or "C:\\")
        if d:
            self.var_log.set(d)

    def _toggle_tail(self):
        if self.var_tail.get():
            self._start_tail()
        else:
            self._stop_tail()
            self._set_status("unknown")

    def _start_tail(self):
        self._stop_tail()
        path = self.var_log.get().strip()
        problem = self.log_path_problem()
        self.lbl_log_warning.configure(text=problem or "")
        if problem:
            self.app.log_warn("[%s] %s" % (self.name, problem))
            return
        self._tail_thread = LogTail(self, path, self._on_tail)
        self._tail_thread.start()
        self.app.log(self.app.tr("tail_started", name=self.name, path=path))

    def log_path_problem(self):
        path = self.var_log.get().strip()
        if not path or not os.path.isdir(path):
            return t("Brak odczytu logu — folder nie istnieje: %s",
                     "Log unavailable — folder does not exist: %s") % (path or t("(pusta ścieżka)", "(empty path)"))
        return None

    def _stop_tail(self):
        if self._tail_thread is not None:
            self._tail_thread.stop()
            self._tail_thread = None
            self.app.log(self.app.tr("tail_stopped", name=self.name))

    def _stop_threads(self):
        self._stop_tail()

    def _on_server_event(self, event):
        self.app.post_ui(lambda e=dict(event): self._apply_server_event(e))

    def _apply_server_event(self, event):
        now = time.time()
        typ = event.get("type")
        if typ == "log_source":
            source = tuple(event["source"])
            previous = self.__dict__.get("_log_source")
            if previous is not None and previous != source:
                self._boot_seq += 1
                self._server_versions = {}
            self._log_source = source
            return
        if typ == "ready_marker":
            # Preserve the first observation time when a log is replayed.
            if event["proof"] != self.__dict__.get("_ready_proof"):
                self._ready_proof = event["proof"]
                self._ready_observed_at = event["observed_at"]
            return
        if typ == "log_open":
            # Nowy proces serwera: dowody wersji starego PID są nieaktualne.
            self._server_versions = {}
            self._dl_last = 0.0
            self._dl_alarm = False
            return
        if typ in ("install_requested", "download_started", "upgrade_required"):
            self._dl_last = now
            self._dl_alarm = False
        if typ == "install_succeeded":
            mid, fid = event.get("mod_id"), event.get("file_id")
            if mid and fid:
                self._server_versions[mid] = fid
            self._dl_last = now  # progress marker, not completion of whole batch
            self._dl_alarm = False
        elif typ == "mods_loaded":
            self._server_versions.update(event.get("mods") or {})
            self._dl_last = 0.0
            self._dl_alarm = False

    def _on_tail(self, tab, status, line):
        identity = getattr(self, "_monitor_identity", None)
        if status == "crash":
            identity = getattr(self, "_crash_trace_identity", identity)
        self.app.post_ui(lambda: self._apply_tail(status, line, crash_identity=identity))

    def confirm_ready_by_rcon(self, identity=None, boot_seq=None):
        """Confirm UNKNOWN/READY after a successful process-bound read-only RCON probe.

        This does not pretend that a log line was observed and therefore does not
        refresh the WISI clock or create version evidence.
        """
        if identity is not None:
            current = self.__dict__.get("_monitor_identity")
            if (current is None or tuple(identity) != tuple(current)
                    or boot_seq != self._boot_seq or self._tail_status not in ("unknown", "ready")):
                return False
            self._rcon_ready_identity = tuple(identity)
        elif self._tail_status != "unknown":
            return False
        self._tail_status = "ready"
        self._tail_last = t("RCON listplayers potwierdził działający serwer",
                            "RCON listplayers confirmed a running server")
        self._set_status("ready", self._tail_last)
        return True

    def _apply_tail(self, status, line, crash_identity=None):
        old = self._tail_status
        if status != "ready":
            self._rcon_ready_identity = None
        self._tail_status = status
        self._tail_last = line
        self._set_status(status, line)
        # 3.50: jednorazowa weryfikacja listy modow po starcie serwera
        # (tab z importu, gdy log w chwili importu milczal)
        if (status in ("loading_mods", "ready")
                and getattr(self, "_mods_unverified", False)):
            self._mods_unverified = False
            try:
                self.after_idle(self._verify_mods_after_boot)
            except Exception:
                pass
        now = time.time()
        # 3.71: karmienie monitora (WISI/PAD4/samorestarty/Downloading mod)
        if status != "offline":
            self._last_log_t = now
        # Download progress is fed by per-line CFCore events in
        # _apply_server_event; do not clear it merely because the last status
        # line contains unrelated engine text.
        if old == "ready" and status in ("starting", "loading_mods", "engine", "offline", "crash"):
            self._boot_seq += 1
            # Dowody wersji należą do konkretnego procesu — V3.81: zeruje je
            # zdarzenie "log_open" (pierwsza linia nowego logu), w kolejności
            # linii. Zerowanie TUTAJ kasowało wersje, gdy LogTail odczytał cały
            # początek startu jednym fragmentem (zdarzenia przed statusem).
            if status == "starting":
                self.app._samorestart_zlicz(self)
        if status == "crash" and old != "crash":
            self.app._pad4_start(self, identity=crash_identity)
            self._crash_times.append(now)
            self._crash_times = [t for t in self._crash_times
                                 if now - t <= CRASHLOOP_WINDOW_S]
            if len(self._crash_times) >= CRASHLOOP_COUNT and not self._crashloop_alarm:
                self._crashloop_alarm = True
                self.app.log_warn(self.app.tr("crashloop_log", name=self.name,
                                              n=len(self._crash_times),
                                              m=CRASHLOOP_WINDOW_S // 60))
        elif status == "ready" and old != "ready":
            self._crash_times = []
            self._crashloop_alarm = False
        if status != old and status in ("starting", "loading_mods", "engine",
                                        "ready", "crash", "offline"):
            st_text = self.app.tr("st_" + status)
            self.app.log_status(self.app.tr("status_change",
                                            name=self.name, status=st_text),
                                status, nazwa=self.name)

    def _set_status(self, status, line=""):
        colors = {
            "starting": ("#b07000", self.app.tr("st_starting")),
            "loading_mods": ("#b07000", self.app.tr("st_loading_mods")),
            "engine": ("#b07000", self.app.tr("st_engine")),
            "ready": ("#207020", self.app.tr("st_ready")),
            "crash": ("#b00020", self.app.tr("st_crash")),
            "offline": ("#b00020", self.app.tr("st_offline")),
            "unknown": ("#555555", self.app.tr("st_unknown")),
        }
        color, text = colors.get(status, colors["unknown"])
        try:
            self.lbl_status.configure(text=self.app.tr("tab_status") + text, foreground=color)
            if line:
                self.lbl_last.configure(text=self.app.tr("tab_last_log") + line)
            elif not self.var_log.get().strip():
                self.lbl_last.configure(text=self.app.tr("tab_no_log"))
        except tk.TclError:
            pass

    def set_lines_editable(self, editable):
        # Editing is owned by the RCON plugin. Kept as coordinator API.
        return None

    def to_config(self):
        # Automatic/global saves must be lossless. Invalid legacy records remain
        # byte-for-value equivalent until the operator explicitly replaces them
        # through the RCON panel and accepts the migration warning.
        if self._rcon_migration_issues and not self._rcon_rows_replaced:
            lines = copy.deepcopy(self._rcon_original_lines)
        else:
            lines = [dict(row) for row in self.rows]
        return {
            "ip": self.var_ip.get().strip(),
            "port": self.var_port.get().strip(),
            # 3.43: haslo RCON NIE trafia juz do config.json - osobny
            # plik sekretow taba (secrets.json) + przycisk "Zapisz sekret"
            "log_path": self.var_log.get().strip(),
            "tail_log": bool(self.var_tail.get()),
            "mods_unverified": bool(getattr(self, "_mods_unverified", False)),
            "mod_ids": self.var_tab_mods.get().strip(),
            "map_on": bool(self.var_map_on.get()),
            "lines": lines,
            "admin_cmd": self.var_admin.get(),
            "stash": list(self.stash),
        }
