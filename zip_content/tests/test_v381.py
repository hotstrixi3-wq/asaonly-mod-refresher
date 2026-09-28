# -*- coding: utf-8 -*-
"""V3.81: regresje na PRAWDZIWYCH danych z działającego klastra (bez sekretów)."""
import unittest

from asaonly import kolejka as K
from asaonly.procedura import ProcedureMixin
from asaonly.serwer_wersje import parse_cfcore_event
from asaonly.server_tab import validate_rcon_line_values

# Linia skopiowana z prawdziwego ShooterGame.log (ASA 93.28, 2026-09-20).
LINIA_LOADGAMEMODS = (
    "[2026.09.20-03.09.27:845][ 18]UShooterEngine::LoadGameMods Loading Mod "
    "ShooterGame/Mods/83374/928548_7005633/ShinyAscended/Content/"
    "PrimalGameData_Shiny.uasset : 928548")

# Linie RCON z działającej konfiguracji V3.74 (20.09.2026), bez haseł.
LINIE_V374 = {
    "Genesis 1": [{"time": "5", "cmd": "doExit", "on": True},
                  {"time": "", "cmd": "", "on": False},
                  {"time": "", "cmd": "", "on": False}],
    "Ragnarok": [{"time": "205", "cmd": "doExit", "on": True},
                 {"time": "", "cmd": "", "on": False}],
    "Extinction": [{"time": "405", "cmd": "DoExit", "on": True},
                   {"time": "", "cmd": "", "on": True},
                   {"time": "", "cmd": "", "on": True},
                   {"time": "", "cmd": "", "on": True},
                   {"time": "", "cmd": "", "on": True}],
}


def aktywne(rows):
    return [(r["time"], r["cmd"]) for r in rows if r.get("on", True)]


class WersjeZLoguSerwera(unittest.TestCase):
    def test_prawdziwa_linia_loadgamemods_daje_wersje(self):
        ev = parse_cfcore_event(LINIA_LOADGAMEMODS)
        self.assertEqual(ev["type"], "mods_loaded")
        self.assertEqual(ev["mods"], {"928548": "7005633"})

    def test_stary_format_par_nadal_dziala(self):
        ev = parse_cfcore_event("UShooterEngine::LoadGameMods: 928548 (7005633), 929684 (8510257)")
        self.assertEqual(ev["mods"], {"928548": "7005633", "929684": "8510257"})

    def test_prawdziwe_linie_cfcore(self):
        ev = parse_cfcore_event("[2026.09.17-19.23.36:034][ 18]LogCFCore: Mod: Cybers Structures "
                                "QoL+ (Crossplay) (940975) requires upgrade/downgrade (8673705 -> 8837561)")
        self.assertEqual((ev["type"], ev["mod_id"], ev["file_id"]),
                         ("upgrade_required", "940975", "8837561"))


class KonfiguracjaZywegoKlastra(unittest.TestCase):
    def test_zaznaczone_puste_wiersze_extinction_nie_blokuja(self):
        # V3.74 na tych danych zatrzymałaby procedurę CAŁEGO klastra.
        linie, blad = validate_rcon_line_values(aktywne(LINIE_V374["Extinction"]))
        self.assertIsNone(blad)
        self.assertEqual(linie, [(405, "DoExit")])

    def test_czasy_sa_lokalne_puste_mapy_ida_od_razu(self):
        mapy = []
        for nazwa in ("Genesis 1", "Ragnarok", "Extinction"):
            linie, blad = validate_rcon_line_values(aktywne(LINIE_V374[nazwa]))
            self.assertIsNone(blad)
            mapy.append(K.Mapa(nazwa, linie))
        self.assertEqual([m.t_wyjscia_ludzie for m in mapy], [5, 205, 405])
        for m in mapy:
            m.ustaw_tryb("pusto")
            self.assertEqual((m.t_wyjscia, m.harmonogram), (0, []))

    def test_czekanie_bez_komunikatu_jest_rozpoznawalne(self):
        # Procedura ostrzega: 205/405 s czekania bez ServerChat nic graczom nie daje.
        m = K.Mapa("Ragnarok", [(205, "doExit")])
        self.assertTrue(m.t_wyjscia_ludzie and not any(K.jest_komunikatem(c) for _, c in m.przed))


class _Zmienna:
    def __init__(self, v): self.v = v
    def get(self): return self.v


class _KoniecKolejki(ProcedureMixin):
    """Minimalna aplikacja: metody zdefiniowane w KLASIE, jak w prawdziwym App."""
    def __init__(self):
        self.zapisy = 0; self.odswiezenia = 0; self.dziennik = []
        self.pending_updates = []; self.updated_mods = []
        self.watch_maps = set(); self.tabs = {}
        self.restart_active = True; self.watch_active = True
        self.auto_rcon = _Zmienna(True); self.procedure_run = {"run_id": "x"}

    def save_config(self, silent=False): self.zapisy += 1
    def _refresh_pending_ui(self): self.odswiezenia += 1
    def log(self, tekst, *a, **k): self.dziennik.append(tekst)
    def tr(self, klucz, **kw): return klucz


class _Zaleglosci(ProcedureMixin):
    def __init__(self, pending):
        self.pending_updates = pending; self.mod_names = {}; self.tabs = {}

    def _targets_for_mid(self, mid): return []
    def log_warn(self, *a): pass


class JednaProbaNaWersje(unittest.TestCase):
    def test_nieudana_proba_przezywa_restart_programu(self):
        app = _Zaleglosci([{"mid": "928548", "name": "Shiny", "fid": "7005700",
                            "targets": ["Ragnarok"], "verified": [], "qualified": True,
                            "nieudane_proby": {"Ragnarok": "7005700", "Usunieta": "1"}}])
        app._normalize_pending_updates()
        p = app.pending_updates[0]
        self.assertEqual(p["nieudane_proby"], {"Ragnarok": "7005700"})
        self.assertTrue(app._proba_juz_byla(p, "Ragnarok"))

    def test_nowa_wersja_kasuje_zapis_proby(self):
        app = _Zaleglosci([{"mid": "928548", "name": "Shiny", "fid": "7005700",
                            "targets": ["Ragnarok"], "verified": [], "qualified": True,
                            "nieudane_proby": {"Ragnarok": "7005700"}}])
        app._add_or_update_pending("928548", "Shiny", "7005800", targets=["Ragnarok"])
        p = app.pending_updates[0]
        self.assertNotIn("nieudane_proby", p)
        self.assertFalse(app._proba_juz_byla(p, "Ragnarok"))


class KoniecKolejki(unittest.TestCase):
    def test_koniec_kolejki_zapisuje_konfiguracje_i_odswieza_zaleglosci(self):
        # Blizna V3.80.35: metody szukane w self.__dict__ nigdy się nie wykonywały,
        # więc koniec kolejki nie zapisywał konfiguracji (czasy startu, wersje).
        app = _KoniecKolejki()
        app._finish_coordinator()
        self.assertEqual((app.zapisy, app.odswiezenia), (1, 1))
        self.assertFalse(app.restart_active or app.watch_active)
        self.assertIsNone(app.procedure_run)


if __name__ == "__main__":
    unittest.main(verbosity=2)
