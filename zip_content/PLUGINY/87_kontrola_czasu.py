# -*- coding: utf-8 -*-
"""Kontrola ręcznych ustawień czasu (V3.82).

Sprawdza harmonogramy RCON map tymi samymi regułami co procedura i pokazuje
podgląd fali restartów liczony prawdziwym planistą kolejki. Tylko odczyt:
niczego nie wysyła do serwerów i niczego nie zmienia w konfiguracji map.
Logika jest w asaonly/kontrola.py (testy: tests/test_kontrola.py).
"""
import copy
import tkinter as tk
from tkinter import ttk

from asaonly import kontrola as K
from asaonly.jezyk import t

CO_ILE_S = 5.0          # jak często tło sprawdza, czy ustawienia się zmieniły
KOLOR = {K.BLAD: "#b00020", K.UWAGA: "#b06000", K.INFO: "#555555"}


class Wtyczka:
    nazwa = "kontrola_czasu"
    API = 1
    TR = {}
    manager_visible = True
    version = "1.1.1"
    required = False
    # Na prośbę użytkownika (V3.82) kontrola działa od pierwszego uruchomienia;
    # tylko czyta, więc włączenie bez zapisanego wyboru jest bezpieczne.
    default_enabled = True
    main_action_hook = "panel"
    main_action_requires_enabled = False
    panel_available_when_off = True

    # Teksty dla człowieka są właściwościami: język liczy się w chwili odczytu.
    @property
    def manager_name(self):
        return t("Kontrola czasu RCON", "RCON time check")

    @property
    def main_action_text(self):
        return t("KONTROLA CZASU", "TIME CHECK")

    @property
    def manager_description(self):
        return t(
            "Sprawdza ręczne ustawienia czasu w harmonogramach RCON map tymi samymi regułami "
            "co procedura: które mapy procedura pominie (BŁĄD), podejrzane czasy i komunikaty "
            "(UWAGA), jak mapa zachowa się pusta i z graczami. Pokazuje podgląd fali restartów "
            "liczony prawdziwym planistą kolejki. Gdy jest ON, nowe błędy i uwagi trafiają do "
            "dziennika. Tylko odczyt — niczego nie wysyła do serwerów.",
            "Checks the manual time settings in the maps' RCON schedules with the same rules "
            "the procedure uses: which maps the procedure will skip (ERROR), suspicious times "
            "and messages (WARNING), how a map behaves when empty and with players. Shows a "
            "preview of the restart wave computed by the real queue planner. When ON, new "
            "errors and warnings go to the log. Read-only — sends nothing to the servers.")

    def __init__(self):
        self.core = None
        self.enabled = True
        self._nastepny_t = 0.0
        self._odcisk = None
        self._wynik = None            # (ogolne, wynik, mapy, konf)
        self._zalogowane = None       # zbiór (mapa, poziom, tekst) już w dzienniku
        self._podglad_nr = 0
        self._zamknij_okno()

    # -- cykl życia --------------------------------------------------------------
    def prepare(self, core):
        self.core = core
        cfg = core.plugin_config(self.nazwa)
        self.enabled = bool(cfg.get("enabled", self.default_enabled))
        self._wskaznik()

    def start(self, core):
        self.prepare(core)

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, value):
        self.enabled = bool(value)
        self.core.save_plugin_config(self.nazwa, {"enabled": self.enabled})
        self.core.set_plugin_toggle(self.nazwa, self.enabled)
        # Po ponownym włączeniu dziennik dostaje pełne podsumowanie od nowa.
        self._zalogowane = None
        self._odcisk = None
        self._wskaznik()

    def stop(self):
        self._zamknij_okno()

    def konfiguracja(self):
        return {"enabled": self.enabled}

    def self_test(self):
        ogolne, wynik = self._sprawdz_teraz()[:2]
        return {"ok": True, "details": t("kontrola tylko do odczytu: %s, %s",
                                         "read-only check: %s, %s") % (
            K.liczba(len(wynik), t("mapa|mapy|map", "map|maps")),
            K.bledy_i_uwagi(K.licz(ogolne, wynik, K.BLAD), K.licz(ogolne, wynik, K.UWAGA)))}

    # -- dane --------------------------------------------------------------------
    @staticmethod
    def _pole(tab, nazwa, domyslna):
        zmienna = getattr(tab, nazwa, None)
        try:
            return zmienna.get() if zmienna is not None else domyslna
        except Exception:
            return domyslna

    def _dane(self):
        app = self.core.application()
        mapy = []
        for nazwa, tab in list((getattr(app, "tabs", None) or {}).items()):
            mapy.append(K.MapaWe(str(nazwa), bool(self._pole(tab, "var_map_on", True)),
                                 str(self._pole(tab, "var_ip", "")),
                                 str(self._pole(tab, "var_port", "")),
                                 [dict(w) for w in (getattr(tab, "rows", None) or ())
                                  if isinstance(w, dict)]))
        cfg = getattr(app, "config_data", None)
        cfg = cfg if isinstance(cfg, dict) else {}
        konf = {"czasy_startu": copy.deepcopy(cfg.get("czasy_startu", {})),
                "pusty_serwer_od_razu": cfg.get("pusty_serwer_od_razu", True),
                "listplayers_pusto": copy.deepcopy(cfg.get("listplayers_pusto"))}
        return mapy, konf

    def _sprawdz_teraz(self):
        mapy, konf = self._dane()
        ogolne, wynik = K.sprawdz_klaster(mapy, konf)
        return ogolne, wynik, mapy, konf

    # -- praca w tle (tylko gdy ON) --------------------------------------------------
    def tik(self, teraz):
        if teraz < self._nastepny_t:
            return
        self._nastepny_t = teraz + CO_ILE_S
        self._odswiez()

    def _odswiez(self, wymus=False):
        mapy, konf = self._dane()
        odcisk = repr((mapy, sorted((k, repr(v)) for k, v in konf.items())))
        if odcisk == self._odcisk and not wymus:
            return
        self._odcisk = odcisk
        ogolne, wynik = K.sprawdz_klaster(mapy, konf)
        self._wynik = (ogolne, wynik, mapy, konf)
        self._wskaznik()
        if self.enabled:
            # Tylko NOWE błędy/uwagi — powtórne sprawdzenie niczego nie dubluje.
            self._do_dziennika(ogolne, wynik)
        self._pokaz_kontrole()
        self._przelicz_podglad()

    def _do_dziennika(self, ogolne, wynik):
        teraz = set()
        for x in ogolne:
            if x.poziom in (K.BLAD, K.UWAGA):
                teraz.add(("", x.poziom, x.tekst))
        for nazwa, (ustalenia, _) in wynik.items():
            for x in ustalenia:
                if x.poziom in (K.BLAD, K.UWAGA):
                    teraz.add((nazwa, x.poziom, x.tekst))
        poprzednio = self._zalogowane
        self._zalogowane = teraz
        nowe = sorted(teraz - (poprzednio or set()),
                      key=lambda x: (x[1] != K.BLAD, x[0], x[2]))
        if nowe:
            bledy = sum(1 for x in teraz if x[1] == K.BLAD)
            uwagi = len(teraz) - bledy
            self.core.log(t("[KONTROLA CZASU] Harmonogramy RCON: %s. Szczegóły: przycisk "
                            "KONTROLA CZASU.",
                            "[TIME CHECK] RCON schedules: %s. Details: the TIME CHECK button.")
                          % K.bledy_i_uwagi(bledy, uwagi), "st_wait")
            for nazwa, poziom, tekst in nowe:
                linia = t("[KONTROLA CZASU] %s%s: %s", "[TIME CHECK] %s%s: %s") % (
                    (nazwa + " — ") if nazwa else "", K.nazwa_poziomu(poziom), tekst)
                if poziom == K.BLAD:
                    self.core.warn(linia)
                else:
                    self.core.log(linia, "st_wait")
        elif poprzednio and not teraz:
            self.core.log(t("[KONTROLA CZASU] Harmonogramy RCON bez błędów i uwag.",
                            "[TIME CHECK] RCON schedules without errors or warnings."), "st_ok")

    def _wskaznik(self):
        if self.core is None:
            return
        if self._wynik is None:
            tekst = (t("ON — kontrola w tle", "ON — background check") if self.enabled
                     else t("OFF — panel działa na żądanie", "OFF — panel works on demand"))
            self.core.set_indicator(self.nazwa, tekst, "#207020" if self.enabled else "#555555")
            return
        ogolne, wynik = self._wynik[:2]
        bledy, uwagi = K.licz(ogolne, wynik, K.BLAD), K.licz(ogolne, wynik, K.UWAGA)
        if bledy:
            self.core.set_indicator(self.nazwa, K.bledy_i_uwagi(bledy, uwagi), KOLOR[K.BLAD])
        elif uwagi:
            self.core.set_indicator(self.nazwa, K.liczba(uwagi, t("uwaga|uwagi|uwag",
                                                                  "warning|warnings")),
                                    KOLOR[K.UWAGA])
        else:
            self.core.set_indicator(self.nazwa, t("harmonogramy bez uwag",
                                                  "schedules without warnings"), "#207020")

    # -- panel ---------------------------------------------------------------------------
    def _zamknij_okno(self):
        okno = getattr(self, "okno", None)
        self.okno = None
        self.txt = None
        self.lbl_podsum = None
        self.tree = None
        self.lbl_fala = None
        self.frm_puste = None
        self.var_zalozony = None
        self.vars_puste = {}
        if okno is not None:
            try:
                okno.destroy()
            except Exception:
                pass

    def _okno_zyje(self):
        try:
            return self.okno is not None and bool(self.okno.winfo_exists())
        except Exception:
            return False

    def panel(self, parent):
        if self._okno_zyje():
            self.okno.deiconify()
            self.okno.lift()
            self._odswiez(wymus=True)
            return self.okno
        self._zamknij_okno()
        okno = tk.Toplevel(parent)
        self.okno = okno
        okno.title(t("Kontrola czasu RCON", "RCON time check"))
        okno.geometry("1000x720")
        okno.minsize(760, 520)
        okno.protocol("WM_DELETE_WINDOW", self._zamknij_okno)
        ramka = ttk.Frame(okno, padding=12)
        ramka.pack(fill="both", expand=True)
        ttk.Label(ramka, text=t("KONTROLA RĘCZNYCH USTAWIEŃ CZASU", "MANUAL TIME SETTINGS CHECK"),
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(ramka, wraplength=940, justify="left", foreground="#555555", text=t(
            "Sprawdza harmonogramy RCON map tymi samymi regułami co procedura i pokazuje, "
            "jak pójdzie fala restartów. Czasy w harmonogramie są lokalne dla mapy (od początku "
            "jej odliczania). Tylko odczyt — niczego nie wysyła do serwerów. Zmiany robisz "
            "w panelu RCON; kontrola odświeża się sama.",
            "Checks the maps' RCON schedules with the same rules the procedure uses and shows "
            "how the restart wave will go. Times in a schedule are local to the map (from the "
            "start of its countdown). Read-only — sends nothing to the servers. You make changes "
            "in the RCON panel; the check refreshes itself.")).pack(anchor="w", pady=(2, 8))
        gora = ttk.Frame(ramka)
        gora.pack(fill="x")
        ttk.Button(gora, text=t("SPRAWDŹ TERAZ", "CHECK NOW"),
                   command=lambda: self._odswiez(wymus=True)).pack(side="left")
        self.lbl_podsum = ttk.Label(gora, text="", font=("TkDefaultFont", 10, "bold"))
        self.lbl_podsum.pack(side="left", padx=12)

        zakladki = ttk.Notebook(ramka)
        zakladki.pack(fill="both", expand=True, pady=(8, 0))

        # --- zakładka 1: kontrola -------------------------------------------------------
        str1 = ttk.Frame(zakladki, padding=6)
        zakladki.add(str1, text=t("KONTROLA HARMONOGRAMÓW", "SCHEDULE CHECK"))
        self.txt = tk.Text(str1, wrap="word", height=20, borderwidth=0)
        pasek = ttk.Scrollbar(str1, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=pasek.set)
        pasek.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        self.txt.tag_configure("mapa", font=("TkDefaultFont", 11, "bold"), spacing1=8)
        for poziom, kolor in KOLOR.items():
            self.txt.tag_configure(poziom, foreground=kolor, lmargin1=12, lmargin2=12)
        self.txt.tag_configure(K.BLAD, font=("TkDefaultFont", 9, "bold"))

        # --- zakładka 2: podgląd fali -------------------------------------------------
        str2 = ttk.Frame(zakladki, padding=6)
        zakladki.add(str2, text=t("PODGLĄD FALI", "WAVE PREVIEW"))
        ttk.Label(str2, wraplength=920, justify="left", text=t(
            "Liczy ten sam planista, który prowadzi prawdziwą kolejkę: jeden start naraz, puste mapy "
            "pierwsze, ogłoszenia „na styk”. Zakłada update moda używanego przez wszystkie mapy, które "
            "przechodzą kontrolę. Zaznacz mapy, które w tym scenariuszu są puste.",
            "Computed by the same planner that runs the real queue: one start at a time, empty maps "
            "first, announcements just in time. Assumes an update of a mod used by all maps that "
            "pass the check. Tick the maps that are empty in this scenario.")).pack(anchor="w")
        self.frm_puste = ttk.Frame(str2)
        self.frm_puste.pack(fill="x", pady=(6, 2))
        rzad = ttk.Frame(str2)
        rzad.pack(fill="x", pady=(2, 6))
        ttk.Button(rzad, text=t("WSZYSTKIE Z GRACZAMI", "ALL WITH PLAYERS"),
                   command=lambda: self._ustaw_puste(False)).pack(side="left")
        ttk.Button(rzad, text=t("WSZYSTKIE PUSTE", "ALL EMPTY"),
                   command=lambda: self._ustaw_puste(True)).pack(side="left", padx=(6, 18))
        ttk.Label(rzad, text=t("Czas startu map bez pomiaru [s]:",
                               "Start time of maps without a measurement [s]:")).pack(side="left")
        self.var_zalozony = tk.StringVar(value="")
        wpis = ttk.Entry(rzad, textvariable=self.var_zalozony, width=7)
        wpis.pack(side="left", padx=4)
        wpis.bind("<Return>", lambda _e: self._przelicz_podglad())
        ttk.Button(rzad, text=t("PRZELICZ", "RECALCULATE"),
                   command=self._przelicz_podglad).pack(side="left")
        kolumny = ("mapa", "tryb", "odliczanie", "doexit", "gotowa", "start")
        self.tree = ttk.Treeview(str2, columns=kolumny, show="headings", height=12)
        naglowki = {"mapa": t("Mapa", "Map"), "tryb": t("Tryb", "Mode"),
                    "odliczanie": t("Odliczanie od", "Countdown from"), "doexit": "DoExit",
                    "gotowa": t("GOTOWY", "READY"), "start": t("Czas startu", "Start time")}
        szer = {"mapa": 200, "tryb": 90, "odliczanie": 120, "doexit": 100, "gotowa": 100, "start": 220}
        for k in kolumny:
            self.tree.heading(k, text=naglowki[k])
            self.tree.column(k, width=szer[k], anchor="w" if k in ("mapa", "start") else "center")
        self.tree.pack(fill="both", expand=True)
        self.lbl_fala = ttk.Label(str2, text="", wraplength=920, justify="left")
        self.lbl_fala.pack(anchor="w", pady=(6, 0))

        ttk.Button(ramka, text=t("ZAMKNIJ", "CLOSE"),
                   command=self._zamknij_okno).pack(anchor="e", pady=(8, 0))
        self._odswiez(wymus=True)
        return okno

    def _pokaz_kontrole(self):
        if not self._okno_zyje() or self._wynik is None:
            return
        ogolne, wynik, mapy, _ = self._wynik
        bledy, uwagi = K.licz(ogolne, wynik, K.BLAD), K.licz(ogolne, wynik, K.UWAGA)
        if self.lbl_podsum is not None:
            if not mapy:
                tekst = t("Brak map do oceny", "No maps to assess")
                kolor = "#555555"
            elif bledy:
                tekst = t("%s — mapy z błędem procedura pominie",
                          "%s — the procedure will skip maps with an error") % K.bledy_i_uwagi(bledy, uwagi)
                kolor = KOLOR[K.BLAD]
            elif uwagi:
                tekst = t("Bez błędów; %s do przejrzenia", "No errors; %s to review") % K.liczba(
                    uwagi, t("uwaga|uwagi|uwag", "warning|warnings"))
                kolor = KOLOR[K.UWAGA]
            else:
                tekst = t("Harmonogramy bez błędów i uwag", "Schedules without errors or warnings")
                kolor = "#207020"
            self.lbl_podsum.configure(text=tekst, foreground=kolor)
        txt = self.txt
        if txt is None:
            return
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        if not mapy:
            txt.insert("end", t("Brak map. Dodaj mapę w głównym oknie.\n",
                                "No maps. Add a map in the main window.\n"), K.INFO)
        if ogolne:
            txt.insert("end", t("Ustawienia ogólne\n", "General settings\n"), "mapa")
            for x in ogolne:
                txt.insert("end", "%s: %s\n" % (K.nazwa_poziomu(x.poziom), x.tekst), x.poziom)
        for m in mapy:
            ustalenia, _ = wynik.get(m.nazwa, ([], None))
            txt.insert("end", "%s\n" % m.nazwa, "mapa")
            porzadek = {K.BLAD: 0, K.UWAGA: 1, K.INFO: 2}
            for x in sorted(ustalenia, key=lambda u: porzadek.get(u.poziom, 3)):
                txt.insert("end", "%s: %s\n" % (K.nazwa_poziomu(x.poziom), x.tekst), x.poziom)
        txt.configure(state="disabled")
        self._odbuduj_puste(mapy, wynik)

    def _odbuduj_puste(self, mapy, wynik):
        if self.frm_puste is None:
            return
        nazwy = [m.nazwa for m in mapy if wynik.get(m.nazwa, ([], None))[1]]
        if list(self.vars_puste) == nazwy:
            return
        stare = {n: v.get() for n, v in self.vars_puste.items()}
        for dziecko in self.frm_puste.winfo_children():
            dziecko.destroy()
        self.vars_puste = {}
        if nazwy:
            ttk.Label(self.frm_puste, text=t("Puste w scenariuszu:", "Empty in this scenario:")).pack(
                side="left", padx=(0, 6))
        for n in nazwy:
            var = tk.BooleanVar(value=stare.get(n, False))
            ttk.Checkbutton(self.frm_puste, text=n, variable=var,
                            command=self._przelicz_podglad).pack(side="left", padx=(0, 8))
            self.vars_puste[n] = var

    def _ustaw_puste(self, wartosc):
        for var in self.vars_puste.values():
            var.set(bool(wartosc))
        self._przelicz_podglad()

    def _przelicz_podglad(self):
        if not self._okno_zyje() or self._wynik is None or self.tree is None:
            return
        ogolne, wynik, mapy, konf = self._wynik
        dane = [(m.nazwa, wynik[m.nazwa][1]) for m in mapy if wynik.get(m.nazwa, ([], None))[1]]
        puste = {n for n, v in self.vars_puste.items() if v.get()}
        zalozony = None
        tekst = (self.var_zalozony.get() if self.var_zalozony is not None else "").strip()
        if tekst:
            if tekst.isdecimal() and int(tekst) > 0:
                zalozony = int(tekst)
            else:
                self._pokaz_fale([], [], t("Czas startu musi być liczbą sekund większą od zera.",
                                           "The start time must be a number of seconds greater than zero."))
                return
        sondy = bool(konf.get("pusty_serwer_od_razu", True))
        czasy = copy.deepcopy(konf.get("czasy_startu") or {})
        self._podglad_nr += 1
        nr = self._podglad_nr
        self.lbl_fala.configure(text=t("Liczę…", "Calculating…"), foreground="#555555")

        def praca():
            try:
                wiersze, braki = K.podglad_fali(dane, puste=puste, czasy_startu=czasy,
                                                czas_zalozony=zalozony, sondy=sondy)
                wynik_p = (wiersze, braki, None)
            except Exception as exc:
                wynik_p = ([], [], t("Błąd podglądu: %s", "Preview error: %s") % exc)
            self.core.post_ui(lambda: self._wynik_podgladu(nr, wynik_p, sondy, puste))
        self.core.run_async(praca)

    def _wynik_podgladu(self, nr, wynik_p, sondy, puste):
        if nr != self._podglad_nr or not self._okno_zyje():
            return
        wiersze, braki, blad = wynik_p
        if blad:
            self._pokaz_fale([], [], blad)
            return
        if braki:
            self._pokaz_fale([], braki, None)
            return
        uwagi = []
        if not sondy and puste:
            uwagi.append(t("Wykrywanie pustych map jest wyłączone — w programie wszystkie mapy "
                           "dostaną pełne harmonogramy, więc podgląd też.",
                           "Empty-map detection is turned off — in the program every map gets "
                           "its full schedule, so the preview does too."))
        self._pokaz_fale(wiersze, [], " ".join(uwagi) or None)

    def _pokaz_fale(self, wiersze, braki, komunikat):
        if self.tree is None:
            return
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for w in wiersze:
            self.tree.insert("", "end", values=(
                w.nazwa, K.nazwa_trybu(w.tryb),
                K.fmt_czas(w.ogloszenia_od) if w.ogloszenia_od is not None else "—",
                K.fmt_czas(w.doexit), K.fmt_czas(w.gotowa) if w.gotowa is not None else "?",
                "%s (%s)" % (K.fmt_czas(w.czas_startu), K.nazwa_zrodla(w.zrodlo))))
        if braki:
            tekst = (t("Brak zmierzonych czasów startu (%s). Wpisz zakładany czas startu w sekundach "
                       "i kliknij PRZELICZ — albo poczekaj, aż program zmierzy pierwszy restart.",
                       "No measured start times (%s). Enter an assumed start time in seconds "
                       "and click RECALCULATE — or wait until the program measures the first restart.")
                     % ", ".join(braki))
            kolor = KOLOR[K.UWAGA]
        elif wiersze:
            koniec = max(w.gotowa for w in wiersze if w.gotowa is not None)
            tekst = (t("Koniec fali po %s od wykrycia update'u. Czasy liczone od wykrycia; start map "
                       "„założony” lub „innej mapy” to przybliżenie.",
                       "The wave ends %s after the update is detected. Times are counted from "
                       "detection; an 'assumed' or 'from another map' start time is an approximation.")
                     % K.fmt_czas(koniec))
            kolor = "#207020"
        else:
            tekst = t("Żadna mapa nie przechodzi kontroli — nie ma czego pokazać.",
                      "No map passes the check — nothing to show.")
            kolor = KOLOR[K.INFO]
        if komunikat:
            tekst = komunikat + ("\n" + tekst if wiersze or braki else "")
            kolor = KOLOR[K.UWAGA] if not wiersze else kolor
        if self.lbl_fala is not None:
            self.lbl_fala.configure(text=tekst, foreground=kolor)
