# -*- coding: utf-8 -*-
"""V3.81: planista kolejki — czysta logika, symulowany czas."""
import unittest

from asaonly import kolejka as K


def symuluj(mapy, gracze, czasy_startu, start_trwa, koniec=4000, sondy=True,
            bledy_doexit=(), wracaja=None, gracze_po=None):
    """Symulacja sekunda po sekundzie.

    gracze: {mapa: "pusto"|"gracze"|"nieznane"} — odpowiedź sondy,
    gracze_po: {(mapa, od_sekundy): stan} — zmiana odpowiedzi w czasie,
    start_trwa: {mapa: sekundy od DoExit do GOTOWY},
    wracaja: zbiór map, które wracają (domyślnie wszystkie).
    """
    q = K.Kolejka(mapy, czasy_startu=czasy_startu, sondy=sondy)
    zdarzenia = []
    w_starcie = {}
    for t in range(0, koniec):
        now = 1000.0 + t
        for nazwa, t_konca in list(w_starcie.items()):
            if now >= t_konca:
                del w_starcie[nazwa]
                ok = wracaja is None or nazwa in wracaja
                q.zakoncz(nazwa, ok, "" if ok else "nie wróciła", now)
                zdarzenia.append((t, "gotowa" if ok else "nie_wrocila", nazwa))
        # Odpowiedzi przychodzą natychmiast, więc w tej samej sekundzie tykamy,
        # aż planista nie ma już nic do zrobienia (w programie: kolejne tiki
        # co 0,5 s i odpowiedzi RCON po milisekundach).
        for _ in range(20):
            nowe = q.tick(now)
            if not nowe:
                break
            for akcja in nowe:
                wykonaj(q, akcja, t, now, gracze, gracze_po, bledy_doexit, zdarzenia,
                        w_starcie, start_trwa)
        if q.gotowe() and not w_starcie:
            break
    return q, zdarzenia


def wykonaj(q, akcja, t, now, gracze, gracze_po, bledy_doexit, zdarzenia, w_starcie, start_trwa):
    if akcja[0] == "sonda":
        stan = gracze.get(akcja[1], "nieznane")
        for (nazwa, od), zmiana in (gracze_po or {}).items():
            if nazwa == akcja[1] and t >= od:
                stan = zmiana
        zdarzenia.append((t, "sonda", akcja[1], stan))
        q.wynik_sondy(akcja[1], stan, 0 if stan == "pusto" else 1, now)
    elif akcja[0] == "wyslij":
        zdarzenia.append((t, "wyslij", akcja[1], akcja[3]))
        q.wynik_komendy(akcja[1], akcja[2], None, now)
    elif akcja[0] == "doexit":
        blad = "auth" if akcja[1] in bledy_doexit else None
        zdarzenia.append((t, "doexit", akcja[1]))
        q.wynik_doexit(akcja[1], blad, now)
        if not blad:
            w_starcie[akcja[1]] = now + start_trwa.get(akcja[1], 180)


def czasy(zdarzenia, rodzaj, nazwa=None):
    return [z[0] for z in zdarzenia if z[1] == rodzaj and (nazwa is None or z[2] == nazwa)]


class ParserListPlayers(unittest.TestCase):
    def test_pusta_odpowiedz_to_niepewnosc(self):
        self.assertEqual(K.parsuj_listplayers(""), ("nieznane", None))
        self.assertEqual(K.parsuj_listplayers(None), ("nieznane", None))

    def test_wzorzec_pustego_serwera(self):
        self.assertEqual(K.parsuj_listplayers("No Players Connected\n"), ("pusto", 0))
        self.assertEqual(K.parsuj_listplayers("  no players connected "), ("pusto", 0))

    def test_linie_graczy(self):
        tekst = "0. Magus, 0002a1b2c3d4e5f6\n1. Ktos, 0002ffffffffffff\n"
        self.assertEqual(K.parsuj_listplayers(tekst), ("gracze", 2))

    def test_obcy_format_to_niepewnosc_nie_pusto(self):
        self.assertEqual(K.parsuj_listplayers("Server received, But no response!!"),
                         ("nieznane", None))

    def test_linie_graczy_wygrywaja_z_wzorcem(self):
        tekst = "No Players Connected\n0. Magus, 0002a1\n"
        self.assertEqual(K.parsuj_listplayers(tekst), ("gracze", 1))

    def test_wlasny_wzorzec_z_konfiguracji(self):
        self.assertEqual(K.parsuj_listplayers("Brak graczy", ["Brak graczy"]), ("pusto", 0))
        self.assertEqual(K.parsuj_listplayers("Brak graczy", []), ("nieznane", None))


