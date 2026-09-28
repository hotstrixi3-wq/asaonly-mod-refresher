# -*- coding: utf-8 -*-
"""CPU process panel: observe first, change only a real mismatch."""
import json
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from asaonly.jezyk import t


PRIORITIES = {
    "Idle": 0x40,
    "Below Normal": 0x4000,
    "Normal": 0x20,
    "Above Normal": 0x8000,
    "High": 0x80,
    "RealTime": 0x100,
}
PRIORITY_BY_VALUE = {value: name for name, value in PRIORITIES.items()}

# Affinity presets: the config stores the id, only the label is translated.
# Older versions stored the Polish menu label itself ("Wszystkie", "Pierwsza
# połowa", ...) — its first word still identifies the preset.
_LEGACY_AFFINITY = {"wszystkie": "all", "pierwsza": "first_half", "druga": "second_half",
                    "parzyste": "even", "nieparzyste": "odd"}


def _affinity_presets():
    """{config id: label in the UI language} — built at use time."""
    return {
        "all": t("Wszystkie", "All CPUs"),
        "first_half": t("Pierwsza połowa", "First half"),
        "second_half": t("Druga połowa", "Second half"),
        "even": t("Parzyste", "Even CPUs"),
        "odd": t("Nieparzyste", "Odd CPUs"),
    }


def _affinity_id(value):
    """Config id of an affinity choice: preset id, or e.g. "CPU 0,2" unchanged."""
    text = str(value)
    for key, label in _affinity_presets().items():
        if text in (key, label):
            return key
    return _LEGACY_AFFINITY.get(text.split(" ")[0].lower(), text)


def _affinity_label(value):
    """Text shown for a stored affinity choice."""
    key = _affinity_id(value)
    return _affinity_presets().get(key, key)


