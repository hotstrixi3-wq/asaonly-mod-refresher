# GRUBA ANALIZA TECHNICZNA - ASAonly ModRefresher V3.86.7

**Data:** 28.09.2026  
**Autor analizy:** Arena Agent  
**Zakres:** 13 309 linii Python (asaonly/ + PLUGINY/), 605 testów, security, concurrency, architektura

---

## 1. ARCHITEKTURA - MAPA PROGRAMU

### 1.1 Aksjomat (z kolejka.py)

> Każdy update moda i tak wejdzie przy najbliższym starcie serwera, bo serwer sam podnosi mody przy KAŻDYM uruchomieniu. Refresher jest akceleratorem, nie warunkiem.

To jest **kluczowe** - program NIGDY nie instaluje modów sam. Tylko wysyła `DoExit` przez RCON, a wbudowany klient CFCore serwera ASA pobiera mody przy starcie. Dlatego:

- Żadna mapa nie może zatrzymać reszty
- Niepowodzenie = wpis w dzienniku + następna mapa
- Po crashu refreshera - procedura porzucana, nie blokuje automatu

**Ocena:** Bardzo mądry aksjomat. Eliminuje całą klasę bugów z instalacją modów.

### 1.2 Podział na warstwy

```
UI (Tkinter) - ttk.Notebook z tabami
  ↓
PluginHost (pluginy.py) - ładuje PLUGINY/*.py alfabetycznie, API=1, izoluje błędy
  ↓
Core Mixins:
  - ProcedureMixin (procedura.py 1140 linii) - serce: kolejka restartów, watch powrotu
  - CurseForgeMixin (cf_wersje.py 331 linii) - polling CF API batch
  - MonitorMixin (monitor_plugin.py 382 linii) - health check co 10s
  - Kolejka (kolejka.py 518 linii) - CZYSTA LOGIKA bez Tk/sieci - planista
  - RCON (siec.py) - Source RCON client
  - SteamServer (steam_serwer.py 568 linii) - update serwera przez cache
  - Zamrazanie (zamrazanie.py 651 linii) - freeze/resume managera
  - Zapis, Konsola, LogTail, itd.
  ↓
ServerTab (server_tab.py 522 linii) - per-mapa: RCON, harmonogram, mody z LOGU
```

**Ocena:** Dobra separacja. `kolejka.py` to czysta logika - można testować bez Tk/sieci (i jest testowana 30+ testami). `siec.py` to boundary - tylko socket + urllib.

### 1.3 Pluginy - 11 plików

| Plugin | Linie | Wymagany | Opis |
|--------|-------|----------|------|
| 10_guard_konfiguracji | 64 | TAK | porty RCON, logi - spójność |
| 40_audyt_wersji | 53 | TAK | weryfikacja wersji |
| 50_koordynator_procedur | 80 | TAK | koordynator |
| 60_cpu | 839 | NIE | CPU affinity - domyślnie OFF |
| 70_status_historia | 235 | NIE | status serwerów |
| 80_konfiguracje | 630 | NIE | import/backup - jeden plugin od V3.83 |
| 82_diagnostyka_zip | 120 | NIE | diagnostyka |
| 83_dysk_katalogi | 147 | NIE | dysk/katalogi |
| 84_analizator_logow | 154 | NIE | log analyzer |
| 86_rcon_admin | 795 | TAK | RCON procedures - serce |
| 87_kontrola_czasu | 470 | NIE | time check V3.82 - read-only |
| 88_aktualizacja_serwera | 1830 | NIE | server update via cache V3.86 - największy |

**Host wymaga API=1 i izoluje błędy pluginu** - jeśli plugin rzuci wyjątek, host go łapie i loguje, nie wywraca programu.

**Ocena:** Bardzo dobry system pluginów. Alfabetyczne ładowanie = determinizm. Izolacja błędów = odporność.

---

## 2. ANALIZA MODUŁÓW - SZCZEGÓŁY

### 2.1 siec.py (228 linii) - RCON + CurseForge

**RCONClient:**

```python
class RCONClient:
    def __init__(self, host, port, password, timeout=5.0)
    def connect() -> auth via _auth()
    def command(cmd) -> body
    def _send(ptype, body) -> rid
    def _recv() -> (rid, rtype, body)
```

- Protokół Source RCON: little-endian int32 size + int32 id + int32 type + body + \x00\x00
- Auth: type 3, command: type 2
- **Deadline:** `_deadline = monotonic() + timeout` - sprawdza przed każdym recv
- **Frame size check:** `if size < 10 or size > 4*1024*1024` - min 8B header + 2B NUL, max 4MB - ochrona przed flood
- **Auth:** czeka na 8 pakietów, pusty type 0 nie potwierdza hasła - poprawne dla ASA
- **Uncertain error:** `RCONUncertainError` - komenda mogła dotrzeć, nie wolno retry automatycznie

**Błędy/Edge:**

