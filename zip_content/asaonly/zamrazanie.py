# -*- coding: utf-8 -*-
"""Zamrażanie managera serwerów na czas podmiany plików serwera (V3.85, V3.86).

Po co: ASADedicatedManager sam podnosi serwer ok. 30 s po zniknięciu procesu
(w jego logu: trzy sprawdzenia co 10 s, potem „automatic restart”). Pliki
serwera wolno podmieniać tylko przy wyłączonym serwerze. Dlatego na ten czas
proces managera jest wstrzymany (NtSuspendProcess z ntdll — wstrzymanie całego
procesu, jak w Process Explorer; psutil #1379), a potem wznowiony: wtedy
manager sam podnosi już zaktualizowany serwer, dokładnie jak po każdym DoExit.
Refresher nie uruchamia serwerów sam. V3.86: pliki przychodzą z cache
refreshera (asaonly.synchronizacja), a nie z SteamCMD uruchomionego na mapie.

Bezpieczniki:
  * dzierżawa (plik JSON) opisuje, co jest zamrożone — przy starcie refresher
    wznawia to, co zostało po awarii,
  * osobny strażnik (python -m asaonly.zamrazanie <dzierżawa>) wznawia managera,
    jeśli refresher zniknie; czeka przy tym, aż skończy się SteamCMD,
  * V3.86: jeśli refresher zniknął w trakcie kopiowania plików, strażnik (albo
    następny start refreshera) najpierw cofa kopiowanie z dziennika — manager
    podnosi wtedy serwer na starym, kompletnym buildzie, nie na mieszance,
  * żywy właściciel zawsze blokuje recovery, również po przekroczeniu limitu.

Funkcje systemowe są w klasie ApiWindows; testy podstawiają atrapę.
"""
import json
import os
import subprocess
import sys
import time

from .jezyk import t

LIMIT_S = 150 * 60                # próg ostrzeżenia; żywy worker nadal blokuje recovery