class Wtyczka:
    nazwa = "cpu"
    API = 1
    TR = {}
    manager_visible = True
    version = "1.3.2"
    required = False
    # Panel służy także do przygotowania ustawień przed włączeniem egzekwowania.
    panel_available_when_off = True

    @property
    def manager_name(self):
        return t("CPU / Priorytet / Affinity", "CPU / Priority / Affinity")

    @property
    def manager_description(self):
        return t("Odczytuje i opcjonalnie egzekwuje priorytet oraz affinity "
                 "procesów serwerów po GOTOWY i karencji.",
                 "Reads and optionally enforces the priority and affinity "
                 "of server processes after READY and the grace period.")

    def __init__(self):
        self.core = None
        self.cfg = {"enabled": False, "delay_s": 30, "maps": {}}
        self.last_monitor = {}
        self.monitor_snapshot_received = False
        self.states = {}
        self.applied_pid = {}
        self.last_change = {}  # map -> exact PID, timestamp and properties changed by us
        self.next_check = 0.0
        self.window = None
        self.rows_frame = None
        self.rows = {}
        self.summary_var = None
        self.global_var = None
        self.global_status_label = None
        self.last_logged = {}
        self.benchmark_running = False
        self.benchmark_stop = False
        self.benchmark_results = {}
        self.benchmark_recommendations = {}
        self.benchmark_maps = []
        self.benchmark_status_var = None
        self.benchmark_progress = None
        self.benchmark_results_text = None

    def prepare(self, rdzen):
        self.core = rdzen
        raw = rdzen.plugin_config(self.nazwa)
        self.cfg = {
            "enabled": bool(raw.get("enabled", False)),
            "delay_s": max(26, int(raw.get("delay_s", 30))),
            "maps": dict(raw.get("maps", {})) if isinstance(raw.get("maps", {}), dict) else {},
        }
        self._publish_indicator()

    def set_enabled(self, enabled):
        self.cfg["enabled"] = bool(enabled)
        self.core.save_plugin_config(self.nazwa, self.cfg)
        self.core.set_plugin_toggle(self.nazwa, self.cfg["enabled"])
        if self.global_var is not None:
            self.global_var.set(self.cfg["enabled"])
        self._publish_indicator()
        if self.cfg["enabled"]:
            self.core.log(t("[CPU] GLOBAL ON — rozjazdy będą korygowane po GOTOWY i karencji",
                            "[CPU] GLOBAL ON — mismatches will be corrected after READY and the grace period"),
                          "cpu_ok")
            self._scan(time.time(), apply_changes=True)
        else:
            self.core.log(t("[CPU] GLOBAL OFF — tylko odczyt, żadnych zmian procesów",
                            "[CPU] GLOBAL OFF — read-only, no process changes"))
        self._refresh_panel_values()

    def dane_monitora(self, dane):
        # Even an empty snapshot is authoritative once the monitor completed.
        self.last_monitor = dict(dane or {})
        self.monitor_snapshot_received = True

    def tik(self, teraz):
        # Manager OFF means the plugin performs no background work and emits
        # no periodic process-state logs. Settings and manual panel stay available.
        if not self.cfg.get("enabled", False):
            return
        if teraz < self.next_check:
            return
        self.next_check = teraz + 5.0
        self._scan(teraz, apply_changes=True)

    def _scan(self, now, apply_changes=False):
        if not self.monitor_snapshot_received:
            # Startup synchronization: lack of monitor data is not evidence
            # that server processes are absent. Do not emit false PID=brak.
            if self.summary_var is not None:
                self.summary_var.set(t("Czekam na pierwszy skan monitora procesów…",
                                       "Waiting for the first process monitor scan…"))
            self._publish_indicator()
            return
        tabs = self.core.tabs()
        pid_by_port = self.last_monitor.get("pid", {})
        seen = set()
        for tab in tabs.values():
            if not tab.enabled:
                continue
            pid = pid_by_port.get(tab.rcon_port)
            state = {
                "name": tab.name, "pid": int(pid or 0), "server_status": tab.status,
                "restart": bool(getattr(tab, "restart", False)),
                "priority": "—", "affinity": "—", "affinity_mask": 0,
                "uptime": 0, "result": t("Brak procesu", "No process"), "color": "#b00020",
            }
            if not pid:
                if state["restart"]:
                    # V3.86.2: po DoExit z kolejki brak procesu to plan, nie błąd.
                    state["result"] = t("Restart po DoExit — CPU dopiero po READY",
                                        "Restart after DoExit — CPU only after READY")
                    state["color"] = "#b07000"
                self.states[tab.name] = state
                self._log_state_if_changed(tab.name, state)
                continue
            seen.add(int(pid))
            try:
                actual = self._read_process(int(pid))
                state.update(actual)
                state["priority"] = PRIORITY_BY_VALUE.get(actual["priority_value"],
                                                           hex(actual["priority_value"]))
                state["affinity"] = self._mask_text(actual["affinity_mask"])
                state["result"] = t("Odczytano aktualny stan", "Current state read")
                state["color"] = "#207020"
                if tab.status != "ready":
                    state["result"] = t("Serwer %s — bez ingerencji",
                                        "Server %s — no intervention") % tab.status.upper()
                    state["color"] = "#b07000"
                elif actual["uptime"] < self.cfg["delay_s"]:
                    state["result"] = t("GOTOWY — czekam na managera (%d/%d s)",
                                        "READY — waiting for the manager (%d/%d s)") % (
                        actual["uptime"], self.cfg["delay_s"])
                    state["color"] = "#b07000"
                elif apply_changes:
                    self._compare_and_apply(tab.name, state)
            except Exception as exc:
                state["result"] = t("Błąd odczytu: %s", "Read error: %s") % exc
                state["color"] = "#b00020"
            self.states[tab.name] = state
            self._log_state_if_changed(tab.name, state)
        # Remove dead PIDs from the once-per-process application memory.
        self.applied_pid = {name: pid for name, pid in self.applied_pid.items()
                            if pid in seen}
        self.last_change = {name: info for name, info in self.last_change.items()
                            if info.get("pid") in seen}
        self._refresh_panel_values()
        self._publish_indicator()

    def _log_state_if_changed(self, name, state):
        # V3.86.2: [CPU] w dzienniku dopiero przy READY. Fazy startu i restart po
        # DoExit (brak procesu, ładowanie modów, silnik) widać w panelu CPU, nie
        # w dzienniku — zmiany i tak są robione wyłącznie po READY i karencji.
        if state.get("server_status") != "ready" or state.get("restart"):
            return
        settings = self.cfg.get("maps", {}).get(name, {})
        target_p = settings.get("priority", "—") if settings.get("priority_on") else "OFF"
        target_a = _affinity_label(settings.get("affinity", "—")) if settings.get("affinity_on") else "OFF"
        signature = (state.get("pid"), state.get("server_status"), state.get("priority"),
                     state.get("affinity"), target_p, target_a, state.get("result"),
                     bool(self.cfg.get("enabled")))
        if self.last_logged.get(name) == signature:
            return
        self.last_logged[name] = signature
        message = (t("[CPU] %s | PID=%s | serwer=%s | aktualnie: priority=%s, affinity=%s\n"
                     "      → cel: priority=%s, affinity=%s | %s",
                     "[CPU] %s | PID=%s | server=%s | current: priority=%s, affinity=%s\n"
                     "      → target: priority=%s, affinity=%s | %s") %
                   (name, state.get("pid") or t("brak", "none"), state.get("server_status", "?"),
                    state.get("priority", "—"), state.get("affinity", "—"),
                    target_p, target_a, state.get("result", "")))
        color = state.get("color")
        if color == "#b00020":
            self.core.warn(message)
        else:
            tag = {"#207020": "cpu_ok", "#0066aa": "cpu_change",
                   "#b07000": "cpu_wait", "#555555": "cpu_off"}.get(
                       color, "cpu_read")
            self.core.log(message, tag)

    def _compare_and_apply(self, name, state):
        settings = self.cfg["maps"].get(name)
        if not settings:
            state["result"] = t("TYLKO ODCZYT — brak zapisanych ustawień",
                                "READ-ONLY — no saved settings")
            state["color"] = "#555555"
            return
        priority_on = bool(settings.get("priority_on", False))
        affinity_on = bool(settings.get("affinity_on", False))
        target_priority_name = settings.get("priority", "Normal")
        target_priority = PRIORITIES.get(target_priority_name, PRIORITIES["Normal"])
        target_mask = self._affinity_value(settings.get("affinity", "all"))
        priority_diff = priority_on and state["priority_value"] != target_priority
        affinity_diff = affinity_on and target_mask and state["affinity_mask"] != target_mask
        if not priority_on and not affinity_on:
            state["result"] = t("TYLKO ODCZYT — obie opcje wyłączone",
                                "READ-ONLY — both options turned off")
            state["color"] = "#555555"
            return
        if affinity_on and not target_mask:
            # V3.84: cel spoza tego komputera (np. „CPU 12” przy 8 CPU) dawał maskę 0
            # i fałszywe „ZGODNE”. Niczego nie zmieniamy, ale mówimy, co jest nie tak.
            state["result"] = (t("BŁĘDNY CEL AFFINITY: %s — takich CPU nie ma w tym komputerze; "
                                 "niczego nie zmieniam, popraw ustawienie",
                                 "INVALID AFFINITY TARGET: %s — no such CPUs on this computer; "
                                 "nothing is changed, fix the setting")
                               % _affinity_label(settings.get("affinity", "all")))
            state["color"] = "#b00020"
            return
        if not priority_diff and not affinity_diff:
            if not self.cfg["enabled"]:
                state["result"] = t("GLOBAL OFF — aktualny stan odpowiada zapisanemu celowi; "
                                    "plugin go nie egzekwuje",
                                    "GLOBAL OFF — the current state matches the saved target; "
                                    "the plugin does not enforce it")
                state["color"] = "#555555"
                return
            change = self.last_change.get(name)
            if change and change.get("pid") == state["pid"]:
                state["result"] = (t("ZGODNE — ostatnia zmiana tego PID wykonana przez plugin "
                                     "o %s (%s)",
                                     "MATCH — the last change of this PID was made by the plugin "
                                     "at %s (%s)") % (change["time"], ", ".join(change["what"])))
            else:
                state["result"] = t("ZGODNE — stan zastany przy uruchomieniu bieżącej sesji; "
                                    "brak zarejestrowanej zmiany w tej sesji",
                                    "MATCH — state as found when this session started; "
                                    "no change recorded in this session")
            state["color"] = "#207020"
            return
        if not self.cfg["enabled"]:
            parts = []
            if priority_diff: parts.append("priority %s → %s" % (state["priority"], target_priority_name))
            if affinity_diff: parts.append("affinity %s → %s" % (state["affinity"], self._mask_text(target_mask)))
            state["result"] = t("ROZJAZD (plugin OFF): ", "MISMATCH (plugin OFF): ") + "; ".join(parts)
            state["color"] = "#b00020"
            return
        self._apply_process(state["pid"], target_priority if priority_diff else None,
                            target_mask if affinity_diff else None)
        requested = []
        if priority_diff:
            requested.append("priority %s → %s" % (state["priority"], target_priority_name))
        if affinity_diff:
            requested.append("affinity %s → %s" % (state["affinity"], self._mask_text(target_mask)))
        # Do not trust only the Set* return value — read Windows again.
        verified = self._read_process(state["pid"])
        state["priority_value"] = verified["priority_value"]
        state["priority"] = PRIORITY_BY_VALUE.get(verified["priority_value"], hex(verified["priority_value"]))
        state["affinity_mask"] = verified["affinity_mask"]
        state["affinity"] = self._mask_text(verified["affinity_mask"])
        priority_ok = (not priority_on) or state["priority_value"] == target_priority
        affinity_ok = (not affinity_on) or state["affinity_mask"] == target_mask
        if priority_ok and affinity_ok:
            state["result"] = t("POPRAWIONO I POTWIERDZONO: ", "CORRECTED AND CONFIRMED: ") + "; ".join(requested)
            state["color"] = "#0066aa"
        else:
            state["result"] = (t("ZAPIS WINDOWS NIE UTRZYMAŁ SIĘ — po ponownym odczycie: "
                                 "priority=%s, affinity=%s",
                                 "WINDOWS DID NOT KEEP THE CHANGE — after re-reading: "
                                 "priority=%s, affinity=%s") % (state["priority"], state["affinity"]))
            state["color"] = "#b00020"
        self.applied_pid[name] = state["pid"]
        if priority_ok and affinity_ok:
            changed_what = []
            if priority_diff: changed_what.append("priority")
            if affinity_diff: changed_what.append("affinity")
            self.last_change[name] = {
                "pid": state["pid"],
                "time": time.strftime("%H:%M:%S"),
                "what": changed_what,
            }
        self.core.log("[CPU] %s PID %d — %s" % (name, state["pid"], state["result"]))

    def _read_process(self, pid):
        if os.name != "nt":
            raise OSError(t("panel procesów CPU działa na Windows",
                            "the CPU process panel requires Windows"))
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.GetPriorityClass.argtypes = (wintypes.HANDLE,)
        k32.GetProcessAffinityMask.argtypes = (wintypes.HANDLE,
                                               ctypes.POINTER(ctypes.c_size_t),
                                               ctypes.POINTER(ctypes.c_size_t))
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE,
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME),
                                       ctypes.POINTER(wintypes.FILETIME))
        PROCESS_QUERY_INFORMATION = 0x0400
        handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            raise PermissionError(t("brak dostępu do PID %d", "no access to PID %d") % pid)
        try:
            priority = int(k32.GetPriorityClass(handle))
            process_mask = ctypes.c_size_t()
            system_mask = ctypes.c_size_t()
            if not k32.GetProcessAffinityMask(handle, ctypes.byref(process_mask),
                                              ctypes.byref(system_mask)):
                raise OSError("GetProcessAffinityMask failed")
            creation = wintypes.FILETIME(); exit_t = wintypes.FILETIME()
            kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
            uptime = 0
            if k32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_t),
                                   ctypes.byref(kernel), ctypes.byref(user)):
                created = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
                now_filetime = int((time.time() + 11644473600) * 10000000)
                uptime = max(0, int((now_filetime - created) / 10000000))
            return {"priority_value": priority, "affinity_mask": int(process_mask.value),
                    "system_mask": int(system_mask.value), "uptime": uptime}
        finally:
            k32.CloseHandle(handle)

    def _apply_process(self, pid, priority=None, affinity=None):
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.SetProcessAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
        PROCESS_SET_INFORMATION = 0x0200
        handle = k32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
        if not handle:
            raise PermissionError(t("brak praw administratora do PID %d",
                                    "no administrator rights for PID %d") % pid)
        try:
            if priority is not None and not k32.SetPriorityClass(handle, priority):
                raise OSError("SetPriorityClass failed")
            if affinity is not None and not k32.SetProcessAffinityMask(handle, affinity):
                raise OSError("SetProcessAffinityMask failed")
        finally:
            k32.CloseHandle(handle)

    def _affinity_options(self):
        count = max(1, os.cpu_count() or 1)
        presets = _affinity_presets()
        options = [presets["all"]]
        if count > 1:
            options += [presets[key] for key in ("first_half", "second_half", "even", "odd")]
        options += ["CPU %d" % i for i in range(count)]
        return options

    def _affinity_value(self, label):
        count = max(1, os.cpu_count() or 1)
        all_mask = (1 << count) - 1
        label = _affinity_id(label)
        if label == "all": return all_mask
        if label == "first_half": return (1 << max(1, count // 2)) - 1
        if label == "second_half":
            low = max(1, count // 2); return all_mask ^ ((1 << low) - 1)
        if label == "even": return sum(1 << i for i in range(0, count, 2))
        if label == "odd": return sum(1 << i for i in range(1, count, 2)) or 1
        if str(label).startswith("CPU "):
            try:
                values = [int(x.strip()) for x in str(label)[4:].split(",")]
                return sum(1 << i for i in values if 0 <= i < count)
            except Exception: return 0
        return 0

    @staticmethod
    def _mask_text(mask):
        cpus = [str(i) for i in range(max(1, os.cpu_count() or 1)) if mask & (1 << i)]
        return "CPU " + ",".join(cpus) if cpus else t("brak", "none")

    def panel(self, rodzic):
        if self.window is not None:
            try:
                self.window.deiconify(); self.window.lift(); self.window.focus_force(); return self.window
            except tk.TclError:
                self.window = None
        win = tk.Toplevel(rodzic)
        self.window = win
        win.title("ASAonly — CPU Priority / Affinity")
        win.geometry("1250x650")
        win.minsize(980, 420)
        win.protocol("WM_DELETE_WINDOW", self._close_panel)
        top = ttk.Frame(win); top.pack(fill="x", padx=10, pady=10)
        self.global_var = tk.BooleanVar(value=bool(self.cfg.get("enabled")))
        ttk.Checkbutton(top, text="PLUGIN CPU GLOBAL ON/OFF",
                        variable=self.global_var,
                        command=lambda: self.set_enabled(self.global_var.get())).pack(side="left", padx=(0, 12))
        ttk.Button(top, text=t("Wykryj / odczytaj ponownie", "Detect / read again"),
                   command=self.detect_now).pack(side="left")
        self.summary_var = tk.StringVar(value=t("Oczekiwanie na dane monitora", "Waiting for monitor data"))
        self.global_status_label = ttk.Label(top, textvariable=self.summary_var,
                  font=("TkDefaultFont", 10, "bold"))
        self.global_status_label.pack(side="left", padx=15)
        ttk.Label(top, text=t("Zmiany dopiero po GOTOWY i min. %d s od startu procesu",
                              "Changes only after READY and at least %d s after process start") %
                  self.cfg["delay_s"]).pack(side="right")

        notebook = ttk.Notebook(win); notebook.pack(fill="both", expand=True, padx=8, pady=(0,8))
        tab_servers = ttk.Frame(notebook); tab_topology = ttk.Frame(notebook); tab_tester = ttk.Frame(notebook)
        notebook.add(tab_servers, text=t("1. SERWERY", "1. SERVERS"))
        notebook.add(tab_topology, text=t("2. TOPOLOGIA CPU", "2. CPU TOPOLOGY"))
        notebook.add(tab_tester, text=t("3. TESTER CPU", "3. CPU TESTER"))

        canvas = tk.Canvas(tab_servers, highlightthickness=0)
        scroll = ttk.Scrollbar(tab_servers, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        self.rows_frame = ttk.Frame(canvas)
        rows_id = canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(rows_id, width=max(e.width, 1180)))

        self._build_topology_tab(tab_topology)
        self._build_tester_tab(tab_tester)
        self.detect_now()
        return win

    def _topology_info(self):
        info = {"model": platform.processor() or t("Nieznany procesor", "Unknown processor"),
                "physical": None, "logical": max(1, os.cpu_count() or 1)}
        if os.name == "nt":
            try:
                command = ("Get-CimInstance Win32_Processor | Select-Object -First 1 "
                           "Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress")
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-Command", command], text=True,
                    timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                data = json.loads(out.strip())
                info["model"] = str(data.get("Name") or info["model"]).strip()
                info["physical"] = int(data.get("NumberOfCores") or 0) or None
                info["logical"] = int(data.get("NumberOfLogicalProcessors") or info["logical"])
            except Exception:
                pass
        return info

    def _build_topology_tab(self, parent):
        topology = self._topology_info(); count = topology["logical"]
        box = ttk.Frame(parent, padding=16); box.pack(fill="both", expand=True)
        ttk.Label(box, text=t("TOPOLOGIA CPU — ODCZYT BEZ OBCIĄŻENIA", "CPU TOPOLOGY — READ WITHOUT LOAD"),
                  font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(box, text=topology["model"], font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(10,2))
        physical = str(topology["physical"]) if topology["physical"] else t("brak danych", "no data")
        ttk.Label(box, text=(t("Rdzenie fizyczne: %s | procesory logiczne: %d. Numery CPU poniżej "
                               "są numerami używanymi przez maskę affinity.",
                               "Physical cores: %s | logical processors: %d. The CPU numbers below "
                               "are the numbers used by the affinity mask.") % (physical, count))).pack(anchor="w")
        grid = ttk.LabelFrame(box, text=t("Logiczne CPU", "Logical CPUs"), padding=10); grid.pack(fill="x", pady=14)
        for i in range(count):
            ttk.Label(grid, text="CPU %d" % i, relief="solid", padding=(8,5)).grid(
                row=i//8, column=i%8, padx=3, pady=3, sticky="ew")
        ttk.Label(box, text=t("Sama numeracja nie dowodzi, które CPU są P-core/E-core ani które są "
                              "rodzeństwem SMT. Zakładka TESTER mierzy każdy logiczny CPU i tworzy "
                              "praktyczny ranking. Nie wybieraj jednego CPU dla serwera.",
                              "The numbering alone does not prove which CPUs are P-cores/E-cores or which are "
                              "SMT siblings. The TESTER tab measures each logical CPU and builds "
                              "a practical ranking. Do not pick a single CPU for a server."),
                  foreground="#555555", wraplength=900, justify="left").pack(anchor="w", pady=5)

    def _build_tester_tab(self, parent):
        box = ttk.Frame(parent, padding=16); box.pack(fill="both", expand=True)
        ttk.Label(box, text=t("TESTER WYDAJNOŚCI LOGICZNYCH CPU", "LOGICAL CPU BENCHMARK"),
                  font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(box, text=t("Test przypina jeden wątek testowy kolejno do CPU 0…N. Nie zmienia "
                              "procesów serwerów ani ich affinity. Podczas testu może wystąpić "
                              "chwilowe dodatkowe obciążenie.",
                              "The test pins one test thread to CPU 0…N in turn. It does not change "
                              "server processes or their affinity. A brief extra load may occur "
                              "during the test."), wraplength=900,
                  justify="left").pack(anchor="w", pady=(5,10))
        buttons = ttk.Frame(box); buttons.pack(fill="x")
        ttk.Button(buttons, text=t("SZYBKI TEST (~0,25 s / CPU)", "QUICK TEST (~0.25 s / CPU)"),
                   command=lambda:self._start_benchmark(0.25)).pack(side="left", padx=(0,6))
        ttk.Button(buttons, text=t("DOKŁADNY TEST (~0,75 s / CPU)", "THOROUGH TEST (~0.75 s / CPU)"),
                   command=lambda:self._start_benchmark(0.75)).pack(side="left", padx=6)
        ttk.Button(buttons, text=t("PRZERWIJ", "STOP"), command=self._stop_benchmark).pack(side="left", padx=6)
        ttk.Button(buttons, text=t("PRZENIEŚ PROPOZYCJE DO SERWERÓW", "COPY PROPOSALS TO SERVERS"),
                   command=self._apply_recommendations_to_rows).pack(side="right")
        self.benchmark_status_var = tk.StringVar(value=t("Test nie był uruchamiany.", "The test has not been run."))
        ttk.Label(box, textvariable=self.benchmark_status_var,
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(12,4))
        self.benchmark_progress = ttk.Progressbar(box, mode="determinate")
        self.benchmark_progress.pack(fill="x")
        result_box = ttk.LabelFrame(box, text=t("Ranking i propozycje", "Ranking and proposals"), padding=8)
        result_box.pack(fill="both", expand=True, pady=(10,0))
        self.benchmark_results_text = tk.Text(result_box, height=18, wrap="word", state="disabled")
        self.benchmark_results_text.pack(fill="both", expand=True)

    def _start_benchmark(self, duration):
        if self.benchmark_running:
            messagebox.showwarning(t("Tester CPU", "CPU tester"), t("Test już trwa.", "A test is already running."),
                                   parent=self.window); return
        if not messagebox.askyesno(t("Tester CPU — potwierdzenie", "CPU tester — confirmation"),
                t("Test obciąży kolejno każdy logiczny CPU. Serwery nie zostaną zmienione.\n\nUruchomić?",
                  "The test will load each logical CPU in turn. The servers will not be changed.\n\nRun it?"),
                parent=self.window): return
        self.benchmark_running = True; self.benchmark_stop = False
        self.benchmark_results = {}; self.benchmark_recommendations = {}
        self.benchmark_maps = sorted(tab.name for tab in self.core.tabs().values() if tab.enabled)
        count = min(max(1, os.cpu_count() or 1), 64)
        self.benchmark_progress.configure(maximum=count, value=0)
        self.benchmark_status_var.set(t("Uruchamianie testu…", "Starting the test…"))
        threading.Thread(target=self._benchmark_worker, args=(duration, count), daemon=True).start()

    def _stop_benchmark(self):
        self.benchmark_stop = True
        if self.benchmark_running and self.benchmark_status_var:
            self.benchmark_status_var.set(t("Zatrzymywanie po bieżącym CPU…", "Stopping after the current CPU…"))

    @staticmethod
    def _bench_one(cpu_index, duration):
        previous = None; k32 = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            k32.GetCurrentThread.restype = wintypes.HANDLE
            k32.SetThreadAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
            k32.SetThreadAffinityMask.restype = ctypes.c_size_t
            previous = k32.SetThreadAffinityMask(k32.GetCurrentThread(), ctypes.c_size_t(1 << cpu_index))
            if not previous:
                raise OSError(t("SetThreadAffinityMask failed dla CPU %d",
                                "SetThreadAffinityMask failed for CPU %d") % cpu_index)
        try:
            end = time.perf_counter() + duration; loops = 0; x = 0x12345678
            while time.perf_counter() < end:
                for _ in range(1500):
                    x = ((x * 1664525 + 1013904223) ^ (x >> 7)) & 0xffffffff
                loops += 1500
            return loops / duration
        finally:
            if k32 is not None and previous:
                k32.SetThreadAffinityMask(k32.GetCurrentThread(), previous)

    def _benchmark_worker(self, duration, count):
        errors = []
        try:
            for cpu in range(count):
                if self.benchmark_stop: break
                self.core.post_ui(lambda c=cpu: self.benchmark_status_var.set(
                    t("Testuję CPU %d z %d…", "Testing CPU %d of %d…") % (c, count-1)))
                try: self.benchmark_results[cpu] = self._bench_one(cpu, duration)
                except Exception as exc: errors.append("CPU %d: %s" % (cpu, exc))
                self.core.post_ui(lambda v=cpu+1: self._pokaz_postep_testu(v))
        finally:
            self.benchmark_running = False
            self._make_recommendations()
            self.core.post_ui(lambda: self._show_benchmark_results(errors, self.benchmark_stop))

    def _make_recommendations(self):
        ranked = [cpu for cpu, score in sorted(self.benchmark_results.items(),
                                                key=lambda x:x[1], reverse=True)]
        maps = list(self.benchmark_maps)
        self.benchmark_recommendations = {name: [] for name in maps}
        if not maps: return
        # Balanced round-robin over measured CPUs; every server receives several CPUs
        # whenever hardware capacity allows it.
        for index, cpu in enumerate(ranked):
            self.benchmark_recommendations[maps[index % len(maps)]].append(cpu)
        for values in self.benchmark_recommendations.values(): values.sort()

    @staticmethod
    def _widget_zyje(widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    def _pokaz_postep_testu(self, wartosc):
        # V3.84: panel mógł zostać zamknięty w trakcie testu — wtedy nie ma czego odświeżać.
        if self._widget_zyje(self.benchmark_progress):
            self.benchmark_progress.configure(value=wartosc)

    def _show_benchmark_results(self, errors, stopped):
        if not self._widget_zyje(self.benchmark_results_text): return
        scores = sorted(self.benchmark_results.items(), key=lambda x:x[1], reverse=True)
        best = scores[0][1] if scores else 1
        lines = [t("RANKING (wynik względny; 100% = najlepszy pomiar):",
                   "RANKING (relative score; 100% = best measurement):")]
        for cpu, score in scores:
            lines.append("CPU %-2d  %6.1f%%" % (cpu, 100.0*score/best))
        lines.append(t("\nPROPOZYCJE — wiele logicznych CPU na serwer:",
                       "\nPROPOSALS — several logical CPUs per server:"))
        for name, cpus in self.benchmark_recommendations.items():
            lines.append("%s: CPU %s" % (name, ",".join(map(str,cpus))))
        if errors: lines.append(t("\nBŁĘDY:\n", "\nERRORS:\n") + "\n".join(errors))
        self.benchmark_results_text.configure(state="normal")
        self.benchmark_results_text.delete("1.0","end"); self.benchmark_results_text.insert("1.0","\n".join(lines))
        self.benchmark_results_text.configure(state="disabled")
        self.benchmark_status_var.set(t("Test przerwany — wyniki częściowe", "Test stopped — partial results")
                                      if stopped else
                                      t("Test zakończony; propozycje nie są jeszcze zapisane",
                                        "Test finished; the proposals are not saved yet"))
        self.core.log(t("[CPU TESTER] %s; pomierzono %d CPU", "[CPU TESTER] %s; measured %d CPUs") %
                      (t("PRZERWANY", "STOPPED") if stopped else t("ZAKOŃCZONY", "FINISHED"), len(scores)),
                      "cpu_wait" if stopped else "plugin_ok")

    def _apply_recommendations_to_rows(self):
        if not self.benchmark_recommendations:
            messagebox.showwarning(t("Tester CPU", "CPU tester"),
                                   t("Brak propozycji. Najpierw wykonaj test.", "No proposals. Run the test first."),
                                   parent=self.window); return
        applied = 0
        for name, cpus in self.benchmark_recommendations.items():
            row = self.rows.get(name)
            if row and cpus:
                row["affinity"].set("CPU " + ",".join(map(str,cpus)))
                applied += 1
        messagebox.showinfo(t("Tester CPU", "CPU tester"), t("Przeniesiono propozycje do %d wierszy zakładki SERWERY.\n"
            "Affinity nie zostało włączone ani zapisane. Sprawdź propozycje, zaznacz Affinity i użyj Zapisz ustawienia.",
            "Copied the proposals to %d rows of the SERVERS tab.\n"
            "Affinity was not turned on or saved. Check the proposals, tick the Affinity box and use Save settings.") % applied,
            parent=self.window)

    def _close_panel(self):
        self.benchmark_stop = True
        if self.window is not None:
            try: self.window.destroy()
            except tk.TclError: pass
        self.window = None; self.rows_frame = None; self.rows = {}

    def detect_now(self):
        self.core.log(t("[CPU] RĘCZNY ODCZYT — wykrywam aktywne serwery i bieżące ustawienia Windows",
                        "[CPU] MANUAL READ — detecting active servers and current Windows settings"))
        self.last_logged.clear()
        self._scan(time.time(), apply_changes=False)
        self._build_rows()

    def _build_rows(self):
        if self.rows_frame is None: return
        for child in self.rows_frame.winfo_children(): child.destroy()
        self.rows = {}
        headers = [t("Serwer / stan", "Server / status"), "PID / uptime",
                   t("AKTUALNY priority", "CURRENT priority"),
                   t("Priority ON/OFF i cel", "Priority ON/OFF and target"),
                   t("AKTUALNE affinity", "CURRENT affinity"),
                   t("Affinity ON/OFF i cel", "Affinity ON/OFF and target"), t("Wynik", "Result"), ""]
        for col,text in enumerate(headers):
            ttk.Label(self.rows_frame,text=text,font=("TkDefaultFont",9,"bold")).grid(
                row=0,column=col,padx=5,pady=6,sticky="w")
        for row_index,name in enumerate(sorted(self.states), start=1):
            state=self.states[name]; saved=self.cfg["maps"].get(name,{})
            p_on=tk.BooleanVar(value=bool(saved.get("priority_on",False)))
            p_val=tk.StringVar(value=saved.get("priority", state["priority"] if state["priority"] in PRIORITIES else "Normal"))
            a_on=tk.BooleanVar(value=bool(saved.get("affinity_on",False)))
            a_val=tk.StringVar(value=_affinity_label(saved.get("affinity","all")))
            vars_={"priority_on":p_on,"priority":p_val,"affinity_on":a_on,"affinity":a_val}
            self.rows[name]=vars_
            ttk.Label(self.rows_frame,text="%s\n%s"%(name,state["server_status"].upper())).grid(row=row_index,column=0,padx=5,pady=5,sticky="w")
            ttk.Label(self.rows_frame,text="%s\n%s"%(state["pid"] or "—",self._uptime_text(state["uptime"]))).grid(row=row_index,column=1,padx=5,sticky="w")
            vars_["actual_priority_label"]=ttk.Label(self.rows_frame,text=state["priority"])
            vars_["actual_priority_label"].grid(row=row_index,column=2,padx=5,sticky="w")
            pf=ttk.Frame(self.rows_frame); pf.grid(row=row_index,column=3,padx=5,sticky="w")
            ttk.Checkbutton(pf,variable=p_on).pack(side="left")
            ttk.Combobox(pf,textvariable=p_val,values=list(PRIORITIES),state="readonly",width=14).pack(side="left")
            vars_["actual_affinity_label"]=ttk.Label(self.rows_frame,text=state["affinity"],wraplength=180)
            vars_["actual_affinity_label"].grid(row=row_index,column=4,padx=5,sticky="w")
            af=ttk.Frame(self.rows_frame); af.grid(row=row_index,column=5,padx=5,sticky="w")
            ttk.Checkbutton(af,variable=a_on).pack(side="left")
            ttk.Combobox(af,textvariable=a_val,values=self._affinity_options(),state="readonly",width=16).pack(side="left")
            vars_["result_label"]=ttk.Label(self.rows_frame,text=state["result"],foreground=state["color"],wraplength=260)
            vars_["result_label"].grid(row=row_index,column=6,padx=5,sticky="w")
            ttk.Button(self.rows_frame,text=t("Zapisz ustawienia", "Save settings"),
                       command=lambda n=name:self._save_row(n)).grid(row=row_index,column=7,padx=5)

    def _save_row(self, name):
        row=self.rows[name]
        self.cfg["maps"][name]={"priority_on":bool(row["priority_on"].get()),
                                "priority":row["priority"].get(),
                                "affinity_on":bool(row["affinity_on"].get()),
                                "affinity":_affinity_id(row["affinity"].get())}
        self.core.save_plugin_config(self.nazwa,self.cfg)
        saved = self.cfg["maps"][name]
        self.core.log(t("[CPU] ZAPIS %s | priority: %s / %s | affinity: %s / %s | global=%s",
                        "[CPU] SAVED %s | priority: %s / %s | affinity: %s / %s | global=%s") %
                      (name, "ON" if saved["priority_on"] else "OFF", saved["priority"],
                       "ON" if saved["affinity_on"] else "OFF", _affinity_label(saved["affinity"]),
                       "ON" if self.cfg["enabled"] else "OFF"), "cpu_config")
        if not self.cfg["enabled"]:
            messagebox.showwarning(
                t("CPU — zapisano, ale plugin jest wyłączony", "CPU — saved, but the plugin is turned off"),
                t("Ustawienia zapisano, ale GLOBAL CPU jest OFF.\n"
                  "Plugin niczego nie zmieni, dopóki nie włączysz przełącznika u góry panelu lub w głównym oknie.",
                  "Settings saved, but GLOBAL CPU is OFF.\n"
                  "The plugin will not change anything until you turn on the switch at the top of the panel "
                  "or in the main window."),
                parent=self.window)
        else:
            messagebox.showinfo("CPU", t("Zapisano. Odczytuję ponownie i stosuję tylko rzeczywisty rozjazd: %s",
                                         "Saved. Reading again and applying only a real mismatch: %s")%name,
                                parent=self.window)
        self.last_logged.pop(name, None)
        self._scan(time.time(),apply_changes=bool(self.cfg["enabled"]))

    def _refresh_panel_values(self):
        if self.window is None: return
        for name,row in list(self.rows.items()):
            state=self.states.get(name)
            if not state: continue
            try:
                row["actual_priority_label"].configure(text=state["priority"])
                row["actual_affinity_label"].configure(text=state["affinity"])
                row["result_label"].configure(text=state["result"],foreground=state["color"])
            except tk.TclError: pass
        if self.summary_var is not None:
            self.summary_var.set(self._summary())

    @staticmethod
    def _uptime_text(seconds):
        seconds=int(seconds or 0); return "%02d:%02d:%02d"%(seconds//3600,(seconds//60)%60,seconds%60)

    def _summary(self):
        if not self.states: return t("Nie wykryto aktywnych serwerów", "No active servers detected")
        errors=sum(s["color"]=="#b00020" for s in self.states.values())
        waiting=sum(s["color"]=="#b07000" for s in self.states.values())
        good=sum(s["color"]=="#207020" for s in self.states.values())
        if errors: return t("%d problemów / rozjazdów", "%d problems / mismatches")%errors
        if waiting: return t("%d serwerów oczekuje", "%d servers waiting")%waiting
        return t("%d/%d zgodne lub odczytane", "%d/%d matching or read")%(good,len(self.states))

    def _publish_indicator(self):
        if self.core is None: return
        if not self.cfg.get("enabled"):
            text,color="OFF","#555555"
        elif not self.monitor_snapshot_received:
            text,color=t("ON — czekam na pierwszy skan monitora", "ON — waiting for the first monitor scan"),"#b07000"
        elif not self.states:
            text,color=t("ON — brak aktywnych map", "ON — no active maps"),"#b07000"
        else:
            bad=sum(s["color"]=="#b00020" for s in self.states.values())
            wait=sum(s["color"]=="#b07000" for s in self.states.values())
            if bad: text,color=t("%d rozjazdów", "%d mismatches")%bad,"#b00020"
            elif wait: text,color=t("%d oczekuje", "%d waiting")%wait,"#b07000"
            else: text,color=t("%d serwerów OK", "%d servers OK")%len(self.states),"#207020"
        self.core.set_indicator(self.nazwa,text,color)

    def start(self, core):
        self.prepare(core)

    def is_enabled(self):
        return bool(self.cfg.get("enabled", False))

    def self_test(self):
        """Read-only test for the manager; never calls a Windows setter."""
        if os.name != "nt":
            return {"ok": False, "details": t("plugin CPU wymaga Windows", "the CPU plugin requires Windows")}
        import ctypes
        required = ("OpenProcess", "GetPriorityClass", "GetProcessAffinityMask",
                    "GetProcessTimes", "SetPriorityClass", "SetProcessAffinityMask")
        missing = [name for name in required if not hasattr(ctypes.windll.kernel32, name)]
        if missing:
            raise RuntimeError(t("brak Windows API: ", "missing Windows API: ") + ", ".join(missing))
        readable = 0
        errors = []
        for name, state in self.states.items():
            pid = int(state.get("pid") or 0)
            if not pid:
                continue
            try:
                self._read_process(pid)
                readable += 1
            except Exception as exc:
                errors.append("%s/PID %d: %s" % (name, pid, exc))
        if errors:
            return {"ok": False, "details": "; ".join(errors)}
        admin = self.core.is_admin() if hasattr(self.core, "is_admin") else None
        if admin is False:
            return {"ok": False,
                    "details": t("Windows API i odczyt %d PID: OK; ADMIN: NIE — "
                                 "test bez zapisu, zmiana procesu może zostać odrzucona",
                                 "Windows API and reading %d PIDs: OK; ADMIN: NO — "
                                 "read-only test, a process change may be rejected") % readable}
        admin_text = (t("ADMIN: TAK", "ADMIN: YES") if admin is True else
                      t("status administratora nieznany", "administrator status unknown"))
        return {"ok": True,
                "details": t("Windows API OK; odczytano %d aktywnych PID; %s; bez zapisu",
                             "Windows API OK; read %d active PIDs; %s; nothing written") %
                           (readable, admin_text)}

    def konfiguracja(self): return dict(self.cfg)
    def stop(self): self._close_panel()
