# -*- coding: utf-8 -*-
"""Kontrola ręcznych ustawień czasu (V3.82) — czysta logika, bez okien i sieci.

Sprawdza harmonogramy RCON map TYMI SAMYMI regułami, których używa procedura
(validate_rcon_line_values, duplicate_enabled_ports, Mapa i Kolejka z
kolejka.py), i przewiduje, jak pójdzie fala restartów na prawdziwym planiście.
Niczego nie wysyła do serwerów i niczego nie zapisuje.

Poziomy ustaleń:
    BŁĄD  — procedura POMINIE tę mapę (update wejdzie dopiero przy jej
            najbliższym starcie z innego powodu),
    UWAGA — procedura zadziała, ale czasy/komunikaty wyglądają na pomyłkę,
    INFO  — jak mapa zachowa się pusta i z graczami, pomiary czasu startu.
"""
import re
from collections import namedtuple

from .jezyk import t
from .kolejka import (Kolejka, Mapa, jest_komunikatem, przewidywany_czas_startu,
                      wzorce_pusto_z_konfiguracji)
from .server_tab import duplicate_enabled_ports, validate_rcon_line_values

# Poziomy to identyfikatory; do wyświetlania służy nazwa_poziomu().
BLAD = "blad"
UWAGA = "uwaga"
INFO = "info"


def nazwa_poziomu(poziom):
    return {BLAD: t("BŁĄD", "ERROR"), UWAGA: t("UWAGA", "WARNING"), INFO: "INFO"}.get(poziom, poziom)


def nazwa_trybu(tryb):
    """Tryb mapy w podglądzie fali: "pusta" / "gracze" (identyfikatory)."""
    return {"pusta": t("pusta", "empty"), "gracze": t("gracze", "players")}.get(tryb, tryb)


def nazwa_zrodla(zrodlo):
    """Skąd podgląd wziął czas startu mapy (identyfikatory z podglad_fali)."""
    return {"zmierzony": t("zmierzony", "measured"), "zalozony": t("założony", "assumed"),
            "innej_mapy": t("innej mapy", "from another map")}.get(zrodlo, zrodlo)

Ustalenie = namedtuple("Ustalenie", "poziom tekst")
# wiersze: lista słowników {"time", "cmd", "on"} — dokładnie jak tab.rows.
MapaWe = namedtuple("MapaWe", "nazwa wlaczona host port wiersze")

# Komunikat „za 30 sekund” wysłany 32 s przed DoExit to nie pomyłka: RCON ma
# prawo do kilku sekund opóźnienia (ponawianie 3 × 2 s), a ludzie zaokrąglają.
TOLERANCJA_S = 10
TOLERANCJA_WZGL = 0.10

# Te same granice co ostrzeżenia w procedurze (asaonly/procedura.py): krótsze
# czekanie bez komunikatu jest nieszkodliwe, dłuższe to zwykle pomyłka.
PRZESUNIECIE_STAREGO_ZEGARA_S = 60
DLUGIE_CZEKANIE_S = 60

_JEDNOSTKI = (
    (3600, r"(?:h|hrs?|hours?|godz\.?|godzin[aęy]?)"),
    (60, r"(?:min(?:ut(?:[aęy]|es?)?|s)?\.?)"),
    (1, r"(?:s(?:ek(?:\.|und[aęy]?)?|ec(?:ond)?s?)?\.?)"),
)
_LITERA = r"a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
_CZLON = re.compile(
    r"(?<![\d:.,])(\d+(?:[.,]\d+)?)\s*(" + "|".join(j for _, j in _JEDNOSTKI) +
    r")(?![" + _LITERA + r"])", re.I)
_LACZNIK = re.compile(r"\s*(?:,|\bi\b|\band\b|\boraz\b)?\s*", re.I)
# Zapowiedzi bez liczby („Restart za minutę!”).
_BEZ_LICZBY = (
    (re.compile(r"\bpół\s+godziny\b|\bhalf\s+an\s+hour\b", re.I), 1800),
    (re.compile(r"\bpół\s+minuty\b|\bhalf\s+a\s+minute\b", re.I), 30),
    (re.compile(r"\bgodzin[ęa]\b|\b(?:an|one)\s+hour\b", re.I), 3600),
    (re.compile(r"\bminut[ęa]\b|\b(?:a|one)\s+minute\b", re.I), 60),
    (re.compile(r"\bsekund[ęa]\b|\b(?:a|one)\s+second\b", re.I), 1),
)


def _mnoznik(jednostka):
    for mnoznik, wzorzec in _JEDNOSTKI:
        if re.fullmatch(wzorzec, jednostka, re.I):
            return mnoznik
    return None


