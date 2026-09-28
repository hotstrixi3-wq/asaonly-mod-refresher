# RECENZJA V3.80.35 (agent arena.ai) — co dobre, co spaprane

> Dla asystenta AI, który będzie to poprawiał: każda pozycja ma dowód
> w postaci `plik:linia` albo wyniku komendy. Nic tu nie jest domysłem —
> miejsca niepewne są oznaczone jako NIE WIEM.
>
> Data recenzji: 2026-09-24 · paczka: `ASAonly-ModRefresher-V3.80.35-diagnostic-widget-lifecycle.zip`
> Punkt odniesienia: V3.74.1 (4530 linii) i `ANALIZA-COMBO-I-ROZBICIE.md` (K1–K10).

---

## 0. WERDYKT

Agent **naprawił prawie wszystko, co było źle w wykrywaniu wersji** (K1, K2, K3a,
K6, K7, K10) i to jest prawdziwa, dobra robota do zachowania.

Ale jednocześnie **odwrócił filozofię porażki programu**. V3.74 stała na
aksjomacie: *update wejdzie i tak przy najbliższym starcie serwera, refresher
tylko przyspiesza — więc każde pominięcie jest bezpieczne*. V3.80.35 w trzech
kluczowych miejscach robi odwrotnie: **zatrzymuje wszystko i czeka na człowieka**.
Dla programu, który ma chodzić non-stop obok managera i działać o 2 w nocy,
to jest regres ważniejszy niż wszystkie naprawy razem.

Dobra wiadomość: te trzy miejsca są lokalne. Naprawa nie wymaga przepisywania.

---

## 1. LICZBY

| | V3.74.1 | V3.80.35 | Zmiana |
|---|---|---|---|
| Kod produkcyjny | 4530 linii | **8842 linii** | **+95%** |
| Plik główny | 4530 | 2129 | −53% |
| Zadanie 3 (procedura RCON) | ~304 | `procedura.py` 752 + `50_koordynator` 74 + `86_rcon_admin` 710 = **1536** | **×5** |
| Plugin CPU | (plan: ~60) | **709** | ×12 |
| Testy | flota: sterownik v6 62/62, jednostkowe 39, debug5–27 | 131 testów w **2,86 s** | inna klasa |
| Wersje w 2 dni | — | V3.75 → V3.80.35 | ~60 notatek w WIEDZY |

Cel rozbicia brzmiał: *„żeby agent łatwo kminił"*. Pojedyncze pliki są mniejsze,
ale **cały system do ogarnięcia jest dwa razy większy**, a jedno zadanie
(procedura) jest rozsmarowane po trzech plikach.

---

## 2. CO JEST DOBRE — ZOSTAWIĆ

| Pozycja | Gdzie | Status |
|---|---|---|
| **K3a** zaznaczony pusty wiersz RCON jest pomijany; w pół wypełniony = błąd | `asaonly/server_tab.py:39` `validate_rcon_line_values` | ✅ dokładnie wg decyzji użytkownika |
| **K3b** zła mapa → `continue`, reszta dalej | `asaonly/procedura.py:333` | ✅ (ale patrz S3 — okienko modalne) |
| **K7** prawdziwe markery CFCore: `Request to Install`, `Starting download`, `requires upgrade/downgrade` | `asaonly/logtail.py:13`, `asaonly/serwer_wersje.py:15,23` | ✅ |
| **K1/K10** wybór pliku `-windowsserver` zamiast `max(latestFiles)` | `asaonly/siec.py:123` | ✅ |
| **K2** odczyt `library.json` CFCore (`installedFile`) | `asaonly/serwer_wersje.py:30–110` | ✅ |
| **K6** wykrywanie zdublowanego portu RCON | `asaonly/server_tab.py` `duplicate_enabled_ports` | ✅ (ale patrz S6) |
| Bug V3.74: podbijanie `known_versions` mimo nieudanego `DoExit` | weryfikacja wersji per mapa | ✅ dobre znalezisko agenta |
| Plugin CPU — rdzeń logiki: `ctypes`, uchwyty zamykane w `finally`, rusza tylko przy statusie GOTOWY i gdy proces żyje ≥ 30 s (manager nakłada swoje po 25 s — K9), koryguje przy każdym rozjeździe, po zapisie czyta Windows ponownie | `PLUGINY/60_cpu.py:180–316` | ✅ |
| Blizny: `FILE_SHARE_DELETE`, skan 2 MB, łaska 15 s, retry RCON 3× co 2 s | `asaonly/logtail.py:47–60,137,271`, `PLUGINY/86_rcon_admin.py:528` | ✅ zachowane |
| Wydzielenie `tr.py`, `widgety.py`, `siec.py`, `zapis.py` | `asaonly/` | ✅ |
| Uczciwość dokumentacji: agent sam wypisał, czego nie sprawdził na Windows/ASA | `AKTUALNA-LISTA-…`, `LISTA-ZAPOMNIANYCH-…` | ✅ |