class ApiWindows(object):
    """Wywołania Win32/ntdll przez ctypes. Poza Windows każda metoda zgłasza błąd."""

    PROCESS_TERMINATE = 0x0001
    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    def __init__(self):
        if os.name != "nt":
            self._k32 = self._nt = None
            return
        import ctypes
        from ctypes import wintypes
        self._c = ctypes
        self._w = wintypes
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._nt = ctypes.WinDLL("ntdll")
        k = self._k32
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        k.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        self._nt.NtSuspendProcess.argtypes = (wintypes.HANDLE,)
        self._nt.NtResumeProcess.argtypes = (wintypes.HANDLE,)
        self._nt.NtSuspendProcess.restype = ctypes.c_long
        self._nt.NtResumeProcess.restype = ctypes.c_long

    def _wymagaj(self):
        if self._k32 is None:
            raise OSError(t("tylko Windows", "Windows only"))

    def _otworz(self, pid, dostep):
        self._wymagaj()
        uchwyt = self._k32.OpenProcess(dostep, False, int(pid))
        if not uchwyt:
            raise OSError(self._c.get_last_error(), "OpenProcess(%s)" % pid)
        return uchwyt

    def procesy(self, nazwa_exe):
        """[pid] procesów o danej nazwie pliku (bez względu na wielkość liter)."""
        self._wymagaj()
        c, w = self._c, self._w

        class PROCESSENTRY32W(c.Structure):
            _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD),
                        ("th32ProcessID", w.DWORD), ("th32DefaultHeapID", c.c_size_t),
                        ("th32ModuleID", w.DWORD), ("cntThreads", w.DWORD),
                        ("th32ParentProcessID", w.DWORD), ("pcPriClassBase", c.c_long),
                        ("dwFlags", w.DWORD), ("szExeFile", c.c_wchar * 260)]
        k32 = self._k32
        k32.CreateToolhelp32Snapshot.restype = w.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = (w.DWORD, w.DWORD)
        k32.Process32FirstW.argtypes = (w.HANDLE, c.POINTER(PROCESSENTRY32W))
        k32.Process32NextW.argtypes = (w.HANDLE, c.POINTER(PROCESSENTRY32W))
        migawka = k32.CreateToolhelp32Snapshot(0x00000002, 0)     # TH32CS_SNAPPROCESS
        if not migawka or migawka == w.HANDLE(-1).value:
            raise OSError(c.get_last_error(), "CreateToolhelp32Snapshot")
        wynik = []
        try:
            wpis = PROCESSENTRY32W()
            wpis.dwSize = c.sizeof(PROCESSENTRY32W)
            dalej = k32.Process32FirstW(migawka, c.byref(wpis))
            szukana = str(nazwa_exe).lower()
            while dalej:
                if wpis.szExeFile.lower() == szukana:
                    wynik.append(int(wpis.th32ProcessID))
                dalej = k32.Process32NextW(migawka, c.byref(wpis))
        finally:
            k32.CloseHandle(migawka)
        return wynik

    def czas_startu(self, pid):
        """Czas utworzenia procesu (jednostki 100 ns) — odróżnia PID użyty ponownie."""
        c, w = self._c, self._w
        uchwyt = self._otworz(pid, self.PROCESS_QUERY_LIMITED_INFORMATION)
        try:
            czasy = [w.FILETIME() for _ in range(4)]
            if not self._k32.GetProcessTimes(uchwyt, *[c.byref(x) for x in czasy]):
                raise OSError(c.get_last_error(), "GetProcessTimes")
            return (czasy[0].dwHighDateTime << 32) | czasy[0].dwLowDateTime
        finally:
            self._k32.CloseHandle(uchwyt)

    def zyje(self, pid, start=None):
        c, w = self._c, self._w
        try:
            uchwyt = self._otworz(pid, self.PROCESS_QUERY_LIMITED_INFORMATION)
        except OSError as exc:
            if exc.errno == 87:          # ERROR_INVALID_PARAMETER: PID nie istnieje
                return False
            raise                       # odmowa dostępu nie dowodzi śmierci procesu
        try:
            kod = w.DWORD()
            if not self._k32.GetExitCodeProcess(uchwyt, c.byref(kod)):
                raise OSError(c.get_last_error(), "GetExitCodeProcess")
            if kod.value != self.STILL_ACTIVE:
                return False
        finally:
            self._k32.CloseHandle(uchwyt)
        if start is not None:
            return self.czas_startu(pid) == int(start)
        return True

    def sciezka_exe(self, pid):
        c, w = self._c, self._w
        uchwyt = self._otworz(pid, self.PROCESS_QUERY_LIMITED_INFORMATION)
        try:
            bufor = c.create_unicode_buffer(32768)
            rozmiar = w.DWORD(32768)
            if not self._k32.QueryFullProcessImageNameW(uchwyt, 0, bufor, c.byref(rozmiar)):
                raise OSError(c.get_last_error(), "QueryFullProcessImageNameW")
            return bufor.value
        finally:
            self._k32.CloseHandle(uchwyt)

    def _nt_wywolaj(self, pid, funkcja, nazwa, start=None):
        dostep = self.PROCESS_SUSPEND_RESUME | (self.PROCESS_QUERY_LIMITED_INFORMATION if start is not None else 0)
        uchwyt = self._otworz(pid, dostep)
        try:
            if start is not None:
                czasy = [self._w.FILETIME() for _ in range(4)]
                if not self._k32.GetProcessTimes(uchwyt, *[self._c.byref(x) for x in czasy]):
                    raise OSError(self._c.get_last_error(), "GetProcessTimes")
                if (czasy[0].dwHighDateTime << 32) | czasy[0].dwLowDateTime != int(start):
                    raise OSError("process identity changed")
            status = funkcja(uchwyt)
            if status != 0:
                raise OSError("%s: NTSTATUS 0x%08X" % (nazwa, status & 0xFFFFFFFF))
        finally:
            self._k32.CloseHandle(uchwyt)

    def dostep_wstrzymania(self, pid):
        """Czy wolno nam wstrzymać ten proces (bez wstrzymywania)."""
        self._wymagaj()
        self._k32.CloseHandle(self._otworz(pid, self.PROCESS_SUSPEND_RESUME))

    def zamroz(self, pid):
        self._wymagaj()
        self._nt_wywolaj(pid, self._nt.NtSuspendProcess, "NtSuspendProcess")

    def odmroz(self, pid):
        self._wymagaj()
        self._nt_wywolaj(pid, self._nt.NtResumeProcess, "NtResumeProcess")

    def zamroz_wpis(self, wpis):
        self._wymagaj()
        self._nt_wywolaj(wpis["pid"], self._nt.NtSuspendProcess, "NtSuspendProcess", wpis["start"])

    def odmroz_wpis(self, wpis):
        self._wymagaj()
        self._nt_wywolaj(wpis["pid"], self._nt.NtResumeProcess, "NtResumeProcess", wpis["start"])

    def zakoncz(self, pid):
        self._wymagaj()
        uchwyt = self._otworz(pid, self.PROCESS_TERMINATE)
        try:
            self._k32.TerminateProcess(uchwyt, 1)
        finally:
            self._k32.CloseHandle(uchwyt)

    def uruchom_straznika(self, sciezka_dzierzawy):
        """Osobny proces pilnujący dzierżawy (przeżywa awarię refreshera)."""
        katalog = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        flagi = 0x00000008 | 0x00000200        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        proces = subprocess.Popen([sys.executable, "-m", "asaonly.zamrazanie", sciezka_dzierzawy],
                         cwd=katalog, creationflags=flagi, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        lease_id = czytaj_dzierzawe(sciezka_dzierzawy)["lease_id"]
        koniec = time.monotonic() + 20.0
        while time.monotonic() < koniec:
            if proces.poll() is not None:
                raise OSError("guardian exited before acknowledging the lease")
            try:
                with open(sciezka_dzierzawy + ".ready", encoding="utf-8") as fh:
                    if json.load(fh).get("lease_id") == lease_id:
                        return proces
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        raise OSError("guardian did not acknowledge the lease")


# ---------------------------------------------------------------------------
# Dzierżawa
# ---------------------------------------------------------------------------
from contextlib import contextmanager
from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class WynikOdzyskiwania:
    stan: str
    wznowione: tuple = ()
    bledy: tuple = ()
    safe_to_resume: bool = False

    @property
    def zablokowane(self):
        return self.stan not in ("NONE", "RECOVERED")


@contextmanager
def blokada_dzierzawy(sciezka):
    """Blokada pliku zwalniana przez system także po śmierci procesu."""
    os.makedirs(os.path.dirname(os.path.abspath(sciezka)), exist_ok=True)
    with open(sciezka + ".lock", "a+b") as fh:
        if os.fstat(fh.fileno()).st_size == 0:
            fh.write(b"\0")
            fh.flush()
        fh.seek(0)
        if os.name == "nt":
            import msvcrt
            _ponow_io(lambda: msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1))
        else:
            import fcntl
            _ponow_io(lambda: fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB))
        try:
            yield
        finally:
            fh.seek(0)
            if os.name == "nt":
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _ponow_io(fn):
    """Krótkie ponowienia odmowy dostępu/blokady; pełny dysk nie wymaga czekania."""
    for proba in range(6):
        try:
            return fn()
        except OSError as exc:
            if proba == 5 or (exc.errno not in (13, 11) and getattr(exc, "winerror", None) not in (5, 32, 33)):
                raise
            time.sleep(0.15)