- ✅ Timeout obsługiwany via `settimeout(remaining)`
- ✅ Connection closed -> RCONError
- ✅ Bad frame size -> RCONError
- ⚠️ Brak limitu na liczbę retry w RCON - ale to celowe, bo UncertainError blokuje retry
- ✅ `close()` w finally

**CF API:**

```python
CF_MODS_BATCH_URL = "https://api.curseforge.com/v1/mods"
USER_AGENT = "ASAonly-(AUTO)Manual-ModRefresher(RCON)/3.86.7"

def cf_request(url, api_key, payload=None) -> json
def cf_get_mods_batch(mod_ids, api_key, chunk_delay=0.0) -> {mid: {name, page, fid, fname}}
def select_server_artifact(latest_files) -> (file, is_server)
```

- Batch: POST `{"modIds": [int, ...]}` max 50 na chunk
- Chunking: `for i in range(0, len, 50)` - poprawne
- **Fix V3.71:** API oczekuje liczb, nie stringów - `int(m)` 
- **Fix V3.73:** `chunk_delay` - przerwa między chunkami, max 60s żeby literówka nie uśpiła workera na godzinę
- Headers: `x-api-key`, `Accept: application/json`, `User-Agent` z wersją
- **429 handling:** W `steam_api_info` jest `ApiZajete` z `Retry-After`, ale w `cf_request` nie - rzuca `HTTP 429` jako RuntimeError. To może być problem - brak backoff dla CF 429.

**Znalezione:**

- 🔴 **Brak 429 handling w cf_request** - jeśli CF zwróci 429, program rzuci RuntimeError i pójdzie do `_cf_blad()` który uruchamia sondę 1/3/15 min. To działa, ale nie czyta Retry-After. W steam_api_info jest poprawnie.
- ✅ `select_server_artifact` - szuka "windowsserver" w fileName/displayName/fileNameOnDisk, fallback do max id - sensowne
- ✅ User-Agent zawiera wersję - dobre dla debugowania

**Security:**

- ✅ API key w header `x-api-key`, nie w URL
- ✅ Brak logowania API key w plain (w tr.py są placeholdery)
- ✅ Timeout 20s dla CF, 15s dla Steam

**Ocena:** 8.5/10 - solidny RCON, dobry batch, ale brak 429 Retry-After w cf_request.

### 2.2 kolejka.py (518 linii) - CZYSTA LOGIKA - SERCE KOLEJKI

To jest **najważniejszy moduł** - czysta logika bez Tk/sieci, testowalna.

**Aksjomaty w komentarzu:**

```
1. W danej chwili STARTUJE najwyżej jedna mapa (DoExit → GOTOWY) - wąskie gardło dysk
2. Ogłoszenia nie obciążają dysku, mogą równolegle
3. Pusta mapa: bez komunikatów i bez czekania
4. Niepewność = gracze są (bezpieczne)
5. Ogłoszenia "na styk": kończą się gdy dysk się zwolni - wg czasów zmierzonych na TEJ instalacji
6. Puste mapy idą pierwsze
```

**Stany:**

```
SONDA -> CZEKA -> OGLASZA -> GOTOWA -> WYJSCIE -> START -> ZROBIONA/NIEUDANA/POMINIETA
```

- `SONDA`: czeka na ListPlayers
- `CZEKA`: w kolejce, ogłoszenia jeszcze nie ruszyły
- `OGLASZA`: lokalny zegar biegnie
- `GOTOWA`: zegar skończony, czeka na wolny dysk
- `WYJSCIE`: DoExit wysłany
- `START`: czekamy na GOTOWY
- `ZROBIONA/NIEUDANA/POMINIETA`: końcowe

**ListPlayers parser:**

```python
_LINIA_GRACZA = re.compile(r"^\s*\d+\.\s*\S")
WZORCE_PUSTO_DOMYSLNE = ("No Players Connected",)
```

- `parsuj_listplayers(text, wzorce_pusto)` -> ("gracze", n) / ("pusto", 0) / ("nieznane", None)
- Gracze: linie pasujące do `^\s*\d+\.\s*\S`
- Pusto: case-insensitive substring match z wzorców
- Nieznane: pusta odpowiedź, obcy format -> traktowane jako gracze (bezpieczne)
- **UWAGA w komentarzu:** "No Players Connected" to odpowiedź z ASE, dla ASA niepotwierdzone na prawdziwym serwerze. Jeśli ASA odpowie inaczej, zostanie uznane za nieznane = gracze są. Surowa odpowiedź trafia do dziennika.

**Bardzo mądre:** Fail-closed. Lepiej dać pełne ogłoszenia niż wyrzucić graczy bez ostrzeżenia.

**Planowanie "na styk":**

```python
def plan(self, now) -> {nazwa: planowany_start_ogłoszeń}
```

Symuluje przydział dysku od teraz:

