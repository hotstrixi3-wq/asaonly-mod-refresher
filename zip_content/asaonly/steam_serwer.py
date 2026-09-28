# -*- coding: utf-8 -*-
"""Wersja serwera ASA ze Steama i z dysku (V3.85, V3.86) — czysta logika, bez Tk i sieci.

Fakty sprawdzone u źródła (nie zgadywane):
  * ARK: Survival Ascended Dedicated Server = aplikacja Steam 2430930, pliki gry
    w depocie 2430931 (appinfo.vdf z SteamCMD użytkownika, SteamDB).
  * Stan instalacji: <katalog>/steamapps/appmanifest_2430930.acf — "buildid",
    "StateFlags" ("4" = w pełni zainstalowana) i InstalledDepots/2430931/manifest.
  * Najnowszy build: app_info_print → depots/branches/public/buildid, manifest
    depotu: depots/2430931/manifests/public/gid.
  * SteamCMD potrafi pokazać STARY build z pamięci podręcznej — przed pytaniem
    usuwa się appcache/appinfo.vdf (tak robią LinuxGSM i WindowsGSM), a
    app_info_print powtarza się kilka razy (WindowsGSM), bo pierwsze wywołanie
    bywa puste. Dlatego parser bierze ostatni KOMPLETNY blok aplikacji.
  * Tekst wyjścia SteamCMD bywa ucięty przy przekierowaniu na Windows, więc
    drugim źródłem jest binarny appcache/appinfo.vdf (format v41 sprawdzony na
    prawdziwym pliku: nagłówek 0x07564429, tablica napisów, klucze = indeksy).
"""
import os
import re
import struct

from .jezyk import t

APPID = 2430930
DEPOT = 2430931
PLIK_MANIFESTU = "appmanifest_%d.acf" % APPID
STAN_ZAINSTALOWANA = 4          # StateFlags "4" = Fully Installed


# ---------------------------------------------------------------------------
# Tekstowy VDF (app_info_print, appmanifest .acf) — parser liniowy
# ---------------------------------------------------------------------------
def vdf_tekst(tekst, klucze_glowne=()):
    """Tekstowy KeyValues → słownik.

    Parser liniowy (jedna para albo jeden znak klamry w linii — tak piszą
    SteamCMD i pliki .acf), bez interpretacji ukośników, więc ścieżki Windows
    go nie psują. Linie spoza VDF (komunikaty SteamCMD) są pomijane. Blok
    najwyższego poziomu trafia do wyniku dopiero po zamknięciu — ucięte wyjście
    nie nadpisze wcześniejszego kompletnego wydruku tej samej aplikacji.
    Klucz z `klucze_glowne` zawsze otwiera nowy blok najwyższego poziomu
    (porzuca niedomknięty poprzedni wydruk).
    """
    korzen = {}
    stos = []                  # [(klucz, słownik)] otwartych bloków
    czeka = None               # klucz czekający na "{"
    glowne = set(str(k) for k in klucze_glowne)
    for surowa in str(tekst or "").splitlines():
        linia = surowa.strip()
        if not linia or linia.startswith("//"):
            continue
        if linia == "{":
            if czeka is None:
                continue
            stos.append((czeka, {}))
            czeka = None
            continue
        if linia == "}":
            czeka = None
            if not stos:
                continue
            klucz, blok = stos.pop()
            if stos:
                stos[-1][1][klucz] = blok
            else:
                korzen[klucz] = blok
            continue
        if not linia.startswith('"'):
            # Komunikat SteamCMD. Na najwyższym poziomie przerywa oczekiwanie
            # na klamrę; wewnątrz bloku jest po prostu ignorowany.
            if not stos:
                czeka = None
            continue
        koniec = linia.find('"', 1)
        if koniec < 0:
            czeka = None
            continue
        klucz = linia[1:koniec]
        reszta = linia[koniec + 1:].strip()
        if not reszta:
            if klucz in glowne:
                stos = []          # nowy wydruk aplikacji — ucięty poprzedni odpada
            czeka = klucz
            continue
        if reszta == "{":
            stos.append((klucz, {}))
            czeka = None
            continue
        if len(reszta) >= 2 and reszta[0] == '"' and reszta[-1] == '"':
            wartosc = reszta[1:-1]
            if stos:
                stos[-1][1][klucz] = wartosc
            else:
                korzen[klucz] = wartosc
        czeka = None
    return korzen


