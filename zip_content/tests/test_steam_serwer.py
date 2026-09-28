# -*- coding: utf-8 -*-
"""V3.85: wersja serwera ASA ze Steama i z dysku — parsery i decyzje.

Struktura danych jak w prawdziwych plikach z klastra użytkownika (24.09.2026):
appinfo.vdf SteamCMD (build 25449744, depot 2430931, manifest 2491590067154671259)
i appmanifest_2430930.acf map (bez sekretów — to tylko numery wersji).
"""
import os
import struct
import tempfile
import unittest

from asaonly import steam_serwer as S

BANER = """Redirecting stderr to 'C:\\steamcmd\\logs\\stderr.txt'
[  0%] Checking for available updates...
[----] Verifying installation...
Steam Console Client (c) Valve Corporation - version 1788292693
-- type 'quit' to exit --
Loading Steam API...OK

Connecting anonymously to Steam Public...OK
Waiting for client config...OK
Waiting for user info...OK
"""


def wydruk(buildid=25449744, gid="2491590067154671259", sciezka="ShooterGame\\Binaries\\Win64\\"):
    return """AppID : 2430930, change number : 39101106/0, last change : Tue Sep 22 16:26:43 2026
"2430930"
{
\t"appid"\t\t"2430930"
\t"common"
\t{
\t\t"name"\t\t"ARK: Survival Ascended Dedicated Server"
\t\t"type"\t\t"Tool"
\t}
\t"config"
\t{
\t\t"launch"
\t\t{
\t\t\t"0"
\t\t\t{
\t\t\t\t"executable"\t\t"%s"
\t\t\t}
\t\t}
\t}
\t"depots"
\t{
\t\t"1004"
\t\t{
\t\t\t"manifests"
\t\t\t{
\t\t\t\t"public"
\t\t\t\t{
\t\t\t\t\t"gid"\t\t"7604377918839582995"
\t\t\t\t}
\t\t\t}
\t\t}
\t\t"2430931"
\t\t{
\t\t\t"manifests"
\t\t\t{
\t\t\t\t"public"
\t\t\t\t{
\t\t\t\t\t"gid"\t\t"%s"
\t\t\t\t\t"size"\t\t"12141715297"
\t\t\t\t\t"download"\t\t"9232139344"
\t\t\t\t}
\t\t\t}
\t\t}
\t\t"branches"
\t\t{
\t\t\t"public"
\t\t\t{
\t\t\t\t"buildid"\t\t"%d"
\t\t\t\t"timeupdated"\t\t"1790094403"
\t\t\t}
\t\t\t"public_test_realm"
\t\t\t{
\t\t\t\t"buildid"\t\t"21994402"
\t\t\t}
\t\t}
\t}
}
""" % (sciezka, gid, buildid)


MANIFEST = """"AppState"
{
\t"appid"\t\t"2430930"
\t"universe"\t\t"1"
\t"name"\t\t"ARK: Survival Ascended Dedicated Server"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"ARK Survival Ascended Dedicated Server"
\t"LastUpdated"\t\t"1790095624"
\t"buildid"\t\t"25449744"
\t"TargetBuildID"\t\t"25449744"
\t"InstalledDepots"
\t{
\t\t"1004"
\t\t{
\t\t\t"manifest"\t\t"7604377918839582995"
\t\t}
\t\t"2430931"
\t\t{
\t\t\t"manifest"\t\t"2491590067154671259"
\t\t\t"size"\t\t"12141715297"
\t\t}
\t}
}
"""


