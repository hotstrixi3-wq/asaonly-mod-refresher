# -*- coding: utf-8 -*-
"""Przeniesienie nowego buildu z cache refreshera do katalogu mapy (V3.86).

Dlaczego tak (sprawdzone 25–26.09.2026 na komputerze serwerów):
  * SteamCMD aktualizuje instalację tylko wtedy, gdy ma w swoim depotcache
    manifest buildu, który na niej leży. Mapy instalował SteamCMD managera,
    więc SteamCMD refreshera prosił Steam o stary manifest i dostawał
    „Access Denied” (content_log.txt, 9 prób 25.09 21:30–22:55).
  * Manager robi to inaczej i to działa: jeden cache aktualizowany zawsze tym
    samym SteamCMD, a potem kopiowanie plików z cache do serwerów (jego kod:
    CacheUpdateManager.ApplyCacheToProfileAsync, pomija „steamapps” i
    „steamcmd”; appmanifest kopiowany osobno — UpdateManifestForProfile).
Tu: ta sama zasada, ale
  * kopiowane są tylko pliki, które się różnią (manager kopiuje zawsze całe
    ok. 12 GB — to zapisy na SSD i dłuższy postój serwera),
  * każda podmiana idzie przez plik tymczasowy, a stary plik trafia do kopii
    zapasowej w katalogu mapy; dziennik na dysku pozwala cofnąć wszystko —
    także po awarii refreshera (robi to strażnik z asaonly.zamrazanie),
  * appmanifest mapy jest podmieniany jako ostatni: jego build = dowód, że
    pliki przeszły w całości.

Czysta logika plików, bez Tk i sieci — testowana na prawdziwym systemie plików.
"""
import json
import os
import shutil
import time
from dataclasses import dataclass

from .jezyk import t

KATALOG_KOPII = ".refresher-kopia"
PLIK_DZIENNIKA = "dziennik.json"
SUFIKS_NOWY = ".refresher-tmp"
REL_MANIFESTU = os.path.join("steamapps", "appmanifest_2430930.acf")
# Katalogi najwyższego poziomu, których nie kopiujemy (jak manager), i dane serwera.
POMIJANE_GORA = ("steamapps", "steamcmd", KATALOG_KOPII)
POMIJANE_PREFIKSY = (os.path.join("shootergame", "saved") + os.sep,)
TOLERANCJA_CZASU_NS = 1000000            # 1 ms — różnice zaokrągleń systemu plików
BLOK = 1024 * 1024


@dataclass(frozen=True)
class WynikSynchronizacji:
    ok: bool
    powod: str
    stat: dict
    safe_to_resume: bool

    def __iter__(self):
        # Zachowanie interfejsu odczytu dla istniejących wywołań i testów.
        return iter((self.ok, self.powod, self.stat))

    def __getitem__(self, index):
        return (self.ok, self.powod, self.stat)[index]


def _pomijany(rel):
    czesci = rel.split(os.sep)
    if czesci and czesci[0].lower() in POMIJANE_GORA:
        return True
    niska = rel.lower() + (os.sep if not rel.endswith(os.sep) else "")
    return any(niska.startswith(p) for p in POMIJANE_PREFIKSY)


def pliki_zrodla(zrodlo):
    """[(rel, os.stat_result)] plików cache bez katalogów pomijanych."""
    wynik = []
    for katalog, podkatalogi, pliki in os.walk(zrodlo):
        rel_kat = os.path.relpath(katalog, zrodlo)
        if rel_kat == ".":
            rel_kat = ""
        podkatalogi[:] = [d for d in podkatalogi
                          if not _pomijany(os.path.join(rel_kat, d) if rel_kat else d)]
        for nazwa in pliki:
            rel = os.path.join(rel_kat, nazwa) if rel_kat else nazwa
            if _pomijany(rel) or nazwa.endswith(SUFIKS_NOWY):
                continue
            wynik.append((rel, os.stat(os.path.join(katalog, nazwa))))
    wynik.sort()
    return wynik