def _liczba(wartosc):
    try:
        return int(str(wartosc).strip())
    except (TypeError, ValueError):
        return None


def zdalny_z_aplikacji(app):
    """{"buildid", "manifest", "czas"} z drzewa aplikacji albo None."""
    if not isinstance(app, dict):
        return None
    if isinstance(app.get("appinfo"), dict):
        app = app["appinfo"]
    depoty = app.get("depots")
    if not isinstance(depoty, dict):
        return None
    galezie = depoty.get("branches")
    public = galezie.get("public") if isinstance(galezie, dict) else None
    if not isinstance(public, dict):
        return None
    buildid = _liczba(public.get("buildid"))
    if not buildid:
        return None
    manifest = None
    depot = depoty.get(str(DEPOT))
    manifesty = depot.get("manifests") if isinstance(depot, dict) else None
    m = manifesty.get("public") if isinstance(manifesty, dict) else None
    if isinstance(m, dict):
        manifest = str(m.get("gid") or "") or None
    elif m:
        manifest = str(m)
    return {"buildid": buildid, "manifest": manifest,
            "czas": _liczba(public.get("timeupdated"))}


def zdalny_z_konsoli(tekst, appid=APPID):
    """Najnowszy build z wyjścia app_info_print albo None."""
    return zdalny_z_aplikacji(vdf_tekst(tekst, klucze_glowne=(str(appid),)).get(str(appid)))


# ---------------------------------------------------------------------------
# api.steamcmd.net (V3.86) — szybkie wykrywanie nowego buildu
# ---------------------------------------------------------------------------
# Sprawdzone 26.09.2026: https://api.steamcmd.net/v1/info/2430930 zwraca
# {"status": "success", "data": {"2430930": {"depots": {"branches": {"public":
# {"buildid": "25535041", "timeupdated": "1790364583"}}, "2430931": {"manifests":
# {"public": {"gid": "6068136383897274900", "size": "12141718519", ...}}}}}}}.
# Usługa nieoficjalna (nie Valve), bez klucza; wg jej strony dane pojawiają się
# „zwykle w kilka sekund” po zmianie na Steamie. Limitów zapytań nie podaje.
URL_API = "https://api.steamcmd.net/v1/info/%d"


def zdalny_z_api(dane, appid=APPID):
    """{"buildid", "manifest", "czas", "rozmiar"} z odpowiedzi api.steamcmd.net albo None."""
    if not isinstance(dane, dict) or dane.get("status") != "success":
        return None
    app = (dane.get("data") or {}).get(str(appid)) if isinstance(dane.get("data"), dict) else None
    wynik = zdalny_z_aplikacji(app)
    if wynik is None:
        return None
    depot = app["depots"].get(str(DEPOT)) if isinstance(app.get("depots"), dict) else None
    m = ((depot or {}).get("manifests") or {}).get("public") if isinstance(depot, dict) else None
    wynik["rozmiar"] = _liczba(m.get("size")) if isinstance(m, dict) else None
    return wynik


# ---------------------------------------------------------------------------
# content_log.txt SteamCMD — prawdziwy powód porażki
# ---------------------------------------------------------------------------
# 25.09 wyjście konsoli mówiło tylko „Error! App '2430930' state is 0x6 after
# update job.”; powód był wyłącznie w logs/content_log.txt, np.:
#   CDepotDownloadMgr::BYldRequestDepotManifest(App: 2430930, Depot: 2430931,
#   Manifest: 8699400601246504390, branch: ): Failed to get manifest request code,
#   'Access Denied'
#   AppID 2430930 update canceled : Failed downloading 1 manifests (No connection)
_WAZNE_W_LOGU = re.compile(
    r"Failed to get manifest request code|update canceled|Access Denied|disk space|"
    r"not enough|No space|Disk write failure|Failed to write|corrupt|state is 0x|"
    r"Failed installing|Missing configuration", re.I)
_ODMOWA_MANIFESTU = re.compile(
    r"Manifest:\s*(\d+).*Failed to get manifest request code,\s*'Access Denied'")