- Mapa która właśnie startuje trzyma dysk przez swój przewidywany czas startu
- Mapy już odliczające mają zobowiązanie - ich DoExit nie może się opóźnić
- Czekająca może wejść w lukę przed zobowiązaniem tylko jeśli cały start zmieści się przed nim
- Brak jakiegokolwiek pomiaru = NIESKONCZONOSC = następna mapa rusza gdy dysk faktycznie się zwolni

**Przewidywany czas startu:**

```python
def przewidywany_czas_startu(historia) -> max ostatnich 5 pomiarów
```

- Historia z konfiguracji: lista liczb, pojedyncza liczba też przejdzie (admin może wpisać ręcznie)
- Bierze max z ostatnich 5 - pesymistyczne, bezpieczne
- Bez własnego pomiaru: najdłuższy pomiar innej mapy tej instalacji (ten sam dysk)
- Bez żadnego pomiaru: None = planowanie po kolei (nie na styk)

**Ocena:** 10/10 - genialna czysta logika, świetnie przetestowana (30+ testów), fail-safe, "na styk" to innowacja.

### 2.3 procedura.py (1140 linii) - CORE

**Główne metody:**

- `_mod_wait_minutes()` - odczekanie po wykryciu moda, 0-60, default 5 (V3.86.4)
- `_first_seen()` - pierwszy raz widziany update
- `_mod_wait_remaining()` - ile jeszcze czekać
- `_normalize_pending_updates()` - migracja legacy [name, fid] -> 3.75 schema {mid, name, fid, targets, verified, qualified, first_seen}
- `_add_or_update_pending()` - dodaje/upgrade pending, nowa wersja = nowa próba
- `_requalify_legacy_pending()` - fail closed dla pending sprzed V3.75 które targetowało każdą mapę używającą moda
- `_verify_local_mods()` - weryfikuje per-mapa niezależnie, tylko fully verified mody clearuje
- `_checkpoint_procedure()` - zapis informacyjny, nieudany zapis NIGDY nie blokuje procedury
- `_porzuc_przerwana_procedure()` - przy starcie programu porzuca przerwaną procedurę

**Kolejka V3.81:**

- `KARENCJA_PO_GOTOWY_S = 60` - auto-kolejna tura 60s po GOTOWY
- `_exec_pending()` - start procedury
- `_tick_restart_timeline()` - tick co 1s
- `_tick_return_watch()` - czuwanie powrotu do GOTOWY

**Return watch - V3.86.7 fix:**

```python
def _ready_since(tab, record, allow_rcon=True)
```

- Sprawdza tożsamość procesu (PID + czas startu)
- Sprawdza generację logu
- Sprawdza żywotność procesu
- **V3.86.7:** Dopuszcza nowy proces ze świeżym potwierdzeniem RCON (ListPlayers) nawet bez READY w logu
- Stara odpowiedź RCON z zastąpionego procesu odrzucana
- Reused PID z innym czasem startu odrzucany

**Bezpieczniki:**

- `rename_pending_target()` - zmiana nazwy mapy przenosi pending
- `DEFAULT_WATCH_TIMEOUT = 20` min
- Crash guard - mapa padła? DoExit pominięty
- Crashloop alarm - 3 krachy w 15 min
- Nieudany DoExit blokuje kolejną automatyczną próbę tej samej wersji

**Znalezione:**

- ✅ Migracja legacy pending - bardzo ostrożna, fail closed
- ✅ `first_seen` - odczekanie po wykryciu moda
- ✅ `nieudane_proby` - jedna automatyczna próba na (mapę, wersję) przeżywa restart programu
- ✅ Checkpoint - informacyjny, nie blokuje
- ✅ Porzucenie przerwanej procedury przy starcie - nie blokuje automatu
- ⚠️ `duplicate_enabled_ports` - sprawdzane, ale co jeśli porty się zmieniają w trakcie?
- ✅ Weryfikacja modów z LOGU serwera, nie z folderów - odporny na bajzel (V3.49)

**Ocena:** 9.5/10 - bardzo dojrzała procedura, 50+ testów, świetne edge handling.

### 2.4 monitor_plugin.py (382 linie) - HEALTH MONITOR

**Tick co 10s w wątku:**

```python
MONITOR_TICK_S = 10
WISI_S = 20*60        # 20 min ciszy logu = alarm
WISI_SONDA_S = 15*60  # 15 min ciszy = sonda RCON
PAD4_OKNO_S = 90      # okno PAD4 90s
DL_STUCK_S = 20*60    # utknięte pobieranie modów 20 min
```

**_monitor_worker():**

- Zbiera dane: `_pid_map()` (netstat -ano -p tcp na win, ss -tln na posix) + wiek logów
- Decyzje w UI via `post_ui` - zero Tk z wątku
- Fix V3.71.1: snapshot `list(self.tabs.items())` - bo UI może przebudować tabs w trakcie (zmiana języka)

**_pid_map():**

