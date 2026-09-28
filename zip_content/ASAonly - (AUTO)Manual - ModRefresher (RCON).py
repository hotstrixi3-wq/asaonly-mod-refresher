#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASAonly - Manual Mod Refresher   [V3.86.7]
3.86.7: powrót przez RCON związany z nowym PID i czasem startu, bez wymogu READY w logu.
3.86.6: świeży znacznik READY, alarmy po zmianie nazwy mapy i limit/rotacja PADY.
3.86.5: powrót po crashu przy DoExit, bazowy crashstack, alarmy RCON i poprawki okna.
3.86.4: kopie dowodów padu, PID+czas startu w PAD4, odczekanie po wykryciu
wersji moda i trwały alarm braku powrotu. WIEDZA_O_PROGRAMIE/V3.86.4-RUNDA-I-PADY.md.
3.86.3: odzyskiwanie podmiany plików po recenzji, ponowienia strażnika,
obserwacja procesu po niepewnym DoExit. Szczegóły: WIEDZA_O_PROGRAMIE/V3.86.3-RECOVERY.md.
3.86.2: PO ANALIZIE LOGOW Z 26.09 (prosba usera). (1) Dziennik zdarzen takze
w pliku WIEDZA_O_PROGRAMIE/dziennik-zdarzen.txt (asaonly/dziennik_plik.py,
osobny watek, data na starcie i przy zmianie dnia, rotacja 5 x 5 MB); napis
"zapis tez w asa_debug.log" byl nieprawdziwy - tam ida tylko ukryte bledy.
(2) Planowy restart nie wyglada jak awaria: po DoExit z kolejki monitor pisze
"zamkniety po DoExit" zamiast "PAD ... zdechl cicho", OFFLINE nie na czerwono,
[CPU] w dzienniku dopiero przy READY (mapa_w_restarcie, TabSnapshot.restart).
(3) Okno cmd bez zatrzyman: wylaczony tryb szybkiej edycji w oknie programu
(SetConsoleMode), przywracany przy zamknieciu. WERSJA_PROGRAMU = jedna stala.
3.86.1: PIERWSZE URUCHOMIENIE 3.86 NA ZYWO (26.09.2026). Swiezo pobrany SteamCMD
za pierwszym razem skonczyl sie "Missing configuration" (pusta appcache, prosba
o dane serwera ASA sekunde przed porazka); druga proba po 5 min pobrala caly
build. Teraz "Missing configuration" = ponowienie od razu (do 2 razy, co 10 s),
zamiast 5 min przerwy. Linia "Failed installing AppID ..." z content_log jest
rozpoznawana (3.86.0 pisalo "brak wpisow"), a liczba plikow przed i w trakcie
kopiowania liczy appmanifest jak licznik (bylo "39 plikow", potem "40/40").
Runda 26.09: Extinction, Genesis 1, Ragnarok 25489097 -> 25535041, po 40 plikow
(11238.7 MB) w 9-10 s, manager wstrzymany najwyzej ok. 40 s na mape.
3.86.0: AKTUALIZACJA SERWERA PRZEZ WLASNY CACHE (plugin 88 2.0.0,
asaonly/synchronizacja.py). 25.09.2026 V3.85 dala 9 restartow bez aktualizacji:
SteamCMD refreshera uruchamiany na mapie nie mial manifestu buildu z mapy
(mapy instalowal SteamCMD managera), Steam odmawial go anonimowo ("Access
Denied"), a plugin po DoExit i tak wznawial managera. Teraz: api.steamcmd.net
co minute (zapasowo SteamCMD co 5 min), nowy build od razu do cache obok
serwerow (serwery dzialaja, blad = zaden restart, powod z content_log.txt),
plan roznic przed DoExit, kopiowanie tylko zmienionych plikow z kopia
zapasowa i wycofaniem (takze po awarii - robi to straznik), appmanifest na
koncu. Wlaczony updater managera = plugin nic nie robi i mowi dlaczego.
3.85.4: "O programie" wymienia obu autorow kodu: Arena.ai Agent Mode (do 3.80.35)
i Claude (Anthropic, od 3.81).
3.85.3: PORZADEK W GORNEJ CZESCI OKNA. Przyciski pluginow maja wlasny pasek
"Pluginy" (z Managerem Pluginow), zawijany w waskim oknie - wczesniej jeden
rzad wypychal pluginy, "Wykonaj zalegle aktualizacje" i "Anuluj procedure"
poza okno. Te dwa przyciski sa teraz w ramce Status obok "Sprawdz mody
teraz". "Zapisz tab" stoi pod polami mapy (zapisuje tylko te mape) ze
znacznikiem niezapisanych zmian tej mapy. Pole klucza API zweza sie zamiast
chowac "Zapisz klucz".
3.85.2: OKNO NIE STAJE PO KLIKNIECIU W KONSOLE. Dziennik drukowal watek okna;
zaznaczenie w konsoli Windows (QuickEdit) wstrzymuje kazdy zapis do niej, wiec
stawalo cale okno ("Brak odpowiedzi"), automat i kolejka. Teraz konsole pisze
osobny watek (asaonly/konsola.py), bledy zdarzen okna ida do dziennika
i asa_debug.log. Plugin 88: bezpiecznik "brak DoExit" dziala z timera, nie
z watku okna - wstrzymany manager wraca po 300 s nawet przy stojacym oknie.
3.85.1: POPRAWKA PLUGINU 88 po pierwszym uruchomieniu na Windows. Host pluginow
dla pluginu z prepare() wola activate(), nie start() - plugin 88 nie mial
activate(), wiec przy starcie nie wznawial managera zostawionego po awarii,
a pierwsze sprawdzenie Steama szlo od razu zamiast po minucie. Zmiana jezyka
w trakcie instalacji podmieniala zamrazarke (manager zostalby wstrzymany).
Odzyskanie po awarii nie rusza dzierzawy zywego refreshera.
3.85: AKTUALIZACJA SAMEGO SERWERA ASA PRZEZ STEAMCMD (plugin 88,
asaonly/steam_serwer.py, asaonly/zamrazanie.py). Updater managera (metoda CDN)
potrafi mowic "aktualny", choc Steam ma nowy build - plugin pyta Steama sam
(SteamCMD, bez starego appinfo.vdf), porownuje z appmanifest kazdej mapy i
starsza mape daje do zwyklej kolejki (zlecenie restartu: ogloszenia, pusta =
od razu, jeden start naraz). Tuz przed DoExit wstrzymuje managera (inaczej
podnioslby serwer w trakcie instalacji), SteamCMD instaluje, plugin sprawdza
appmanifest i wznawia managera - manager sam podnosi zaktualizowany serwer.
Dzierzawa + osobny straznik: manager nie zostaje wstrzymany po awarii.
Rdzen: zlecenia restartu od pluginow (zlec_restart / odwolaj_zlecenia,
przed_doexit / po_doexit / doexit_nieudany); start z praca pluginu nie jest
zapisywany jako czas startu serwera.
3.84: PELNA WERSJA ANGIELSKA I PORZADKI. Teksty spoza slownika TR stoja w kodzie
w obu jezykach: t("polski", "English") z asaonly/jezyk.py; jezyk ustawia App.lang.
Po EN caly program (okna, 11 pluginow, Manager, kolejka, dziennik) mowi po
angielsku - pilnuje tego tests/test_i18n.py. Usuniety martwy kod po przenosinach
3.75-3.83 (import_tab_from_file, RconLineRow, stare API koordynatora, 40 kluczy
TR, nieuzywane importy). Drobne poprawki: CPU (cel affinity spoza komputera nie
jest juz "ZGODNE", panel zamkniety w trakcie testu), dysk (skan po zamknieciu
okna), RCON (nieudane wstawienie do kolejki nie blokuje mapy).
3.83: JEDEN PLUGIN "Konfiguracje" (80_konfiguracje.py) zamiast Importera (80)
i Backup/Przywracanie (81): jeden panel, jeden ON/OFF, przejete zapisane wybory.
Host pomija stare pliki, jesli zostaly w PLUGINY (atrybut `zastepuje`). Po
przywroceniu backupu program zamyka sie BEZ zapisu (_zamknij_teraz) - wczesniej
zwykle zamkniecie nadpisywalo przywrocone pliki starym stanem z pamieci.
3.82: KONTROLA CZASU (plugin 87, asaonly/kontrola.py). Sprawdza reczne ustawienia
czasu w harmonogramach RCON tymi samymi regulami co procedura: BLAD = mapa, ktora
procedura pominie; UWAGA = czekanie bez komunikatu, komunikat "za 15 min" niezgodny
z czasem do DoExit, linie po DoExit, slad starego wspolnego zegara. Podglad fali
restartow liczony prawdziwym planista kolejki. Tylko odczyt. Przy okazji: czas
i port z cyframi typu "2" w indeksie gornym nie wywracaja juz procedury.
3.81: AKSJOMAT AKCELERATORA + INTELIGENTNA KOLEJKA. Update moda i tak wejdzie
przy najblizszym starcie serwera (serwer sam podnosi mody), wiec: jedna mapa
nigdy nie zatrzymuje reszty kolejki; zadnych okienek na sciezce automatycznej;
przerwana procedura po restarcie refreshera jest porzucana, nie blokuje
automatu. Kolejka (asaonly/kolejka.py): najwyzej JEDEN start naraz (dysk),
ogloszenia rownolegle i "na styk" wg zmierzonych czasow startu, pusta mapa
(ListPlayers) = bez ogloszen, niepewnosc = gracze sa, mapa ktora wstala sama
z nowymi modami wypada z kolejki. Czasy linii RCON sa LOKALNE dla mapy.
Poprawki: prawdziwy format LoadGameMods ASA, "Log file open" zeruje dowody
wersji starego procesu, monitor bez bledu "free variable 'e'", koniec kolejki
zapisuje config, plugin 84 na odczycie wspoldzielonym, testy nie zasmiecaja
asa_debug.log ani CONFIG_PROGRAM, testy przez prawdziwa sciezke produkcyjna
(PluginHost + RCON na gniazdach) + e2e prawdziwej aplikacji.
3.75-3.80.35: podzial na pakiet asaonly/ i PLUGINY/, wersje -windowsserver,
library.json CFCore, pomijanie pustych wierszy RCON (historia: README.txt).
3.74: "Biblioteka wiedzy" - do zipa wchodzi PRZYKLAD harmonogramu
restartow klastra + swiezy raport z testow; logika kodu bez zmian.
3.73: netstat po polsku (NASLUCHUJACE - PAD-y dzialaja u polskich adminow),
cf_delay naprawde dziala (odstep miedzy chunkami), DL_STUCK 20 min,
kafelki [SONDA]/[WISI!], TR auto_on_log prawdziwe (audyt kozaka 2 rol).
3.72: testy od strony uzytkownika - marsz przyciskowy (debug25, 54 checki):
kazdy przycisk kilkukrotnie, rowniez anulowania/duplikaty/bledne dane;
zero bledow Tk w calym marszu. Fix 3.71.1 w zestawie.
3.71.1: FIX zmiana jezyka / nowa mapa = crash monitora (brak _wisi_st na
tabach urodzonych po starcie); snapshot tabow w watku; snapshoty zapisu po EN/PL.
3.71: monitor procesow+portow (10 s), pady/WISI/sondy RCON, modul padu CF (sonda
1 mod, rytm 1/3/15), dziennik stanu modow (rotacja 15x10 KB), samorestarty, nowe
serwery, auto-kolejna tura po GOTOWY (karencja 60 s) + naprawy z 3 audytow AI.
==============================

Monitor aktualizacji modow ARK: Survival Ascended przez CurseForge API
z planowanymi komendami RCON, zaprojektowany do wspolpracy z ASA Dedicated
Manager (ASM).

Wersja, historia zmian i instrukcja:
    WIEDZA_O_PROGRAMIE/README - ASAonly - (AUTO)Manual - ModRefresher (RCON).txt
    WIEDZA_O_PROGRAMIE/V3.81-KOLEJKA-I-GRACZE.md
    WIEDZA_O_PROGRAMIE/V3.82-KONTROLA-CZASU.md
    WIEDZA_O_PROGRAMIE/V3.83-KONFIGURACJE-JEDEN-PLUGIN.md
    WIEDZA_O_PROGRAMIE/V3.84-ANGIELSKI-I-PORZADKI.md
    WIEDZA_O_PROGRAMIE/V3.85-AKTUALIZACJA-SERWERA-STEAMCMD.md
    WIEDZA_O_PROGRAMIE/V3.86-AKTUALIZACJA-SERWERA-PRZEZ-CACHE.md
    WIEDZA_O_PROGRAMIE/V3.86.2-DZIENNIK-W-PLIKU-I-SPOKOJNY-RESTART.md
Pomysl i koncepcja: Magus. Kod: Arena.ai (do 3.80.35), Claude (od 3.81).
"""

import copy
import json
import os
import glob
import queue
import re
import shutil
import sys
import threading
import tempfile
import time
import tkinter as tk
import traceback
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Stałe
# ---------------------------------------------------------------------------

# 3.45: Czytelne nazwy plikow - bez przedrostka, samoopisujace sie, z data
# i godzina zapisu (gg-mm-ss: dwukropek jest niedozwolony w nazwach na
# Windows). Kazdy zapis = nowy plik; rotacja trzyma BACKUP_KEEP najnowszych
# (to jednoczesnie system backupow). Stare nazwy migrowane automatycznie.
CONFIG_BASE = "CONFIG_PROGRAM - zapis"  # 3.63 (bylo: konfiguracja programu - zapis)
SECRETS_BASE = "CONFIG_SECRET_API - zapis"  # 3.63
TAB_CFG_BASE = "CONFIG_MAP - zapis"  # 3.63
TAB_SEC_BASE = "CONFIG_SECRET_RCON - zapis"  # 3.63
# 3.64: katalog glowny = TYLKO program i .bat; reszta w podkatalogach
CFG_DIR_NAME = "CONFIG_PROGRAM"
SEC_API_DIR_NAME = "CONFIG_SECRET_API"
KNOW_DIR_NAME = "WIEDZA_O_PROGRAMIE"
TAB_SEC_DIR_NAME = "CONFIG_SECRET_RCON"
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), CFG_DIR_NAME)
PROCEDURE_STATE_NAME = "PROCEDURE_RUN_STATE.json"
SECRET_API_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), SEC_API_DIR_NAME)
KNOW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), KNOW_DIR_NAME)
PLUGIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PLUGINY")
# V3.86.2: jedna stała wersji — „O programie” i wiersz startu w pliku dziennika.
WERSJA_PROGRAMU = "3.86.7"


def tab_cfg_base(name):
    """3.64: nazwa mapy w nazwie pliku konfiguracji - backup wyjety
    z katalogu mowi SAM, czyjej mapy jest."""
    return "CONFIG_MAP %s - zapis" % name


def tab_sec_base(name):
    """3.70: jasne przyciski zamykania ("Zamknij i nic nie zapisuj" itd.)
    3.69: trzy przyciski przy zamykaniu (zamknij bez zapisywania)
    3.67: redakcja jezykowa TR po ekspertyzie AI (ogonki + szyk "Błąd RCON")
    3.66: nazwa mapy takze w nazwie pliku sekretu RCON (rownosc
    z CONFIG_MAP - oba pliki mapy mowia, czyje sa)."""
    return "CONFIG_SECRET_RCON %s - zapis" % name

TABS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "CONFIG_MAPS_TABS")  # 3.63 (bylo: taby)
BACKUP_KEEP = 10
# --- 3.71 (mapa logiki): monitor ogolny, pady, WISI, sondy, dziennik modow ---
MONITOR_TICK_S = 10            # rytm skanu procesow+portow+wiek logow
WISI_S = 20 * 60               # prog ciszy loga (autosave <=15 min + 5 min)
WISI_SONDA_S = 15 * 60         # kiedy sonda RCON (listplayers, read-only)
PAD4_OKNO_S = 90               # okno obserwacji "crash w logu a proces zyje"
KARENCJA_PO_GOTOWY_S = 60      # karencja auto-kolejnej tury po GOTOWY
DL_STUCK_S = 20 * 60           # 3.73: bylo 10 min - gigantyczne mody (konwersje
                                 # totalne) sciagaja sie dluzej; mniej falszywych alarmow
DZIENNIK_KEEP = 15             # pliki rotacji dziennika modow
DZIENNIK_MAX_B = 10 * 1024     # max rozmiar jednego pliku dziennika
SERVER_PREFIX = "asa_server_"
TS_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4}) (\d{2})-(\d{2})-(\d{2})")

CF_MODS_BATCH_URL = "https://api.curseforge.com/v1/mods" # 3.39: Endpoint zbiorczy
CF_API_KEYS_URL = "https://console.curseforge.com/?#/api-keys"  # 3.56: Generator CF-API

MIN_CHECK_INTERVAL = 30
DEFAULT_CHECK_INTERVAL = 300
CF_REQUEST_DELAY = 1.0
MAX_RCON_LINES = 20
DEFAULT_WATCH_TIMEOUT = 20
CRASHLOOP_WINDOW_S = 15 * 60
CRASHLOOP_COUNT = 3

# 3.42: kolory dziennika w konsoli (ANSI; aktywne tylko gdy stdout to TTY)
TAG_ANSI = {
    "warn": "\x1b[1;91m", "st_ok": "\x1b[92m",
    "st_bad": "\x1b[91m", "st_wait": "\x1b[93m",
    "cpu_read": "\x1b[96m",       # jasny cyan — świeży odczyt
    "cpu_ok": "\x1b[92m",         # zielony — stan zgodny
    "cpu_change": "\x1b[1;96m",   # jasny cyan bold — wykonana zmiana
    "cpu_wait": "\x1b[93m",       # żółty — GOTOWY/karencja/oczekiwanie
    "cpu_off": "\x1b[90m",        # szary — OFF / tylko odczyt
    "cpu_config": "\x1b[95m",     # fioletowy — zapis konfiguracji
    "plugin_test": "\x1b[94m",    # niebieski — diagnostyka pluginów
    "plugin_ok": "\x1b[92m",      # zielony — test pluginu OK
    "admin_ok": "\x1b[1;92m",     # jasny zielony — administrator potwierdzony
}

DEFAULT_CORE_W = 900
DEFAULT_MODS_W = 420
# 3.42: stała DEFAULT_LOG_W usunięta razem z oknem dziennika (dziennik = konsola)
WINDOW_H = 900
SCREEN_MARGIN = 40
CORE_FLOOR = 620
PANEL_FLOOR = 300

# V3.81: stałe LogTail (skan 2 MB, łaska 15 s) i wzorce logu mieszkają WYŁĄCZNIE
# w asaonly/logtail.py. Wcześniej były tu martwe kopie — zmiana tutaj nic nie
# robiła, a stary wzorzec CFCore (Updating|Installing) nie pasował do niczego.

# ---------------------------------------------------------------------------
# Telemetria Debugująca (3.39)
# ---------------------------------------------------------------------------

def write_debug_log(msg):
    """Zapisuje niewidoczne bledy do pliku dla latwiejszej analizy."""
    try:
        # 3.64: dziennik diagnostyczny w WIEDZA_O_PROGRAMIE/ (czysty root)
        # V3.81: testy przekierowują go zmienną ASAONLY_DEBUG_LOG, żeby fałszywe
        # błędy z testów nie trafiały do prawdziwej czarnej skrzynki.
        debug_path = os.environ.get("ASAONLY_DEBUG_LOG") or os.path.join(KNOW_DIR, "asa_debug.log")
        os.makedirs(os.path.dirname(debug_path) or ".", exist_ok=True)
        with open(debug_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def sanitize_name(name):
    s = re.sub(r"[^A-Za-z0-9_.\- ]+", "_", str(name))
    return s.strip(" ._") or "tab"

# ---------------------------------------------------------------------------
# Tłumaczenia
# ---------------------------------------------------------------------------

from asaonly.tr import TR
from asaonly import jezyk
from asaonly.jezyk import t
# select_server_artifact, read_cfcore_library, validate_rcon_line_values i
# duplicate_enabled_ports: re-eksport — testy sięgają po nie przez moduł programu.
from asaonly.siec import select_server_artifact
from asaonly.serwer_wersje import (parse_cfcore_event, library_json_path,
                                      read_cfcore_library)
from asaonly.widgety import Led, ToolTip, ModTile, BadgeFlow
from asaonly.zapis import (write_json_atomic, newest_matching,
                           save_versioned, migrate_old_file, migrate_old_base,
                           set_debug_logger)
set_debug_logger(write_debug_log)
from asaonly.pluginy import PluginHost
from asaonly.logtail import (open_log_shared, mods_dir_candidates,
                           set_debug_logger as set_logtail_debug,
                           set_event_parser)
set_logtail_debug(write_debug_log)
set_event_parser(parse_cfcore_event)
from asaonly.server_tab import ServerTab, validate_rcon_line_values, duplicate_enabled_ports
from asaonly.procedura import ProcedureMixin, rename_pending_target
from asaonly.kolejka import wzorce_pusto_z_konfiguracji
from asaonly.monitor_plugin import MonitorMixin
from asaonly.cf_wersje import CurseForgeMixin
from asaonly.konsola import PisarzKonsoli, wylacz_szybka_edycje, przywroc_tryb
from asaonly.dziennik_plik import PisarzPliku


# ---------------------------------------------------------------------------
# Klient RCON (Source RCON)
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# CurseForge API (3.39: Batch Architecture)
# ---------------------------------------------------------------------------




















# ---------------------------------------------------------------------------
# Wiersz linii RCON
# ---------------------------------------------------------------------------











# ---------------------------------------------------------------------------
# Zakladka mapy
# ---------------------------------------------------------------------------









# ---------------------------------------------------------------------------
# Główne okno
# ---------------------------------------------------------------------------























class App(CurseForgeMixin, MonitorMixin, ProcedureMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self._tips = {}
        self.knowledge_dir = KNOW_DIR
        self.config_data = self._load_config()
        self.first_run = not self.config_data
        # Runtime procedure intent has its own authoritative atomic file. Legacy
        # global `procedure_run` is used only when that file does not yet exist.
        self.config_data["procedure_run"] = self._load_procedure_state(
            self.config_data.get("procedure_run"))
        self.secrets = self._load_secrets()

        # 3.39: Kolejka asynchroniczna do 100% bezpiecznego logowania w GUI
        self._log_queue = queue.Queue()
        # V3.85.2: konsolę pisze osobny wątek. Zaznaczenie w oknie konsoli
        # (kliknięcie myszą, QuickEdit) wstrzymuje zapis do niej — gdy pisał wątek
        # okna, stawało całe okno („Brak odpowiedzi”), automat i kolejka.
        self._konsola = PisarzKonsoli()
        # V3.86.2: dziennik także w pliku WIEDZA_O_PROGRAMIE/dziennik-zdarzen.txt
        # (osobny wątek; testy kierują go zmienną ASAONLY_EVENT_LOG_DIR).
        self._dziennik_plik = PisarzPliku(
            os.environ.get("ASAONLY_EVENT_LOG_DIR") or KNOW_DIR,
            naglowek=t("start programu %s", "program start %s") % WERSJA_PROGRAMU,
            na_blad=write_debug_log)
        # V3.86.2: kliknięcie w okno konsoli nie wstrzymuje wypisywania dziennika.
        self._tryb_konsoli = wylacz_szybka_edycje()
        # 3.45 FIX: bufor loga tworzony PRZED _load_server_tabs() - migracje
        # loguja podczas ladowania, a bufor powstawal za pozno (AttributeError
        # polykany przez except => tab po cichu pomijany; bug od 3.43)
        # 3.42: dziennik w konsoli; kolory ANSI tylko gdy stdout to prawdziwy TTY
        # 3.71 POWROT (audyt3 mylil sie co do "martwoty"): _log_buffer to
        # interfejs miedzywatkowy dla narzedzi (sterownik symulacji czyta
        # log stąd); bufor 2000 linii, jak w 3.45-3.70
        self._log_buffer = []
        # 3.42: dziennik w konsoli; kolory ANSI tylko gdy stdout to prawdziwy TTY
        self._ansi = False
        try:
            if sys.stdout is not None and sys.stdout.isatty():
                if os.name == "nt":
                    os.system("")  # wlacza sekwencje ANSI w konsoli Windows
                self._ansi = True
        except Exception:
            pass

        # 3.45 FIX: lang PRZED _load_server_tabs() - migracje hasel uzywaja
        # self.tr(), a lang powstawal za pozno (AttributeError polykany
        # przez except => tab po cichu pomijany przy migracji z <=3.44)
        if self.first_run:
            self.lang = self._detect_lang()
        else:
            self.lang = self.config_data.get("lang", "pl")

        self.servers = {}
        self.server_files = {}
        self._load_server_tabs()
        self._tidy_docs()  # 3.64: dokumenty -> WIEDZA_O_PROGRAMIE/

        self.var_api_key = tk.StringVar(value=self.secrets.get("api_key", ""))
        self.monitor_off = set(self.config_data.get("mods_disabled", []))
        self.var_interval = tk.StringVar(value=str(self.config_data.get("interval", DEFAULT_CHECK_INTERVAL)))
        self.var_cf_delay = tk.StringVar(value=str(self.config_data.get("cf_delay", CF_REQUEST_DELAY)))
        self.var_mod_wait = tk.StringVar(value=str(self.config_data.get("mod_wait_min", 5)))
        from asaonly.retencja_padow import limit_mib
        self.pad_archive_limit_mib = limit_mib(self.config_data.get("pad_archive_limit_mib", 2048))
        self.var_pad_limit = tk.StringVar(value=str(self.pad_archive_limit_mib))
        def update_pad_limit(*_):
            # Plain immutable integer snapshot: crash workers never read Tk.
            self.pad_archive_limit_mib = limit_mib(self.var_pad_limit.get())
        self.var_pad_limit.trace_add("write", update_pad_limit)
        self.var_watch = tk.StringVar(value=str(self.config_data.get("watch_timeout_min", DEFAULT_WATCH_TIMEOUT)))
        self._destroying = False
        self.is_admin = self._detect_admin_rights()

        self.auto_rcon = tk.BooleanVar(value=bool(self.config_data.get("auto_rcon", True)))
        # 3.75: pending is keyed by mod_id and carries per-map verification.
        # Legacy [name, fid] entries are migrated after tabs are restored.
        self.pending_updates = list(self.config_data.get("pending_updates", []))
        self.procedure_run = copy.deepcopy(self.config_data.get("procedure_run"))

        self.restart_active = False
        self.restart_t0 = None
        self.updated_mods = []
        self.schedule = []
        self.check_in_progress = False
        self.next_check = time.time() + 1.0
        self._no_key_warned = False  # 3.51: jednorazowe ostrzezenie braku klucza

        self.known_versions = dict(self.config_data.get("known_versions", {}))
        self.mod_names = dict(self.config_data.get("mod_names", {}))
        self.mod_pages = dict(self.config_data.get("mod_pages", {}))
        self._proc_incidents = set()
        self._proc_map_results = {}
        self._leds = {}
        self._chips = {}  # 3.60: kafelki statusow map

        self.mod_latest = {}
        self.mod_states = {}
        self._mod_rows = {}
        self._last_mod_ids = None
        self._blink = False

        self.watch_active = False
        self.watch_t0 = 0.0
        self.watch_deadline = 0.0
        self.watch_maps = {}

        self.tabs = {}
        self._save_pending = False

        self._ui_queue = queue.Queue()

        self._win_open = {"mods": True}
        self._win_pos = {"mods": (None, None)}
        try:
            self._core_w = int(self.config_data.get("log_core_w", DEFAULT_CORE_W))
        except Exception:
            self._core_w = DEFAULT_CORE_W
        if self._core_w < 300:
            self._core_w = DEFAULT_CORE_W
        try:
            self._mods_w = int(self.config_data.get("mods_w", DEFAULT_MODS_W))
        except Exception:
            self._mods_w = DEFAULT_MODS_W
        self._panel_w = {"mods": self._mods_w}

        self._win_open["mods"] = bool(self.config_data.get("mods_open", True))
        for name, kx, ky in (("mods", "mods_x", "mods_y"),):
            x = self.config_data.get(kx)
            y = self.config_data.get(ky)
            if isinstance(x, int) and isinstance(y, int):
                self._win_pos[name] = (x, y)

        self._build_ui()
        self._restore_tabs()
        self._normalize_pending_updates()
        self._refresh_pending_ui()
        self.plugin_host = PluginHost(self, PLUGIN_DIR)
        self.plugin_host.load_all()
        self.plugin_host.start_all()
        # Bezpieczna diagnostyka techniczna wykonuje się sama. Opóźnienie daje
        # monitorowi czas na pierwszy snapshot procesów, istotny dla CPU.
        self.after(3000, self.plugin_host.run_startup_diagnostics)
        # V3.81: przerwana procedura nie blokuje automatu (aksjomat akceleratora).
        self._porzuc_przerwana_procedure()
        if self.is_admin is True:
            self.log(t("[UPRAWNIENIA] Program uruchomiony jako administrator.",
                       "[PERMISSIONS] The program is running as administrator."), "admin_ok")
        elif self.is_admin is False:
            self.log_warn(t("[UPRAWNIENIA] ADMIN: NIE — odczyt może działać, ale Windows może odrzucić "
                            "zmianę priority/affinity i wstrzymanie managera przy aktualizacji "
                            "serwera. Uruchom program jako administrator.",
                            "[PERMISSIONS] ADMIN: NO — reading may work, but Windows may refuse a "
                            "priority/affinity change and pausing the manager for a server update. "
                            "Run the program as administrator."))

        self.after(500, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if self.first_run:
            self.after(600, self._show_first_run_hint)
        self._saved_cfg = self._build_cfg_snapshot()
        self._saved_sec = self._build_sec_snapshot()
        self._saved_tabs = self._build_tabs_snapshot()
        self._startup_warn_line = self.log_warn(self.tr("config_warn_title") + ": " + self.tr("config_warn"))

    @staticmethod
    def _detect_admin_rights():
        """True/False on Windows; None when the check is not applicable."""
        if os.name != "nt":
            return None
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _detect_lang(self):
        try:
            import ctypes
            lang = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "pl" if (lang & 0x3FF) == 0x15 else "en"
        except Exception:
            return "pl"

    def _show_first_run_hint(self):
        # 3.53: intro w KONSOLI (zamiast okienka z "OK" - zgloszenie usera).
        # Krótkie linie - zeby sie miescily i czytalo wygodnie.
        self.log(self.tr("first_run_title"))
        for line in self.tr("first_run_steps").split("\n"):
            self.log(line)

    @property
    def lang(self):
        return self.__dict__.get("_lang", "pl")

    @lang.setter
    def lang(self, value):
        # V3.84: jedno źródło języka — TR (słownik) i t() (teksty w kodzie).
        self.__dict__["_lang"] = jezyk.ustaw(value)

    def tr(self, key, **kwargs):
        s = TR.get(self.lang, TR["pl"]).get(key, key)
        if kwargs:
            try:
                s = s.format(**kwargs)
            except Exception:
                pass
        return s

    def toggle_lang(self):
        if self.restart_active or self.watch_active:
            messagebox.showwarning(
                self.tr("app_title"),
                t("Zmiana języka jest zablokowana do zakończenia procedury i powrotu serwera.",
                  "Changing the language is blocked until the procedure finishes and the server is back."),
                parent=self)
            return
        # 3.68: PRZED przełączeniem języka zapytaj o niezapisane zmiany
        # (dotąd niedokończone taby znikały bez pytania; wykryła to
        # analiza Gemini całości kodu, potwierdził komentarz 3.61 niżej).
        rcon_plugin = (self.plugin_host.get("rcon_admin")
                       if getattr(self, "plugin_host", None) else None)
        if rcon_plugin and not rcon_plugin.all_idle():
            messagebox.showwarning(
                self.tr("app_title"),
                t("Zmiana języka jest zablokowana, gdy komenda RCON jest w kolejce lub w trakcie wysyłania.",
                  "Changing the language is blocked while an RCON command is queued or being sent."),
                parent=self)
            return
        rcon_unsaved = bool(rcon_plugin and rcon_plugin.has_unsaved_editor())
        cfg_snap = self._build_cfg_snapshot()
        sec_snap = self._build_sec_snapshot()
        tabs_snap = self._build_tabs_snapshot()
        if (cfg_snap != self._saved_cfg or sec_snap != self._saved_sec or
                tabs_snap != self._saved_tabs or self._save_pending or rcon_unsaved):
            if not messagebox.askyesno(self.tr("lang_unsaved_title"),
                                       self.tr("lang_unsaved_msg"),
                                       parent=self):
                return
            if rcon_unsaved and not rcon_plugin.save_open_editor():
                return
        was_restart = self.restart_active
        was_watch = self.watch_active
        mods_bylo = self._win_open.get("mods", False)  # 3.61: stan okna modow
        old_lang = self.lang
        self.lang = "en" if self.lang == "pl" else "pl"
        if self._startup_warn_line and self._startup_warn_line in self._log_buffer:
            self._log_buffer.remove(self._startup_warn_line)
        self._startup_warn_line = None
        if not self.save_config(silent=True):
            self.lang = old_lang
            messagebox.showerror(self.tr("app_title"), self.tr("save_err"), parent=self)
            return
        # 3.61: po zapisie wczytaj serwery Z DYSKU (jak przy starcie).
        # Wczesniej _restore_tabs czytal self.servers z pamieci startupu:
        # swiezo dodane (niezapisane) taby ZNIKALY po zmianie jezyka,
        # a edycje bez "Zapisz tab" wracaly do starych wartosci.
        self.servers = {}
        self.server_files = {}
        self._load_server_tabs()
        self._tidy_docs()  # 3.64: dokumenty -> WIEDZA_O_PROGRAMIE/
        if hasattr(self, "plugin_host"):
            self.plugin_host.stop_all()
        for tab in self.tabs.values():
            tab._stop_threads()
        for child in self.winfo_children():
            child.destroy()
        self.tabs = {}
        self._tips.clear()
        self._build_ui()
        # 3.61 FIX "martwe okno modow po zmianie jezyka": _build_ui stawia
        # nowe (schowane) okno modow z pustym panelem, ale _last_mod_ids
        # trzymalo stara liste -> _update_mods_panel "odswiezal" kafelki,
        # ktore juz nie istnialy = pusty panel do restartu programu.
        self._last_mod_ids = None       # wymus odbudowe kafelkow od zera
        self._win_open["mods"] = False  # nowe okno startuje schowane
        self._restore_tabs()
        if hasattr(self, "plugin_host"):
            self.plugin_host.start_all()
            # Zmiana języka niszczy i buduje GUI ponownie oraz ponownie startuje
            # pluginy, więc poprzedni wynik nie wystarcza. Kontrola musi przejść
            # jeszcze raz na nowym cyklu interfejsu.
            self.after(500, self.plugin_host.run_language_change_diagnostics)
        if mods_bylo:
            self._toggle_win("mods")  # okno wraca OD RAZU, w nowym jezyku
        if was_restart:
            for item in self.schedule:
                item["tab"] = self.tabs.get(item["tab"].name, item["tab"])
            self.btn_cancel.configure(state="normal")
            mod_txt = self.build_mod_name_text().replace("\n", " | ")
            self.lbl_updated.configure(text=self.tr("st_updated") + mod_txt)
            for tab in self.tabs.values():
                tab.set_lines_editable(False)
        if was_watch:
            for info in self.watch_maps.values():
                info["tab"] = self.tabs.get(info["tab"].name, info["tab"])
        self._startup_warn_line = self.log_warn(self.tr("config_warn_title") + ": " + self.tr("config_warn"))
        # 3.71.1 FIX "gwiazdka zapisu po EN/PL": przełączenie języka zapisuje
        # config i przebudowuje taby, ale snapshoty "_saved_*" trzymały STARY
        # język -> przy zamykaniu program pytał o "niezapisane zmiany" bez
        # żadnej zmiany usera. Po przebudowie stan = zapisany na dysku.
        self._saved_cfg = self._build_cfg_snapshot()
        self._saved_sec = self._build_sec_snapshot()
        self._saved_tabs = self._build_tabs_snapshot()
        self._save_pending = False

    def _open_plugin_manager(self):
        if not hasattr(self, "plugin_host"):
            self.log_warn(t("Pluginy jeszcze się uruchamiają.", "Plugins are still starting."))
            return
        self.plugin_host.open_manager(self)

    def _build_ui(self):
        self.title(self.tr("app_title"))
        w0, h0 = self._initial_geometry()
        self.geometry(f"{w0}x{h0}")
        self.minsize(CORE_FLOOR, 600)
        self._leds = {}

        # V3.85.3: układ górnej części (wcześniej jeden rząd wypychał przyciski
        # pluginów, „Wykonaj zaległe aktualizacje” i „Anuluj procedurę” poza okno):
        #   rząd programu: język, O programie, mapy, mody … ADMIN,
        #   pasek „Pluginy”: Manager Pluginów + przyciski pluginów (zawijane),
        #   procedura (zaległe, anuluj) — w ramce Status, obok „Sprawdź mody teraz”.
        frm_top = ttk.Frame(self)
        frm_top.pack(fill="x", padx=8, pady=(8, 0))

        def przycisk(rodzic, text, cmd, tt_key, flow=None, **k):
            b = ttk.Button(rodzic, text=text, command=cmd, **k)
            if flow is None:
                b.pack(side="left", padx=(0, 6))
            else:
                flow.append(b)
            self._add_tooltip(b, tt_key)
            return b

        self.btn_lang = przycisk(frm_top, self.tr("lang_btn"), self.toggle_lang, "tt_lang")
        self.btn_about = przycisk(frm_top, self.tr("about_btn"), self.show_about, "tt_about")
        self.btn_add = przycisk(frm_top, self.tr("add_server"), self.add_server, "tt_add_map")
        self.btn_mods_win = przycisk(frm_top, self.tr("btn_mon_mods"),
                                     lambda: self._toggle_win("mods"), "tt_mods_win")
        if self.is_admin is True:
            admin_text, admin_color = t("ADMIN: TAK", "ADMIN: YES"), "#207020"
        elif self.is_admin is False:
            admin_text, admin_color = t("ADMIN: NIE", "ADMIN: NO"), "#b00020"
        else:
            admin_text, admin_color = t("ADMIN: N/D", "ADMIN: N/A"), "#555555"
        self.lbl_admin = ttk.Label(frm_top, text=admin_text, foreground=admin_color,
                                   font=("TkDefaultFont", 9, "bold"))
        self.lbl_admin.pack(side="right", padx=(8, 0))
        self._add_tooltip(self.lbl_admin, "tt_admin_status")

        self.frm_pluginy = ttk.LabelFrame(self, text=t("Pluginy", "Plugins"))
        self.frm_pluginy.pack(fill="x", padx=8, pady=(6, 0))
        self.btn_plugins = ttk.Button(self.frm_pluginy, text=t("MANAGER PLUGINÓW", "PLUGIN MANAGER"),
                                      command=self._open_plugin_manager)
        self.btn_plugins.pack(side="left", padx=(6, 0), pady=(2, 6), anchor="n")
        self._add_tooltip(self.btn_plugins, "tt_plugin_manager")
        ttk.Separator(self.frm_pluginy, orient="vertical").pack(side="left", fill="y", padx=8, pady=(2, 6))
        # Miejsce na przyciski pluginów (wypełnia host po starcie pluginów); zawija się.
        self.frm_plugin_actions = BadgeFlow(self.frm_pluginy)
        self.frm_plugin_actions.pack(side="left", fill="x", expand=True, pady=(2, 3))

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=(8, 0))
        lbl_key = ttk.Label(top, text=self.tr("api_key"))
        lbl_key.pack(side="left")
        self._add_tooltip(lbl_key, "tt_api_entry")
        # V3.85.3: przyciski od prawej, pole klucza zajmuje resztę — w węższym
        # oknie zwęża się pole, a „Zapisz klucz” nie wypada poza okno.
        self.btn_save_api = ttk.Button(top, text=self.tr("save_api"),
                                       command=lambda: self.save_secrets(silent=False))
        self.btn_save_api.pack(side="right", padx=(8, 0))
        self._add_tooltip(self.btn_save_api, "tt_save_api")
        # 3.56: Generator CF-API - prosto do strony kluczy (deep link)
        self.btn_cf_gen = ttk.Button(top, text=self.tr("cf_key_gen"),
                                     command=self._open_cf_api_keys)
        self.btn_cf_gen.pack(side="right", padx=4)
        self._add_tooltip(self.btn_cf_gen, "tt_cf_key_gen")
        self.btn_api_bak = ttk.Button(top, text=self.tr("api_from_backup"),
                                      command=self._load_api_from_backup)
        self.btn_api_bak.pack(side="right", padx=4)
        self._add_tooltip(self.btn_api_bak, "tt_api_from_backup")
        self.btn_show = ttk.Button(top, text=self.tr("show"), width=6,
                                   command=self._toggle_key)
        self.btn_show.pack(side="right")
        self._add_tooltip(self.btn_show, "tt_show_key")
        ent_key = ttk.Entry(top, textvariable=self.var_api_key, width=40,
                            show="*")
        ent_key.pack(side="left", padx=5, fill="x", expand=True)
        self._add_tooltip(ent_key, "tt_api_entry")

        top3 = ttk.Frame(self)
        top3.pack(fill="x", padx=8, pady=(6, 0))
        lbl_i = ttk.Label(top3, text=self.tr("check_interval"))
        lbl_i.pack(side="left")
        self._add_tooltip(lbl_i, "tt_interval")
        ttk.Entry(top3, textvariable=self.var_interval,
                  width=8).pack(side="left", padx=5)
        lbl_c = ttk.Label(top3, text=self.tr("cf_delay"))
        lbl_c.pack(side="left", padx=(15, 0))
        self._add_tooltip(lbl_c, "tt_cf_delay")
        ttk.Entry(top3, textvariable=self.var_cf_delay,
                  width=8).pack(side="left", padx=5)
        lbl_w = ttk.Label(top3, text=self.tr("watch_timeout"))
        lbl_w.pack(side="left", padx=(15, 0))
        self._add_tooltip(lbl_w, "tt_watch")
        ttk.Entry(top3, textvariable=self.var_watch,
                  width=4).pack(side="left", padx=5)
        wait_row = ttk.Frame(self)
        wait_row.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(wait_row, text=t("Odczekanie po wykryciu moda [min, 0–60; 0 = wyłączone]:",
                                   "Wait after detecting a mod [min, 0–60; 0 = off]:")).pack(side="left")
        ttk.Entry(wait_row, textvariable=self.var_mod_wait, width=4).pack(side="left", padx=5)
        pad_row = ttk.Frame(self)
        pad_row.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Label(pad_row, text=t("Archiwum PADY — limit [MiB, 256–65536; 0 = bez rotacji]:",
                                  "PADY archive — limit [MiB, 256–65536; 0 = no rotation]:")).pack(side="left")
        self.ent_pad_limit = ttk.Entry(pad_row, textvariable=self.var_pad_limit, width=7)
        self.ent_pad_limit.pack(side="left", padx=5)
        ToolTip(self.ent_pad_limit, t(
            "Domyślnie 2048 MiB. Najnowsza kopia oraz ostatnia pełna kopia każdej mapy są chronione. "
            "Starsze rozpoznane kopie są usuwane po zapisie nowych dowodów. Stare formaty i obce pliki pozostają. "
            "Przekroczenie limitu lub błąd pomiaru powodują ostrzeżenie w dzienniku. Błędna wartość = 2048 MiB.",
            "Default 2048 MiB. The latest and latest complete snapshot of each map are protected. "
            "Older recognized snapshots are removed after capturing new evidence. Legacy/foreign files remain. "
            "Over-budget or accounting failures are reported in the journal. Invalid input = 2048 MiB."))

        self.win_mods = tk.Toplevel(self)
        self.win_mods.withdraw()
        self.win_mods.title(self.tr("win_mods_title"))
        self.win_mods.protocol("WM_DELETE_WINDOW",
                               lambda: self._close_win("mods"))
        self.win_mods.minsize(360, 200)  # 3.40: dolna granica sensownego okna
        self.frm_mods = ttk.Frame(self.win_mods)
        self.frm_mods.pack(fill="both", expand=True)
        self.mods_canvas = tk.Canvas(self.frm_mods, highlightthickness=0,
                                     bg="#f6f7f9")
        self._sb_mods = ttk.Scrollbar(self.frm_mods, orient="vertical",
                                      command=self.mods_canvas.yview)
        self.mods_canvas.configure(yscrollcommand=self._sb_mods.set)
        self._sb_mods.pack(side="right", fill="y")
        self.mods_canvas.pack(side="left", fill="both", expand=True,
                              padx=(8, 0), pady=(0, 6))
        self._mods_inner = ttk.Frame(self.mods_canvas)
        self._mods_win = self.mods_canvas.create_window(
            (0, 0), window=self._mods_inner, anchor="nw")
        self._mods_inner.bind(
            "<Configure>",
            lambda e: self.mods_canvas.configure(
                scrollregion=self.mods_canvas.bbox("all")))
        self.mods_canvas.bind("<Configure>", self._on_mods_canvas_resize)
        # 3.40: kółko myszy przewija listę modów. Router aktywny tylko gdy
        # kursor jest nad oknem modów - pozostałe okna nietknięte.
        self.mods_canvas.configure(yscrollincrement=22)
        self.bind_all("<MouseWheel>", self._on_mods_wheel)
        self._mod_rows = {}

        self.frm_status = ttk.LabelFrame(self, text=self.tr("status"))
        self.frm_status.pack(fill="x", padx=8, pady=8)
        # 3.60: rzędy: tekst stanu; (V3.85.3) przyciski procedury i przełączniki
        # automatu — zawijane; kafelki statusów map (kropka + nazwa + status).
        self.frm_status_top = ttk.Frame(self.frm_status)
        self.frm_status_top.pack(side="top", fill="x", padx=6, pady=(4, 0))
        self.lbl_status = ttk.Label(self.frm_status_top, text="", font=("TkDefaultFont", 10, "bold"))
        self.lbl_updated = ttk.Label(self.frm_status, text="", foreground="#0a5", wraplength=820, justify="left")

        self.chk_auto = ttk.Checkbutton(self.frm_status_top, text=self.tr("auto_rcon"),
                                        variable=self.auto_rcon,
                                        command=self._toggle_auto)
        self.chk_auto.pack(side="right", padx=(0, 10))
        self._add_tooltip(self.chk_auto, "tt_auto")
        # V3.81: pusta mapa (potwierdzona przez ListPlayers) = restart bez ogłoszeń.
        self.var_pusty = tk.BooleanVar(value=bool(self.config_data.get("pusty_serwer_od_razu", True)))
        self.chk_pusty = ttk.Checkbutton(self.frm_status_top, text=self.tr("pusty_od_razu"),
                                         variable=self.var_pusty,
                                         command=self._toggle_pusty)
        self.chk_pusty.pack(side="right", padx=(0, 10))
        self._add_tooltip(self.chk_pusty, "tt_pusty")
        # Teksty stanu pakowane PO przełącznikach: w wąskim oknie skraca się tekst,
        # a nie opis przełącznika.
        self.lbl_status.pack(side="left", padx=(4, 0), pady=(4, 2))
        self.lbl_updated.pack(side="top", fill="x", padx=10)
        self.frm_status.bind("<Configure>", lambda e: self.lbl_updated.configure(wraplength=max(100, e.width - 24)))

        # V3.85.3: przyciski procedury razem (wcześniej „zaległe” i „anuluj” wypadały
        # poza okno w górnym rzędzie); rząd zawija się w wąskim oknie.
        self.frm_status_akcje = BadgeFlow(self.frm_status)
        self.frm_status_akcje.pack(side="top", fill="x", padx=10, pady=(2, 4))
        akcje = []
        self.btn_check_now = przycisk(self.frm_status_akcje, self.tr("check_now"),
                                      lambda: self.check_now(manual=True), "tt_check_now", flow=akcje)
        self.btn_pending = przycisk(self.frm_status_akcje, self.tr("btn_pending_full"),
                                    lambda: self._exec_pending(manual=True), "tt_pending",
                                    flow=akcje, state="disabled")
        self.btn_cancel = przycisk(self.frm_status_akcje, self.tr("cancel_restart"),
                                   self.cancel_restart, "tt_cancel", flow=akcje, state="disabled")
        self.frm_status_akcje.set_badges(akcje)
        self.lbl_return_alarm = ttk.Label(self.frm_status, text="", foreground="#b00020",
                                          wraplength=800, justify="left")
        self.lbl_return_alarm.pack(side="top", fill="x", padx=12, pady=2)
        self._refresh_return_alarm()

        # 3.60: kafelki statusow map - wlasna linia, zawijanie jak diody modow
        self.frm_leds = BadgeFlow(self.frm_status)
        self.frm_leds.pack(side="top", fill="x", padx=16, pady=(0, 6))

        self.mid = ttk.Frame(self)
        self.mid.rowconfigure(0, weight=1)
        self.mid.columnconfigure(0, weight=1)

        # 3.42: okno dziennika usuniete - dziennik zyje w konsoli
        self.log(self.tr("console_hint"))
        if self._tryb_konsoli is not None:
            self.log(t("[KONSOLA] Zaznaczanie myszą w tym oknie jest wyłączone — kliknięcie nie "
                       "wstrzymuje dziennika. Kopiowanie: menu okna (ikona w lewym górnym rogu) → "
                       "Edytuj → Zaznacz, albo plik WIEDZA_O_PROGRAMIE\\dziennik-zdarzen.txt.",
                       "[CONSOLE] Mouse selection in this window is off — a click does not pause "
                       "the log. To copy: the window menu (icon in the top-left corner) → Edit → "
                       "Mark, or the file WIEDZA_O_PROGRAMIE\\dziennik-zdarzen.txt."))

        self.notebook = ttk.Notebook(self.mid)
        self.notebook.bind("<Double-Button-1>", self._on_tab_dblclick)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.mid.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        self.bind("<Configure>", self._on_win_configure)
        self._apply_startup_windows()

        self._show_key = False
        self._refresh_pending_ui()

    def _initial_geometry(self):
        try:
            scr_w = self.winfo_screenwidth()
            scr_h = self.winfo_screenheight()
            h = min(WINDOW_H, max(680, scr_h - 120))
            avail = scr_w - SCREEN_MARGIN
            w = self._core_w or DEFAULT_CORE_W
            if w > avail:
                w = max(CORE_FLOOR, avail)
            return w, h
        except Exception:
            return DEFAULT_CORE_W, WINDOW_H

    def _add_tooltip(self, widget, key):
        try:
            text = self.tr(key)
            if text and text != key:
                tt = ToolTip(widget, text)
                self._tips.setdefault(key, []).append(tt)
        except Exception:
            pass

    def _toggle_win(self, name):
        win = self.win_mods
        if self._win_open.get(name, False):
            self._save_win_pos(name, win)
            win.withdraw()
            self._win_open[name] = False
        else:
            win.deiconify()
            self._win_open[name] = True
            self._restore_win_pos(name, win)
            win.lift()
            # 3.44: widoczny slad w konsoli, GDZIE okno wyladowalo
            # (gdyby znowu "uciekalo" - dziennik pokaze wspolrzedne)
            self.log(self.tr("win_shown", geom=win.winfo_geometry()))
            if name == "mods":
                self._update_mods_panel()
                if getattr(self, "_mods_fit2", None):
                    self.after_cancel(self._mods_fit2)
                self._mods_fit2 = self.after(200, self._mods_fit)
        self.save_config(silent=True)

    def _close_win(self, name):
        win = self.win_mods
        self._save_win_pos(name, win)
        win.withdraw()
        self._win_open[name] = False
        self.save_config(silent=True)

    def _save_win_pos(self, name, win):
        # 3.44: pozycje zapisujemy TYLKO z widocznego okna - okno ukryte
        # raportuje rootx/rooty = -1 i to trafialo potem do configu
        try:
            if not win.winfo_viewable():
                return
            self._win_pos[name] = (win.winfo_rootx(), win.winfo_rooty())
            self._panel_w[name] = max(PANEL_FLOOR, win.winfo_width())
        except Exception:
            pass

    def _restore_win_pos(self, name, win):
        # 3.44: zapisana pozycja musi lezec na WIDOCZNEJ czesci ekranu
        # (stare configi mialy -1/-1 albo wspolrzedne drugiego monitora -
        # okno "mrugnelo" w domyslnym miejscu i uciekalo poza ekran).
        try:
            x, y = self._win_pos.get(name) or (None, None)
            if x is None or y is None:
                return
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            if not (0 <= x <= sw - 120 and 0 <= y <= sh - 60):
                # pozycja smieciowa: centruj nad oknem glownym
                x = max(0, self.winfo_rootx()
                        + (self.winfo_width() - win.winfo_width()) // 2)
                y = max(0, self.winfo_rooty() + 60)
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _apply_startup_windows(self):
        for name in ("mods",):
            win = self.win_mods
            w = self._panel_w.get(name, DEFAULT_MODS_W)
            win.geometry(f"{w}x{WINDOW_H}")
            if self._win_open.get(name, False):
                win.deiconify()
                self._restore_win_pos(name, win)
            else:
                win.withdraw()

    def _on_win_configure(self, event):
        if event.widget == self:
            self._core_w = event.width

    def _on_mods_canvas_resize(self, event):
        self.mods_canvas.itemconfig(self._mods_win, width=event.width)

    def _on_mods_wheel(self, event):
        # 3.40: przewijamy tylko, gdy kursor jest nad oknem modów
        # (wspinaczka po drzewie rodziców az do Toplevela tego okna).
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
            while w is not None and w is not self.win_mods:
                w = getattr(w, "master", None)
            if w is self.win_mods and self._win_open.get("mods", False):
                self.mods_canvas.yview_scroll(
                    int(-1 * (event.delta / 120)) * 3, "units")
        except Exception:
            pass

    def _mods_fit(self):
        try:
            self.mods_canvas.configure(scrollregion=self.mods_canvas.bbox("all"))
        except Exception:
            pass

    def _toggle_key(self):
        self._show_key = not self._show_key
        show_char = "" if self._show_key else "*"
        self.btn_show.configure(text=self.tr("hide") if self._show_key else self.tr("show"))

        def recurse(parent):
            for w in parent.winfo_children():
                if isinstance(w, ttk.Entry):
                    try:
                        if w.cget("textvariable") == str(self.var_api_key):
                            w.configure(show=show_char)
                    except Exception:
                        pass
                recurse(w)
        recurse(self)

    def _toggle_pusty(self):
        val = bool(self.var_pusty.get())
        self.config_data["pusty_serwer_od_razu"] = val
        self.log(self.tr("pusty_on_log") if val else self.tr("pusty_off_log"))
        self.save_config(silent=True)

    def _toggle_auto(self):
        val = self.auto_rcon.get()
        if val:
            self.log(self.tr("auto_on_log"))
        else:
            self.log(self.tr("auto_off_log"))
        self.save_config(silent=True)




    def _refresh_pending_ui(self):
        n = len(self.pending_updates)
        if n > 0:
            self.btn_pending.configure(state="normal")
            mod_names = ", ".join(
                p.get("name", p.get("mid", "?")) if isinstance(p, dict)
                else str(p[0]) for p in self.pending_updates)
            self.lbl_updated.configure(text=self.tr("st_pending") + f"{n} ({mod_names})", foreground="#d9534f")
        else:
            self.btn_pending.configure(state="disabled")
            if not self.restart_active:
                self.lbl_updated.configure(text="", foreground="#0a5")
        # 3.42: zaleglosc zmienia kolor diody w tabach
        for tab in self.tabs.values():
            tab._refresh_badges()

    def _on_tab_dblclick(self, event):
        try:
            clicked_tab = self.notebook.identify(event.x, event.y)
            if clicked_tab == "label":
                index = self.notebook.index(f"@{event.x},{event.y}")
                tab_name = self.notebook.tab(index, "text")
                tab = self.tabs.get(tab_name)
                if tab:
                    self.rename_server(tab)
        except Exception:
            pass

    # ------------------------------------------------------------------ Wczytywanie i Zapis
    def _tidy_docs(self):
        """3.64: w katalogu glownym zostaje TYLKO program i .bat -
        dokumenty schodza do WIEDZA_O_PROGRAMIE/."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            os.makedirs(KNOW_DIR, exist_ok=True)
            for pat in ("README - *.txt", "README.md", "MANUAL - *.md",
                        "MAPA-PROGRAMU.md", "PROMPT-ASAonly-*.md",
                        "SYMULACJA-REPORT-*.md"):
                for fp in glob.glob(os.path.join(base_dir, pat)):
                    dst = os.path.join(KNOW_DIR, os.path.basename(fp))
                    if not os.path.exists(dst):
                        shutil.move(fp, dst)
            # 3.65 FIX: STARY asa_debug.log z roota tez schodzi do WIEDZY
            # (w 3.64 nowe wpisy szly do WIEDZY, ale stary plik zostawal)
            old_log = os.path.join(base_dir, "asa_debug.log")
            if os.path.exists(old_log):
                new_log = os.path.join(KNOW_DIR, "asa_debug.log")
                try:
                    if os.path.exists(new_log):
                        with open(old_log, "r", encoding="utf-8", errors="replace") as f:
                            stara = f.read()
                        with open(new_log, "a", encoding="utf-8") as f:
                            f.write(stara)
                        os.remove(old_log)
                    else:
                        shutil.move(old_log, new_log)
                except Exception:
                    pass
        except Exception:
            pass

    def _load_config(self):
        # 3.45: czytelne nazwy - czytamy NAJNOWSZY plik wersjonowany
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 3.64: konfiguracja programu we wlasnym katalogu CONFIG_PROGRAM/
        os.makedirs(CONFIG_DIR, exist_ok=True)
        migrate_old_base(base_dir, "konfiguracja programu - zapis",
                         CONFIG_DIR, CONFIG_BASE)  # przed 3.63
        migrate_old_base(base_dir, CONFIG_BASE,
                         CONFIG_DIR, CONFIG_BASE)  # 3.63 (luźno) -> 3.64
        migrate_old_file(os.path.join(base_dir, "asa_config.json"),
                         CONFIG_DIR, CONFIG_BASE)
        p = newest_matching(CONFIG_DIR, CONFIG_BASE)
        if p:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _load_procedure_state(self, legacy=None):
        """Read the single authoritative runtime checkpoint, fail-closed."""
        path = os.path.join(CONFIG_DIR, PROCEDURE_STATE_NAME)
        if not os.path.exists(path):
            return copy.deepcopy(legacy) if isinstance(legacy, dict) else None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                envelope = json.load(fh)
            if not isinstance(envelope, dict) or "procedure_run" not in envelope:
                raise ValueError("missing procedure_run field")
            run = envelope["procedure_run"]
            if run is None:
                return None
            if not isinstance(run, dict):
                raise TypeError("procedure_run is not an object")
            if not isinstance(run.get("run_id"), str) or not run.get("run_id"):
                raise ValueError("missing run_id")
            if not isinstance(run.get("stage"), str) or not run.get("stage"):
                raise ValueError("missing stage")
            return run
        except Exception as exc:
            write_debug_log("Invalid procedure checkpoint %s: %s" % (path, exc))
            return {"run_id": "INVALID-CHECKPOINT", "stage": "invalid_checkpoint",
                    "map": None, "error": str(exc)}

    def save_procedure_state(self):
        """Atomically persist frequent runtime intent without consuming config backups."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        path = os.path.join(CONFIG_DIR, PROCEDURE_STATE_NAME)
        ok = write_json_atomic(path, {
            "schema": 1,
            "procedure_run": copy.deepcopy(getattr(self, "procedure_run", None))})
        if not ok:
            self._save_pending = True
            self.log(self.tr("save_err") + " procedure_run")
        return bool(ok)

    def _load_secrets(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 3.64: sekret API we wlasnym katalogu CONFIG_SECRET_API/
        os.makedirs(SECRET_API_DIR, exist_ok=True)
        migrate_old_base(base_dir, "sekrety programu (klucz API) - zapis",
                         SECRET_API_DIR, SECRETS_BASE)  # przed 3.63
        migrate_old_base(base_dir, SECRETS_BASE,
                         SECRET_API_DIR, SECRETS_BASE)  # 3.63 -> 3.64
        migrate_old_file(os.path.join(base_dir, "asa_secrets.json"),
                         SECRET_API_DIR, SECRETS_BASE)
        p = newest_matching(SECRET_API_DIR, SECRETS_BASE)
        if p:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _load_server_tabs(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(TABS_DIR, exist_ok=True)

        # 3.45: migracja katalogu asa_tabs -> taby (jednorazowo)
        old_tabs = os.path.join(base_dir, "asa_tabs")
        if os.path.isdir(old_tabs) and old_tabs != TABS_DIR:
            try:
                for item in os.listdir(old_tabs):
                    src = os.path.join(old_tabs, item)
                    dst = os.path.join(TABS_DIR, item)
                    if os.path.isdir(src) and not os.path.exists(dst):
                        shutil.move(src, dst)
                if not os.listdir(old_tabs):
                    os.rmdir(old_tabs)
            except Exception:
                pass

        # 3.63: migracja katalogu taby -> CONFIG_MAPS_TABS (jednorazowo)
        stare_taby = os.path.join(base_dir, "taby")
        if os.path.isdir(stare_taby) and stare_taby != TABS_DIR:
            try:
                for item in os.listdir(stare_taby):
                    src = os.path.join(stare_taby, item)
                    dst = os.path.join(TABS_DIR, item)
                    if os.path.isdir(src) and not os.path.exists(dst):
                        shutil.move(src, dst)
                if not os.listdir(stare_taby):
                    os.rmdir(stare_taby)
            except Exception:
                pass

        # 3.37: legacy asa_server_*.json obok programu -> katalog tabu
        for fp in glob.glob(os.path.join(base_dir, f"{SERVER_PREFIX}*.json")):
            try:
                base = os.path.basename(fp)
                name_part = base[len(SERVER_PREFIX):-5]
                if name_part:
                    name = name_part.replace("_", " ")
                    dest_dir = os.path.join(TABS_DIR, sanitize_name(name))
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(fp, os.path.join(dest_dir, "config.json"))
                    os.remove(fp)
            except Exception:
                pass

        for item in os.listdir(TABS_DIR):
            dir_path = os.path.join(TABS_DIR, item)
            if os.path.isdir(dir_path):
                # 3.63: stara konwencja nazw -> CONFIG_* (jednorazowo)
                migrate_old_base(dir_path, "konfiguracja mapy - zapis",
                                 dir_path, TAB_CFG_BASE)
                # 3.45: stare nazwy -> czytelne wersjonowane (jednorazowo)
                migrate_old_file(os.path.join(dir_path, "config.json"),
                                 dir_path, TAB_CFG_BASE)
                cfg0 = newest_matching(dir_path, "CONFIG_MAP")
                if not cfg0:
                    continue
                try:
                    with open(cfg0, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        name = data.get("name") or item.replace("_", " ")
                        # 3.64: nazwa mapy w nazwie pliku konfiguracji
                        migrate_old_base(dir_path, TAB_CFG_BASE, dir_path,
                                         tab_cfg_base(name))
                        cfg_path = newest_matching(dir_path, tab_cfg_base(name))
                        # 3.64: sekret mapy w podkatalogu CONFIG_SECRET_RCON/
                        sec_dir = os.path.join(dir_path, TAB_SEC_DIR_NAME)
                        migrate_old_base(dir_path,
                                         "sekret mapy (hasło RCON) - zapis",
                                         sec_dir, TAB_SEC_BASE)
                        migrate_old_base(dir_path, TAB_SEC_BASE,
                                         sec_dir, TAB_SEC_BASE)
                        migrate_old_file(os.path.join(dir_path, "secrets.json"),
                                         sec_dir, TAB_SEC_BASE)
                        # 3.66: nazwa mapy w nazwie pliku sekretu
                        migrate_old_base(sec_dir, TAB_SEC_BASE,
                                         sec_dir, tab_sec_base(name))
                        sec_path = newest_matching(sec_dir, "CONFIG_SECRET_RCON")
                        if sec_path:
                            try:
                                with open(sec_path, "r", encoding="utf-8") as sf:
                                    sec = json.load(sf)
                                if isinstance(sec, dict):
                                    data["password"] = sec.get("password") or ""
                            except Exception:
                                pass
                        elif "password" in data:
                            os.makedirs(sec_dir, exist_ok=True)
                            save_versioned(sec_dir, tab_sec_base(name), {
                                "password": data.get("password") or ""})
                            self.log(self.tr("secret_migrated", name=name))
                        self.servers[name] = data
                        self.server_files[name] = cfg_path
                except Exception:
                    pass

    def _restore_tabs(self):
        for name, cfg in self.servers.items():
            self.add_server(name=name, config=cfg)
        self._update_mods_panel()
        # 3.62 FIX: add_server podbija flage "do zapisu" -> po starcie programu
        # (i po przebudowie UI) pytanie o niezapisane zmiany strzelalo przy
        # KAZDYM zamknieciu, nawet bez zadnej zmiany usera. Odtworzenie z
        # dysku = stan zsynchronizowany = czysto.
        self._save_pending = False

    def _update_mods_panel(self):
        mod_ids = set()
        for tab in self.tabs.values():
            if tab.var_map_on.get():
                mod_ids.update(tab.get_effective_mod_ids())

        sorted_mids = sorted(list(mod_ids), key=lambda x: int(x) if x.isdigit() else 99999999)

        if self._last_mod_ids != sorted_mids:
            self._last_mod_ids = sorted_mids
            for w in self._mods_inner.winfo_children():
                w.destroy()
            self._mod_rows.clear()

            if not sorted_mids:
                lbl = ttk.Label(self._mods_inner, text=self.tr("mods_no_mods"), justify="center", padding=20)
                lbl.pack(fill="x", expand=True)
                return

            for mid in sorted_mids:
                # 3.39.2: bez width=... - szerokość da mu pack fill="x" + <Configure>
                tile = ModTile(self._mods_inner, self, mid)
                tile.pack(fill="x", pady=4, padx=4)
                self._mod_rows[mid] = tile
                tile.refresh()
        else:
            for tile in self._mod_rows.values():
                tile.refresh()

        self._mods_fit()
        # 3.42: diody tabow zsynchronizowane z panelem modow
        for tab in self.tabs.values():
            tab._refresh_badges()

    def _mod_state_ui(self, state, mid):
        mapping = {
            "ok": (self.tr("mods_state_ok"), "#207020"),
            "update": (self.tr("mods_state_update"), "#e0a050"),
            "pending": (self.tr("mods_state_pending"), "#d9534f"),
            "error": (self.tr("mods_state_error"), "#b00020"),
            "checking": (self.tr("mods_state_checking"), "#007acc"),
            "off": (self.tr("mods_state_off"), "#999999"),
            "wait": (self.tr("mods_state_wait"), "#3d6db5"),  # 3.59: zapalony
        }
        return mapping.get(state, (self.tr("mods_state_wait"), "#3d6db5"))

    def _badge_state(self, mid, map_name=None):
        """3.42: stan diody moda: zaleglosc > wylaczony > stan z checku."""
        name = self.mod_names.get(mid)
        if map_name is not None:
            for p in self.pending_updates:
                if isinstance(p, dict) and p.get("mid") == mid:
                    if map_name in p.get("verified", []):
                        return "ok"
                    if map_name in p.get("targets", []):
                        return "pending"
                    tab = self.tabs.get(map_name)
                    loaded = getattr(tab, "_server_versions", {}).get(mid)
                    return "ok" if str(loaded).isdigit() and int(loaded) >= int(p["fid"]) else "wait"
        if any((isinstance(p, dict) and p.get("mid") == mid) or
               (isinstance(p, (list, tuple)) and p and p[0] == name)
               for p in self.pending_updates):
            return "pending"
        if mid in self.monitor_off:
            return "off"
        return self.mod_states.get(mid, "wait")

    def _tabs_for_mod(self, mid):
        out = []
        for tab in self.tabs.values():
            if mid in tab.get_effective_mod_ids():
                out.append(tab.name)
        return out

    def _loaded_mods_from_log(self, log_dir):
        """3.49: mody, ktore serwer NAPRAWDE ladowal - z ogona logu.
        Szukamy linii o ladowaniu modow (LoadGameMods / 'loading mod...') i
        wyciagamy numery (6-10 cyfr). Zwraca liste ID w kolejnosci z logu
        albo None (brak logu / nic nie wyczytano)."""
        if not log_dir or not os.path.isdir(log_dir):
            return None
        path = os.path.join(log_dir, "ShooterGame.log")
        try:
            f = open_log_shared(path)
            if f is None:
                return None
            try:
                try:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 512 * 1024))
                except Exception:
                    pass
                data = f.read()
            finally:
                try:
                    f.close()
                except Exception:
                    pass
        except Exception:
            return None
        ids, seen = [], set()
        for line in data.splitlines():
            low = line.lower()
            if "loadgamemods" not in low and not ("load" in low and "mod" in low):
                continue
            # 3.58: PIERWSZA liczba z kazdego fragmentu po przecinku.
            # Realny serwer ASA wypisuje w linii LoadGameMods PARY:
            # "mod (wersja)" / "mod_plik", np. "...: 940975, 928548 (7005633),
            # 929684 (8510257)". Wczesniejsza regula "lista z przecinkami =
            # bierz wszystkie" wciągala obie liczby z pary (9 modow + 9 wersji
            # = 18 "modow" - log usera). Pierwsza liczba pary = mod ID.
            for token in line.split(","):
                m = re.search(r"\d{6,12}", token)  # 3.71 (audyt2): zapas na przyszle ID
                if m and m.group(0) not in seen:
                    seen.add(m.group(0))
                    ids.append(m.group(0))
        return ids or None

    def _mods_dir_for_tab(self, tab):
        # nie dotykamy self (jednostkowe wolaja z fabrycznym obiektem)
        for p in mods_dir_candidates(tab.var_log.get().strip()):
            if os.path.isdir(p):
                return p
        return None

    def _installed_file_ids(self, mods_dir):
        if not mods_dir or not os.path.isdir(mods_dir):
            return []
        # CFCore's own registry is authoritative for completed installations.
        merged = read_cfcore_library(library_json_path(mods_dir))
        try:
            for item in os.listdir(mods_dir):
                item_path = os.path.join(mods_dir, item)
                if not os.path.isdir(item_path):
                    continue
                mod_id, file_id = item, "0"
                if "_" in item:
                    a, b = item.split("_", 1)
                    if a.isdigit() and b.isdigit():
                        mod_id, file_id = a, b
                    else:
                        continue
                elif not item.isdigit():
                    continue
                for f in os.listdir(item_path):
                    if f.endswith(".mod"):
                        name_part = f[:-4]
                        if name_part.isdigit() and name_part != mod_id:
                            file_id = name_part
                            break
                old = merged.get(mod_id)
                if file_id != "0" and (old is None or int(file_id) > int(old)):
                    merged[mod_id] = file_id
                elif old is None:
                    merged[mod_id] = file_id
        except Exception as e:
            write_debug_log("installed-file scan error: %s" % e)
        return sorted(merged.items(), key=lambda x: int(x[0]))

    def open_mod_page(self, mod_id):
        url = self.mod_pages.get(mod_id)
        if not url:
            # 3.53 FIX: w sciezce strony CF NIE wolno wstawiac cyfrowego ID
            # ( taki link prowadzi donikad - zgloszenie usera). Dopoki API
            # nie podalo adresu (slug/websiteUrl), kierujemy na wyszukiwarke.
            url = ("https://www.curseforge.com/ark-survival-ascended"
                   "/mods/search?search=" + str(mod_id))
        webbrowser.open(url)

    def add_server(self, name=None, config=None):
        if name is None:
            from tkinter import simpledialog
            name = simpledialog.askstring(self.tr("server_name_title"), self.tr("server_name_prompt"), parent=self)
            if not name:
                return
            name = name.strip()
            if name in self.tabs:
                messagebox.showerror("", self.tr("server_exists"))
                return

        tab = ServerTab(self.notebook, self, name, config=config)
        self.notebook.add(tab, text=name)
        self.tabs[name] = tab
        if getattr(self, "plugin_host", None):
            self.plugin_host.call_hook("on_tab_added", name, tab)

        self._update_leds_frame()
        self.request_save()
        self._update_mods_panel()
        # Import/dodanie mapy po pustym starcie nie może czekać do końca
        # pełnego interwału CF. Działające serwery mają zostać zaadaptowane
        # od razu po pojawieniu się ich tabów.
        if tab.get_effective_mod_ids():
            self.schedule_immediate_mod_check()

    def _normalize_legacy_tab(self, data, fname):
        """3.57: stary format taba -> dzisiejszy: lines bez "on" = wlaczone,
        pary [time, cmd] -> slownik, mod_ids jako lista -> string."""
        data = dict(data)
        if isinstance(data.get("mod_ids"), list):
            data["mod_ids"] = ",".join(str(m) for m in data["mod_ids"])
        lines = data.get("lines")
        if isinstance(lines, list):
            norm = []
            for l in lines:
                if isinstance(l, dict):
                    if "on" not in l:
                        l = dict(l)
                        l["on"] = True
                    norm.append(l)
                elif isinstance(l, (list, tuple)) and len(l) >= 2:
                    norm.append({"time": l[0], "cmd": l[1], "on": True})
            data["lines"] = norm
        if "lines" not in data:
            data["lines"] = []
        return data

    def _import_one_tab(self, data, fname):
        """Import jednego taba (woła go plugin „Konfiguracje”). Zwraca True, gdy tab powstał."""

        pwd, sec_note = "", self.tr("import_sec_none")
        _fd = os.path.dirname(fname)
        sec = (newest_matching(os.path.join(_fd, TAB_SEC_DIR_NAME),
                               "CONFIG_SECRET_RCON")
               or newest_matching(_fd, "CONFIG_SECRET_RCON"))  # 3.66: prefix (z nazwa i bez)
        if sec:
            try:
                with open(sec, "r", encoding="utf-8") as sf:
                    sd = json.load(sf)
                if isinstance(sd, dict) and sd.get("password"):
                    pwd = sd["password"]
                    sec_note = self.tr("import_sec_from")
            except Exception:
                pass
        if not pwd and data.get("password"):
            pwd = data.get("password") or ""
            sec_note = self.tr("import_sec_legacy")

        data = dict(data)
        data["password"] = pwd
        base = (data.get("name")
                or os.path.basename(os.path.dirname(fname))
                or "Import").strip() or "Import"
        # 3.47: czy backup lezy w SWOIM miejscu standardowym (taby/<mapa>/)?
        home_dir = os.path.join(TABS_DIR, sanitize_name(base))
        is_home = (os.path.normpath(os.path.dirname(fname))
                   == os.path.normpath(home_dir))
        name, i = base, 2
        while name in self.tabs:
            name = "%s (%d)" % (base, i)
            i += 1
        if name != base:
            # 3.47: tab juz dziala - jego backupy to i tak jego wlasna
            # rotacja; duplikat tylko na wyrazne "TAK"
            if not messagebox.askyesno(self.tr("import_dup_title"),
                                       self.tr("import_dup_ask",
                                               name=base, new=name),
                                       parent=self):
                return
        data["name"] = name

        self.add_server(name=name, config=data)
        tab = self.tabs[name]
        self.notebook.select(tab)

        # 3.50: weryfikacja listy modow z backupu wzgledem logu serwera
        log_ids = self._loaded_mods_from_log(tab.var_log.get().strip())
        if log_ids:
            cur = tab.get_effective_mod_ids()
            if sorted(cur) != sorted(log_ids):
                tab.var_tab_mods.set(",".join(log_ids))
                tab._refresh_badges()
                self.log(self.tr("import_mods_fixed", n=len(log_ids),
                                 ids=", ".join(log_ids)))
            else:
                self.log(self.tr("import_mods_ok", n=len(log_ids)))
        else:
            # serwer nie dziala / log milczy - flaga: zweryfikuj po starcie
            tab._mods_unverified = True
            self.log(self.tr("import_mods_unverified"))

        self.save_tab(tab, silent=True)
        self.save_tab_secrets(tab, silent=True)

        self.log(self.tr("import_ok", name=name, file=os.path.basename(fname)))
        self.log(sec_note)
        if name != base:
            self.log(self.tr("import_renamed", old=base, new=name))
        elif is_home:
            # 3.47: katalog pojawil sie po starcie programu - tab podciagniety
            # bez restartu; zapis identyczny = zero nowych plikow (dedupe)
            self.log(self.tr("import_home_note", dir=sanitize_name(base)))
        self.request_save()
        return True

    def _update_leds_frame(self):
        for child in self.frm_leds.winfo_children():
            child.destroy()
        self._leds.clear()
        self._chips = {}

        chips = []
        # 3.71: przycisk WYKRYJ (skan logow + dopasowanie CF)
        btn_w = ttk.Button(self.frm_leds, text=self.tr("wykryj"),
                           command=self._wykryj_mody, width=6)
        ToolTip(btn_w, self.tr("wykryj_tip"))
        chips.append(btn_w)
        # 3.71: plyta CF (dioda zyje z _cf_tick)
        cf = ttk.Frame(self.frm_leds)
        cf_led = Led(cf, size=10)
        cf_led.pack(side="left", padx=(0, 2))
        ttk.Label(cf, text="CF", font=("TkDefaultFont", 8, "bold")).pack(side="left")
        self._leds["__cf__"] = cf_led
        ToolTip(cf, self.tr("cf_tip_ok") if getattr(self, "_cf_st", "ok") == "ok"
                else self.tr("cf_tip_blad"))
        chips.append(cf)
        for name, tab in self.tabs.items():
            if tab.var_map_on.get():
                frm = ttk.Frame(self.frm_leds)
                led = Led(frm, size=12)
                led.pack(side="left", padx=(0, 3))
                txt = self._chip_label(name, tab)  # 3.73: status+NOWY+SONDA/WISI
                lbl = ttk.Label(frm, text=txt,
                                font=("TkDefaultFont", 8, "bold"))
                lbl.pack(side="left")
                # 3.71: kafelek klikalny -> wybor mapy
                def _wybierz(e, _n=name):
                    try:
                        self.notebook.select(self.tabs[_n])
                    except Exception:
                        pass
                for w in (frm, lbl, led):
                    try:
                        w.bind("<Button-1>", _wybierz)
                        w.configure(cursor="hand2")
                    except Exception:
                        pass
                tip = ToolTip(frm, self._chip_tip(tab._tail_status))
                self._leds[name] = led
                self._chips[name] = (lbl, tip)
                chips.append(frm)
        self.frm_leds.set_badges(chips)
        for name, tab in self.tabs.items():
            self._update_led_color(name, tab)

    def _chip_text(self, name, status):
        # 3.60: kafelek = nazwa + status SLOWAMI (ten sam slownik co w tabie)
        return "%s \u00b7 %s" % (name, self.tr("st_" + (status or "unknown")))

    def _chip_label(self, name, tab):
        """3.73: pelna etykieta kafelka: status + [NOWY] + [SONDA]/[WISI!]
        (stan diagnozy straznika widoczny na pasku - raport admina 3.73)."""
        txt = self._chip_text(name, tab._tail_status)
        if getattr(tab, "_mods_unverified", False):
            txt += " [" + self.tr("nowy_chip") + "]"
        w = getattr(tab, "_wisi_st", 0)
        if w == 1:
            txt += " [" + self.tr("sonda_chip") + "]"
        elif w == 2:
            txt += " [" + self.tr("wisi_chip") + "]"
        return txt

    def _chip_tip(self, status):
        return self.tr("tip_map_" + (status or "unknown"))

    def _update_led_color(self, name, tab):
        status = tab._tail_status  # 3.73: bierzemy z taba (etykieta z SONDA/WISI)
        led = self._leds.get(name)
        chip = getattr(self, "_chips", {}).get(name)
        if not led and not chip:
            return
        colors = {
            "starting": "#b07000",
            "loading_mods": "#b07000",
            "engine": "#b07000",
            "ready": "#207020",
            "crash": "#b00020",
            "offline": "#b00020",
            "unknown": "#555555",
        }
        kol = colors.get(status, "#555555")
        if led:
            led.set_color(kol)
        if chip:
            lbl, tip = chip
            try:
                lbl.configure(text=self._chip_label(name, tab), foreground=kol)
                tip.text = self._chip_tip(status)
            except Exception:
                pass

    def rename_server(self, tab):
        from tkinter import simpledialog
        if self.restart_active or self.watch_active:
            messagebox.showwarning(
                self.tr("app_title"),
                t("Nie można zmieniać nazwy mapy podczas procedury ani oczekiwania na powrót.",
                  "A map cannot be renamed during a procedure or while waiting for a map to come back."),
                parent=self)
            return
        old_name = tab.name
        new_name = simpledialog.askstring(self.tr("rename_title"), self.tr("rename_prompt"), initialvalue=old_name, parent=self)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showerror("", self.tr("rename_err_empty"))
            return
        if new_name == old_name:
            return
        if new_name in self.tabs:
            messagebox.showerror("", self.tr("server_exists"))
            return
        # Do not overwrite an orphaned alert under the destination name.
        alarm_keys = ("return_failures", "rcon_failures")
        if any(new_name in self.config_data.get(key, {}) for key in alarm_keys):
            messagebox.showerror("", t("Nazwa docelowa ma zapisany alarm. Wybierz inną nazwę.",
                                       "The destination name has a saved alert. Choose another name."))
            return
        if getattr(self, "plugin_host", None):
            rcon_plugin = self.plugin_host.get("rcon_admin")
            if rcon_plugin and not rcon_plugin.prepare_tab_rename(tab):
                return

        old_safe = sanitize_name(old_name)
        new_safe = sanitize_name(new_name)
        old_dir = os.path.join(TABS_DIR, old_safe)
        new_dir = os.path.join(TABS_DIR, new_safe)

        same_dir = (os.path.normcase(os.path.abspath(old_dir)) ==
                    os.path.normcase(os.path.abspath(new_dir)))
        if not same_dir and os.path.exists(new_dir):
            messagebox.showerror("", t("Docelowy katalog mapy już istnieje: ",
                                       "The target map folder already exists: ") + new_dir)
            return

        old_alarms = {key: copy.deepcopy(self.config_data.get(key, {})) for key in alarm_keys}
        old_pending = copy.deepcopy(self.pending_updates)
        old_server_files = dict(self.server_files)
        old_dir_existed = os.path.isdir(old_dir)
        notebook_index = next((idx for idx in range(self.notebook.index("end"))
                               if self.notebook.tab(idx, "text") == old_name), None)

        # Rename is one transaction from the operator's perspective. Backups are
        # temporary and include both the map directory and global pending state.
        with tempfile.TemporaryDirectory(prefix="asaonly-rename-") as txn:
            map_backup = os.path.join(txn, "map")
            config_backup = os.path.join(txn, "global-config")
            config_existed = os.path.isdir(CONFIG_DIR)
            if old_dir_existed:
                shutil.copytree(old_dir, map_backup)
            if config_existed:
                shutil.copytree(CONFIG_DIR, config_backup)
            try:
                if old_dir_existed:
                    if not same_dir:
                        os.rename(old_dir, new_dir)
                    migrate_old_base(new_dir, tab_cfg_base(old_name),
                                     new_dir, tab_cfg_base(new_name))
                    migrate_old_base(os.path.join(new_dir, TAB_SEC_DIR_NAME),
                                     tab_sec_base(old_name),
                                     os.path.join(new_dir, TAB_SEC_DIR_NAME),
                                     tab_sec_base(new_name))
                else:
                    os.makedirs(new_dir)

                self.tabs.pop(old_name)
                self.tabs[new_name] = tab
                tab.name = new_name
                rename_pending_target(self.pending_updates, old_name, new_name)
                for key in alarm_keys:
                    alarms = self.config_data.get(key, {})
                    if old_name in alarms:
                        alarms[new_name] = alarms.pop(old_name)
                if notebook_index is not None:
                    self.notebook.tab(notebook_index, text=new_name)
                self.server_files.pop(old_name, None)
                self.server_files[new_name] = new_dir

                if not self.save_tab(tab, silent=True):
                    raise OSError(t("nie udało się zapisać konfiguracji przemianowanej mapy",
                                    "could not save the configuration of the renamed map"))
                if not save_versioned(CONFIG_DIR, CONFIG_BASE, self._global_config_data()):
                    raise OSError(t("nie udało się zapisać globalnej konfiguracji i pendingów",
                                    "could not save the global configuration and pending updates"))
            except Exception as exc:
                rollback_errors = []
                try:
                    self.tabs.pop(new_name, None)
                    self.tabs[old_name] = tab
                    tab.name = old_name
                    self.pending_updates[:] = old_pending
                    self.config_data.update(old_alarms)
                    self.server_files.clear()
                    self.server_files.update(old_server_files)
                    if notebook_index is not None:
                        self.notebook.tab(notebook_index, text=old_name)
                except Exception as rollback_exc:
                    rollback_errors.append(t("pamięć/UI: %s", "memory/UI: %s") % rollback_exc)

                # Attempt every restore step even if an earlier one fails. Never
                # replace the original error with a silent rollback exception.
                try:
                    if same_dir:
                        if os.path.isdir(old_dir):
                            shutil.rmtree(old_dir)
                    elif os.path.isdir(new_dir):
                        shutil.rmtree(new_dir)
                    if old_dir_existed:
                        shutil.copytree(map_backup, old_dir)
                except Exception as rollback_exc:
                    rollback_errors.append(t("katalog mapy: %s", "map folder: %s") % rollback_exc)
                try:
                    if os.path.isdir(CONFIG_DIR):
                        shutil.rmtree(CONFIG_DIR)
                    if config_existed:
                        shutil.copytree(config_backup, CONFIG_DIR)
                except Exception as rollback_exc:
                    rollback_errors.append(t("konfiguracja globalna: %s",
                                             "global configuration: %s") % rollback_exc)
                try:
                    self._refresh_return_alarm()
                    self._update_leds_frame()
                except Exception as rollback_exc:
                    rollback_errors.append(t("odświeżenie UI: %s", "UI refresh: %s") % rollback_exc)
                details = (t("\nRollback częściowo nieudany: ", "\nRollback partly failed: ")
                           + "; ".join(rollback_errors) if rollback_errors else
                           t("\nPrzywrócono pamięć, pendingi i pliki.",
                             "\nMemory, pending updates and files were restored."))
                messagebox.showerror(
                    "", t("Nie zmieniono nazwy mapy. Błąd: %s%s",
                          "The map was not renamed. Error: %s%s") % (exc, details))
                return

        if getattr(self, "plugin_host", None):
            self.plugin_host.call_hook("on_tab_renamed", old_name, new_name, tab)
        self._save_pending = False
        self._refresh_return_alarm()
        self.log(self.tr("rename_ok", old=old_name, new=new_name))
        self._update_leds_frame()

    def save_tab(self, tab, silent=False):
        """3.45: zapis do pliku 'CONFIG_MAP - zapis DD.MM.YYYY
        HH-MM-SS.json' w katalogu tabu; nowy plik tylko gdy tresc inna,
        rotacja 10 najnowszych (to jednoczesnie backupy)."""
        safe = sanitize_name(tab.name)
        t_dir = os.path.join(TABS_DIR, safe)
        new_data = tab.to_config()
        new_data["name"] = tab.name
        ok = save_versioned(t_dir, tab_cfg_base(tab.name), new_data)  # 3.64
        self.server_files[tab.name] = t_dir
        if ok:
            # V3.85.3: ta mapa jest zapisana — znacznik zmian i pytanie przy
            # zamykaniu porównują od teraz z tym zapisem.
            zapisane = self.__dict__.get("_saved_tabs")
            if isinstance(zapisane, dict):
                migawka = tab.to_config()
                migawka["_pw"] = tab.var_pass.get()
                zapisane[tab.name] = migawka
            if not silent:
                self.log(self.tr("tab_saved", name=tab.name))
        else:
            self.log(self.tr("save_err") + f" {tab.name}")
        return bool(ok)

    def save_tab_secrets(self, tab, silent=False):
        """3.43/3.45: haslo RCON taba w osobnym pliku sekretow (wersjonowanym)."""
        safe = sanitize_name(tab.name)
        t_dir = os.path.join(TABS_DIR, safe)
        s_dir = os.path.join(t_dir, TAB_SEC_DIR_NAME)  # 3.64: podkatalog
        data = {"password": tab.var_pass.get()}
        ok = save_versioned(s_dir, tab_sec_base(tab.name), data)  # 3.66
        if ok:
            if not silent:
                self.log(self.tr("tab_secret_saved", name=tab.name, dir=safe))
        else:
            self.log(self.tr("save_err") + f" secrets/{tab.name}")
        return bool(ok)

    def save_secrets(self, silent=False):
        data = {"api_key": self.var_api_key.get().strip()}
        ok = save_versioned(SECRET_API_DIR, SECRETS_BASE, data)  # 3.64
        if ok:
            if not silent:
                self.log(self.tr("secrets_ok"))
        else:
            self.log(self.tr("save_err") + " secrets")
        return bool(ok)

    def _global_config_data(self):
        return {
            "lang": self.lang,
            "interval": int(self.var_interval.get().strip() or DEFAULT_CHECK_INTERVAL),
            "cf_delay": float(self.var_cf_delay.get().strip() or CF_REQUEST_DELAY),
            "mod_wait_min": self._mod_wait_minutes(),
            "pad_archive_limit_mib": self.__dict__.get("pad_archive_limit_mib", 2048),
            "watch_timeout_min": int(self.var_watch.get().strip() or DEFAULT_WATCH_TIMEOUT),
            "auto_rcon": bool(self.auto_rcon.get()),
            "pending_updates": copy.deepcopy(self.pending_updates),
            "return_failures": copy.deepcopy(self.config_data.get("return_failures", {})),
            "rcon_failures": copy.deepcopy(self.config_data.get("rcon_failures", {})),
            # procedure_run is intentionally excluded: frequent command-boundary
            # checkpoints live in PROCEDURE_RUN_STATE.json and must not rotate
            # ordinary configuration backups.
            "known_versions": dict(self.known_versions),
            "mod_names": dict(self.mod_names),
            "mod_pages": dict(self.mod_pages),
            "mods_disabled": list(self.monitor_off),
            "plugins": copy.deepcopy(self.config_data.get("plugins", {})),
            # V3.81: inteligentna kolejka
            "czasy_startu": copy.deepcopy(self.config_data.get("czasy_startu", {})),
            "pusty_serwer_od_razu": bool(self.config_data.get("pusty_serwer_od_razu", True)),
            "listplayers_pusto": wzorce_pusto_z_konfiguracji(
                self.config_data.get("listplayers_pusto")),
            "log_core_w": self._core_w,
            "mods_w": self._panel_w["mods"],
            "mods_open": bool(self._win_open["mods"]),
            "mods_x": self._win_pos["mods"][0],
            "mods_y": self._win_pos["mods"][1]
        }

    def save_global_state(self):
        """Persist coordinator/pending state without rewriting every map or secret."""
        ok = bool(save_versioned(CONFIG_DIR, CONFIG_BASE, App._global_config_data(self)))
        if not ok:
            self._save_pending = True
            self.log(self.tr("save_err"))
        return ok

    def save_config(self, silent=False):
        results = [App.save_global_state(self), App.save_procedure_state(self)]

        for tab in self.tabs.values():
            results.append(self.save_tab(tab, silent=True))
            results.append(self.save_tab_secrets(tab, silent=True))

        results.append(self.save_secrets(silent=True))
        ok = all(result is not False for result in results)

        if ok:
            self._save_pending = False
            if not silent:
                self.log(self.tr("save_ok"))
        else:
            self._save_pending = True
            self.log(self.tr("save_err"))
        return ok

    def _build_cfg_snapshot(self):
        return (self.lang, self.var_interval.get(), self.var_cf_delay.get(), self.var_watch.get(), self.auto_rcon.get(), self._mod_wait_minutes(), self.__dict__.get("pad_archive_limit_mib", 2048))

    def _build_sec_snapshot(self):
        return self.var_api_key.get()

    def _build_tabs_snapshot(self):
        snapshot = {}
        for k, tab in self.tabs.items():
            snapshot[k] = tab.to_config()
            snapshot[k]["_pw"] = tab.var_pass.get()  # 3.43: haslo poza to_config
        return snapshot

    def request_save(self):
        self._save_pending = True

    def _tab_niezapisany(self, tab):
        """V3.85.3: czy mapa ma zmiany względem ostatniego zapisu (bez hasła RCON)."""
        zapisany = dict((self.__dict__.get("_saved_tabs") or {}).get(tab.name) or {})
        zapisany.pop("_pw", None)
        return tab.to_config() != zapisany

    # ------------------------------------------------------------------ Pętla Monitorowania (Tick)
    def _tick(self):
        # Jedyny punkt wykonywania callbacków przekazanych przez workery.
        # Tk.after/after_idle również są wywołaniami Tcl i nie wolno ich
        # uruchamiać bezpośrednio z obcego wątku.
        for _ in range(1000):
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            if self._destroying:
                continue
            try:
                callback()
            except Exception as exc:
                self.log_warn(t("Błąd callbacku UI: %s", "UI callback error: %s") % exc)

        # 3.42: Dziennik zdarzen zyje w KONSOLI (okno logow usuniete).
        # Konsumpcja kolejki w glownym watku (Thread-Safe) i wydruk batchem.
        self._oproznij_dziennik()

        if self._destroying:
            return

        # 3.71: monitor ogolny (procesy+porty, cykl 10 s w watku) + CF + auto-tura
        if not hasattr(self, "_mon"):
            self._monitor_init()
        teraz_m = time.time()
        if not self._mon_busy and teraz_m >= self._mon_next:
            self._mon_busy = True
            self._mon_next = teraz_m + MONITOR_TICK_S
            threading.Thread(target=self._monitor_worker, daemon=True).start()
        self._cf_tick(teraz_m)
        self._auto_next_tick(teraz_m)
        if hasattr(self, "plugin_host"):
            self.plugin_host.tick(teraz_m)

        # 3.42: siatka bezpieczenstwa diod tabow (co ~2 s, tanie refresh)
        self._badge_tick = getattr(self, "_badge_tick", 0) + 1
        if self._badge_tick >= 4:
            self._badge_tick = 0
            for tab in self.tabs.values():
                tab._refresh_badges()
                tab._odswiez_zapis()          # V3.85.3: znacznik niezapisanych zmian mapy

        for name, tab in self.tabs.items():
            self._update_led_color(name, tab)

        if self.restart_active:
            self._tick_restart_timeline()

        if self.watch_active:
            self._tick_return_watch()

        now = time.time()
        if not self.check_in_progress and now >= self.next_check:
            self.check_now()

        self._blink = not self._blink
        self._update_pending_ui_blink()

        # 3.71: id zapamietane -> _on_close robi after_cancel (po destroy
        # timer wybuchal w nastepnej instancji Tk: "invalid command name
        # ..._tick"; widoczne w fuzz 10-seedowym, seed 3)
        self._tick_after = self.after(500, self._tick)

    # ===================== 3.71: MASZYNA (MAPA-LOGIKI) =====================
















    def _update_pending_ui_blink(self):
        if self.check_in_progress:
            lbl_txt = self.tr("st_checking") + (" •" if self._blink else "  ")
            self.lbl_status.configure(text=lbl_txt, foreground="#007acc")
        elif self.restart_active:
            dt = int(time.time() - self.restart_t0)
            self.lbl_status.configure(text=self.tr("st_restart") + f" (T+{dt}s)", foreground="#d9534f")
        elif self.watch_active:
            done_cnt = sum(1 for v in self.watch_maps.values() if v["done"])
            tot_cnt = len(self.watch_maps)
            self.lbl_status.configure(text=self.tr("watch_status_fmt", ready=done_cnt, total=tot_cnt), foreground="#e0a050")
        else:
            # 3.52: WIDOCZNY zegar - licznik do nastepnego automatycznego
            # sprawdzenia modow (string "st_next_check" istnial w slownikach
            # od dawna, ale nic go nie wyswietlalo - sierota). Pokazujemy
            # tylko, gdy jest co sprawdzac (sa mody).
            has_mods = any(t.get_effective_mod_ids()
                           for t in self.tabs.values() if t.var_map_on.get())
            if has_mods:
                poz = int(max(0, self.next_check - time.time()))
                cnt = "%d s" % poz  # 3.59: odliczanie w SEKUNDACH (user)
                self.lbl_status.configure(
                    text=self.tr("st_monitoring") + " · " +
                         self.tr("st_next_check") + cnt,
                    foreground="#207020")
            else:
                self.lbl_status.configure(text=self.tr("st_monitoring"),
                                          foreground="#207020")






    def _open_cf_api_keys(self):
        """3.56: przycisk Generator CF-API - otwiera strone kluczy."""
        webbrowser.open(CF_API_KEYS_URL)

    def _load_api_from_backup(self):
        """3.53: klucz API ze starego pliku sekretow (np. backup folderu
        albo dziedzictwo po reinstalacji)."""
        p = filedialog.askopenfilename(
            title=self.tr("api_from_backup"),
            filetypes=[("JSON", "*.json"), (self.tr("all_files"), "*.*")])
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as e:
            self.log(self.tr("api_backup_err", err=e))
            return
        key = ""
        if isinstance(data, dict):
            key = str(data.get("api_key", "") or "").strip()
        if not key:
            self.log(self.tr("api_backup_bad"))
            return
        self.var_api_key.set(key)
        self.log(self.tr("api_backup_ok", file=os.path.basename(p)))




    # ------------------------------------------------------------------ Procedura RCON









    def run_async(self, func, *args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        t.start()
        return t

    def post_ui(self, func):
        """Thread-safe handoff; Tk is touched only by the main `_tick`."""
        if not self._destroying:
            self._ui_queue.put(func)

    def log(self, text, tag=None):
        """3.39: Logowanie jest w 100% bezpieczne dla watkow (Queue)"""
        now = datetime.now().strftime("[%H:%M:%S] ")
        full_line = f"{now}{text}\n"

        self._log_buffer.append(full_line)
        while len(self._log_buffer) > 2000:
            self._log_buffer.pop(0)
        self._log_queue.put((full_line, tag))
        return full_line

    def log_warn(self, text):
        return self.log(text, "warn")

    def log_status(self, text, status, nazwa=None):
        tag = "st_ok" if status == "ready" else "st_bad" if status in ("crash", "offline") else "st_wait"
        if status == "offline" and nazwa is not None and self.mapa_w_restarcie(nazwa):
            tag = "st_wait"               # V3.86.2: OFFLINE po DoExit to plan, nie awaria
        return self.log(text, tag)

    def show_about(self):
        about_text = (
            f"{self.tr('about_app_name')}\n"
            f"{self.tr('about_version')}: {WERSJA_PROGRAMU}\n\n"
            f"{self.tr('about_concept')} {self.tr('about_concept_name')}\n"
            f"{self.tr('about_code')}\n"
            f"  • {self.tr('about_code_desc')}\n"
            f"  • {self.tr('about_code_claude')}\n\n"
            f"{self.tr('about_purpose')}\n\n"
            f"{self.tr('about_free')}\n"
            f"{self.tr('about_joke')}"
        )
        messagebox.showinfo(self.tr("about_title"), about_text, parent=self)

    def _ask_close_unsaved(self):
        """3.70: własne TRZY przyciski z jasnymi opisami (zgłoszenie
        usera: przyciski mają same mówić, co robią — zamiast
        ogólnych Tak/Nie/Anuluj i legendy w treści).
        Zwraca: 'save' / 'nosave' / None (= nie zapisuj i nie zamykaj)."""
        dlg = tk.Toplevel(self)
        dlg.title(self.tr("unsaved_title"))
        dlg.resizable(False, False)
        dlg.transient(self)
        wynik = {"odp": None}
        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=self.tr("unsaved_msg"), wraplength=330,
                  justify="left").pack(fill="x", pady=(0, 12))

        def wybierz(odp):
            wynik["odp"] = odp
            dlg.destroy()

        for klucz, odp in (("unsaved_btn_save", "save"),
                           ("unsaved_btn_nosave", "nosave"),
                           ("unsaved_btn_stay", None)):
            ttk.Button(frm, text=self.tr(klucz),
                       command=lambda o=odp: wybierz(o)).pack(
                           fill="x", ipady=4, pady=3)
        dlg.protocol("WM_DELETE_WINDOW", lambda: wybierz(None))  # X = zostań
        dlg.bind("<Escape>", lambda e: wybierz(None))            # Esc = zostań
        dlg.grab_set()
        dlg.wait_window()
        return wynik["odp"]

    def _on_close(self):
        if self.restart_active:
            if not messagebox.askyesno(self.tr("app_title"), self.tr("close_warn"), parent=self):
                return

        rcon_plugin = (self.plugin_host.get("rcon_admin")
                       if getattr(self, "plugin_host", None) else None)
        rcon_unsaved = bool(rcon_plugin and rcon_plugin.has_unsaved_editor())
        cfg_snap = self._build_cfg_snapshot()
        sec_snap = self._build_sec_snapshot()
        tabs_snap = self._build_tabs_snapshot()
        zapisz = True  # 3.69: bez pytania (czyste zamkniecie) = zapisz jak dotad

        if (cfg_snap != self._saved_cfg or
            sec_snap != self._saved_sec or
            tabs_snap != self._saved_tabs or
            self._save_pending or rcon_unsaved):

            # 3.70: własny dialog z trzema JASNYMI przyciskami (3.69 miao
            # ogólne Tak/Nie/Anuluj). None = zostań; 'nosave' = zamknij
            # bez zapisywania (także geometrii okna); 'save' = zapisz wszystko.
            odp = self._ask_close_unsaved()
            if odp is None:              # "Nie zapisuj i nie zamykaj"
                return
            zapisz = (odp == "save")     # 'nosave' = zamknij bez zapisywania
        if zapisz and rcon_unsaved and not rcon_plugin.save_open_editor():
            return
        if zapisz:
            try:
                self._win_open["mods"] = self.win_mods.winfo_viewable()
                self._save_win_pos("mods", self.win_mods)
                if not self.save_config(silent=True):
                    messagebox.showerror(self.tr("app_title"), self.tr("save_err"), parent=self)
                    return
            except Exception as exc:
                self.log_warn(t("Błąd zapisu przy zamykaniu: %s", "Save error while closing: %s") % exc)
                messagebox.showerror(self.tr("app_title"), self.tr("save_err"), parent=self)
                return

        self._zamknij_teraz()

    def _oproznij_dziennik(self):
        """Linie z kolejki dziennika: do konsoli (z kolorami) i do pliku (bez kolorów).

        V3.85.2: bez pisania do konsoli z wątku okna (asaonly/konsola.py);
        V3.86.2: plik dziennika też pisze osobny wątek (asaonly/dziennik_plik.py)."""
        batch = []
        czyste = []
        while not self._log_queue.empty():
            try:
                line, tag = self._log_queue.get_nowait()
            except queue.Empty:
                break
            czyste.append(line)
            if self._ansi and tag in TAG_ANSI:
                batch.append(TAG_ANSI[tag] + line.rstrip("\n") + "\x1b[0m\n")
            else:
                batch.append(line)
        if batch:
            self._konsola.pisz("".join(batch))
            plik = getattr(self, "_dziennik_plik", None)
            if plik is not None:
                plik.pisz("".join(czyste))

    def _zamknij_teraz(self):
        """Zamyka program natychmiast i niczego już nie zapisuje.

        V3.83: woła to także plugin „Konfiguracje” po przywróceniu backupu —
        stan w pamięci jest wtedy STARY, a jego zapis nadpisałby przywrócone pliki.
        """
        self._destroying = True

        try:
            self.after_cancel(getattr(self, "_tick_after", None))
        except Exception:
            pass

        for tab in self.tabs.values():
            tab._stop_threads()

        if getattr(self, "plugin_host", None):
            self.plugin_host.stop_all()
        konsola = getattr(self, "_konsola", None)
        if konsola is not None:
            self._oproznij_dziennik()     # linie z zamykania pluginów też do konsoli i pliku
            konsola.zamknij(1.0)          # ostatnie linie dziennika, o ile konsola nie stoi
        plik = getattr(self, "_dziennik_plik", None)
        if plik is not None:
            plik.zamknij(2.0)
        przywroc_tryb(getattr(self, "_tryb_konsoli", None))
        self.destroy()

    def report_callback_exception(self, exc, val, tb):
        """V3.85.2: błąd w obsłudze zdarzenia okna trafia do dziennika i asa_debug.log.

        Domyślnie Tk drukuje go na stderr z wątku okna — przy zaznaczeniu
        w konsoli to też zatrzymałoby okno."""
        try:
            opis = "".join(traceback.format_exception(exc, val, tb))
        except Exception:
            opis = repr(val)
        write_debug_log(t("Błąd w obsłudze zdarzenia okna:\n", "Error in a window event handler:\n") + opis)
        self.log_warn(t("Błąd w obsłudze zdarzenia okna: %s (szczegóły: asa_debug.log)",
                        "Error in a window event handler: %s (details: asa_debug.log)") % val)


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        write_debug_log(f"CRITICAL APP FAILURE: {e}\n{traceback.format_exc()}")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            t("ASA Mod Refresher - Błąd Krytyczny", "ASA Mod Refresher - Critical Error"),
            t("Program napotkał problem podczas startu.\n\nBłąd: %s\n\n"
              "Szczegóły zostały zapisane w asa_debug.log",
              "The program ran into a problem during startup.\n\nError: %s\n\n"
              "Details were saved to asa_debug.log") % e)
        root.destroy()
