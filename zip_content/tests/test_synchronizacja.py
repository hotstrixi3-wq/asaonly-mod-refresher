# -*- coding: utf-8 -*-
"""V3.86: przeniesienie buildu z cache do mapy — plan, podmiana, wycofanie.

Na prawdziwym systemie plików (katalog tymczasowy). Kluczowe obietnice:
  * kopiowane są tylko pliki, które się różnią; dane serwera (Saved) nietknięte,
  * każdy błąd w trakcie = mapa dokładnie taka jak przed kopiowaniem,
  * przerwane kopiowanie (awaria refreshera) da się cofnąć z dziennika,
  * appmanifest mapy zmienia się jako ostatni.
"""
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

from asaonly import synchronizacja as SYNC

REL_EXE = os.path.join("ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe")
REL_PAK = os.path.join("ShooterGame", "Content", "Paks", "ShooterGame-WindowsServer.pak")
REL_NOWY = os.path.join("ShooterGame", "Content", "Paks", "Nowy.ucas")
REL_INI = os.path.join("ShooterGame", "Saved", "Config", "WindowsServer", "Game.ini")
REL_ZAPIS = os.path.join("ShooterGame", "Saved", "SavedArks", "Ragnarok_WP.ark")


def manifest(buildid):
    return ('"AppState"\n{\n\t"appid"\t\t"2430930"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"%d"\n}\n' % buildid)


def zapisz(katalog, rel, tresc, mtime=None):
    sciezka = os.path.join(katalog, rel)
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    with open(sciezka, "wb" if isinstance(tresc, bytes) else "w") as fh:
        fh.write(tresc)
    if mtime is not None:
        os.utime(sciezka, (mtime, mtime))
    return sciezka


def czytaj(katalog, rel):
    with open(os.path.join(katalog, rel), "rb") as fh:
        return fh.read()