class TekstowyVdf(unittest.TestCase):
    def test_wydruk_app_info_print_z_banerem(self):
        z = S.zdalny_z_konsoli(BANER + wydruk())
        self.assertEqual(z, {"buildid": 25449744, "manifest": "2491590067154671259",
                             "czas": 1790094403})

    def test_konce_linii_windows_i_ukosniki_w_wartosciach(self):
        tekst = (BANER + wydruk(sciezka="C:\\ARK\\")).replace("\n", "\r\n")
        self.assertEqual(S.zdalny_z_konsoli(tekst)["buildid"], 25449744)

    def test_kilka_wydrukow_bierze_ostatni_kompletny(self):
        # WindowsGSM drukuje app_info_print 4×; pierwszy bywa pusty, ostatni bywa ucięty.
        tekst = (BANER + "No app info for AppID 2430930 found, requesting...\n"
                 + wydruk(buildid=25449744) + wydruk(buildid=25500000, gid="8699400601246504390")
                 + wydruk(buildid=25600000)[:400])
        self.assertEqual(S.zdalny_z_konsoli(tekst),
                         {"buildid": 25500000, "manifest": "8699400601246504390", "czas": 1790094403})

    def test_tylko_uciety_wydruk_to_brak_danych(self):
        self.assertIsNone(S.zdalny_z_konsoli(BANER + wydruk()[:600]))
        self.assertIsNone(S.zdalny_z_konsoli(BANER + "No app info for AppID 2430930 found, requesting...\n"))
        self.assertIsNone(S.zdalny_z_konsoli(""))

    def test_appmanifest(self):
        self.assertEqual(S.lokalny_z_manifestu(MANIFEST),
                         {"buildid": 25449744, "manifest": "2491590067154671259", "stan": 4,
                          "cel": 25449744})
        self.assertIsNone(S.lokalny_z_manifestu('"AppState"\n{\n}\n'))

    def test_czytaj_lokalny_z_dysku(self):
        with tempfile.TemporaryDirectory() as katalog:
            self.assertEqual(S.czytaj_lokalny(katalog), (None, "brak"))
            os.makedirs(os.path.join(katalog, "steamapps"))
            with open(S.sciezka_manifestu(katalog), "w", encoding="utf-8") as fh:
                fh.write(MANIFEST)
            dane, blad = S.czytaj_lokalny(katalog)
            self.assertIsNone(blad)
            self.assertEqual(dane["buildid"], 25449744)


def binarny_appinfo(appid, drzewo, wersja=0x07564429):
    """Minimalny appinfo.vdf w formacie SteamCMD (do testu parsera)."""
    napisy = []

    def klucz(k):
        if wersja == 0x07564429:
            if k not in napisy:
                napisy.append(k)
            return struct.pack("<I", napisy.index(k))
        return k.encode() + b"\0"

    def kv(d):
        out = b""
        for k, v in d.items():
            if isinstance(v, dict):
                out += b"\x00" + klucz(k) + kv(v)
            elif isinstance(v, int):
                out += b"\x02" + klucz(k) + struct.pack("<i", v)
            else:
                out += b"\x01" + klucz(k) + str(v).encode() + b"\0"
        return out + b"\x08"

    cialo = kv({"appinfo": drzewo})
    naglowek_wpisu = (40 if wersja == 0x07564427 else 60)
    wpis = struct.pack("<I", 2) + struct.pack("<I", 0) + b"\0" * (naglowek_wpisu - 8) + cialo
    wpisy = struct.pack("<II", appid, len(wpis)) + wpis + struct.pack("<I", 0)
    if wersja == 0x07564429:
        tablica = struct.pack("<I", len(napisy)) + b"".join(n.encode() + b"\0" for n in napisy)
        naglowek = struct.pack("<IIq", wersja, 1, 16 + len(wpisy))
        return naglowek + wpisy + tablica
    return struct.pack("<II", wersja, 1) + wpisy


DRZEWO = {"appid": 2430930, "depots": {
    "2430931": {"manifests": {"public": {"gid": "8699400601246504390", "size": "1"}}},
    "branches": {"public": {"buildid": 25500000, "timeupdated": 1790283000}}}}


class BinarnyAppinfo(unittest.TestCase):
    def test_wersja_41_z_tablica_napisow(self):
        dane = binarny_appinfo(2430930, DRZEWO)
        z = S.zdalny_z_aplikacji(S.appinfo_aplikacja(dane))
        self.assertEqual(z, {"buildid": 25500000, "manifest": "8699400601246504390", "czas": 1790283000})

    def test_starsze_wersje(self):
        for wersja in (0x07564427, 0x07564428):
            dane = binarny_appinfo(2430930, DRZEWO, wersja)
            self.assertEqual(S.zdalny_z_aplikacji(S.appinfo_aplikacja(dane))["buildid"], 25500000)

    def test_inna_aplikacja_i_smieci(self):
        self.assertIsNone(S.appinfo_aplikacja(binarny_appinfo(740, DRZEWO)))
        self.assertIsNone(S.appinfo_aplikacja(b"\x00" * 10))
        self.assertIsNone(S.appinfo_aplikacja(binarny_appinfo(2430930, DRZEWO)[:40]))


