# -*- coding: utf-8 -*-
"""Inteligentna kolejka procedury RCON (V3.81) — czysta logika, bez Tk i bez sieci.

AKSJOMAT PROGRAMU (nie łamać przy zmianach):
    Każdy update moda i tak wejdzie przy najbliższym starcie serwera, bo serwer
    sam podnosi mody przy KAŻDYM uruchomieniu. Refresher jest akceleratorem,
    nie warunkiem. Dlatego:
      * żadna pojedyncza mapa nie może zatrzymać reszty kolejki,
      * niepowodzenie mapy = wpis w dzienniku i następna mapa,
      * nigdy nie czekamy na kliknięcie człowieka na ścieżce automatycznej.

ZASADY KOLEJKI:
    1. W danej chwili STARTUJE najwyżej jedna mapa (DoExit → nowy start →
       GOTOWY). To jest jedyne wąskie gardło — dysk.
    2. Ogłoszenia dysku nie obciążają, więc mogą trwać równolegle na wielu
       mapach.
    3. Mapa z POTWIERDZONYM brakiem graczy: bez komunikatów i bez czekania.
       Pozostałe komendy z harmonogramu (np. SaveWorld) zostają, w tej samej
       kolejności.
    4. Niepewność co do graczy = gracze są (pełny harmonogram człowieka).
       Pomyłka w stronę „są” kosztuje minuty, w stronę „pusto” — wyrzucenie
       kogoś z gry bez ostrzeżenia.
    5. Ogłoszenia mapy startują „na styk”: tak, żeby jej zegar skończył się
       wtedy, gdy dysk się zwolni — według czasów startu zmierzonych na TEJ
       instalacji. Mapa bez własnego pomiaru bierze najdłuższy pomiar innej
       mapy (ten sam dysk). Bez żadnego pomiaru nie planujemy do przodu:
       następna mapa rusza, gdy dysk faktycznie się zwolni (po kolei).
       Przewidywanie wpływa tylko na moment ogłoszeń — zasady 1 nie łamie
       nigdy (DoExit czeka na wolny dysk).
    6. Mapy potwierdzone jako puste idą w kolejce przed pozostałymi.

Moduł nie zna Tk, RCON ani plików. Aplikacja wykonuje zwrócone akcje i odsyła
wyniki metodami wynik_*().
"""
import re

from .jezyk import t

# Komendy, które są wyłącznie komunikatami dla graczy. Na pustym serwerze
# pomijamy tylko je — wszystkie inne komendy człowieka zostają.
KOMUNIKATY = ("serverchat", "serverchatto", "serverchattoplayer", "broadcast")

# Tekst, którym serwer odpowiada na ListPlayers, gdy nikogo nie ma.
# UWAGA: taką odpowiedź daje ARK: Survival Evolved; dla Ascended NIE zostało to
# potwierdzone na prawdziwym serwerze. Jeśli ASA odpowie inaczej, odpowiedź
# zostanie uznana za „nieznaną” (= gracze są) — funkcja po prostu nie skróci
# procedury. Surowa odpowiedź trafia do dziennika, żeby wzorzec dało się
# potwierdzić albo poprawić w konfiguracji (klucz "listplayers_pusto").
WZORCE_PUSTO_DOMYSLNE = ("No Players Connected",)

# Najkrótszy wzorzec pustego serwera, jaki przyjmujemy z konfiguracji. Krótszy
# (np. jedna litera wpisana przez pomyłkę) pasowałby do prawie każdej odpowiedzi
# i wyrzucałby graczy bez ostrzeżenia.
MIN_DLUGOSC_WZORCA = 4