# 26.09 (V3.86.0, świeżo pobrany SteamCMD, pusta appcache\appinfo.vdf):
#   konsola:     ERROR! Failed to install app '2430930' (Missing configuration)
#   content_log: Failed installing AppID 2430930 (Missing configuration)
# appinfo_log: o informację o 2430930 SteamCMD poprosił sekundę przed porażką.
# Druga próba 5 min później (w appinfo.vdf 737 aplikacji) dostała ją w 2 s
# i pobrała cały build. To samo przy ASA na Windows zgłaszano w AMP — rada:
# po prostu ponowić („It's a steamcmd bug”).
_BRAK_KONFIGURACJI = re.compile(r"Missing configuration", re.I)


def ostatnia_sesja_logu(tekst):
    """Linie content_log.txt od ostatniego startu SteamCMD („Client version”)."""
    linie = str(tekst or "").splitlines()
    for i in range(len(linie) - 1, -1, -1):
        if "Client version:" in linie[i]:
            return linie[i:]
    return linie


def powod_z_logu(tekst, maks=4):
    """Najważniejsze linie ostatniej sesji content_log.txt (dosłownie, bez czasu)."""
    wynik = []
    for linia in ostatnia_sesja_logu(tekst):
        if _WAZNE_W_LOGU.search(linia):
            czysta = re.sub(r"^\[[0-9: -]+\]\s*", "", linia).strip()
            if czysta and czysta not in wynik:
                wynik.append(czysta)
    return wynik[-maks:]


def odmowa_manifestu(tekst):
    """GID manifestu, którego Steam odmówił w ostatniej sesji, albo None."""
    for linia in ostatnia_sesja_logu(tekst):
        m = _ODMOWA_MANIFESTU.search(linia)
        if m:
            return m.group(1)
    return None


def brak_konfiguracji(wyjscie, log=""):
    """True, gdy ten przebieg SteamCMD skończył się „Missing configuration”
    (wyjście konsoli albo ostatnia sesja content_log.txt)."""
    if _BRAK_KONFIGURACJI.search(str(wyjscie or "")):
        return True
    return any(_BRAK_KONFIGURACJI.search(linia) for linia in ostatnia_sesja_logu(log))


# ---------------------------------------------------------------------------
# Ustawienia updatera ASADedicatedManager (user.config) — tylko do odczytu
# ---------------------------------------------------------------------------
# Sprawdzone w kodzie managera 3.8.2.3 (UpdateService, UpdateSettings) i w jego
# user.config: „Enable automatic update checking” = AutoCheckUpdates,
# „Update all servers / Only update cache !” = AutoApplyUpdates. Przed własną
# aktualizacją cache manager zabija KAŻDY steamcmd.exe (taskkill /F /IM
# steamcmd.exe /T) — dwa updatery naraz się pogryzą.
USTAWIENIA_MANAGERA = ("AutoCheckUpdates", "AutoApplyUpdates", "UpdateMethod",
                       "CacheUpdatePath", "UpdateCheckIntervalMinutes")


def ustawienia_managera_z_xml(tekst):
    """{nazwa: wartość} wybranych ustawień z user.config (bez haseł i tokenów)."""
    wynik = {}
    for nazwa in USTAWIENIA_MANAGERA:
        m = re.search(r'<setting name="%s"[^>]*>\s*<value>(.*?)</value>' % re.escape(nazwa),
                      str(tekst or ""), re.S)
        if m:
            wynik[nazwa] = m.group(1).strip()
    return wynik


def znajdz_user_config(localappdata):
    """Najświeższy user.config managera albo None (…\\ASADedicatedManager\\*\\*\\user.config)."""
    baza = os.path.join(str(localappdata or ""), "ASADedicatedManager")
    kandydaci = []
    try:
        for a in os.listdir(baza):
            pa = os.path.join(baza, a)
            if not os.path.isdir(pa):
                continue
            for b in os.listdir(pa):
                plik = os.path.join(pa, b, "user.config")
                if os.path.isfile(plik):
                    kandydaci.append((os.path.getmtime(plik), plik))
    except OSError:
        return None
    return max(kandydaci)[1] if kandydaci else None