def czas_z_komunikatu(tekst):
    """Czas zapowiedziany w treści komunikatu (sekundy) albo None.

    Rozpoznaje liczbę z jednostką: s/sek/sekund…/sec/seconds, min/minut…/minutes,
    h/godz/godzin…/hours. Kolejne człony tuż po sobie się sumują („1 min 30 s”
    = 90). Liczy się PIERWSZE takie wyrażenie w tekście; liczby bez jednostki
    i godziny zegarowe (12:30) są pomijane. Bez liczby: „minutę”, „godzinę”,
    „sekundę”, „pół minuty”, „pół godziny” (i angielskie odpowiedniki).
    """
    tekst = str(tekst or "")
    m = _CZLON.search(tekst)
    if not m:
        trafienia = [(w.search(tekst), sek) for w, sek in _BEZ_LICZBY]
        trafienia = [(x.start(), sek) for x, sek in trafienia if x]
        return min(trafienia)[1] if trafienia else None
    suma = 0.0
    while m:
        liczba = float(m.group(1).replace(",", "."))
        mnoznik = _mnoznik(m.group(2))
        if mnoznik is None:
            break
        suma += liczba * mnoznik
        pozycja = _LACZNIK.match(tekst, m.end()).end()
        m = _CZLON.match(tekst, pozycja)
    return int(round(suma))


def odmiana(n, jeden, kilka, wiele):
    """„1 błąd”, „3 błędy”, „5 błędów”, „22 błędy”, „12 błędów”."""
    n = int(n)
    if n == 1:
        return "%d %s" % (n, jeden)
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "%d %s" % (n, kilka)
    return "%d %s" % (n, wiele)


def liczba(n, formy):
    """Liczba z rzeczownikiem w języku interfejsu.

    formy = t("błąd|błędy|błędów", "error|errors"): trzy formy = polska odmiana,
    dwie = angielska (1 / wiele).
    """
    czesci = str(formy).split("|")
    if len(czesci) == 3:
        return odmiana(n, *czesci)
    jeden, wiele = (czesci + czesci)[:2]
    return "%d %s" % (int(n), jeden if int(n) == 1 else wiele)


def bledy_i_uwagi(bledy, uwagi):
    return "%s, %s" % (liczba(bledy, t("błąd|błędy|błędów", "error|errors")),
                       liczba(uwagi, t("uwaga|uwagi|uwag", "warning|warnings")))


