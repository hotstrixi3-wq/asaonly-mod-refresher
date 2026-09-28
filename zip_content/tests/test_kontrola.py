# -*- coding: utf-8 -*-
"""V3.82: kontrola ręcznych ustawień czasu i podgląd fali (czysta logika)."""
import unittest

from asaonly import kontrola as K


def mapa(nazwa, wiersze, wlaczona=True, host="127.0.0.1", port="27020"):
    rows = [{"time": str(t), "cmd": c, "on": on} for t, c, on in wiersze]
    return K.MapaWe(nazwa, wlaczona, host, port, rows)


def poziomy(ustalenia, poziom):
    return [u.tekst for u in ustalenia if u.poziom == poziom]


SZABLON = [(0, "ServerChat RESTART SERWERA za 15 minut", True),
           (300, "ServerChat Restart za 10 minut.", True),
           (600, "ServerChat Restart za 5 minut.", True),
           (780, "ServerChat Restart za 2 minuty.", True),
           (870, "ServerChat Restart za 30 sekund!", True),
           (900, "DoExit", True)]


class CzasZKomunikatu(unittest.TestCase):
    def test_formy_polskie_i_angielskie(self):
        przypadki = {
            "ServerChat RESTART za 15 minut - zapisz się!": 900,
            "ServerChat Restart za 2 minuty.": 120,
            "ServerChat Restart za 30 sekund": 30,
            "ServerChat restart za 1 min 30 s": 90,
            "ServerChat za 2 h i 5 min": 7500,
            "Broadcast restart in 30 seconds": 30,
            "ServerChat Restart in 5 min": 300,
            "ServerChat 10min": 600,
            "ServerChat za 1,5 min": 90,
            "ServerChat restart za minutę!": 60,
            "ServerChat za pół godziny": 1800,
            "Broadcast restart in a minute": 60,
        }
        for tekst, oczekiwane in przypadki.items():
            self.assertEqual(K.czas_z_komunikatu(tekst), oczekiwane, tekst)

    def test_bez_zapowiedzi_czasu(self):
        for tekst in ("ServerChat restart o 12:30", "ServerChat Mapa 2 restart",
                      "ServerChat 5 serwerów restartuje", "ServerChat 3 sekcje", "SaveWorld", ""):
            self.assertIsNone(K.czas_z_komunikatu(tekst), tekst)

    def test_liczy_sie_pierwsze_wyrazenie(self):
        self.assertEqual(K.czas_z_komunikatu("ServerChat za 90 s, potem 5 min przerwy"), 90)