def updater_managera(localappdata):
    """("wylaczony" | "wlaczony" | "nieznany", opis, ustawienia)."""
    plik = znajdz_user_config(localappdata)
    if plik is None:
        return "nieznany", t("nie znalazłem ustawień managera (user.config)",
                             "the manager settings (user.config) were not found"), {}
    try:
        with open(plik, "r", encoding="utf-8-sig", errors="replace") as fh:
            ust = ustawienia_managera_z_xml(fh.read())
    except OSError as exc:
        return "nieznany", t("nie mogę odczytać %s: %s", "cannot read %s: %s") % (plik, exc), {}
    if ust.get("AutoCheckUpdates", "").lower() == "true":
        return "wlaczony", t("w managerze włączone „Enable automatic update checking”",
                             "the manager has \"Enable automatic update checking\" on"), ust
    return "wylaczony", t("updater managera wyłączony", "the manager updater is off"), ust


# ---------------------------------------------------------------------------
# Binarny appcache/appinfo.vdf (drugie źródło)
# ---------------------------------------------------------------------------
_MAGIA = {0x07564427: 40, 0x07564428: 60, 0x07564429: 60}   # bajty nagłówka wpisu


def appinfo_aplikacja(dane, appid=APPID):
    """Drzewo jednej aplikacji z binarnego appinfo.vdf albo None.

    Obsługuje wersje 0x07564427/28/29 (w 29 klucze są indeksami tablicy
    napisów). Każdy błąd formatu = None (źródło po prostu nie zadziałało).
    """
    try:
        magia, _ = struct.unpack_from("<II", dane, 0)
        naglowek_wpisu = _MAGIA.get(magia)
        if naglowek_wpisu is None:
            return None
        pozycja = 8
        napisy = None
        koniec_wpisow = len(dane)
        if magia == 0x07564429:
            (offset,) = struct.unpack_from("<q", dane, 8)
            pozycja = 16
            (ile,) = struct.unpack_from("<I", dane, offset)
            p = offset + 4
            napisy = []
            for _ in range(ile):
                e = dane.index(b"\0", p)
                napisy.append(dane[p:e].decode("utf-8", "replace"))
                p = e + 1
            koniec_wpisow = offset
        while pozycja + 8 <= koniec_wpisow:
            app, rozmiar = struct.unpack_from("<II", dane, pozycja)
            if app == 0:
                return None
            start = pozycja + 8
            if app == int(appid):
                drzewo, _ = _kv_binarny(dane, start + naglowek_wpisu, napisy)
                return drzewo
            pozycja = start + rozmiar
    except (struct.error, ValueError, IndexError, UnicodeDecodeError, RecursionError):
        return None
    return None


def _kv_binarny(dane, pozycja, napisy):
    wynik = {}
    while True:
        typ = dane[pozycja]
        pozycja += 1
        if typ == 0x08:
            return wynik, pozycja
        if napisy is not None:
            (i,) = struct.unpack_from("<I", dane, pozycja)
            pozycja += 4
            klucz = napisy[i]
        else:
            e = dane.index(b"\0", pozycja)
            klucz = dane[pozycja:e].decode("utf-8", "replace")
            pozycja = e + 1
        if typ == 0x00:
            wartosc, pozycja = _kv_binarny(dane, pozycja, napisy)
        elif typ == 0x01:
            e = dane.index(b"\0", pozycja)
            wartosc = dane[pozycja:e].decode("utf-8", "replace")
            pozycja = e + 1
        elif typ in (0x02, 0x04, 0x06):          # int32, color, pointer
            (wartosc,) = struct.unpack_from("<i", dane, pozycja)
            pozycja += 4
        elif typ == 0x03:                          # float32
            (wartosc,) = struct.unpack_from("<f", dane, pozycja)
            pozycja += 4
        elif typ in (0x07, 0x0A):                  # uint64, int64
            (wartosc,) = struct.unpack_from("<Q", dane, pozycja)
            pozycja += 8
        else:
            raise ValueError("nieznany typ KeyValues %r" % typ)
        wynik[klucz] = wartosc