def wzorce_pusto_z_konfiguracji(wartosc):
    """Wzorce pustego serwera z konfiguracji (klucz "listplayers_pusto").

    Brak klucza albo zły typ = wzorce domyślne. Pojedynczy tekst = lista z jednym
    wzorcem. Wzorce krótsze niż MIN_DLUGOSC_WZORCA są odrzucane; jeśli nic nie
    zostanie — pusta lista, czyli wykrywanie pustych map po prostu nie działa
    (pełne harmonogramy), co jest bezpieczne.
    """
    if isinstance(wartosc, str):
        wartosc = [wartosc]
    if not isinstance(wartosc, (list, tuple)):
        return list(WZORCE_PUSTO_DOMYSLNE)
    return [x.strip() for x in wartosc
            if isinstance(x, str) and len(x.strip()) >= MIN_DLUGOSC_WZORCA]


# Linia gracza w odpowiedzi ListPlayers: "0. Nick, identyfikator".
_LINIA_GRACZA = re.compile(r"^\s*\d+\.\s*\S")

SONDA_TIMEOUT_S = 20.0
# Jednoznaczna odpowiedź ListPlayers młodsza niż tyle sekund nie jest powtarzana
# przed startem ogłoszeń ani przed DoExit (mniej ruchu RCON, ta sama pewność).
SWIEZOSC_SONDY_S = 30.0
HISTORIA_STARTOW = 5
NIESKONCZONOSC = float("inf")

# Stany mapy w kolejce.
SONDA = "sonda"            # czeka na odpowiedź ListPlayers
CZEKA = "czeka"            # w kolejce, ogłoszenia jeszcze nie ruszyły
OGLASZA = "oglasza"        # lokalny zegar mapy biegnie, lecą komendy przed DoExit
GOTOWA = "gotowa"          # zegar skończony, czeka na wolny dysk
WYJSCIE = "wyjscie"        # DoExit wysłany, czekamy na wynik RCON
START = "start"            # czekamy na nowy start i GOTOWY
ZROBIONA = "zrobiona"
NIEUDANA = "nieudana"
POMINIETA = "pominieta"

KONCOWE = (ZROBIONA, NIEUDANA, POMINIETA)
ZAJMUJE_DYSK = (WYJSCIE, START)


def jest_doexit(cmd):
    parts = str(cmd or "").strip().split()
    return bool(parts) and parts[0].lower() == "doexit"


def jest_komunikatem(cmd):
    parts = str(cmd or "").strip().split()
    return bool(parts) and parts[0].lower() in KOMUNIKATY


def parsuj_listplayers(tekst, wzorce_pusto=WZORCE_PUSTO_DOMYSLNE):
    """Zinterpretuj odpowiedź ListPlayers.

    Zwraca (stan, liczba):
      ("gracze", n)     — rozpoznano n linii graczy,
      ("pusto", 0)      — odpowiedź pasuje do wzorca pustego serwera,
      ("nieznane", None) — wszystko inne (pusta odpowiedź, obcy format).
    Stan "nieznane" aplikacja traktuje jak "gracze".
    """
    t = str(tekst or "").strip()
    if not t:
        return "nieznane", None
    gracze = [linia for linia in t.splitlines() if _LINIA_GRACZA.match(linia)]
    if gracze:
        return "gracze", len(gracze)
    niski = t.lower()
    for wzorzec in wzorce_pusto or ():
        w = str(wzorzec or "").strip().lower()
        if w and w in niski:
            return "pusto", 0
    return "nieznane", None


def _jako_lista(historia):
    """Historia z konfiguracji: lista liczb; pojedyncza liczba też przejdzie
    (admin może ją wpisać ręcznie), wszystko inne = brak historii."""
    if isinstance(historia, bool):
        return []
    if isinstance(historia, (int, float)):
        return [historia]
    if isinstance(historia, (list, tuple)):
        return list(historia)
    return []


def przewidywany_czas_startu(historia):
    """Najdłuższy z ostatnich zmierzonych startów mapy (sekundy) albo None."""
    wartosci = []
    for x in _jako_lista(historia)[-HISTORIA_STARTOW:]:
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if v > 0:
            wartosci.append(v)
    return max(wartosci) if wartosci else None


