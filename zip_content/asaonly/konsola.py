# -*- coding: utf-8 -*-
"""Wydruk dziennika do konsoli w osobnym wątku (V3.85.2) i okno bez zatrzymań (V3.86.2).

Po co: w oknie konsoli Windows kliknięcie myszą włącza zaznaczanie (QuickEdit)
i od tej chwili KAŻDY zapis do konsoli czeka, aż zaznaczenie się skończy
(Esc, Enter albo prawy przycisk myszy). Do 3.85.1 dziennik drukował wątek
okna (Tk) — jedno kliknięcie w konsolę zatrzymywało całe okno programu
(„Brak odpowiedzi”) i wszystko, co robi wątek okna: automat, kolejkę
restartów, pluginy. Teraz czeka tylko ten wątek; linie zbierają się w kolejce
i pojawiają się w konsoli po zakończeniu zaznaczania.

V3.86.2: 26.09.2026 użytkownik musiał wcisnąć Enter w oknie refreshera, żeby
zobaczyć nowe linie. Program przy starcie wyłącza w SWOIM oknie tryb szybkiej
edycji (SetConsoleMode bez ENABLE_QUICK_EDIT_MODE, z ENABLE_EXTENDED_FLAGS —
tak każe dokumentacja Microsoft), a przy zamknięciu przywraca poprzedni tryb.
Kopiowanie tekstu: menu okna → Edytuj → Zaznacz albo plik dziennika.
"""
import os
import queue
import sys
import threading


class PisarzKonsoli(object):
    def __init__(self, strumien=None):
        self._strumien = strumien          # None = bieżące sys.stdout przy każdym zapisie
        self._kolejka = queue.Queue()
        self._watek = threading.Thread(target=self._praca, name="konsola", daemon=True)
        self._watek.start()

    def pisz(self, tekst):
        """Nie blokuje — tekst trafia do kolejki wątku konsoli."""
        if tekst:
            self._kolejka.put(str(tekst))

    def zamknij(self, czekaj_s=1.0):
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
            try:
                out = self._strumien if self._strumien is not None else sys.stdout
                if out is not None:
                    out.write("".join(czesci))
                    out.flush()
            except Exception:
                pass
            if koniec:
                return


# ---------------------------------------------------------------------------
# Tryb szybkiej edycji (QuickEdit) okna konsoli — V3.86.2
# ---------------------------------------------------------------------------
# Microsoft Learn, SetConsoleMode: ENABLE_QUICK_EDIT_MODE 0x0040 — „To disable
# this mode, use ENABLE_EXTENDED_FLAGS without this flag”; ENABLE_EXTENDED_FLAGS
# = 0x0080 (consoleapi.h). Uchwyt: bufor wejścia konsoli (STD_INPUT_HANDLE).
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
STD_INPUT_HANDLE = 0xFFFFFFF6            # (DWORD)-10


class _KonsolaWindows(object):
    """GetConsoleMode/SetConsoleMode wejścia konsoli przez ctypes (tylko Windows)."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._c = ctypes
        self._w = wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetStdHandle.restype = wintypes.HANDLE
        k.GetStdHandle.argtypes = (wintypes.DWORD,)
        k.GetConsoleMode.restype = wintypes.BOOL
        k.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k.SetConsoleMode.restype = wintypes.BOOL
        k.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        self._k = k
        self._h = k.GetStdHandle(STD_INPUT_HANDLE)

    def tryb(self):
        """Bieżący tryb wejścia konsoli albo None (brak konsoli, np. pythonw)."""
        if not self._h or self._h == self._w.HANDLE(-1).value:
            return None
        tryb = self._w.DWORD()
        if not self._k.GetConsoleMode(self._h, self._c.byref(tryb)):
            return None
        return int(tryb.value)

    def ustaw(self, tryb):
        return bool(self._k.SetConsoleMode(self._h, int(tryb)))


def _api_konsoli(api):
    if api is not None:
        return api
    if os.name != "nt":
        return None
    try:
        return _KonsolaWindows()
    except Exception:
        return None


def wylacz_szybka_edycje(api=None):
    """Kliknięcie w okno konsoli nie włącza zaznaczania.

    Zwraca poprzedni tryb (do przywroc_tryb) albo None, gdy nic nie zmieniono:
    nie Windows, brak konsoli, tryb już wyłączony albo system odmówił."""
    api = _api_konsoli(api)
    if api is None:
        return None
    try:
        stary = api.tryb()
        if stary is None or not stary & ENABLE_QUICK_EDIT_MODE:
            return None
        nowy = (stary | ENABLE_EXTENDED_FLAGS) & ~ENABLE_QUICK_EDIT_MODE
        return stary if api.ustaw(nowy) else None
    except Exception:
        return None


def przywroc_tryb(stary, api=None):
    """Przywróć tryb sprzed wylacz_szybka_edycje (przy zamknięciu programu)."""
    if stary is None:
        return False
    api = _api_konsoli(api)
    if api is None:
        return False
    try:
        return bool(api.ustaw(stary))
    except Exception:
        return False
