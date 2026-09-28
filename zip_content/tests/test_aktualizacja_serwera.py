# -*- coding: utf-8 -*-
"""V3.86: plugin 88 „Aktualizacja serwera (SteamCMD)” — cache, decyzje, kolejka, podmiana plików.

Najważniejsze (tu padało 25.09.2026): SteamCMD NIGDY nie jest uruchamiany na
katalogu mapy, a porażka pobierania nie restartuje żadnego serwera.
"""
import importlib.util
import os
import pathlib
import shutil
import tempfile
import time
import types
import unittest
from unittest.mock import patch

from asaonly import steam_serwer as S
from asaonly import synchronizacja as SYNC

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
_spec = importlib.util.spec_from_file_location("aktualizacja_serwera_test",
                                               ROOT / "PLUGINY" / "88_aktualizacja_serwera.py")
modul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(modul)

STARY, NOWY, NOWSZY = 25489097, 25535041, 25600000
GID = {STARY: "8699400601246504390", NOWY: "6068136383897274900", NOWSZY: "1111111111111111111"}
REL_EXE = os.path.join("ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe")
REL_PAK = os.path.join("ShooterGame", "Content", "Paks", "ShooterGame-WindowsServer.pak")
REL_STALY = os.path.join("Engine", "Binaries", "ThirdParty", "stale.dll")


def manifest(buildid, gid=None, stan=4):
    return ('"AppState"\n{\n\t"appid"\t\t"2430930"\n\t"StateFlags"\t\t"%d"\n\t"buildid"\t\t"%d"\n'
            '\t"InstalledDepots"\n\t{\n\t\t"2430931"\n\t\t{\n\t\t\t"manifest"\t\t"%s"\n\t\t}\n\t}\n}\n'
            % (stan, buildid, gid or GID.get(buildid, "1")))


def zapisz(katalog, rel, tresc, mtime=None):
    sciezka = os.path.join(katalog, rel)
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    with open(sciezka, "wb" if isinstance(tresc, bytes) else "w") as fh:
        fh.write(tresc)
    if mtime is not None:
        os.utime(sciezka, (mtime, mtime))


def czytaj(katalog, rel):
    with open(os.path.join(katalog, rel), "rb") as fh:
        return fh.read()


def instalacja(katalog, buildid, mtime=None):
    """Pliki serwera danego buildu (treść zależy od buildu) + appmanifest."""
    mtime = mtime or (1700000000 + buildid % 1000)
    zapisz(katalog, REL_EXE, ("EXE-%d" % buildid).encode(), mtime)
    zapisz(katalog, REL_PAK, ("PAK-%d-" % buildid).encode() * (1 + buildid % 3), mtime)
    zapisz(katalog, REL_STALY, b"STALY-PLIK", 1600000000)
    zapisz(katalog, S.sciezka_manifestu(""), manifest(buildid), mtime)


def api_odpowiedz(buildid):
    return {"status": "success", "data": {"2430930": {"depots": {
        "branches": {"public": {"buildid": str(buildid), "timeupdated": "1790364583"}},
        "2430931": {"manifests": {"public": {"gid": GID.get(buildid, "1"), "size": "4096"}}}}}}}


USER_CONFIG = ('<?xml version="1.0" encoding="utf-8"?>\n<configuration><userSettings>'
               '<ASADedicatedManager.Properties.Settings>'
               '<setting name="AutoCheckUpdates" serializeAs="String"><value>%s</value></setting>'
               '<setting name="CacheUpdatePath" serializeAs="String"><value>%s</value></setting>'
               '</ASADedicatedManager.Properties.Settings></userSettings></configuration>\n')


class Api(object):
    def __init__(self, manager=True, serwery=None):
        self.manager = manager
        self.serwery = dict(serwery or {})          # pid -> ścieżka exe
        self.licznik = {}

    def procesy(self, nazwa):
        if nazwa == "ASADedicatedManager.exe":
            return [10] if self.manager else []
        return list(self.serwery)

    def czas_startu(self, pid):
        return 1

    def zyje(self, pid, start=None):
        return pid == 10 and self.manager or pid in self.serwery

    def dostep_wstrzymania(self, pid):
        pass

    def sciezka_exe(self, pid):
        return self.serwery[pid]

    def zamroz(self, pid):
        self.licznik[pid] = self.licznik.get(pid, 0) + 1

    def odmroz(self, pid):
        self.licznik[pid] = self.licznik.get(pid, 0) - 1

    def uruchom_straznika(self, sciezka):
        pass


class App(object):
    def __init__(self):
        self.restart_active = False
        self.zlecenia = []
        self.uruchomienia = []
        self.odwolane = []
        self.czekajace = {}

    def zlec_restart(self, nazwy, powod, wlasciciel):
        self.zlecenia.append((list(nazwy), powod, wlasciciel))
        return list(nazwy)

    def _zlecenia(self):
        return self.czekajace

    def odwolaj_zlecenia(self, wlasciciel):
        self.odwolane.append(wlasciciel)
        return []

    def _exec_pending(self, manual=False):
        self.uruchomienia.append(manual)


class Core(object):
    def __init__(self, app, tabs=None):
        self.app = app
        self._tabs = dict(tabs or {})
        self.logi = []
        self.cfg = {}

    def log(self, x, tag=None): self.logi.append(str(x))
    def warn(self, x): self.logi.append("WARN " + str(x))
    def set_indicator(self, *a): self.wskaznik = a
    def set_plugin_toggle(self, *a): pass
    def plugin_config(self, nazwa): return dict(self.cfg)
    def save_plugin_config(self, nazwa, wartosc): self.cfg = dict(wartosc)
    def application(self): return self.app
    def post_ui(self, cb): cb()
    def run_async(self, fn, *a): fn(*a)
    def tabs(self): return dict(self._tabs)


