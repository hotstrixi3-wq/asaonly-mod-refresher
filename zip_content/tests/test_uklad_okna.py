# -*- coding: utf-8 -*-
"""V3.85.3: układ głównego okna — PRAWDZIWA aplikacja (Tk) w kopii programu.

Do 3.85.2 jeden górny rząd wypychał przyciski pluginów oraz „Wykonaj zaległe
aktualizacje” i „Anuluj procedurę” poza okno o domyślnej szerokości.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAPY = {"Extinction": 27121, "Ragnarok": 27122}


def _wewnatrz(widget, rodzic):
    return str(widget) == str(rodzic) or str(widget).startswith(str(rodzic) + ".")


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "brak ekranu")
class UkladOkna(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="asaonly-uklad-"))
        app_dir = cls.tmp / "program"
        shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns(
            "tests", "symulacja", "__pycache__", ".git", ".pytest_cache", "CONFIG_*", "STEAMCMD"))
        cls.app_dir = app_dir
        stamp = time.strftime("%d.%m.%Y %H-%M-%S")
        for nazwa, port in MAPY.items():
            logi = cls.tmp / "serwery" / nazwa / "ShooterGame" / "Saved" / "Logs"
            logi.mkdir(parents=True)
            tab_dir = app_dir / "CONFIG_MAPS_TABS" / nazwa
            (tab_dir / "CONFIG_SECRET_RCON").mkdir(parents=True)
            cfg = {"ip": "127.0.0.1", "port": str(port), "log_path": str(logi), "tail_log": False,
                   "mod_ids": "928548", "map_on": True, "name": nazwa,
                   "lines": [{"time": "0", "cmd": "DoExit", "on": True}]}
            (tab_dir / ("CONFIG_MAP %s - zapis %s.json" % (nazwa, stamp))).write_text(
                json.dumps(cfg), encoding="utf-8")
        (app_dir / "CONFIG_PROGRAM").mkdir()
        (app_dir / "CONFIG_PROGRAM" / ("CONFIG_PROGRAM - zapis %s.json" % stamp)).write_text(json.dumps({
            "lang": "pl", "interval": 300, "auto_rcon": False,
            "plugins": {"konfiguracje": {"enabled": True}}}), encoding="utf-8")
        os.environ["ASAONLY_DEBUG_LOG"] = str(cls.tmp / "asa_debug.log")
        sys.path.insert(0, str(app_dir))
        spec = importlib.util.spec_from_file_location("asaonly_program_uklad",
                                                      str(app_dir / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"))
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.app = cls.mod.App()
        cls.app.geometry("900x880+0+0")
        for _ in range(40):                       # układ i BadgeFlow (Configure → relayout)
            cls.app.update()
            time.sleep(0.02)

    @classmethod
    def tearDownClass(cls):
        app = cls.app
        app._destroying = True
        try:
            app.plugin_host.stop_all()
        except Exception:
            pass
        for tab in app.tabs.values():
            tab._stop_threads()
        app.destroy()
        os.environ.pop("ASAONLY_DEBUG_LOG", None)
        shutil.rmtree(cls.tmp, True)

    def test_pluginy_maja_wlasny_pasek(self):
        app = self.app
        self.assertTrue(_wewnatrz(app.btn_plugins, app.frm_pluginy))
        self.assertTrue(_wewnatrz(app.frm_plugin_actions, app.frm_pluginy))
        przyciski = app.plugin_host.main_action_buttons
        self.assertIn("rcon_admin", przyciski)
        self.assertIn("aktualizacja_serwera", przyciski)
        for przycisk in przyciski.values():
            self.assertTrue(_wewnatrz(przycisk, app.frm_plugin_actions))

    def test_procedura_w_ramce_status(self):
        app = self.app
        for w in (app.btn_check_now, app.btn_pending, app.btn_cancel, app.chk_auto, app.chk_pusty):
            self.assertTrue(_wewnatrz(w, app.frm_status), str(w))

    def test_nic_nie_wypada_poza_okno_o_domyslnej_szerokosci(self):
        app = self.app
        prawa = app.winfo_rootx() + app.winfo_width()
        widoczne = [app.btn_lang, app.btn_about, app.btn_add, app.btn_mods_win, app.lbl_admin,
                    app.btn_plugins, app.btn_check_now, app.btn_pending, app.btn_cancel]
        widoczne += list(app.plugin_host.main_action_buttons.values())
        for w in widoczne:
            self.assertTrue(w.winfo_ismapped(), str(w))
            self.assertLessEqual(w.winfo_rootx() + w.winfo_width(), prawa, str(w))

    def test_kazda_mapa_ma_wlasny_zapis_i_znacznik_zmian(self):
        app = self.app
        self.assertEqual(sorted(app.tabs), sorted(MAPY))
        for nazwa, tab in app.tabs.items():
            self.assertTrue(_wewnatrz(tab.btn_zapisz, tab), nazwa)
            tab._odswiez_zapis()
            self.assertEqual(tab.lbl_zapis.cget("text"), "", nazwa)      # świeżo wczytana = zapisana
        tab = app.tabs["Ragnarok"]
        tab.var_tab_mods.set("928548,933099")
        tab._on_mods_edited()
        self.assertIn("niezapisane", tab.lbl_zapis.cget("text"))
        self.assertEqual(app.tabs["Extinction"].lbl_zapis.cget("text"), "")   # inna mapa czysta
        tab.btn_zapisz.invoke()
        self.assertEqual(tab.lbl_zapis.cget("text"), "")
        katalog = self.app_dir / "CONFIG_MAPS_TABS" / "Ragnarok"
        najnowszy = sorted(katalog.glob("CONFIG_MAP Ragnarok - zapis *.json"), key=os.path.getmtime)[-1]
        self.assertEqual(json.loads(najnowszy.read_text(encoding="utf-8"))["mod_ids"], "928548,933099")


if __name__ == "__main__":
    unittest.main(verbosity=2)