def _ta_sama_tresc(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            ka = fa.read(BLOK)
            kb = fb.read(BLOK)
            if ka != kb:
                return False
            if not ka:
                return True


def _czy_ta_sama_tresc(a, b):
    """Plik mapy zajęty przez działający serwer (Windows) = nie wiadomo, więc
    kopiujemy go przy wyłączonym serwerze, zamiast wstrzymywać całą aktualizację."""
    try:
        return _ta_sama_tresc(a, b)
    except OSError:
        return False


def plan(zrodlo, cel, porownaj_tresc=True):
    """Co trzeba zrobić, żeby pliki `cel` były takie jak w `zrodlo`.

    Wynik: {"kopiuj": [rel], "czas": [rel], "bajty": n, "odcisk": {rel: [rozmiar, mtime_ns]},
            "manifest": bool, "plikow": n}
      kopiuj — brak w mapie albo inna treść,
      czas   — ta sama treść, inny czas modyfikacji (np. po kopii managera):
               wystarczy wyrównać czas, żeby następny plan był szybki,
      manifest — appmanifest cache istnieje i ma zostać skopiowany na końcu.
    Nic nie zmienia na dysku. Plików mapy, których nie ma w cache, nie dotyka.
    """
    kopiuj, czas, odcisk, bajty = [], [], {}, 0
    pliki = pliki_zrodla(zrodlo)
    for rel, st in pliki:
        docelowy = os.path.join(cel, rel)
        odcisk[rel] = [st.st_size, st.st_mtime_ns]
        try:
            st_cel = os.stat(docelowy)
        except FileNotFoundError:
            kopiuj.append(rel)
            bajty += st.st_size
            continue
        if st_cel.st_size != st.st_size:
            kopiuj.append(rel)
            bajty += st.st_size
        elif abs(st_cel.st_mtime_ns - st.st_mtime_ns) <= TOLERANCJA_CZASU_NS:
            continue
        elif porownaj_tresc and _czy_ta_sama_tresc(os.path.join(zrodlo, rel), docelowy):
            czas.append(rel)
        else:
            kopiuj.append(rel)
            bajty += st.st_size
    manifest = os.path.isfile(os.path.join(zrodlo, REL_MANIFESTU))
    if manifest:
        st = os.stat(os.path.join(zrodlo, REL_MANIFESTU))
        odcisk[REL_MANIFESTU] = [st.st_size, st.st_mtime_ns]
    return {"kopiuj": kopiuj, "czas": czas, "bajty": bajty, "odcisk": odcisk,
            "manifest": manifest, "plikow": len(pliki)}


def zmiany_zrodla(pl, zrodlo):
    """Pliki planu, które w cache zmieniły się od planowania (lista rel)."""
    zmienione = []
    sprawdzane = list(pl.get("kopiuj", ())) + list(pl.get("czas", ()))
    if pl.get("manifest"):
        sprawdzane.append(REL_MANIFESTU)
    for rel in sprawdzane:
        try:
            st = os.stat(os.path.join(zrodlo, rel))
        except OSError:
            zmienione.append(rel)
            continue
        rozmiar, mtime = pl["odcisk"].get(rel, (None, None))
        if st.st_size != rozmiar or abs(st.st_mtime_ns - int(mtime or 0)) > TOLERANCJA_CZASU_NS:
            zmienione.append(rel)
    return zmienione


def sciezka_dziennika(cel):
    return os.path.join(cel, KATALOG_KOPII, PLIK_DZIENNIKA)


def _zapisz(sciezka, dane):
    tymczasowa = sciezka + ".tmp"
    with open(tymczasowa, "w", encoding="utf-8") as fh:
        json.dump(dane, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tymczasowa, sciezka)


def _czytaj(sciezka):
    try:
        with open(sciezka, "r", encoding="utf-8") as fh:
            dane = json.load(fh)
        if not isinstance(dane, dict):
            raise ValueError("journal must be an object")
        return dane
    except FileNotFoundError:
        return None


def _ponow(fn, *args, prob=5, przerwa=1.0, spij=time.sleep):
    """Windows: antywirus albo indeksowanie potrafi na chwilę trzymać plik."""
    for i in range(prob):
        try:
            return fn(*args)
        except PermissionError:
            if i == prob - 1:
                raise
            spij(przerwa)


def _wycofaj(dziennik, spij=time.sleep, zachowaj_dziennik=False):
    """Przywróć stan sprzed synchronizacji. Zwraca listę błędów (pusta = OK)."""
    cel = dziennik["cel"]
    kopia = os.path.join(cel, KATALOG_KOPII)
    bledy = []
    for op in reversed(dziennik.get("operacje") or []):
        rel = op.get("rel")
        if not rel:
            continue
        docelowy = os.path.join(cel, rel)
        zapas = os.path.join(kopia, rel)
        try:
            if os.path.exists(zapas):
                _ponow(os.replace, zapas, docelowy, spij=spij)
            elif not op.get("istnial") and os.path.exists(docelowy):
                _ponow(os.remove, docelowy, spij=spij)
            elif op.get("istnial") and not os.path.exists(docelowy):
                raise OSError("both original file and backup are missing")
            # istniał, a kopii nie ma = oryginał nie został jeszcze ruszony
        except OSError as exc:
            bledy.append("%s: %s" % (rel, exc))
        nowy = docelowy + SUFIKS_NOWY
        try:
            if os.path.exists(nowy):
                os.remove(nowy)
        except OSError as exc:
            bledy.append("%s: %s" % (nowy, exc))
    for rel in dziennik.get("plan") or ():
        nowy = os.path.join(cel, rel) + SUFIKS_NOWY
        try:
            if os.path.exists(nowy):
                os.remove(nowy)
        except OSError as exc:
            bledy.append("%s: %s" % (nowy, exc))
    if not bledy and zachowaj_dziennik:
        dziennik["stan"] = "wycofane"
        try:
            _zapisz(os.path.join(kopia, PLIK_DZIENNIKA), dziennik)
        except OSError as exc:
            bledy.append("rollback checkpoint: %s" % exc)
    elif not bledy:
        shutil.rmtree(kopia, ignore_errors=True)
    else:
        dziennik["stan"] = "wycofanie_niepelne"
        try:
            _zapisz(os.path.join(kopia, PLIK_DZIENNIKA), dziennik)
        except OSError:
            pass
    return bledy


def przywroc_z_dziennika(sciezka, spij=time.sleep, zachowaj_dziennik=False):
    """Po awarii (refresher zniknął w trakcie kopiowania): cofnij albo posprzątaj.

    Zwraca ("brak" | "wycofane" | "zatwierdzone" | "bledy", [błędy])."""
    try:
        dziennik = _czytaj(sciezka)
        if dziennik is not None:
            cel = dziennik.get("cel")
            if not isinstance(cel, str) or not cel or os.path.normcase(os.path.realpath(sciezka)) != \
                    os.path.normcase(os.path.realpath(sciezka_dziennika(cel))):
                raise ValueError("journal target does not match its location")
            if dziennik.get("stan") not in ("w_toku", "gotowe", "wycofane", "wycofanie_niepelne"):
                raise ValueError("unknown journal state")
            operacje = dziennik.get("operacje")
            planowane = dziennik.get("plan")
            if not isinstance(operacje, list) or not isinstance(planowane, list):
                raise ValueError("missing journal operations/plan")
            for op in operacje:
                if not isinstance(op, dict) or not isinstance(op.get("istnial"), bool):
                    raise ValueError("invalid journal operation")
            for rel in planowane + [op.get("rel") for op in operacje]:
                parts = str(rel or "").replace("\\", "/").split("/")
                if not rel or any(p in ("", ".", "..") or ":" in p for p in parts):
                    raise ValueError("invalid journal path")
    except (OSError, ValueError, TypeError) as exc:
        return "bledy", ["unreadable or invalid journal: %s" % exc]
    if dziennik is None:
        return "brak", []
    if dziennik.get("stan") in ("gotowe", "wycofane"):
        if not zachowaj_dziennik:
            shutil.rmtree(os.path.dirname(sciezka), ignore_errors=True)
        return ("zatwierdzone" if dziennik["stan"] == "gotowe" else "wycofane"), []
    if not dziennik.get("cel"):
        return "bledy", [t("dziennik bez katalogu mapy", "journal without a map folder")]
    bledy = _wycofaj(dziennik, spij=spij, zachowaj_dziennik=zachowaj_dziennik)
    return ("wycofane", []) if not bledy else ("bledy", bledy)


def wykonaj(pl, zrodlo, cel, na_postep=None, spij=time.sleep, zachowaj_dziennik=False):
    """Podmień pliki mapy według planu. (ok, powód, statystyka).

    Serwer mapy MUSI być wyłączony (a manager wstrzymany) — funkcja tego nie
    sprawdza. Przy każdym błędzie wszystko wraca do stanu sprzed wywołania."""
    stat = {"skopiowane": 0, "bajty": 0, "czas": 0}
    dz_sciezka = sciezka_dziennika(cel)
    kopia = os.path.join(cel, KATALOG_KOPII)
    if os.path.exists(dz_sciezka):
        # Resztki poprzedniej, przerwanej synchronizacji — najpierw porządek.
        stan, bledy = przywroc_z_dziennika(dz_sciezka, spij=spij)
        if stan == "bledy":
            return WynikSynchronizacji(False, t("nie da się cofnąć poprzedniej przerwanej synchronizacji: %s",
                            "the previous interrupted sync cannot be undone: %s") % "; ".join(bledy), stat, False)
        if stan == "wycofane":
            # Plan liczono na mieszance plików sprzed wycofania — liczymy od nowa.
            pl = plan(zrodlo, cel)
    if os.path.exists(kopia):
        # Brak dziennika nie jest dowodem, że backup można bezpiecznie usunąć.
        return WynikSynchronizacji(False, t("kopia bez prawidłowego dziennika wymaga sprawdzenia: %s",
                                            "backup without a valid journal needs inspection: %s") % kopia, stat, False)
    zmienione = zmiany_zrodla(pl, zrodlo)
    if zmienione:
        return WynikSynchronizacji(False, t("cache zmienił się od planowania (%d plików, np. %s)",
                        "the cache changed since planning (%d files, e.g. %s)") % (
            len(zmienione), zmienione[0]), stat, True)
    kolejka = list(pl.get("kopiuj", ()))
    if pl.get("manifest"):
        kolejka.append(REL_MANIFESTU)          # zawsze ostatni: dowód kompletności
    dziennik = {"stan": "w_toku", "cel": cel, "zrodlo": zrodlo, "t": time.time(),
                "plan": kolejka, "operacje": []}
    try:
        os.makedirs(kopia, exist_ok=True)
        _zapisz(dz_sciezka, dziennik)
    except OSError as exc:
        return WynikSynchronizacji(False, t("nie mogę założyć kopii zapasowej w %s: %s",
                        "cannot create the backup in %s: %s") % (kopia, exc), stat, True)
    try:
        for i, rel in enumerate(kolejka, 1):
            zrodlowy = os.path.join(zrodlo, rel)
            docelowy = os.path.join(cel, rel)
            nowy = docelowy + SUFIKS_NOWY
            os.makedirs(os.path.dirname(docelowy) or cel, exist_ok=True)
            shutil.copy2(zrodlowy, nowy)
            rozmiar = os.path.getsize(zrodlowy)
            if os.path.getsize(nowy) != rozmiar:
                raise OSError(t("kopia %s ma inny rozmiar niż plik w cache",
                                "the copy of %s differs in size from the cache file") % rel)
            istnial = os.path.exists(docelowy)
            dziennik["operacje"].append({"rel": rel, "istnial": istnial})
            _zapisz(dz_sciezka, dziennik)
            if istnial:
                zapas = os.path.join(kopia, rel)
                os.makedirs(os.path.dirname(zapas), exist_ok=True)
                _ponow(os.replace, docelowy, zapas, spij=spij)
            _ponow(os.replace, nowy, docelowy, spij=spij)
            stat["skopiowane"] += 1
            stat["bajty"] += rozmiar
            if na_postep is not None:
                try:
                    na_postep(i, len(kolejka), rel)
                except Exception:
                    pass
        dziennik["stan"] = "gotowe"
        _zapisz(dz_sciezka, dziennik)
    except Exception as exc:
        bledy = _wycofaj(dziennik, spij=spij, zachowaj_dziennik=zachowaj_dziennik)
        powod = t("kopiowanie przerwane (%s) — przywrócono poprzednie pliki",
                  "copying interrupted (%s) — previous files restored") % exc
        if bledy:
            powod = t("kopiowanie przerwane (%s), a przywracanie NIEPEŁNE: %s — kopia zapasowa "
                      "zostaje w %s",
                      "copying interrupted (%s) and the restore is INCOMPLETE: %s — the backup "
                      "stays in %s") % (exc, "; ".join(bledy), kopia)
        return WynikSynchronizacji(False, powod, stat, not bledy)
    for rel in pl.get("czas", ()):
        # Ta sama treść — tylko czas, żeby następny plan nie czytał pliku od nowa.
        try:
            mtime = pl["odcisk"][rel][1]
            st = os.stat(os.path.join(cel, rel))
            os.utime(os.path.join(cel, rel), ns=(st.st_atime_ns, int(mtime)))
            stat["czas"] += 1
        except (OSError, KeyError, TypeError, ValueError):
            pass
    if not zachowaj_dziennik:
        shutil.rmtree(kopia, ignore_errors=True)
    return WynikSynchronizacji(True, "", stat, True)