def zapisz_dzierzawe(sciezka, dane):
    katalog = os.path.dirname(sciezka)
    if katalog:
        os.makedirs(katalog, exist_ok=True)
    tymczasowa = sciezka + ".tmp"
    def zapisz():
        with open(tymczasowa, "w", encoding="utf-8") as fh:
            json.dump(dane, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tymczasowa, sciezka)
    _ponow_io(zapisz)


def czytaj_dzierzawe(sciezka):
    """None tylko gdy pliku nie ma. Uszkodzenie/odmowa odczytu to błąd."""
    try:
        def odczyt():
            with open(sciezka, "r", encoding="utf-8") as fh:
                return json.load(fh)
        dane = _ponow_io(odczyt)
    except FileNotFoundError:
        return None
    if not isinstance(dane, dict) or not isinstance(dane.get("manager"), list):
        raise ValueError("invalid manager lease")
    if dane.get("schema") not in (None, 2):
        raise ValueError("unsupported lease schema")
    if dane.get("faza") not in (None, "przygotowany", "zamrozony", "kopiowanie", "bezpieczne"):
        raise ValueError("invalid lease phase")
    if dane.get("schema") == 2 and (not dane.get("refresher") or not dane.get("lease_id")):
        raise ValueError("missing lease owner")
    for wpis in dane["manager"]:
        if not isinstance(wpis, dict) or not isinstance(wpis.get("pid"), int) or wpis["pid"] <= 0:
            raise ValueError("invalid manager identity")
        if not isinstance(wpis.get("start"), int):
            raise ValueError("missing manager creation time")
        if wpis.get("stan") not in (None, "przygotowany", "zamrazanie", "zamrozony", "zamrozenie_niepewne",
                                    "wznawianie", "wznowiony"):
            raise ValueError("invalid manager operation state")
    for key in ("refresher", "steamcmd"):
        ref = dane.get(key)
        if ref is not None and (not isinstance(ref, dict) or
                                not isinstance(ref.get("pid"), int) or ref["pid"] <= 0 or
                                not isinstance(ref.get("start"), int)):
            raise ValueError("invalid %s identity" % key)
    return dane


