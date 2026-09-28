# -*- coding: utf-8 -*-
"""Task 1: process/port health monitor and read-only RCON probes."""
import os
import re
import subprocess
import time

from .jezyk import t
from .monitor import _netstat_map, pad_klasyfikuj, dziennik_dopisz

MONITOR_TICK_S=10
WISI_S=20*60
WISI_SONDA_S=15*60
PAD4_OKNO_S=90
DL_STUCK_S=20*60

class MonitorMixin:
    def _monitor_init(self):
            """3.71: stan monitora ogolnego (procesy+porty+WISI+pady+CF)."""
            if hasattr(self, "_mon"):
                return  # 3.71 FIX: init dokladnie raz (wczesniej co tick!)
            self._mon = True
            self._mon_busy = False
            self._mon_next = 0.0
            self._pad4 = {}          # name -> {"t0": czas sladu crasha}
            self._pad_byl = {}       # name -> True (juz zgloszony pad w tej rundzie)
            self._last_pid_by_port = {}  # port -> ostatni autorytatywnie widziany PID
            self._monitor_error_last = {}
            self._samorestarty = {}  # name -> liczba ready->starting bez czlowieka
            self._auto_next_t = None
            self._cf_st = "ok"       # ok | blad
            self._cf_t0 = 0.0
            self._cf_next = 0.0
            # 3.71.1: stan per-tab (_wisi_st/_sonda_t/_dl_last/_dl_alarm/
            # _last_log_t) inicjuje SAM ServerTab.__init__ - taby powstaja tez
            # PO starcie monitora (zmiana jezyka, dodanie mapy, import) i kazdy
            # nosi swoj stan od urodzenia. Tu juz zadnych tabow nie dotykamy
            # (wczesniej ta petla ustawiala stan TYLKO tabom z chwili startu
            # i maskowala problem).
            self.log(self.tr("mon_start"))

    def _pid_map(self):
            """3.71: port(TCP, sluchajacy) -> PID. Netstat na win, ss na posix.
            Pusta mapa = nie wiemy (wtedy PAD-y nie sa zgloszone - zero falszywych)."""
            mapa = {}
            try:
                if os.name == "nt":
                    out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                                         capture_output=True, timeout=8).stdout
                    return _netstat_map(out.decode("utf-8", "replace"))  # 3.73
                else:
                    out = subprocess.run(["ss", "-tln"],
                                         capture_output=True, timeout=8).stdout
                    out = out.decode("utf-8", "replace")
                    for linia in out.splitlines()[1:]:
                        mm = re.search(r":(\d+)\s", linia)
                        if mm:
                            mapa.setdefault(mm.group(1), 0)
            except Exception as exc:
                raise RuntimeError(t("odczyt portów/PID nie powiódł się: %s",
                                     "reading ports/PIDs failed: %s") % exc) from exc
            return mapa

    def _proc_zyje(self, pid):
            """3.71: czy proces o PID zyje (win: tasklist, posix: kill 0)."""
            if not pid:
                return True  # PID nieznany -> zakladamy zycie (nie false'ujemy PAD-u)
            try:
                if os.name == "nt":
                    out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                                         capture_output=True, timeout=8).stdout
                    return str(pid) in out.decode("utf-8", "replace")
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    return False
                except PermissionError:
                    return True
            except Exception as exc:
                raise RuntimeError(t("sprawdzenie PID %s nie powiodło się: %s",
                                     "checking PID %s failed: %s") % (pid, exc)) from exc

    def _tab_alive(self, tab, pid_map):
            port = tab.var_port.get().strip()
            pid = pid_map.get(port)
            if pid is None:
                pid = self._server_pid_for_tab(tab)  # start przed otwarciem RCON
            if pid is not None:
                self._last_pid_by_port[port] = pid
                identity = self._process_identity(pid)
                tab._monitor_identity = identity
                if identity is not None:
                    self.__dict__.setdefault("_last_identity_by_port", {})[port] = identity
                else:
                    self.__dict__.get("_last_identity_by_port", {}).pop(port, None)
                return self._proc_zyje(pid), pid
            previous = self._last_pid_by_port.get(port)
            if previous is None:
                # Pierwszy niepełny skan pozostaje stanem nieznanym; bez
                # wcześniejszego PID nie wolno zgłaszać fałszywego padu.
                return True, None
            # Port zniknął. Dopóki dawny PID żyje, proces może być w przejściu.
            # Gdy PID naprawdę zniknął, zwracamy pewny OFFLINE i nadal czekamy
            # na nowy PID uruchomiony przez ASADedicatedManager.
            identity = self.__dict__.get("_last_identity_by_port", {}).get(port)
            if identity is not None:
                alive = self._identity_alive(identity)
                if alive is None:
                    raise RuntimeError("process identity unavailable")
                return alive, previous
            return self._proc_zyje(previous), previous

    def _process_identity(self, pid):
            if os.name != "nt" or not pid:
                return None
            try:
                from .zamrazanie import ApiWindows
                api = ApiWindows()
                start = api.czas_startu(pid)
                return (int(pid), int(start)) if api.zyje(pid, start) else None
            except OSError:
                return None

    def _identity_alive(self, identity):
            if os.name != "nt" or identity is None:
                return None
            try:
                from .zamrazanie import ApiWindows
                return ApiWindows().zyje(*identity)
            except OSError:
                return None  # niepewność nie dowodzi przeżycia ani śmierci

    def _server_pid_for_tab(self, tab):
            """Dokładna ścieżka EXE mapy, gdy proces jeszcze nie słucha na RCON."""
            var = getattr(tab, "var_log", None)
            if os.name != "nt" or var is None or not var.get().strip():
                return None
            logs = os.path.normpath(var.get().strip())
            if os.path.basename(logs).lower() != "logs" or os.path.basename(os.path.dirname(logs)).lower() != "saved":
                return None
            expected = os.path.normcase(os.path.join(os.path.dirname(os.path.dirname(logs)),
                                                    "Binaries", "Win64", "ArkAscendedServer.exe"))
            from .zamrazanie import ApiWindows
            api = ApiWindows()
            matches = []
            for pid in api.procesy("ArkAscendedServer.exe"):
                try:
                    if os.path.normcase(api.sciezka_exe(pid)) == expected:
                        matches.append(pid)
                except OSError:
                    continue
            return matches[0] if len(matches) == 1 else None

    def _archive_pad(self, tab, reason):
            root = getattr(self, "knowledge_dir", None)
            var = getattr(tab, "var_log", None)
            if not root or var is None or not var.get().strip():
                return
            folder, name = var.get().strip(), tab.name
            identity = getattr(tab, "_monitor_identity", None)
            limit_bytes = self.__dict__.get("pad_archive_limit_mib", 2048) * 1024 * 1024
            def save():
                from .archiwum_padow import zapisz_dowody
                result = zapisz_dowody(root, name, folder, reason, identity, limit_bytes=limit_bytes)
                self.post_ui(lambda: (self.log_warn if result.get("warning") else self.log)(result["message"]))
            self.run_async(save)

    def _monitor_worker(self):
            """3.71: cykl 10 s w watku: zbierz dane (netstat + wiek logow),
            decyzje oddaj do watku UI przez post_ui (zero Tk z watku)."""
            if getattr(self, "_destroying", False):
                return
            dane = {"pid": {}, "wiek": {}}
            try:
                dane["pid"] = self._pid_map()
                teraz = time.time()
                # 3.71.1: snapshot tabow - w miedzy czasie UI moze przebudowac
                # self.tabs (zmiana jezyka burzy i stawia taby na nowo); iteracja
                # po zywym slowniku z watku grozila "dictionary changed size
                # during iteration"
                for name, tab in list(self.tabs.items()):
                    dane["wiek"][name] = teraz - getattr(tab, "_last_log_t", teraz)
                self.post_ui(lambda: self._monitor_apply(dane))
            except Exception as e:
                # V3.81: treść błędu wiązana TERAZ (argument domyślny). Wcześniej
                # lambda odwoływała się do 'e' po wyjściu z bloku except —
                # w UI pojawiało się „cannot access free variable 'e'” zamiast
                # prawdziwej przyczyny, co 10 s.
                tekst = self.tr("mon_blad", e=str(e))
                try:
                    self.post_ui(lambda t=tekst: self._monitor_warn_throttled("worker", t))
                except Exception as dispatch_exc:
                    print(t("Monitor: nie udało się przekazać błędu do UI: %s; pierwotny: %s",
                            "Monitor: could not pass the error to the UI: %s; original: %s")
                          % (dispatch_exc, tekst))
            finally:
                self._mon_busy = False

    def _monitor_warn_throttled(self, key, text, interval=60.0):
            now = time.time()
            if now - self._monitor_error_last.get(key, 0.0) >= interval:
                self._monitor_error_last[key] = now
                self.log_warn(text)

    def _monitor_apply(self, dane):
            """3.71: decyzje monitora (w watku UI)."""
            now = time.time()
            if hasattr(self, "plugin_host"):
                self.plugin_host.call_hook("dane_monitora", dict(dane))
                self.plugin_host.emit("monitor.data", data=dict(dane), now=now)
            for name, tab in self.tabs.items():
                if not tab.var_map_on.get():
                    continue
                try:
                    alive, pid = self._tab_alive(tab, dane["pid"])
                except Exception as exc:
                    self._monitor_warn_throttled(
                        ("pid", name), t("[%s] Monitor procesu nie ustalił stanu: %s",
                                         "[%s] Process monitor could not determine the state: %s")
                        % (name, exc))
                    continue
                wiek = dane["wiek"].get(name, 0.0)
                # --- PAD4: slad crasha w logu, proces zyje -> okno 90 s ---
                st4 = self._pad4.get(name)
                if st4:
                    original = st4.get("identity")
                    survived = self._identity_alive(original)
                    if survived is False:
                        del self._pad4[name]
                        self.log_warn(self.tr("pad_crash", tab=name) +
                                      " [PID/start=%s; current=%s]" % (original, getattr(tab, "_monitor_identity", None) if alive else None))
                        self._archive_pad(tab, "crash_process_exited")
                        if not alive:
                            self._pad_byl[name] = True
                    elif now - st4["t0"] >= PAD4_OKNO_S:
                        del self._pad4[name]
                        if survived is True and getattr(tab, "_monitor_identity", None) == original:
                            self.log(self.tr("pad4_koniec", tab=name, s=int(now - st4["t0"])))
                        else:
                            self.log_warn(t("[%s] Po śladzie crasha nie potwierdzono tożsamości pierwotnego procesu — wynik niepewny.",
                                            "[%s] Original process identity after the crash trace is unconfirmed — outcome uncertain.") % name)
                # --- PAD pewny: proces zniknal (PID znany = pewnosc) ---
                if pid is not None and not alive and not self._pad_byl.get(name):
                    self._pad_byl[name] = True
                    kl = pad_klasyfikuj(alive, tab._tail_status == "crash")
                    w_restarcie = getattr(self, "mapa_w_restarcie", None)
                    if kl == "PAD_BEZ_SLADU" and w_restarcie is not None and w_restarcie(name):
                        # V3.86.2: proces zniknął po DoExit z kolejki — to plan, nie pad.
                        self.log(self.tr("zamkniety_po_doexit", tab=name))
                    else:
                        self._archive_pad(tab, kl)
                        self.log(self.tr("pad_bez_sladu", tab=name) if kl == "PAD_BEZ_SLADU"
                                 else self.tr("pad_crash", tab=name))
                    tab._apply_tail("offline", "")
                if pid is not None and alive:
                    self._pad_byl[name] = False
                if getattr(type(self), "_check_return_alarm", None) is not None:
                    self._check_return_alarm(tab, alive)
                # UNKNOWN after startup can mean that READY fell outside the bounded
                # initial log scan. Resolve it with independent read-only RCON proof;
                # never infer STARTING from unrelated new log activity.
                if ((tab._tail_status == "unknown" or self._needs_return_probe(tab)) and alive and
                        now >= getattr(tab, "_sonda_t", 0.0) + 30.0):
                    tab._sonda_t = now
                    self._sonda_rcon(tab, confirm_unknown=True)
                # --- WISI: cisza loga 15 min -> sonda, 20 min -> alarm ---
                if wiek >= WISI_SONDA_S and now >= getattr(tab, "_sonda_t", 0.0) + WISI_SONDA_S:
                    tab._sonda_t = now
                    if tab._wisi_st == 0:
                        tab._wisi_st = 1
                        self.log(self.tr("wisi_sonda", tab=name, m=int(wiek // 60)))
                    self._sonda_rcon(tab)
                if wiek >= WISI_S and tab._wisi_st < 2:
                    tab._wisi_st = 2
                    self.log(self.tr("wisi_info", tab=name, m=int(wiek // 60)))
                if wiek < WISI_SONDA_S and tab._wisi_st:
                    m = int(wiek // 60)
                    tab._wisi_st = 0
                    self.log(self.tr("wisi_wrocil", tab=name, m=m))
                # --- pobieranie modów przez CFCore bez postępu (linie LogCFCore;
                #     tekstu "Downloading mod" prawdziwy log ASA nie wypisuje) ---
                if tab._dl_last and now - tab._dl_last >= DL_STUCK_S and not tab._dl_alarm:
                    tab._dl_alarm = True
                    self.log(self.tr("dl_stuck", tab=name, m=int((now - tab._dl_last) // 60)))

    def _needs_return_probe(self, tab):
            if tab._tail_status not in ("unknown", "ready"):
                return False
            record = (self.__dict__.get("watch_maps") or {}).get(tab.name)
            if not record:
                record = (self.__dict__.get("config_data", {}).get("return_failures") or {}).get(tab.name)
            current = getattr(tab, "_monitor_identity", None)
            before = record.get("identity") if record else None
            return bool(before is not None and current is not None
                        and tuple(before) != tuple(current)
                        and not self._ready_since(tab, record))

    def _sonda_rcon(self, tab, confirm_unknown=False):
            """Allow a read-only return probe only after DoExit, for a new process."""
            returning = self._needs_return_probe(tab)
            if getattr(self, "restart_active", False) and not returning:
                return
            tab_name = tab.name
            identity = getattr(tab, "_monitor_identity", None)
            boot_seq = tab._boot_seq
            confirm = confirm_unknown or returning
            def _cb(err):
                if getattr(self, "_destroying", False):
                    return
                def apply_result():
                    current = self.tabs.get(tab_name)
                    if current is not tab:
                        return
                    if err is None and confirm:
                        if identity is not None:
                            # Check the captured process again: the monitor snapshot
                            # may lag behind a death or PID reuse while RCON is queued.
                            if (getattr(tab, "_monitor_identity", None) == identity
                                    and tab._boot_seq == boot_seq
                                    and self._identity_alive(identity) is True):
                                tab.confirm_ready_by_rcon(identity=identity, boot_seq=boot_seq)
                        elif not returning and getattr(tab, "_monitor_identity", None) is None:
                            tab.confirm_ready_by_rcon()  # UI only; no return proof
                    kl = "sonda_odp" if err is None else "sonda_brak"
                    self.log(self.tr(kl, tab=tab.name))
                self.post_ui(apply_result)
            try:
                host = getattr(self, "plugin_host", None)
                plugin = host.get("rcon_admin") if host else None
                if plugin is None:
                    raise RuntimeError(t("brak wymaganego pluginu RCON", "required RCON plugin is missing"))
                plugin.enqueue(tab, "listplayers", _cb, owner="monitor")
            except Exception as e:
                self.log(self.tr("sonda_blad", tab=tab.name, e=str(e)))

    def _pad4_start(self, tab, identity=None):
            """3.71: slad crasha w logu a proces moze zywc - start okna 90 s."""
            if not hasattr(self, "_pad4"):
                self._monitor_init()
            if tab.name not in self._pad4:
                self._pad4[tab.name] = {"t0": time.time(), "identity": identity}
                self.post_ui(lambda: self.log(self.tr("pad4_start", tab=tab.name)))

    def _samorestart_zlicz(self, tab):
            """3.71: GOTOWY->STARTING bez czlowieka = samorestart serwera."""
            if not hasattr(self, "_samorestarty"):
                self._monitor_init()
            n = self._samorestarty.get(tab.name, 0) + 1
            self._samorestarty[tab.name] = n
            self.post_ui(lambda: self.log(self.tr("samorestart", tab=tab.name, n=n)))

    def _dziennik_modow(self):
            """3.71: zapis stanu modow do dziennika (rotacja 15x10 KB)."""
            linie = ["=== %s ===" % time.strftime("%Y-%m-%d %H:%M:%S")]
            for name in sorted(self.tabs):
                tab = self.tabs[name]
                if not tab.var_map_on.get():
                    continue
                try:
                    md = self._mods_dir_for_tab(tab)
                    ids = list(self._installed_file_ids(md))
                    roz = 0
                    missing_sizes = []
                    for mid, fid in ids:
                        mod_path = os.path.join(md, "%s_%s" % (mid, fid))
                        try:
                            roz += os.path.getsize(mod_path)
                        except OSError as exc:
                            missing_sizes.append("%s: %s" % (os.path.basename(mod_path), exc))
                    if missing_sizes:
                        self.log_warn(t("[DZIENNIK MODÓW] %s: nie odczytano rozmiaru: %s",
                                        "[MOD JOURNAL] %s: size not read: %s")
                                      % (name, "; ".join(missing_sizes)))
                    linie.append(t("  %s: %d modow, %d B", "  %s: %d mods, %d B") % (name, len(ids), roz))
                except Exception:
                    linie.append(t("  %s: brak danych", "  %s: no data") % name)
            path = dziennik_dopisz(self.knowledge_dir, linie)
            if path:
                self.log(self.tr("dziennik_ok", path=os.path.basename(path)))
            else:
                self.log(self.tr("dziennik_blad"))