class Baza(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        serwery = os.path.join(self.tmp, "ARKservers")
        self.cache = os.path.join(serwery, "ASA UPDATES REFRESHER")
        self.katalogi = {}
        tabs = {}
        for nazwa, build in (("Ragnarok", STARY), ("Genesis", STARY), ("Extinction", NOWY)):
            katalog = os.path.join(serwery, nazwa + "_WP")
            instalacja(katalog, build, mtime=1690000000)
            os.makedirs(os.path.join(katalog, "ShooterGame", "Saved", "Logs"))
            zapisz(katalog, os.path.join("ShooterGame", "Saved", "SavedArks", "swiat.ark"), b"SWIAT")
            self.katalogi[nazwa] = katalog
            tabs[nazwa] = types.SimpleNamespace(
                name=nazwa, enabled=True, rcon_port=str(27020 + len(tabs)), status="ready",
                log_path=os.path.join(katalog, "ShooterGame", "Saved", "Logs"))
        # Updater managera wyłączony (jak po przejściu na refresher).
        self.local = os.path.join(self.tmp, "local")
        self.user_config(False)
        env = patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        env.start()
        self.addCleanup(env.stop)
        self.app = App()
        self.core = Core(self.app, tabs)
        katalog_programu = os.path.join(self.tmp, "program")
        os.makedirs(os.path.join(katalog_programu, "CONFIG_PROGRAM"))
        self.steamcmd = os.path.join(katalog_programu, "STEAMCMD", "steamcmd.exe")
        patchery = [patch.object(modul.Wtyczka, "_katalog_programu", staticmethod(lambda: katalog_programu)),
                    patch.object(modul.siec, "steam_api_info", side_effect=self.api_steam)]
        for p in patchery:
            p.start()
            self.addCleanup(p.stop)
        self.p = modul.Wtyczka()
        self.p.start(self.core)
        self.api = Api()
        self.p.zamrazarka.api = self.api
        self.api_build = NOWY
        self.api_blad = None
        self.wywolania = []
        self.content_log = ""
        self.steamcmd_wynik = "ok"
        for nazwa, cel in (("_zapewnij_steamcmd", lambda cfg: (self.steamcmd, None)),
                           ("_uruchom", self.falszywy_steamcmd),
                           ("_content_log", lambda exe: self.content_log)):
            p = patch.object(self.p, nazwa, side_effect=cel)
            p.start()
            self.addCleanup(p.stop)

    def user_config(self, auto_check, cache_managera="C:\\ARKservers\\ASA UPDATES"):
        kat = os.path.join(self.local, "ASADedicatedManager", "ASADedicatedManager.exe_Url_x", "1.0.0.0")
        os.makedirs(kat, exist_ok=True)
        with open(os.path.join(kat, "user.config"), "w", encoding="utf-8") as fh:
            fh.write(USER_CONFIG % ("True" if auto_check else "False", cache_managera))

    def api_steam(self, url, timeout=15):
        if self.api_blad is not None:
            raise self.api_blad
        return api_odpowiedz(self.api_build)

    def falszywy_steamcmd(self, argv, limit, na_start=None, na_linie=None):
        """SteamCMD: app_update do cache (tylko tam wolno) albo app_info (sprawdzenie)."""
        self.wywolania.append(list(argv))
        if "+force_install_dir" not in argv:
            return 0, "", False
        katalog = argv[argv.index("+force_install_dir") + 1]
        self.assertEqual(katalog, self.cache, "SteamCMD poza cache (na mapie!)")
        if na_linie:
            na_linie(" Update state (0x61) downloading, progress: 55.00 (1 / 2)")
        if self.steamcmd_wynik == "ok":
            instalacja(katalog, self.api_build)
            return 0, "Success! App '2430930' fully installed.", False
        if self.steamcmd_wynik == "odmowa_raz":
            self.steamcmd_wynik = "ok"
            with open(FIXTURES / "content_log_access_denied.txt", encoding="utf-8") as fh:
                self.content_log = fh.read()
            return 8, "Error! App '2430930' state is 0x6 after update job.", False
        if self.steamcmd_wynik in ("konfiguracja_raz", "konfiguracja_zawsze"):
            # 26.09: świeżo pobrany SteamCMD, pusta appcache (prawdziwe linie).
            if self.steamcmd_wynik == "konfiguracja_raz":
                self.steamcmd_wynik = "ok"
            with open(FIXTURES / "content_log_missing_configuration.txt", encoding="utf-8") as fh:
                self.content_log = fh.read()
            return 8, "ERROR! Failed to install app '2430930' (Missing configuration)", False
        if self.steamcmd_wynik == "blad_bez_logu":
            self.content_log = "[2026-09-26 14:25:48] Client version: 1788292693\n"
            return 8, "Error! App '2430930' state is 0x202 after update job.", False
        with open(FIXTURES / "content_log_access_denied.txt", encoding="utf-8") as fh:
            self.content_log = fh.read()
        return 8, "Error! App '2430930' state is 0x6 after update job.", False

    def sprawdzenie(self, reczne=False, wymus=False, zrodlo="api"):
        self.assertTrue(self.p.sprawdz(reczne=reczne, wymus=wymus, zrodlo=zrodlo))

    def logi(self, tekst):
        return [x for x in self.core.logi if tekst in x]

    def pobrania(self):
        return [a for a in self.wywolania if "+app_update" in a]


class Cache(Baza):
    def test_nowy_build_najpierw_do_cache_serwery_nietkniete_potem_kolejka(self):
        self.sprawdzenie()
        self.assertEqual(len(self.pobrania()), 1)
        self.assertEqual(S.czytaj_lokalny(self.cache)[0]["buildid"], NOWY)
        self.assertTrue(self.logi("Cache: pierwsze pobranie serwera do"))
        self.assertTrue(self.logi("Cache: build %d gotowy" % NOWY))
        self.assertTrue(self.logi("cache: SteamCMD downloading 55%"))
        self.assertEqual(self.app.zlecenia, [(["Genesis", "Ragnarok"],
                                              "aktualizacja serwera ASA do buildu %d" % NOWY,
                                              "aktualizacja_serwera")])
        self.assertEqual(self.api.licznik, {})                    # manager nietknięty
        for nazwa in ("Ragnarok", "Genesis"):                    # mapy jeszcze stare
            self.assertEqual(S.czytaj_lokalny(self.katalogi[nazwa])[0]["buildid"], STARY)
        self.assertTrue(self.logi("Ragnarok: do buildu %d brakuje 2 z 3 plików" % NOWY))

    def test_blad_pobierania_bez_restartu_i_z_prawdziwym_powodem(self):
        self.steamcmd_wynik = "blad"
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia, [])
        self.assertEqual(self.api.licznik, {})
        ostrzezenie = self.logi("Cache: pobieranie NIEUDANE")
        self.assertEqual(len(ostrzezenie), 1)
        self.assertIn("Access Denied", ostrzezenie[0])
        self.assertIn("Serwery NIE były ruszane", ostrzezenie[0])
        # Następna próba dopiero po przerwie — nie co minutę.
        self.sprawdzenie()
        self.assertEqual(len(self.pobrania()), 1)
        self.sprawdzenie(reczne=True, wymus=True)                 # AKTUALIZUJ TERAZ — od razu
        self.assertEqual(len(self.pobrania()), 2)

    def test_missing_configuration_ponowienie_od_razu(self):
        """26.09 V3.86.0: pierwszy przebieg świeżo pobranego SteamCMD skończył się
        'Missing configuration', a następna próba była dopiero po 5 min."""
        self.steamcmd_wynik = "konfiguracja_raz"
        with patch.object(modul, "PRZERWA_BRAK_KONFIGURACJI_S", 0):
            self.sprawdzenie()
        self.assertEqual(len(self.pobrania()), 2)                  # druga próba w tym samym zadaniu
        self.assertEqual(len(self.logi("SteamCMD zgłosił 'Missing configuration'")), 1)
        self.assertTrue(self.logi("Ponawiam od razu (1/%d)" % modul.PONOWIENIA_BRAK_KONFIGURACJI))
        self.assertFalse(self.logi("Cache: pobieranie NIEUDANE"))
        self.assertTrue(self.logi("Cache: build %d gotowy" % NOWY))
        self.assertEqual(len(self.app.zlecenia), 1)
        self.assertEqual(self.api.licznik, {})                    # manager nietknięty

    def test_missing_configuration_uparcie_zwykla_przerwa_bez_restartu(self):
        self.steamcmd_wynik = "konfiguracja_zawsze"
        with patch.object(modul, "PRZERWA_BRAK_KONFIGURACJI_S", 0):
            self.sprawdzenie()
        prob = 1 + modul.PONOWIENIA_BRAK_KONFIGURACJI
        self.assertEqual(len(self.pobrania()), prob)
        self.assertEqual(self.app.zlecenia, [])
        self.assertEqual(self.api.licznik, {})
        ostrzezenie = self.logi("Cache: pobieranie NIEUDANE")
        self.assertEqual(len(ostrzezenie), 1)
        self.assertIn("Failed installing AppID 2430930 (Missing configuration)", ostrzezenie[0])
        self.assertIn("Następna próba za 5 min", ostrzezenie[0])
        with patch.object(modul, "PRZERWA_BRAK_KONFIGURACJI_S", 0):
            self.sprawdzenie()                                    # przerwa jak przy innych błędach
        self.assertEqual(len(self.pobrania()), prob)

    def test_bez_rozpoznanej_linii_content_log_mowi_to_wprost(self):
        # V3.86.0 pisało „brak wpisów w content_log.txt”, choć wpisy były.
        self.steamcmd_wynik = "blad_bez_logu"
        self.sprawdzenie()
        ostrzezenie = self.logi("Cache: pobieranie NIEUDANE")
        self.assertEqual(len(ostrzezenie), 1)
        self.assertIn("w ostatniej sesji content_log.txt brak rozpoznanej linii błędu", ostrzezenie[0])
        self.assertIn("state is 0x202", ostrzezenie[0])
        self.assertEqual(len(self.pobrania()), 1)                 # to nie 'Missing configuration'

    def test_odmowa_manifestu_cache_pobierany_od_zera(self):
        instalacja(self.cache, STARY)                             # cache od innego SteamCMD
        self.steamcmd_wynik = "odmowa_raz"
        self.sprawdzenie()
        self.assertEqual(len(self.pobrania()), 2)
        self.assertTrue(self.logi("Steam odmówił manifestu %s" % GID[STARY]))
        self.assertEqual(S.czytaj_lokalny(self.cache)[0]["buildid"], NOWY)
        self.assertEqual(len(self.app.zlecenia), 1)

    def test_steam_nowszy_niz_cache_mapy_czekaja(self):
        instalacja(self.cache, NOWY)
        self.api_build = NOWSZY
        self.steamcmd_wynik = "blad"
        self.sprawdzenie()
        # Mapy mogłyby dostać NOWY z cache, ale Steam ma już NOWSZY: czekają (jeden restart, nie dwa).
        self.assertEqual(self.app.zlecenia, [])

    def test_wszystko_aktualne_bez_pobierania_i_zlecen(self):
        instalacja(self.cache, NOWY)
        for nazwa in ("Ragnarok", "Genesis"):
            instalacja(self.katalogi[nazwa], NOWY)
        self.sprawdzenie()
        self.assertEqual(self.pobrania(), [])
        self.assertEqual(self.app.zlecenia, [])

    def test_cache_nie_jest_ruszany_w_trakcie_rundy(self):
        instalacja(self.cache, NOWY)
        self.app.czekajace = {"Ragnarok": {"wlasciciel": "aktualizacja_serwera"}}
        self.api_build = NOWSZY
        self.sprawdzenie()
        self.assertEqual(self.pobrania(), [])
        self.assertTrue(self.logi("po zakończeniu bieżącej rundy"))

    def test_pliki_jak_w_cache_tylko_appmanifest_bez_restartu(self):
        instalacja(self.cache, NOWY)
        instalacja(self.katalogi["Genesis"], NOWY)
        with open(S.sciezka_manifestu(self.katalogi["Genesis"]), "w", encoding="utf-8") as fh:
            fh.write(manifest(STARY))                             # np. po kopii managera bez manifestu
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Ragnarok"])
        self.assertEqual(S.czytaj_lokalny(self.katalogi["Genesis"])[0]["buildid"], NOWY)
        self.assertTrue(self.logi("Genesis: pliki już są jak w cache"))