def fmt_czas(sekundy):
    """0:05, 3:25, 1:02:03."""
    s = int(round(float(sekundy)))
    znak = "-" if s < 0 else ""
    s = abs(s)
    if s >= 3600:
        return "%s%d:%02d:%02d" % (znak, s // 3600, s % 3600 // 60, s % 60)
    return "%s%d:%02d" % (znak, s // 60, s % 60)


def _opis_s(sekundy):
    return "%d s (%s)" % (sekundy, fmt_czas(sekundy)) if sekundy >= 60 else "%d s" % sekundy


def _port_poprawny(wartosc):
    # Ta sama reguła co Wtyczka._valid_port w PLUGINY/86_rcon_admin.py.
    wartosc = str(wartosc or "").strip()
    return wartosc.isdecimal() and 1 <= int(wartosc) <= 65535


def _pierwszy_zly_wiersz(aktywne):
    """(numer wiersza od 1, opis) dla pierwszego wiersza, który odrzuca walidacja."""
    for indeks, wiersz in aktywne:
        czas = str(wiersz.get("time", "") or "").strip()
        cmd = str(wiersz.get("cmd", "") or "").strip()
        if not czas and not cmd:
            continue
        if not czas:
            return indeks + 1, t("komenda „%s” bez czasu", "command \"%s\" without a time") % cmd
        if not czas.isdecimal():
            return indeks + 1, t("czas „%s” nie jest liczbą sekund",
                                 "time \"%s\" is not a number of seconds") % czas
        if not cmd:
            return indeks + 1, t("czas %s s bez komendy", "time %s s without a command") % czas
    return None, t("nieprawidłowy wiersz", "invalid row")


def _historie(konfiguracja):
    hist = (konfiguracja or {}).get("czasy_startu")
    return hist if isinstance(hist, dict) else {}


def sprawdz_mape(m, kolizje_portow=None, konfiguracja=None):
    """Ustalenia dla jednej mapy i jej zweryfikowane linie (albo None).

    kolizje_portow: {nazwa mapy: (port, [inne mapy])} z sprawdz_klaster.
    """
    u = []
    if not m.wlaczona:
        u.append(Ustalenie(INFO, t("Mapa wyłączona — procedura jej nie dotyczy.",
                                   "Map turned off — the procedure does not apply to it.")))
        return u, None

    if not str(m.host or "").strip():
        u.append(Ustalenie(BLAD, t("Brak adresu RCON — procedura pominie tę mapę.",
                                   "No RCON address — the procedure will skip this map.")))
    if not _port_poprawny(m.port):
        u.append(Ustalenie(BLAD, t("Nieprawidłowy port RCON „%s” — procedura pominie tę mapę.",
                                   "Invalid RCON port \"%s\" — the procedure will skip this map.")
                           % str(m.port or "").strip()))
    kolizja = (kolizje_portow or {}).get(m.nazwa)
    if kolizja:
        port, inne = kolizja
        u.append(Ustalenie(BLAD, t("Port RCON %s ma też: %s — procedura pominie wszystkie te mapy "
                                   "(nie wiadomo, który serwer odpowiada).",
                                   "RCON port %s is also used by: %s — the procedure will skip all "
                                   "these maps (it is unclear which server answers).")
                           % (port, ", ".join(inne))))

    wiersze = list(m.wiersze or ())
    aktywne = [(i, w) for i, w in enumerate(wiersze) if bool(w.get("on", True))]
    puste = [i + 1 for i, w in aktywne
             if not str(w.get("time", "") or "").strip() and not str(w.get("cmd", "") or "").strip()]
    if puste:
        u.append(Ustalenie(INFO, t("Zaznaczone puste wiersze (nr %s) — pomijane.",
                                   "Ticked empty rows (no. %s) — skipped.")
                           % ", ".join(str(n) for n in puste)))

    linie, blad = validate_rcon_line_values(
        [(w.get("time", ""), w.get("cmd", "")) for _, w in aktywne])
    if blad:
        nr, opis = _pierwszy_zly_wiersz(aktywne)
        u.append(Ustalenie(BLAD, t("Wiersz %s: %s — procedura odrzuci cały harmonogram "
                                   "i pominie tę mapę.",
                                   "Row %s: %s — the procedure will reject the whole schedule "
                                   "and skip this map.") % (nr if nr else "?", opis)))
        return u, None
    if not linie:
        u.append(Ustalenie(BLAD, t("Brak aktywnych linii RCON — procedura pominie tę mapę.",
                                   "No active RCON lines — the procedure will skip this map.")))
        return u, None
    mapa = Mapa(m.nazwa, linie)
    if mapa.cmd_wyjscia is None:
        u.append(Ustalenie(BLAD, t("Brak DoExit w harmonogramie — procedura pominie tę mapę.",
                                   "No DoExit in the schedule — the procedure will skip this map.")))
        return u, None
    if any(x.poziom == BLAD for x in u):
        return u, None

    t_wyjscia = int(mapa.t_wyjscia_ludzie or 0)
    if mapa.po:
        u.append(Ustalenie(UWAGA, t("Linie po DoExit nie zostaną wysłane (serwera już nie ma): %s.",
                                    "Lines after DoExit will not be sent (the server is gone): %s.")
                           % "; ".join("%d s %s" % (ts, c) for ts, c in mapa.po)))
    komunikaty = [(ts, c) for ts, c in mapa.przed if jest_komunikatem(c)]
    if t_wyjscia >= DLUGIE_CZEKANIE_S and not komunikaty:
        u.append(Ustalenie(UWAGA, t("Czeka %s przed DoExit, ale nie ma komunikatu dla graczy — "
                                    "to czekanie nic im nie daje. Czasy są lokalne dla mapy; "
                                    "odstępy między mapami robi kolejka.",
                                    "Waits %s before DoExit, but there is no message for players — "
                                    "the wait gives them nothing. Times are local to the map; "
                                    "the queue handles the spacing between maps.") % _opis_s(t_wyjscia)))
    elif t_wyjscia and not komunikaty:
        u.append(Ustalenie(INFO, t("Czeka %s przed DoExit bez komunikatu — krótko, nieszkodliwe.",
                                   "Waits %s before DoExit without a message — short, harmless.")
                           % _opis_s(t_wyjscia)))
    elif mapa.przed and int(mapa.przed[0][0]) >= PRZESUNIECIE_STAREGO_ZEGARA_S:
        u.append(Ustalenie(UWAGA, t("Pierwsza linia dopiero po %s. Jeśli to przesunięcie ze starego "
                                    "wspólnego zegara (≤ V3.80), odejmij je od wszystkich linii tej mapy.",
                                    "The first line comes only after %s. If this is an offset from the "
                                    "old shared clock (≤ V3.80), subtract it from all lines of this map.")
                           % _opis_s(int(mapa.przed[0][0]))))
    for ts, c in komunikaty:
        zostaje = t_wyjscia - int(ts)
        if zostaje == 0:
            u.append(Ustalenie(UWAGA, t("Komunikat w tej samej sekundzie co DoExit (%d s) — gracze "
                                        "go nie zdążą przeczytać: „%s”.",
                                        "Message in the same second as DoExit (%d s) — players "
                                        "will not have time to read it: \"%s\".") % (ts, c)))
            continue
        zapowiedz = czas_z_komunikatu(c)
        if zapowiedz is None:
            continue
        if abs(zapowiedz - zostaje) > max(TOLERANCJA_S, TOLERANCJA_WZGL * zostaje):
            u.append(Ustalenie(UWAGA, t("Komunikat na %d s zapowiada %s, a DoExit jest %s później: „%s”.",
                                        "The message at %d s announces %s, but DoExit comes %s later: \"%s\".")
                               % (ts, fmt_czas(zapowiedz), fmt_czas(zostaje), c)))

    pozostale = [c for _, c in mapa.przed if not jest_komunikatem(c)]
    u.append(Ustalenie(INFO, t("Z graczami: %s, DoExit po %s.", "With players: %s, DoExit after %s.")
                       % (liczba(len(komunikaty), t("komunikat|komunikaty|komunikatów",
                                                    "message|messages")),
                          fmt_czas(t_wyjscia))))
    u.append(Ustalenie(INFO, t("Pusta: od razu, bez komunikatów%s.",
                               "Empty: at once, without messages%s.")
                       % ((t(" (zostają: %s)", " (kept: %s)") % ", ".join(pozostale))
                          if pozostale else "")))

    hist = _historie(konfiguracja)
    wlasny = przewidywany_czas_startu(hist.get(m.nazwa))
    if wlasny:
        u.append(Ustalenie(INFO, t("Zmierzony czas startu (DoExit → GOTOWY): %s — najdłuższy "
                                   "z ostatnich pomiarów.",
                                   "Measured start time (DoExit → READY): %s — the longest "
                                   "of the recent measurements.") % fmt_czas(wlasny)))
    else:
        inne = [przewidywany_czas_startu(v) for n, v in hist.items() if n != m.nazwa]
        inne = [x for x in inne if x]
        if inne:
            u.append(Ustalenie(INFO, t("Brak własnego pomiaru czasu startu — kolejka przyjmie "
                                       "najdłuższy pomiar innej mapy: %s.",
                                       "No start-time measurement of its own — the queue will use "
                                       "the longest measurement from another map: %s.") % fmt_czas(max(inne))))
        else:
            u.append(Ustalenie(INFO, t("Brak pomiarów czasu startu — pierwsza fala pójdzie po kolei, "
                                       "potem program już wie.",
                                       "No start-time measurements — the first wave goes one by one; "
                                       "after that the program knows.")))
    return u, list(linie)


def sprawdz_klaster(mapy, konfiguracja=None):
    """Zwraca (ogólne ustalenia, {nazwa: (ustalenia, linie albo None)})."""
    konfiguracja = konfiguracja or {}
    kolizje = duplicate_enabled_ports([(m.nazwa, m.wlaczona, m.port) for m in mapy])
    kolizje_portow = {}
    for port, nazwy in kolizje.items():
        for n in nazwy:
            kolizje_portow[n] = (port, [x for x in nazwy if x != n])
    wynik = {}
    for m in mapy:
        wynik[m.nazwa] = sprawdz_mape(m, kolizje_portow, konfiguracja)

    ogolne = []
    if not bool(konfiguracja.get("pusty_serwer_od_razu", True)):
        ogolne.append(Ustalenie(INFO, t("Wykrywanie pustych map jest wyłączone („Pusta mapa: restart "
                                        "od razu”) — każda mapa dostanie pełny harmonogram.",
                                        "Empty-map detection is off (\"Empty map: restart at once\") "
                                        "— every map gets its full schedule.")))
    elif not wzorce_pusto_z_konfiguracji(konfiguracja.get("listplayers_pusto")):
        ogolne.append(Ustalenie(UWAGA, t("Brak poprawnych wzorców pustego serwera (listplayers_pusto) — "
                                         "pusta mapa zawsze dostanie pełny harmonogram.",
                                         "No valid empty-server patterns (listplayers_pusto) — "
                                         "an empty map always gets its full schedule.")))
    if any(m.wlaczona for m in mapy) and not any(linie for _, linie in wynik.values()):
        ogolne.append(Ustalenie(UWAGA, t("Żadna mapa nie przejdzie procedury — update wejdzie dopiero "
                                         "przy najbliższym starcie serwerów z innego powodu.",
                                         "No map will go through the procedure — the update will land "
                                         "only when the servers start for another reason.")))
    return ogolne, wynik


def licz(ogolne, wynik, poziom):
    return (sum(1 for x in ogolne if x.poziom == poziom) +
            sum(1 for u, _ in wynik.values() for x in u if x.poziom == poziom))


# ---------------------------------------------------------------------------
# Podgląd fali — prawdziwy planista (Kolejka) na symulowanym czasie
# ---------------------------------------------------------------------------
WierszFali = namedtuple("WierszFali", "nazwa tryb ogloszenia_od doexit gotowa czas_startu zrodlo")


def podglad_fali(mapy, puste=(), czasy_startu=None, czas_zalozony=None, sondy=True,
                 limit_s=7 * 24 * 3600):
    """Przewidywany przebieg fali restartów. Zwraca (wiersze, braki).

    mapy:          [(nazwa, linie)] — zweryfikowane linie, kolejność tabów,
    puste:         nazwy map, które w tym scenariuszu są puste,
    czasy_startu:  historia z konfiguracji {nazwa: [sekundy, …]}; planista dostaje
                   DOKŁADNIE to, co dostanie w programie (bez pomiarów = po kolei),
    czas_zalozony: sekundy startu dla map bez żadnego pomiaru — tylko do symulacji
                   „świata”, planista go nie widzi,
    sondy:         jak ustawienie „Pusta mapa: restart od razu” (False = wszyscy
                   z pełnym harmonogramem).
    braki:         mapy, dla których nie ma czym zasymulować startu (brak pomiarów
                   i brak czasu założonego) — wtedy wiersze są puste.
    """
    przewid = {}
    for nazwa, hist in (czasy_startu or {}).items():
        v = przewidywany_czas_startu(hist)
        if v:
            przewid[nazwa] = v
    najdluzszy = max(przewid.values()) if przewid else None
    swiat, zrodlo, braki = {}, {}, []
    for nazwa, _ in mapy:
        if nazwa in przewid:
            swiat[nazwa], zrodlo[nazwa] = przewid[nazwa], "zmierzony"
        elif czas_zalozony:
            swiat[nazwa], zrodlo[nazwa] = float(czas_zalozony), "zalozony"
        elif najdluzszy:
            swiat[nazwa], zrodlo[nazwa] = najdluzszy, "innej_mapy"
        else:
            braki.append(nazwa)
    if braki or not mapy:
        return [], braki

    puste = set(puste or ()) if sondy else set()
    q = Kolejka([Mapa(n, linie) for n, linie in mapy], czasy_startu=przewid, sondy=sondy)
    teraz = 0.0
    start, wyjscie, gotowa, w_starcie = {}, {}, {}, {}
    while not q.gotowe():
        if teraz > limit_s:
            raise RuntimeError(t("podgląd fali przekroczył %d s symulacji",
                                 "the wave preview exceeded %d s of simulation") % limit_s)
        for nazwa, koniec in list(w_starcie.items()):
            if teraz >= koniec:
                del w_starcie[nazwa]
                q.zakoncz(nazwa, True, "", teraz)
                gotowa[nazwa] = teraz
        for _ in range(50):
            akcje = q.tick(teraz)
            if not akcje:
                break
            for a in akcje:
                if a[0] == "sonda":
                    pusta = a[1] in puste
                    q.wynik_sondy(a[1], "pusto" if pusta else "gracze", 0 if pusta else 1, teraz)
                elif a[0] == "wyslij":
                    q.wynik_komendy(a[1], a[2], None, teraz)
                elif a[0] == "doexit":
                    q.wynik_doexit(a[1], None, teraz)
                    wyjscie[a[1]] = teraz
                    w_starcie[a[1]] = teraz + swiat[a[1]]
        for m in q.mapy:
            if m.start_odliczania is not None and m.nazwa not in start:
                start[m.nazwa] = m.start_odliczania
        # Sekunda po sekundzie, jak tik programu (planista jest tani).
        teraz += 1.0
    tryby = {m.nazwa: m.tryb for m in q.mapy}
    wiersze = []
    for nazwa in sorted(wyjscie, key=lambda n: (wyjscie[n], n)):
        tryb = "pusta" if tryby.get(nazwa) == "pusto" else "gracze"
        od = start.get(nazwa) if tryb == "gracze" else None
        wiersze.append(WierszFali(nazwa, tryb, od, wyjscie[nazwa], gotowa.get(nazwa),
                                  swiat[nazwa], zrodlo[nazwa]))
    return wiersze, []