---

## 3. CO SPAPRANE — od najgroźniejszego

### S1 ★★★ Blokada po restarcie refreshera — program staje i czeka na człowieka

**Dowód:**
```python
# ASAonly…py:346-347
self.procedure_run = copy.deepcopy(self.config_data.get("procedure_run"))
self._procedure_recovery_blocked = bool(self.procedure_run)

# asaonly/procedura.py:244-262
def _exec_pending(self):
    if self.__dict__.get("_procedure_recovery_blocked", False):
        if messagebox.askyesno(... "Czy po ręcznym sprawdzeniu serwerów usunąć
                blokadę odzyskiwania? Procedura NIE rozpocznie się w tym kliknięciu." ...):
            ...
        return
```

**Skutek:** refresher padnie w trakcie procedury (prąd, aktualizacja Windows,
crash, zamknięcie okna) → po starcie **cała automatyka RCON jest zablokowana**,
dopóki ktoś nie kliknie TAK w okienku, a nawet wtedy procedura rusza dopiero
przy następnym wywołaniu.

**Dlaczego to błąd, a nie ostrożność:** przerwana procedura niczego nie psuje.
Mapa, która dostała `DoExit`, wstała i sama podniosła mody. Mapa, która nie
dostała, zostanie obsłużona przy następnym sprawdzeniu — zaległość wciąż wisi,
a istniejące guardy (blokada `DoExit` przy wstającym serwerze, zdejmowanie
zaległości po wersji na dysku) chronią przed podwójnym restartem.

