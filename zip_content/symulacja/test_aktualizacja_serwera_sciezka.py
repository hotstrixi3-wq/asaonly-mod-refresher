# -*- coding: utf-8 -*-
"""V3.86: aktualizacja serwera przez PRAWDZIWĄ kolejkę i PRAWDZIWY plugin 88 z cache.

Prawdziwe: PluginHost, plugin RCON (86) na gniazdach TCP, kolejka procedury,
plugin 88, kopiowanie plików (asaonly.synchronizacja) na dysku. Atrapy: procesy
Windows (manager i serwery), api.steamcmd.net i sam SteamCMD (zapisuje nowy
build do cache). Symulowany manager zachowuje się jak ASADedicatedManager w jego
logach: podnosi serwer, którego proces zniknął — ale tylko wtedy, gdy nie jest
wstrzymany.

Scenariusz z 25.09.2026 (SteamCMD nie może pobrać) ma teraz jeden wynik: żadnej
komendy RCON, żadnego DoExit, żadnego restartu.
"""
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from asaonly import siec
from asaonly import steam_serwer as S
from asaonly import synchronizacja as SYNC
from symulacja.test_sciezka_produkcyjna import App, AtrapaRcon, Tab, Var

STARY, NOWY = 25489097, 25535041
REL_EXE = os.path.join("ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe")
REL_PAK = os.path.join("ShooterGame", "Content", "Paks", "ShooterGame-WindowsServer.pak")


def manifest(buildid):
    return ('"AppState"\n{\n\t"appid"\t\t"2430930"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"%d"\n'
            '\t"InstalledDepots"\n\t{\n\t\t"2430931"\n\t\t{\n\t\t\t"manifest"\t\t"%d"\n\t\t}\n\t}\n}\n'
            % (buildid, buildid))


def instalacja(katalog, buildid):
    for rel, tresc in ((REL_EXE, "EXE-%d" % buildid), (REL_PAK, "PAK-%d-dluzszy" % buildid),
                       (os.path.join("steamapps", S.PLIK_MANIFESTU), manifest(buildid))):
        sciezka = os.path.join(katalog, rel)
        os.makedirs(os.path.dirname(sciezka), exist_ok=True)
        with open(sciezka, "w", encoding="utf-8") as fh:
            fh.write(tresc)