class KontrolaMapy(unittest.TestCase):
    def test_zywa_konfiguracja_v374(self):
        # Ostatni zapis z działającego klastra (20.09.2026), bez haseł.
        ext = mapa("Extinction", [(405, "DoExit", True), ("", "", True), ("", "", True),
                                  ("", "", True), ("", "", True)])
        u, linie = K.sprawdz_mape(ext)
        self.assertEqual(linie, [(405, "DoExit")])
        self.assertFalse(poziomy(u, K.BLAD))
        self.assertTrue(any("nr 2, 3, 4, 5" in x for x in poziomy(u, K.INFO)))
        uwagi = poziomy(u, K.UWAGA)
        self.assertEqual(len(uwagi), 1)
        self.assertIn("Czeka 405 s (6:45) przed DoExit", uwagi[0])
        self.assertIn("nie ma komunikatu dla graczy", uwagi[0])
        rag = mapa("Ragnarok", [(205, "doExit", True), ("", "", False)])
        u, _ = K.sprawdz_mape(rag)
        self.assertEqual(len(poziomy(u, K.UWAGA)), 1)
        self.assertIn("205 s (3:25)", poziomy(u, K.UWAGA)[0])

    def test_poprawny_szablon_bez_uwag(self):
        u, linie = K.sprawdz_mape(mapa("A", SZABLON))
        self.assertEqual(poziomy(u, K.BLAD) + poziomy(u, K.UWAGA), [])
        self.assertEqual(len(linie), 6)
        self.assertTrue(any("5 komunikatów" in x and "15:00" in x for x in poziomy(u, K.INFO)))

    def test_komunikat_niezgodny_z_czasem_doexit(self):
        u, _ = K.sprawdz_mape(mapa("A", [(0, "ServerChat Restart za 15 minut", True),
                                         (600, "DoExit", True)]))
        uwagi = poziomy(u, K.UWAGA)
        self.assertEqual(len(uwagi), 1)
        self.assertIn("zapowiada 15:00", uwagi[0])
        self.assertIn("10:00 później", uwagi[0])

    def test_tolerancja_kilku_sekund(self):
        u, _ = K.sprawdz_mape(mapa("A", [(0, "ServerChat za 30 s", True), (38, "DoExit", True)]))
        self.assertEqual(poziomy(u, K.UWAGA), [])

    def test_komunikat_razem_z_doexit(self):
        u, _ = K.sprawdz_mape(mapa("A", [(60, "ServerChat Restart teraz!", True),
                                         (0, "ServerChat za 1 min", True), (60, "DoExit", True)]))
        self.assertTrue(any("tej samej sekundzie" in x for x in poziomy(u, K.UWAGA)))

    def test_slad_starego_zegara(self):
        u, _ = K.sprawdz_mape(mapa("Fjordur", [(185, "ServerChat za 15 minut", True),
                                               (1085, "DoExit", True)]))
        uwagi = poziomy(u, K.UWAGA)
        self.assertEqual(len(uwagi), 1)
        self.assertIn("Pierwsza linia dopiero po 185 s", uwagi[0])

    def test_linie_po_doexit(self):
        u, _ = K.sprawdz_mape(mapa("A", [(0, "DoExit", True), (5, "ServerChat po", True)]))
        self.assertTrue(any("po DoExit nie zostaną wysłane" in x for x in poziomy(u, K.UWAGA)))

    def test_bledy_ktore_pomijaja_mape(self):
        przypadki = [
            (mapa("A", [(10, "", True), (20, "DoExit", True)]), "Wiersz 1: czas 10 s bez komendy"),
            (mapa("A", [("", "ServerChat x", True), (20, "DoExit", True)]), "Wiersz 1: komenda"),
            (mapa("A", [("²", "DoExit", True)]), "nie jest liczbą"),
            (mapa("A", [("-5", "DoExit", True)]), "nie jest liczbą"),
            (mapa("A", [(0, "ServerChat x", True)]), "Brak DoExit"),
            (mapa("A", [("", "", True)]), "Brak aktywnych linii"),
            (mapa("A", [(0, "DoExit", True)], host=""), "Brak adresu RCON"),
            (mapa("A", [(0, "DoExit", True)], port="70000"), "Nieprawidłowy port"),
        ]
        for m, fragment in przypadki:
            u, linie = K.sprawdz_mape(m)
            self.assertIsNone(linie, fragment)
            self.assertTrue(any(fragment in x for x in poziomy(u, K.BLAD)), (fragment, u))

    def test_wylaczony_wiersz_z_bledem_nie_przeszkadza(self):
        u, linie = K.sprawdz_mape(mapa("A", [("abc", "", False), (0, "DoExit", True)]))
        self.assertEqual(linie, [(0, "DoExit")])

    def test_mapa_wylaczona(self):
        u, linie = K.sprawdz_mape(mapa("A", [(10, "", True)], wlaczona=False))
        self.assertIsNone(linie)
        self.assertEqual([x.poziom for x in u], [K.INFO])

    def test_pomiary_czasu_startu(self):
        m = mapa("A", SZABLON)
        u, _ = K.sprawdz_mape(m, konfiguracja={"czasy_startu": {"A": [100, 140]}})
        self.assertTrue(any("2:20" in x for x in poziomy(u, K.INFO)))
        u, _ = K.sprawdz_mape(m, konfiguracja={"czasy_startu": {"B": [90]}})
        self.assertTrue(any("innej mapy: 1:30" in x for x in poziomy(u, K.INFO)))
        u, _ = K.sprawdz_mape(m, konfiguracja={})
        self.assertTrue(any("pierwsza fala pójdzie po kolei" in x for x in poziomy(u, K.INFO)))


