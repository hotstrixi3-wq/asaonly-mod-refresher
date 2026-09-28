# -*- coding: utf-8 -*-
"""Wymagany koordynator procedur: pokazuje stan kolejki (asaonly/kolejka.py) na kafelku.

V3.84: stara kolejka V3.80 (configure/pop_next/…) usunięta — od V3.81 nieużywana."""

from asaonly.jezyk import t


class Wtyczka:
    nazwa = "koordynator_procedur"
    API = 1
    TR = {}
    manager_visible = True
    version = "1.2.1"
    required = True

    @property
    def manager_name(self):
        return t("Koordynator procedur klastra / SSD", "Cluster / SSD procedure coordinator")

    @property
    def manager_description(self):
        return t(
            "Wymagany: pokazuje stan kolejki procedury. Naraz startuje najwyżej jedna "
            "mapa (dysk), ogłoszenia mogą trwać równolegle, puste mapy idą bez ogłoszeń. "
            "Mapa, która nie wróci, nie zatrzymuje pozostałych.",
            "Required: shows the state of the procedure queue. At most one map starts "
            "at a time (disk), announcements can run in parallel, empty maps go without "
            "announcements. A map that does not come back does not stop the others."
        )

    def __init__(self):
        self.core = None

    def start(self, core):
        self.core = core
        self._publish(t("GOTOWY — kolejka pusta", "READY — queue empty"), "#207020")

    def _publish(self, text, color="#555555"):
        if self.core:
            self.core.set_indicator(self.nazwa, text, color)

    def clear(self):
        self._publish(t("GOTOWY — kolejka anulowana", "READY — queue cancelled"), "#555555")

    def opublikuj(self, wiersze):
        """V3.81: stan inteligentnej kolejki (nazwa, stan, tryb, powód) na kafelku."""
        # Klucze to identyfikatory stanów kolejki (bez tłumaczenia), wartości — tekst na kafelek.
        opisy = {"sonda": t("sprawdza graczy", "checking players"),
                 "czeka": t("czeka", "waiting"),
                 "oglasza": t("ogłasza", "announcing"),
                 "gotowa": t("czeka na dysk", "waiting for disk"),
                 "wyjscie": "DoExit",
                 "start": t("startuje", "starting"),
                 "zrobiona": t("gotowa", "done"),
                 "nieudana": t("NIEUDANA", "FAILED"),
                 "pominieta": t("pominięta", "skipped")}
        aktywne = [(n, s, tryb) for n, s, tryb, _ in wiersze
                   if s not in ("zrobiona", "nieudana", "pominieta")]
        if not aktywne:
            failed = [n for n, s, _, _ in wiersze if s == "nieudana"]
            if failed:
                self._publish(t("ALARM — NIEUDANE: %s", "ALARM — FAILED: %s") % ", ".join(failed), "#b00020")
                return
            self._publish(t("GOTOWY — kolejka zakończona", "READY — queue finished"), "#207020")
            return
        tekst = "; ".join("%s: %s%s" % (n, opisy.get(s, s),
                                          t(" (pusto)", " (empty)") if tryb == "pusto" else "")
                          for n, s, tryb in aktywne)
        self._publish(t("TRWA — ", "RUNNING — ") + tekst, "#005a9c")

    def self_test(self):
        return {"ok": True, "details": t("publikacja stanu kolejki dostępna; wymagany plugin",
                                         "queue state publishing available; required plugin")}

    def konfiguracja(self):
        return {"required": True}

    def stop(self):
        self.clear()
