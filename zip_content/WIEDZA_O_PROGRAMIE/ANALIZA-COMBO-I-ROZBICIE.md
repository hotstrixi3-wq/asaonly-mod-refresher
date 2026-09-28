# ANALIZA WSTECZNA COMBO + PROPOZYCJA ROZBICIA NA KLOCKI

> Dla asystenta AI: ten plik opisuje, jak współpracują trzy programy —
> **serwer ARK**, **ASA Dedicated Manager** i **ASAonly ModRefresher** — gdzie
> sobie wchodzą w drogę, i jak rozbić refreshera na klocki mieszczące się
> w głowie jednego agenta. Wszystko poniżej jest sprawdzone w logach
> serwera albo w kodzie refreshera V3.74.1. Miejsca niepewne są oznaczone.
>
> Data analizy: 2026-09-20 · analizowana wersja: V3.74.1 (4530 linii)

---

## 0. TRZEJ AKTORZY — kto za co odpowiada

Potwierdzone w logu serwera i przez użytkownika.

| Aktor | Robota | Czego NIE robi |
|---|---|---|
| **CurseForge** | wie, jaka wersja moda istnieje | nie wie, co masz zainstalowane |
| **SERWER** (`ArkAscendedServer.exe`) | przy KAŻDYM starcie sam sprawdza i podnosi mody, własnym kluczem CF | nie rusza modów w trakcie pracy |
| **MANAGER** (ASADedicatedManager) | uruchamia serwery, monitoruje swoje procesy, stawia po padzie, aktualizuje build serwera, nakłada priorytet CPU | **nie umie sprawdzać wersji modów** |
| **REFRESHER** | monitoruje stan serwerów, kontroluje wersje modów na CF i na serwerach, zarządza procedurą RCON zaplanowaną w czasie | nie pobiera modów, nie stawia procesów, nie zabija procesów |

### Dowód, że mody podnosi serwer, nie manager

Extinction, start 2026-09-20:

```
[03.09.25:939] Log file open
[03.09.26:983] LogCFCore: SetSettings called: { "gameId": 83374, "apiKey": "*****" }
[03.09.27:563] LogCFCore: No need to update existing mod: Better Horde Mode (1163881)
[03.09.27:845] UShooterEngine::LoadGameMods with 10 mods
```

**1,6 sekundy od otwarcia logu.** Klient CurseForge wbudowany w silnik
(`cfcore.ue 1.47.0`), własny klucz API, własny rejestr `library.json`.

Przykład faktycznego podniesienia (17.09, trzy mody):

```
19:23:35.520  Deleting mods dir .../1163881_7737973
19:23:36.034  Mod: Cybers Structures QoL+ (940975) requires upgrade/downgrade (8673705 -> 8837561)
19:23:36.034  Mod: Awesome ARK Tools (941450) requires upgrade/downgrade (8637822 -> 8828067)
19:23:36.039  Request to Install mod 'Better Horde Mode' (modId=1163881, fileId=7737976)
19:23:36.762  Starting download - 1 parts for https://mediafilez.forgecdn.net/...
19:23:38.557  Successfully installed mod 'Cybers Structures QoL+' (fileId=8837561)
19:23:38.627  Mod valid: ... (10 modów)
```

**Trzy sekundy**, całość przed dotknięciem modów przez silnik.

### Dlaczego mody NIE wchodzą w trakcie pracy

Trzy niezależne dowody:

1. Silnik wczytuje mody raz — `UShooterEngine::LoadGameMods`. Podmiana plików
   na dysku pod żywym serwerem nie rusza tego, co jest w pamięci.
2. Obserwacja: 3 h 41 min pracy Extinction, **zero aktywności CFCore po starcie**
   (ani w `ShooterGame.log`, ani we własnym logu CFCore).
3. Mod „Mod Updater" na CurseForge, pisany przez kogoś działającego WEWNĄTRZ
   serwera, rozwiązuje ten sam problem restartem: *„Auto detect mod updates and
   restart your servers"*, i wprost zaznacza, że nie aktualizuje modów na
   chodzącym serwerze.

**Wniosek: restart to jedyna droga. To nie jest ograniczenie refreshera, to
własność gry.**

---

## 1. PEŁNY ŁAŃCUCH JEDNEJ AKTUALIZACJI

