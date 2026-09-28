# -*- coding: utf-8 -*-
"""Aktualizacja serwera ASA przez własny cache refreshera (V3.86; V3.85 = SteamCMD na mapie).

Dlaczego V3.85 restartowała serwery bez aktualizacji (25.09.2026, sprawdzone w logach):
SteamCMD refreshera uruchamiany wprost na katalogu mapy potrzebował manifestu
buildu leżącego na mapie. Mapy instalował SteamCMD managera, więc refresher
tego manifestu nie miał, Steam odmawiał go anonimowo („Access Denied”), a plugin
— po DoExit — wznawiał managera, który podnosił serwer na starym buildzie.
Trzy próby na mapę = trzy restarty bez aktualizacji.

Jak jest teraz (ta sama zasada co w managerze, który to robi poprawnie):
  1. co minutę api.steamcmd.net podaje najnowszy build (zapasowo, gdy API nie
     odpowiada — SteamCMD co 5 min; raz na godzinę SteamCMD kontrolnie),
  2. nowy build od razu trafia do CACHE refreshera (osobny folder obok
     serwerów) — zawsze tym samym SteamCMD, więc manifest jest zawsze pod ręką.
     Serwery w tym czasie działają. Błąd pobierania = żadnego restartu,
     w dzienniku prawdziwy powód z content_log.txt SteamCMD,
  3. gdy cache jest gotowy i sprawdzony, plugin planuje (jeszcze przy
     działającym serwerze), które pliki mapy się różnią,
  4. mapa idzie zwykłą kolejką restartu (ogłoszenia z jej harmonogramu, pusta
     = od razu, jeden start naraz); tuż przed DoExit manager zostaje
     wstrzymany, po wyłączeniu serwera kopiowane są TYLKO różniące się pliki
     (z kopią zapasową; przy błędzie wszystko wraca), appmanifest na końcu,
     potem manager jest wznawiany i sam podnosi zaktualizowany serwer,
  5. mapa, której serwer nie działa (OFFLINE/CRASH albo długo nie GOTOWA) —
     to samo bez kolejki i bez DoExit,
  6. jeśli w managerze włączone jest „Enable automatic update checking”,
     plugin nic nie aktualizuje i mówi dlaczego — dwa updatery się pogryzą.

Refresher nie uruchamia serwerów sam. Logika czysta: asaonly/steam_serwer.py,
kopiowanie z wycofaniem: asaonly/synchronizacja.py, wstrzymanie managera
i strażnik: asaonly/zamrazanie.py.
"""
import os
import json
import shutil
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
import zipfile
from tkinter import messagebox, ttk

from asaonly import siec
from asaonly import steam_serwer as S
from asaonly import synchronizacja as SYNC
from asaonly.jezyk import t
from asaonly.zamrazanie import Zamrazarka, LIMIT_S

URL_STEAMCMD = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
EXE_SERWERA = "ArkAscendedServer.exe"
MANAGER_DOMYSLNY = "ASADedicatedManager.exe"
API_CO_S = 60                          # api.steamcmd.net: co ile sekund
API_MIN_S = 30
STEAMCMD_CO_MIN = 5                    # zapas, gdy API nie odpowiada
KONTROLA_STEAMCMD_S = 60 * 60          # gdy API działa: SteamCMD kontrolnie raz na godzinę
PIERWSZE_SPRAWDZENIE_S = 30
TIMEOUT_INFO_S = 300
TIMEOUT_API_S = 15
TIMEOUT_UPDATE_S = 2 * 60 * 60         # twardy limit SteamCMD (pierwsze pobranie ~12 GB)
CZEKAJ_NA_WYJSCIE_S = 300
ZAMROZENIE_BEZ_DOEXIT_S = 300
NIE_GOTOWA_S = 30 * 60                 # tak długo mapa nie GOTOWA = serwer uznany za niedziałający
STANY_BEZ_SERWERA = ("offline", "crash")
PLIK_DZIERZAWY = "zamrozenie_managera.json"
ZAPAS_MIEJSCA = 2 * 1024 ** 3          # ponad potrzebne bajty (cache i kopie tymczasowe)
PRZERWY_CACHE_S = (5 * 60, 15 * 60, 30 * 60)   # po nieudanym pobraniu do cache
# V3.86.1: „Missing configuration” = SteamCMD nie ma jeszcze informacji o aplikacji
# (26.09: pierwszy przebieg świeżo pobranego SteamCMD). Ponowienie od razu, w tym
# samym zadaniu — zamiast czekać 5 min jak przy innych błędach.
PONOWIENIA_BRAK_KONFIGURACJI = 2
PRZERWA_BRAK_KONFIGURACJI_S = 10
GB = 1024.0 ** 3
MB = 1024.0 ** 2


def _pliki_do_kopii(plan):
    """Ile plików pójdzie z cache na mapę — z appmanifest, tak jak liczy licznik
    kopiowania (26.09 dziennik mówił „kopiuję 39 plików”, a potem „skopiowano 40/40”)."""
    return len(plan.get("kopiuj") or ()) + (1 if plan.get("manifest") else 0)


class _Blad(Exception):
    def __init__(self, tekst, licz=True):
        super().__init__(tekst)
        self.licz = licz          # False = „nie teraz”, nie nieudana próba