# ---------------------------------------------------------------------------
# Instalacja na dysku
# ---------------------------------------------------------------------------
def katalog_instalacji(folder_logu):
    """Katalog serwera z folderu logu mapy (…/ShooterGame/Saved/Logs) albo None.

    Idzie w górę ścieżki do katalogu „ShooterGame”; instalacja to jego rodzic.
    """
    sciezka = str(folder_logu or "").strip()
    if not sciezka:
        return None
    sciezka = os.path.normpath(sciezka)
    while True:
        rodzic = os.path.dirname(sciezka)
        if os.path.basename(sciezka).lower() == "shootergame":
            return rodzic if rodzic and rodzic != sciezka else None
        if not rodzic or rodzic == sciezka:
            return None
        sciezka = rodzic


def sciezka_manifestu(katalog):
    return os.path.join(katalog, "steamapps", PLIK_MANIFESTU)


def lokalny_z_manifestu(tekst):
    """{"buildid", "manifest", "stan", "cel"} z appmanifest_2430930.acf albo None."""
    drzewo = vdf_tekst(tekst).get("AppState")
    if not isinstance(drzewo, dict):
        return None
    buildid = _liczba(drzewo.get("buildid"))
    if not buildid:
        return None
    manifest = None
    depoty = drzewo.get("InstalledDepots")
    depot = depoty.get(str(DEPOT)) if isinstance(depoty, dict) else None
    if isinstance(depot, dict):
        manifest = str(depot.get("manifest") or "") or None
    return {"buildid": buildid, "manifest": manifest,
            "stan": _liczba(drzewo.get("StateFlags")),
            "cel": _liczba(drzewo.get("TargetBuildID"))}


def czytaj_lokalny(katalog):
    """(dane, błąd) — dane jak w lokalny_z_manifestu, błąd to tekst albo None."""
    sciezka = sciezka_manifestu(katalog)
    try:
        with open(sciezka, "r", encoding="utf-8", errors="replace") as fh:
            tekst = fh.read()
    except FileNotFoundError:
        return None, "brak"
    except OSError as exc:
        return None, str(exc)
    dane = lokalny_z_manifestu(tekst)
    return (dane, None) if dane else (None, "format")


# ---------------------------------------------------------------------------
# SteamCMD: komendy, postęp, wynik
# ---------------------------------------------------------------------------
_WSPOLNE = ["+@ShutdownOnFailedCommand", "1", "+@NoPromptForPassword", "1"]


def komenda_info(steamcmd, appid=APPID, powtorzen=4):
    """Pytanie o najnowszy build (app_info_print powtórzony — pierwszy bywa pusty)."""
    argv = [steamcmd] + _WSPOLNE + ["+login", "anonymous", "+app_info_update", "1"]
    for _ in range(max(1, int(powtorzen))):
        argv += ["+app_info_print", str(appid)]
    return argv + ["+quit"]


def komenda_update(steamcmd, katalog, walidacja=True, appid=APPID):
    """Aktualizacja jednej instalacji (force_install_dir PRZED login — wymóg SteamCMD)."""
    argv = [steamcmd] + _WSPOLNE + ["+force_install_dir", str(katalog),
                                    "+login", "anonymous", "+app_info_update", "1",
                                    "+app_update", str(appid)]
    if walidacja:
        argv.append("validate")
    return argv + ["+quit"]


_POSTEP = re.compile(r"Update state \((0x[0-9a-fA-F]+)\)\s*([a-zA-Z ]+?),\s*progress:\s*([0-9.]+)")


def postep(linia):
    """("downloading", 6.42) z linii postępu SteamCMD albo None."""
    m = _POSTEP.search(str(linia or ""))
    if not m:
        return None
    try:
        return m.group(2).strip(), float(m.group(3))
    except ValueError:
        return None


def wynik_update(tekst, kod, appid=APPID):
    """("ok"|"blad", szczegół) z wyjścia `app_update`.

    Ostatecznym dowodem jest i tak appmanifest po zakończeniu — ta funkcja
    rozpoznaje tylko oczywiste przypadki z tekstu i kodu wyjścia.
    """
    tekst = str(tekst or "")
    blad = re.search(r"Error! App '%d'[^\r\n]*" % int(appid), tekst)
    if blad:
        return "blad", blad.group(0).strip()
    # Tylko wielkie ERROR! — SteamCMD pisze tak błędy; zwykłe „Failed …” bywa
    # nieszkodliwym komunikatem startowym.
    inny = re.search(r"(?m)^\s*(ERROR![^\r\n]*)", tekst)
    sukces = re.search(r"Success! App '%d'[^\r\n]*" % int(appid), tekst)
    if sukces and not inny:
        return "ok", sukces.group(0).strip()
    if inny:
        return "blad", inny.group(1).strip()
    if kod not in (0, None):
        return "blad", t("kod wyjścia %s", "exit code %s") % kod
    return "blad", t("brak potwierdzenia", "no confirmation")