def _alarm(sciezka, bledy):
    try:
        zapisz_dzierzawe(sciezka + ".alarm.json",
                        {"czas": time.time(), "bledy": list(bledy)})
    except OSError:
        pass


def _zablokowane(sciezka, powod, stan="BLOCKED", wznowione=()):
    _alarm(sciezka, [str(powod)])
    return WynikOdzyskiwania(stan, tuple(wznowione), (str(powod),), False)


def cofnij_kopiowanie(dzierzawa):
    """Zawsze jawny wynik. Brak/uszkodzenie oczekiwanego journala nie jest SAFE."""
    if dzierzawa.get("faza") == "bezpieczne":
        return "zatwierdzone", []
    sciezka = dzierzawa.get("kopia")
    if not sciezka:
        if dzierzawa.get("faza") == "kopiowanie":
            return "bledy", ["missing copy checkpoint"]
        return "brak", []
    try:
        from .synchronizacja import przywroc_z_dziennika
        stan, bledy = przywroc_z_dziennika(sciezka, zachowaj_dziennik=True)
        if stan == "brak":
            return "bledy", ["expected copy journal is missing"]
        return stan, bledy
    except Exception as exc:
        return "bledy", ["rollback: %s" % exc]


def decyzja_straznika(dzierzawa, teraz, zyje):
    """Żywy albo niepewny właściciel zawsze chroni workera przed recovery."""
    try:
        ref = dzierzawa.get("refresher") or {}
        if ref.get("pid") and zyje(ref["pid"], ref.get("start")):
            return "czekaj"
        steam = dzierzawa.get("steamcmd") or {}
        if steam.get("pid") and zyje(steam["pid"], steam.get("start")):
            return "czekaj"
    except (OSError, TypeError, ValueError):
        return "niepewny"
    return "odmroz"