class Wtyczka:
    nazwa = "aktualizacja_serwera"
    API = 1
    TR = {}
    manager_visible = True
    version = "2.1.1"
    required = False
    default_enabled = True
    main_action_hook = "panel"
    main_action_requires_enabled = False
    panel_available_when_off = True

    @property
    def manager_name(self):
        return t("Aktualizacja serwera (SteamCMD)", "Server update (SteamCMD)")

    @property
    def main_action_text(self):
        return t("UPDATE SERWERA", "SERVER UPDATE")

    @property
    def manager_description(self):
        return t(
            "Co minutę sprawdza najnowszy build serwera ASA (api.steamcmd.net, zapasowo SteamCMD) "
            "i od razu pobiera go do własnego cache obok serwerów — serwery w tym czasie działają, "
            "a błąd pobierania nie wywołuje żadnego restartu. Gdy cache jest gotowy, mapa ze "
            "starszym buildem przechodzi zwykłą kolejkę restartu (ogłoszenia, pusta = od razu, "
            "jeden start naraz); po wyłączeniu serwera kopiowane są tylko zmienione pliki "
            "(z kopią zapasową), a manager serwerów jest na ten czas wstrzymany i potem sam "
            "podnosi zaktualizowany serwer. Nie działa, gdy w managerze włączony jest jego własny "
            "updater. Wymaga uprawnień administratora.",
            "Checks the latest ASA server build every minute (api.steamcmd.net, SteamCMD as a "
            "fallback) and downloads it right away into its own cache next to the servers — the "
            "servers keep running, and a failed download never causes a restart. Once the cache "
            "is ready, a map with an older build goes through the normal restart queue "
            "(announcements, empty = at once, one start at a time); after the server stops only "
            "the changed files are copied (with a backup), and the server manager is paused "
            "meanwhile and then starts the updated server itself. Does nothing while the manager's "
            "own updater is on. Needs administrator rights.")

    def __init__(self):
        self.core = None
        self.enabled = True
        self.cfg = self._domyslne()
        self.zdalny = None
        self.zrodlo = ""
        self.blad = None
        self.wyjscie = ""
        self.lokalne = {}
        self.cache = {"katalog": None, "dane": None, "blad": None, "konflikt": None}
        self.manager_upd = ("nieznany", "", {})
        self.plany = {}
        self.api_awaria = False
        self.api_blad = None
        self.ostatnie = 0.0
        self._nastepne_api = 0.0
        self._nastepne_steamcmd = 0.0
        self._sprawdzanie = False
        self._planowanie = False
        self._cache_praca = None
        self._cache_porazki = []
        self._cache_nastepna = 0.0
        self._zadanie = None
        self._recovery_praca = False
        self._recovery_proby = 0
        self._recovery_nastepna = 0.0
        self._alarm_tekst = ""
        self._alarm_nastepny = 0.0
        self._pid_portu = {}
        self._zgloszone = set()
        self._powod_czekania = None
        self._nie_gotowa_od = {}
        self._lock = threading.Lock()     # jeden SteamCMD refreshera naraz
        self._stan = threading.Lock()     # przejścia fazy zadania (UI, timer, wątek pracy)
        self.zamrazarka = None
        self.window = None
        self._widok = {}

    @staticmethod
    def _domyslne():
        return {"enabled": True, "auto": True, "walidacja": True, "api": True,
                "api_co_s": API_CO_S, "steamcmd_co_min": STEAMCMD_CO_MIN,
                "manager": MANAGER_DOMYSLNY, "steamcmd": "", "cache": "", "proby": {}, "proby_v": 2}

    @staticmethod
    def _katalog_programu():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # -- cykl życia --------------------------------------------------------------
    def prepare(self, core):
        self.core = core
        cfg = self._domyslne()
        zapisane = core.plugin_config(self.nazwa)
        if isinstance(zapisane, dict):
            cfg.update({k: v for k, v in zapisane.items() if k in cfg})
            if zapisane.get("proby_v") != 2:
                # Próby z V3.85 dotyczyły SteamCMD na katalogu mapy (inny mechanizm,
                # inne błędy) — nie mogą blokować podmiany z cache.
                cfg["proby"] = {}
                cfg["proby_v"] = 2
        if not isinstance(cfg.get("proby"), dict):
            cfg["proby"] = {}
        self.cfg = cfg
        self.enabled = bool(cfg.get("enabled", self.default_enabled))
        # Host woła prepare() ponownie przy zmianie języka — wstrzymanego managera
        # musi wznowić TA SAMA zamrażarka, która go wstrzymała.
        if self.zamrazarka is None or not self.zamrazarka.aktywna():
            self.zamrazarka = self._nowa_zamrazarka()
        self._wskaznik()

    def _nowa_zamrazarka(self):
        katalog = os.path.join(self._katalog_programu(), "CONFIG_PROGRAM")
        return Zamrazarka(os.path.join(katalog, PLIK_DZIERZAWY), self.cfg.get("manager"))

    def start(self, core):
        """Dla hostów bez prepare/activate: przygotowanie i aktywacja naraz."""
        self.prepare(core)
        self.activate()

    def activate(self):
        """Host woła to po prepare(), gdy plugin ma działać (start programu, ON)."""
        # Refresher padł w trakcie podmiany plików? Manager mógł zostać wstrzymany,
        # a kopiowanie przerwane — odzyskanie najpierw je cofa, potem wznawia managera.
        try:
            odzyskanie = self.zamrazarka.odzyskaj_po_awarii()
            wznowione = odzyskanie.wznowione
            if odzyskanie.zablokowane:
                self.core.warn(t("[SERWER] Odzyskiwanie: %s. Automatyczne restarty wstrzymane: %s",
                                 "[SERVER] Recovery: %s. Automatic restarts blocked: %s") %
                               (odzyskanie.stan, "; ".join(odzyskanie.bledy)))
        except Exception as exc:
            wznowione = []
            self.core.warn(t("[SERWER] Nie udało się sprawdzić stanu managera po awarii: %s",
                             "[SERVER] Could not check the manager state after a crash: %s") % exc)
        if wznowione:
            self.core.warn(t("[SERWER] Po poprzednim uruchomieniu manager był wstrzymany — "
                             "wznowiony (PID %s).",
                             "[SERVER] The manager was left paused by the previous run — "
                             "resumed (PID %s).") % ", ".join(str(p) for p in wznowione))
        teraz = time.time()
        self._nastepne_api = teraz + PIERWSZE_SPRAWDZENIE_S
        self._nastepne_steamcmd = teraz + (KONTROLA_STEAMCMD_S if self.cfg.get("api", True)
                                           else PIERWSZE_SPRAWDZENIE_S)

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, value):
        self.enabled = bool(value)
        self.cfg["enabled"] = self.enabled
        self._zapisz_cfg()
        if not self.enabled:
            z = self._zadanie
            bledy = self._anuluj_zamrozenie(z)
            if bledy is not None:
                # DoExit jeszcze nie poszedł — nic się nie kopiuje, wznawiamy od razu.
                self._ostrzez_o_wznowieniu(bledy)
                self._zadanie = None
            # Wyłączony plugin nie restartuje map: czekające zlecenia znikają.
            # (Trwająca podmiana plików kończy się normalnie i sama wznawia managera;
            # trwające pobieranie do cache też się kończy — nie dotyka serwerów.)
            app = self.core.application() if self.core is not None else None
            if app is not None and getattr(type(app), "odwolaj_zlecenia", None) is not None:
                app.odwolaj_zlecenia(self.nazwa)
        if self.core is not None:
            self.core.set_plugin_toggle(self.nazwa, self.enabled)
        self._wskaznik()

    def konfiguracja(self):
        return dict(self.cfg)

    def stop(self):
        z = self._zadanie
        if self._anuluj_zamrozenie(z) is not None:
            # DoExit jeszcze nie poszedł — nic się nie kopiuje, wznawiamy od razu.
            self._zadanie = None
        # W trakcie kopiowania wznowienie zrobi strażnik (po wycofaniu kopiowania).
        self._zamknij_okno()

    def self_test(self):
        exe = self._sciezka_steamcmd(self.cfg)
        ma_steamcmd = os.path.isfile(exe)
        ok, powod = self._warunki_managera()
        return {"ok": True, "details": t("SteamCMD: %s; manager: %s; cache: %s; bez aktualizacji",
                                         "SteamCMD: %s; manager: %s; cache: %s; nothing updated") % (
            t("jest", "present") if ma_steamcmd else t("zostanie pobrany", "will be downloaded"),
            t("dostępny", "reachable") if ok else self._opis_zamrozenia(powod),
            self.cache.get("katalog") or self.cfg.get("cache") or t("jeszcze nieustalony", "not set yet"))}

    def _zapisz_cfg(self):
        if self.core is not None:
            self.core.save_plugin_config(self.nazwa, dict(self.cfg))

    # -- dane z monitora procesów --------------------------------------------------
    def dane_monitora(self, dane):
        pidy = dane.get("pid") if isinstance(dane, dict) else None
        if isinstance(pidy, dict):
            self._pid_portu = {str(k): v for k, v in pidy.items()}

    # -- praca w tle ----------------------------------------------------------------
    def _api_co_s(self):
        try:
            return max(API_MIN_S, int(self.cfg.get("api_co_s") or API_CO_S))
        except (TypeError, ValueError):
            return API_CO_S

    def _steamcmd_co_s(self):
        """SteamCMD: co 5 min jako zapas, raz na godzinę kontrolnie przy działającym API."""
        if self.cfg.get("api", True) and not self.api_awaria:
            return KONTROLA_STEAMCMD_S
        try:
            return max(5, int(self.cfg.get("steamcmd_co_min") or STEAMCMD_CO_MIN)) * 60
        except (TypeError, ValueError):
            return STEAMCMD_CO_MIN * 60

    def tik(self, teraz):
        if self.zamrazarka and teraz >= self._alarm_nastepny:
            self._alarm_nastepny = teraz + 5
            self._pokaz_alarm()
        if self.zamrazarka and self.zamrazarka.aktywna() and not self._zadanie \
                and not self._recovery_praca and self._recovery_proby < 10 and teraz >= self._recovery_nastepna:
            self.ponow_odzyskiwanie(reczne=False)
        z = self._zadanie
        if z and z.get("faza") == "instalacja" and teraz - z.get("t0", teraz) > LIMIT_S \
                and self._raz(("copy_timeout", z.get("t0"))):
            self.core.warn(t("[SERWER] %s: przekroczono czas podmiany. Worker nadal może pracować — "
                             "manager pozostaje wstrzymany. Zamknięcie procesu Refreshera uruchomi strażnika: "
                             "spróbuje cofnąć pliki i dopiero po potwierdzeniu spójności wznowi managera.",
                             "[SERVER] %s: copy deadline exceeded. The worker may still be active — "
                             "the manager remains paused. Exiting the Refresher process lets the guardian attempt "
                             "rollback and resume the manager only after file consistency is confirmed.") % z["mapa"])
        if z and z.get("faza") == "zamrozony" and teraz - z.get("t0", teraz) > ZAMROZENIE_BEZ_DOEXIT_S:
            self._bez_instalacji(z)               # to samo robi też timer (bez wątku UI)
        if not self.enabled or self._sprawdzanie or self._zadanie:
            return
        if self.cfg.get("api", True) and teraz >= self._nastepne_api:
            self.sprawdz(zrodlo="api")
        elif teraz >= self._nastepne_steamcmd:
            self.sprawdz(zrodlo="steamcmd")

    def sprawdz(self, reczne=False, wymus=False, zrodlo=None):
        """Uruchom sprawdzenie w tle. False = już trwa albo trwa podmiana plików.

        zrodlo: "api" | "steamcmd" | "lokalne" (bez pytania Steama) | None = API,
        a gdy wyłączone albo nie odpowiada — SteamCMD. reczne — z przycisku (błędy
        zawsze w dzienniku); wymus — „AKTUALIZUJ TERAZ”: działa także przy
        wyłączonym „automatycznie” i mimo limitu nieudanych prób."""
        if self._sprawdzanie or self._zadanie:
            return False
        teraz = time.time()
        if zrodlo is None:
            zrodlo = "api" if self.cfg.get("api", True) and not self.api_awaria else "steamcmd"
        if zrodlo == "api":
            self._nastepne_api = teraz + self._api_co_s()
        elif zrodlo == "steamcmd":
            self._nastepne_steamcmd = teraz + self._steamcmd_co_s()
        self._sprawdzanie = True
        mapy = {}
        for nazwa, tab in self.core.tabs().items():
            if tab.enabled:
                mapy[nazwa] = {"katalog": S.katalog_instalacji(tab.log_path),
                               "port": str(tab.rcon_port or "").strip(),
                               "status": str(getattr(tab, "status", "") or "")}
        self._wskaznik()
        self.core.run_async(self._sprawdz_praca, mapy, dict(self.cfg), zrodlo, reczne, wymus)
        return True

    def _katalog_cache(self, cfg, mapy):
        wlasny = str(cfg.get("cache") or "").strip()
        return wlasny or S.domyslny_katalog_cache([m.get("katalog") for m in mapy.values()])

    def _sprawdz_praca(self, mapy, cfg, zrodlo, reczne, wymus=False):
        wynik = {"lokalne": {}, "zdalny": None, "zrodlo": "", "blad": None, "wyjscie": "",
                 "rodzaj": zrodlo, "api_blad": None, "api_czekaj": None, "zajety": False,
                 "cache": {"katalog": None, "dane": None, "blad": None, "konflikt": None},
                 "manager": ("nieznany", "", {})}
        try:
            for nazwa, info in mapy.items():
                wpis = dict(info, dane=None, blad=None)
                if not info["katalog"]:
                    wpis["blad"] = "katalog"
                else:
                    wpis["dane"], wpis["blad"] = S.czytaj_lokalny(info["katalog"])
                wynik["lokalne"][nazwa] = wpis
            try:
                wynik["manager"] = S.updater_managera(os.environ.get("LOCALAPPDATA", ""))
            except Exception as exc:
                wynik["manager"] = ("nieznany", str(exc), {})
            katalog = self._katalog_cache(cfg, mapy)
            cache = wynik["cache"]
            cache["katalog"] = katalog
            cache["konflikt"] = S.konflikt_katalogu_cache(
                katalog, [m.get("katalog") for m in mapy.values()],
                (wynik["manager"][2] or {}).get("CacheUpdatePath"))
            if katalog and not cache["konflikt"]:
                cache["dane"], cache["blad"] = S.czytaj_lokalny(katalog)
            if zrodlo == "api":
                try:
                    odp = siec.steam_api_info(S.URL_API % S.APPID, timeout=TIMEOUT_API_S)
                    zdalny = S.zdalny_z_api(odp)
                    if zdalny:
                        wynik["zdalny"], wynik["zrodlo"] = zdalny, "api.steamcmd.net"
                    else:
                        wynik["api_blad"] = t("nieczytelna odpowiedź", "unreadable response")
                except siec.ApiZajete as exc:
                    wynik["api_blad"], wynik["api_czekaj"] = str(exc), exc.za_ile
                except RuntimeError as exc:
                    wynik["api_blad"] = str(exc)
            elif zrodlo == "steamcmd":
                if not self._lock.acquire(blocking=False):
                    wynik["zajety"] = True           # np. trwa pobieranie do cache
                else:
                    try:
                        exe, blad = self._zapewnij_steamcmd(cfg)
                        if exe:
                            (wynik["zdalny"], wynik["zrodlo"], wynik["blad"],
                             wynik["wyjscie"]) = self._zapytaj_steam(exe)
                        else:
                            wynik["blad"] = blad
                    finally:
                        self._lock.release()
        except Exception as exc:
            wynik["blad"] = t("błąd sprawdzania: %s", "check error: %s") % exc
        finally:
            self.core.post_ui(lambda: self._po_sprawdzeniu(wynik, reczne, wymus))

    def _sciezka_steamcmd(self, cfg):
        wlasna = str(cfg.get("steamcmd") or "").strip()
        return wlasna or os.path.join(self._katalog_programu(), "STEAMCMD", "steamcmd.exe")

    def _zapewnij_steamcmd(self, cfg):
        """(ścieżka, błąd). Własny SteamCMD pobierany od Valve przy pierwszym użyciu."""
        sciezka = self._sciezka_steamcmd(cfg)
        if os.path.isfile(sciezka):
            return sciezka, None
        if str(cfg.get("steamcmd") or "").strip():
            return None, t("nie ma SteamCMD pod wskazaną ścieżką: %s",
                           "SteamCMD not found at the given path: %s") % sciezka
        if os.name != "nt":
            return None, t("SteamCMD dla serwera ASA działa tylko na Windows",
                           "SteamCMD for the ASA server works only on Windows")
        katalog = os.path.dirname(sciezka)
        os.makedirs(katalog, exist_ok=True)
        czesciowy = os.path.join(katalog, "steamcmd.zip.part")
        self.core.log(t("[SERWER] Pobieram SteamCMD od Valve: %s", "[SERVER] Downloading SteamCMD from Valve: %s")
                      % URL_STEAMCMD)
        try:
            with urllib.request.urlopen(URL_STEAMCMD, timeout=60) as odp, open(czesciowy, "wb") as fh:
                shutil.copyfileobj(odp, fh)
            with zipfile.ZipFile(czesciowy) as z:
                if z.testzip() is not None or "steamcmd.exe" not in z.namelist():
                    return None, t("pobrane archiwum SteamCMD jest uszkodzone",
                                   "the downloaded SteamCMD archive is damaged")
                z.extract("steamcmd.exe", katalog)
        except Exception as exc:
            return None, t("nie udało się pobrać SteamCMD: %s", "could not download SteamCMD: %s") % exc
        finally:
            try:
                os.remove(czesciowy)
            except OSError:
                pass
        self.core.log(t("[SERWER] SteamCMD zapisany: %s (pierwsze uruchomienie sam się aktualizuje).",
                        "[SERVER] SteamCMD saved: %s (the first run updates itself).") % sciezka)
        return sciezka, None

    def _zapytaj_steam(self, exe):
        """(zdalny, źródło, błąd, wyjście). appinfo.vdf usuwane przed pytaniem —
        inaczej SteamCMD potrafi podać stary build (LinuxGSM, WindowsGSM)."""
        appinfo = os.path.join(os.path.dirname(exe), "appcache", "appinfo.vdf")
        try:
            os.remove(appinfo)
        except FileNotFoundError:
            pass
        except OSError as exc:
            return None, "", t("nie mogę usunąć starego appinfo.vdf: %s",
                               "cannot delete the old appinfo.vdf: %s") % exc, ""
        start = time.time()
        kod, tekst, za_dlugo = self._uruchom(S.komenda_info(exe), TIMEOUT_INFO_S)
        # Po samoaktualizacji SteamCMD potrafi uruchomić się ponownie jako nowy
        # proces — appinfo.vdf jest kompletny dopiero, gdy skończy i on.
        self._dokoncz_steamcmd(exe, TIMEOUT_INFO_S - (time.time() - start))
        zdalny, zrodlo = S.zdalny_z_konsoli(tekst), "SteamCMD"
        if zdalny is None:
            try:
                with open(appinfo, "rb") as fh:
                    zdalny = S.zdalny_z_aplikacji(S.appinfo_aplikacja(fh.read()))
                zrodlo = "SteamCMD (appinfo.vdf)"
            except OSError:
                zdalny = None
        if zdalny is None:
            return None, "", t("SteamCMD nie podał buildu (kod wyjścia %s%s)",
                               "SteamCMD did not report a build (exit code %s%s)") % (
                kod, t(", przekroczony czas", ", timed out") if za_dlugo else ""), tekst[-4000:]
        return zdalny, zrodlo, None, tekst[-4000:]

    def _pozostale_steamcmd(self, exe):
        """PID-y działających procesów z TEGO pliku steamcmd.exe."""
        api = getattr(self.zamrazarka, "api", None)
        if api is None:
            return []
        cel = os.path.normcase(os.path.abspath(exe))
        try:
            pidy = api.procesy(os.path.basename(exe))
        except OSError:
            return []
        wynik = []
        for pid in pidy:
            try:
                if os.path.normcase(os.path.abspath(api.sciezka_exe(pid))) == cel:
                    wynik.append(pid)
            except OSError:
                pass
        return wynik

    def _dokoncz_steamcmd(self, exe, limit_s, spij=time.sleep):
        """Czekaj, aż skończą się pozostałe procesy naszego SteamCMD (np. ponowne
        uruchomienie po samoaktualizacji); po limicie — zakończ je.
        True = nic nie trzeba było kończyć."""
        koniec = time.time() + max(0.0, float(limit_s))
        while True:
            pidy = self._pozostale_steamcmd(exe)
            if not pidy:
                return True
            if time.time() >= koniec:
                for pid in pidy:
                    try:
                        self.zamrazarka.api.zakoncz(pid)
                    except OSError:
                        pass
                return False
            spij(2.0)

    @staticmethod
    def _uruchom(argv, limit_s, na_start=None, na_linie=None):
        """(kod, tekst, przekroczony_czas). Wyjście czytane na bieżąco."""
        flagi = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
        proces = subprocess.Popen(argv, cwd=os.path.dirname(argv[0]) or None,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, creationflags=flagi)
        if na_start is not None:
            try:
                na_start(proces.pid)
            except Exception:
                pass
        linie = []

        def czytaj():
            for surowa in iter(proces.stdout.readline, b""):
                linia = surowa.decode("utf-8", "replace").rstrip("\r\n")
                linie.append(linia)
                if len(linie) > 5000:
                    del linie[:1000]
                if na_linie is not None:
                    try:
                        na_linie(linia)
                    except Exception:
                        pass
        czytnik = threading.Thread(target=czytaj, daemon=True)
        czytnik.start()
        za_dlugo = False
        try:
            kod = proces.wait(timeout=limit_s)
        except subprocess.TimeoutExpired:
            za_dlugo = True
            proces.kill()
            kod = proces.wait()
        czytnik.join(5.0)
        return kod, "\n".join(linie), za_dlugo

    @staticmethod
    def _content_log(exe):
        """Koniec logs/content_log.txt SteamCMD (tam jest prawdziwy powód porażki)."""
        sciezka = os.path.join(os.path.dirname(exe), "logs", "content_log.txt")
        try:
            with open(sciezka, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                rozmiar = fh.tell()
                fh.seek(max(0, rozmiar - 256 * 1024))
                return fh.read().decode("utf-8", "replace")
        except OSError:
            return ""

    # -- wynik sprawdzenia (wątek UI) -------------------------------------------------
    @staticmethod
    def _oznacz_wspolne(lokalne):
        """Mapy z tej samej instalacji: pliki można podmienić tylko przy wyłączonych
        wszystkich tych mapach naraz, a kolejka restartuje po jednej — takich map
        nie aktualizujemy."""
        wg_katalogu = {}
        for nazwa, info in lokalne.items():
            if info.get("katalog") and info.get("blad") != "katalog":
                klucz = os.path.normcase(os.path.normpath(info["katalog"]))
                wg_katalogu.setdefault(klucz, []).append(nazwa)
        for nazwy in wg_katalogu.values():
            if len(nazwy) > 1:
                for nazwa in nazwy:
                    lokalne[nazwa]["blad"] = "wspolny"
                    lokalne[nazwa]["wspolny"] = sorted(n for n in nazwy if n != nazwa)

    def _raz(self, klucz):
        """True tylko przy pierwszym zgłoszeniu danego stanu (bez spamu co minutę)."""
        if klucz in self._zgloszone:
            return False
        self._zgloszone.add(klucz)
        return True

    def _po_sprawdzeniu(self, wynik, reczne, wymus=False):
        self._sprawdzanie = False
        teraz = time.time()
        self._oznacz_wspolne(wynik["lokalne"])
        self.lokalne = wynik["lokalne"]
        self.cache = wynik["cache"]
        self.manager_upd = wynik["manager"]
        self.wyjscie = wynik.get("wyjscie") or self.wyjscie
        if wynik["rodzaj"] == "api":
            if wynik["api_blad"]:
                self.api_blad = wynik["api_blad"]
                if not self.api_awaria or reczne:
                    self.core.warn(t("[SERWER] api.steamcmd.net nie odpowiada (%s) — zapasowo SteamCMD "
                                     "co %d min.",
                                     "[SERVER] api.steamcmd.net does not answer (%s) — SteamCMD every "
                                     "%d min as a fallback.")
                                   % (wynik["api_blad"], max(5, int(self.cfg.get("steamcmd_co_min") or 5))))
                if not self.api_awaria:
                    # Pierwsza porażka: SteamCMD od razu, dalej co N min (nie co minutę).
                    self._nastepne_steamcmd = min(self._nastepne_steamcmd, teraz)
                self.api_awaria = True
                if wynik.get("api_czekaj"):
                    self._nastepne_api = teraz + max(self._api_co_s(), int(wynik["api_czekaj"]))
            else:
                if self.api_awaria:
                    self.core.log(t("[SERWER] api.steamcmd.net znowu odpowiada.",
                                    "[SERVER] api.steamcmd.net answers again."))
                    # Koniec trybu zapasowego: SteamCMD wraca do kontroli raz na godzinę.
                    self._nastepne_steamcmd = teraz + KONTROLA_STEAMCMD_S
                self.api_awaria = False
                self.api_blad = None
        if wynik.get("zajety"):
            self._nastepne_steamcmd = teraz + 5 * 60        # SteamCMD zajęty (pobieranie) — bez ostrzeżeń
        nowy = wynik.get("zdalny")
        if nowy:
            if not self.zdalny or nowy["buildid"] != self.zdalny["buildid"]:
                self.core.log(t("[SERWER] Steam: build %d (manifest %s, źródło: %s).",
                                "[SERVER] Steam: build %d (manifest %s, source: %s).")
                              % (nowy["buildid"], nowy.get("manifest") or "?", wynik["zrodlo"]))
            self.zdalny, self.zrodlo, self.blad = nowy, wynik["zrodlo"], None
            self.ostatnie = teraz
        elif wynik.get("blad"):
            if wynik.get("blad") != self.blad or reczne:
                self.core.warn(t("[SERWER] Nie znam najnowszego buildu ze Steama: %s",
                                 "[SERVER] The latest Steam build is unknown: %s") % wynik.get("blad"))
            self.blad = wynik.get("blad")
        for nazwa in sorted(self.lokalne):
            info = self.lokalne[nazwa]
            if info.get("status", "ready") == "ready":
                self._nie_gotowa_od.pop(nazwa, None)
            klucz = ("mapa", nazwa, info.get("blad"))
            if info.get("blad") == "katalog":
                if self._raz(klucz):
                    self.core.warn(t("[SERWER] %s: folder logu mapy nie leży w …\\ShooterGame\\Saved\\Logs — "
                                     "nie wiem, gdzie jest serwer; tej mapy nie aktualizuję.",
                                     "[SERVER] %s: the map's log folder is not inside …\\ShooterGame\\Saved\\Logs "
                                     "— the server location is unknown; this map is not updated.") % nazwa)
            elif info.get("blad") == "wspolny":
                if self._raz(klucz):
                    self.core.warn(t("[SERWER] %s: ta sama instalacja serwera co %s (%s) — pliki można "
                                     "podmienić tylko przy wyłączeniu wszystkich tych map naraz, a kolejka "
                                     "restartuje po jednej; tej mapy nie aktualizuję.",
                                     "[SERVER] %s: the same server install as %s (%s) — files can only be "
                                     "replaced with all those maps shut down at once, while the queue "
                                     "restarts one at a time; this map is not updated.")
                                   % (nazwa, ", ".join(info.get("wspolny") or ()), info["katalog"]))
            elif info.get("blad"):
                if self._raz(klucz):
                    self.core.warn(t("[SERWER] %s: brak czytelnego %s w %s — to nie wygląda na "
                                     "instalację SteamCMD; tej mapy nie aktualizuję.",
                                     "[SERVER] %s: no readable %s in %s — this does not look like a "
                                     "SteamCMD install; this map is not updated.")
                                   % (nazwa, S.PLIK_MANIFESTU, os.path.join(info["katalog"], "steamapps")))
        self._wskaznik()
        self._odswiez_panel()
        if not (self.enabled and (self.cfg.get("auto") or wymus)):
            return
        self._decyduj(reczne, wymus)

    # -- decyzje (wątek UI) --------------------------------------------------------------
    def _decyduj(self, reczne=False, wymus=False):
        stan, opis, _ = self.manager_upd
        if stan == "wlaczony":
            if self._raz(("manager_upd", "wlaczony")) or reczne:
                self.core.warn(t("[SERWER] Aktualizacja wstrzymana: %s. Dwa updatery by się pogryzły "
                                 "(manager przed swoją aktualizacją zabija każdy steamcmd.exe). Wyłącz "
                                 "je w Update Settings managera albo wyłącz ten plugin.",
                                 "[SERVER] Update on hold: %s. Two updaters would clash (before its own "
                                 "update the manager kills every steamcmd.exe). Turn it off in the "
                                 "manager's Update Settings or turn this plugin off.") % opis)
            self._wskaznik()
            return
        self._zgloszone.discard(("manager_upd", "wlaczony"))
        if stan == "nieznany" and self._raz(("manager_upd", "nieznany", opis)):
            self.core.warn(t("[SERWER] Nie wiem, czy updater managera jest wyłączony (%s). Jeśli jest "
                             "włączony, wyłącz go — inaczej dwa updatery się pogryzą.",
                             "[SERVER] Unknown whether the manager updater is off (%s). If it is on, "
                             "turn it off — otherwise two updaters will clash.") % opis)
        konflikt = self.cache.get("konflikt")
        if konflikt:
            if self._raz(("cache_konflikt", konflikt)) or reczne:
                self.core.warn(t("[SERWER] Cache: %s — nic nie pobieram.",
                                 "[SERVER] Cache: %s — nothing is downloaded.") % konflikt)
            return
        if self._zadanie or self._planowanie or self._cache_praca:
            return
        dane_cache = self.cache.get("dane")
        if S.cache_do_aktualizacji(self.zdalny, dane_cache):
            if self.zdalny is None and not wymus:
                return                  # nie wiadomo, czego chce Steam — nic nie pobieramy na ślepo
            self._aktualizuj_cache(reczne, wymus)
            return
        mapy = S.mapy_do_przeniesienia(self.lokalne, dane_cache, self.zdalny)
        if not mapy:
            if wymus:
                self.core.log(t("[SERWER] Nic do aktualizacji — mapy z odczytanym buildem mają build "
                                "cache %d.",
                                "[SERVER] Nothing to update — maps with a readable build have the "
                                "cache build %d.") % dane_cache["buildid"])
            return
        if any(not self._plan_aktualny(m) for m in mapy):
            # Wszystkie razem: jedna runda kolejki zamiast mapy po mapie co minutę.
            self._zaplanuj(mapy, reczne, wymus)
            return
        self._zlec_mapy(mapy, reczne, wymus)

    def _moje_zlecenia_czekaja(self):
        """Czy w kolejce rdzenia są jeszcze zlecenia tego pluginu (runda niezakończona)."""
        app = self.core.application() if self.core is not None else None
        if app is None:
            return False
        zlecenia = {}
        fn = getattr(app, "_zlecenia", None)
        try:
            zlecenia = fn() if callable(fn) else {}
        except Exception:
            zlecenia = {}
        w_kolejce = getattr(app, "__dict__", {}).get("_zlecenia_w_kolejce") or {}
        for z in list((zlecenia or {}).values()) + list(w_kolejce.values()):
            if isinstance(z, dict) and z.get("wlasciciel") == self.nazwa:
                return True
        return False

    # -- cache ----------------------------------------------------------------------------
    def _aktualizuj_cache(self, reczne=False, wymus=False):
        if self._cache_praca:
            return False
        teraz = time.time()
        katalog = self.cache.get("katalog")
        if not katalog:
            return False
        if not wymus and teraz < self._cache_nastepna:
            return False
        if self._zadanie or self._moje_zlecenia_czekaja():
            # Nie ruszamy cache w trakcie rundy: mapy w kolejce mają plan na obecny cache.
            if self._raz(("cache_czeka_runda", (self.zdalny or {}).get("buildid"))):
                self.core.log(t("[SERWER] Cache: nowy build pobiorę po zakończeniu bieżącej rundy "
                                "restartów.",
                                "[SERVER] Cache: the new build is downloaded after the current "
                                "restart round."))
            return False
        dane_cache = self.cache.get("dane")
        pierwsze = not S.cache_gotowy(dane_cache)
        rozmiar = (self.zdalny or {}).get("rozmiar")
        if pierwsze and rozmiar:
            wolne = self._wolne_miejsce(katalog)
            if wolne is not None and wolne < rozmiar + ZAPAS_MIEJSCA:
                if self._raz(("cache_miejsce", int(wolne // GB))) or reczne:
                    self.core.warn(t("[SERWER] Cache: za mało miejsca na dysku (%s): potrzeba ok. %.1f GB, "
                                     "wolne %.1f GB — nic nie pobieram.",
                                     "[SERVER] Cache: not enough disk space (%s): about %.1f GB needed, "
                                     "%.1f GB free — nothing is downloaded.")
                                   % (katalog, (rozmiar + ZAPAS_MIEJSCA) / GB, wolne / GB))
                self._cache_nastepna = teraz + PRZERWY_CACHE_S[-1]
                return False
        cel = (self.zdalny or {}).get("buildid")
        self._cache_praca = {"t0": teraz, "cel": cel, "katalog": katalog, "wymus": bool(wymus)}
        self.plany.clear()              # plany dotyczą poprzedniej zawartości cache
        if pierwsze:
            self.core.log(t("[SERWER] Cache: pierwsze pobranie serwera do %s%s — serwery działają dalej.",
                            "[SERVER] Cache: first server download into %s%s — the servers keep running.")
                          % (katalog, (t(" (ok. %.1f GB)", " (about %.1f GB)") % (rozmiar / GB)) if rozmiar
                             else ""), "st_wait")
        else:
            self.core.log(t("[SERWER] Cache: pobieram build %s (w cache jest %d) — serwery działają dalej.",
                            "[SERVER] Cache: downloading build %s (the cache has %d) — the servers keep "
                            "running.") % (cel if cel else "?", dane_cache["buildid"]), "st_wait")
        self._wskaznik()
        self._odswiez_panel()
        self.core.run_async(self._cache_praca_fn, dict(self._cache_praca), dict(self.cfg))
        return True

    @staticmethod
    def _wolne_miejsce(sciezka):
        """Wolne bajty na dysku ścieżki (idzie w górę do istniejącego katalogu) albo None."""
        p = os.path.abspath(str(sciezka))
        while p and not os.path.exists(p):
            rodzic = os.path.dirname(p)
            if rodzic == p:
                return None
            p = rodzic
        try:
            return shutil.disk_usage(p).free
        except OSError:
            return None

    def _cache_praca_fn(self, zadanie, cfg, spij=time.sleep):
        wynik = {"ok": False, "powod": "", "wyjscie": "", "dane": None, "log": [], "czas": 0.0}
        start = time.time()
        katalog = zadanie["katalog"]
        if not self._lock.acquire(timeout=TIMEOUT_INFO_S + 60):
            wynik["powod"] = t("SteamCMD refreshera jest zajęty", "the refresher's SteamCMD is busy")
            self.core.post_ui(lambda: self._po_cache(zadanie, wynik))
            return
        try:
            exe, blad = self._zapewnij_steamcmd(cfg)
            if not exe:
                raise _Blad(blad)
            os.makedirs(katalog, exist_ok=True)
            odmowa_obsluzona = False
            ponowienia = 0
            while True:
                poczatek = time.time()
                kod, tekst, za_dlugo = self._uruchom(
                    S.komenda_update(exe, katalog, bool(cfg.get("walidacja"))), TIMEOUT_UPDATE_S,
                    na_linie=self._postep(t("cache", "cache")))
                self._dokoncz_steamcmd(exe, max(60.0, TIMEOUT_UPDATE_S - (time.time() - poczatek)))
                wynik["wyjscie"] = tekst[-4000:]
                dane, _ = S.czytaj_lokalny(katalog)
                wynik["dane"] = dane
                if za_dlugo:
                    raise _Blad(t("SteamCMD przekroczył limit %d min", "SteamCMD exceeded the %d min limit")
                                % (TIMEOUT_UPDATE_S // 60))
                cel = zadanie.get("cel")
                if S.cache_gotowy(dane) and (not cel or int(dane["buildid"]) >= int(cel)):
                    wynik["ok"] = True
                    break
                log = self._content_log(exe)
                wynik["log"] = S.powod_z_logu(log)
                odmowa = S.odmowa_manifestu(log)
                if not odmowa_obsluzona and odmowa and dane and dane.get("manifest") == odmowa:
                    # SteamCMD nie ma manifestu buildu, który leży w cache (np. usunięty
                    # depotcache) — cache od zera: sam skan i pobranie. Serwery nietknięte.
                    odmowa_obsluzona = True
                    try:
                        os.remove(S.sciezka_manifestu(katalog))
                    except OSError:
                        pass
                    self.core.log(t("[SERWER] Cache: Steam odmówił manifestu %s — pobieram cache od zera "
                                    "(serwery nietknięte).",
                                    "[SERVER] Cache: Steam refused manifest %s — downloading the cache "
                                    "from scratch (servers untouched).") % odmowa)
                    continue
                if ponowienia < PONOWIENIA_BRAK_KONFIGURACJI and S.brak_konfiguracji(tekst, log):
                    ponowienia += 1
                    self.core.log(t("[SERWER] Cache: SteamCMD zgłosił 'Missing configuration' — nie miał "
                                    "jeszcze informacji o serwerze ASA (tak kończy się zwykle pierwszy "
                                    "przebieg świeżo pobranego SteamCMD). Ponawiam od razu (%d/%d), "
                                    "serwery nietknięte.",
                                    "[SERVER] Cache: SteamCMD reported 'Missing configuration' — it did "
                                    "not have the ASA server information yet (usually the first run of a "
                                    "freshly downloaded SteamCMD). Retrying right away (%d/%d), servers "
                                    "untouched.") % (ponowienia, PONOWIENIA_BRAK_KONFIGURACJI))
                    spij(PRZERWA_BRAK_KONFIGURACJI_S)
                    continue
                stan, opis = S.wynik_update(tekst, kod)
                if dane and dane.get("buildid") and cel and int(dane["buildid"]) < int(cel) and stan == "ok":
                    opis = t("po SteamCMD w cache jest build %s, oczekiwany %s",
                             "after SteamCMD the cache has build %s, expected %s") % (dane["buildid"], cel)
                wynik["powod"] = opis
                break
        except _Blad as exc:
            wynik["powod"] = str(exc)
        except Exception as exc:
            wynik["powod"] = t("błąd: %s", "error: %s") % exc
        finally:
            self._lock.release()
            wynik["czas"] = time.time() - start
            self.core.post_ui(lambda: self._po_cache(zadanie, wynik))

    def _po_cache(self, zadanie, wynik):
        self._cache_praca = None
        self.wyjscie = wynik.get("wyjscie") or self.wyjscie
        teraz = time.time()
        if wynik["ok"]:
            self._cache_porazki = []
            self._cache_nastepna = 0.0
            self.cache["dane"] = wynik["dane"]
            self.cache["blad"] = None
            self.core.log(t("[SERWER] Cache: build %d gotowy (%d s). Serwery nie były ruszane.",
                            "[SERVER] Cache: build %d ready (%d s). The servers were not touched.")
                          % (wynik["dane"]["buildid"], int(wynik["czas"])), "st_ok")
            self._wskaznik()
            self._odswiez_panel()
            # Od razu dalej: plan i kolejka (bez czekania na następne sprawdzenie).
            self.sprawdz(zrodlo="lokalne", wymus=bool(zadanie.get("wymus")))
            return
        self._cache_porazki.append(teraz)
        przerwa = PRZERWY_CACHE_S[min(len(self._cache_porazki), len(PRZERWY_CACHE_S)) - 1]
        self._cache_nastepna = teraz + przerwa
        szczegoly = ("; ".join(wynik.get("log") or ())) or t(
            "w ostatniej sesji content_log.txt brak rozpoznanej linii błędu",
            "no recognised error line in the last content_log.txt session")
        self.core.warn(t("[SERWER] Cache: pobieranie NIEUDANE — %s. SteamCMD (content_log): %s. Serwery NIE "
                         "były ruszane (żadnego restartu). Następna próba za %d min.",
                         "[SERVER] Cache: download FAILED — %s. SteamCMD (content_log): %s. The servers "
                         "were NOT touched (no restart). Next attempt in %d min.")
                       % (wynik["powod"] or "?", szczegoly, przerwa // 60))
        self._wskaznik()
        self._odswiez_panel()

    # -- planowanie kopiowania ---------------------------------------------------------
    def _plan_aktualny(self, mapa):
        p = self.plany.get(mapa)
        dane = self.cache.get("dane") or {}
        return bool(p) and p.get("cache_build") == dane.get("buildid") and \
            p.get("cache") == self.cache.get("katalog")

    def _zaplanuj(self, mapy, reczne=False, wymus=False):
        if self._planowanie:
            return False
        katalog_cache = self.cache.get("katalog")
        build = (self.cache.get("dane") or {}).get("buildid")
        zadania = []
        for nazwa in mapy:
            info = self.lokalne.get(nazwa) or {}
            if info.get("katalog") and not info.get("blad"):
                zadania.append((nazwa, info["katalog"]))
        if not zadania or not katalog_cache or not build:
            return False
        self._planowanie = True
        self._wskaznik()
        self.core.run_async(self._planuj_praca, zadania, katalog_cache, build, reczne, wymus)
        return True

    def _planuj_praca(self, zadania, katalog_cache, build, reczne, wymus):
        wyniki = {}
        try:
            for nazwa, katalog in zadania:
                try:
                    wyniki[nazwa] = {"plan": SYNC.plan(katalog_cache, katalog), "katalog": katalog,
                                     "cache": katalog_cache, "cache_build": build}
                except OSError as exc:
                    wyniki[nazwa] = {"blad": str(exc)}
        finally:
            self.core.post_ui(lambda: self._po_planowaniu(wyniki, build, reczne, wymus))

    def _po_planowaniu(self, wyniki, build, reczne, wymus):
        self._planowanie = False
        if (self.cache.get("dane") or {}).get("buildid") != build or self._cache_praca:
            return                                      # cache zmienił się w międzyczasie
        gotowe = []
        for nazwa, w in sorted(wyniki.items()):
            if w.get("blad"):
                if self._raz(("plan_blad", nazwa, w["blad"])) or reczne:
                    self.core.warn(t("[SERWER] %s: nie da się porównać plików z cache: %s — bez aktualizacji.",
                                     "[SERVER] %s: files cannot be compared with the cache: %s — no update.")
                                   % (nazwa, w["blad"]))
                continue
            pl = w["plan"]
            self.plany[nazwa] = w
            self.core.log(t("[SERWER] %s: do buildu %d brakuje %d z %d plików (%.1f MB); %d bez zmian treści.",
                            "[SERVER] %s: build %d needs %d of %d files (%.1f MB); %d with unchanged content.")
                          % (nazwa, build, len(pl["kopiuj"]), pl["plikow"], pl["bajty"] / MB, len(pl["czas"])))
            if not pl["kopiuj"]:
                self._tylko_manifest(nazwa, w)
            else:
                gotowe.append(nazwa)
        self._wskaznik()
        self._odswiez_panel()
        if gotowe:
            self._zlec_mapy(gotowe, reczne, wymus)

    def _tylko_manifest(self, nazwa, w):
        """Pliki identyczne z cache — brakuje tylko appmanifestu: bez restartu."""
        if self.zamrazarka.aktywna() or os.path.exists(os.path.join(w["katalog"], SYNC.KATALOG_KOPII)):
            self.core.warn(t("[SERWER] %s: najpierw odzyskiwanie poprzedniej operacji — bez zmiany manifestu.",
                             "[SERVER] %s: recover the previous operation before changing the manifest.") % nazwa)
            return
        ok, powod, _ = SYNC.wykonaj(w["plan"], w["cache"], w["katalog"])
        dane, _ = S.czytaj_lokalny(w["katalog"])
        if ok and dane and dane.get("buildid") == w["cache_build"]:
            self.plany.pop(nazwa, None)
            info = self.lokalne.get(nazwa)
            if info is not None:
                info["dane"] = dane
            self.core.log(t("[SERWER] %s: pliki już są jak w cache — zapisany tylko appmanifest "
                            "(build %d), bez restartu.",
                            "[SERVER] %s: the files already match the cache — only the appmanifest "
                            "was written (build %d), no restart.") % (nazwa, dane["buildid"]), "st_ok")
        else:
            self.core.warn(t("[SERWER] %s: nie udało się zapisać appmanifestu: %s",
                             "[SERVER] %s: the appmanifest could not be written: %s") % (nazwa, powod or "?"))

    def _zlec_mapy(self, mapy, reczne=False, wymus=False):
        do_kolejki, bez_serwera = [], []
        teraz = time.time()
        for nazwa in mapy:
            info = self.lokalne.get(nazwa) or {}
            status = info.get("status", "ready")
            if status == "ready":
                do_kolejki.append(nazwa)
                continue
            od = self._nie_gotowa_od.setdefault(nazwa, teraz)
            if status in STANY_BEZ_SERWERA or teraz - od >= NIE_GOTOWA_S or wymus:
                # Serwer nie działa (albo od dawna nie wstaje, np. pętla krachów po
                # modzie, który wymaga nowego serwera): DoExit niemożliwy — bez niego.
                bez_serwera.append(nazwa)
            elif self._raz(("gotowa", nazwa, status)):
                # Ogłoszenia dla mapy, która nie jest GOTOWA, poszłyby na próżno
                # (DoExit i tak czeka na GOTOWY) — zlecenie przy następnym sprawdzeniu.
                self.core.log(t("[SERWER] %s: czeka z aktualizacją, aż mapa będzie GOTOWA "
                                "(albo wyłączona).",
                                "[SERVER] %s: the update waits until the map is READY "
                                "(or shut down).") % nazwa)
        if do_kolejki:
            self.zlec(do_kolejki, reczne=wymus)
        if bez_serwera and not self._zadanie:
            # Jedna naraz; następna przy kolejnym sprawdzeniu.
            self.aktualizuj_bez_serwera(bez_serwera[0], reczne=wymus)

    # -- kolejka ----------------------------------------------------------------------------
    def _manager_gotowy(self, reczne):
        """Czy da się wstrzymać managera. Ten sam powód nie jest powtarzany co sprawdzenie."""
        ok, powod = self._warunki_managera()
        if not ok:
            if reczne or powod != self._powod_czekania:
                self.core.warn(t("[SERWER] Aktualizacja czeka: %s",
                                 "[SERVER] The update waits: %s") % self._opis_zamrozenia(powod))
            self._powod_czekania = powod
            return False
        self._powod_czekania = None
        return True

    def _cel(self):
        return (self.cache.get("dane") or {}).get("buildid")

    def _dozwolone(self, nazwy, reczne):
        """Mapy, dla których limit nieudanych prób pozwala próbować (ręcznie — zawsze)."""
        cel = self._cel()
        teraz = time.time()
        dozwolone = []
        for nazwa in nazwy:
            wolno, dlaczego = S.proby_dozwolone(self._proby(nazwa, cel), teraz)
            if wolno or reczne:
                dozwolone.append(nazwa)
            elif dlaczego == "limit" and self._raz(("limit", nazwa, cel)):
                self.core.warn(t("[SERWER] %s: %d nieudane próby podmiany plików na build %d — "
                                 "automat przestaje próbować (ręcznie: panel UPDATE SERWERA).",
                                 "[SERVER] %s: %d failed attempts to replace the files with build %d — "
                                 "the automation stops trying (manually: the SERVER UPDATE panel).")
                               % (nazwa, S.MAKS_PROB, cel))
        return dozwolone

    def zlec(self, nazwy, reczne=False):
        """Zlecenie restartu map do kolejki. Warunki sprawdzone PRZED ogłoszeniami."""
        cel = self._cel()
        if not cel or not self._manager_gotowy(reczne):
            return []
        dozwolone = [n for n in self._dozwolone(nazwy, reczne) if self._plan_aktualny(n)]
        if not dozwolone:
            return []
        app = self.core.application()
        if getattr(type(app), "zlec_restart", None) is None:
            self.core.warn(t("[SERWER] Rdzeń programu nie przyjmuje zleceń restartu.",
                             "[SERVER] The program core does not accept restart requests."))
            return []
        przyjete = app.zlec_restart(dozwolone, t("aktualizacja serwera ASA do buildu %d",
                                                 "ASA server update to build %d") % cel, self.nazwa)
        if reczne and not getattr(app, "restart_active", False):
            app._exec_pending(manual=True)
        return przyjete

    def _proby(self, nazwa, cel):
        return list(self.cfg.get("proby", {}).get("%s|%s" % (nazwa, cel), []))

    def _warunki_managera(self):
        if self.zamrazarka is None:
            return False, "brak_nazwy"
        if self.zamrazarka.aktywna():
            return False, "recovery"
        api = self.zamrazarka.api
        nazwa = self.zamrazarka.nazwa_exe
        if not nazwa:
            return False, "brak_nazwy"
        try:
            pidy = self.zamrazarka.wybierz_managera()
        except OSError as exc:
            reason = str(exc)
            return False, reason if reason in ("brak_procesu", "brak_nazwy", "niejednoznaczny_manager") else "lista:%s" % exc
        if not pidy:
            return False, "brak_procesu"
        for pid in pidy:
            try:
                api.dostep_wstrzymania(pid)
            except OSError as exc:
                return False, "dostep:%s" % exc
        return True, ""

    def _opis_zamrozenia(self, powod):
        powod = str(powod or "")
        rodzaj, _, szczegol = powod.partition(":")
        opisy = {
            "brak_nazwy": t("nie ustawiono procesu managera", "no manager process is set"),
            "brak_procesu": t("manager %s nie działa — po DoExit nikt nie podniósłby serwera",
                              "the manager %s is not running — nobody would start the server after DoExit")
            % (self.zamrazarka.nazwa_exe if self.zamrazarka else "?"),
            "dostep": t("brak dostępu do procesu managera (uruchom refresher jako administrator): %s",
                        "no access to the manager process (run the refresher as administrator): %s")
            % szczegol,
            "lista": t("nie udało się odczytać listy procesów: %s", "could not read the process list: %s")
            % szczegol,
            "zamrozenie": t("nie udało się wstrzymać managera: %s", "could not pause the manager: %s")
            % szczegol,
            "dzierzawa": t("nie udało się zapisać pliku dzierżawy: %s", "could not write the lease file: %s")
            % szczegol,
            "juz": t("manager jest już wstrzymany", "the manager is already paused"),
            "recovery": t("pozostała niedokończona operacja; sprawdź dziennik odzyskiwania",
                          "an unfinished operation remains; inspect the recovery journal"),
            "niejednoznaczny_manager": t("działa więcej niż jeden manager; ustaw pełną ścieżkę EXE",
                                        "multiple managers are running; set the full EXE path"),
            "straznik": t("strażnik nie potwierdził gotowości: %s",
                          "guardian readiness was not confirmed: %s") % szczegol,
        }
        return opisy.get(rodzaj, powod)

    # -- wywołania z kolejki (wątek UI) -------------------------------------------------
    def aktualizuj_bez_serwera(self, nazwa, reczne=False):
        """Mapa, której serwer nie działa (OFFLINE/CRASH albo długo nie GOTOWA):
        bez DoExit i bez kolejki — wstrzymany manager, kopiowanie, wznowienie.
        Manager po wznowieniu podnosi serwer sam, jak po każdym krachu."""
        if self._zadanie or not self._cel():
            return False
        app = self.core.application()
        if getattr(app, "restart_active", False) or getattr(app, "watch_active", False):
            return False                 # trwa kolejka — przy następnym sprawdzeniu
        automat = getattr(app, "auto_rcon", None)
        if not reczne and automat is not None and not automat.get():
            # Jak zlecenia w kolejce: przy wyłączonym automacie RCON nic samo nie rusza.
            if self._raz(("automat", nazwa, self._cel())):
                self.core.log(t("[SERWER] %s: automat RCON wyłączony — aktualizacja tylko ręcznie "
                                "(panel UPDATE SERWERA).",
                                "[SERVER] %s: RCON automation is off — update only manually "
                                "(the SERVER UPDATE panel).") % nazwa)
            return False
        info = self.lokalne.get(nazwa) or {}
        status = info.get("status", "?")
        port = str(info.get("port") or "")
        dziala, pewne = self._serwer_dziala({"katalog": info.get("katalog") or "",
                                            "pid": self._pid_portu.get(port) if port else None})
        if dziala or not pewne:
            # Proces serwera jest (np. manager właśnie go podnosi) — managera nie
            # wstrzymujemy; aktualizacja pójdzie kolejką, gdy mapa będzie GOTOWA.
            if self._raz(("dziala", nazwa, status)):
                self.core.log(t("[SERWER] %s: stan %s, ale proces serwera działa — aktualizacja, "
                                "gdy mapa będzie GOTOWA albo wyłączona.",
                                "[SERVER] %s: state %s, but the server process is running — the "
                                "update goes ahead once the map is READY or shut down.")
                              % (nazwa, status))
            return False
        if not self._manager_gotowy(reczne) or not self._dozwolone([nazwa], reczne):
            return False
        kod, powod = self._przygotuj(nazwa, "bez_serwera")
        if kod != "ok":
            self.core.log(t("[SERWER] %s: bez aktualizacji — %s", "[SERVER] %s: no update — %s")
                          % (nazwa, powod))
            return False
        self.core.log(t("[SERWER] %s: serwer nie działa albo nie wstaje (stan: %s) — aktualizacja "
                        "bez DoExit.",
                        "[SERVER] %s: the server is down or does not come up (state: %s) — update "
                        "without DoExit.") % (nazwa, status), "st_wait")
        z = self._zadanie
        if not self._rozpocznij_instalacje(z):
            return False
        self._wskaznik()
        self.core.run_async(self._aktualizuj_praca, dict(z), dict(self.cfg))
        return True

    def blokada_kolejki(self):
        """Dla rdzenia: przy wstrzymanym managerze nowa kolejka nie rusza —
        DoExit innej mapy czekałby na wznowienie managera."""
        z = self._zadanie
        if z:
            return t("trwa aktualizacja serwera mapy %s (manager wstrzymany)",
                     "the server of map %s is being updated (manager paused)") % z["mapa"]
        if self.zamrazarka is not None and self.zamrazarka.aktywna():
            return t("niedokończone odzyskiwanie managera — UPDATE SERWERA → PONÓW ODZYSKIWANIE",
                     "manager recovery is unfinished — SERVER UPDATE → RETRY RECOVERY")
        return None

    def _pokaz_alarm(self):
        try:
            with open(self.zamrazarka.sciezka + ".alarm.json", encoding="utf-8") as fh:
                tekst = "; ".join(str(x) for x in json.load(fh).get("bledy", []))
        except FileNotFoundError:
            tekst = ""
        except (OSError, ValueError, AttributeError):
            return
        if tekst != self._alarm_tekst:
            self._alarm_tekst = tekst
            if tekst:
                self.core.warn(t("[SERWER] Strażnik: %s", "[SERVER] Guardian: %s") % tekst)
            self._odswiez_panel()

    def ponow_odzyskiwanie(self, reczne=True):
        if self._zadanie or self._recovery_praca or not self.zamrazarka:
            if reczne:
                self.core.warn(t("[SERWER] Trwa operacja — odzyskiwanie poczeka na jej zakończenie.",
                                 "[SERVER] An operation is running — recovery must wait for it to finish."))
            return False
        if reczne:
            self._recovery_proby = 0
        self._recovery_praca = True
        self._recovery_proby += 1
        self._recovery_nastepna = time.time() + 30
        def rob():
            wynik = self.zamrazarka.ponow_po_zakonczeniu_pracy()
            def koniec():
                self._recovery_praca = False
                if wynik.zablokowane:
                    self.core.warn(t("[SERWER] Odzyskiwanie nadal zablokowane: %s. "
                                     "Po usunięciu przyczyny wybierz PONÓW ODZYSKIWANIE. "
                                     "Nie usuwaj dzierżawy ani kopii plików.",
                                     "[SERVER] Recovery is still blocked: %s. "
                                     "After fixing the cause, choose RETRY RECOVERY. "
                                     "Do not delete the lease or backup files.") % ("; ".join(wynik.bledy) or wynik.stan))
                else:
                    self._recovery_proby = 0
                    self.core.log(t("[SERWER] Odzyskiwanie zakończone — blokada kolejki zwolniona.",
                                    "[SERVER] Recovery completed — queue unblocked."))
                self._pokaz_alarm()
                self._wskaznik()
                self._odswiez_panel()
            self.core.post_ui(koniec)
        self.core.run_async(rob)
        return True

    # -- przejścia fazy (bezpieczne z każdego wątku) -------------------------------------
    def _anuluj_zamrozenie(self, z):
        """Wznów managera, jeśli zadanie z nadal czeka na DoExit. None = nie było czego."""
        with self._stan:
            if z is None or self._zadanie is not z or z.get("faza") != "zamrozony":
                return None
            z["faza"] = "anulowany"
        return self.zamrazarka.odmroz()

    def _rozpocznij_instalacje(self, z):
        """zamrozony → instalacja. False = za późno (np. bezpiecznik już wznowił managera)."""
        with self._stan:
            if z is None or self._zadanie is not z or z.get("faza") != "zamrozony":
                return False
            z["faza"] = "instalacja"
        return True

    def _bez_instalacji(self, z):
        """Bezpiecznik: DoExit/kopiowanie nie ruszyło w ZAMROZENIE_BEZ_DOEXIT_S. Działa
        także z timera, gdy wątek okna stoi (np. zaznaczenie w konsoli) — manager
        nie może czekać na okno programu."""
        bledy = self._anuluj_zamrozenie(z)
        if bledy is None:
            return

        def koniec():
            if self._zadanie is z:
                self._zadanie = None
            self.core.warn(t("[SERWER] %s: brak DoExit przez %d s — bez kopiowania; wznowienie managera: %s.",
                             "[SERVER] %s: no DoExit for %d s — no copying; manager resume: %s.") %
                           (z.get("mapa"), ZAMROZENIE_BEZ_DOEXIT_S,
                            t("niepotwierdzone", "unconfirmed") if bledy else "OK"))
            self._ostrzez_o_wznowieniu(bledy)
            self._wskaznik()
        self.core.post_ui(koniec)

    def przed_doexit(self, nazwa):
        if not self.enabled:
            return "blad", t("plugin aktualizacji serwera jest wyłączony (OFF)",
                             "the server update plugin is OFF")
        return self._przygotuj(nazwa, "doexit")

    def _przygotuj(self, nazwa, tryb):
        """Sprawdź, czy mapa nadal potrzebuje nowych plików i czy da się je podmienić,
        potem wstrzymaj managera. ("ok" | "zbedne" | "blad", powód)."""
        if self._zadanie:
            return "blad", t("trwa aktualizacja mapy %s", "map %s is being updated") % self._zadanie["mapa"]
        if self.manager_upd[0] == "wlaczony":
            return "blad", self.manager_upd[1]
        info = self.lokalne.get(nazwa) or {}
        katalog = info.get("katalog")
        if not katalog:
            return "blad", t("nie wiem, gdzie jest instalacja serwera", "the server install location is unknown")
        if os.path.exists(os.path.join(katalog, SYNC.KATALOG_KOPII)):
            return "blad", t("pozostała kopia poprzedniej operacji — najpierw odzyskiwanie. "
                             "Jeśli brak dziennika, zachowaj kopię i odtwórz kompletną instalację przed aktualizacją",
                             "a previous operation backup remains — recovery is required first. "
                             "If the journal is missing, retain the backup and restore a complete install before updating")
        if info.get("blad") == "wspolny":
            return "blad", t("ta sama instalacja serwera co %s", "the same server install as %s") % ", ".join(
                info.get("wspolny") or ())
        katalog_cache = self.cache.get("katalog")
        if self._cache_praca or not katalog_cache:
            return "blad", t("cache nie jest gotowy", "the cache is not ready")
        dane_cache, _ = S.czytaj_lokalny(katalog_cache)
        if not S.cache_gotowy(dane_cache):
            return "blad", t("cache nie jest gotowy", "the cache is not ready")
        dane, _ = S.czytaj_lokalny(katalog)
        if not dane:
            return "blad", t("nie da się odczytać %s", "%s cannot be read") % S.PLIK_MANIFESTU
        if int(dane["buildid"]) >= int(dane_cache["buildid"]):
            return "zbedne", t("serwer ma już build %d", "the server already has build %d") % dane["buildid"]
        w = self.plany.get(nazwa)
        if not w or w.get("cache_build") != dane_cache["buildid"] or w.get("cache") != katalog_cache:
            return "blad", t("brak aktualnego planu kopiowania — mapa wróci do kolejki po zaplanowaniu",
                             "no current copy plan — the map returns to the queue once planned")
        potrzeba = int(w["plan"]["bajty"]) + ZAPAS_MIEJSCA
        wolne = self._wolne_miejsce(katalog)
        if wolne is not None and wolne < potrzeba:
            return "blad", t("za mało miejsca na dysku mapy: potrzeba ok. %.1f GB, wolne %.1f GB",
                             "not enough disk space for the map: about %.1f GB needed, %.1f GB free") % (
                potrzeba / GB, wolne / GB)
        port = str(info.get("port") or "")
        pid = self._pid_portu.get(port) if port else None
        pid_start = None
        if pid:
            try:
                pid_start = self.zamrazarka.api.czas_startu(pid)
            except OSError:
                pid = None       # dalej sprawdzamy rzeczywiste ścieżki wszystkich procesów ASA
        ok, powod = self.zamrazarka.zamroz()
        if not ok:
            return "blad", self._opis_zamrozenia(powod)
        z = {"mapa": nazwa, "katalog": katalog, "cel": dane_cache["buildid"], "z": dane["buildid"],
             "pid": pid, "pid_start": pid_start, "faza": "zamrozony", "t0": time.time(), "tryb": tryb,
             "plan": w["plan"], "cache": katalog_cache}
        self._zadanie = z
        bezpiecznik = threading.Timer(ZAMROZENIE_BEZ_DOEXIT_S, self._bez_instalacji, args=(z,))
        bezpiecznik.daemon = True
        bezpiecznik.start()
        self.core.log(t("[SERWER] %s: manager wstrzymany na czas podmiany plików (build %d → %d, "
                        "%d plików, %.1f MB).",
                        "[SERVER] %s: manager paused while the files are replaced (build %d → %d, "
                        "%d files, %.1f MB).")
                      % (nazwa, dane["buildid"], dane_cache["buildid"], _pliki_do_kopii(w["plan"]),
                         w["plan"]["bajty"] / MB), "st_wait")
        self._wskaznik()
        return "ok", ""

    def po_doexit(self, nazwa):
        z = self._zadanie
        if not z or z["mapa"] != nazwa or not self._rozpocznij_instalacje(z):
            return
        self._wskaznik()
        self.core.run_async(self._aktualizuj_praca, dict(z), dict(self.cfg))

    def rozstrzygnij_doexit(self, nazwa, callback):
        """Brak odpowiedzi RCON: obserwuj proces, zachowując zamrożonego managera."""
        with self._stan:
            z = self._zadanie
            if not z or z["mapa"] != nazwa or z.get("faza") != "zamrozony":
                return False
            z["faza"] = "oczekiwanie_doexit"
        self.core.warn(t("[SERWER] %s: wynik DoExit niepewny. Sprawdzam wyjście procesu do %d s; nie wysyłam ponownie.",
                         "[SERVER] %s: DoExit outcome uncertain. Watching process exit for up to %d s; not resending.") %
                       (nazwa, CZEKAJ_NA_WYJSCIE_S))
        self.core.run_async(self._obserwuj_doexit, z, callback)
        return True

    def _obserwuj_doexit(self, z, callback, spij=time.sleep):
        blad = t("nie potwierdzono wyjścia procesu po DoExit", "process exit after DoExit was not confirmed")
        try:
            koniec = time.monotonic() + CZEKAJ_NA_WYJSCIE_S
            while True:
                dziala, pewne = self._serwer_dziala(z)
                if not dziala and pewne:
                    blad = None
                    break
                if time.monotonic() >= koniec:
                    break
                spij(1.0)
        except Exception as exc:
            blad = str(exc)
        def koniec_ui():
            with self._stan:
                if self._zadanie is not z or z.get("faza") != "oczekiwanie_doexit":
                    return
                z["faza"] = "zamrozony"
                z["t0"] = time.time()
            callback(blad)
        self.core.post_ui(koniec_ui)

    def doexit_nieudany(self, nazwa):
        z = self._zadanie
        if not z or z["mapa"] != nazwa:
            return
        bledy = self._anuluj_zamrozenie(z)
        if bledy is None and z.get("faza") == "instalacja":
            return                    # kopiowanie już trwa — jego wątek sam wznowi managera
        self._zadanie = None
        self.cfg.setdefault("proby", {}).setdefault("%s|%s" % (nazwa, z["cel"]), []).append(time.time())
        self._zapisz_cfg()
        self.core.warn(t("[SERWER] %s: DoExit nie przeszedł — bez kopiowania; wznowienie managera: %s.",
                         "[SERVER] %s: DoExit failed — no copying; manager resume: %s.") %
                       (nazwa, t("niepotwierdzone", "unconfirmed") if bledy else "OK"))
        self._ostrzez_o_wznowieniu(bledy or [])
        self._wskaznik()

    # -- podmiana plików (wątek w tle) ---------------------------------------------------
    def _serwer_dziala(self, z):
        """(działa, pewne). Niepewność = czekamy dalej (bezpieczniej)."""
        api = self.zamrazarka.api
        try:
            if z.get("pid") and z.get("pid_start") is not None and api.zyje(z["pid"], z["pid_start"]):
                return True, True
            prefiks = os.path.normcase(os.path.join(z["katalog"], ""))
            for pid in api.procesy(EXE_SERWERA):
                try:
                    sciezka = os.path.normcase(api.sciezka_exe(pid))
                except OSError:
                    return True, False
                if sciezka.startswith(prefiks):
                    return True, True
            return False, True
        except OSError:
            return True, False

    def _aktualizuj_praca(self, z, cfg, spij=time.sleep):
        wynik = {"ok": False, "powod": "", "dane": None, "wznowienie": [], "licz": True,
                 "stat": {}, "czas": 0.0}
        zamrazarka = self.zamrazarka          # ta, która wstrzymała managera
        safe_to_resume = True                # przed podmianą serwer ma oryginalne pliki
        try:
            koniec = time.time() + CZEKAJ_NA_WYJSCIE_S
            while True:
                dziala, pewne = self._serwer_dziala(z)
                if not dziala and pewne:
                    break
                if time.time() > koniec:
                    if z.get("tryb") == "bez_serwera":
                        # Serwer jednak działa (np. długi start) — to nie jest nieudana próba.
                        raise _Blad(t("serwer działa (stan był: nie GOTOWY) — nic nie kopiuję; "
                                      "aktualizacja pójdzie kolejką, gdy mapa będzie GOTOWA",
                                      "the server is running (state was: not READY) — nothing "
                                      "copied; the update goes through the queue once the map "
                                      "is READY"), licz=False)
                    raise _Blad(t("serwer nie wyłączył się w %d s — nic nie kopiuję",
                                  "the server did not shut down within %d s — nothing copied")
                                % CZEKAJ_NA_WYJSCIE_S)
                spij(1.0)
            spij(3.0)                          # system zwalnia uchwyty plików
            self.core.log(t("[SERWER] %s: kopiuję %d plików z cache (%.1f MB)…",
                            "[SERVER] %s: copying %d files from the cache (%.1f MB)…")
                          % (z["mapa"], _pliki_do_kopii(z["plan"]), z["plan"]["bajty"] / MB))
            zamrazarka.ustaw_kopie(SYNC.sciezka_dziennika(z["katalog"]))
            start = time.time()
            safe_to_resume = False
            synchronizacja = SYNC.wykonaj(z["plan"], z["cache"], z["katalog"],
                                         na_postep=self._postep_kopii(z["mapa"]), spij=spij,
                                         zachowaj_dziennik=True)
            ok, powod, stat = synchronizacja
            safe_to_resume = synchronizacja.safe_to_resume
            wynik["stat"], wynik["czas"] = stat, time.time() - start
            dane, _ = S.czytaj_lokalny(z["katalog"])
            wynik["dane"] = dane
            if not ok:
                raise _Blad(powod)
            if not dane or dane["buildid"] != z["cel"] or dane.get("stan") != S.STAN_ZAINSTALOWANA:
                raise _Blad(t("po kopiowaniu appmanifest mapy ma build %s, oczekiwany %d",
                              "after copying the map appmanifest has build %s, expected %d") % (
                    (dane or {}).get("buildid", "?"), z["cel"]))
            wynik["ok"] = True
        except _Blad as exc:
            wynik["powod"] = str(exc)
            wynik["licz"] = exc.licz
        except Exception as exc:
            wynik["powod"] = t("błąd: %s", "error: %s") % exc
        finally:
            if safe_to_resume:
                try:
                    zamrazarka.potwierdz_bezpieczne()
                    wynik["wznowienie"] = zamrazarka.odmroz()
                except Exception as exc:
                    wynik["wznowienie"] = [str(exc)]
            else:
                wynik["wznowienie"] = [t("pliki nie mają potwierdzonego spójnego stanu; manager pozostaje wstrzymany",
                                            "file consistency is unconfirmed; the manager remains paused")]
            wynik["recovery_required"] = bool(wynik["wznowienie"])
            self.core.post_ui(lambda: self._po_aktualizacji(z, wynik))

    def _postep(self, co):
        stan = {"prog": -10.0}

        def na_linie(linia):
            p = S.postep(linia)
            if p and p[1] >= stan["prog"] + 10.0:
                stan["prog"] = p[1] - (p[1] % 10.0)
                self.core.log(t("[SERWER] %s: SteamCMD %s %.0f%%", "[SERVER] %s: SteamCMD %s %.0f%%")
                              % (co, p[0], p[1]))
        return na_linie

    def _postep_kopii(self, mapa):
        stan = {"prog": -25.0}

        def na_postep(i, razem, rel):
            procent = 100.0 * i / max(1, razem)
            if procent >= stan["prog"] + 25.0:
                stan["prog"] = procent - (procent % 25.0)
                self.core.log(t("[SERWER] %s: skopiowano %d/%d plików", "[SERVER] %s: copied %d/%d files")
                              % (mapa, i, razem))
        return na_postep

    def _po_aktualizacji(self, z, wynik):
        self._zadanie = None
        klucz = "%s|%s" % (z["mapa"], z["cel"])
        proby = self.cfg.setdefault("proby", {})
        self.plany.pop(z["mapa"], None)          # po każdej próbie plan liczony od nowa
        if wynik.get("recovery_required"):
            self.core.warn(t("[SERWER] %s: wymagane odzyskiwanie. Nie potwierdzono wznowienia managera. %s",
                             "[SERVER] %s: recovery required. Manager resume was not confirmed. %s") %
                           (z["mapa"], wynik.get("powod", "")))
        elif wynik["ok"]:
            proby.pop(klucz, None)
            self._nie_gotowa_od.pop(z["mapa"], None)
            stat = wynik.get("stat") or {}
            self.core.log(t("[SERWER] %s: zainstalowany build %d (skopiowano %d plików, %.1f MB, %d s). "
                            "Manager wznowiony — podniesie serwer sam.",
                            "[SERVER] %s: build %d installed (%d files copied, %.1f MB, %d s). Manager "
                            "resumed — it will start the server itself.")
                          % (z["mapa"], wynik["dane"]["buildid"], stat.get("skopiowane", 0),
                             stat.get("bajty", 0) / MB, int(wynik.get("czas") or 0)), "st_ok")
        elif not wynik.get("licz", True):
            # „Nie teraz”: licznik czasu „nie GOTOWA” liczy się od nowa, bez próby.
            self._nie_gotowa_od[z["mapa"]] = time.time()
            self.core.log(t("[SERWER] %s: %s. Manager wznowiony.", "[SERVER] %s: %s. Manager resumed.")
                          % (z["mapa"], wynik["powod"]))
        else:
            proby.setdefault(klucz, []).append(time.time())
            self.core.warn(t("[SERWER] %s: aktualizacja NIEUDANA — %s. Manager wznowiony (serwer wstanie "
                             "na dotychczasowym buildzie).",
                             "[SERVER] %s: update FAILED — %s. Manager resumed (the server starts on "
                             "its previous build).") % (z["mapa"], wynik["powod"]))
        # Zostaw tylko próby aktualnego celu — stare buildy nie mają znaczenia.
        aktualny = self._cel()
        for k in [k for k in proby if not k.endswith("|%s" % aktualny)]:
            proby.pop(k, None)
        self._zapisz_cfg()
        info = self.lokalne.get(z["mapa"])
        if info is not None and wynik.get("dane"):
            info["dane"] = wynik["dane"]
            info["blad"] = None
        self._ostrzez_o_wznowieniu(wynik.get("wznowienie"))
        self._wskaznik()
        self._odswiez_panel()

    def _ostrzez_o_wznowieniu(self, bledy):
        if bledy:
            self.core.warn(t("[SERWER] Wznowienie niepotwierdzone (%s). Program ponowi odzyskiwanie "
                             "do 10 razy co 30 s. Możesz też wybrać UPDATE SERWERA → PONÓW ODZYSKIWANIE "
                             "lub zamknąć i ponownie uruchomić Refresher. Zachowaj dzierżawę i kopię plików.",
                             "[SERVER] Resume unconfirmed (%s). Recovery will be retried up to 10 times every 30 s. "
                             "You can also choose SERVER UPDATE → RETRY RECOVERY or close and restart Refresher. "
                             "Keep the lease and backup files.") % "; ".join(bledy))

    # -- wskaźnik ---------------------------------------------------------------------------
    def _stan_map(self):
        aktualne, stare, bez = [], [], []
        cel = max(filter(None, (self._cel(), (self.zdalny or {}).get("buildid"))), default=None)
        for nazwa, info in sorted(self.lokalne.items()):
            if info.get("blad") or not info.get("dane"):
                bez.append(nazwa)
            elif cel and int(info["dane"]["buildid"]) < int(cel):
                stare.append(nazwa)
            else:
                aktualne.append(nazwa)
        return aktualne, stare, bez

    def _wskaznik(self):
        if self.core is None:
            return
        if self._zadanie:
            tekst, kolor = t("aktualizuję %s…", "updating %s…") % self._zadanie["mapa"], "#005a9c"
        elif self.zamrazarka is not None and self.zamrazarka.aktywna():
            tekst, kolor = t("STOP: wymagane odzyskiwanie", "STOP: recovery required"), "#b00020"
        elif not self.enabled:
            tekst, kolor = "OFF", "#555555"
        elif self.manager_upd[0] == "wlaczony":
            tekst, kolor = t("STOP: updater managera włączony", "STOP: manager updater is on"), "#b00020"
        elif self._cache_praca:
            tekst = t("cache: pobieram build %s…", "cache: downloading build %s…") % (
                self._cache_praca.get("cel") or "?")
            kolor = "#005a9c"
        elif self._sprawdzanie and not self.zdalny:
            tekst, kolor = t("sprawdzam Steam…", "checking Steam…"), "#005a9c"
        elif not self.zdalny:
            tekst = t("błąd: %s", "error: %s") % self.blad if self.blad else \
                t("ON — pierwsze sprawdzenie wkrótce", "ON — first check soon")
            kolor = "#b00020" if self.blad else "#555555"
        else:
            aktualne, stare, _ = self._stan_map()
            if stare:
                tekst = t("UPDATE %d: %s", "UPDATE %d: %s") % (self.zdalny["buildid"], ", ".join(stare))
                kolor = "#b06000"
            else:
                tekst = t("build %d — aktualne %d/%d", "build %d — up to date %d/%d") % (
                    self.zdalny["buildid"], len(aktualne), len(self.lokalne))
                kolor = "#207020"
        self.core.set_indicator(self.nazwa, tekst, kolor)

    # -- panel ------------------------------------------------------------------------------
    def _zamknij_okno(self):
        okno = self.window
        self.window = None
        self._widok = {}
        if okno is not None:
            try:
                okno.destroy()
            except Exception:
                pass

    def _okno_zyje(self):
        try:
            return self.window is not None and bool(self.window.winfo_exists())
        except Exception:
            return False

    def panel(self, parent):
        if self._okno_zyje():
            self.window.deiconify()
            self.window.lift()
            self._odswiez_panel()
            return self.window
        self._zamknij_okno()
        okno = tk.Toplevel(parent)
        self.window = okno
        okno.title(self.manager_name)
        okno.geometry("1000x720")
        okno.minsize(780, 560)
        okno.protocol("WM_DELETE_WINDOW", self._zamknij_okno)
        ramka = ttk.Frame(okno, padding=12)
        ramka.pack(fill="both", expand=True)
        ttk.Label(ramka, text=t("AKTUALIZACJA SERWERA ASA (CACHE + STEAMCMD)", "ASA SERVER UPDATE (CACHE + STEAMCMD)"),
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(ramka, wraplength=950, justify="left", foreground="#555555",
                  text=self.manager_description).pack(anchor="w", pady=(2, 8))
        stan = ttk.Label(ramka, text="", font=("TkDefaultFont", 10, "bold"), wraplength=950, justify="left")
        stan.pack(anchor="w")
        kolumny = ("mapa", "build", "stan", "katalog")
        drzewo = ttk.Treeview(ramka, columns=kolumny, show="headings", height=8)
        naglowki = {"mapa": t("Mapa", "Map"), "build": t("Build na dysku", "Build on disk"),
                    "stan": t("Stan", "Status"), "katalog": t("Katalog", "Folder")}
        szer = {"mapa": 160, "build": 120, "stan": 260, "katalog": 400}
        for k in kolumny:
            drzewo.heading(k, text=naglowki[k])
            drzewo.column(k, width=szer[k], anchor="w")
        drzewo.pack(fill="x", pady=(6, 6))

        ust = ttk.LabelFrame(ramka, text=t("Ustawienia", "Settings"), padding=8)
        ust.pack(fill="x")
        v_auto = tk.BooleanVar(value=bool(self.cfg.get("auto")))
        v_wal = tk.BooleanVar(value=bool(self.cfg.get("walidacja")))
        v_api = tk.BooleanVar(value=bool(self.cfg.get("api", True)))
        v_api_s = tk.StringVar(value=str(self.cfg.get("api_co_s")))
        v_steam = tk.StringVar(value=str(self.cfg.get("steamcmd_co_min")))
        v_cache = tk.StringVar(value=str(self.cfg.get("cache") or ""))
        v_man = tk.StringVar(value=str(self.cfg.get("manager") or ""))
        v_exe = tk.StringVar(value=str(self.cfg.get("steamcmd") or ""))
        ttk.Checkbutton(ust, variable=v_auto, text=t(
            "Instaluj automatycznie (gdy automat RCON jest włączony)",
            "Install automatically (when RCON automation is on)")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(ust, variable=v_wal, text=t(
            "Weryfikuj pliki cache przy pobieraniu (validate)",
            "Validate the cache files when downloading")).grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(ust, variable=v_api, text=t(
            "Sprawdzaj przez api.steamcmd.net (zewnętrzna usługa, nie Valve), co [s]:",
            "Check via api.steamcmd.net (a third-party service, not Valve), every [s]:")).grid(
            row=2, column=0, sticky="w")
        ttk.Entry(ust, textvariable=v_api_s, width=6).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(ust, text=t("Zapasowo SteamCMD co [min]:", "SteamCMD as a fallback every [min]:")).grid(
            row=3, column=0, sticky="w")
        ttk.Entry(ust, textvariable=v_steam, width=6).grid(row=3, column=1, sticky="w", padx=4)
        ttk.Label(ust, text=t("Folder cache (puste = obok serwerów):", "Cache folder (empty = next to the servers):")).grid(
            row=4, column=0, sticky="w")
        ttk.Entry(ust, textvariable=v_cache, width=60).grid(row=4, column=1, columnspan=2, sticky="w", padx=4)
        ttk.Label(ust, text=t("Manager: nazwa EXE lub pełna ścieżka:", "Manager: EXE name or full path:")).grid(
            row=5, column=0, sticky="w")
        ttk.Entry(ust, textvariable=v_man, width=60).grid(row=5, column=1, columnspan=2, sticky="w", padx=4)
        ttk.Label(ust, text=t("SteamCMD (puste = własny w katalogu refreshera):",
                              "SteamCMD (empty = own copy in the refresher folder):")).grid(row=6, column=0, sticky="w")
        ttk.Entry(ust, textvariable=v_exe, width=60).grid(row=6, column=1, columnspan=2, sticky="w", padx=4)
        ttk.Button(ust, text=t("ZAPISZ USTAWIENIA", "SAVE SETTINGS"),
                   command=lambda: self._zapisz_ustawienia(v_auto, v_wal, v_api, v_api_s, v_steam, v_cache,
                                                           v_man, v_exe)).grid(
            row=7, column=0, sticky="w", pady=(6, 0))

        rzad = ttk.Frame(ramka)
        rzad.pack(fill="x", pady=(8, 4))
        ttk.Button(rzad, text=t("SPRAWDŹ TERAZ", "CHECK NOW"),
                   command=self._sprawdz_teraz).pack(side="left")
        ttk.Button(rzad, text=t("AKTUALIZUJ TERAZ", "UPDATE NOW"),
                   command=self._aktualizuj_teraz).pack(side="left", padx=6)
        ttk.Button(rzad, text=t("ZAMKNIJ", "CLOSE"), command=self._zamknij_okno).pack(side="right")
        ttk.Button(rzad, text=t("PONÓW ODZYSKIWANIE", "RETRY RECOVERY"),
                   command=self.ponow_odzyskiwanie).pack(side="left", padx=5)
        ttk.Label(ramka, text=t("Ostatnie wyjście SteamCMD:", "Last SteamCMD output:")).pack(anchor="w")
        wyj = tk.Text(ramka, height=10, wrap="none", borderwidth=0)
        wyj.pack(fill="both", expand=True)
        self._widok = {"stan": stan, "drzewo": drzewo, "wyjscie": wyj}
        self._odswiez_panel()
        return okno

    def _zapisz_ustawienia(self, v_auto, v_wal, v_api, v_api_s, v_steam, v_cache, v_man, v_exe):
        api_s = v_api_s.get().strip()
        steam = v_steam.get().strip()
        if not api_s.isdecimal() or int(api_s) < API_MIN_S:
            messagebox.showerror(self.manager_name, t("Odstęp API: liczba sekund, co najmniej %d.",
                                                      "API interval: whole seconds, at least %d.") % API_MIN_S,
                                 parent=self.window)
            return
        if not steam.isdecimal() or int(steam) < 5:
            messagebox.showerror(self.manager_name, t("Odstęp SteamCMD: liczba minut, co najmniej 5.",
                                                      "SteamCMD interval: whole minutes, at least 5."),
                                 parent=self.window)
            return
        cache = v_cache.get().strip()
        if cache and not os.path.isabs(cache):
            messagebox.showerror(self.manager_name, t("Folder cache: pełna ścieżka (np. C:\\ARKservers\\CACHE).",
                                                      "Cache folder: a full path (e.g. C:\\ARKservers\\CACHE)."),
                                 parent=self.window)
            return
        self.cfg.update(auto=bool(v_auto.get()), walidacja=bool(v_wal.get()), api=bool(v_api.get()),
                        api_co_s=int(api_s), steamcmd_co_min=int(steam), cache=cache,
                        manager=v_man.get().strip(), steamcmd=v_exe.get().strip())
        if not self._zadanie:
            self.zamrazarka = self._nowa_zamrazarka()
        self._zapisz_cfg()
        teraz = time.time()
        self._nastepne_api = min(self._nastepne_api, teraz + self._api_co_s())
        self._nastepne_steamcmd = min(self._nastepne_steamcmd, teraz + self._steamcmd_co_s())
        self.plany.clear()
        self.core.log(t("[SERWER] Ustawienia zapisane.", "[SERVER] Settings saved."))
        self._odswiez_panel()

    def _sprawdz_teraz(self):
        if not self.sprawdz(reczne=True):
            messagebox.showinfo(self.manager_name, t("Trwa sprawdzanie albo aktualizacja — wynik w dzienniku.",
                                                     "A check or an update is in progress — see the log."),
                                parent=self.window)

    def _aktualizuj_teraz(self):
        """Świeże sprawdzenie i aktualizacja od razu (wynik w dzienniku)."""
        if not self.enabled:
            messagebox.showinfo(self.manager_name, t("Plugin jest wyłączony (OFF).", "The plugin is OFF."),
                                parent=self.window)
            return
        if not self.sprawdz(reczne=True, wymus=True):
            messagebox.showinfo(self.manager_name, t("Trwa sprawdzanie albo aktualizacja — wynik w dzienniku.",
                                                     "A check or an update is in progress — see the log."),
                                parent=self.window)

    def _opis_stanu(self):
        czesci = []
        if self.zdalny:
            czesci.append(t("Steam: build %d (manifest %s, źródło: %s, %s).",
                            "Steam: build %d (manifest %s, source: %s, %s).") % (
                self.zdalny["buildid"], self.zdalny.get("manifest") or "?", self.zrodlo,
                time.strftime("%H:%M:%S", time.localtime(self.ostatnie))))
        elif self.blad:
            czesci.append(t("Steam: nie wiadomo — %s.", "Steam: unknown — %s.") % self.blad)
        else:
            czesci.append(t("Steam: jeszcze nie sprawdzano.", "Steam: not checked yet."))
        if self.api_awaria:
            czesci.append(t("api.steamcmd.net nie odpowiada (%s) — zapasowo SteamCMD.",
                            "api.steamcmd.net does not answer (%s) — SteamCMD as a fallback.") % (
                self.api_blad or "?"))
        stan, opis, _ = self.manager_upd
        if stan == "wlaczony":
            czesci.append(t("STOP — %s: wyłącz go w Update Settings managera.",
                            "STOP — %s: turn it off in the manager's Update Settings.") % opis)
        elif stan == "nieznany":
            czesci.append((t("Updater managera: nie wiem (%s).", "Manager updater: unknown (%s).") % opis)
                          if opis else t("Updater managera: brak danych.", "Manager updater: no data."))
        if self._zadanie:
            czesci.append(t("Trwa: %s (build %d → %d).", "In progress: %s (build %d → %d).") % (
                self._zadanie["mapa"], self._zadanie["z"], self._zadanie["cel"]))
        if self._alarm_tekst:
            czesci.append(t("Strażnik: %s", "Guardian: %s") % self._alarm_tekst)
        return "  ".join(czesci)

    def _odswiez_panel(self):
        if not self._okno_zyje() or not self._widok:
            return
        self._widok["stan"].configure(text=self._opis_stanu())
        drzewo = self._widok["drzewo"]
        for iid in drzewo.get_children():
            drzewo.delete(iid)
        dane_cache = self.cache.get("dane") or {}
        if self.cache.get("konflikt"):
            stan_cache = self.cache["konflikt"]
        elif self._cache_praca:
            stan_cache = t("pobieram build %s…", "downloading build %s…") % (self._cache_praca.get("cel") or "?")
        elif S.cache_gotowy(dane_cache):
            stan_cache = t("gotowy", "ready")
        elif self._cache_porazki:
            stan_cache = t("pobieranie nieudane — następna próba %s", "download failed — next attempt %s") % (
                time.strftime("%H:%M", time.localtime(self._cache_nastepna)))
        else:
            stan_cache = t("pusty — zostanie pobrany", "empty — will be downloaded")
        drzewo.insert("", "end", values=(t("CACHE", "CACHE"), dane_cache.get("buildid", "—"), stan_cache,
                                         self.cache.get("katalog") or "—"))
        cel = self._cel()
        for nazwa, info in sorted(self.lokalne.items()):
            dane = info.get("dane") or {}
            if info.get("blad") == "katalog":
                stan = t("nieznany katalog serwera", "unknown server folder")
            elif info.get("blad") == "wspolny":
                stan = t("wspólna instalacja z: %s", "shared install with: %s") % ", ".join(
                    info.get("wspolny") or ())
            elif info.get("blad"):
                stan = t("brak appmanifest (nie SteamCMD)", "no appmanifest (not SteamCMD)")
            elif not cel and not self.zdalny:
                stan = "?"
            elif cel and int(dane.get("buildid") or 0) < int(cel):
                plan = self.plany.get(nazwa)
                stan = t("UPDATE → %d", "UPDATE → %d") % cel
                if plan and self._plan_aktualny(nazwa):
                    stan += t(" (%d plików, %.1f MB)", " (%d files, %.1f MB)") % (
                        _pliki_do_kopii(plan["plan"]), plan["plan"]["bajty"] / MB)
            elif self.zdalny and int(dane.get("buildid") or 0) < int(self.zdalny["buildid"]):
                stan = t("czeka na cache (Steam: %d)", "waits for the cache (Steam: %d)") % self.zdalny["buildid"]
            else:
                stan = t("aktualny", "up to date")
            drzewo.insert("", "end", values=(nazwa, dane.get("buildid", "—"), stan, info.get("katalog") or "—"))
        wyj = self._widok["wyjscie"]
        wyj.configure(state="normal")
        wyj.delete("1.0", "end")
        wyj.insert("1.0", self.wyjscie or "—")
        wyj.configure(state="disabled")