```
[AUTOR MODA]  publikuje wydanie na CurseForge
              → powstaje KILKA plików: klient, -windowsserver, ...       ⚠ K1

[REFRESHER]   co 300 s: batch POST /v1/mods → max(latestFiles)
              → porównanie z known_versions
              → wybór map używających moda (_tabs_for_mod)               ⚠ K2

[REFRESHER]   harmonogram z linii RCON, czas = sekundy od wykrycia
              T+5   Genesis  → doExit
              T+205 Ragnarok → doExit                                    ⚠ K3 ⚠ K4

[SERWER]      zapis świata → "Log file closed" → proces kończy się

[MANAGER]     wykrywa brak SWOJEGO procesu → stawia serwer              ⚠ K5 ⚠ K6

[SERWER]      +1,6 s  CFCore: requires upgrade/downgrade (A -> B)
              +3,0 s  pobiera -windowsserver, hash, rozpakowanie        ⚠ K7 ⚠ K8
              LoadGameMods → engine → "advertising for join"

[MANAGER]     +25 s   nakłada priorytet CPU z zaznaczenia listy         ⚠ K9

[REFRESHER]   czuwanie widzi READY → _verify_local_mods zdejmuje
              zaległość, porównując KATALOG z known_versions            ⚠ K10
```

---

## 2. KOLIZJE — od najgroźniejszej

### K4 ★★★ DWA HARMONOGRAMY RESTARTÓW NA JEDNYM KLASTRZE

Manager ma własny harmonogram restartów (`WarnDelayMinutes`,
`ScheduleRconMessageText` — **różne na trzech serwerach**). Refresher ma swój
w liniach RCON. **Żaden nie wie o drugim.**

Scenariusze awarii:

- manager usypia serwer, refresher wysyła do niego `doExit` — komenda w próżnię
- manager stawia mapę w środku rozjazdu — wraca, zanim reszta padła
- czuwanie widzi READY i melduje sukces, choć połowa map nie dostała `doExit`

**Brak jakiegokolwiek zabezpieczenia.** Największa dziura w combo.

### K9 ★★★ MANAGER NADPISUJE PRIORYTET CPU

Zmierzone na 192 wpisach: manager nakłada priorytet **25,0 s po starcie
procesu** (mediana; min 25,0 / max 26,0). Bierze wartość z zaznaczenia listy
rozwijanej, nie z zapisanego profilu — stąd samoczynne powroty na RealTime,
rozjazd między zakładkami i zmiany bez restartu managera.

**Konsekwencja dla pluginu CPU: nakładać PO 25 sekundzie.** Wcześniej =
walka z managerem, przegrana.

### K3 ★★★ JEDNA ZŁA MAPA BLOKUJE CAŁY KLASTER

```python
# _exec_pending()
lines, err = tab.validate_lines()
if err:
    messagebox.showerror(tab.name, err)
    return          # <-- RETURN, nie CONTINUE
```

`get_lines()` zwraca wiersze z `on=True`, także puste. `validate_lines()`
wywala się na `t == ""`. Efekt: **procedura nie rusza dla ŻADNEJ mapy**,
a zaległość zostaje i przy kolejnej turze powtarza błąd.

Źródło: `add_line()` tworzy wiersz przez `_add_row(time_val, cmd_val, True)` —
**nowy wiersz rodzi się zaznaczony i pusty**, więc każda świeżo dodana mapa
jest miną do momentu skonfigurowania.

**Decyzja użytkownika: zaznaczony pusty wiersz ma być pomijany.**

### K5 ★★ MANAGER KASUJE LOG, REFRESHER MOŻE ZABIĆ START SERWERA

Już zabliźnione: `open_log_shared` otwiera z `FILE_SHARE_READ|WRITE|DELETE`,
bo manager kasuje log przy restarcie, a zwykły `open()` blokuje plik
i **przerywa start serwera**.

Najlepszy dowód, jak blisko siebie te trzy programy chodzą. Nie wolno tego
„uprościć" przy refaktorze.

### K6 ★★ PORT RCON JAKO TOŻSAMOŚĆ PROCESU

Refresher rozpoznaje proces mapy po porcie RCON:
`netstat -ano` → port nasłuchujący → PID (`_pid_map` / `_netstat_map`).
Działa, dopóki porty są unikalne.

**Valguero ma skonfigurowany RCONPort 27021 — ten sam co Extinction.**
Dziś Valguero stoi. W dniu uruchomienia refresher przypisze jeden PID dwóm
mapom i PAD-y zaczną kłamać.

**Do zrobienia: kontrola unikalności portów przy starcie, głośne ostrzeżenie.**

### K7 ★★ REFRESHER NIE WIDZI POBIERANIA

Program wypatruje w logu dosłownego napisu `Downloading mod`
(`ServerTab`, ustawia `_dl_last`; alarm `DL_STUCK` po 20 min).

Sprawdzone w logu z 17.09, gdzie **trzy mody naprawdę się ściągały**:

```
grep -ci "downloading mod" ShooterGame.log                → 0
grep -ci "downloading mod" game_83374_2026.09.17-....log  → 0
```

Prawdziwe brzmienie:

```
LogCFCore: Request to Install mod 'Awesome ARK Tools' (modId=941450, fileId=8828067)
LogCFCore: Starting download - 1 parts for https://mediafilez.forgecdn.net/...
```

**Alarm o utkniętym pobieraniu najprawdopodobniej nigdy nie zadziałał.**
(Zastrzeżenie: dostępne były dwa logi; potwierdzić przy następnym realnym
pobieraniu.)

Skutek: w oknie, w którym dysk pracuje najciężej, refresher jest ślepy.

### K8 ★★ TRZY MAPY, JEDEN DYSK

Główny powód rozjazdu restartów, w słowach użytkownika: **żeby restarty nie
zajechały SSD**.

Serwer pobiera z `maxConcurrentInstallations: 3`, rozpakowuje do `.temp/`,
weryfikuje hash, przenosi. Przy update'cie moda bazowego na trzech mapach to
trzy takie operacje plus trzy ładowania świata na jednym Samsungu 980.

Refresher tego **nie mierzy**, bo nie widzi pobierania (K7).

### K1 / K10 ★ REFRESHER ŚLEDZI NIE TEN PLIK

Jedno wydanie moda = kilka plików na CurseForge. Serwer instaluje wersję
`-windowsserver`. Refresher bierze `max(id)` z `latestFiles` publicznego API
i dostaje **rodzeństwo** tego pliku. Różnica: **dokładnie +3, dla wszystkich
10 modów**.

| Mod | API CF | Katalog na dysku |
|---|---|---|
| Shiny! Dinos Ascended | 7005630 | `928548_7005633` |
| Super Spyglass Plus | 8160170 | `929420_8160173` |
| No Untameables | 8510254 | `929684_8510257` |
| Crafting Skill Potion | 6562319 | `929785_6562322` |
| Arkitect Structures | 8636499 | `931874_8636502` |
| Super Cryo Storage | 8482339 | `933099_8482342` |
| Cybers Structures QoL+ | 8837558 | `940975_8837561` |
| Awesome ARK Tools | 8828064 | `941450_8828067` |
| Runic Wyverns | 8474000 | `974884_8474003` |
| Better Horde Mode | 7737973 | `1163881_7737976` |

Dowód w `library.json`:

```json
"filename":    "shiny dinos ascended-windowsserver 101.zip",
"downloadUrl": ".../files/7005/633/shiny dinos ascended-windowsserver 101.zip"
```

To **regularność, nie przypadek** — stała szerokość paczki plików wydania.
Wykrywanie działa, bo między wydaniami numery CF rozjeżdżają się o tysiące.
Ale numer w okienku „Known/Latest" i numer w katalogu **nigdy nie będą równe**.

### K2 ★ SERWER MA GOTOWĄ ODPOWIEDŹ, KTÓREJ NIKT NIE CZYTA

`ShooterGame/Binaries/Win64/ShooterGame/ModsUserData/83374/library.json` —
własny rejestr CFCore, pola `installedFile`, `latestUpdatedFile`, `pathOnDisk`,
`dateUpdated`, `users: ["local"]`.

Autorytatywna odpowiedź na pytanie „co jest zainstalowane", leżąca na dysku,
nietknięta przez refreshera.

---

## 3. STAN ZADANIA 2 — „wersje modów na CF i na serwerach"

Strona **CF** jest zrobiona solidnie: batch POST, chunki po 50, event sourcing
przez `known_versions`, godzenie wersji (3.41).

Strona **na serwerach** jest zrobiona w połowie:

```python
# _loaded_mods_from_log — z pary "mod (wersja)" bierze TYLKO pierwszą liczbę
for token in line.split(","):
    m = re.search(r"\d{6,12}", token)   # = mod ID; WERSJA WYRZUCONA
```

To była świadoma poprawka 3.58 (program liczył 9 modów jako 18). Skutek uboczny:
**log mówi programowi tylko KTÓRE mody, nigdy KTÓRA wersja.**

Wersje biorą się więc z dwóch innych źródeł:
- API CurseForge → `known_versions`
- katalog na dysku → `_installed_file_ids` → `installed_max`, `_verify_local_mods`

A w logu leży to, czego program szuka gdzie indziej:

```
Mod: Cybers Structures QoL+ (940975) requires upgrade/downgrade (8673705 -> 8837561)
Successfully installed mod 'Awesome ARK Tools' (modId=941450, fileId=8828067)
```

Numer, kierunek zmiany, potwierdzenie instalacji — wprost.