class Blokady(Baza):
    def test_updater_managera_wlaczony_nic_nie_robi(self):
        self.user_config(True)
        self.sprawdzenie()
        self.assertEqual(self.pobrania(), [])
        self.assertEqual(self.app.zlecenia, [])
        ostrzezenie = self.logi("Aktualizacja wstrzymana")
        self.assertEqual(len(ostrzezenie), 1)
        self.assertIn("Enable automatic update checking", ostrzezenie[0])
        self.assertIn("STOP", self.core.wskaznik[1])
        self.sprawdzenie()                                        # bez spamu co minutę
        self.assertEqual(len(self.logi("Aktualizacja wstrzymana")), 1)

    def test_nie_wiem_czy_updater_managera_ale_dzialam(self):
        shutil.rmtree(os.path.join(self.local, "ASADedicatedManager"))
        self.sprawdzenie()
        self.assertEqual(len(self.logi("Nie wiem, czy updater managera jest wyłączony")), 1)
        self.assertEqual(len(self.app.zlecenia), 1)

    def test_cache_managera_nie_moze_byc_cache_refreshera(self):
        self.user_config(False, cache_managera=self.cache)
        self.sprawdzenie()
        self.assertEqual(self.pobrania(), [])
        self.assertTrue(self.logi("to jest cache managera"))

    def test_bez_managera_nie_ma_ogloszen_na_prozno(self):
        self.api.manager = False
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia, [])
        self.assertTrue(self.logi("nie działa"))

    def test_auto_wylaczone_tylko_recznie(self):
        self.p.cfg["auto"] = False
        self.sprawdzenie()
        self.assertEqual((self.pobrania(), self.app.zlecenia), ([], []))
        self.sprawdzenie(reczne=True)                             # SPRAWDŹ TERAZ — tylko sprawdza
        self.assertEqual((self.pobrania(), self.app.zlecenia), ([], []))
        self.sprawdzenie(reczne=True, wymus=True)                 # AKTUALIZUJ TERAZ
        self.assertEqual(len(self.pobrania()), 1)
        self.assertEqual(len(self.app.zlecenia), 1)
        self.assertEqual(self.app.uruchomienia, [True])           # ręcznie: kolejka rusza od razu

    def test_proby_z_v385_nie_blokuja_podmiany_z_cache(self):
        # Zapis z 25.09.2026: 3 próby SteamCMD na mapie na każdą mapę (stary mechanizm).
        self.core.cfg = {"enabled": True, "auto": True, "walidacja": True, "co_ile_min": 20,
                         "manager": "ASADedicatedManager.exe", "steamcmd": "",
                         "proby": {"Ragnarok|%d" % NOWY: [1.0, 2.0, 3.0],
                                   "Genesis 1|%d" % NOWY: [1.0, 2.0, 3.0]}}
        self.p.prepare(self.core)
        self.p.zamrazarka.api = self.api                      # prepare() tworzy nową zamrażarkę
        self.assertEqual(self.p.cfg["proby"], {})
        self.assertNotIn("co_ile_min", self.p.cfg)
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Genesis", "Ragnarok"])
        # Nowe próby (proby_v = 2) zostają po ponownym wczytaniu.
        self.core.cfg = dict(self.p.cfg, proby={"Ragnarok|%d" % NOWY: [1.0]})
        self.p.prepare(self.core)
        self.assertEqual(self.p.cfg["proby"], {"Ragnarok|%d" % NOWY: [1.0]})

    def test_limit_nieudanych_prob(self):
        self.p.cfg["proby"] = {"Ragnarok|%d" % NOWY: [1.0, 2.0, 3.0]}
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Genesis"])
        self.assertTrue(self.logi("3 nieudane próby podmiany plików"))

    def test_mapa_nie_gotowa_czeka(self):
        self.core._tabs["Genesis"].status = "starting"
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Ragnarok"])
        self.assertTrue(self.logi("Genesis: czeka z aktualizacją"))
        self.assertIsNone(self.p._zadanie)

    def test_wspolna_instalacja_nie_jest_aktualizowana(self):
        self.core._tabs["Genesis"].log_path = self.core._tabs["Ragnarok"].log_path
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia, [])
        self.assertTrue(self.logi("Genesis: ta sama instalacja serwera co Ragnarok"))
        self.assertEqual(self.p.przed_doexit("Ragnarok")[0], "blad")
        self.assertEqual(self.api.licznik, {})
        ile = len(self.core.logi)
        self.sprawdzenie()
        self.assertEqual([x for x in self.core.logi[ile:] if "ta sama instalacja" in x], [])

    def test_katalog_bez_appmanifest_jest_pomijany(self):
        os.remove(S.sciezka_manifestu(self.katalogi["Genesis"]))
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Ragnarok"])
        self.assertTrue(self.logi("Genesis: brak czytelnego appmanifest_2430930.acf"))