class Windows(object):
    """Procesy: manager (PID 10) i serwery map (PID → ścieżka exe)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.serwery = {}
        self.licznik = 0
        self.zamrozony_przy_wyjsciu = []
        self.nastepny_pid = 100

    def dodaj_serwer(self, katalog):
        with self.lock:
            pid = self.nastepny_pid
            self.nastepny_pid += 1
            self.serwery[pid] = os.path.join(katalog, REL_EXE)
            return pid

    def zakoncz_serwer(self, katalog):
        with self.lock:
            for pid, sciezka in list(self.serwery.items()):
                if sciezka.startswith(katalog):
                    del self.serwery[pid]
                    self.zamrozony_przy_wyjsciu.append(self.licznik > 0)

    def dziala(self, katalog):
        with self.lock:
            return any(s.startswith(katalog) for s in self.serwery.values())

    # -- API jak asaonly.zamrazanie.ApiWindows --
    def procesy(self, nazwa):
        with self.lock:
            if nazwa == "ASADedicatedManager.exe":
                return [10]
            return list(self.serwery)

    def czas_startu(self, pid):
        return 1

    def zyje(self, pid, start=None):
        with self.lock:
            return pid == 10 or pid in self.serwery

    def dostep_wstrzymania(self, pid):
        pass

    def sciezka_exe(self, pid):
        with self.lock:
            if pid not in self.serwery:
                raise OSError("brak procesu")
            return self.serwery[pid]

    def zamroz(self, pid):
        self.licznik += 1

    def odmroz(self, pid):
        self.licznik -= 1

    def uruchom_straznika(self, sciezka):
        pass


class AktualizacjaSerweraPrzezKolejke(unittest.TestCase):
    CZAS_STARTU_S = 0.3
    RESTART_MANAGERA_S = 0.2

    def przygotuj(self, gracze, offline=()):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        local = os.path.join(self.tmp, "local", "ASADedicatedManager", "x", "1.0.0.0")
        os.makedirs(local)
        with open(os.path.join(local, "user.config"), "w", encoding="utf-8") as fh:
            fh.write('<setting name="AutoCheckUpdates" serializeAs="String"><value>False</value></setting>')
        env = patch.dict(os.environ, {"LOCALAPPDATA": os.path.join(self.tmp, "local")})
        env.start()
        self.addCleanup(env.stop)
        self.win = Windows()
        self.serwery, tabs, self.katalogi = {}, [], {}
        for nazwa, odp in gracze:
            katalog = os.path.join(self.tmp, "ARKservers", nazwa + "_WP")
            instalacja(katalog, STARY)
            self.katalogi[nazwa] = katalog
            srv = AtrapaRcon(nazwa, "pw", odp)
            self.addCleanup(srv.zamknij)
            self.serwery[nazwa] = srv
            tab = Tab(nazwa, srv.port, "pw", [(0, "ServerChat restart"), (1, "DoExit")], ["111"])
            tab.var_log = Var(os.path.join(katalog, "ShooterGame", "Saved", "Logs"))
            tabs.append(tab)
            if nazwa not in offline:
                self.win.dodaj_serwer(katalog)
        self.cache = os.path.join(self.tmp, "ARKservers", "ASA UPDATES REFRESHER")
        self.app = App(tabs, [])
        for nazwa in offline:
            self.app.tabs[nazwa]._tail_status = "offline"
        self.plugin = self.app.plugin_host.get("aktualizacja_serwera")
        self.assertIsNotNone(self.plugin)
        program = os.path.join(self.tmp, "program")
        os.makedirs(os.path.join(program, "CONFIG_PROGRAM"))
        self.pobrania, self.kopie = [], []
        self.steamcmd_ok = True
        prawdziwe = SYNC.wykonaj

        def wykonaj(pl, zrodlo, cel, **kw):
            # Podmiana plików tylko przy wyłączonym serwerze i wstrzymanym managerze.
            self.assertFalse(self.win.dziala(cel), "kopiowanie przy działającym serwerze")
            self.assertGreater(self.win.licznik, 0, "kopiowanie bez wstrzymanego managera")
            self.kopie.append(os.path.basename(cel))
            return prawdziwe(pl, zrodlo, cel, **kw)
        for p in (patch.object(type(self.plugin), "_katalog_programu", staticmethod(lambda: program)),
                  patch.object(self.plugin, "_zapewnij_steamcmd", return_value=("steamcmd.exe", None)),
                  patch.object(self.plugin, "_uruchom", side_effect=self.steamcmd),
                  patch.object(self.plugin, "_content_log", return_value=(
                      "[2026-09-25 21:30:49] Client version: 1\n[2026-09-25 21:30:54] AppID 2430930 update "
                      "canceled : Failed downloading 1 manifests (No connection)\n")),
                  patch.object(siec, "steam_api_info", return_value={
                      "status": "success", "data": {"2430930": {"depots": {
                          "branches": {"public": {"buildid": str(NOWY), "timeupdated": "1"}},
                          "2430931": {"manifests": {"public": {"gid": str(NOWY), "size": "100"}}}}}}}),
                  patch.object(SYNC, "wykonaj", side_effect=wykonaj)):
            p.start()
            self.addCleanup(p.stop)
        self.plugin.zamrazarka = self.plugin._nowa_zamrazarka()
        self.plugin.zamrazarka.api = self.win

    def steamcmd(self, argv, limit, na_start=None, na_linie=None):
        katalog = argv[argv.index("+force_install_dir") + 1]
        self.assertEqual(katalog, self.cache, "SteamCMD na katalogu mapy")
        # Pobieranie do cache idzie przy DZIAŁAJĄCYCH serwerach i działającym managerze.
        self.assertEqual(self.win.licznik, 0, "pobieranie do cache przy wstrzymanym managerze")
        self.pobrania.append(katalog)
        time.sleep(0.1)
        if not self.steamcmd_ok:
            return 8, "Error! App '2430930' state is 0x6 after update job.", False
        instalacja(katalog, NOWY)
        return 0, "Success! App '2430930' fully installed.", False

    def pompuj(self, warunek, limit=15.0, kolejka=False, manager=False):
        widziane, powrot = set(), {}
        koniec = time.time() + limit
        while not warunek() and time.time() < koniec:
            self.app.obsluz_ui()
            if kolejka:
                self.app._tick_restart_timeline()
            if manager:
                self.manager_i_serwery(widziane, powrot)
            time.sleep(0.02)
        self.app.obsluz_ui()

    def manager_i_serwery(self, widziane, powrot):
        """Serwer po DoExit kończy proces; manager (gdy nie wstrzymany) podnosi go po chwili."""
        teraz = time.time()
        for nazwa, srv in self.serwery.items():
            if nazwa not in widziane and "DoExit" in srv.komendy():
                widziane.add(nazwa)
                self.win.zakoncz_serwer(self.katalogi[nazwa])
                self.app.tabs[nazwa]._tail_status = "offline"
        for nazwa in self.serwery:
            tab = self.app.tabs[nazwa]
            if tab._tail_status != "offline" or self.win.dziala(self.katalogi[nazwa]):
                continue
            if self.win.licznik > 0:
                powrot.pop(nazwa, None)
            elif nazwa not in powrot:
                powrot[nazwa] = teraz + self.RESTART_MANAGERA_S
            elif teraz >= powrot[nazwa]:
                del powrot[nazwa]
                self.win.dodaj_serwer(self.katalogi[nazwa])
                tab._ready_proof = str(tab._boot_seq + 1); tab._ready_observed_at = time.time(); tab._boot_seq += 1
                tab._tail_status = "ready"

    def test_dwie_mapy_po_kolei_cache_przed_ogloszeniami_manager_wstrzymany_tylko_na_kopie(self):
        self.przygotuj((("A", "No Players Connected"), ("B", "0. Gracz, 0002")))
        self.assertTrue(self.plugin.sprawdz())
        self.pompuj(lambda: sorted(self.app._zlecenia()) == ["A", "B"])
        self.assertEqual(sorted(self.app._zlecenia()), ["A", "B"])
        self.assertEqual(self.pobrania, [self.cache])              # najpierw cache, zanim cokolwiek poszło
        for srv in self.serwery.values():
            self.assertEqual(srv.komendy(), [])                    # do tej chwili żadnej komendy RCON
        self.app._exec_pending()
        self.assertTrue(self.app.restart_active)
        self.pompuj(lambda: not (self.app.restart_active or self.app.watch_active), limit=30,
                    kolejka=True, manager=True)
        self.assertFalse(self.app.restart_active)
        self.assertEqual(sorted(self.kopie), ["A_WP", "B_WP"])
        self.assertEqual(self.serwery["A"].komendy(), ["ListPlayers", "DoExit"])           # pusta
        self.assertEqual(self.serwery["B"].komendy(), ["ListPlayers", "ServerChat restart", "DoExit"])
        self.assertEqual(self.win.zamrozony_przy_wyjsciu, [True, True])
        self.assertEqual(self.win.licznik, 0)
        for katalog in self.katalogi.values():
            self.assertEqual(S.czytaj_lokalny(katalog)[0]["buildid"], NOWY)
            with open(os.path.join(katalog, REL_EXE), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "EXE-%d" % NOWY)
            self.assertFalse(os.path.exists(os.path.join(katalog, SYNC.KATALOG_KOPII)))
        self.assertEqual(self.app._zlecenia(), {})
        self.assertEqual(self.app.config_data["czasy_startu"], {})       # to nie były zwykłe starty
        self.assertTrue(any("zainstalowany build %d" % NOWY in x for x in self.app.logs))
        self.assertIsNone(self.plugin._zadanie)

    def test_nieudane_pobieranie_zero_komend_rcon_zero_restartow(self):
        """Regresja 25.09.2026: SteamCMD nie może pobrać — dawniej 9 restartów bez aktualizacji."""
        self.przygotuj((("A", "No Players Connected"), ("B", "0. Gracz, 0002")))
        self.steamcmd_ok = False
        self.assertTrue(self.plugin.sprawdz())
        self.pompuj(lambda: bool(self.pobrania) and self.plugin._cache_praca is None
                    and not self.plugin._sprawdzanie)
        self.app._exec_pending()                                    # automat zajrzałby do kolejki
        self.pompuj(lambda: False, limit=1.0, kolejka=True, manager=True)
        self.assertEqual(self.app._zlecenia(), {})
        self.assertFalse(self.app.restart_active)
        for srv in self.serwery.values():
            self.assertEqual(srv.komendy(), [])
        self.assertEqual(self.win.zamrozony_przy_wyjsciu, [])       # żaden serwer nie zniknął
        self.assertEqual(self.win.licznik, 0)
        self.assertEqual(self.kopie, [])
        for katalog in self.katalogi.values():
            self.assertTrue(self.win.dziala(katalog))
            self.assertEqual(S.czytaj_lokalny(katalog)[0]["buildid"], STARY)
        self.assertTrue(any("Serwery NIE były ruszane" in x for x in self.app.logs))

    def test_mapa_z_wylaczonym_serwerem_bez_doexit_a_kolejka_czeka(self):
        self.przygotuj((("A", "0. Gracz, 0002"), ("B", "No Players Connected")), offline=("B",))
        self.assertTrue(self.plugin.sprawdz())
        self.pompuj(lambda: "A" in self.app._zlecenia() and self.plugin._zadanie is None and bool(self.kopie))
        # A (GOTOWA) — zlecenie do kolejki; B (OFFLINE) — podmiana od razu, bez kolejki i bez RCON.
        self.assertEqual(sorted(self.app._zlecenia()), ["A"])
        self.assertEqual(self.kopie, ["B_WP"])
        self.assertEqual(self.serwery["B"].komendy(), [])
        widziane, powrot = set(), {}
        koniec = time.time() + 10
        while self.app.tabs["B"]._tail_status != "ready" and time.time() < koniec:
            self.app.obsluz_ui()
            self.manager_i_serwery(widziane, powrot)
            time.sleep(0.02)
        self.assertEqual(self.app.tabs["B"]._tail_status, "ready")       # manager podniósł B sam
        self.app._exec_pending()
        self.assertTrue(self.app.restart_active)
        self.pompuj(lambda: not (self.app.restart_active or self.app.watch_active), limit=30,
                    kolejka=True, manager=True)
        self.assertEqual(self.kopie, ["B_WP", "A_WP"])
        self.assertEqual(self.serwery["A"].komendy(), ["ListPlayers", "ServerChat restart", "DoExit"])
        self.assertEqual(self.win.licznik, 0)
        for katalog in self.katalogi.values():
            self.assertEqual(S.czytaj_lokalny(katalog)[0]["buildid"], NOWY)
        self.assertTrue(any("B: serwer nie działa" in x for x in self.app.logs))
        self.assertEqual(self.app._zlecenia(), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
