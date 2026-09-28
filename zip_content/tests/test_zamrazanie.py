# -*- coding: utf-8 -*-
"""V3.85: wstrzymanie managera na czas SteamCMD — dzierżawa, wznowienie, strażnik."""
import json
import os
import tempfile
import unittest

from asaonly import zamrazanie as Z


class ApiAtrapa(object):
    """Procesy jako słownik pid -> start; zamrożone liczone jak w Windows (licznik)."""

    def __init__(self, procesy=None, odmowa=()):
        self.procesy_ = dict(procesy or {})         # pid -> (nazwa, start)
        self.licznik = {}
        self.odmowa = set(odmowa)
        self.zabite = []
        self.straznicy = []

    def procesy(self, nazwa):
        return [pid for pid, (n, _) in self.procesy_.items() if n.lower() == nazwa.lower()]

    def czas_startu(self, pid):
        if pid == os.getpid():
            return 123456
        if pid not in self.procesy_:
            raise OSError("brak")
        return self.procesy_[pid][1]

    def zyje(self, pid, start=None):
        return pid in self.procesy_ and (start is None or self.procesy_[pid][1] == start)

    def dostep_wstrzymania(self, pid):
        if pid in self.odmowa:
            raise OSError(5, "Access is denied")

    def zamroz(self, pid):
        if pid in self.odmowa:
            raise OSError(5, "Access is denied")
        self.licznik[pid] = self.licznik.get(pid, 0) + 1

    def odmroz(self, pid):
        self.licznik[pid] = max(0, self.licznik.get(pid, 0) - 1)

    def zakoncz(self, pid):
        self.zabite.append(pid)
        self.procesy_.pop(pid, None)

    def uruchom_straznika(self, sciezka):
        self.straznicy.append(sciezka)


class Zamrazarka(unittest.TestCase):
    def setUp(self):
        self.katalog = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(self.katalog, f)) for f in os.listdir(self.katalog)])
        self.dzierzawa = os.path.join(self.katalog, "zamrozenie.json")

    def test_zamrozenie_i_wznowienie(self):
        api = ApiAtrapa({10: ("ASADedicatedManager.exe", 111), 20: ("inny.exe", 1)})
        z = Z.Zamrazarka(self.dzierzawa, "asadedicatedmanager.exe", api=api)
        self.assertEqual(z.zamroz(), (True, ""))
        self.assertEqual(api.licznik, {10: 1})
        self.assertEqual(api.straznicy, [self.dzierzawa])
        with open(self.dzierzawa, encoding="utf-8") as fh:
            dane = json.load(fh)
        self.assertEqual(dane["manager"], [{"pid": 10, "start": 111, "stan": "zamrozony"}])
        self.assertEqual(z.zamroz(), (False, "juz"))            # nie zamrażamy dwa razy
        self.assertEqual(z.odmroz(), [])
        self.assertEqual(api.licznik, {10: 0})
        self.assertFalse(os.path.exists(self.dzierzawa))

    def test_brak_managera_i_brak_uprawnien(self):
        z = Z.Zamrazarka(self.dzierzawa, "ASADedicatedManager.exe", api=ApiAtrapa())
        self.assertEqual(z.zamroz(), (False, "brak_procesu"))
        api = ApiAtrapa({10: ("ASADedicatedManager.exe", 1), 11: ("ASADedicatedManager.exe", 2)},
                        odmowa={11})
        z = Z.Zamrazarka(self.dzierzawa, "ASADedicatedManager.exe", api=api)
        ok, powod = z.zamroz()
        self.assertFalse(ok)
        self.assertEqual(powod, "niejednoznaczny_manager")
        # Kilku managerów bez jednoznacznej ścieżki: żaden nie zostaje ruszony.
        self.assertEqual(api.licznik, {})
        self.assertFalse(os.path.exists(self.dzierzawa))
        self.assertFalse(Z.Zamrazarka(self.dzierzawa, "", api=api).zamroz()[0])

    def test_odzyskanie_po_awarii_refreshera(self):
        api = ApiAtrapa({10: ("ASADedicatedManager.exe", 111)})
        api.licznik[10] = 1                                       # zostało zamrożone
        Z.zapisz_dzierzawe(self.dzierzawa, {"manager": [{"pid": 10, "start": 111},
                                                        {"pid": 99, "start": 5}]})
        z = Z.Zamrazarka(self.dzierzawa, "ASADedicatedManager.exe", api=api)
        self.assertEqual(z.odzyskaj_po_awarii().wznowione, (10,)) # PID 99 już nie żyje
        self.assertEqual(api.licznik[10], 0)
        self.assertFalse(os.path.exists(self.dzierzawa))
        self.assertEqual(z.odzyskaj_po_awarii().stan, "NONE")

    def test_dzierzawa_zywego_refreshera_nie_jest_ruszana(self):
        # Np. ten sam proces po zmianie języka, gdy instalacja jeszcze trwa.
        api = ApiAtrapa({10: ("ASADedicatedManager.exe", 111), 7: ("python.exe", 70)})
        api.licznik[10] = 1
        Z.zapisz_dzierzawe(self.dzierzawa, {"refresher": {"pid": 7, "start": 70},
                                            "manager": [{"pid": 10, "start": 111}]})
        z = Z.Zamrazarka(self.dzierzawa, "ASADedicatedManager.exe", api=api)
        self.assertEqual(z.odzyskaj_po_awarii().stan, "OWNER_ALIVE")
        self.assertEqual(api.licznik[10], 1)                      # nadal wstrzymany
        self.assertTrue(os.path.exists(self.dzierzawa))           # dzierżawa zostaje

    def test_pid_uzyty_ponownie_nie_jest_wznawiany(self):
        api = ApiAtrapa({10: ("ASADedicatedManager.exe", 222)})  # inny proces z tym samym PID
        Z.zapisz_dzierzawe(self.dzierzawa, {"manager": [{"pid": 10, "start": 111}]})
        z = Z.Zamrazarka(self.dzierzawa, "ASADedicatedManager.exe", api=api)
        self.assertEqual(z.odzyskaj_po_awarii().wznowione, ())
        self.assertEqual(api.licznik, {})