class Wykrywanie(Baza):
    def test_api_nie_odpowiada_zapasowo_steamcmd(self):
        self.api_blad = RuntimeError("network error: timed out")
        instalacja(self.cache, NOWY)
        with patch.object(self.p, "_zapytaj_steam",
                          return_value=({"buildid": NOWY, "manifest": GID[NOWY], "czas": 1}, "SteamCMD",
                                        None, "")) as zapytanie:
            self.sprawdzenie()
            self.assertTrue(self.p.api_awaria)
            self.assertTrue(self.logi("api.steamcmd.net nie odpowiada (network error: timed out)"))
            self.p.tik(time.time() + 1)                           # zapas: SteamCMD od razu
            zapytanie.assert_called_once()
            # API nadal leży: SteamCMD dalej co 5 min, nie co minutę.
            self.p._nastepne_api = 0
            self.p.tik(time.time())
            self.p.tik(time.time() + 1)
            zapytanie.assert_called_once()
            self.assertGreater(self.p._nastepne_steamcmd, time.time() + 4 * 60)
        self.assertEqual(self.p.zrodlo, "SteamCMD")
        # Cache (sprawdzony build) jest nowszy niż mapy — kolejka nie czeka na API.
        # Ponowne zlecenie tych samych map rdzeń łączy (słownik zleceń po nazwie mapy).
        self.assertTrue(self.app.zlecenia)
        self.assertEqual({tuple(z[0]) for z in self.app.zlecenia}, {("Genesis", "Ragnarok")})
        # API wraca — SteamCMD znowu tylko kontrolnie (raz na godzinę).
        self.api_blad = None
        self.p._nastepne_api = 0
        self.p.tik(time.time())
        self.assertFalse(self.p.api_awaria)
        self.assertGreater(self.p._nastepne_steamcmd, time.time() + modul.KONTROLA_STEAMCMD_S - 60)

    def test_api_429_czeka_ile_kaze(self):
        self.api_blad = modul.siec.ApiZajete("HTTP 429: Too Many Requests", 600)
        teraz = time.time()
        self.sprawdzenie()
        self.assertGreaterEqual(self.p._nastepne_api, teraz + 600)

    def test_tik_co_minute_api(self):
        self.p.tik(self.p._nastepne_api - 1)
        self.assertFalse(self.p._sprawdzanie)
        self.p.tik(self.p._nastepne_api + 0.1)
        self.assertEqual(len(self.pobrania()), 1)                 # API → cache → kolejka
        self.assertGreater(self.p._nastepne_api, time.time() + modul.API_CO_S - 5)


