# -*- coding: utf-8 -*-
"""Shared-delete-safe ASA log tail and status recognizer."""
import hashlib
import os
import re
import threading
import time

# Blizny (nie „upraszczać”): skan 2 MB ogona logu od tyłu — logi bywają duże;
# 15 s łaski — manager kasuje/rotuje log przy restarcie.
# V3.80 świadomie USUNĘŁO dawną heurystykę BIG_LOG_BYTES („duży log bez
# markera = GOTOWY”): mapa bez markera zostaje UNKNOWN, a GOTOWY potwierdza
# dopiero odpowiedź RCON (sonda). Stała była martwa — V3.81 ją usuwa.
INITIAL_SCAN_BYTES = 2 * 1024 * 1024
ROTATION_GRACE_S = 15.0
LOG_PATTERNS = {
    "start": re.compile(r"Log file open"),
    "mod_update": re.compile(r"LogCFCore:.*(?:Updating|Installing|Request to Install|Starting download|requires upgrade/downgrade)", re.I),
    "loading_mods": re.compile(r"UShooterEngine::LoadGameMods"),
    "engine_up": re.compile(r"has successfully started!"),
    "ready": re.compile(r"Server has completed startup and is now advertising", re.I),
    "fatal": re.compile(r"Fatal error|Unhandled Exception|ensure condition failed", re.I),
}
_debug_logger = lambda message: None

def status_after_unclassified_activity(current_status):
    """A plain log line carries no lifecycle evidence; preserve current status."""
    return current_status

def set_debug_logger(logger):
    global _debug_logger
    _debug_logger = logger or (lambda message: None)

# injected to avoid an import cycle and keep parser independently testable
_event_parser = lambda line: None

def set_event_parser(parser):
    global _event_parser
    _event_parser = parser or (lambda line: None)

