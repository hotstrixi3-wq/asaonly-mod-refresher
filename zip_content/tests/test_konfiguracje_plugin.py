# -*- coding: utf-8 -*-
"""V3.83: plugin „Konfiguracje” = dawny importer (80) + backup/przywracanie (81)."""
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from asaonly.pluginy import PluginHost

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLIK = ROOT / "PLUGINY" / "80_konfiguracje.py"
_spec = importlib.util.spec_from_file_location("konfiguracje_plugin_test", PLIK)
modul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(modul)


class App:
    def __init__(self, plugins=None):
        self.logs = []
        self.config_data = {"plugins": dict(plugins or {})} if plugins is not None else {}
        self.tabs = {}
        self.zapisy = 0
        self.zamkniecia = 0
        self.restart_active = False
        self.watch_active = False
        self.plugin_host = None

    def log(self, x, tag=None): self.logs.append(str(x))
    def log_warn(self, x): self.logs.append(str(x))
    def tr(self, key, **kw): return key
    def post_ui(self, cb): cb()
    def run_async(self, fn, *args): fn(*args)
    def request_save(self): pass

    def save_config(self, silent=False):
        self.zapisy += 1
        return True

    def _zamknij_teraz(self):
        self.zamkniecia += 1


def host_z_pluginem(app, katalog, dodatkowe=()):
    shutil.copy(PLIK, katalog)
    for nazwa, tresc in dodatkowe:
        pathlib.Path(katalog, nazwa).write_text(tresc, encoding="utf-8")
    host = PluginHost(app, katalog)
    app.plugin_host = host
    host.load_all()
    host.start_all()
    return host


class PrzejecieWyborowStarychPluginow(unittest.TestCase):
    def wlaczony(self, stare):
        with tempfile.TemporaryDirectory() as katalog:
            app = App(stare)
            host = host_z_pluginem(app, katalog)
            plugin = host.get("konfiguracje")
            return plugin.is_enabled(), host._effective_enabled(plugin), app

    def test_brak_zapisanych_wyborow_domyslnie_on(self):
        self.assertEqual(self.wlaczony({})[:2], (True, True))

    def test_oba_stare_wylaczone_zostaje_off(self):
        wynik = self.wlaczony({"importer_starych_konfigow": {"enabled": False},
                               "backup_restore": {"enabled": False}})
        self.assertEqual(wynik[:2], (False, False))
        # Wybór zapisany pod nową nazwą — przejęcie jest jednorazowe.
        self.assertEqual(wynik[2].config_data["plugins"]["konfiguracje"], {"enabled": False})

    def test_wystarczy_jeden_stary_wlaczony(self):
        wynik = self.wlaczony({"importer_starych_konfigow": {"enabled": False},
                               "backup_restore": {"enabled": True}})
        self.assertEqual(wynik[:2], (True, True))

    def test_importer_bez_zapisanego_wyboru_byl_on(self):
        wynik = self.wlaczony({"backup_restore": {"enabled": False}})
        self.assertEqual(wynik[:2], (True, True))

    def test_wlasny_zapisany_wybor_wygrywa(self):
        wynik = self.wlaczony({"konfiguracje": {"enabled": False},
                               "importer_starych_konfigow": {"enabled": True}})
        self.assertEqual(wynik[:2], (False, False))


class StarePlikiWFolderzePluginow(unittest.TestCase):
    def test_stare_pliki_obok_nastepcy_sa_pomijane(self):
        stary = ("class Wtyczka:\n    API = 1\n    nazwa = '%s'\n    manager_visible = True\n"
                 "    def start(self, core): pass\n")
        with tempfile.TemporaryDirectory() as katalog:
            app = App()
            host = host_z_pluginem(app, katalog, dodatkowe=(
                ("80_importer_starych_konfigow.py", stary % "importer_starych_konfigow"),
                ("81_backup_restore.py", stary % "backup_restore")))
            self.assertEqual([p.nazwa for p in host.plugins], ["konfiguracje"])
            self.assertTrue(any("[PLUGIN backup_restore] pominięty — zastąpiony przez konfiguracje"
                                in x for x in app.logs))


class Przywracanie(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.baza = pathlib.Path(self.tmp, "program")
        (self.baza / "CONFIG_PROGRAM").mkdir(parents=True)
        (self.baza / "CONFIG_PROGRAM" / "stary.json").write_text("{\"stary\": 1}", encoding="utf-8")
        self.zip = pathlib.Path(self.tmp, "backup.zip")
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("CONFIG_PROGRAM/przywrocony.json", json.dumps({"przywrocony": 1}))
        self.app = App({})
        self.plugin = modul.Wtyczka()
        katalog = tempfile.mkdtemp(dir=self.tmp)
        host = PluginHost(self.app, katalog)
        self.app.plugin_host = host
        self.plugin.prepare(host.core)
        self.zapisy_po_prepare = self.app.zapisy

    def przywroc(self, zgoda=True):
        with patch.object(modul.Wtyczka, "_base_dir", staticmethod(lambda: str(self.baza))), \
                patch.object(modul.filedialog, "askopenfilename", return_value=str(self.zip)) as wybor, \
                patch.object(modul.messagebox, "askyesno", return_value=zgoda), \
                patch.object(modul.messagebox, "showinfo") as info, \
                patch.object(modul.messagebox, "showwarning") as ostrzezenie, \
                patch.object(modul.messagebox, "showerror") as blad:
            self.plugin._restore(None)
        return wybor, info, ostrzezenie, blad

    def test_po_przywroceniu_program_zamyka_sie_bez_zapisu(self):
        wybor, info, _, blad = self.przywroc()
        blad.assert_not_called()
        pliki = sorted(p.name for p in (self.baza / "CONFIG_PROGRAM").iterdir())
        self.assertEqual(pliki, ["przywrocony.json"])
        self.assertEqual(self.app.zamkniecia, 1)
        self.assertEqual(self.app.zapisy, self.zapisy_po_prepare)      # żadnego zapisu
        self.assertIn("BEZ zapisywania", info.call_args[0][1])
        # Transakcja posprzątana — w katalogu programu nie zostają śmieci.
        self.assertEqual(sorted(p.name for p in self.baza.iterdir()), ["CONFIG_PROGRAM"])

    def test_odmowa_nic_nie_zmienia(self):
        self.przywroc(zgoda=False)
        self.assertEqual(sorted(p.name for p in (self.baza / "CONFIG_PROGRAM").iterdir()),
                         ["stary.json"])
        self.assertEqual(self.app.zamkniecia, 0)

    def test_w_trakcie_procedury_przywracanie_zablokowane(self):
        self.app.restart_active = True
        wybor, _, ostrzezenie, _ = self.przywroc()
        wybor.assert_not_called()
        ostrzezenie.assert_called_once()
        self.assertEqual(self.app.zamkniecia, 0)
        self.assertEqual(sorted(p.name for p in (self.baza / "CONFIG_PROGRAM").iterdir()),
                         ["stary.json"])


class ProgramGlowny(unittest.TestCase):
    def test_zamkniecie_bez_zapisu_jest_jedna_sciezka(self):
        zrodlo = (ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py").read_text(encoding="utf-8")
        cialo = zrodlo.split("    def _on_close(self):", 1)[1].split("    def _zamknij_teraz(self):", 1)[0]
        self.assertIn("self._zamknij_teraz()", cialo)
        self.assertNotIn("self.destroy()", cialo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