class Kolejka(Baza):
    def setUp(self):
        super().setUp()
        self.sprawdzenie()

    def test_przed_doexit_wstrzymuje_managera(self):
        self.assertEqual(self.p.przed_doexit("Ragnarok"), ("ok", ""))
        self.assertEqual(self.api.licznik, {10: 1})
        self.assertEqual(self.p._zadanie["cel"], NOWY)
        self.assertEqual(self.p.przed_doexit("Genesis")[0], "blad")    # jeden naraz
        self.p.doexit_nieudany("Ragnarok")
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertIsNone(self.p._zadanie)

    def test_zbedne_gdy_mapa_juz_ma_build_cache(self):
        instalacja(self.katalogi["Ragnarok"], NOWY)
        self.assertEqual(self.p.przed_doexit("Ragnarok")[0], "zbedne")
        self.assertEqual(self.api.licznik, {})

    def test_bez_planu_odmowa_bez_wstrzymania(self):
        self.p.plany.clear()
        kod, powod = self.p.przed_doexit("Ragnarok")
        self.assertEqual(kod, "blad")
        self.assertIn("brak aktualnego planu", powod)
        self.assertEqual(self.api.licznik, {})

    def test_za_malo_miejsca_odmowa(self):
        with patch.object(modul.Wtyczka, "_wolne_miejsce", staticmethod(lambda s: 0)):
            kod, powod = self.p.przed_doexit("Ragnarok")
        self.assertEqual(kod, "blad")
        self.assertIn("za mało miejsca", powod)
        self.assertEqual(self.api.licznik, {})

    def test_updater_managera_wlaczony_w_miedzyczasie(self):
        self.p.manager_upd = ("wlaczony", "w managerze włączone „Enable automatic update checking”", {})
        self.assertEqual(self.p.przed_doexit("Ragnarok")[0], "blad")
        self.assertEqual(self.api.licznik, {})

    def test_bez_doexit_manager_nie_wisi(self):
        self.p.przed_doexit("Ragnarok")
        self.p.tik(self.p._zadanie["t0"] + modul.ZAMROZENIE_BEZ_DOEXIT_S + 1)
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertIsNone(self.p._zadanie)

    def test_bezpiecznik_dziala_bez_watku_okna(self):
        with patch.object(modul, "ZAMROZENIE_BEZ_DOEXIT_S", 0.05):
            self.assertEqual(self.p.przed_doexit("Ragnarok"), ("ok", ""))
            z = self.p._zadanie
            koniec = time.time() + 5
            # Wznowienie poprzedza trwały checkpoint i callback kończący zadanie.
            while (self.api.licznik.get(10) != 0 or self.p._zadanie is not None) and time.time() < koniec:
                time.sleep(0.01)
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertIsNone(self.p._zadanie)
        self.assertTrue(self.logi("brak DoExit"))
        # Spóźniony wynik DoExit nie uruchamia już kopiowania przy działającym managerze.
        with patch.object(modul.SYNC, "wykonaj") as wykonaj:
            self.p._zadanie = z
            self.p.po_doexit("Ragnarok")
            wykonaj.assert_not_called()
        self.assertEqual(z["faza"], "anulowany")
        self.assertEqual(czytaj(self.katalogi["Ragnarok"], REL_EXE), ("EXE-%d" % STARY).encode())

    def test_wylaczenie_pluginu_wznawia_managera_i_odwoluje_zlecenia(self):
        self.assertEqual(self.p.przed_doexit("Ragnarok"), ("ok", ""))
        self.p.set_enabled(False)
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertIsNone(self.p._zadanie)
        self.assertEqual(self.app.odwolane, ["aktualizacja_serwera"])
        kod, powod = self.p.przed_doexit("Ragnarok")
        self.assertEqual(kod, "blad")
        self.assertIn("OFF", powod)
        self.p.set_enabled(True)
        self.assertEqual(self.p.przed_doexit("Ragnarok"), ("ok", ""))


