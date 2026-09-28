# -*- coding: utf-8 -*-
"""V3.84: wersja angielska jest kompletna — pilnuje tego ten test.

Zasada: każdy tekst dla człowieka stoi w kodzie jako t("polski", "English")
(asaonly/jezyk.py) albo w słowniku TR (asaonly/tr.py). Test przegląda AST
programu, pakietu asaonly/ i wszystkich pluginów:
  * polski tekst poza t()/TR/docstringiem = błąd,
  * tekst angielski w t() nie może mieć polskich liter,
  * obie wersje w t() muszą mieć te same wstawki (%s, %d, {nazwa}).
Nie tłumaczy się: identyfikatorów (stany kolejki, klucze konfiguracji), nazw
plików (także dawnych nazw w migracji: „… - zapis”) i wzorców wyrażeń regularnych.
"""
import ast
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

POLSKIE_LITERY = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
POLSKIE_SLOWA = re.compile(
    r"\b(nie|jest|są|serwer\w*|mapa|mapy|mapę|mapie|brak\w*|plik\w*|katalog\w*|wybierz|skanuj|"
    r"zapisz|włącz\w*|wyłącz\w*|gotow\w*|czeka\w*|trwa|kolejk\w*|gracz\w*|"
    # Tylko polskie formy — angielskie „procedure” (dziennik asa_debug.log) jest w porządku.
    r"procedur(?:a|y|ze|ę|ą|om|ami|ach)?|rekord\w*|ponad|konfiguracj\w*|"
    r"komunikat\w*|pomini\w*|zamknij|dziennik\w*|odczyt\w*|sekund\w*|minut\w*|godzin\w*|"
    r"wersj\w*|modów|klucz\w*|hasło|uwag\w*|błąd|błęd\w*|oraz|tylko|już|gdy|jeśli|przez|"
    r"bez|dla|albo|lub|ustawieni\w*|sprawdz\w*|zaległ\w*|czuwani\w*|restartu|pusta|puste|"
    r"pusty|zrobiona|nieudana|startuje|ogłasza\w*|dysku|wolny|wolne|konieczn\w*|opcjonaln\w*|"
    r"zawsze|uruchom\w*|diagnostyk\w*|techniczn\w*|aktywn\w*|niezgodn\w*|wynik\w*|zapisan\w*|"
    r"wczytan\w*|zmian\w*|dodaj|wyślij|szczegół\w*|kontrol\w*|ustaw\w*|okno|okna|przycisk\w*|"
    r"pobier\w*|pobran\w*|zainstal\w*|nazw\w*|stan|stanu|mapa|tak|nowy|nowa|nowe|stary|stara|"
    r"odczytu|zapisu|pliku|folder\w*u|serwerów|map\b(?=[:\s]*$)|mod\b(?= \w+ł)|wszystk\w*|"
    r"żaden|żadna|żadne|zamknięt\w*|otw\w*|wybran\w*|wybierz|anuluj\w*|potwierdz\w*)\b", re.I)
WSTAWKI = re.compile(r"%(?:\([a-z_]+\))?[-+ 0#]*\d*(?:\.\d+)?[sdifr%]|\{[a-zA-Z_][a-zA-Z0-9_]*[^}]*\}")


def pliki_programu():
    yield ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
    for p in sorted((ROOT / "asaonly").glob("*.py")):
        if p.name != "tr.py":                       # TR ma własne testy parzystości
            yield p
    yield from sorted((ROOT / "PLUGINY").glob("*.py"))


def techniczny(tekst):
    """Identyfikatory, nazwy plików i wzorce regex zostają bez tłumaczenia."""
    if re.fullmatch(r"[a-z][a-z0-9_]*", tekst):                    # stan, klucz, tag
        return True
    if re.search(r"\.(json|jsonl|txt|md|log|py|zip|exe)\b", tekst):  # nazwa pliku
        return True
    if tekst.rstrip().endswith("- zapis"):                         # baza nazw plików zapisu
        return True
    if re.search(r"\(\?[:!=<]|\\[bdswSW]|\[[^\]]+\][*+?]", tekst):  # wzorzec regex
        return True
    if "a-z" in tekst and " " not in tekst:                        # klasa znaków regex
        return True
    return False


def _docstringi(drzewo):
    wynik = set()
    for w in ast.walk(drzewo):
        if isinstance(w, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            b = w.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                wynik.add(id(b[0].value))
    return wynik


def _wywolania_t(drzewo):
    return [w for w in ast.walk(drzewo)
            if isinstance(w, ast.Call) and isinstance(w.func, ast.Name) and w.func.id == "t"]


class WersjaAngielska(unittest.TestCase):
    def test_brak_polskiego_tekstu_poza_t_i_tr(self):
        bledy = []
        for plik in pliki_programu():
            drzewo = ast.parse(plik.read_text(encoding="utf-8"))
            pomin = _docstringi(drzewo)
            for w in _wywolania_t(drzewo):
                for arg in w.args:
                    pomin.update(id(x) for x in ast.walk(arg))
            for w in ast.walk(drzewo):                             # namedtuple("X", "pola ...")
                if isinstance(w, ast.Call) and getattr(w.func, "id", "") == "namedtuple":
                    pomin.update(id(x) for x in w.args)
            for w in ast.walk(drzewo):
                if isinstance(w, ast.Constant) and isinstance(w.value, str) and id(w) not in pomin:
                    if techniczny(w.value):
                        continue
                    if POLSKIE_LITERY.search(w.value) or POLSKIE_SLOWA.search(w.value):
                        bledy.append("%s:%d: %r" % (plik.relative_to(ROOT), w.lineno, w.value[:80]))
        self.assertEqual(bledy, [], "Polski tekst bez t():\n" + "\n".join(bledy))

    def test_t_ma_dwa_teksty_angielski_bez_polskich_liter_i_te_same_wstawki(self):
        bledy = []
        for plik in pliki_programu():
            drzewo = ast.parse(plik.read_text(encoding="utf-8"))
            for w in _wywolania_t(drzewo):
                miejsce = "%s:%d" % (plik.relative_to(ROOT), w.lineno)
                if len(w.args) != 2 or w.keywords or not all(
                        isinstance(a, ast.Constant) and isinstance(a.value, str) for a in w.args):
                    bledy.append("%s: t() musi dostać dwa zwykłe teksty (bez f-stringów)" % miejsce)
                    continue
                pl, en = w.args[0].value, w.args[1].value
                if POLSKIE_LITERY.search(en):
                    bledy.append("%s: polskie litery w tekście EN: %r" % (miejsce, en[:60]))
                if sorted(WSTAWKI.findall(pl)) != sorted(WSTAWKI.findall(en)):
                    bledy.append("%s: różne wstawki PL %s / EN %s" % (
                        miejsce, WSTAWKI.findall(pl), WSTAWKI.findall(en)))
        self.assertEqual(bledy, [], "\n".join(bledy))

    def test_przelaczenie_jezyka(self):
        from asaonly import jezyk
        self.addCleanup(jezyk.ustaw, "pl")
        self.assertEqual(jezyk.t("tak", "yes"), "tak")
        jezyk.ustaw("en")
        self.assertEqual(jezyk.t("tak", "yes"), "yes")
        jezyk.ustaw("cokolwiek")
        self.assertEqual(jezyk.jezyk(), "pl")


if __name__ == "__main__":
    unittest.main(verbosity=2)