class KatalogISteamcmd(unittest.TestCase):
    def test_katalog_serwera_z_folderu_logu(self):
        log = os.path.join(os.sep, "ARKservers", "Ragnarok_WP", "ShooterGame", "Saved", "Logs")
        self.assertEqual(S.katalog_instalacji(log), os.path.join(os.sep, "ARKservers", "Ragnarok_WP"))
        self.assertEqual(S.katalog_instalacji(log + os.sep),
                         os.path.join(os.sep, "ARKservers", "Ragnarok_WP"))
        self.assertIsNone(S.katalog_instalacji(os.path.join(os.sep, "logi", "gdzies")))
        self.assertIsNone(S.katalog_instalacji(""))

    def test_kolejnosc_komend(self):
        argv = S.komenda_update("steamcmd.exe", "C:\\ARK\\Rag", walidacja=True)
        # force_install_dir musi być PRZED login (SteamCMD inaczej ostrzega i ignoruje).
        self.assertLess(argv.index("+force_install_dir"), argv.index("+login"))
        self.assertEqual(argv[argv.index("+force_install_dir") + 1], "C:\\ARK\\Rag")
        self.assertEqual(argv[-3:], ["2430930", "validate", "+quit"])
        self.assertNotIn("validate", S.komenda_update("s", "k", walidacja=False))
        info = S.komenda_info("steamcmd.exe")
        self.assertEqual(info.count("+app_info_print"), 4)
        self.assertLess(info.index("+app_info_update"), info.index("+app_info_print"))

    def test_postep_z_prawdziwej_linii(self):
        self.assertEqual(S.postep("[2026-09-22 18:46:44]  Update state (0x61) downloading, "
                                  "progress: 6.42 (756812737 / 11782050983)"), ("downloading", 6.42))
        self.assertEqual(S.postep(" Update state (0x81) verifying update, progress: 9.03 (1 / 2)"),
                         ("verifying update", 9.03))
        self.assertIsNone(S.postep("Loading Steam API...OK"))

    def test_wynik_update(self):
        self.assertEqual(S.wynik_update("Success! App '2430930' fully installed.", 0)[0], "ok")
        self.assertEqual(S.wynik_update("Success! App '2430930' already up to date.", 0)[0], "ok")
        stan, opis = S.wynik_update("Error! App '2430930' state is 0x202 after update job.", 8)
        self.assertEqual(stan, "blad")
        self.assertIn("0x202", opis)
        self.assertEqual(S.wynik_update("ERROR! Failed to install app '2430930' (No subscription)", 8)[0],
                         "blad")
        self.assertEqual(S.wynik_update("", 7)[0], "blad")


class Decyzje(unittest.TestCase):
    def test_potrzebuje(self):
        self.assertTrue(S.potrzebuje({"buildid": 25500000}, {"buildid": 25449744}))
        self.assertFalse(S.potrzebuje({"buildid": 25449744}, {"buildid": 25449744}))
        self.assertFalse(S.potrzebuje(None, {"buildid": 1}))

    def test_limit_i_odstep_prob(self):
        self.assertEqual(S.proby_dozwolone([], 1000.0), (True, ""))
        self.assertEqual(S.proby_dozwolone([990.0], 1000.0), (False, "odstep"))
        self.assertEqual(S.proby_dozwolone([0.0], 1000.0 + S.ODSTEP_PROB_S), (True, ""))
        self.assertEqual(S.proby_dozwolone([1.0, 2.0, 3.0], 99999.0), (False, "limit"))


FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class ApiSteamcmdNet(unittest.TestCase):
    """V3.86: odpowiedź api.steamcmd.net (skrócona prawdziwa z 26.09.2026)."""

    def dane(self):
        import json
        with open(os.path.join(FIXTURES, "api_steamcmd_2430930.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_prawdziwa_odpowiedz(self):
        self.assertEqual(S.zdalny_z_api(self.dane()),
                         {"buildid": 25535041, "manifest": "6068136383897274900", "czas": 1790364583,
                          "rozmiar": 12141718519})

    def test_bledna_odpowiedz_to_brak_danych(self):
        dane = self.dane()
        self.assertIsNone(S.zdalny_z_api(dict(dane, status="failed")))
        self.assertIsNone(S.zdalny_z_api({"status": "success", "data": {}}))
        self.assertIsNone(S.zdalny_z_api(None))
        bez_galezi = self.dane()
        del bez_galezi["data"]["2430930"]["depots"]["branches"]
        self.assertIsNone(S.zdalny_z_api(bez_galezi))


class ContentLog(unittest.TestCase):
    """V3.86: prawdziwy powód porażki z content_log.txt (sesja z 25.09.2026 21:30)."""

    def log(self):
        with open(os.path.join(FIXTURES, "content_log_access_denied.txt"), encoding="utf-8") as fh:
            return fh.read()

    def test_odmowa_manifestu_z_prawdziwego_logu(self):
        self.assertEqual(S.odmowa_manifestu(self.log()), "8699400601246504390")
        powod = " | ".join(S.powod_z_logu(self.log()))
        self.assertIn("Failed to get manifest request code, 'Access Denied'", powod)
        self.assertIn("update canceled : Failed downloading 1 manifests (No connection)", powod)
        self.assertNotIn("[2026", powod)                   # bez znaczników czasu

    def test_tylko_ostatnia_sesja(self):
        log = self.log() + ("\n[2026-09-25 22:10:26] Client version: 1788292693\n"
                            "[2026-09-25 22:10:40] AppID 2430930 finished update, 2 mounted depots\n")
        self.assertIsNone(S.odmowa_manifestu(log))
        self.assertEqual(S.powod_z_logu(log), [])


class BrakKonfiguracji(unittest.TestCase):
    """V3.86.1: pierwszy przebieg świeżo pobranego SteamCMD (26.09.2026 14:25)."""

    WYJSCIE = "ERROR! Failed to install app '2430930' (Missing configuration)"

    def log(self):
        with open(os.path.join(FIXTURES, "content_log_missing_configuration.txt"), encoding="utf-8") as fh:
            return fh.read()

    def test_prawdziwa_linia_content_log_jest_powodem(self):
        self.assertEqual(S.powod_z_logu(self.log()),
                         ["Failed installing AppID 2430930 (Missing configuration)"])

    def test_rozpoznanie_z_konsoli_albo_content_log(self):
        self.assertTrue(S.brak_konfiguracji(self.WYJSCIE))
        self.assertTrue(S.brak_konfiguracji("", self.log()))
        self.assertFalse(S.brak_konfiguracji("Success! App '2430930' fully installed.", ""))
        with open(os.path.join(FIXTURES, "content_log_access_denied.txt"), encoding="utf-8") as fh:
            self.assertFalse(S.brak_konfiguracji("Error! App '2430930' state is 0x6 after update job.",
                                                 fh.read()))

    def test_starsza_sesja_sie_nie_liczy(self):
        # 14:31 druga próba przeszła — stara porażka z 14:25 nie jest już powodem.
        log = self.log() + ("[2026-09-26 14:31:37] Client version: 1788292693\n"
                            "[2026-09-26 14:31:42] AppID 2430930 update started : download 0/9254324576\n")
        self.assertFalse(S.brak_konfiguracji("", log))
        self.assertEqual(S.powod_z_logu(log), [])


USER_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
    <userSettings>
        <ASADedicatedManager.Properties.Settings>
            <setting name="Token" serializeAs="String">
                <value>tajny-token-nie-czytac</value>
            </setting>
            <setting name="CacheUpdatePath" serializeAs="String">
                <value>C:\\ARKservers\\ASA UPDATES</value>
            </setting>
            <setting name="AutoCheckUpdates" serializeAs="String">
                <value>%s</value>
            </setting>
            <setting name="AutoApplyUpdates" serializeAs="String">
                <value>True</value>
            </setting>
            <setting name="UpdateMethod" serializeAs="String">
                <value>SteamCMD</value>
            </setting>
        </ASADedicatedManager.Properties.Settings>
    </userSettings>
</configuration>
"""


class UstawieniaManagera(unittest.TestCase):
    """V3.86: odczyt updatera ASADedicatedManager z jego user.config (tylko potrzebne klucze)."""

    def katalog(self, auto_check):
        tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        kat = os.path.join(tmp, "ASADedicatedManager", "ASADedicatedManager.exe_Url_abc", "1.0.0.0")
        os.makedirs(kat)
        with open(os.path.join(kat, "user.config"), "w", encoding="utf-8") as fh:
            fh.write(USER_CONFIG % auto_check)
        return tmp

    def test_wlaczony_updater_managera(self):
        stan, opis, ust = S.updater_managera(self.katalog("True"))
        self.assertEqual(stan, "wlaczony")
        self.assertIn("Enable automatic update checking", opis)
        self.assertEqual(ust["CacheUpdatePath"], "C:\\ARKservers\\ASA UPDATES")
        self.assertNotIn("Token", ust)                       # sekrety nie są czytane

    def test_wylaczony_i_brak_pliku(self):
        self.assertEqual(S.updater_managera(self.katalog("False"))[0], "wylaczony")
        self.assertEqual(S.updater_managera(tempfile.gettempdir() + os.sep + "brak-takiego")[0], "nieznany")


class DecyzjeCache(unittest.TestCase):
    def test_cache_do_aktualizacji(self):
        gotowy = {"buildid": 25489097, "stan": 4}
        self.assertTrue(S.cache_do_aktualizacji({"buildid": 25535041}, gotowy))
        self.assertFalse(S.cache_do_aktualizacji({"buildid": 25489097}, gotowy))
        self.assertTrue(S.cache_do_aktualizacji(None, None))                        # brak cache
        self.assertTrue(S.cache_do_aktualizacji({"buildid": 25489097}, {"buildid": 25489097, "stan": 6}))

    def test_mapy_dopiero_gdy_cache_dogonil_steam(self):
        lokalne = {"Ragnarok": {"dane": {"buildid": 25489097}}, "Genesis": {"dane": {"buildid": 25535041}},
                   "Zla": {"blad": "katalog"}}
        cache = {"buildid": 25535041, "stan": 4}
        self.assertEqual(S.mapy_do_przeniesienia(lokalne, cache, {"buildid": 25535041}), ["Ragnarok"])
        self.assertEqual(S.mapy_do_przeniesienia(lokalne, cache, None), ["Ragnarok"])
        # Steam ma jeszcze nowszy build: najpierw cache — jeden restart zamiast dwóch.
        self.assertEqual(S.mapy_do_przeniesienia(lokalne, cache, {"buildid": 25600000}), [])
        self.assertEqual(S.mapy_do_przeniesienia(lokalne, {"buildid": 25535041, "stan": 6}, None), [])

    def test_folder_cache(self):
        mapy = [os.path.join("C:", os.sep, "ARKservers", "Ragnarok_WP"),
                os.path.join("C:", os.sep, "ARKservers", "Genesis_WP")]
        domyslny = S.domyslny_katalog_cache(mapy)
        self.assertEqual(os.path.basename(domyslny), "ASA UPDATES REFRESHER")
        self.assertEqual(os.path.dirname(domyslny), os.path.dirname(mapy[0]))
        self.assertIsNone(S.konflikt_katalogu_cache(domyslny, mapy, os.path.join("C:", os.sep, "ARKservers",
                                                                                "ASA UPDATES")))
        self.assertIsNotNone(S.konflikt_katalogu_cache(mapy[0], mapy))
        self.assertIsNotNone(S.konflikt_katalogu_cache(os.path.join(mapy[0], "cache"), mapy))
        self.assertIsNotNone(S.konflikt_katalogu_cache("C:\\ARKservers\\ASA UPDATES", mapy,
                                                       "C:\\ARKservers\\ASA UPDATES"))
        self.assertIsNotNone(S.konflikt_katalogu_cache("", mapy))


if __name__ == "__main__":
    unittest.main(verbosity=2)