class Straznik(unittest.TestCase):
    def dzierzawa(self, refresher=True, steam=False, limit=1000.0):
        return {"refresher": {"pid": 1, "start": 1} if refresher else {"pid": 7, "start": 7},
                "manager": [{"pid": 10, "start": 111}],
                "steamcmd": {"pid": 2, "start": 2} if steam else None, "limit": limit}

    def test_decyzje(self):
        zyje = lambda pid, start: pid in (1, 2)                                   # noqa: E731
        d = Z.decyzja_straznika
        self.assertEqual(d(self.dzierzawa(), 10.0, zyje), "czekaj")                 # wszystko OK
        self.assertEqual(d(self.dzierzawa(refresher=False), 10.0, zyje), "odmroz")  # refresher padł
        # Refresher padł, ale SteamCMD jeszcze instaluje — manager nie może ruszyć serwera.
        self.assertEqual(d(self.dzierzawa(refresher=False, steam=True), 10.0, zyje), "czekaj")
        self.assertEqual(d(self.dzierzawa(steam=True), 1000.0 + 30 * 60 + 1, zyje),
                         "czekaj")
        self.assertEqual(d(self.dzierzawa(), 1001.0, zyje), "czekaj")              # żywy także po limicie

    def test_petla_czeka_na_steamcmd_potem_wznawia(self):
        with tempfile.TemporaryDirectory() as katalog:
            sciezka = os.path.join(katalog, "d.json")
            Z.zapisz_dzierzawe(sciezka, self.dzierzawa(refresher=False, steam=True))
            api = ApiAtrapa({10: ("ASADedicatedManager.exe", 111), 2: ("steamcmd.exe", 2)})
            api.licznik[10] = 1
            kroki = []

            def spij(_):
                kroki.append(1)
                if len(kroki) == 3:
                    api.procesy_.pop(2)                  # SteamCMD skończył
            self.assertEqual(Z.straznik(sciezka, api=api, zegar=lambda: 10.0, spij=spij), "odmrozono")
            self.assertEqual(len(kroki), 3)
            self.assertEqual(api.licznik[10], 0)
            self.assertFalse(os.path.exists(sciezka))

    def test_petla_konczy_gdy_refresher_sam_wznowil(self):
        with tempfile.TemporaryDirectory() as katalog:
            sciezka = os.path.join(katalog, "d.json")
            self.assertEqual(Z.straznik(sciezka, api=ApiAtrapa(), spij=lambda _: None), "koniec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