class Podmiana(Baza):
    def setUp(self):
        super().setUp()
        self.sprawdzenie()
        self.assertEqual(self.p.przed_doexit("Ragnarok"), ("ok", ""))
        self.z = dict(self.p._zadanie)
        self.ragnarok = self.katalogi["Ragnarok"]

    def test_udana_podmiana(self):
        from asaonly import zamrazanie as Z
        prawdziwe = SYNC.wykonaj
        widziane = {}

        def wykonaj(*a, **kw):
            widziane["dzierzawa"] = Z.czytaj_dzierzawe(self.p.zamrazarka.sciezka)
            widziane["manager"] = dict(self.api.licznik)
            return prawdziwe(*a, **kw)
        with patch.object(modul.SYNC, "wykonaj", side_effect=wykonaj):
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda s: None)
        # W trakcie: manager wstrzymany, a strażnik zna dziennik kopiowania.
        self.assertEqual(widziane["manager"], {10: 1})
        self.assertEqual(widziane["dzierzawa"]["kopia"], SYNC.sciezka_dziennika(self.ragnarok))
        self.assertEqual(czytaj(self.ragnarok, REL_EXE), czytaj(self.cache, REL_EXE))
        self.assertEqual(czytaj(self.ragnarok, REL_PAK), czytaj(self.cache, REL_PAK))
        self.assertEqual(S.czytaj_lokalny(self.ragnarok)[0]["buildid"], NOWY)
        self.assertEqual(czytaj(self.ragnarok, os.path.join("ShooterGame", "Saved", "SavedArks", "swiat.ark")),
                         b"SWIAT")
        self.assertEqual(self.api.licznik, {10: 0})               # manager wznowiony
        self.assertIsNone(self.p._zadanie)
        self.assertTrue(self.logi("Ragnarok: zainstalowany build %d (skopiowano 3 plików" % NOWY))
        # Te same liczby przed, w trakcie i po kopiowaniu (26.09: „39 plików”, potem „40/40”).
        self.assertTrue(self.logi("Ragnarok: manager wstrzymany na czas podmiany plików (build %d → %d, "
                                  "3 plików" % (STARY, NOWY)))
        self.assertTrue(self.logi("Ragnarok: kopiuję 3 plików z cache"))
        self.assertTrue(self.logi("Ragnarok: skopiowano 3/3 plików"))
        self.assertNotIn("Ragnarok|%d" % NOWY, self.p.cfg["proby"])
        self.assertEqual(self.pobrania()[-1][self.pobrania()[-1].index("+force_install_dir") + 1], self.cache)

    def test_blad_kopiowania_przywraca_pliki_i_liczy_probe(self):
        prawdziwy = os.replace
        licznik = {"n": 0}

        def replace(a, b):
            if a.endswith(SYNC.SUFIKS_NOWY):
                licznik["n"] += 1
                if licznik["n"] == 2:
                    raise OSError("dysk pełny")
            return prawdziwy(a, b)
        with patch.object(SYNC.os, "replace", side_effect=replace):
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda s: None)
        self.assertEqual(czytaj(self.ragnarok, REL_EXE), ("EXE-%d" % STARY).encode())
        self.assertEqual(S.czytaj_lokalny(self.ragnarok)[0]["buildid"], STARY)
        self.assertEqual(self.api.licznik, {10: 0})
        ostrzezenie = self.logi("aktualizacja NIEUDANA")
        self.assertEqual(len(ostrzezenie), 1)
        self.assertIn("przywrócono poprzednie pliki", ostrzezenie[0])
        self.assertIn("dotychczasowym buildzie", ostrzezenie[0])
        self.assertEqual(len(self.p.cfg["proby"]["Ragnarok|%d" % NOWY]), 1)
        self.assertNotIn("Ragnarok", self.p.plany)                # następna runda liczy plan od nowa

    def test_serwer_nie_wylaczyl_sie_nic_nie_kopiuje(self):
        exe = os.path.join(self.ragnarok, REL_EXE)
        self.api.serwery = {4242: exe}
        with patch.object(modul, "CZEKAJ_NA_WYJSCIE_S", -1), patch.object(modul.SYNC, "wykonaj") as wykonaj:
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda s: None)
        wykonaj.assert_not_called()
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertTrue(self.logi("nic nie kopiuję"))

    def test_serwer_innej_mapy_nie_blokuje(self):
        inny = os.path.join(self.katalogi["Genesis"], REL_EXE)
        self.api.serwery = {4243: inny}
        self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda s: None)
        self.assertEqual(S.czytaj_lokalny(self.ragnarok)[0]["buildid"], NOWY)

    def test_pozostaly_steamcmd_po_limicie_jest_konczony(self):
        steam = os.path.join(self.tmp, "STEAMCMD", "steamcmd.exe")
        self.api.serwery = {77: steam, 78: os.path.join(self.tmp, "inny", "steamcmd.exe")}
        zabite = []
        self.api.zakoncz = zabite.append
        self.assertFalse(self.p._dokoncz_steamcmd(steam, 0, spij=lambda s: None))
        self.assertEqual(zabite, [77])                            # cudzy SteamCMD nietknięty