def _wznow_bezpieczne(sciezka, dane, api):
    """Wywoływane pod blokadą. Dziennik potwierdza każdy zakończony PID."""
    wznowione, bledy = [], []
    for wpis in dane["manager"]:
        if wpis.get("stan") == "wznowiony":
            continue
        if wpis.get("stan") == "przygotowany":
            wpis["stan"] = "wznowiony"  # strażnik wystartował, ale freeze jeszcze nie
            zapisz_dzierzawe(sciezka, dane)
            continue
        # Przy wyłącznej kontroli Refreshera dodatkowe resume przy liczniku 0
        # niczego nie zmienia (próba Windows w testach). Spójność plików musi
        # być potwierdzona PRZED wejściem tutaj, także dla stanów niejednoznacznych.
        try:
            if not api.zyje(wpis["pid"], wpis["start"]):
                wpis["stan"] = "wznowiony"
                zapisz_dzierzawe(sciezka, dane)
                continue
            wpis["stan"] = "wznawianie"
            zapisz_dzierzawe(sciezka, dane)
            try:
                if hasattr(api, "odmroz_wpis"):
                    api.odmroz_wpis(wpis)
                else:
                    api.odmroz(wpis["pid"])
            except OSError as exc:
                wpis["stan"] = "zamrozony"
                zapisz_dzierzawe(sciezka, dane)
                bledy.append("%s: %s" % (wpis["pid"], exc))
                continue
            wznowione.append(wpis["pid"])
            wpis["stan"] = "wznowiony"
            zapisz_dzierzawe(sciezka, dane)
        except (OSError, ValueError) as exc:
            bledy.append("%s: %s" % (wpis["pid"], exc))
            break
    if bledy:
        return _zablokowane(sciezka, "; ".join(bledy), wznowione=wznowione)
    # Faza SAFE pozostaje na dysku aż do końca sprzątania; restart nie cofnie
    # zatwierdzonych plików ani nie powtórzy potwierdzonego NtResumeProcess.
    journal = dane.get("kopia")
    if journal:
        try:
            from .synchronizacja import _czytaj, przywroc_z_dziennika
            stan = _czytaj(journal)
            if stan is not None and stan.get("stan") in ("gotowe", "wycofane"):
                _, bledy = przywroc_z_dziennika(journal)
                if bledy:
                    return _zablokowane(sciezka, "; ".join(bledy), wznowione=wznowione)
            elif stan is not None:
                return _zablokowane(sciezka, "unexpected unfinished journal after SAFE; no rollback performed",
                                   wznowione=wznowione)
        except Exception as exc:
            return _zablokowane(sciezka, str(exc), wznowione=wznowione)
    try:
        os.remove(sciezka)
    except FileNotFoundError:
        pass
    except OSError as exc:
        return _zablokowane(sciezka, str(exc), wznowione=wznowione)
    for suffix in (".ready", ".alarm.json"):
        try:
            os.remove(sciezka + suffix)
        except OSError:
            pass
    return WynikOdzyskiwania("RECOVERED", tuple(wznowione), (), True)


def _odzyskaj(sciezka, api, oczekiwany_id=None, wlasny_bezczynny_id=None):
    """Jedna próba recovery; blokada wyklucza konkurencję ze strażnikiem."""
    if not os.path.lexists(sciezka):
        return WynikOdzyskiwania("NONE", safe_to_resume=True)
    try:
        with blokada_dzierzawy(sciezka):
            dane = czytaj_dzierzawe(sciezka)
            if dane is None:
                return WynikOdzyskiwania("NONE", safe_to_resume=True)
            if oczekiwany_id is not None and dane.get("lease_id") != oczekiwany_id:
                return WynikOdzyskiwania("OWNER_ALIVE")
            decyzja = decyzja_straznika(dane, time.time(), api.zyje)
            wlasny = (wlasny_bezczynny_id is not None and
                      dane.get("lease_id") == wlasny_bezczynny_id and
                      (dane.get("refresher") or {}).get("pid") == os.getpid() and
                      api.zyje(os.getpid(), dane["refresher"]["start"]) and not dane.get("steamcmd"))
            if decyzja == "czekaj" and not wlasny:
                return WynikOdzyskiwania("OWNER_ALIVE")
            if decyzja == "niepewny":
                return _zablokowane(sciezka, "cannot establish that the owner has stopped")
            stan, bledy = cofnij_kopiowanie(dane)
            if stan == "bledy":
                return _zablokowane(sciezka, "; ".join(bledy))
            dane["faza"] = "bezpieczne"
            zapisz_dzierzawe(sciezka, dane)
            return _wznow_bezpieczne(sciezka, dane, api)
    except (OSError, ValueError, TypeError) as exc:
        return _zablokowane(sciezka, str(exc), "INVALID_OR_UNREADABLE")


