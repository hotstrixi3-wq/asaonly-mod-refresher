# -*- coding: utf-8 -*-
"""V3.82: plugin 87 „Kontrola czasu RCON” — ładowanie, praca w tle, panel."""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

from asaonly.pluginy import PluginHost

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLIK = ROOT / "PLUGINY" / "87_kontrola_czasu.py"
_spec = importlib.util.spec_from_file_location("kontrola_czasu_plugin_test", PLIK)
modul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(modul)


class Var:
    def __init__(self, v): self.v = v
    def get(self): return self.v


class Tab:
    def __init__(self, port, wiersze, wlaczona=True):
        self.var_map_on = Var(wlaczona)
        self.var_ip = Var("127.0.0.1")
        self.var_port = Var(str(port))
        self.ustaw(wiersze)

    def ustaw(self, wiersze):
        self.rows = [{"time": str(t), "cmd": c, "on": on} for t, c, on in wiersze]


class App:
    def __init__(self, tabs=None, config=None):
        self.logs = []
        self.tags = []
        self.tabs = dict(tabs or {})
        self.config_data = dict(config or {})
        self.plugin_host = None

    def log(self, x, tag=None):
        self.logs.append(str(x)); self.tags.append(tag)

    def log_warn(self, x):
        self.log(x, "warn")

    def tr(self, key, **kw): return key
    def post_ui(self, cb): cb()
    def run_async(self, fn, *args): fn(*args)
    def request_save(self): pass
    def save_config(self, silent=False): return True


def klaster():
    return {
        "Ragnarok": Tab(27022, [(205, "doExit", True), ("", "", False)]),
        "Extinction": Tab(27021, [(405, "DoExit", True), ("", "", True), ("", "", True)]),
    }


class HostZJednymPluginem(unittest.TestCase):
    def setUp(self):
        self.katalog = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.katalog, True)
        shutil.copy(PLIK, self.katalog)
        self.app = App(klaster())
        self.host = PluginHost(self.app, self.katalog)
        self.app.plugin_host = self.host
        self.host.load_all()
        self.host.start_all()
        self.plugin = self.host.get("kontrola_czasu")

    def logi_kontroli(self):
        return [x for x in self.app.logs if x.startswith("[KONTROLA CZASU]")]

    def test_ladowanie_i_domyslnie_wlaczony(self):
        self.assertIsNotNone(self.plugin)
        self.assertFalse(self.plugin.required)
        self.assertIn("kontrola_czasu", self.host._active)
        self.assertTrue(self.host._effective_enabled(self.plugin))
        self.assertEqual(self.plugin.main_action_text, "KONTROLA CZASU")
        self.assertTrue(self.plugin.self_test()["ok"])

    def test_tlo_loguje_tylko_nowe_ustalenia(self):
        self.host.tick(1000.0)
        pierwsze = self.logi_kontroli()
        self.assertEqual(len(pierwsze), 3)                 # podsumowanie + 2 uwagi
        self.assertIn("0 błędów, 2 uwagi", pierwsze[0])
        self.assertTrue(any("Ragnarok — UWAGA: Czeka 205 s" in x for x in pierwsze))
        # Bez zmian = bez nowych wpisów (także po „SPRAWDŹ TERAZ”).
        self.host.tick(1006.0)
        self.plugin._odswiez(wymus=True)
        self.assertEqual(self.logi_kontroli(), pierwsze)
        # Naprawa jednej mapy nic nie dopisuje, naprawa obu — jedno „bez uwag”.
        self.app.tabs["Ragnarok"].ustaw([(0, "ServerChat Restart za 3 min 25 s", True),
                                         (205, "doExit", True)])
        self.host.tick(1012.0)
        self.assertEqual(self.logi_kontroli(), pierwsze)
        self.app.tabs["Extinction"].ustaw([(0, "DoExit", True)])
        self.host.tick(1018.0)
        self.assertEqual(self.logi_kontroli()[-1],
                         "[KONTROLA CZASU] Harmonogramy RCON bez błędów i uwag.")
        # Nowy BŁĄD trafia do dziennika jako ostrzeżenie.
        self.app.tabs["Extinction"].ustaw([(10, "", True), (20, "DoExit", True)])
        self.host.tick(1024.0)
        ostatni = self.logi_kontroli()[-1]
        self.assertIn("Extinction — BŁĄD: Wiersz 1: czas 10 s bez komendy", ostatni)
        self.assertEqual(self.app.tags[self.app.logs.index(ostatni)], "warn")

    def test_wylaczony_nie_pracuje_w_tle(self):
        self.host.set_enabled_from_manager("kontrola_czasu", False)
        self.assertFalse(self.app.config_data["plugins"]["kontrola_czasu"]["enabled"])
        self.host.tick(1000.0)
        self.assertEqual(self.logi_kontroli(), [])
        # Panel i tak działa na żądanie (tylko odczyt).
        self.assertTrue(self.plugin.panel_available_when_off)
        self.assertFalse(self.plugin.main_action_requires_enabled)


class PanelNaEkranie(unittest.TestCase):
    def test_panel_kontrola_i_podglad(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("brak ekranu: %s" % exc)
        self.addCleanup(root.destroy)
        root.withdraw()
        app = App(klaster())
        katalog = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, katalog, True)
        host = PluginHost(app, katalog)
        app.plugin_host = host
        plugin = modul.Wtyczka()
        plugin.prepare(host.core)
        plugin.panel(root)
        root.update()
        tekst = plugin.txt.get("1.0", "end")
        self.assertIn("Ragnarok", tekst)
        self.assertIn("Czeka 405 s (6:45)", tekst)
        # Bez pomiarów i bez założenia podgląd nie zgaduje.
        self.assertEqual(plugin.tree.get_children(), ())
        self.assertIn("Brak zmierzonych czasów startu", plugin.lbl_fala.cget("text"))
        plugin.var_zalozony.set("120")
        plugin._przelicz_podglad()
        root.update()
        wiersze = [plugin.tree.item(i, "values") for i in plugin.tree.get_children()]
        self.assertEqual([w[0] for w in wiersze], ["Ragnarok", "Extinction"])
        self.assertIn("Koniec fali po", plugin.lbl_fala.cget("text"))
        # Obie puste: od razu, bez ogłoszeń.
        plugin._ustaw_puste(True)
        root.update()
        wiersze = [plugin.tree.item(i, "values") for i in plugin.tree.get_children()]
        self.assertEqual([(w[1], w[2], w[3]) for w in wiersze],
                         [("pusta", "—", "0:00"), ("pusta", "—", "2:00")])
        plugin._zamknij_okno()
        self.assertIsNone(plugin.okno)


if __name__ == "__main__":
    unittest.main(verbosity=2)