class BezSerwera(Baza):
    """Serwer nie działa (OFFLINE/CRASH albo długo nie GOTOWY): aktualizacja bez DoExit."""

    def setUp(self):
        super().setUp()
        self.blokada_w_trakcie = []
        orig = self.p._aktualizuj_praca
        prawdziwe = SYNC.wykonaj

        def wykonaj(*a, **kw):
            self.blokada_w_trakcie.append(self.p.blokada_kolejki())
            return prawdziwe(*a, **kw)
        for x in (patch.object(self.p, "_aktualizuj_praca",
                               side_effect=lambda z, cfg: orig(z, cfg, spij=lambda s: None)),
                  patch.object(modul.SYNC, "wykonaj", side_effect=wykonaj)):
            x.start()
            self.addCleanup(x.stop)

    def test_offline_bez_doexit_i_bez_kolejki(self):
        self.core._tabs["Genesis"].status = "offline"
        self.sprawdzenie()
        self.assertEqual(self.app.zlecenia[0][0], ["Ragnarok"])
        self.assertEqual(S.czytaj_lokalny(self.katalogi["Genesis"])[0]["buildid"], NOWY)
        self.assertIn("Genesis", self.blokada_w_trakcie[0])       # kolejka nie rusza w trakcie
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertIsNone(self.p._zadanie)
        self.assertIsNone(self.p.blokada_kolejki())
        self.assertTrue(self.logi("Genesis: serwer nie działa"))
        self.assertTrue(self.logi("Genesis: zainstalowany build %d" % NOWY))

    def test_dlugo_nie_gotowa_tez(self):
        self.core._tabs["Genesis"].status = "loading_mods"
        self.sprawdzenie()
        self.assertEqual(self.blokada_w_trakcie, [])
        self.p._nie_gotowa_od["Genesis"] -= modul.NIE_GOTOWA_S + 1
        self.sprawdzenie(zrodlo="lokalne")
        self.assertEqual(len(self.blokada_w_trakcie), 1)

    def test_proces_serwera_dziala_manager_nie_jest_wstrzymywany(self):
        self.core._tabs["Genesis"].status = "crash"
        self.api.serwery = {4242: os.path.join(self.katalogi["Genesis"], REL_EXE)}
        self.sprawdzenie()
        self.assertEqual(self.blokada_w_trakcie, [])
        self.assertEqual(self.api.licznik, {})
        self.assertTrue(self.logi("Genesis: stan crash, ale proces serwera działa"))

    def test_serwer_wstal_tuz_przed_wstrzymaniem_to_nie_nieudana_proba(self):
        self.core._tabs["Genesis"].status = "crash"
        exe = os.path.join(self.katalogi["Genesis"], REL_EXE)
        zamroz = self.api.zamroz

        def zamroz_po_starcie(pid):                              # manager zdążył go podnieść
            self.api.serwery = {4242: exe}
            zamroz(pid)
        self.api.zamroz = zamroz_po_starcie
        with patch.object(modul, "CZEKAJ_NA_WYJSCIE_S", -1):
            self.sprawdzenie()
        self.assertEqual(self.blokada_w_trakcie, [])
        self.assertEqual(self.api.licznik, {10: 0})
        self.assertEqual(self.p.cfg["proby"], {})
        self.assertTrue(self.logi("Genesis: serwer działa"))
        self.assertFalse(self.logi("NIEUDANA"))

    def test_nie_w_trakcie_kolejki(self):
        self.core._tabs["Genesis"].status = "offline"
        self.app.restart_active = True
        self.sprawdzenie()
        self.assertEqual(self.blokada_w_trakcie, [])
        self.assertEqual(self.api.licznik, {})

    def test_automat_rcon_wylaczony_nic_samo(self):
        self.app.auto_rcon = types.SimpleNamespace(get=lambda: False)
        self.core._tabs["Genesis"].status = "offline"
        self.sprawdzenie()
        self.assertEqual(self.blokada_w_trakcie, [])
        self.assertTrue(self.logi("Genesis: automat RCON wyłączony"))
        self.sprawdzenie(reczne=True, wymus=True)
        self.assertEqual(len(self.blokada_w_trakcie), 1)