class Zamrazarka:
    def __init__(self, sciezka_dzierzawy, nazwa_exe, api=None, straznik=True):
        self.sciezka = sciezka_dzierzawy
        self.nazwa_exe = str(nazwa_exe or "").strip()
        self.api = api if api is not None else ApiWindows()
        self.straznik = straznik
        self.zamrozone = []
        self._lease_id = None
        self.wynik_odzyskiwania = WynikOdzyskiwania("NONE", safe_to_resume=True)

    def aktywna(self):
        return bool(self.zamrozone) or os.path.lexists(self.sciezka)

    def wybierz_managera(self):
        """Ścieżka opcjonalna; niejednoznaczna nazwa nigdy nie zamraża kilku PID."""
        if not self.nazwa_exe:
            raise OSError("brak_nazwy")
        pidy = self.api.procesy(os.path.basename(self.nazwa_exe))
        if os.path.isabs(self.nazwa_exe):
            cel = os.path.normcase(os.path.realpath(self.nazwa_exe))
            pidy = [pid for pid in pidy if
                    os.path.normcase(os.path.realpath(self.api.sciezka_exe(pid))) == cel]
        if not pidy:
            raise OSError("brak_procesu")
        if len(pidy) != 1:
            raise OSError("niejednoznaczny_manager")
        return pidy

    def zamroz(self):
        try:
            with blokada_dzierzawy(self.sciezka):
                if self.zamrozone:
                    return False, "juz"
                if os.path.lexists(self.sciezka):
                    return False, "recovery"
                pidy = self.wybierz_managera()
                wpisy = []
                for pid in pidy:
                    self.api.dostep_wstrzymania(pid)
                    wpisy.append({"pid": pid, "start": self.api.czas_startu(pid), "stan": "przygotowany"})
                start = self.api.czas_startu(os.getpid())
                if start is None or any(w["start"] is None for w in wpisy):
                    return False, "dostep:missing creation time"
                self._lease_id = uuid.uuid4().hex
                dane = {"schema": 2, "lease_id": self._lease_id,
                        "refresher": {"pid": os.getpid(), "start": start},
                        "manager": wpisy, "steamcmd": None,
                        "faza": "przygotowany", "limit": time.time() + LIMIT_S}
                zapisz_dzierzawe(self.sciezka, dane)
                try:
                    if self.straznik:
                        self.api.uruchom_straznika(self.sciezka)
                except Exception as exc:
                    # Jeszcze nie dotknięto procesu managera.
                    os.remove(self.sciezka)
                    return False, "straznik:%s" % exc
                for wpis in wpisy:
                    wpis["stan"] = "zamrazanie"
                    zapisz_dzierzawe(self.sciezka, dane)
                    try:
                        if hasattr(self.api, "zamroz_wpis"):
                            self.api.zamroz_wpis(wpis)
                        else:
                            self.api.zamroz(wpis["pid"])
                    except OSError:
                        wpis["stan"] = "zamrozenie_niepewne"
                        zapisz_dzierzawe(self.sciezka, dane)
                        raise
                    self.zamrozone.append(dict(wpis))
                    wpis["stan"] = "zamrozony"
                    dane["faza"] = "zamrozony"
                    zapisz_dzierzawe(self.sciezka, dane)
                return True, ""
        except (OSError, ValueError) as exc:
            if os.path.lexists(self.sciezka):
                _alarm(self.sciezka, [str(exc)])
                # Zamroz() nie kopiuje plików. Po częściowym/błędnym suspend
                # własną dzierżawę można od razu bezpiecznie wznowić.
                if self._lease_id:
                    self.ponow_po_zakonczeniu_pracy()
            return False, str(exc)

    def _wlasna_dzierzawa(self):
        dane = czytaj_dzierzawe(self.sciezka)
        if dane is None or not self._lease_id or dane.get("lease_id") != self._lease_id:
            raise OSError("missing or foreign lease")
        return dane

    def ustaw_kopie(self, sciezka_dziennika):
        with blokada_dzierzawy(self.sciezka):
            dane = self._wlasna_dzierzawa()
            dane["kopia"] = str(sciezka_dziennika)
            dane["faza"] = "kopiowanie"
            zapisz_dzierzawe(self.sciezka, dane)
        return True

    def potwierdz_bezpieczne(self):
        """Wyłącznie worker, gdy SyncResult potwierdził spójny stan plików."""
        with blokada_dzierzawy(self.sciezka):
            dane = self._wlasna_dzierzawa()
            dane["faza"] = "bezpieczne"
            zapisz_dzierzawe(self.sciezka, dane)

    def odmroz(self):
        try:
            with blokada_dzierzawy(self.sciezka):
                if not os.path.lexists(self.sciezka) and not self.zamrozone:
                    return []
                dane = self._wlasna_dzierzawa()
                # Odmroz() nigdy nie uruchamia rollbacku obok żywego workera.
                if dane.get("faza") == "kopiowanie":
                    raise OSError("copy safety has not been confirmed; recovery required")
                dane["faza"] = "bezpieczne"
                zapisz_dzierzawe(self.sciezka, dane)
                wynik = _wznow_bezpieczne(self.sciezka, dane, self.api)
                self.wynik_odzyskiwania = wynik
                if not wynik.zablokowane:
                    self.zamrozone = []
                    self._lease_id = None
                return list(wynik.bledy)
        except (OSError, ValueError, TypeError) as exc:
            self.wynik_odzyskiwania = _zablokowane(self.sciezka, str(exc))
            return list(self.wynik_odzyskiwania.bledy)

    def odzyskaj_po_awarii(self):
        wynik = _odzyskaj(self.sciezka, self.api)
        self.wynik_odzyskiwania = wynik
        return wynik

    def ponow_po_zakonczeniu_pracy(self):
        """Wyłącznie gdy własny worker i timer już zakończyły operację."""
        wynik = _odzyskaj(self.sciezka, self.api, wlasny_bezczynny_id=self._lease_id)
        self.wynik_odzyskiwania = wynik
        if not wynik.zablokowane:
            self.zamrozone = []
            self._lease_id = None
        return wynik


