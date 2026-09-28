# -*- coding: utf-8 -*-
"""V3.84: kompletna wersja angielska + drobne błędy znalezione przy przeglądzie kodu."""
import importlib.util
import pathlib
import types
import unittest

from asaonly import jezyk

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLSKIE_LITERY = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def wczytaj(plik, nazwa):
    spec = importlib.util.spec_from_file_location(nazwa, ROOT / "PLUGINY" / plik)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Var:
    def __init__(self, v): self.v = v
    def get(self): return self.v
    def set(self, v): self.v = v


class Martwy:
    """Widget zamkniętego okna: istnieje w Pythonie, ale nie w Tk."""
    def winfo_exists(self): return 0
    def configure(self, **kw): raise AssertionError("zapis do zniszczonego widgetu")
    def delete(self, *a): raise AssertionError("zapis do zniszczonego widgetu")
    def insert(self, *a): raise AssertionError("zapis do zniszczonego widgetu")


class Core:
    def __init__(self, app=None):
        self.logi, self.wskazniki = [], []
        self._app = app or types.SimpleNamespace(restart_active=False, watch_active=False)
    def application(self): return self._app
    def log(self, x, tag=None): self.logi.append(str(x))
    def warn(self, x): self.logi.append(str(x))
    def set_indicator(self, nazwa, tekst, kolor="#555555"): self.wskazniki.append(tekst)
    def post_ui(self, cb): cb()
    def run_async(self, fn, *a): fn(*a)


class TekstyPoAngielsku(unittest.TestCase):
    """Nazwy i opisy pluginów w Managerze liczą się w chwili odczytu — po EN bez polskich liter."""

    def setUp(self):
        self.addCleanup(jezyk.ustaw, "pl")

    def test_nazwy_opisy_i_przyciski_pluginow(self):
        for plik in sorted((ROOT / "PLUGINY").glob("*.py")):
            modul = wczytaj(plik.name, "en_" + plik.stem)
            plugin = modul.Wtyczka()
            for jez in ("en", "pl"):
                jezyk.ustaw(jez)
                teksty = [str(getattr(plugin, a, "") or "")
                          for a in ("manager_name", "manager_description", "main_action_text")]
                polskie = [x for x in teksty if POLSKIE_LITERY & set(x)]
                if jez == "en":
                    self.assertEqual(polskie, [], plik.name)
            jezyk.ustaw("en")
            self.assertTrue(str(plugin.manager_name).strip(), plik.name)

    def test_kontrola_czasu_pokazuje_nazwy_a_nie_identyfikatory(self):
        from asaonly import kontrola as K
        jezyk.ustaw("en")
        self.assertEqual([K.nazwa_poziomu(x) for x in (K.BLAD, K.UWAGA, K.INFO)],
                         ["ERROR", "WARNING", "INFO"])
        self.assertEqual(K.bledy_i_uwagi(1, 2), "1 error, 2 warnings")
        jezyk.ustaw("pl")
        self.assertEqual(K.nazwa_poziomu(K.BLAD), "BŁĄD")
        self.assertEqual(K.bledy_i_uwagi(5, 22), "5 błędów, 22 uwagi")


class Cpu(unittest.TestCase):
    def setUp(self):
        self.m = wczytaj("60_cpu.py", "cpu_v384")
        self.p = self.m.Wtyczka()
        self.p.core = Core()

    def test_cel_affinity_spoza_komputera_nie_jest_zgodny(self):
        # Wcześniej maska 0 dawała „ZGODNE” — ustawienie nie działało, a panel mówił, że jest OK.
        self.p.cfg = {"enabled": True, "delay_s": 30, "maps": {"A": {
            "priority_on": True, "priority": "High", "affinity_on": True, "affinity": "CPU 4096"}}}
        state = {"pid": 7, "priority_value": self.m.PRIORITIES["Normal"], "priority": "Normal",
                 "affinity_mask": 3, "affinity": "CPU 0,1"}
        self.p._apply_process = lambda *a: self.fail("przy błędnym celu nic nie zmieniamy")
        self.p._compare_and_apply("A", state)
        self.assertIn("BŁĘDNY CEL AFFINITY", state["result"])
        self.assertNotIn("ZGODNE", state["result"])
        self.assertEqual(state["color"], "#b00020")

    def test_zamkniety_panel_w_trakcie_testu_cpu(self):
        self.p.benchmark_progress = Martwy()
        self.p.benchmark_results_text = Martwy()
        self.p._pokaz_postep_testu(3)                 # bez wyjątku
        self.p._show_benchmark_results([], False)     # bez wyjątku


class Dysk(unittest.TestCase):
    def test_wynik_skanu_po_zamknieciu_okna_trafia_na_wskaznik(self):
        m = wczytaj("83_dysk_katalogi.py", "dysk_v384")
        p = m.Wtyczka()
        p.core = Core()
        p.busy = True
        p.scan_button, p.text = Martwy(), Martwy()
        p._scan_done(["A: OK"], 0)
        self.assertFalse(p.busy)
        self.assertEqual(p.core.wskazniki[-1], "ODCZYT OK")


class Rcon(unittest.TestCase):
    def test_nieudane_wstawienie_do_kolejki_odblokowuje_mape(self):
        m = wczytaj("86_rcon_admin.py", "rcon_v384")
        p = m.Wtyczka()
        p.core = Core()
        wyjscie = []
        przyciski = types.SimpleNamespace(configure=lambda **kw: None)
        p.editors["A"] = {"host": Var("127.0.0.1"), "port": Var("27020"), "password": Var("pw"),
                          "command": Var(""), "test_button": przyciski, "send_button": przyciski,
                          "output": types.SimpleNamespace(
                              configure=lambda **kw: None, see=lambda *a: None,
                              insert=lambda _gdzie, tekst: wyjscie.append(tekst))}
        p.stopping = True                              # kolejka odmawia przyjęcia komendy
        p._send("A", True)                             # TEST LISTPLAYERS — bez okienka
        self.assertNotIn("A", p.busy)
        self.assertTrue(any("BŁĄD" in x for x in wyjscie), wyjscie)


if __name__ == "__main__":
    unittest.main(verbosity=2)