def dopisz_czas_startu(historia, sekundy):
    """Zwróć nową historię z dopisanym pomiarem (ostatnie HISTORIA_STARTOW)."""
    nowa = [float(x) for x in _jako_lista(historia)
            if isinstance(x, (int, float)) and not isinstance(x, bool)]
    nowa.append(round(float(sekundy), 1))
    return nowa[-HISTORIA_STARTOW:]


def podziel_harmonogram(linie):
    """Rozdziel zweryfikowane linie [(t, cmd)] mapy.

    Zwraca (przed, t_wyjscia, cmd_wyjscia, po):
      przed       — linie przed pierwszym DoExit (po czasie, stabilnie),
      t_wyjscia   — czas lokalny pierwszego DoExit albo None,
      cmd_wyjscia — dokładna komenda DoExit,
      po          — linie po DoExit (serwera już nie ma — nie będą wysłane).
    """
    posortowane = [x for _, x in sorted(enumerate(linie), key=lambda p: (int(p[1][0]), p[0]))]
    for i, (ts, cmd) in enumerate(posortowane):
        if jest_doexit(cmd):
            return (list(posortowane[:i]), int(ts), str(cmd), list(posortowane[i + 1:]))
    return list(posortowane), None, None, []


class Mapa(object):
    """Jedna mapa w kolejce: jej harmonogram, tryb i stan."""

    def __init__(self, nazwa, linie):
        self.nazwa = str(nazwa)
        self.przed, self.t_wyjscia_ludzie, self.cmd_wyjscia, self.po = podziel_harmonogram(linie)
        self.tryb = "?"                  # "?" | "pusto" | "gracze"
        self.stan = CZEKA
        self.powod = ""
        self.harmonogram = []            # [{"t", "cmd", "stan"}] dla bieżącego trybu
        self.t_wyjscia = 0
        self.start_odliczania = None     # czas bezwzględny startu lokalnego zegara
        self.wyjscie_t = None            # czas bezwzględny wysłania DoExit
        self.sonda_od = None
        self.sonda_cel = None            # "wstepna" | "przed_startem" | "przed_wyjsciem"
        self.sonda_swieza = False        # tryb "pusto" potwierdzony tuż przed wyjściem
        self.gracze = None               # liczba graczy z ostatniej sondy
        self.sonda_t = None              # czas ostatniej JEDNOZNACZNEJ odpowiedzi
        if self.cmd_wyjscia is None:
            self.stan = POMINIETA
            self.powod = t("brak DoExit w harmonogramie", "no DoExit in the schedule")

    # -- tryb i harmonogram -------------------------------------------------
    def ustaw_tryb(self, tryb):
        self.tryb = "pusto" if tryb == "pusto" else "gracze"
        if self.tryb == "pusto":
            self.harmonogram = [{"t": 0, "cmd": cmd, "stan": "czeka"}
                                for _, cmd in self.przed if not jest_komunikatem(cmd)]
            self.t_wyjscia = 0
        else:
            self.harmonogram = [{"t": int(t), "cmd": cmd, "stan": "czeka"}
                                for t, cmd in self.przed]
            self.t_wyjscia = int(self.t_wyjscia_ludzie or 0)

    def dlugosc_odliczania(self):
        if self.tryb == "pusto":
            return 0.0
        return float(self.t_wyjscia_ludzie or 0)

    def koniec_odliczania(self):
        if self.start_odliczania is None:
            return None
        return self.start_odliczania + float(self.t_wyjscia)

    def koncowa(self):
        return self.stan in KONCOWE