**Naprawa:** przy starcie przerwany `procedure_run` → wpis w dzienniku
(„przerwana procedura z <czas>, mapa X, etap Y — porzucona") i **wyzerowanie**.
Żadnej blokady, żadnego okienka.

---

### S2 ★★★ Jedna mapa, która nie wróci, kasuje kolejkę pozostałych

**Dowód:**
```python
# asaonly/procedura.py:618-630
if not all_done:
    self._pause_coordinator("serwer nie wrócił do GOTOWY", names[0])
    return
...
if still_pending:
    self._pause_coordinator("nieudana weryfikacja wersji", name)
    return

# PLUGINY/50_koordynator_procedur.py
def pause(self, reason, map_name=None):
    self._queue = []          # <-- pozostałe mapy WYRZUCONE
```

**Skutek:** to jest **K3 odrodzone w skali klastra**. Pierwsza mapa w kolejce
nie wróci w 20 min albo nie potwierdzi wersji → pozostałe mapy nie dostają
`DoExit` w ogóle.

Kolejka budowana jest w stałej kolejności tabów (`asaonly/procedura.py:320`,
`for tab in self.tabs.values()`), więc **jeśli ta sama mapa zawodzi co turę,
reszta klastra nie zrestartuje się nigdy**.

Weryfikacja wersji jest nowa i — wg samego agenta
(`LISTA-ZAPOMNIANYCH-…` pkt 10) — **niesprawdzona na prawdziwych serwerach**.
Niesprawdzony mechanizm jest bramką dla całego klastra.

**Naprawa:** mapa, która nie wróciła albo nie potwierdziła wersji → oznaczona
jako nieudana, głośny wpis, **następna mapa rusza**. Zaległość dla nieudanej
mapy zostaje i spróbuje się przy kolejnej turze.

---

### S3 ★★★ Okienka modalne na ścieżce automatycznej

`_exec_pending` jest wołane automatycznie z `asaonly/cf_wersje.py:114` i `:231`.
W jego ciele jest **sześć** okienek modalnych (`asaonly/procedura.py:247, 274,
288, 299, 372, 391`), z czego **pięć** leży na ścieżce automatycznej.

Najgorsze jest to w linii 372:
```python
if invalid_maps:
    messagebox.showwarning(...,
        "Pominięto błędnie skonfigurowane mapy; pozostałe będą kontynuowane: ...")
# dopiero PO kliknięciu OK kod idzie dalej i startuje procedurę
```

Komunikat mówi „pozostałe będą kontynuowane", ale `showwarning` **blokuje
wykonanie do kliknięcia OK**. O 2 w nocy dobre mapy czekają na człowieka.
Naprawa K3b jest w praktyce unieważniona przez to okienko.

**Naprawa:** `_exec_pending(manual=False)`. Okienka tylko gdy `manual=True`
(wywołanie z przycisku). Na ścieżce automatycznej — `log_warn` i dalej.

---

### S4 ★★ Znaczenie czasów w liniach RCON zmienione po cichu

V3.74 (PTK 11, decyzja użytkownika): **globalny zegar T0**, czasy per mapa
służą **rozjazdowi**. Genesis `5 → doExit`, Ragnarok `205 → doExit` = 200 s
odstępu od chwili wykrycia.

V3.80 (`V3.80-KOORDYNATOR-STANOWY.md`): *„harmonogram taba jest jego lokalną
osią czasu"*, mapy idą **ściśle po kolei**, następna rusza dopiero po GOTOWY
poprzedniej i potwierdzeniu wersji.

**Skutek:** Ragnarokowe `205` znaczy teraz „205 s **po tym, jak Genesis już
wstała i się zweryfikowała**" — czyli 205 s czystego czekania ponad już
wymuszony odstęp. Trzy mapy = trzy pełne starty jeden po drugim plus suma
czasów lokalnych.

**NIE WIEM**, czy użytkownik zamówił tryb ściśle sekwencyjny. Jeśli tak — to
dobry pomysł pod SSD, ale stare czasy trzeba przeliczyć (zwykle na `5` dla
każdej mapy). Jeśli nie — zmiana semantyki bez zgody.

---

### S5 ★★ Testy „klastra" nie testują ścieżki produkcyjnej

**Dowód:** `symulacja/test_cluster.py` buduje `FakeApp(ProcedureMixin)` **bez**
`plugin_host`. Wtedy procedura idzie gałęzią:
```python
# asaonly/procedura.py:41-44
# Wyłącznie dla izolowanych symulacji bez hosta pluginów.
if not self.__dict__.get("plugin_host"):
    return tab.enqueue_rcon(command, callback)
```
czyli **gałęzią oznaczoną w kodzie jako „wyłącznie dla symulacji"**. Produkcyjny
tor — RCON przez plugin 86, kolejka przez plugin 50 — nie jest przez te testy
wykonywany. Dodatkowo `_rcon_validate` w tej gałęzi woła `tab.validate_lines()`,
którego prawdziwy `ServerTab` już nie ma (`grep "def validate_lines"` → brak).

Ponadto: **11 z 64** testów w `tests/test_plugins.py` sprawdza **tekst kodu
źródłowego** (`read_text()` + `assertIn`), nie działanie. Agent sam to przyznaje
(`AKTUALNA-LISTA-…` pkt 3).

Stara flota (sterownik v6 z prawdziwym mainloop Tk, FakeRCON na prawdziwych
gniazdach, FakeArk na dysku, marsz przyciskowy 54 checki) **nie istnieje w
paczce**. 131 testów w 2,86 s to wyłącznie testy jednostkowe i makiety.

---

### S6 ★★ Konflikt portów zatrzymuje całą procedurę

```python
# asaonly/procedura.py:284-291
if dup:
    self.log_warn("Konflikt portów RCON — procedura zatrzymana:\n" + msg)
    messagebox.showerror(...)
    return
```

Wykrycie jest dobre, reakcja zła: dwie mapy na wspólnym porcie → **cały klaster**
bez procedury, plus okienko modalne. Niejednoznaczne są tylko te dwie mapy.

**Naprawa:** pominąć mapy z konfliktem, głośny wpis, reszta dalej.

---

### S7 ★★ Testy zaśmiecają prawdziwą czarną skrzynkę programu

**Dowód — wykonany:**
```
asa_debug.log w paczce:                109 linii
po JEDNYM przebiegu pytest:            112 linii
dopisane: "JSON save error /tmp/tmp…/state.json: injected commit failure"
          "legacy conflict quarantined: /tmp/tmp…/legacy.json -> …"
          "Invalid procedure checkpoint /tmp/tmp…/PROCEDURE_RUN_STATE.json …"
```

Każdy przebieg testów dopisuje trzy fałszywe błędy do
`WIEDZA_O_PROGRAMIE/asa_debug.log` — prawdziwego dziennika diagnostycznego.
**Log dostarczony w paczce to w 100% śmieci z sandboksa agenta** (ścieżki
`/tmp/…`). Plugin `82_diagnostyka_zip` pakuje ten plik do zipów diagnostycznych.

**Naprawa:** testy przekierowują `write_debug_log` do katalogu tymczasowego.

---

### S8 ★ Plugin 84 łamie bliznę, której reszta programu pilnuje

```python
# PLUGINY/84_analizator_logow.py:27
with open(path,'rb') as f: ...        # path = …/ShooterGame.log
```

Zwykły `open()` na żywym logu serwera — **dokładnie ten przypadek, przed którym
ostrzega blizna nr 1**: manager kasuje log przy restarcie, a otwarty bez
`FILE_SHARE_DELETE` plik może przerwać start serwera. W `asaonly/logtail.py`
jest poprawne `open_log_shared` — tu nie użyte.

Ten sam plugin szuka zdarzeń CFCore wzorcem `Updating|Installing`, który **nie
pasuje do żadnej prawdziwej linii** — licznik „CFCore update" zawsze pokaże 0.

---

### S9 ★ Martwe stałe blizn — pułapka dla następnego agenta

- `BIG_LOG_BYTES` (heurystyka „duży log bez markera = GOTOWY") została
  **świadomie usunięta** z logiki (`asaonly/logtail.py`, komentarz „Rozmiar pliku
  nie jest dowodem gotowości"), co jest do obrony. Ale stała **dalej jest
  zdefiniowana w dwóch miejscach**: `ASAonly…py:146` i `asaonly/logtail.py:9`.
  Nigdzie nieużywana.
- `INITIAL_SCAN_BYTES` i `ROTATION_GRACE_S` są zdefiniowane w pliku głównym
  (`ASAonly…py:145,147`), ale `LogTail` używa **własnych kopii** z
  `asaonly/logtail.py`. Zmiana w pliku głównym **nic nie robi**.

Sekcja 4a („blizny") w dokumentacji dalej opisuje `BIG_LOG_BYTES` jako działającą.

---

### S10 ★ Rozrost funkcji

| Plugin | Linii | Wymagany |
|---|---|---|
| 60 CPU — w tym **benchmark rdzeni, topologia, rekomendacje** | 709 | nie |
| 70 Status i historia | 214 | nie |
| 80 Importer starych konfigów | 288 | nie (domyślnie ON) |
| 81 Backup / przywracanie | 233 | nie |
| 82 Pakiet diagnostyczny ZIP | 102 | nie |
| 83 Dysk / katalogi | 117 | nie |
| 84 Analizator logów | 33 | nie |

**NIE WIEM**, które z tych funkcji zamówił użytkownik. Część wersji 3.80.x
(ON/OFF, diagnostyka na zniszczonych widgetach, migracja stanów) to naprawianie
**samego mechanizmu pluginów**, a nie funkcji programu.

---

### S11 ★ Porządki w paczce

- w zipie: `.pytest_cache/`, `CONFIG_PROGRAM/PROCEDURE_RUN_STATE.json`
  (stan uruchomieniowy), zaśmiecony `asa_debug.log`
- nagłówek pliku głównego: tytuł `V3.80.35`, historia zmian kończy się na `3.74`

---

### Otwarte bez zmian

**K4 — dwa harmonogramy restartów** (managera i refreshera). Własna analiza
agenta (`PELNA-ANALIZA-WSTECZNA-V3.74.1.md:399,403,778`) doszła do tego samego
wniosku i zaleciła wyłączenie harmonogramu managera — ale w kodzie nie ma nic,
a decyzji użytkownika nie zapisano.

---

## 4. WSPÓLNY KORZEŃ S1, S2, S3, S6

Wszystkie cztery to ten sam odruch: **„nie mam pewności → zatrzymaj wszystko
i zapytaj człowieka"**. To jest poprawny odruch dla banku. Dla akceleratora
jest błędny, bo tu **niepewność kosztuje co najwyżej opóźnienie**, a zatrzymanie
kosztuje brak działania do czasu, aż ktoś wstanie.

Reguła do wpisania na stałe w kontekst agenta:

> Refresher NIGDY nie zatrzymuje całego klastra z powodu jednej mapy.
> Refresher NIGDY nie czeka na kliknięcie na ścieżce automatycznej.
> Po restarcie refresher NIGDY nie blokuje się — porzuca przerwaną procedurę
> i ocenia stan od nowa.
> Uzasadnienie: każdy update wejdzie i tak przy najbliższym starcie serwera.

---

## 5. KOLEJNOŚĆ NAPRAWY

| # | Co | Rozmiar |
|---|---|---|
| 1 | **S1** — przerwany `procedure_run` przy starcie: wpis w dzienniku + wyzerowanie, bez blokady | mały |
| 2 | **S2** — `_pause_coordinator` zastąpić „mapa nieudana → następna" | mały |
| 3 | **S3** — `_exec_pending(manual=False)`; okienka tylko dla przycisku | mały |
| 4 | **S6** — pomijać mapy z konfliktem portu, reszta dalej | mały |
| 5 | **S7** — izolacja `write_debug_log` w testach; wyczyścić `asa_debug.log` | mały |
| 6 | **S8** — `open_log_shared` + prawdziwe wzorce CFCore w pluginie 84 | mały |
| 7 | **S9** — usunąć martwe stałe z pliku głównego i `BIG_LOG_BYTES`; poprawić sekcję 4a | mały |
| 8 | **S5** — co najmniej jedna symulacja klastra przez prawdziwy `PluginHost` | średni |
| 9 | **S4** — decyzja użytkownika o semantyce czasów | decyzja |
| 10 | **K4** — decyzja użytkownika o jednej władzy nad restartami | decyzja |
| 11 | **S10** — decyzja użytkownika, które pluginy zostają | decyzja |

Punkty 1–7 to razem prawdopodobnie kilkadziesiąt linii zmian. **Przywracają
aksjomat bez ruszania dobrych napraw wersji.**