def open_log_shared(path, binary=False):
    mode = "rb" if binary else "r"
    options = {} if binary else {"encoding": "utf-8", "errors": "replace"}
    if os.name != "nt":
        try:
            return open(path, mode, **options)
        except Exception:
            return None
    h = None
    try:
        import ctypes
        from ctypes import wintypes
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x1
        FILE_SHARE_WRITE = 0x2
        FILE_SHARE_DELETE = 0x4
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        INVALID_HANDLE = wintypes.HANDLE(-1).value
        k32 = ctypes.windll.kernel32
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD,
                                    wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.DWORD, wintypes.DWORD,
                                    wintypes.HANDLE)
        h = k32.CreateFileW(path, GENERIC_READ,
                            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                            None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if not h or h == INVALID_HANDLE or h == -1 or h == 0xFFFFFFFFFFFFFFFF:
            return open(path, mode, **options)
        import msvcrt
        fd = msvcrt.open_osfhandle(int(h), os.O_RDONLY | (os.O_BINARY if binary else 0))
        return os.fdopen(fd, mode, **options)
    except Exception as e:
        _debug_logger(f"open_log_shared fail: {e}")
        if h and h != -1 and h != 0xFFFFFFFFFFFFFFFF:
            try:
                ctypes.windll.kernel32.CloseHandle(h)
            except Exception:
                pass
        try:
            return open(path, mode, **options)
        except Exception:
            return None

def mods_dir_candidates(log_dir):
    """3.54: kandydaci na folder modow wg PRAWDZIWEGO layoutu ASA.
    Serwer dedykowany ASA trzyma mody w ShooterGame/Binaries/Win64/
    ShooterGame/Mods/83374 (potwierdzone guide'em Steam i listingami
    adminow) - wczesniej program szukal tylko w ShooterGame/Mods, przez
    co u realnych adminow widzial 'brak folderu' majac 9 modow."""
    if not log_dir or not os.path.isdir(log_dir):
        return []
    norm = os.path.normpath(log_dir)
    parts = norm.split(os.sep)
    for i in range(len(parts) - 1, 1, -1):
        if parts[i].lower() == "logs" and parts[i - 1].lower() == "saved":
            base = os.sep.join(parts[:i - 1])  # = .../ShooterGame
            return [
                os.path.join(base, "Binaries", "Win64", "ShooterGame",
                             "Mods", "83374"),              # realny ASA
                os.path.join(base, "Mods", "83374"),        # uproszczony
                os.path.join(base, "Content", "Mods", "83374"),  # styl ASE
                os.path.join(os.path.dirname(base), "Content", "Mods",
                             "83374"),                      # wariant B
            ]
    return []

class LogTail(threading.Thread):
    def __init__(self, tab, path, callback):
        super().__init__(daemon=True)
        self.tab = tab
        self.folder = path
        self.callback = callback
        self._stop = threading.Event()
        self._fh = None
        self._last_crash_check = 0.0
        self._last_crash = self._crash_signature()
        self._status = "unknown"
        self._last_size = 0
        self._last_line = ""
        self._grace_until = 0.0
        self._last_err = None
        self._last_err_t = 0.0
        self._crash_archived = False

    def stop(self):
        self._stop.set()

    def _log_file(self):
        return os.path.join(self.folder, "ShooterGame.log")

    def _open_latest(self):
        p = self._log_file()
        if not os.path.isfile(p):
            return None
        fh = open_log_shared(p)
        if fh is None:
            return None
        size = 0
        try:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - INITIAL_SCAN_BYTES))
            stat = os.fstat(fh.fileno())
            self._source_key = (stat.st_dev, stat.st_ino, getattr(stat, "st_birthtime_ns", 0))
            try:
                self.tab._on_server_event({"type": "log_source", "source": self._source_key})
            except AttributeError:
                pass
            # Adaptacja do serwera, który już stoi: odtwórz z ogona nie tylko
            # status, lecz także rzeczywiście raportowane pary mod/file ID.
            # Samo śledzenie od EOF gubiło wersje procesu uruchomionego przed
            # Refresherem.
            lines = []
            while True:
                line = fh.readline()
                if not line:
                    break
                lines.append(line)
                self._ready_marker(line, fh.tell())
                event = _event_parser(line)
                if event:
                    try:
                        self.tab._on_server_event(event)
                    except Exception:
                        pass
            self._infer_initial_state("".join(lines))
        except Exception:
            pass
        try:
            fh.seek(0, os.SEEK_END)
            self._last_size = fh.tell()
            return fh
        except Exception:
            try:
                fh.close()
            except Exception:
                pass
            return None

    def _infer_initial_state(self, text):
        status = "unknown"
        last_line = ""
        for line in reversed(text.splitlines()):
            low = line.lower()
            if "fatal error" in low or "unhandled exception" in low:
                status = "crash"
                last_line = line[-160:]
                break
            if LOG_PATTERNS["ready"].search(line):
                status = "ready"
                last_line = line[-160:]
                break
            if LOG_PATTERNS["engine_up"].search(line):
                status = "engine"
                last_line = line[-160:]
                break
            if LOG_PATTERNS["loading_mods"].search(line):
                status = "loading_mods"
                last_line = line[-160:]
                break
            if LOG_PATTERNS["mod_update"].search(line):
                status = "loading_mods"
                last_line = line[-160:]
                break
            if LOG_PATTERNS["start"].search(line):
                status = "starting"
                last_line = line[-160:]
                break
        if status == "unknown":
            # Rozmiar pliku nie jest dowodem gotowości. Duży stary log bez
            # markera READY pozostaje UNKNOWN zamiast fałszywego GOTOWY.
            status = "unknown"
            nonempty = [l for l in text.splitlines() if l.strip()]
            if nonempty:
                last_line = nonempty[-1][-160:]
        self._status = status
        self._emit(status, last_line)

    def _newest_crashstack(self):
        try:
            files = [os.path.join(self.folder, f)
                     for f in os.listdir(self.folder)
                     if f.endswith(".crashstack")]
            if not files:
                return None
            return max(files, key=os.path.getmtime)
        except Exception:
            return None

    def _crash_signature(self):
        path = self._newest_crashstack()
        if path:
            try:
                stat = os.stat(path)
                return (path, stat.st_mtime_ns, stat.st_size)
            except OSError:
                pass
        return None

    def _poll_crashstack(self, now):
        current = self._crash_signature()
        if current and current != self._last_crash:
            self._last_crash = current
            if now - current[1] / 1e9 < 300:
                self._crash_archived = False
                self._status = "crash"
                self._last_line = self.tab.app.tr("crash_detected")
                self._emit("crash", self._last_line)

    def _file_changed(self):
        try:
            st_path = os.stat(self._log_file())
            st_open = os.fstat(self._fh.fileno())
        except Exception:
            return True
        same_ino = False
        try:
            if st_path.st_ino and st_open.st_ino:
                same_ino = (st_path.st_dev, st_path.st_ino) == \
                           (st_open.st_dev, st_open.st_ino)
            else:
                # 3.71 FIX (audyt1): FAT/exFAT nie daje st_ino (0) — wczesniej
                # same_ino zostawalo False -> przeladowanie 2 MB co 0,5 s
                same_ino = st_path.st_size >= self._last_size
        except Exception:
            pass
        if not same_ino:
            return True
        if st_path.st_size < self._last_size:
            return True
        return False

    def _log_throttled(self, e):
        now = time.time()
        try:
            msg = f"[{self.tab.name}] {self.tab.app.tr('log_tail_err')}{e}"
        except Exception:
            msg = f"{e}"
        if msg != self._last_err or (now - self._last_err_t) > 30:
            self._last_err = msg
            self._last_err_t = now
            try:
                self.tab.app.log(msg)
            except Exception:
                pass

    def run(self):
        while not self._stop.is_set():
            try:
                if self._fh is None:
                    self._fh = self._open_latest()
                    if self._fh is None:
                        if self._grace_until and time.time() < self._grace_until:
                            pass
                        else:
                            self._emit("offline")
                    else:
                        self._grace_until = 0.0
                else:
                    if self._file_changed():
                        try:
                            self._fh.close()
                        except Exception:
                            pass
                        self._fh = None
                        self._grace_until = time.time() + ROTATION_GRACE_S
                        time.sleep(1.0)
                        continue

                    had_lines = False
                    line = self._fh.readline()
                    while line:
                        self._handle_line(line.rstrip("\n"))
                        had_lines = True
                        line = self._fh.readline()
                    try:
                        self._last_size = self._fh.tell()
                    except Exception:
                        pass
                    if had_lines:
                        # Ordinary activity is not evidence of a boot. If READY fell
                        # outside the initial scan window, remain UNKNOWN until an
                        # actual marker or an independent successful RCON probe proves
                        # the server is operational.
                        self._emit(status_after_unclassified_activity(self._status),
                                   self._last_line)

                    now = time.time()
                    if now - self._last_crash_check > 10:
                        self._last_crash_check = now
                        try:
                            self._poll_crashstack(now)
                        except Exception:
                            pass
            except Exception as e:
                _debug_logger(f"LogTail error: {e}")
                self._log_throttled(e)
            time.sleep(0.5)

    def _handle_line(self, line):
        if not line:
            return
        if self._fh is not None:
            # End offset is stable across initial scan and incremental reads.
            self._ready_marker(line, None)
        event = _event_parser(line)
        if event:
            try:
                self.tab._on_server_event(event)
            except Exception:
                pass
        self._last_line = line[-160:]
        low = line.lower()
        if "fatal error" in low or "unhandled exception" in low:
            self._status = "crash"
            return
        if LOG_PATTERNS["ready"].search(line):
            self._status = "ready"
            return
        if LOG_PATTERNS["engine_up"].search(line):
            self._status = "engine"
            return
        if LOG_PATTERNS["loading_mods"].search(line):
            self._status = "loading_mods"
            return
        if LOG_PATTERNS["mod_update"].search(line):
            self._status = "loading_mods"
            return
        if LOG_PATTERNS["start"].search(line):
            self._status = "starting"
            return

    def _ready_marker(self, line, offset):
        if not LOG_PATTERNS["ready"].search(line):
            return
        # A file identity plus the byte position identifies the *actual* READY
        # marker. Replaying the same log after toggling monitoring is not proof
        # of another boot. Ordinary activity carrying status=ready is not either.
        end = self._fh.tell() if offset is None else offset
        key = repr((self._source_key, end, line.rstrip("\r\n")))
        proof = hashlib.sha256(key.encode("utf-8")).hexdigest()
        try:
            self.tab._on_server_event({"type": "ready_marker", "proof": proof,
                                       "observed_at": time.time()})
        except AttributeError:
            pass

    def _emit(self, status, line=""):
        # W wątku czytającym, przed kolejką UI i przed 90-sekundową klasyfikacją.
        if status == "crash":
            # Kopia dużego dumpa może trwać dłużej niż zmiana procesu przez managera.
            self.tab._crash_trace_identity = getattr(self.tab, "_monitor_identity", None)
        if status == "starting":
            self._crash_archived = False
        if status == "crash" and not getattr(self, "_crash_archived", False):
            self._crash_archived = True
            app = getattr(self.tab, "app", None)
            root = getattr(app, "knowledge_dir", None)
            if root:
                try:
                    from .archiwum_padow import zapisz_dowody
                    result = zapisz_dowody(root, self.tab.name, self.folder, "crash_trace",
                                          self.tab._crash_trace_identity,
                                          limit_bytes=app.__dict__.get("pad_archive_limit_mib", 2048) * 1024 * 1024)
                    app.post_ui(lambda r=result: (app.log_warn if r.get("warning") else app.log)(r["message"]))
                except Exception as exc:
                    _debug_logger("crash evidence: %s" % exc)
        try:
            self.callback(self.tab, status, line)
        except Exception:
            pass