class Kolejka(object):
    """Planista kolejki procedury. Aplikacja woła tick(now) i wykonuje akcje.

    Akcje zwracane przez tick():
      ("sonda", nazwa)               — wyślij ListPlayers, potem wynik_sondy()
      ("wyslij", nazwa, indeks, cmd) — wyślij komendę, potem wynik_komendy()
      ("doexit", nazwa, cmd)         — wyślij DoExit, potem wynik_doexit()
    """

    def __init__(self, mapy, czasy_startu=None, sondy=True):
        self.mapy = list(mapy)
        self._po_nazwie = {m.nazwa: m for m in self.mapy}
        self.czasy_startu = dict(czasy_startu or {})
        self.sondy = bool(sondy)
        self._kolejnosc_ustalona = False
        for m in self.mapy:
            if m.koncowa():
                continue
            if self.sondy:
                m.stan = SONDA
                m.sonda_cel = "wstepna"
            else:
                m.ustaw_tryb("gracze")
                m.stan = CZEKA
        if not self.sondy:
            self._kolejnosc_ustalona = True

    # -- pomocnicze ---------------------------------------------------------
    def mapa(self, nazwa):
        return self._po_nazwie.get(str(nazwa))

    def zajmuje_dysk(self):
        """Mapa, która ma teraz prawo do startu (także w trakcie ostatniej sondy)."""
        return next((m for m in self.mapy if m.stan in ZAJMUJE_DYSK or
                     (m.stan == SONDA and m.sonda_cel == "przed_wyjsciem")), None)

    def gotowe(self):
        return all(m.koncowa() for m in self.mapy)

    def aktywne_nazwy(self):
        return [m.nazwa for m in self.mapy if not m.koncowa()]

    def _ustal_kolejnosc(self):
        """Puste mapy na początek; w grupach zostaje kolejność tabów."""
        puste = [m for m in self.mapy if m.tryb == "pusto"]
        reszta = [m for m in self.mapy if m.tryb != "pusto"]
        self.mapy = puste + reszta
        self._kolejnosc_ustalona = True

    @staticmethod
    def _sekundy(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None
        return v if v > 0 else None

    def _wlasny_pomiar(self, nazwa):
        return self._sekundy(self.czasy_startu.get(nazwa))

    def _przewidywanie(self, nazwa):
        """Przewidywany czas startu mapy (s) albo None.

        Własny pomiar mapy; bez niego — najdłuższy pomiar innej mapy tej
        instalacji. Brak jakiegokolwiek pomiaru = None (planowanie po kolei).
        """
        v = self._wlasny_pomiar(nazwa)
        if v is not None:
            return v
        inne = [self._sekundy(x) for k, x in self.czasy_startu.items() if k != nazwa]
        inne = [x for x in inne if x is not None]
        return max(inne) if inne else None

    # -- planowanie „na styk” -------------------------------------------------
    def plan(self, now):
        """Zwróć {nazwa: planowany start ogłoszeń} dla map w stanie CZEKA.

        Symulujemy przydział dysku od teraz:
          * mapa, która właśnie startuje, trzyma dysk przez swój czas startu,
          * mapy już odliczające mają „zobowiązanie” wobec graczy — ich DoExit
            nie może się opóźnić przez nikogo, kto zacząłby później,
          * mapa czekająca może wejść w lukę przed zobowiązaniem tylko wtedy,
            gdy jej cały start zmieści się przed nim,
          * czekające idą w kolejności kolejki (puste pierwsze).
        Brak jakiegokolwiek pomiaru = nie planujemy dalej (NIESKONCZONOSC), czyli
        następna mapa ruszy dopiero, gdy dysk faktycznie się zwolni.
        """
        wolny = now
        zajeta = self.zajmuje_dysk()
        if zajeta is not None:
            pred = self._przewidywanie(zajeta.nazwa)
            poczatek = zajeta.wyjscie_t if zajeta.wyjscie_t is not None else now
            wolny = NIESKONCZONOSC if pred is None else max(now, poczatek + pred)

        def koniec(m):
            # Mapa w sondzie „przed startem” zaraz zacznie odliczać od teraz.
            if m.stan == SONDA:
                return now + m.dlugosc_odliczania()
            k = m.koniec_odliczania()
            return k if k is not None else now

        zobowiazania = sorted(
            [m for m in self.mapy if m is not zajeta and (
                m.stan in (OGLASZA, GOTOWA) or
                (m.stan == SONDA and m.sonda_cel == "przed_startem"))],
            key=koniec)
        czekajace = [m for m in self.mapy if m.stan == CZEKA]
        plan = {m.nazwa: NIESKONCZONOSC for m in czekajace}
        while (zobowiazania or czekajace) and wolny != NIESKONCZONOSC:
            z = zobowiazania[0] if zobowiazania else None
            w = czekajace[0] if czekajace else None
            start_z = max(wolny, koniec(z)) if z is not None else NIESKONCZONOSC
            if w is not None:
                dl = w.dlugosc_odliczania()
                start_w = max(wolny, now + dl)
                pred_w = self._przewidywanie(w.nazwa)
                miesci_sie = (z is None or
                              (pred_w is not None and start_w + pred_w <= start_z))
                if start_w <= start_z and miesci_sie:
                    plan[w.nazwa] = start_w - dl
                    wolny = NIESKONCZONOSC if pred_w is None else start_w + pred_w
                    czekajace.pop(0)
                    continue
            pred_z = self._przewidywanie(z.nazwa)
            wolny = NIESKONCZONOSC if pred_z is None else start_z + pred_z
            zobowiazania.pop(0)
        return plan

    # -- główny krok --------------------------------------------------------
    def tick(self, now):
        akcje = []
        # Sondy bez odpowiedzi w terminie = niepewność = gracze są.
        for m in self.mapy:
            if m.stan == SONDA and m.sonda_od is not None and now - m.sonda_od > SONDA_TIMEOUT_S:
                self.wynik_sondy(m.nazwa, "nieznane", None, now)
        # Wstępne sondy: wyślij te, które jeszcze nie wyszły.
        for m in self.mapy:
            if m.stan == SONDA and m.sonda_od is None:
                m.sonda_od = now
                akcje.append(("sonda", m.nazwa))
        if not self._kolejnosc_ustalona:
            if any(m.stan == SONDA and m.sonda_cel == "wstepna" for m in self.mapy):
                return akcje
            self._ustal_kolejnosc()

        # Start ogłoszeń map, których planowany start już minął.
        plan = self.plan(now)
        for m in list(self.mapy):
            if m.stan != CZEKA or plan.get(m.nazwa, NIESKONCZONOSC) > now:
                continue
            if m.tryb == "gracze" and self.sondy and not self._swieza(m, now):
                # Może wszyscy wyszli od wstępnej sondy — sprawdź jeszcze raz.
                m.stan = SONDA
                m.sonda_cel = "przed_startem"
                m.sonda_od = now
                akcje.append(("sonda", m.nazwa))
                continue
            self._rozpocznij_odliczanie(m, now)

        # Komendy odliczających map, których czas lokalny już minął.
        for m in self.mapy:
            if m.stan != OGLASZA:
                continue
            dt = now - m.start_odliczania
            for i, linia in enumerate(m.harmonogram):
                if linia["stan"] == "czeka" and dt >= linia["t"]:
                    linia["stan"] = "wyslana"
                    akcje.append(("wyslij", m.nazwa, i, linia["cmd"]))
            self._moze_gotowa(m, now)

        # Wolny dysk: wybierz mapę, której zegar skończył się najwcześniej.
        if self.zajmuje_dysk() is None:
            gotowe = [m for m in self.mapy if m.stan == GOTOWA]
            if gotowe:
                m = min(gotowe, key=lambda x: (x.koniec_odliczania() or now, self.mapy.index(x)))
                if m.tryb == "pusto" and self.sondy and not m.sonda_swieza \
                        and not self._swieza(m, now):
                    # Ktoś mógł wejść od ostatniej sondy.
                    m.stan = SONDA
                    m.sonda_cel = "przed_wyjsciem"
                    m.sonda_od = now
                    akcje.append(("sonda", m.nazwa))
                else:
                    m.stan = WYJSCIE
                    m.wyjscie_t = now
                    akcje.append(("doexit", m.nazwa, m.cmd_wyjscia))
        return akcje

    @staticmethod
    def _swieza(m, now):
        return m.sonda_t is not None and now - m.sonda_t < SWIEZOSC_SONDY_S

    def _rozpocznij_odliczanie(self, m, now):
        m.stan = OGLASZA
        m.start_odliczania = now
        self._moze_gotowa(m, now)

    def _moze_gotowa(self, m, now):
        if m.stan != OGLASZA:
            return
        if any(linia["stan"] in ("czeka", "wyslana") for linia in m.harmonogram):
            return
        if now - m.start_odliczania >= m.t_wyjscia:
            m.stan = GOTOWA

    # -- wyniki od aplikacji --------------------------------------------------
    def wynik_sondy(self, nazwa, stan, liczba, now, blad=None):
        m = self.mapa(nazwa)
        if m is None or m.stan != SONDA:
            return
        cel = m.sonda_cel
        m.sonda_od = None
        m.sonda_cel = None
        if blad:
            m.stan = NIEUDANA
            m.powod = str(blad)
            return
        m.gracze = liczba
        if stan in ("pusto", "gracze"):
            m.sonda_t = now
        pusto = (stan == "pusto")
        if cel == "wstepna":
            m.ustaw_tryb("pusto" if pusto else "gracze")
            m.stan = CZEKA
        elif cel == "przed_startem":
            m.ustaw_tryb("pusto" if pusto else "gracze")
            m.sonda_swieza = pusto
            self._rozpocznij_odliczanie(m, now)
        elif cel == "przed_wyjsciem":
            if pusto:
                m.sonda_swieza = True
                m.stan = GOTOWA
            else:
                # Ktoś wszedł: pełny harmonogram człowieka od teraz.
                m.ustaw_tryb("gracze")
                m.sonda_swieza = False
                self._rozpocznij_odliczanie(m, now)

    def wynik_komendy(self, nazwa, indeks, blad, now):
        m = self.mapa(nazwa)
        if m is None or m.stan != OGLASZA:
            return
        if 0 <= indeks < len(m.harmonogram):
            m.harmonogram[indeks]["stan"] = "blad" if blad else "ok"
        self._moze_gotowa(m, now)

    def wynik_doexit(self, nazwa, blad, now):
        m = self.mapa(nazwa)
        if m is None or m.stan != WYJSCIE:
            return
        if blad:
            m.stan = NIEUDANA
            m.powod = t("DoExit nie przeszedł: %s", "DoExit failed: %s") % blad
        else:
            m.stan = START

    def zakoncz(self, nazwa, ok, powod, now, wrocila=None):
        """Mapa po DoExit skończyła start: ok=True gdy wersja potwierdzona.

        wrocila=True oznacza, że serwer wstał (nawet jeśli wersji nie
        potwierdzono) — wtedy zwracamy zmierzony czas startu w sekundach.
        Mapa zawsze zwalnia dysk; następna rusza niezależnie od wyniku.
        """
        m = self.mapa(nazwa)
        if m is None or m.stan != START:
            return None
        if wrocila is None:
            wrocila = ok
        czas = (now - m.wyjscie_t) if (wrocila and m.wyjscie_t is not None) else None
        m.stan = ZROBIONA if ok else NIEUDANA
        m.powod = str(powod or "")
        if czas is not None and czas > 0:
            # Tylko WŁASNY pomiar mapy (nie zastępczy z innej mapy).
            self.czasy_startu[m.nazwa] = max(self._wlasny_pomiar(m.nazwa) or 0.0, czas)
        return czas

    def pomin(self, nazwa, powod):
        m = self.mapa(nazwa)
        if m is None or m.koncowa():
            return
        m.stan = POMINIETA
        m.powod = str(powod or "")

    def anuluj(self, powod="anulowano"):
        for m in self.mapy:
            if not m.koncowa():
                m.stan = POMINIETA
                m.powod = powod

    def podsumowanie(self):
        return [(m.nazwa, m.stan, m.tryb, m.powod) for m in self.mapy]
