# -*- coding: utf-8 -*-
"""V3.86.2 — po analizie logów z 26.09.2026 (pierwsza runda aktualizacji serwera).

1. Dziennik zdarzeń także w pliku (wcześniej tylko okno konsoli; napis o
   asa_debug.log był nieprawdziwy — tam idą wyłącznie ukryte błędy).
2. Planowy restart po DoExit nie wygląda jak awaria: zamiast „PAD … zdechł
   cicho” — „zamknięty po DoExit”, OFFLINE nie na czerwono, [CPU] milczy do READY.
3. Okno konsoli bez zatrzymań: program wyłącza w swoim oknie tryb szybkiej edycji.
"""
import importlib.util
import os
import pathlib
import queue
import shutil
import tempfile
import time
import types
import unittest

from asaonly import dziennik_plik as DP
from asaonly import konsola as K
from asaonly.monitor_plugin import MonitorMixin
from asaonly.pluginy import CoreAPI, TabSnapshot
from asaonly.procedura import ProcedureMixin

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
_spec = importlib.util.spec_from_file_location("asaonly_program_v3862", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)
_spec_cpu = importlib.util.spec_from_file_location("cpu_v3862", ROOT / "PLUGINY" / "60_cpu.py")
cpu_modul = importlib.util.module_from_spec(_spec_cpu)
_spec_cpu.loader.exec_module(cpu_modul)


def czekaj_na(warunek, limit=5.0):
    koniec = time.time() + limit
    while time.time() < koniec:
        if warunek():
            return True
        time.sleep(0.02)
    return warunek()


