# -*- coding: utf-8 -*-
"""V3.85.2: konsola pisana w osobnym wątku — zaznaczenie w konsoli nie zatrzymuje okna."""
import pathlib
import threading
import time
import unittest

from asaonly.konsola import PisarzKonsoli

ROOT = pathlib.Path(__file__).resolve().parents[1]


class StojacaKonsola(object):
    """Jak konsola Windows w trybie zaznaczania: zapis czeka, aż zaznaczenie zniknie."""

    def __init__(self):
        self.puszczona = threading.Event()
        self.tekst = []

    def write(self, s):
        self.puszczona.wait(10)
        self.tekst.append(s)

    def flush(self):
        pass


class Pisarz(unittest.TestCase):
    def test_zapis_nie_blokuje_gdy_konsola_stoi(self):
        konsola = StojacaKonsola()
        p = PisarzKonsoli(konsola)
        t0 = time.time()
        for i in range(200):
            p.pisz("linia %d\n" % i)
        self.assertLess(time.time() - t0, 0.5)            # wątek okna idzie dalej
        self.assertEqual(konsola.tekst, [])
        konsola.puszczona.set()                           # koniec zaznaczania
        p.zamknij(5.0)
        self.assertEqual("".join(konsola.tekst), "".join("linia %d\n" % i for i in range(200)))

    def test_zamkniecie_nie_wisi_na_stojacej_konsoli(self):
        konsola = StojacaKonsola()
        p = PisarzKonsoli(konsola)
        p.pisz("x\n")
        t0 = time.time()
        p.zamknij(0.2)
        self.assertLess(time.time() - t0, 2.0)
        konsola.puszczona.set()

    def test_watek_okna_nie_pisze_do_konsoli(self):
        zrodlo = (ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py").read_text(encoding="utf-8")
        tik = zrodlo.split("def _tick(self):", 1)[1].split("\n    def ", 1)[0]
        # V3.86.2: kolejkę dziennika opróżnia _oproznij_dziennik (konsola + plik).
        oproznij = zrodlo.split("def _oproznij_dziennik(self):", 1)[1].split("\n    def ", 1)[0]
        for kod in (tik, oproznij):
            self.assertNotIn("sys.stdout", kod)
            self.assertNotIn(".write(", kod)
        self.assertIn("self._oproznij_dziennik()", tik)
        self.assertIn("self._konsola.pisz(", oproznij)
        self.assertIn("plik.pisz(", oproznij)
        self.assertIn("def report_callback_exception(self", zrodlo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