**Filar „log serwera = prawda o modach" jest dziś prawdziwy tylko w połowie.**

---

## 4. ZASADY WSPÓŁPRACY COMBO (wnioski)

1. **Jedna władza nad restartami.** Albo manager, albo refresher. Jeśli obaj,
   refresher musi znać okno restartowe managera i odmawiać startu procedury
   w tym oknie.
2. **Refresher nigdy nie blokuje plików serwera.** Tylko odczyt współdzielony.
3. **Refresher nigdy nie zabija procesów.** Wyłącznie `DoExit`.
4. **Wszystko, co dotyka procesów, robi się PO 25 s** od ich startu, żeby nie
   ścigać się z managerem.
5. **Tożsamość mapy nie może zależeć od portu**, dopóki unikalność portów nie
   jest wymuszona i sprawdzona.
6. **Jedna źle skonfigurowana mapa nie może zatrzymać klastra.**
7. **Aksjomat akceleratora:** update wejdzie i tak przy najbliższym starcie
   serwera. Refresher tylko przyspiesza. Dlatego **każde pominięcie jest
   bezpieczne** — nic nie ginie, wszystko się co najwyżej przesuwa. To
   licencjonuje wszystkie guardy i parkowania w kodzie. Nie dopisywać retry
   tam, gdzie kod świadomie odpuszcza.

---

## 5. PROPOZYCJA ROZBICIA

Podział idzie po **zadaniach zdefiniowanych przez użytkownika**, nie po
warstwach technicznych:

> 1. skutecznie monitorować aktualny stan serwerów
> 2. kontrolować wersje modów na CF i na serwerach
> 3. zarządzać procedurą zaprogramowaną w czasie liniami RCON

### Rdzeń — wyłącznie host

| Co | Linii ~ |
|---|---|
| okno, tik 500 ms, `post_ui` / `run_async`, dziennik przez kolejkę | |
| trwałość: `save_versioned`, `newest_matching`, `write_json_atomic`, rotacja 10 | |
| **tab = mapa** (`ServerTab`) — to model danych, nie funkcja | |
| ładowarka pluginów, szyna zdarzeń, scalanie słowników TR | |
| **razem** | **~900** |

### Pluginy konieczne

| # | Plugin | Zadanie | Linii ~ |
|---|---|---|---|
| 10 | `logtail` | czyta `ShooterGame.log`, wystawia status mapy | 230 |
| 20 | `monitor` | **zadanie 1** — procesy, porty, PAD, WISI, sondy RCON | 190 |
| 30 | `cf-wersje` | **zadanie 2a** — wersje na CurseForge | 485 |
| 40 | `serwer-wersje` | **zadanie 2b** — wersje NA SERWERACH | ~150 |
| 50 | `procedura` | **zadanie 3** — linie RCON, rozjazd, czuwanie | 305 |
| 60 | `cpu` | priorytet i powinowactwo procesów | ~60 |
| 70 | `mody-okno` | okno kafelków modów | ~200 |

### Moduły (biblioteki — bez stanu, bez haków, nie pluginy)

`tr.py` 551 · `widgety.py` 313 · `siec.py` (RCON + HTTP do CF) 160 ·
`zapis.py` 185

### Dlaczego tak

- **Każdy klocek mieści się w głowie agenta.** Największy to 485 linii.
  Dziś najmniejsza sensowna jednostka to 4530.
- **Nazwy klocków = zadania użytkownika.** Agent dostający `50_procedura.py`
  wie, że to „zadanie 3", i nie musi rozumieć CurseForge.
- **Plugin 40 to miejsce, gdzie leży prawdziwa robota.** Rozdzielenie zadania 2
  na dwie strony odsłania, że druga jest zrobiona w połowie. Kolizje K1, K7,
  K10 i K2 siedzą w tym jednym klocku.
- **Plugin 60 to trzydzieści linijek logiki**, bo PID-y dostaje od pluginu 20.

### Kontrakt pluginu (minimalny)

```python
class Wtyczka:
    nazwa = "cpu"
    API   = 1                      # rdzeń odmawia innej wersji
    TR    = {"pl": {...}, "en": {...}}   # doklejane do TR rdzenia

    def start(self, rdzen):        ...  # raz, po zbudowaniu UI
    def tik(self, teraz):          ...  # co 500 ms, wątek UI, MUSI być krótkie
    def dane_monitora(self, dane): ...  # co 10 s: {"pid": {port: pid}, "wiek": {...}}
    def panel(self, rodzic):       ...  # ramka Tk albo None
    def konfiguracja(self):        ...  # dict → save_versioned
    def stop(self):                ...
```