class Baza(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.cache = os.path.join(self.tmp, "ASA UPDATES REFRESHER")
        self.mapa = os.path.join(self.tmp, "Ragnarok_WP")
        stary, nowy = 1700000000, 1790000000
        # Cache: nowy build (exe i pak zmienione, jeden plik nowy).
        zapisz(self.cache, REL_EXE, b"EXE-NOWY", nowy)
        zapisz(self.cache, REL_PAK, b"PAK-NOWY-dluzszy", nowy)
        zapisz(self.cache, REL_NOWY, b"UCAS", nowy)
        zapisz(self.cache, os.path.join("Engine", "stale.dll"), b"STALE", stary)
        zapisz(self.cache, os.path.join("steamapps", "appmanifest_2430930.acf"), manifest(25535041), nowy)
        zapisz(self.cache, os.path.join("steamapps", "downloading", "x.tmp"), b"smiec", nowy)
        # Mapa: stary build + dane serwera, których nie wolno ruszyć.
        zapisz(self.mapa, REL_EXE, b"EXE-STARY", stary)
        zapisz(self.mapa, REL_PAK, b"PAK-STARY", stary)
        zapisz(self.mapa, os.path.join("Engine", "stale.dll"), b"STALE", stary)
        zapisz(self.mapa, REL_INI, "[ServerSettings]\nMaxPlayers=21\n", stary)
        zapisz(self.mapa, REL_ZAPIS, b"SWIAT", stary)
        zapisz(self.mapa, os.path.join("steamapps", "appmanifest_2430930.acf"), manifest(25489097), stary)
        zapisz(self.mapa, "local_version.txt", "ark_2491590067154671259", stary)


class Plan(Baza):
    def test_tylko_rozne_pliki_bez_steamapps_i_saved(self):
        pl = SYNC.plan(self.cache, self.mapa)
        self.assertEqual(sorted(pl["kopiuj"]), sorted([REL_EXE, REL_PAK, REL_NOWY]))
        self.assertEqual(pl["czas"], [])
        self.assertTrue(pl["manifest"])
        self.assertEqual(pl["plikow"], 4)                 # steamapps pominięte
        self.assertEqual(pl["bajty"], len(b"EXE-NOWY") + len(b"PAK-NOWY-dluzszy") + len(b"UCAS"))

    def test_ta_sama_tresc_inny_czas_to_tylko_czas(self):
        # Tak zostawia pliki kopia managera: ta sama treść, nowy czas modyfikacji.
        zapisz(self.mapa, os.path.join("Engine", "stale.dll"), b"STALE", 1790001234)
        pl = SYNC.plan(self.cache, self.mapa)
        self.assertEqual(pl["czas"], [os.path.join("Engine", "stale.dll")])
        self.assertNotIn(os.path.join("Engine", "stale.dll"), pl["kopiuj"])

    def test_bez_porownania_tresci_inny_czas_to_kopia(self):
        zapisz(self.mapa, os.path.join("Engine", "stale.dll"), b"STALE", 1790001234)
        pl = SYNC.plan(self.cache, self.mapa, porownaj_tresc=False)
        self.assertIn(os.path.join("Engine", "stale.dll"), pl["kopiuj"])

    def test_plik_zajety_przez_serwer_idzie_do_kopii(self):
        # Działający serwer trzyma plik bez prawa odczytu — porównanie się nie uda.
        zapisz(self.mapa, os.path.join("Engine", "stale.dll"), b"STALE", 1790001234)
        with patch.object(SYNC, "_ta_sama_tresc", side_effect=PermissionError("zajęty")):
            pl = SYNC.plan(self.cache, self.mapa)
        self.assertIn(os.path.join("Engine", "stale.dll"), pl["kopiuj"])

    def test_ten_sam_rozmiar_inna_tresc_jest_kopiowany(self):
        zapisz(self.cache, os.path.join("Engine", "stale.dll"), b"INNE", 1790000000)
        zapisz(self.mapa, os.path.join("Engine", "stale.dll"), b"STAR", 1700000000)
        pl = SYNC.plan(self.cache, self.mapa)
        self.assertIn(os.path.join("Engine", "stale.dll"), pl["kopiuj"])

    def test_saved_w_cache_nigdy_nie_trafia_do_planu(self):
        zapisz(self.cache, REL_INI, "[ServerSettings]\nMaxPlayers=70\n")
        pl = SYNC.plan(self.cache, self.mapa)
        self.assertNotIn(REL_INI, pl["kopiuj"] + pl["czas"])


class Wykonanie(Baza):
    def test_udana_podmiana(self):
        pl = SYNC.plan(self.cache, self.mapa)
        ok, powod, stat = SYNC.wykonaj(pl, self.cache, self.mapa)
        self.assertTrue(ok, powod)
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-NOWY")
        self.assertEqual(czytaj(self.mapa, REL_PAK), b"PAK-NOWY-dluzszy")
        self.assertEqual(czytaj(self.mapa, REL_NOWY), b"UCAS")
        self.assertIn(b'"buildid"\t\t"25535041"', czytaj(self.mapa, SYNC.REL_MANIFESTU))
        # Dane serwera i pliki spoza cache nietknięte.
        self.assertEqual(czytaj(self.mapa, REL_ZAPIS), b"SWIAT")
        self.assertIn(b"MaxPlayers=21", czytaj(self.mapa, REL_INI))
        self.assertEqual(czytaj(self.mapa, "local_version.txt"), b"ark_2491590067154671259")
        # Czas jak w cache — następny plan jest pusty (nic do czytania ani kopiowania).
        self.assertEqual(SYNC.plan(self.cache, self.mapa)["kopiuj"], [])
        self.assertEqual(stat["skopiowane"], 4)
        self.assertFalse(os.path.exists(os.path.join(self.mapa, SYNC.KATALOG_KOPII)))
        self.assertFalse([p for p, _, f in os.walk(self.mapa) for x in f if x.endswith(SYNC.SUFIKS_NOWY)])

    def test_blad_w_polowie_przywraca_wszystko(self):
        pl = SYNC.plan(self.cache, self.mapa)
        przed = {rel: czytaj(self.mapa, rel) for rel in (REL_EXE, REL_PAK, SYNC.REL_MANIFESTU, REL_ZAPIS)}
        prawdziwy = os.replace
        licznik = {"n": 0}

        def replace(a, b):
            # Trzecia podmiana pada (np. dysk pełny / plik zablokowany na stałe).
            if a.endswith(SYNC.SUFIKS_NOWY):
                licznik["n"] += 1
                if licznik["n"] == 3:
                    raise OSError("symulowany błąd dysku")
            return prawdziwy(a, b)
        with patch.object(SYNC.os, "replace", side_effect=replace):
            ok, powod, _ = SYNC.wykonaj(pl, self.cache, self.mapa, spij=lambda s: None)
        self.assertFalse(ok)
        self.assertIn("przywrócono", powod)
        for rel, tresc in przed.items():
            self.assertEqual(czytaj(self.mapa, rel), tresc, rel)
        self.assertFalse(os.path.exists(os.path.join(self.mapa, REL_NOWY)))      # nowy plik usunięty
        self.assertFalse(os.path.exists(os.path.join(self.mapa, SYNC.KATALOG_KOPII)))
        self.assertFalse([x for _, _, f in os.walk(self.mapa) for x in f if x.endswith(SYNC.SUFIKS_NOWY)])

    def test_zablokowany_plik_ponawiany(self):
        pl = SYNC.plan(self.cache, self.mapa)
        prawdziwy = os.replace
        stan = {"raz": True}

        def replace(a, b):
            if stan["raz"] and b.endswith("ArkAscendedServer.exe"):
                stan["raz"] = False
                raise PermissionError("antywirus trzyma plik")
            return prawdziwy(a, b)
        with patch.object(SYNC.os, "replace", side_effect=replace):
            ok, powod, _ = SYNC.wykonaj(pl, self.cache, self.mapa, spij=lambda s: None)
        self.assertTrue(ok, powod)
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-NOWY")

    def test_cache_zmieniony_od_planu_nic_nie_rusza(self):
        pl = SYNC.plan(self.cache, self.mapa)
        zapisz(self.cache, REL_EXE, b"EXE-JESZCZE-NOWSZY", 1790009999)
        ok, powod, _ = SYNC.wykonaj(pl, self.cache, self.mapa)
        self.assertFalse(ok)
        self.assertIn("cache zmienił się", powod)
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-STARY")

    def test_manifest_mapy_zmienia_sie_ostatni(self):
        pl = SYNC.plan(self.cache, self.mapa)
        kolejnosc = []
        prawdziwy = os.replace

        def replace(a, b):
            if a.endswith(SYNC.SUFIKS_NOWY):
                kolejnosc.append(os.path.relpath(b, self.mapa))
            return prawdziwy(a, b)
        with patch.object(SYNC.os, "replace", side_effect=replace):
            self.assertTrue(SYNC.wykonaj(pl, self.cache, self.mapa)[0])
        self.assertEqual(kolejnosc[-1], SYNC.REL_MANIFESTU)

    def test_stara_kopia_bez_dziennika_nie_wraca_przy_wycofaniu(self):
        # Resztka po dawnej rundzie: w kopii leży STARSZY exe. Nie może trafić do mapy.
        zapisz(os.path.join(self.mapa, SYNC.KATALOG_KOPII), REL_EXE, b"EXE-PRASTARY")
        pl = SYNC.plan(self.cache, self.mapa)
        prawdziwy = os.replace

        def replace(a, b):
            # Oryginał exe nie daje się przenieść do kopii zapasowej (plik trzymany na stałe):
            # operacja jest już w dzienniku, więc wycofanie zajrzy do kopii zapasowej.
            if SYNC.KATALOG_KOPII in b and b.endswith("ArkAscendedServer.exe"):
                raise OSError("plik zablokowany")
            return prawdziwy(a, b)
        with patch.object(SYNC.os, "replace", side_effect=replace):
            ok, _, _ = SYNC.wykonaj(pl, self.cache, self.mapa, spij=lambda s: None)
        self.assertFalse(ok)
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-STARY")


class Awaria(Baza):
    def _przerwij_po(self, ile):
        """Symulacja zniknięcia refreshera po `ile` podmianach (dziennik zostaje)."""
        pl = SYNC.plan(self.cache, self.mapa)
        prawdziwy = os.replace
        licznik = {"n": 0}

        class Znikniecie(BaseException):
            pass

        def replace(a, b):
            wynik = prawdziwy(a, b)
            if a.endswith(SYNC.SUFIKS_NOWY):
                licznik["n"] += 1
                if licznik["n"] == ile:
                    raise Znikniecie()
            return wynik
        with patch.object(SYNC.os, "replace", side_effect=replace):
            with self.assertRaises(Znikniecie):
                SYNC.wykonaj(pl, self.cache, self.mapa)

    def test_przerwane_kopiowanie_cofane_z_dziennika(self):
        self._przerwij_po(2)
        self.assertNotEqual(czytaj(self.mapa, REL_EXE), b"EXE-STARY")          # mieszanka na dysku
        stan, bledy = SYNC.przywroc_z_dziennika(SYNC.sciezka_dziennika(self.mapa))
        self.assertEqual((stan, bledy), ("wycofane", []))
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-STARY")
        self.assertEqual(czytaj(self.mapa, REL_PAK), b"PAK-STARY")
        self.assertIn(b"25489097", czytaj(self.mapa, SYNC.REL_MANIFESTU))
        self.assertFalse(os.path.exists(os.path.join(self.mapa, SYNC.KATALOG_KOPII)))

    def test_nastepna_synchronizacja_najpierw_sprzata(self):
        self._przerwij_po(1)
        pl = SYNC.plan(self.cache, self.mapa)
        ok, powod, _ = SYNC.wykonaj(pl, self.cache, self.mapa)
        self.assertTrue(ok, powod)
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-NOWY")

    def test_zatwierdzone_nie_jest_cofane(self):
        pl = SYNC.plan(self.cache, self.mapa)
        with patch.object(SYNC.shutil, "rmtree"):          # sprzątanie „nie zdążyło”
            self.assertTrue(SYNC.wykonaj(pl, self.cache, self.mapa)[0])
        dz = SYNC.sciezka_dziennika(self.mapa)
        with open(dz, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["stan"], "gotowe")
        self.assertEqual(SYNC.przywroc_z_dziennika(dz)[0], "zatwierdzone")
        self.assertEqual(czytaj(self.mapa, REL_EXE), b"EXE-NOWY")

    def test_straznik_cofa_przed_wznowieniem_managera(self):
        from asaonly import zamrazanie as Z
        self._przerwij_po(2)
        dzierzawa = os.path.join(self.tmp, "zamrozenie_managera.json")
        Z.zapisz_dzierzawe(dzierzawa, {"refresher": {"pid": 1, "start": 1}, "manager": [{"pid": 10, "start": 1}],
                                       "steamcmd": None, "limit": time.time() + 60,
                                       "kopia": SYNC.sciezka_dziennika(self.mapa)})
        kolejnosc = []
        mapa = self.mapa

        class Api(object):
            def zyje(self, pid, start=None):
                return pid == 10

            def odmroz(self, pid):
                kolejnosc.append(("odmroz", czytaj(mapa, REL_EXE)))
        self.assertEqual(Z.straznik(dzierzawa, api=Api(), spij=lambda s: None), "odmrozono")
        self.assertEqual(kolejnosc, [("odmroz", b"EXE-STARY")])            # najpierw wycofanie


if __name__ == "__main__":
    unittest.main(verbosity=2)
