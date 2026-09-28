# -*- coding: utf-8 -*-
"""Język tekstów spoza słownika TR (V3.84).

Tekst stoi w kodzie w obu językach naraz: t("Polski", "English"). Język ustawia
program: property App.lang woła ustaw() przy starcie i przy przełączeniu PL/EN
(przełączenie przebudowuje okna i restartuje pluginy, więc wszystko rysuje się
od nowa w nowym języku). Wszystko, co widzi użytkownik — okna, pluginy,
dziennik — idzie przez t() albo przez słownik TR (asaonly/tr.py).

Test tests/test_i18n.py pilnuje, żeby polski tekst nie trafił do programu
z pominięciem t(), żeby tekst angielski nie miał polskich liter i żeby obie
wersje miały te same wstawki (%s, %d, {nazwa}).
"""

_jezyk = "pl"


def ustaw(jezyk):
    """Ustaw język interfejsu: "pl" albo "en" (wszystko inne = "pl")."""
    global _jezyk
    _jezyk = "en" if str(jezyk or "").strip().lower() == "en" else "pl"
    return _jezyk


def jezyk():
    return _jezyk


def t(pl, en):
    """Tekst w bieżącym języku interfejsu."""
    return en if _jezyk == "en" else pl