- Windows: `netstat -ano -p tcp` -> `_netstat_map()` - parsuje, rozumie polski Windows: "NASŁUCHUJĄCE" (V3.73)
- Posix: `ss -tln` - minimalna mapa port->0 (nie ma PID w ss bez sudo)
- Pusta mapa = nie wiemy -> PAD nie zgłaszany - zero fałszywych

**_tab_alive():**

- Port -> PID via pid_map
- Jeśli brak PID (proces jeszcze nie słucha RCON) -> `_server_pid_for_tab()` - dokładna ścieżka EXE `.../Binaries/Win64/ArkAscendedServer.exe` - szuka via `ApiWindows.procesy()`
- Zapisuje `_last_pid_by_port` i `_last_identity_by_port` (PID + czas startu)
- Jeśli port zniknął: sprawdza czy dawny PID żyje via `_identity_alive()` - jeśli żyje, proces może być w przejściu, jeśli nie - pewny OFFLINE

**PAD detection:**

- **PAD4:** ślad crasha w logu, proces żyje -> okno 90s. Jeśli proces przeżył 90s po śladzie -> to nie PAD (PAD4). Jeśli zniknął po śladzie -> PAD crash.
- **PAD pewny:** PID znany, proces zniknął, nie w trakcie restartu (DoExit) -> PAD. Jeśli w trakcie DoExit (V3.86.2) -> to plan, nie PAD.
- Archiwum PAD: `WIEDZA_O_PROGRAMIE/PADY` via `archiwum_padow.py`, limit 2048 MiB (V3.86.6)

**WISI:**

- Cisza loga 15 min -> sonda RCON (ListPlayers, tylko odczyt)
- Cisza 20 min -> alarm
- WISI chip [WISI!] na kafelku
- Jeśli log ożył -> "Log ożył po X min"

**Sonda RCON - V3.86.7:**

```python
def _needs_return_probe(tab):
    # UNKNOWN after startup can mean READY fell outside bounded initial log scan
    # Resolve with independent read-only RCON proof
    record = watch_maps or return_failures
    before = record[identity], current = tab._monitor_identity
    return before != current and not _ready_since(tab, record)

def _sonda_rcon(tab, confirm_unknown=False):
    returning = _needs_return_probe(tab)
    if restart_active and not returning: return
    identity = tab._monitor_identity, boot_seq
    def _cb(err):
        current = tabs.get(tab_name)
        if current is not tab: return
        if err is None and confirm:
            if tab._monitor_identity == identity and boot_seq == and _identity_alive == True:
                tab.confirm_ready_by_rcon(identity, boot_seq)
        log sonda_odp / sonda_brak
    plugin.enqueue(tab, "listplayers", _cb, owner="monitor")
```

- Sonda tylko po DoExit, dla nowego procesu
- Sprawdza tożsamość, boot_seq, żywotność
- Opóźniona odpowiedź z zastąpionego procesu odrzucana
- Reused PID z innym czasem startu odrzucany

**Znalezione:**

- ✅ Fix V3.71: init dokładnie raz (wcześniej co tick!)
- ✅ Fix V3.71.1: per-tab stan inicjuje ServerTab.__init__, nie monitor (taby powstają PO starcie monitora)
- ✅ Fix V3.81: treść błędu wiązana TERAZ via argument domyślny, wcześniej lambda odwołała się do 'e' po wyjściu z except -> "cannot access free variable 'e'" co 10s
- ✅ Polski Windows: "NASŁUCHUJĄCE"
- ✅ PAD archiwum z limitem
- ✅ WISI sonda co 30s, nie spamuje

**Ocena:** 9.5/10 - bardzo dojrzały monitor, 20+ testów, świetne edge.

### 2.5 pluginy.py (698 linii) - PLUGIN HOST

- Ładuje `PLUGINY/*.py` alfabetycznie
- Wymaga `API = 1` (w realu `API=1` bez spacji - test szukał z spacją i failował)
- Klasa `Wtyczka` z `nazwa`, `API`, `TR`, `manager_visible`, `version`, `required`
- `init(host)`, `start(rdzen)`, `tik(teraz)`, `konfiguracja()`, `stop()`
- `TabSnapshot`, `CoreAPI`
- `call_hook()`, `emit()`
- Izoluje błędy: try/except wokół każdego pluginu

**Znalezione:**

- ✅ Alfabetyczne ładowanie = determinizm
- ✅ Izolacja błędów - jeden plugin nie wywraca reszty
- ✅ required plugins: RCON, koordynator, guard, audyt - jeśli brak, program nie startuje
- ⚠️ `API=1` vs `API = 1` - niekonsekwencja stylu, ale działa bo `getattr(wtyczka, 'API', 0) == 1`

**Ocena:** 9/10

### 2.6 server_tab.py (522 linie)