class CyklZyciaWPrawdziwymHoscie(unittest.TestCase):
    """Prawdziwy PluginHost (start programu, zmiana języka) z samym pluginem 88."""

    class Aplikacja(object):
        def __init__(self):
            self.tabs = {}
            self.config_data = {"plugins": {}}
            self.logi = []
            self.plugin_host = None

        def log(self, x, tag=None): self.logi.append(str(x))
        def log_warn(self, x): self.logi.append("WARN " + str(x))
        def tr(self, k, **kw): return k
        def post_ui(self, cb): cb()
        def run_async(self, fn, *a): pass
        def request_save(self): pass
        def save_config(self, silent=False): return True

    def setUp(self):
        from asaonly.pluginy import PluginHost
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        program = os.path.join(self.tmp, "program")
        os.makedirs(os.path.join(program, "PLUGINY"))
        os.makedirs(os.path.join(program, "CONFIG_PROGRAM"))
        shutil.copy(ROOT / "PLUGINY" / "88_aktualizacja_serwera.py", os.path.join(program, "PLUGINY"))
        self.dzierzawa = os.path.join(program, "CONFIG_PROGRAM", modul.PLIK_DZIERZAWY)
        self.api = Api()
        self.api.zyje = lambda pid, start=None: pid in (10, os.getpid())
        self.app = self.Aplikacja()
        self.host = PluginHost(self.app, os.path.join(program, "PLUGINY"))
        self.app.plugin_host = self.host
        self.host.load_all()
        self.p = self.host.get("aktualizacja_serwera")
        patcher = patch("asaonly.zamrazanie.ApiWindows", lambda: self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_start_programu_odzyskuje_managera_i_nie_sprawdza_od_razu(self):
        from asaonly import zamrazanie as Z
        Z.zapisz_dzierzawe(self.dzierzawa, {"refresher": {"pid": 999999, "start": 5},    # padł
                                            "manager": [{"pid": 10, "start": 1}]})
        self.api.licznik[10] = 1
        teraz = time.time()
        self.host.start_all()
        self.assertEqual(self.api.licznik, {10: 0})                  # wznowiony przy starcie
        self.assertFalse(os.path.exists(self.dzierzawa))
        self.assertTrue(any("manager był wstrzymany" in x for x in self.app.logi))
        self.assertGreaterEqual(self.p._nastepne_api, teraz + modul.PIERWSZE_SPRAWDZENIE_S - 1)

    def test_zmiana_jezyka_w_trakcie_podmiany_nie_gubi_wstrzymanego_managera(self):
        self.host.start_all()
        zamrazarka = self.p.zamrazarka
        self.assertEqual(zamrazarka.zamroz(), (True, ""))
        self.p._zadanie = {"mapa": "Ragnarok", "faza": "instalacja", "katalog": self.tmp,
                           "cel": 2, "z": 1, "pid": None, "t0": 0, "tryb": "doexit"}
        self.host.stop_all()                                         # zmiana języka
        self.host.start_all()
        self.assertIs(self.p.zamrazarka, zamrazarka)                 # ta sama, aktywna
        self.assertEqual(self.api.licznik, {10: 1})                  # nadal wstrzymany
        self.assertTrue(os.path.exists(self.dzierzawa))
        self.assertIsNotNone(self.p.blokada_kolejki())
        self.assertEqual(self.p.zamrazarka.odmroz(), [])             # koniec podmiany
        self.assertEqual(self.api.licznik, {10: 0})


class ZapytanieSteam(unittest.TestCase):
    def test_zapasowe_zrodlo_appinfo_vdf(self):
        from tests.test_steam_serwer import DRZEWO, binarny_appinfo
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        p = modul.Wtyczka()
        steamcmd = os.path.join(tmp, "STEAMCMD", "steamcmd.exe")
        appinfo = os.path.join(tmp, "STEAMCMD", "appcache", "appinfo.vdf")
        os.makedirs(os.path.dirname(appinfo))
        with open(appinfo, "wb") as fh:
            fh.write(b"stary cache")                         # ma zostać usunięty przed pytaniem

        def falszywy(argv, limit, na_start=None, na_linie=None):
            self.assertFalse(os.path.exists(appinfo))
            with open(appinfo, "wb") as fh:                  # SteamCMD zapisuje świeży cache
                fh.write(binarny_appinfo(2430930, DRZEWO))
            return 0, "Loading Steam API...OK\n", False       # konsola ucięta — bez wydruku
        with patch.object(p, "_uruchom", side_effect=falszywy), \
                patch.object(p, "_dokoncz_steamcmd", return_value=True):
            zdalny, zrodlo, blad, _ = p._zapytaj_steam(steamcmd)
        self.assertIsNone(blad)
        self.assertEqual((zdalny["buildid"], zrodlo), (25500000, "SteamCMD (appinfo.vdf)"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