Rdzeń udostępnia: `log`, `tr`, `post_ui`, `run_async`, `taby` (**snapshot,
tylko do odczytu**), `zapisz_config(nazwa, dict)`, `zdarzenie(...)` /
`nasluchuj(...)`.

Zasady twarde:
- każde wywołanie pluginu w `try/except` + wpis do dziennika (plugin rzucający
  w `tik` zasypałby konsolę dwa razy na sekundę),
- ładowanie alfabetyczne z katalogu `PLUGINY/`, `importlib`, **zero**
  rozwiązywania zależności — przedrostki liczbowe wyznaczają kolejność,
- plugin nie zapisuje do `self.tabs` — tylko przez metody rdzenia.

### Kolejność robót

| Krok | Co | Linii | Ryzyko | Potrzebuje testów? |
|---|---|---|---|---|
| 1 | `tr.py` — czyste dane | 551 | zerowe | nie |
| 2 | `widgety.py` | 313 | zerowe | nie |
| 3 | `siec.py` + `zapis.py` | 345 | zerowe | nie |
| 4 | host pluginów (ładowarka + kontrakt + 3 haki) | ~120 | małe | lekkie |
| 5 | `60_cpu` — pierwszy plugin, nowy kod | ~60 | małe | lekkie |
| 6+ | wycinanie 10 / 20 / 30 / 40 / 50 / 70 | — | rośnie | **tak** |

**Kroki 1–3 zdejmują 1209 linii (27% pliku) bez zmiany choćby jednej linii
logiki.** Nie potrzebują ani kontraktu pluginu, ani floty testowej.

Flota testowa (`symulacja/`, 39 jednostkowych + sterownik 62/62 + debug23–27)
jest niezbędna od kroku 6. **Nie ma jej ani w repozytorium GitHub, ani
w `C:\AAA`.**

---

## 6. BLIZNY — czego NIE WOLNO „uprościć"

Sekcja 4a w `PROMPT-ASAonly-AWARYJNY.md`. Każda z tych rzeczy wygląda przy
refaktorze jak bałagan do posprzątania, a jest zabliźnioną raną:

| Wygląda na | Naprawdę jest | Usuniesz → wraca |
|---|---|---|
| dziwne otwieranie logu | `FILE_SHARE_DELETE` — manager kasuje log | `open()` blokuje plik i **przerywa start serwera** |
| magiczne 2 MB | skan ogona logu od tyłu, logi ważą GB | sekundy zwłoki albo brak stanu mapy |
| 15 s „łaski" | okno na rotację logu | status skacze na OFFLINE przy każdym restarcie |
| osobna kolejka RCON na mapę | world save ignoruje RCON 5–10 s | jedna wisząca mapa **blokuje komendy pozostałych i GUI** |
| `next_check` przesuwany zawsze | lekcja 3.41 | 11 zapytań do CF w 7 sekund |
| retry RCON 3× co 2 s | harmonogram wobec graczy nie może się rozjechać | ogłoszenia rozjeżdżają się z `DoExit` |
| stan per-tab w konstruktorze | taby rodzą się też po starcie (EN/PL, import) | crash monitora, lekcja 3.71.1 |
| geometria Tk w jedną stronę | 7 nieudanych iteracji kafelków (3.27–3.39) | ucięte kafelki wracają |

---

## 7. OTWARTE DECYZJE

1. **K4 — kto jest jedyną władzą nad restartami?** Manager czy refresher?
   Jeśli obaj, refresher musi czytać okno restartowe managera.
   *To decyzja projektowa, nie kod.*
2. **`continue` zamiast `return`** w `_exec_pending` — czy jedna źle
   skonfigurowana mapa ma przestać blokować pozostałe? *Jedna linijka.*
3. **Gdzie jest `symulacja/`?** Bez floty kroki 6+ są ślepe.

## 8. DO POPRAWKI W DOKUMENTACJI

Sześć miejsc przypisuje pobieranie modów managerowi zamiast serwerowi —
i to są pliki, które czyta każdy nowy agent:

- `PROMPT-ASAonly-AWARYJNY.md` sekcja 1, sekcja 8.1, **PTK 10 w sekcji 4a**
- `MANUAL` sekcja 0 (nawias dotyczy restartu, ale przykleja się do instalacji)
- `MANUAL` sekcja 8, filar 6 („to robi ASM/serwer")
- `README.md` („zostawia serwer (ASM)")

Do dopisania w sekcji 4a: **dlaczego mody wchodzą tylko przy starcie**
(trzy dowody z rozdziału 0) i **skąd bierze się +3** (`-windowsserver`).