# ---------------------------------------------------------------------------
# Decyzja: które mapy aktualizować
# ---------------------------------------------------------------------------
MAKS_PROB = 3
ODSTEP_PROB_S = 30 * 60


def proby_dozwolone(historia, teraz, maks=MAKS_PROB, odstep=ODSTEP_PROB_S):
    """(czy_wolno, powód) dla listy czasów wcześniejszych nieudanych prób."""
    historia = sorted(float(x) for x in (historia or ()) if isinstance(x, (int, float)))
    if len(historia) >= maks:
        return False, "limit"
    if historia and teraz - historia[-1] < odstep:
        return False, "odstep"
    return True, ""


def potrzebuje(zdalny, lokalny):
    """Czy mapa ma starszy build niż Steam (buildid rosną — porównanie liczb)."""
    if not zdalny or not lokalny:
        return False
    return int(lokalny["buildid"]) < int(zdalny["buildid"])


# ---------------------------------------------------------------------------
# V3.86: decyzje dla cache
# ---------------------------------------------------------------------------
def cache_gotowy(dane):
    """Cache nadaje się do kopiowania: czytelny appmanifest i StateFlags 4."""
    return bool(dane) and dane.get("stan") == STAN_ZAINSTALOWANA and bool(dane.get("buildid"))


def cache_do_aktualizacji(zdalny, dane_cache):
    """Czy cache trzeba pobrać/zaktualizować (brak, niepełny albo starszy niż Steam)."""
    if not cache_gotowy(dane_cache):
        return True
    return bool(zdalny) and int(dane_cache["buildid"]) < int(zdalny["buildid"])


def mapy_do_przeniesienia(lokalne, dane_cache, zdalny):
    """Mapy ze starszym buildem niż cache — tylko gdy cache jest gotowy i nie
    wiadomo o nowszym buildzie na Steamie (inaczej najpierw cache, potem mapy:
    jeden restart zamiast dwóch)."""
    if not cache_gotowy(dane_cache):
        return []
    if zdalny and int(dane_cache["buildid"]) < int(zdalny["buildid"]):
        return []
    cel = int(dane_cache["buildid"])
    wynik = []
    for nazwa, info in sorted((lokalne or {}).items()):
        dane = (info or {}).get("dane")
        if (info or {}).get("blad") or not dane:
            continue
        if int(dane["buildid"]) < cel:
            wynik.append(nazwa)
    return wynik


def domyslny_katalog_cache(katalogi_map):
    """Folder cache obok serwerów: <wspólny rodzic pierwszej mapy>\\ASA UPDATES REFRESHER."""
    katalogi = sorted(k for k in (katalogi_map or ()) if k)
    if not katalogi:
        return None
    return os.path.join(os.path.dirname(os.path.normpath(katalogi[0])), "ASA UPDATES REFRESHER")


def _norm(sciezka):
    return os.path.normcase(os.path.normpath(os.path.abspath(str(sciezka))))


def konflikt_katalogu_cache(cache, katalogi_map, cache_managera=None):
    """Powód, dla którego ten folder nie może być cache, albo None."""
    if not cache:
        return t("nie ustawiono folderu cache", "no cache folder is set")
    c = _norm(cache)
    for k in katalogi_map or ():
        if not k:
            continue
        m = _norm(k)
        if c == m or c.startswith(m + os.sep) or m.startswith(c + os.sep):
            return t("folder cache pokrywa się z katalogiem serwera %s", "the cache folder overlaps the server folder %s") % k
    if cache_managera and _norm(cache_managera) == c:
        return t("to jest cache managera (%s) — refresher potrzebuje własnego",
                 "this is the manager's cache (%s) — the refresher needs its own") % cache_managera
    return None