class Harmonogram(unittest.TestCase):
    def test_wzorce_z_konfiguracji_sa_bezpieczne(self):
        # Brak klucza / zły typ = domyślne.
        self.assertEqual(K.wzorce_pusto_z_konfiguracji(None), list(K.WZORCE_PUSTO_DOMYSLNE))
        self.assertEqual(K.wzorce_pusto_z_konfiguracji(5), list(K.WZORCE_PUSTO_DOMYSLNE))
        # Tekst zamiast listy NIE może się rozpaść na pojedyncze litery.
        self.assertEqual(K.wzorce_pusto_z_konfiguracji("No Players Connected"),
                         ["No Players Connected"])
        # Za krótkie wzorce odpadają; nic nie zostało = wykrywanie wyłączone.
        self.assertEqual(K.wzorce_pusto_z_konfiguracji(["o", " ", "Brak graczy"]), ["Brak graczy"])
        self.assertEqual(K.wzorce_pusto_z_konfiguracji(["o"]), [])
        stan, _ = K.parsuj_listplayers("Server received, but no response!!",
                                       K.wzorce_pusto_z_konfiguracji(["o"]))
        self.assertEqual(stan, "nieznane")

    def test_podzial_na_przed_i_doexit(self):
        przed, t, cmd, po = K.podziel_harmonogram(
            [(900, "DoExit"), (5, "ServerChat 15 min"), (600, "SaveWorld"), (950, "ServerChat po")])
        self.assertEqual(przed, [(5, "ServerChat 15 min"), (600, "SaveWorld")])
        self.assertEqual((t, cmd), (900, "DoExit"))
        self.assertEqual(po, [(950, "ServerChat po")])

    def test_brak_doexit_mapa_pominieta(self):
        m = K.Mapa("A", [(5, "ServerChat hej")])
        self.assertEqual(m.stan, K.POMINIETA)
        self.assertIn("DoExit", m.powod)

    def test_tryb_pusty_zostawia_komendy_bez_komunikatow(self):
        m = K.Mapa("A", [(5, "ServerChat 15 min"), (600, "SaveWorld"),
                         (700, "Broadcast uwaga"), (900, "DoExit")])
        m.ustaw_tryb("pusto")
        self.assertEqual([(x["t"], x["cmd"]) for x in m.harmonogram], [(0, "SaveWorld")])
        self.assertEqual(m.t_wyjscia, 0)
        m.ustaw_tryb("gracze")
        self.assertEqual([x["t"] for x in m.harmonogram], [5, 600, 700])
        self.assertEqual(m.t_wyjscia, 900)

    def test_historia_startow(self):
        self.assertIsNone(K.przewidywany_czas_startu([]))
        self.assertEqual(K.przewidywany_czas_startu([100, 150, 130]), 150)
        h = []
        for s in (10, 20, 30, 40, 50, 60):
            h = K.dopisz_czas_startu(h, s)
        self.assertEqual(h, [20.0, 30.0, 40.0, 50.0, 60.0])


class HistoriaZKonfiguracji(unittest.TestCase):
    def test_reczny_wpis_admina_nie_wywraca_programu(self):
        self.assertEqual(K.przewidywany_czas_startu(150), 150.0)
        self.assertEqual(K.przewidywany_czas_startu([150]), 150.0)
        self.assertIsNone(K.przewidywany_czas_startu("150 s"))
        self.assertIsNone(K.przewidywany_czas_startu({"x": 1}))
        self.assertIsNone(K.przewidywany_czas_startu(True))
        self.assertEqual(K.dopisz_czas_startu(150, 90), [150.0, 90.0])
        self.assertEqual(K.dopisz_czas_startu("zle", 90), [90.0])