def straznik(sciezka, api=None, krok_s=2.0, zegar=time.time, spij=time.sleep,
             limit_bledow=10, przerwa_bledow_s=30):
    api = api if api is not None else ApiWindows()
    lease_id, potwierdzony, bledy = None, False, 0
    while True:
        blad = False
        try:
            dane = czytaj_dzierzawe(sciezka)
            if dane is None:
                return "koniec"
            if not potwierdzony:
                lease_id = dane.get("lease_id")
                # Handshake bez blokady trzymanej przez rodzica przed suspend.
                zapisz_dzierzawe(sciezka + ".ready", {"lease_id": lease_id})
                potwierdzony = True
            if dane.get("lease_id") != lease_id:
                return "obca_dzierzawa"
            decyzja = decyzja_straznika(dane, zegar(), api.zyje)
            if decyzja == "odmroz":
                wynik = _odzyskaj(sciezka, api, lease_id)
                if wynik.stan in ("RECOVERED", "NONE"):
                    return "odmrozono"
                if wynik.stan != "OWNER_ALIVE":
                    blad = True
            elif decyzja == "niepewny":
                _alarm(sciezka, ["owner identity unavailable; no recovery performed"])
                blad = True
            elif dane.get("limit") and zegar() > float(dane["limit"]):
                _alarm(sciezka, ["deadline exceeded but owner/SteamCMD is alive; no recovery performed"])
        except (OSError, ValueError, TypeError) as exc:
            _alarm(sciezka, [str(exc)])
            blad = True
        bledy = bledy + 1 if blad else 0
        if bledy >= limit_bledow:
            return "zablokowane"
        spij((przerwa_bledow_s if potwierdzony else krok_s) if blad else krok_s)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        straznik(sys.argv[1])
