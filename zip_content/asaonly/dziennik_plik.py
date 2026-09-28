# -*- coding: utf-8 -*-
"""Dziennik zdarzeń także w pliku (V3.86.2).

Po co: do 3.86.1 dziennik żył tylko w oknie konsoli, a napis przy starcie
twierdził „zapis też w asa_debug.log” — tam trafiają jednak wyłącznie ukryte
błędy programu. 26.09.2026 przebieg aktualizacji serwera dało się odtworzyć
tylko ze zrzutu ekranu. Teraz każda linia dziennika (bez kolorów) trafia też
do WIEDZA_O_PROGRAMIE/dziennik-zdarzen.txt.

Pisze osobny wątek z kolejką — wątek okna nigdy nie czeka na dysk (tak samo
jak konsola, asaonly/konsola.py). Linie dziennika mają tylko godzinę, więc na
początku sesji i przy zmianie dnia plik dostaje wiersz z datą. Rotacja jak
dziennik-modow.txt: gdy plik przekroczyłby MAX_B, staje się
dziennik-zdarzen.01.txt (starsze przesuwają się, najwyżej KEEP kopii).
Błąd zapisu nigdy nie zatrzymuje programu — raz trafia do asa_debug.log.
"""
import datetime
import os
import queue
import threading

NAZWA = "dziennik-zdarzen.txt"
WZOR_KOPII = "dziennik-zdarzen.%02d.txt"
MAX_B = 5 * 1024 * 1024
KEEP = 5


def sciezka_kopii(katalog, numer):
    return os.path.join(katalog, WZOR_KOPII % numer)


def rotuj(katalog, keep=KEEP):
    """Bieżący plik -> .01, .01 -> .02 …; kopia ponad keep jest usuwana."""
    najstarsza = sciezka_kopii(katalog, keep)
    if os.path.exists(najstarsza):
        os.remove(najstarsza)
    for numer in range(keep - 1, 0, -1):
        z = sciezka_kopii(katalog, numer)
        if os.path.exists(z):
            os.replace(z, sciezka_kopii(katalog, numer + 1))
    biezacy = os.path.join(katalog, NAZWA)
    if os.path.exists(biezacy):
        os.replace(biezacy, sciezka_kopii(katalog, 1))


class PisarzPliku(object):
    """Dopisuje tekst do pliku dziennika w osobnym wątku. pisz() nie blokuje."""

    def __init__(self, katalog, naglowek="", max_b=MAX_B, keep=KEEP, na_blad=None, dzis=None):
        self.katalog = katalog
        self.sciezka = os.path.join(katalog, NAZWA)
        self._naglowek = str(naglowek or "")
        self._max_b = int(max_b)
        self._keep = int(keep)
        self._na_blad = na_blad
        self._blad_zgloszony = False
        self._dzien = None
        self._dzis = dzis or (lambda: datetime.date.today().isoformat())
        self._kolejka = queue.Queue()
        self._watek = threading.Thread(target=self._praca, name="event-log-writer", daemon=True)
        self._watek.start()

    def pisz(self, tekst):
        """Nie blokuje — tekst trafia do kolejki wątku zapisu."""
        if tekst:
            self._kolejka.put(str(tekst))

    def zamknij(self, czekaj_s=2.0):
        """Dopisz to, co czeka (najwyżej czekaj_s), i zakończ wątek."""
        self._kolejka.put(None)
        self._watek.join(czekaj_s)

    def _praca(self):
        while True:
            tekst = self._kolejka.get()
            if tekst is None:
                return
            czesci, koniec = [tekst], False
            while True:                       # wszystko, co już czeka — jednym zapisem
                try:
                    nastepny = self._kolejka.get_nowait()
                except queue.Empty:
                    break
                if nastepny is None:
                    koniec = True
                    break
                czesci.append(nastepny)
            self._zapisz("".join(czesci))
            if koniec:
                return

    def _zapisz(self, tekst):
        try:
            dzis = self._dzis()
            if self._dzien is None:
                tekst = "\n=== %s%s ===\n%s" % (dzis, (" · " + self._naglowek) if self._naglowek else "",
                                              tekst)
            elif dzis != self._dzien:
                tekst = "=== %s ===\n%s" % (dzis, tekst)
            self._dzien = dzis
            os.makedirs(self.katalog, exist_ok=True)
            if os.path.exists(self.sciezka):
                rozmiar = os.path.getsize(self.sciezka)
                if rozmiar > 0 and rozmiar + len(tekst.encode("utf-8")) > self._max_b:
                    rotuj(self.katalog, self._keep)
            with open(self.sciezka, "a", encoding="utf-8") as fh:
                fh.write(tekst)
        except Exception as exc:
            if not self._blad_zgloszony and self._na_blad is not None:
                self._blad_zgloszony = True
                try:
                    self._na_blad("event log file %s: %s" % (self.sciezka, exc))
                except Exception:
                    pass