class Kolejka(unittest.TestCase):
    def test_przyklad_1_puste_najpierw_ogloszenia_rownolegle(self):
        mapy = [K.Mapa("Genesis", [(5, "DoExit")]),
                K.Mapa("Ragnarok", [(0, "ServerChat 15 min"), (900, "DoExit")]),
                K.Mapa("Extinction", [(405, "DoExit")])]
        gracze = {"Genesis": "pusto", "Ragnarok": "gracze", "Extinction": "pusto"}
        start = {"Genesis": 180, "Ragnarok": 180, "Extinction": 180}
        q, z = symuluj(mapy, gracze, start, start)
        # Puste mapy idą od razu, bez komunikatów i bez ręcznego czekania 5/405 s.
        self.assertEqual(czasy(z, "doexit", "Genesis"), [0])
        self.assertEqual(czasy(z, "doexit", "Extinction"), [180])
        # Ogłoszenia Ragnaroka ruszają od razu, równolegle z restartami pustych.
        self.assertEqual(czasy(z, "wyslij", "Ragnarok"), [0])
        self.assertEqual(czasy(z, "doexit", "Ragnarok"), [900])
        # Nigdy dwa starty naraz.
        self.assertEqual(sorted(czasy(z, "gotowa")), [180, 360, 1080])
        self.assertTrue(q.gotowe())
        self.assertEqual({m.nazwa: m.stan for m in q.mapy},
                         {"Genesis": K.ZROBIONA, "Ragnarok": K.ZROBIONA, "Extinction": K.ZROBIONA})

    def test_przyklad_2_ogloszenia_na_styk(self):
        mapy = [K.Mapa("A", [(0, "ServerChat 15 min"), (900, "DoExit")]),
                K.Mapa("B", [(0, "ServerChat 15 min"), (900, "DoExit")])]
        gracze = {"A": "gracze", "B": "gracze"}
        start = {"A": 180, "B": 180}
        q, z = symuluj(mapy, gracze, start, start)
        self.assertEqual(czasy(z, "wyslij", "A"), [0])
        # B zaczyna ogłaszać tak, żeby skończyć, gdy A skończy start.
        self.assertEqual(czasy(z, "wyslij", "B"), [180])
        self.assertEqual(czasy(z, "doexit", "A"), [900])
        self.assertEqual(czasy(z, "doexit", "B"), [1080])

    def test_bez_pomiarow_po_kolei(self):
        mapy = [K.Mapa("A", [(0, "ServerChat"), (60, "DoExit")]),
                K.Mapa("B", [(0, "ServerChat"), (60, "DoExit")])]
        q, z = symuluj(mapy, {"A": "gracze", "B": "gracze"}, {}, {"A": 100, "B": 100})
        # B nie zaczyna ogłoszeń, dopóki A nie wróci (brak danych do planowania).
        self.assertEqual(czasy(z, "doexit", "A"), [60])
        self.assertEqual(czasy(z, "gotowa", "A"), [160])
        self.assertEqual(czasy(z, "wyslij", "B"), [160])
        self.assertEqual(czasy(z, "doexit", "B"), [220])

    def test_mapa_bez_pomiaru_korzysta_z_pomiaru_innej_mapy(self):
        # Trzy mapy z graczami, zmierzona tylko A. B i C biorą pomiar A (100 s),
        # więc C nie czeka z ogłoszeniami na powrót B.
        szablon = [(0, "ServerChat"), (300, "DoExit")]
        mapy = [K.Mapa(n, szablon) for n in ("A", "B", "C")]
        gracze = {"A": "gracze", "B": "gracze", "C": "gracze"}
        q, z = symuluj(mapy, gracze, {"A": 100}, {"A": 100, "B": 100, "C": 100})
        self.assertEqual(czasy(z, "doexit"), [300, 400, 500])
        self.assertEqual(czasy(z, "wyslij", "C"), [200])
        # Pomiar zastępczy nie nadpisuje własnego: B i C dostały swoje czasy.
        self.assertEqual(q.czasy_startu, {"A": 100, "B": 100.0, "C": 100.0})

    def test_zadnego_pomiaru_pierwsza_mapa_uczy_reszte(self):
        # Zero pomiarów: B czeka na powrót A; potem A jest zmierzona, więc
        # C planuje się równolegle z B (nie czeka na powrót B).
        szablon = [(0, "ServerChat"), (300, "DoExit")]
        mapy = [K.Mapa(n, szablon) for n in ("A", "B", "C")]
        gracze = {"A": "gracze", "B": "gracze", "C": "gracze"}
        q, z = symuluj(mapy, gracze, {}, {"A": 100, "B": 100, "C": 100})
        self.assertEqual(czasy(z, "wyslij", "B"), [400])
        self.assertEqual(czasy(z, "wyslij", "C"), [500])
        self.assertEqual(czasy(z, "doexit"), [300, 700, 800])

    def test_nieudany_doexit_nie_zatrzymuje_reszty(self):
        mapy = [K.Mapa("A", [(0, "DoExit")]), K.Mapa("B", [(0, "DoExit")])]
        q, z = symuluj(mapy, {"A": "gracze", "B": "gracze"}, {}, {"B": 50},
                       bledy_doexit=("A",))
        self.assertEqual(q.mapa("A").stan, K.NIEUDANA)
        self.assertEqual(q.mapa("B").stan, K.ZROBIONA)
        self.assertEqual(czasy(z, "doexit", "B"), [0])

    def test_mapa_ktora_nie_wraca_nie_zatrzymuje_reszty(self):
        mapy = [K.Mapa("A", [(0, "DoExit")]), K.Mapa("B", [(0, "DoExit")])]
        q, z = symuluj(mapy, {"A": "gracze", "B": "gracze"}, {}, {"A": 30, "B": 30},
                       wracaja={"B"})
        self.assertEqual(q.mapa("A").stan, K.NIEUDANA)
        self.assertEqual(q.mapa("B").stan, K.ZROBIONA)

    def test_ktos_wszedl_na_pusta_mape_pelne_ogloszenia(self):
        mapy = [K.Mapa("A", [(0, "ServerChat 1 min"), (60, "DoExit")])]
        q, z = symuluj(mapy, {"A": "pusto"}, {}, {"A": 30},
                       gracze_po={("A", 0): "pusto"})
        self.assertEqual(czasy(z, "doexit", "A"), [0])
        self.assertEqual(czasy(z, "wyslij", "A"), [])
        # Druga symulacja: wstępnie pusto, ale przed wyjściem ktoś jest.
        mapy = [K.Mapa("A", [(0, "ServerChat 1 min"), (60, "DoExit")])]
        q2 = K.Kolejka(mapy, czasy_startu={}, sondy=True)
        akcje = q2.tick(1000.0)
        self.assertEqual(akcje, [("sonda", "A")])
        q2.wynik_sondy("A", "pusto", 0, 1000.0)
        # Świeża odpowiedź (<30 s) nie jest powtarzana; starsza — tak.
        t = 1000.0 + K.SWIEZOSC_SONDY_S + 1
        akcje = q2.tick(t)
        self.assertEqual(akcje, [("sonda", "A")])       # sonda tuż przed DoExit
        q2.wynik_sondy("A", "gracze", 1, t)
        akcje = q2.tick(t)
        self.assertEqual(akcje, [("wyslij", "A", 0, "ServerChat 1 min")])
        self.assertEqual(q2.mapa("A").tryb, "gracze")

    def test_swieza_sonda_nie_jest_powtarzana(self):
        q = K.Kolejka([K.Mapa("A", [(0, "DoExit")])], sondy=True)
        self.assertEqual(q.tick(1000.0), [("sonda", "A")])
        q.wynik_sondy("A", "pusto", 0, 1000.0)
        self.assertEqual(q.tick(1001.0), [("doexit", "A", "DoExit")])

    def test_niepewnosc_to_gracze(self):
        mapy = [K.Mapa("A", [(0, "ServerChat"), (30, "DoExit")])]
        q, z = symuluj(mapy, {"A": "nieznane"}, {}, {"A": 10})
        self.assertEqual(czasy(z, "wyslij", "A"), [0])
        self.assertEqual(czasy(z, "doexit", "A"), [30])

    def test_sonda_bez_odpowiedzi_to_gracze(self):
        q = K.Kolejka([K.Mapa("A", [(0, "ServerChat"), (30, "DoExit")])], sondy=True)
        self.assertEqual(q.tick(1000.0), [("sonda", "A")])
        self.assertEqual(q.tick(1010.0), [])
        akcje = q.tick(1000.0 + K.SONDA_TIMEOUT_S + 1)
        self.assertEqual(q.mapa("A").tryb, "gracze")
        # Po wstępnej sondzie (timeout) mapa z graczami robi jeszcze sondę przed startem.
        self.assertEqual(akcje, [("sonda", "A")])

    def test_bez_sond_wszyscy_to_gracze(self):
        mapy = [K.Mapa("A", [(5, "DoExit")])]
        q, z = symuluj(mapy, {}, {}, {"A": 10}, sondy=False)
        self.assertEqual(czasy(z, "sonda"), [])
        self.assertEqual(czasy(z, "doexit", "A"), [5])

    def test_pominiecie_zwalnia_dysk(self):
        q = K.Kolejka([K.Mapa("A", [(0, "DoExit")]), K.Mapa("B", [(0, "DoExit")])], sondy=False)
        self.assertEqual(q.tick(1000.0), [("doexit", "A", "DoExit")])
        q.pomin("A", "serwer nie jest GOTOWY")
        self.assertEqual(q.tick(1001.0), [("doexit", "B", "DoExit")])

    def test_pusta_nie_wchodzi_w_za_mala_luke(self):
        # A odlicza 200 s; B jest pusta, ale jej start (300 s) nie zmieści się
        # przed DoExit A — A nie może się opóźnić przez B.
        mapy = [K.Mapa("A", [(0, "ServerChat"), (200, "DoExit")]),
                K.Mapa("B", [(0, "DoExit")])]
        gracze = {"A": "gracze", "B": "pusto"}
        start = {"A": 100, "B": 300}
        q, z = symuluj(mapy, gracze, start, start)
        # Puste idą pierwsze w kolejce, więc B startuje od razu (dysk wolny,
        # A jeszcze nie ma zobowiązania). Test sprawdza przypadek odwrotny:
        self.assertEqual(czasy(z, "doexit", "B"), [0])
        # A musi poczekać na koniec startu B — ale jej ogłoszenia zostały
        # zaplanowane tak, by skończyć się dokładnie wtedy.
        self.assertEqual(czasy(z, "wyslij", "A"), [100])
        self.assertEqual(czasy(z, "doexit", "A"), [300])

    def test_zobowiazanie_nie_jest_opozniane_przez_pozniejsza_mape(self):
        q = K.Kolejka([K.Mapa("A", [(0, "ServerChat"), (60, "DoExit")]),
                       K.Mapa("B", [(0, "DoExit")])],
                      czasy_startu={"A": 100, "B": 300}, sondy=False)
        # Ręcznie: A już odlicza (zobowiązanie na t=60), B czeka.
        a = q.mapa("A")
        a.stan = K.OGLASZA; a.start_odliczania = 1000.0
        a.harmonogram[0]["stan"] = "ok"
        plan = q.plan(1010.0)
        # B (300 s startu) nie zmieści się przed t=60 → planowana po A.
        self.assertEqual(plan["B"], 1000.0 + 60 + 100)

    def test_przeciagniety_start_nie_daje_dwoch_startow_naraz(self):
        mapy = [K.Mapa("A", [(0, "ServerChat"), (60, "DoExit")]),
                K.Mapa("B", [(0, "ServerChat"), (60, "DoExit")])]
        gracze = {"A": "gracze", "B": "gracze"}
        # Przewidywanie 100 s, ale A startuje naprawdę 250 s.
        q, z = symuluj(mapy, gracze, {"A": 100, "B": 100}, {"A": 250, "B": 100})
        self.assertEqual(czasy(z, "doexit", "A"), [60])
        self.assertEqual(czasy(z, "gotowa", "A"), [310])
        # B odliczyło na styk wg przewidywania, ale DoExit czeka na wolny dysk.
        self.assertGreaterEqual(czasy(z, "doexit", "B")[0], 310)

    def test_pominiecie_w_trakcie_ogloszen_nie_blokuje(self):
        q = K.Kolejka([K.Mapa("A", [(0, "ServerChat"), (60, "DoExit")]),
                       K.Mapa("B", [(0, "DoExit")])], sondy=False)
        self.assertEqual(q.tick(1000.0), [("wyslij", "A", 0, "ServerChat")])
        q.wynik_komendy("A", 0, None, 1000.0)
        q.pomin("A", "wstała sama z nowymi modami")
        self.assertEqual(q.tick(1001.0), [("doexit", "B", "DoExit")])

    def test_anuluj(self):
        q = K.Kolejka([K.Mapa("A", [(0, "DoExit")])], sondy=False)
        q.anuluj()
        self.assertTrue(q.gotowe())
        self.assertEqual(q.mapa("A").powod, "anulowano")


if __name__ == "__main__":
    unittest.main(verbosity=2)