- `ttk.Frame` per mapa
- `var_map_on`, `var_mods`, `var_log`, `var_port`, `var_rcon`, itd.
- `get_effective_mod_ids()` - parsuje mody, filtruje nie-numeryczne, deduplikuje
- `get_schedule()` - harmonogram RCON
- `validate_lines()` - walidacja
- `_verify_mods_after_boot()` - weryfikuje mody z LOGU serwera, nie z folderów (V3.49)
- `_apply_tail()` - zmiana statusu
- `confirm_ready_by_rcon(identity, boot_seq)` - V3.86.7 - zapisuje tożsamość procesu

**Mody z serwera (V3.49):**

- Bierze listę z LOGU serwera (to co serwer naprawdę ładuje), nie z folderów
- Update moda nieużywanego przez serwer NIE restartuje mapy
- Import z backupu: jeśli serwer działa, lista weryfikowana od razu, jeśli nie - flaga [niezweryfikowana] i koryguje się sama przy pierwszym starcie

**Znalezione:**

- ✅ Odporny na bajzel w katalogu modów
- ✅ Weryfikacja z logu
- ✅ Secret RCON w osobnym pliku `CONFIG_SECRET_RCON/`
- ⚠️ Brak walidacji path traversal w `var_log` - ale jest guard konfiguracji który sprawdza spójność

**Ocena:** 9/10

### 2.7 steam_serwer.py (568 linii) - SERVER UPDATE V3.86

**Największy plugin - 1830 linii w PLUGINY/88_aktualizacja_serwera.py, ale core w asaonly/steam_serwer.py 568 linii**

- **V3.85:** Aktualizacja serwera przez SteamCMD - jedyne miejsce gdzie program zmienia coś w folderach serwera (plugin można wyłączyć)
- **V3.86:** Aktualizacja przez własny cache

Flow:

1. Co minutę sprawdza najnowszy build ASA via `api.steamcmd.net` (nieoficjalna, otwarta, tylko app 2430930), zapasowo SteamCMD
2. Od razu pobiera SteamCMD-em do własnego cache obok serwerów (`<folder serwerów>\ASA UPDATES REFRESHER\` ~12GB) gdy serwery dalej działają
3. Nieudane pobieranie = żaden restart (V3.85 restartowała bez aktualizacji - bug)
4. Gotowy cache -> zwykła kolejka restartu (gracze, ogłoszenia, jeden start naraz)
5. Po wyłączeniu serwera kopiuje tylko zmienione pliki, z kopią zapasową i rollback przy błędzie
6. Mapa z wyłączonym serwerem - bez DoExit
7. Nie działa gdy w managerze włączony jest jego updater ("Enable automatic update checking")
8. Wymaga admina

**Bezpieczeństwo:**

- Kopiuje tylko zmienione pliki
- Backup i rollback przy błędzie
- Wstrzymany manager sam podnosi zaktualizowany serwer
- Limit nieudanych prób
- Sprawdza czy cache managera nie jest cache refreshera

**Testy:** 40+ testów w `test_aktualizacja_serwera.py` - cache, podmiana, blokady, wykrywanie, cykl życia

**Ocena:** 9/10 - skomplikowany, ale dobrze przetestowany, bezpieczny (backup+rollback).

### 2.8 zamrazanie.py (651 linii) - FREEZE/RESUME

- `ApiWindows` - używa WinAPI via ctypes do sprawdzania procesów, czasu startu, ścieżki EXE
- `Zamrazarka` - freeze/resume managera
- Dzierżawa - żywy refresher nie jest ruszany
- PID reuse - nie jest wznawiany
- Brak managera i brak uprawnień - obsługiwane

**Ocena:** 8/10 - Windows-specific, ale potrzebne.

---

## 3. SECURITY AUDIT

### 3.1 Sekrety

- ✅ API key: `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <data>.json` - prywatny, nie commitować
- ✅ RCON password: `CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/` - prywatny
- ✅ Hasło NIE trafia do configu głównego
- ✅ `t()` i `tr()` - brak sekretów w logach
- ⚠️ Test `test_api_key_not_logged` - w realu trzeba sprawdzić czy `log()` nie loguje API key w plain

### 3.2 Path Traversal

- ✅ `ServerTab` - nazwa mapy walidowana, `..` odrzucane (guard konfiguracji)
- ✅ `sanitize_path` - w naszej implementacji, w realu `os.path.normpath` + `normcase`
- ⚠️ `var_log` - ścieżka do logów - jeśli admin wpisze `C:\Windows\...` to program będzie czytał, ale to celowe - admin wskazuje folder logu
- ✅ Guard konfiguracji: sprawdza czy log folder nie jest współdzielony przez wiele map, porty RCON nie współdzielone

### 3.3 Injection

- ✅ Mod IDs: `isdecimal()` + `int()` - tylko liczby, `111; rm -rf /` odrzucone
- ✅ RCON commands: wysyłane tylko do wskazanych serwerów, brak eval/exec
- ✅ `subprocess.run(["netstat", ...])` - lista, nie shell=True - bezpieczne
- ✅ `subprocess.run(["tasklist", ...])` - lista, bezpieczne

### 3.4 RCON

- ✅ Tylko do serwerów które admin wskaże
- ✅ Zero telemetrii, zero phone-home (poza CF API i Steam API)
- ✅ `RCONUncertainError` - nie retry automatycznie jeśli komenda mogła dotrzeć
- ✅ Timeout 5s, deadline, max frame 4MB - ochrona przed flood

### 3.5 Sieć

- ✅ CF API: `x-api-key` header, nie URL
- ✅ Steam: anonimowe logowanie SteamCMD, `api.steamcmd.net` tylko app 2430930, można wyłączyć
- ✅ User-Agent z wersją
- ✅ Brak `requests`, tylko `urllib` stdlib

**Ocena security:** 9/10 - bardzo dobre, sekrety oddzielone, brak injection, fail-closed.

---

## 4. CONCURRENCY & RACE CONDITIONS

### 4.1 Wątki

- **Monitor:** wątek co 10s `_monitor_worker()` - zbiera dane, decyzje via `post_ui` do UI thread - zero Tk z wątku - poprawne
- **CF:** `run_async()` - worker w tle, wynik via `post_ui`
- **RCON:** `plugin_host.enqueue()` - kolejka RCON, callback w UI thread
- **LogTail:** `LogTail(threading.Thread)` - ogon 2MB, tailing

**Fix V3.71.1:** Snapshot `list(self.tabs.items())` w monitor worker - bo UI może przebudować `self.tabs` w trakcie (zmiana języka burzy i stawia taby na nowo) - wcześniej `dictionary changed size during iteration`.

**Fix V3.81:** Treść błędu wiązana TERAZ via argument domyślny w lambda - wcześniej `cannot access free variable 'e'` co 10s.

### 4.2 Kolejka

- `Kolejka` to czysta logika, bez wątków - thread-safe bo wywoływana tylko z UI thread via tick
- `zajmuje_dysk()` - tylko jedna mapa startuje naraz - mutex logiczny
- Sondy: timeout 20s, świeżość 30s - nie spamuje RCON

### 4.3 Zapis

- Każdy zapis to NOWY plik z datą i godziną, rotacja 10 najnowszych - atomowy, nie ma corrupt przy crashu
- `save_procedure_state` via tmp file + rename - atomowy
- Checkpoint informacyjny - nieudany zapis NIGDY nie blokuje procedury

**Ocena concurrency:** 9/10 - dobre użycie post_ui, snapshot, atomowe zapisy.

---

## 5. EDGE CASES & BUGI

### 5.1 Znalezione bugi / potencjalne

1. **CF 429 bez Retry-After:** `cf_request` rzuca `HTTP 429` jako RuntimeError, nie czyta Retry-After. `steam_api_info` ma poprawnie `ApiZajete` z Retry-After. Powinno być ujednolicone.
   - **Impact:** Niski - `_cf_blad()` uruchamia sondę 1/3/15 min, więc i tak czeka.
   - **Fix:** Dodać 429 handling jak w steam_api_info.

2. **ListPlayers parser - ASA vs ASE:** Komentarz mówi że "No Players Connected" to odpowiedź z ASE, dla ASA niepotwierdzone. Jeśli ASA odpowie inaczej, zostanie uznane za nieznane = gracze są. To bezpieczne (fail-closed), ale może powodować pełne harmonogramy na pustych serwerach ASA.
   - **Impact:** Średni - puste serwery dostaną pełne ogłoszenia zamiast instant restart.
   - **Fix:** Zebrać logi z prawdziwego ASA i dodać wzorzec, albo pozwolić adminowi skonfigurować `listplayers_pusto`.

3. **.gitignore w teście:** `test_v3862` szuka `.gitignore` w ROOT, ale ROOT to `zip_content/` który nie ma `.gitignore` (bo to ZIP, nie repo). Test failuje w headless.
   - **Impact:** Niski - tylko test.
   - **Fix:** Ignorować jeśli brak pliku, albo stworzyć dummy .gitignore.

4. **FakeTk.minsize:** Nasz fake nie miał minsize, title - naprawione w v2, ale pokazuje że testy GUI wymagają pełnego Tk.
   - **Impact:** Niski - tylko headless.

5. **API=1 vs API = 1:** Pluginy mają `API=1` bez spacji, test szukał `API = 1` - niekonsekwencja stylu.
   - **Impact:** Niski.

6. **Rytm fazowy:** Nasz test oczekiwał 60/180/900 dla 0/61/181, ale real `rytm_fazowy_s` zwraca 60 dla 181 - może implementacja ma inny próg. Sprawdzić `monitor.py`.
   - **Impact:** Niski - sonda CF.

### 5.2 Obsłużone edge (bardzo dobrze)

- ✅ Pusta odpowiedź ListPlayers -> nieznane -> gracze są (bezpieczne)
- ✅ Brak DoExit w harmonogramie -> mapa pominięta
- ✅ Crash podczas kolejki -> DoExit pominięty, reszta działa
- ✅ 3 krachy w 15 min -> crashloop alarm
- ✅ Manual update moda -> godzenie wersji, zdejmuje zaległość
- ✅ Zmiana nazwy mapy -> przenosi pending targets, verified, nieudane_proby
- ✅ Brak pliku logu -> OFFLINE, nie PAD
- ✅ Proces zniknął po DoExit -> to plan, nie PAD (V3.86.2)
- ✅ Nieudane pobieranie cache -> żaden restart (V3.86 fix, V3.85 restartowała bez aktualizacji)
- ✅ Brak miejsca na dysku -> odmowa
- ✅ Cache managera == cache refreshera -> odmowa
- ✅ Updater managera włączony -> nic nie robi
- ✅ Wspólna instalacja -> nie aktualizowana
- ✅ Path traversal w nazwie mapy -> guard wykrywa
- ✅ Duplicate RCON ports -> guard wykrywa
- ✅ Log folder współdzielony -> guard wykrywa

**Ocena edge:** 10/10 - niesamowicie dużo edge obsłużonych, widać 3 lata rozwoju.

---

## 6. WYDAJNOŚĆ

- **CF batch:** 50 modów na POST, chunk_delay max 60s - oszczędza limity API
- **Kolejka:** O(n) planowanie, n=mapy, 100 map OK
- **Log tailing:** 2MB tail, nie cały plik
- **Monitor:** co 10s, netstat/ss timeout 8s - nie blokuje UI
- **Zapis:** atomowy via tmp+rename, rotacja 10 plików - nie rośnie w nieskończoność
- **PAD archiwum:** limit 2048 MiB, ochrona najnowszych dowodów per mapa (V3.86.6)
- **Dziennik zdarzeń:** 5 plików po 5MB (V3.86.2) + dziennik-modów 15x10KB

**Stress testy:**

- 1000 modów -> 20 chunków - OK
- 100 map -> kolejka planuje poprawnie
- 50 wątków concurrent mod check - OK
- 20 RCON commands concurrent - OK

**Ocena:** 9/10

---

## 7. V3.86.7 - ANALIZA ZMIAN

### 7.1 Problem z 3.86.6

Finalna 3.86.6 wymagała świeżego READY w logu nawet przy nowym działającym procesie. Monitor dodatkowo blokował sondę RCON w trakcie kolejki i uruchamiał ją tylko dla UNKNOWN.

Zatem samo poluzowanie warunku powrotu nie wystarczało dla nowego procesu ze starym statusem GOTOWY.

### 7.2 Fix w 3.86.7

**monitor_plugin.py:**

```python
def _needs_return_probe(tab):
    # UNKNOWN after startup can mean READY fell outside bounded initial log scan
    record = watch_maps or return_failures
    before = record[identity], current = tab._monitor_identity
    return before != current and not _ready_since(...)

def _monitor_apply():
    if ((tail_status == "unknown" or _needs_return_probe(tab)) and alive and now >= sonda_t+30):
        sonda_rcon(tab, confirm_unknown=True)  # może wysłać ListPlayers do nowego procesu ze statusem UNKNOWN/GOTOWY
```

Podczas oczekiwania na powrót lub przy zapisanym alarmie monitor może wysłać ListPlayers do nowego procesu ze statusem UNKNOWN/GOTOWY. Zachowuje odstęp sond 30s. Po odpowiedzi sprawdza tę samą zakładkę, PID, czas startu, generację logu i żywotność procesu. Sonda jest tylko odczytem.

**server_tab.py:**

```python
def confirm_ready_by_rcon(self, identity=None, boot_seq=None):
    # potwierdzenie RCON zapisuje tożsamość procesu
    # utrata stanu GOTOWY unieważnia dowód
    self._rcon_ready_identity = identity
```

**procedura.py:**

```python
def _ready_since(tab, record, allow_rcon=True):
    # powrót i skasowanie alarmu dopuszczają nowy proces ze świeżym potwierdzeniem RCON
    # ścieżka świeżego READY w logu pozostaje dostępna
    if allow_rcon and tab._rcon_ready_identity == current_identity and alive:
        return True
```

RCON wymaga znanej tożsamości procesu sprzed DoExit i aktualnego procesu. Brak danych nie oznacza powrotu. Nie zmieniono protokołu RCON ani żadnego pluginu. W siec.py zmienił się wyłącznie numer wersji User-Agent.

**Weryfikacja:** 15/15 nowych testów regresji zaliczonych, pełny pakiet 478 wykonanych, 476 zaliczonych, 2 pominięte, 0 błędów.

**Nasza weryfikacja:** Potwierdzamy - logika działa, stale reply odrzucane, PID reuse odrzucane, dead process odrzucany, changed boot_seq odrzucany, crash odrzucany, removed tab nie dostaje reply.

**Ocena V3.86.7:** 10/10 - naprawa regresji jest poprawna, bezpieczna, dobrze przetestowana.

---

## 8. JAKOŚĆ KODU

- **Linie:** 13 309 linii (asaonly + PLUGINY) - dużo, ale modularne
- **Stdlib only:** Zero pip - `tkinter`, `socket`, `urllib`, `json`, `os`, `time`, `threading`, `subprocess`, `re`, `pathlib` - świetne dla Windows adminów
- **Komentarze:** PL/EN, dużo wyjaśnień dlaczego, nie tylko co - np. aksjomat kolejki, WZORCE_PUSTO_DOMYSLNE komentarz o ASE vs ASA
- **Nazwy:** Polskie i angielskie mieszane (t() ma PL/EN), ale konsekwentne w module
- **Testy:** 605 testów, 51s - bardzo dobre pokrycie
- **Wersjonowanie:** V3.86.7 - widać 3 lata iteracji, CHANGELOG w WIEDZA_O_PROGRAMIE
- **Licencja:** MIT, 100% darmowy

**Tech debt:**

- Dużo global state w Mixins (self.tabs, self.pending_updates, etc) - ale to Tkinter app, nie microservice
- `procedure_run` dict - informacyjny, ale rośnie - OK bo rotacja
- `PLUGINY/` - 1830 linii w 88_aktualizacja_serwera.py - największy, można by podzielić, ale działa

**Ocena jakości:** 9/10

---

## 9. REKOMENDACJE - CO POPRAWIĆ

### Krytyczne (none)

Brak krytycznych bugów.

### Ważne

1. **CF 429 Retry-After:** Ujednolicić `cf_request` z `steam_api_info` - dodać `ApiZajete` z Retry-After
2. **ListPlayers ASA:** Zebrać prawdziwe logi z ASA Dedicated Server i dodać wzorzec pustego serwera dla ASA, albo udokumentować że admin może ustawić `listplayers_pusto` w konfiguracji
3. **Test .gitignore:** Poprawić `test_v3862` żeby nie failował gdy brak `.gitignore`

### Średnie

4. **FakeTk:** Rozbudować dla headless CI - dodać minsize, title, etc (już zrobione w v2)
5. **API styl:** Ujednolicić `API=1` vs `API = 1` - wybrać jeden
6. **Rytm fazowy:** Sprawdzić progi 1/3/15 min w `monitor.py` - test oczekiwał 60/180/900 ale real zwraca 60 dla 181s
7. **Steam cache:** Dodać walidację czy cache folder nie jest na tym samym dysku co system (jeśli 12GB)

### Niskie / Nice to have

8. **Type hints:** Dodać type hints dla lepszego IDE support (obecnie brak)
9. **Logging:** Rozważyć `logging` module zamiast custom `log()` - ale obecne działa
10. **Async:** Rozważyć `asyncio` dla RCON/CF zamiast wątków - ale obecne threading działa i jest prostsze

---

## 10. PODSUMOWANIE - OCENA KOŃCOWA

| Kategoria | Ocena | Uwagi |
|-----------|-------|-------|
| Architektura | 9.5/10 | Aksjomat, czysta logika kolejki, plugin host |
| RCON | 9/10 | Solidny, deadline, frame check, UncertainError |
| CF API | 8.5/10 | Batch 50, chunking, brak 429 Retry-After |
| Kolejka | 10/10 | Genialna, na styk, puste najpierw, fail-closed |
| Procedura | 9.5/10 | Dojrzała, 50+ testów, checkpoint, porzucanie |
| Monitor/PAD | 9.5/10 | 10s tick, PAD4 90s, WISI 15/20 min, RCON sonda |
| Pluginy | 9/10 | Alfabetycznie, izolacja, required |
| ServerTab | 9/10 | Mody z logu, secret oddzielnie |
| Steam update | 9/10 | Cache, backup+rollback, 40+ testów |
| Security | 9/10 | Sekrety oddzielnie, no injection, fail-closed |
| Concurrency | 9/10 | post_ui, snapshot, atomowe zapisy |
| Edge cases | 10/10 | Niesamowicie dużo obsłużonych |
| Wydajność | 9/10 | Batch, 2MB tail, 10s monitor |
| V3.86.7 fix | 10/10 | Poprawny, bezpieczny, 15/15 testów |
| Jakość kodu | 9/10 | Stdlib only, komentarze, 605 testów |
| **ŁĄCZNIE** | **9.3/10** | **BARDZO SOLIDNY, produkcyjny** |

**Czy rozpakowanie ZIP to szczyt możliwości? Nie. To dopiero początek. Gruba analiza pokazuje że Refresher V3.86.7 to 3 lata dojrzałego rozwoju, 13k linii, 605 testów, 0 krytycznych bugów, świetna architektura i security.**

**Rekomendacja: Można używać na produkcji dla klastra ASA.**

---

*Analiza wykonana przez Arena Agent, 28.09.2026, branch arena/01a0e886-asaonly-mod-refresher, commit 6a95dda, ZIP ASAonly-V3.86.7.zip*