# ---------------------------------------------------------------------------
# 1. Dziennik w pliku
# ---------------------------------------------------------------------------
class DziennikWPliku(unittest.TestCase):
    def setUp(self):
        self.kat = tempfile.mkdtemp(prefix="asaonly-dziennik-")
        self.addCleanup(shutil.rmtree, self.kat, True)

    def czytaj(self, nazwa=DP.NAZWA):
        with open(os.path.join(self.kat, nazwa), encoding="utf-8") as fh:
            return fh.read()

    def test_linie_trafiaja_do_pliku_z_data_sesji(self):
        p = DP.PisarzPliku(self.kat, naglowek="start programu 3.86.2", dzis=lambda: "2026-09-26")
        p.pisz("[14:25:02] pierwsza\n")
        p.pisz("[14:25:03] druga\n")
        p.zamknij(5.0)
        tekst = self.czytaj()
        self.assertIn("=== 2026-09-26 · start programu 3.86.2 ===\n", tekst)
        self.assertTrue(tekst.rstrip().endswith("[14:25:02] pierwsza\n[14:25:03] druga".rstrip()))

    def test_zmiana_dnia_dopisuje_date(self):
        dni = iter(["2026-09-26", "2026-09-27"])
        p = DP.PisarzPliku(self.kat, dzis=lambda: next(dni))
        p.pisz("[23:59:59] przed\n")
        self.assertTrue(czekaj_na(lambda: os.path.exists(p.sciezka) and "przed" in self.czytaj()))
        p.pisz("[00:00:01] po\n")
        p.zamknij(5.0)
        tekst = self.czytaj()
        self.assertIn("=== 2026-09-27 ===\n[00:00:01] po\n", tekst)

    def test_rotacja_jak_dziennik_modow(self):
        p = DP.PisarzPliku(self.kat, max_b=200, keep=2, dzis=lambda: "2026-09-26")
        for i in range(12):
            p.pisz(("[%02d] " % i) + "x" * 60 + "\n")
            time.sleep(0.03)                      # osobne zapisy, żeby rotacja zadziałała
        p.zamknij(5.0)
        pliki = sorted(os.listdir(self.kat))
        self.assertIn(DP.NAZWA, pliki)
        self.assertIn("dziennik-zdarzen.01.txt", pliki)
        self.assertIn("dziennik-zdarzen.02.txt", pliki)
        self.assertNotIn("dziennik-zdarzen.03.txt", pliki)       # najwyżej keep kopii
        for nazwa in pliki:
            self.assertLessEqual(os.path.getsize(os.path.join(self.kat, nazwa)), 200 + 80)
        self.assertIn("[11]", self.czytaj())

    def test_blad_zapisu_nie_zatrzymuje_programu_i_zglasza_raz(self):
        zajety = os.path.join(self.kat, "to-jest-plik")
        with open(zajety, "w") as fh:
            fh.write("x")
        bledy = []
        p = DP.PisarzPliku(os.path.join(zajety, "pod"), na_blad=bledy.append)
        p.pisz("a\n")
        self.assertTrue(czekaj_na(lambda: len(bledy) == 1))
        p.pisz("b\n")                            # drugi, osobny zapis — też nieudany
        p.zamknij(5.0)
        self.assertEqual(len(bledy), 1)

    def test_pisz_nie_czeka_na_dysk(self):
        wstrzymany = __import__("threading").Event()
        p = DP.PisarzPliku(self.kat)
        prawdziwy = p._zapisz
        p._zapisz = lambda tekst: (wstrzymany.wait(10), prawdziwy(tekst))
        t0 = time.time()
        for i in range(300):
            p.pisz("linia %d\n" % i)
        self.assertLess(time.time() - t0, 0.5)
        wstrzymany.set()
        p.zamknij(5.0)
        self.assertIn("linia 299", self.czytaj())

    def test_oproznianie_kolejki_konsola_z_kolorami_plik_bez(self):
        class Pisarz(object):
            def __init__(self):
                self.teksty = []

            def pisz(self, tekst):
                self.teksty.append(tekst)
        app = types.SimpleNamespace(_log_queue=queue.Queue(), _ansi=True,
                                    _konsola=Pisarz(), _dziennik_plik=Pisarz())
        app._log_queue.put(("[14:36:47] zainstalowany\n", "st_ok"))
        app._log_queue.put(("[14:36:48] zwykla\n", None))
        program.App._oproznij_dziennik(app)
        self.assertEqual(app._dziennik_plik.teksty, ["[14:36:47] zainstalowany\n[14:36:48] zwykla\n"])
        self.assertIn("\x1b[", app._konsola.teksty[0])
        self.assertNotIn("\x1b[", app._dziennik_plik.teksty[0])

    def test_program_podpina_plik_i_poprawny_napis(self):
        zrodlo = PROGRAM.read_text(encoding="utf-8")
        self.assertIn("PisarzPliku(", zrodlo)
        self.assertIn('os.environ.get("ASAONLY_EVENT_LOG_DIR") or KNOW_DIR', zrodlo)
        zamkniecie = zrodlo.split("def _zamknij_teraz(self):", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._oproznij_dziennik()", zamkniecie)
        self.assertIn("plik.zamknij(", zamkniecie)
        from asaonly.tr import TR
        for jezyk in ("pl", "en"):
            self.assertIn("dziennik-zdarzen.txt", TR[jezyk]["console_hint"])
        self.assertNotIn("also written to asa_debug.log", TR["en"]["console_hint"])
        diag = (ROOT / "PLUGINY" / "82_diagnostyka_zip.py").read_text(encoding="utf-8")
        self.assertIn('"WIEDZA_O_PROGRAMIE/dziennik-zdarzen.txt"', diag)
        self.assertIn("WIEDZA_O_PROGRAMIE/dziennik-zdarzen*.txt",
                      (ROOT / ".gitignore").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 2. Planowy restart po DoExit
# ---------------------------------------------------------------------------
class Zmienna(object):
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


class ZakladkaMonitora(object):
    def __init__(self, nazwa, port):
        self.name = nazwa
        self.var_map_on = Zmienna(True)
        self.var_port = Zmienna(port)
        self._tail_status = "ready"
        self._wisi_st = 0
        self._sonda_t = time.time()
        self._dl_last = 0
        self._dl_alarm = False
        self.stany = []

    def _apply_tail(self, status, linia):
        self.stany.append(status)
        self._tail_status = status


class AppMonitora(MonitorMixin, ProcedureMixin):
    def __init__(self, zakladka):
        self.tabs = {zakladka.name: zakladka}
        self.logi = []
        self.watch_maps = {}
        self._pad4 = {}
        self._pad_byl = {}
        self._last_pid_by_port = {}
        self._monitor_error_last = {}
        self.zywe = set()

    def _proc_zyje(self, pid):
        return pid in self.zywe

    def log(self, tekst, tag=None):
        self.logi.append(str(tekst))

    def log_warn(self, tekst):
        self.logi.append(str(tekst))

    def tr(self, klucz, **kw):
        return "%s|%s" % (klucz, kw.get("tab", ""))


class PlanowyRestart(unittest.TestCase):
    def przebieg(self, w_restarcie, slad_crasha=False):
        tab = ZakladkaMonitora("Genesis 1", "27020")
        app = AppMonitora(tab)
        app.zywe = {5728}
        app._monitor_apply({"pid": {"27020": 5728}, "wiek": {"Genesis 1": 1.0}})
        if w_restarcie:
            app.watch_maps["Genesis 1"] = {"done": False, "failed": False}
        if slad_crasha:
            tab._tail_status = "crash"
        app.zywe = set()                          # DoExit: proces zniknął
        app._monitor_apply({"pid": {}, "wiek": {"Genesis 1": 1.0}})
        return app, tab

    def test_po_doexit_zamkniety_a_nie_pad(self):
        app, tab = self.przebieg(w_restarcie=True)
        self.assertEqual(app.logi, ["zamkniety_po_doexit|Genesis 1"])
        self.assertEqual(tab.stany, ["offline"])

    def test_bez_doexit_nadal_pad(self):
        app, tab = self.przebieg(w_restarcie=False)
        self.assertEqual(app.logi, ["pad_bez_sladu|Genesis 1"])
        self.assertEqual(tab.stany, ["offline"])

    def test_slad_crasha_po_doexit_zostaje_padem(self):
        app, _ = self.przebieg(w_restarcie=True, slad_crasha=True)
        self.assertEqual(app.logi, ["pad_crash|Genesis 1"])

    def test_mapa_w_restarcie_tylko_do_powrotu(self):
        app = AppMonitora(ZakladkaMonitora("A", "1"))
        self.assertFalse(app.mapa_w_restarcie("A"))
        app.watch_maps["A"] = {"done": False, "failed": False}
        self.assertTrue(app.mapa_w_restarcie("A"))
        app.watch_maps["A"]["done"] = True
        self.assertFalse(app.mapa_w_restarcie("A"))
        app.watch_maps["A"] = {"done": False, "failed": True}
        self.assertFalse(app.mapa_w_restarcie("A"))

    def test_offline_po_doexit_nie_na_czerwono(self):
        tagi = []
        app = types.SimpleNamespace(log=lambda tekst, tag=None: tagi.append(tag),
                                    mapa_w_restarcie=lambda nazwa: nazwa == "Genesis 1")
        program.App.log_status(app, "x", "offline", nazwa="Genesis 1")
        program.App.log_status(app, "x", "offline", nazwa="Ragnarok")
        program.App.log_status(app, "x", "offline")
        program.App.log_status(app, "x", "crash", nazwa="Genesis 1")
        self.assertEqual(tagi, ["st_wait", "st_bad", "st_bad", "st_bad"])

    def test_widok_map_dla_pluginow_ma_restart(self):
        class Tab(object):
            def __init__(self, nazwa):
                self.var_map_on = Zmienna(True)
                self.var_ip = Zmienna("127.0.0.1")
                self.var_port = Zmienna("27020")
                self.var_log = Zmienna("")
                self._tail_status = "offline"
                self.nazwa = nazwa

            def get_effective_mod_ids(self):
                return []
        app = types.SimpleNamespace(tabs={"Genesis 1": Tab("Genesis 1"), "Ragnarok": Tab("Ragnarok")},
                                    mapa_w_restarcie=lambda nazwa: nazwa == "Genesis 1")
        widok = CoreAPI(app).tabs()
        self.assertTrue(widok["Genesis 1"].restart)
        self.assertFalse(widok["Ragnarok"].restart)
        self.assertFalse(TabSnapshot("A", True, "", "", "", (), "ready").restart)


class CpuDopieroPoReady(unittest.TestCase):
    def setUp(self):
        class Core(object):
            def __init__(self):
                self.logi = []
                self.widok = {}

            def tabs(self):
                return dict(self.widok)

            def log(self, tekst, tag=None):
                self.logi.append(str(tekst))

            def warn(self, tekst):
                self.logi.append("WARN " + str(tekst))

            def set_indicator(self, *a):
                pass
        self.core = Core()
        self.p = cpu_modul.Wtyczka()
        self.p.core = self.core
        self.p.cfg = {"enabled": True, "delay_s": 30, "maps": {}}
        self.p.dane_monitora({"pid": {}})

    def widok(self, status, restart):
        self.core.widok = {"Genesis 1": types.SimpleNamespace(
            name="Genesis 1", enabled=True, rcon_port="27020", status=status, restart=restart)}

    def test_restart_po_doexit_bez_czerwonych_linii(self):
        for status in ("ready", "offline", "starting", "loading_mods", "engine"):
            self.widok(status, True)
            self.p._scan(0, apply_changes=True)
        self.assertEqual(self.core.logi, [])
        self.assertIn("Restart po DoExit", self.p.states["Genesis 1"]["result"])

    def test_fazy_startu_bez_doexit_tez_milcza(self):
        for status in ("offline", "starting", "loading_mods", "engine", "crash", "unknown"):
            self.widok(status, False)
            self.p._scan(0, apply_changes=True)
        self.assertEqual(self.core.logi, [])

    def test_gotowa_bez_procesu_to_nadal_ostrzezenie(self):
        self.widok("ready", False)
        self.p._scan(0, apply_changes=True)
        self.assertEqual(len(self.core.logi), 1)
        self.assertTrue(self.core.logi[0].startswith("WARN [CPU] Genesis 1"))
        self.assertIn("Brak procesu", self.core.logi[0])


# ---------------------------------------------------------------------------
# 3. Okno konsoli bez zatrzymań (tryb szybkiej edycji)
# ---------------------------------------------------------------------------
class ApiKonsoli(object):
    def __init__(self, tryb, ustaw_ok=True):
        self._tryb = tryb
        self._ok = ustaw_ok
        self.ustawione = []

    def tryb(self):
        return self._tryb

    def ustaw(self, tryb):
        self.ustawione.append(tryb)
        return self._ok


class SzybkaEdycja(unittest.TestCase):
    def test_wylacza_zostawia_reszte_trybu(self):
        api = ApiKonsoli(0x01F7)                 # typowy tryb cmd.exe: QuickEdit + EXTENDED
        self.assertEqual(K.wylacz_szybka_edycje(api), 0x01F7)
        self.assertEqual(api.ustawione, [(0x01F7 | 0x0080) & ~0x0040])
        self.assertFalse(api.ustawione[0] & K.ENABLE_QUICK_EDIT_MODE)
        self.assertTrue(api.ustawione[0] & K.ENABLE_EXTENDED_FLAGS)

    def test_zawsze_z_enable_extended_flags(self):
        # Dokumentacja: „To disable this mode, use ENABLE_EXTENDED_FLAGS without this flag”.
        api = ApiKonsoli(0x0047)                 # QuickEdit bez EXTENDED
        self.assertEqual(K.wylacz_szybka_edycje(api), 0x0047)
        self.assertEqual(api.ustawione, [0x0087])

    def test_juz_wylaczony_albo_brak_konsoli_nic_nie_robi(self):
        for api in (ApiKonsoli(0x0087), ApiKonsoli(None)):
            self.assertIsNone(K.wylacz_szybka_edycje(api))
            self.assertEqual(api.ustawione, [])

    def test_odmowa_systemu_to_brak_zmiany(self):
        self.assertIsNone(K.wylacz_szybka_edycje(ApiKonsoli(0x01F7, ustaw_ok=False)))

    def test_przywrocenie_przy_zamknieciu(self):
        api = ApiKonsoli(0x0087)
        self.assertTrue(K.przywroc_tryb(0x01F7, api))
        self.assertEqual(api.ustawione, [0x01F7])
        self.assertFalse(K.przywroc_tryb(None, api))
        self.assertEqual(api.ustawione, [0x01F7])

    def test_poza_windows_bez_zmian(self):
        if os.name == "nt":
            self.skipTest("tylko poza Windows")
        self.assertIsNone(K.wylacz_szybka_edycje())
        self.assertFalse(K.przywroc_tryb(0x01F7))

    def test_program_wylacza_przy_starcie_i_przywraca_przy_zamknieciu(self):
        zrodlo = PROGRAM.read_text(encoding="utf-8")
        self.assertIn("self._tryb_konsoli = wylacz_szybka_edycje()", zrodlo)
        zamkniecie = zrodlo.split("def _zamknij_teraz(self):", 1)[1].split("\n    def ", 1)[0]
        self.assertIn('przywroc_tryb(getattr(self, "_tryb_konsoli", None))', zamkniecie)


if __name__ == "__main__":
    unittest.main(verbosity=2)