class KontrolaKlastra(unittest.TestCase):
    def test_wspolny_port(self):
        ogolne, wynik = K.sprawdz_klaster([mapa("A", SZABLON, port="27020"),
                                           mapa("B", SZABLON, port="27020"),
                                           mapa("C", SZABLON, port="27021")])
        self.assertIsNone(wynik["A"][1])
        self.assertIsNone(wynik["B"][1])
        self.assertIsNotNone(wynik["C"][1])
        self.assertTrue(any("ma też: B" in x for x in poziomy(wynik["A"][0], K.BLAD)))

    def test_ustawienia_ogolne(self):
        ogolne, _ = K.sprawdz_klaster([mapa("A", SZABLON)], {"pusty_serwer_od_razu": False})
        self.assertTrue(any("wyłączone" in x for x in poziomy(ogolne, K.INFO)))
        ogolne, _ = K.sprawdz_klaster([mapa("A", SZABLON)], {"listplayers_pusto": ["o"]})
        self.assertTrue(any("wzorców" in x for x in poziomy(ogolne, K.UWAGA)))
        ogolne, _ = K.sprawdz_klaster([mapa("A", [(0, "SaveWorld", True)])])
        self.assertTrue(any("Żadna mapa" in x for x in poziomy(ogolne, K.UWAGA)))
        ogolne, wynik = K.sprawdz_klaster([mapa("A", SZABLON)])
        self.assertEqual((K.licz(ogolne, wynik, K.BLAD), K.licz(ogolne, wynik, K.UWAGA)), (0, 0))


class PodgladFali(unittest.TestCase):
    LINIE = [(0, "ServerChat za 15 min"), (900, "DoExit")]

    def test_bez_pomiarow_i_bez_zalozenia_nie_zgaduje(self):
        wiersze, braki = K.podglad_fali([("A", self.LINIE), ("B", self.LINIE)])
        self.assertEqual((wiersze, braki), ([], ["A", "B"]))

    def test_zgodny_z_planista_ogloszenia_na_styk(self):
        wiersze, braki = K.podglad_fali([("A", self.LINIE), ("B", self.LINIE)],
                                        czasy_startu={"A": [180], "B": [180]})
        self.assertEqual(braki, [])
        self.assertEqual([(w.nazwa, w.ogloszenia_od, w.doexit, w.gotowa) for w in wiersze],
                         [("A", 0.0, 900.0, 1080.0), ("B", 180.0, 1080.0, 1260.0)])

    def test_pierwsza_fala_po_kolei_potem_rownolegle(self):
        mapy = [(n, self.LINIE) for n in ("A", "B", "C")]
        wiersze, _ = K.podglad_fali(mapy, czas_zalozony=100)
        od = {w.nazwa: w.ogloszenia_od for w in wiersze}
        # B czeka na powrót A (planista nie ma danych), C już korzysta z pomiaru A.
        self.assertEqual(od, {"A": 0.0, "B": 1000.0, "C": 1100.0})
        self.assertEqual({w.zrodlo for w in wiersze}, {"zalozony"})

    def test_puste_najpierw_bez_ogloszen(self):
        mapy = [("A", self.LINIE), ("B", self.LINIE)]
        wiersze, _ = K.podglad_fali(mapy, puste={"B"}, czasy_startu={"A": [120], "B": [120]})
        self.assertEqual([(w.nazwa, w.tryb, w.ogloszenia_od, w.doexit) for w in wiersze],
                         [("B", "pusta", None, 0.0), ("A", "gracze", 0.0, 900.0)])

    def test_wykrywanie_wylaczone_ignoruje_puste(self):
        wiersze, _ = K.podglad_fali([("A", self.LINIE)], puste={"A"},
                                    czasy_startu={"A": [60]}, sondy=False)
        self.assertEqual((wiersze[0].tryb, wiersze[0].doexit), ("gracze", 900.0))

    def test_pomiar_innej_mapy_dla_symulacji(self):
        wiersze, braki = K.podglad_fali([("A", self.LINIE), ("B", self.LINIE)],
                                        czasy_startu={"A": [150]})
        self.assertEqual(braki, [])
        self.assertEqual({w.nazwa: w.zrodlo for w in wiersze},
                         {"A": "zmierzony", "B": "innej_mapy"})

    def test_odmiana(self):
        self.assertEqual([K.odmiana(n, "błąd", "błędy", "błędów") for n in (0, 1, 2, 5, 12, 22, 25)],
                         ["0 błędów", "1 błąd", "2 błędy", "5 błędów", "12 błędów", "22 błędy",
                          "25 błędów"])

    def test_krotkie_czekanie_bez_komunikatu_to_tylko_info(self):
        u, _ = K.sprawdz_mape(mapa("Genesis 1", [(5, "doExit", True)]))
        self.assertEqual(poziomy(u, K.UWAGA), [])
        self.assertTrue(any("Czeka 5 s przed DoExit bez komunikatu — krótko" in x
                            for x in poziomy(u, K.INFO)))

    def test_formatowanie_czasu(self):
        self.assertEqual([K.fmt_czas(x) for x in (5, 205, 3723)], ["0:05", "3:25", "1:02:03"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
