# ASAonly – (AUTO)Manual – ModRefresher (RCON)

**V3.86.7** · 100% darmowy · licencja MIT · program `.py` + pakiet `asaonly/` + `PLUGINY/` · tylko biblioteka standardowa Pythona · interfejs PL/EN

**3.86.7 — naprawa regresji powrotu:** świeża odpowiedź RCON dla nowego procesu
(PID i czas startu) potwierdza powrót również bez znacznika READY w logu.
Opóźniona odpowiedź innego procesu jest odrzucana. Sam RCON nie potwierdza wersji
załadowanych modów. [Szczegóły i testy](WIEDZA_O_PROGRAMIE/V3.86.7-POWROT-RCON.md).

**3.86.7 — return detection regression fix:** a fresh RCON response validated
against the replacement process (PID and creation time) confirms its return even
without a READY log marker. Stale process replies are rejected. RCON alone does
not verify loaded mod versions.

**3.86.6 (historia; wymóg READY skorygowany w 3.86.7):** nowy PID ze starym GOTOWY nie kończy oczekiwania na mapę.
Wymagany jest nowy znacznik READY w logu, a ponowny odczyt tego samego znacznika
nie wystarcza. Zmiana nazwy mapy przenosi oba trwałe alarmy wraz z konfiguracją.
Archiwum PADY ma ustawiany limit (domyślnie 2048 MiB), ochronę najnowszych dowodów
i ostrzeżenia o przekroczeniu limitu. [Szczegóły 3.86.6](WIEDZA_O_PROGRAMIE/V3.86.6-GOTOWY-ALARMY-PADY.md).

**3.86.6 (historical; READY requirement corrected in 3.86.7):** a replacement PID carrying stale READY cannot finish the return watch.
A fresh READY log marker is required; replaying the same marker does not count.
Renaming a map preserves its saved alerts. PADY retention has a configurable
2048 MiB default budget and protects the latest evidence for each map.

**3.86.5 — po superteście:** poprawione potwierdzanie powrotu po crashu przy DoExit;
istniejący crashstack przy włączeniu śledzenia nie zmienia GOTOWY na CRASH.
Odrzucone logowanie lub połączenie RCON zostawia alarm i pomija oczekiwanie tej mapy;
nieudany DoExit blokuje kolejną automatyczną próbę tej samej wersji moda.
Przyciski ZAMKNIJ / ZAPISZ WSZYSTKIE w panelu RCON mają stałe miejsce.
[Zmiany, ograniczenia i testy 3.86.5](WIEDZA_O_PROGRAMIE/V3.86.5-SUPERTEST.md).

**3.86.5 — after the sandbox review:** return detection handles a crash during DoExit;
an existing crashstack no longer overrides READY when log tracking starts. Rejected
RCON authentication or connections leave a persistent alert and skip that map's wait.
A failed DoExit prevents another automatic attempt for the same mod version.
The RCON CLOSE / SAVE ALL buttons remain visible. The wire protocol is unchanged.

**3.86.4 — po rundzie z 27.09:** przy śladzie crasha lub nieplanowanym zniknięciu
procesu program zapisuje dowody do `WIEDZA_O_PROGRAMIE/PADY`. Ocena „not a PAD”
wymaga tego samego PID i czasu startu. Nowe ustawienie **Odczekanie po wykryciu
moda** wynosi domyślnie 5 minut (0–60; 0 wyłącza). Przy braku powrotu mapy
pozostaje czerwony alarm; Refresher nadal nie uruchamia serwerów. RCON bez zmian.
[Opis, ograniczenia i wyniki](WIEDZA_O_PROGRAMIE/V3.86.4-RUNDA-I-PADY.md).

**3.86.4 — after the 27 September round:** crash evidence is saved under
`WIEDZA_O_PROGRAMIE/PADY`. Crash survival requires the same PID and creation time.
The new **Wait after detecting a mod** setting defaults to 5 minutes (0–60; 0 disables
it). A map that fails to return leaves a persistent red alert. Refresher still does
not launch servers. RCON behavior is unchanged.

**3.86.3 — odzyskiwanie:** manager wraca dopiero po potwierdzeniu spójności plików;
pozostałą operację można ponowić przyciskiem **UPDATE SERWERA → PONÓW ODZYSKIWANIE**.
Chwilowe błędy dostępu są ponawiane. Niepewny DoExit aktualizacji serwera rozstrzyga
obserwacja procesu mapy (do 300 s). Wykrywanie modów zachowuje fallback `latestFiles`.
[Zmiany, ograniczenia i kroki odzyskiwania](WIEDZA_O_PROGRAMIE/V3.86.3-RECOVERY.md).

**3.86.3 — recovery:** the manager resumes only after file consistency is confirmed.
Use **SERVER UPDATE → RETRY RECOVERY** to retry an unfinished operation. Transient
access failures are retried. An uncertain server-update DoExit is resolved by watching
the map process for up to 300 seconds. Mod detection retains the `latestFiles` fallback.

[🇵🇱 Polski](#polski) · [🇬🇧 English](#english)

---

## Polski

Monitor modów **CurseForge** dla wielu serwerów **ARK: Survival Ascended** z jednego okna.
Gdy CurseForge pokaże nową wersję moda, program restartuje mapy przez **RCON** w kolejce —
jedna mapa startuje naraz; po odczekaniu na nowy mod mapa pusta idzie bez komunikatów, mapa z graczami dostaje
Twój harmonogram ogłoszeń — i pilnuje, aż cały klaster wróci do stanu GOTOWY z nową wersją.
Mody pobiera i instaluje wbudowany w serwer klient CFCore przy każdym uruchomieniu; manager
jedynie ponownie stawia proces po `DoExit`. Program tylko przyspiesza: update i tak wejdzie
przy najbliższym starcie serwera. Od **V3.71** program ma też **strażnika**:
co 10 s zerka na procesy i porty (PAD-y), wykrywa wiszące serwery (sonda RCON po 15 min ciszy
logu), liczy samorestarty, pilnuje dziennika stanu modów i sam pędzi kolejne tury po GOTOWY. Od **V3.85** aktualizuje też sam serwer ASA (plugin „Aktualizacja serwera”) — to jedyne miejsce, w którym program zmienia coś w folderach serwera (plugin można wyłączyć).

### Najważniejsze funkcje
- **Aktualizacja serwera przez własny cache (V3.86)** — przycisk UPDATE SERWERA. Co minutę sprawdza najnowszy build serwera ASA (api.steamcmd.net, zapasowo SteamCMD) i od razu pobiera go SteamCMD-em do własnego folderu cache obok serwerów, gdy serwery dalej działają. Nieudane pobieranie = żaden restart (V3.85 w takiej sytuacji restartowała serwery bez aktualizacji). Gotowy cache → zwykła kolejka restartu (gracze, ogłoszenia, jeden start naraz); po wyłączeniu serwera kopiowane są tylko zmienione pliki, z kopią zapasową i wycofaniem przy błędzie, a wstrzymany na ten czas manager sam podnosi zaktualizowany serwer. Mapa z wyłączonym serwerem — bez DoExit. Nie działa, gdy w managerze włączony jest jego updater („Enable automatic update checking”). Wymaga uruchomienia programu jako administrator.
- **Pełna wersja angielska (V3.84)** — przełącznik EN/PL tłumaczy całe okno, wszystkie pluginy, okienka i dziennik zdarzeń (wcześniej po angielsku był tylko słownik głównego okna).
- **Kontrola czasu (V3.82)** — przycisk KONTROLA CZASU sprawdza ręczne ustawienia czasu w harmonogramach RCON tymi samymi regułami co procedura (mapy, które procedura pominie; komunikat „za 15 minut” niezgodny z czasem do DoExit; czekanie bez komunikatu) i pokazuje podgląd fali restartów liczony prawdziwym planistą kolejki. Tylko odczyt.
- **Kolejka i gracze (V3.81)** — przed restartem program pyta mapę o graczy (`ListPlayers`): pusta = restart od razu, bez komunikatów; z graczami = Twój harmonogram. Startuje najwyżej jedna mapa naraz (dysk SSD), puste idą pierwsze, a ogłoszenia na kolejnych mapach lecą równolegle „na styk” według czasów startu zmierzonych na Twojej instalacji. Żadna mapa nie zatrzymuje reszty.
- **Wiele map w jednym oknie** — każda mapa to osobna karta: własny RCON, własny harmonogram komend, własne mody.
- **Import z backupu (plugin „Konfiguracje”, przycisk IMPORT / BACKUP)** — wskazujesz katalog starego Refreshera albo backupu; skan niczego nie zmienia, a Ty wybierasz mapy, sekrety RCON i klucz API. Hasło RCON podciąga się z pliku sekretu leżącego obok. Tab, który już działa = najpierw pytanie TAK/NIE o świadomy duplikat. (Ten plugin zastąpił dawny przycisk „+ Tab z backupu” z V3.46/3.47.)
- **Import taba z backupu bezpieczny dla listy modów (V3.50)** — serwer działa? Lista z backupu jest od razu weryfikowana i korygowana wg logu. Serwer jeszcze nie wstał? Lista czeka z flagą [niezweryfikowana] i koryguje się SAMA przy pierwszym starcie serwera.
- **Odporny na bajzel w katalogu modów (V3.49)** — „Mody z serwera” biorą listę z LOGU serwera (to, co serwer naprawdę ładuje), nie z folderów; update moda nieużywanego przez serwer NIE restartuje mapy.
- **Wspólna baza modów + mody specyficzne per mapa** — np. Better Horde (event hord) tylko dla Extinction: update moda bazowego restaruje wszystkie żywe mapy, update moda specyficznego — tylko jego mapę.
- **Jedno zapytanie zbiorcze do API CurseForge** (do 50 modów na POST) — oszczędza limity API.
- **Pełna procedura restartu**: ogłoszenie dla graczy (ServerChat) → DoExit w kolejce (jeden start naraz) → czuwanie powrotu każdej mapy do GOTOWY z weryfikacją wersji w logu serwera.
- **Zaległości i parking**: automat RCON wyłączony? Update czeka na liście zaległości — wykonasz je jednym przyciskiem.
- **CRASH GUARD** — mapa padła? DoExit zostaje pominięty, reszta klastra działa dalej.
- **Alarm KRACHLOOP** — 3 krachy w 15 minut = wyraźne ostrzeżenie w dzienniku.
- **Godzenie wersji (V3.41)** — jeśli zaktualizowałeś moda ręcznie, program sam godzi wersje i zdejmuje zaległość.
- **Strażnik (V3.71–3.73)**: monitor procesów+portów co 10 s (PAD pewny / okno 90 s PAD4),
  alarm wiszącego serwera (15 min → sonda RCON, 20 min → alarm), samorestarty, utknięte
  pobieranie modów przez serwer (próg 20 min), dioda stanu CurseForge z sondą 1/3/15 min, dziennik modów
  (15×10 KB), przycisk WYKRYJ i klikalne kafelki map z chipami [NOWY]/[SONDA]/[WISI!]
  (3.73; odczyt portów rozumie polski Windows: NASŁUCHUJĄCE).
- Śledzenie logów serwera (ogon 2 MB), czarna skrzynka diagnostyczna, pełna trwałość ustawień po restarcie.

### Pluginy

Katalog `PLUGINY/` jest ładowany alfabetycznie. Host wymaga `API = 1` i izoluje błędy pluginu. Wymagane: RCON — procedury serwerów (86), koordynator procedur (50), guard konfiguracji (10), audyt wersji (40). Opcjonalne: aktualizacja serwera przez własny cache i SteamCMD (88, domyślnie włączona; od V3.85, cache od V3.86), kontrola czasu RCON (87, domyślnie włączona, tylko odczyt), konfiguracje — import ze starego Refreshera, backup i przywracanie (80, domyślnie włączony; od V3.83 jeden plugin zamiast dwóch), status i historia serwerów, analizator logów ASA, pakiet diagnostyczny, dysk/katalogi oraz CPU priority/affinity (domyślnie wyłączony). Testy: `python symulacja/run_all.py` (bez `pip`).

### Wymagania
- Windows + **Python 3.8+** (tylko biblioteka standardowa — zero `pip install`)
- Klucz API CurseForge (bezpłatny: console.curseforge.com/?#/api-keys)
- Serwery ASA uruchamiane przez ASA Dedicated Manager / ASM

### Szybki start
1. Pobierz i rozpakuj `V3.86.2 ASAonly - (AUTO)Manual - ModRefresher (RCON).zip`, uruchom `STARTER plus Python installer - ASAonly - (AUTO)Manual - ModRefresher (RCON).bat` (sam sprawdzi/zainstaluje Pythona) albo `python "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"`.
2. Wklej klucz API CurseForge (góra okna) i zapisz.
3. Dodaj mapę (**+ Dodaj mapę**): wskaż folder logu serwera, wpisz ID modów (albo kliknij **Mody z serwera** — program odczyta z LOGU, co serwer naprawdę ładuje).
4. Przycisk **RCON**: dane połączenia i harmonogram komend (np. `ServerChat restart za 5 minut` na 0 s, `DoExit` na 300 s — czasy liczone od początku odliczania TEJ mapy), zaznacz aktywne linie → **ZAPISZ WSZYSTKIE**.
5. **Zapisz tab** (pod polami mapy; zapisuje tylko tę mapę) → **Sprawdź mody teraz**. Gotowe — program pilnuje reszty.

### Jak działa aktualizacja (automat)
1. Sprawdzenie CurseForge (ręczne lub w interwale, min. 30 s; domyślnie 5 min).
2. Nowa wersja moda? Mapy niekorzystające z niego są pomijane. Pozostałe czekają ustawiony czas od wykrycia (domyślnie 5 min), potem trafiają do kolejki.
3. Program pyta każdą mapę o graczy (`ListPlayers`). Pusta = restart od razu, bez komunikatów;
   z graczami (albo gdy nie wiadomo) = Twój harmonogram ogłoszeń.
4. Startuje najwyżej jedna mapa naraz (od `DoExit` do GOTOWY) — puste pierwsze; ogłoszenia
   na kolejnych mapach lecą równolegle tak, żeby skończyły się, gdy dysk się zwolni.
5. Po starcie program sprawdza w logu serwera, czy mapa wstała z nową wersją. Mapa nie wróciła?
   Trwały czerwony alarm, wpis w dzienniku i następna mapa. Nowe update'y w trakcie? Kolejna tura uwzględnia również czas odczekania od ich wykrycia.

### Bezpieczeństwo
- Klucz API zostaje lokalnie w `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <data>.json`, a hasła RCON map w prywatnych `CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/` — hasło NIE trafia do configu (nie commituj sekretów publicznie).
- Program wysyła komendy RCON **wyłącznie do serwerów, które sam mu wskażesz**. Zero telemetrii, zero ukrytych połączeń.
- Plugin „Aktualizacja serwera” łączy się ze Steamem przez SteamCMD (logowanie anonimowe), a przy pierwszym użyciu pobiera SteamCMD od Valve do katalogu `STEAMCMD/` obok programu. Od V3.86 pyta też co minutę **api.steamcmd.net** (nieoficjalna, otwarta usługa — nie Valve; bez klucza, pytanie dotyczy tylko aplikacji 2430930) — można to wyłączyć w panelu UPDATE SERWERA (wtedy tylko SteamCMD). Czyta też z `user.config` managera wyłącznie ustawienia jego updatera (bez haseł i tokenów).

### Pliki obok programu
| Plik / katalog | Co zawiera |
|---|---|
| `CONFIG_PROGRAM/CONFIG_PROGRAM - zapis <data>.json` | ustawienia globalne (interwał, automat RCON); każdy zapis = nowy plik z datą i godziną, rotacja 10 najnowszych |
| `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <data>.json` | klucz API CurseForge (prywatny!) |
| `CONFIG_MAPS_TABS/<mapa>/CONFIG_MAP <mapa> - zapis <data>.json` | ustawienia i harmonogram jednej mapy — BEZ hasła |
| `CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON <mapa> - zapis <data>.json` | hasło RCON tej mapy (prywatne; zapisuje je panel RCON) |
| `STEAMCMD/` | własny SteamCMD pluginu „Aktualizacja serwera” (V3.85; pobiera się sam) |
| `<folder serwerów>\ASA UPDATES REFRESHER\` | cache serwera ASA pluginu „Aktualizacja serwera” (V3.86; ok. 12 GB; folder zmienisz w panelu UPDATE SERWERA) |
| `WIEDZA_O_PROGRAMIE/` | dokumentacja + `dziennik-zdarzen.txt` — cały dziennik zdarzeń z okna konsoli (V3.86.2; 5 plików po 5 MB) + `asa_debug.log` (ukryte błędy programu) + `dziennik-modow.txt` (V3.71) |

Każda zapisana zmiana tworzy NOWY plik z datą i godziną w nazwie (np. `... - zapis 29.08.2026 14-05-53.json`); program zawsze czyta najnowszy, a 10 ostatnich wersji pełni rolę backupów. Stare nazwy (`asa_config.json`, `asa_tabs/`…) migrują automatycznie przy pierwszym uruchomieniu.

**Licencja: MIT** (plik `LICENSE` w komplecie) — program jest i będzie 100% darmowy.
Źródło i wydania: https://github.com/hotstrixi3-wq/asaonly-modrefresher Pełna lista zmian: `README - ASAonly - (AUTO)Manual - ModRefresher (RCON).txt` w archiwum.

**[↑](#asaonly--manual-mod-refresher)**

---

## English

A **CurseForge** mod monitor for multiple **ARK: Survival Ascended** servers in a single window.
When CurseForge reports a new mod version, the tool restarts the maps over **RCON** through a queue —
one map starts at a time; after the mod wait, an empty map goes without messages, a map with players gets your
announcement schedule — and watches until the whole cluster is READY again with the new version.
Downloading and installing mods is performed by the ASA server's built-in CFCore client on every start; the manager only brings the process back after `DoExit`. The tool only speeds things up: an update lands at the server's next start anyway. Since **V3.85** it can also update the ASA server itself (the "Server update" plugin) — the only place where the tool changes anything in server folders (the plugin can be switched off).

### Highlights
- **Server update through its own cache (V3.86)** — the SERVER UPDATE button. Every minute it checks the latest ASA server build (api.steamcmd.net, SteamCMD as a fallback) and downloads it right away with SteamCMD into its own cache folder next to the servers, while the servers keep running. A failed download = no restart at all (V3.85 restarted the servers without an update in that situation). Cache ready → the normal restart queue (players, announcements, one start at a time); after the server stops only the changed files are copied, with a backup and a rollback on any error, and the manager — paused meanwhile — starts the updated server itself. A map whose server is down — without DoExit. Does nothing while the manager's own updater is on ("Enable automatic update checking"). The program must run as administrator.
- **Complete English version (V3.84)** — the EN/PL switch translates the whole window, every plugin, the dialogs and the event log (before, only the main window's dictionary was in English).
- **Time check (V3.82)** — the TIME CHECK button (KONTROLA CZASU in Polish) checks the manual time settings in RCON schedules with the same rules as the procedure (maps the procedure will skip; a "15 minutes" message that doesn't match the time to DoExit; waiting without any message) and previews the restart wave using the real queue planner. Read-only.
- **Queue and players (V3.81)** — before a restart the tool asks the map for players (`ListPlayers`): empty = restart at once, no messages; players = your schedule. At most one map starts at a time (SSD), empty maps go first, and announcements on the next maps run in parallel "just in time", using start times measured on your own installation. No single map stops the rest.
- **Many maps, one window** — each map is a tab with its own RCON, command schedule and mod list.
- **Import from a backup (the "Configurations" plugin, IMPORT / BACKUP button)** — point to the folder of the old Refresher or of a backup; the scan changes nothing, and you choose the maps, RCON secrets and the API key. The RCON password rides along from the adjacent secret file. An already-running tab = a Yes/No question first about a deliberate duplicate. (This plugin replaced the old "+ Tab from backup" button from V3.46/3.47.)
- **Backup import safe for the mod list (V3.50)** — server running? The backup list is verified and corrected against the log immediately. Server not up yet? The list waits flagged [unverified] and corrects ITSELF on the server's first boot.
- **Immune to a messy mods directory (V3.49)** — "Mods from server" takes the list from the server LOG (what the server actually loads), not from folders; an update of a mod the server doesn't load does NOT restart the map.
- **Shared mod base + per-map mods** — e.g. Better Horde (horde event) for Extinction only: a base-mod update restarts every live map, a map-specific update only that map.
- **One batch CurseForge API call** (up to 50 mods per POST) — friendly to API limits.
- **Full restart procedure**: player announcement (ServerChat) → queued DoExit (one start at a time) → return watch until every map is READY, with the version verified in the server log.
- **Pending updates & parking**: RCON automation off? Updates wait on a pending list — run them with one button.
- **CRASH GUARD** — a crashed map gets its DoExit skipped; the rest of the cluster proceeds.
- **CRASHLOOP alarm** — 3 crashes within 15 minutes trigger a clear warning.
- **Version syncing (V3.41)** — updated a mod manually? The tool syncs versions and clears the pending item by itself.
- **The Guardian (V3.71/3.73)**: process+port monitor every 10 s (certain PADs / 90 s PAD4
  window), hanging-server alarm (15 min → RCON probe, 20 min → alarm), self-restart counting,
  stuck server mod download watchdog, CurseForge health LED with a 1/3/15 min probe, mod-state
  journal (15×10 KB), a DETECT button and clickable map chips.
- Log tailing (2 MB tail), diagnostic black box, full settings persistence across restarts.

### Plugins

The `PLUGINY/` folder is loaded alphabetically. The host requires `API = 1` and isolates plugin errors. Required: RCON server procedures (86), procedure coordinator (50), config guard (10), version audit (40). Optional: server update through its own cache and SteamCMD (88, on by default; since V3.85, cache since V3.86), RCON time check (87, on by default, read-only), configurations — import from an old Refresher, backup and restore (80, on by default; one plugin instead of two since V3.83), server status & history, ASA log analyzer, diagnostic package, disk/folders and CPU priority/affinity (off by default). Tests: `python symulacja/run_all.py` (no `pip`).

### Requirements
- Windows + **Python 3.8+** (standard library only — no `pip install`)
- A free CurseForge API key (console.curseforge.com/?#/api-keys)
- ASA servers managed by ASA Dedicated Manager / ASM

### Quick start
1. Download and unzip `V3.86.2 ASAonly - (AUTO)Manual - ModRefresher (RCON).zip`, run `STARTER plus Python installer - ASAonly - (AUTO)Manual - ModRefresher (RCON).bat` (it checks/installs Python for you) or `python "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"`.
2. Paste your CurseForge API key (top of the window) and save.
3. Add a map (**+ Add map**): point to the server log folder, type mod IDs (or click **Mods from server** — the list comes from the server LOG).
4. The **RCON** button: connection details and the command schedule (e.g. `ServerChat restart in 5 minutes` at 0 s, `DoExit` at 300 s — times count from the start of THIS map's countdown), tick the active lines → **SAVE ALL**.
5. **Save tab** (under the map's fields; saves this map only) → **Check mods now**. Done — the tool watches the rest.

### How an update plays out (automation)
1. CurseForge check (manual or on an interval, min 30 s; default 5 min).
2. New mod version? Maps that don't use the mod are skipped. The rest wait from detection (5 minutes by default), then join the queue.
3. The tool asks every map for players (`ListPlayers`). Empty = restart at once, no messages;
   players (or unknown) = your announcement schedule.
4. At most one map starts at a time (from `DoExit` to READY) — empty maps first; announcements
   on the next maps run in parallel so that they end when the disk becomes free.
5. After the start the tool checks the server log for the new version. A map didn't return?
   A persistent red alert, a log entry and the next map. New updates meanwhile? The next round also respects their wait from detection.

### Security
- The API key stays local in `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <date>.json` and map RCON passwords in private `CONFIG_MAPS_TABS/<map>/CONFIG_SECRET_RCON/` — passwords never land in the config file (do not commit secrets publicly).
- RCON commands are sent **only to the servers you configure**. No telemetry, no phone-home.
- The "Server update" plugin connects to Steam through SteamCMD (anonymous login) and, on first use, downloads SteamCMD from Valve into the `STEAMCMD/` folder next to the program. Since V3.86 it also asks **api.steamcmd.net** every minute (an unofficial, open-source service — not Valve; no key, the request is only about app 2430930) — this can be turned off in the SERVER UPDATE panel (then SteamCMD only). From the manager's `user.config` it reads only its updater settings (no passwords or tokens).

### Files kept next to the program
| File / folder | Contents |
|---|---|
| `CONFIG_PROGRAM/CONFIG_PROGRAM - zapis <date>.json` | global settings (interval, RCON automation); every save = a new timestamped file, 10 newest kept |
| `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <date>.json` | CurseForge API key (private!) |
| `CONFIG_MAPS_TABS/<map>/CONFIG_MAP <map> - zapis <date>.json` | per-map settings and schedule — NO password inside |
| `CONFIG_MAPS_TABS/<map>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON <map> - zapis <date>.json` | that map's RCON password (private; saved by the RCON panel) |
| `STEAMCMD/` | the "Server update" plugin's own SteamCMD (V3.85; downloads itself) |
| `<servers folder>\ASA UPDATES REFRESHER\` | the "Server update" plugin's ASA server cache (V3.86; about 12 GB; change the folder in the SERVER UPDATE panel) |
| `WIEDZA_O_PROGRAMIE/` | docs + `dziennik-zdarzen.txt` — the whole event log from the console window (V3.86.2; 5 files of 5 MB) + `asa_debug.log` (hidden program errors) + `dziennik-modow.txt` (V3.71) |

Every saved change creates a NEW file with the date and time in its name (e.g. `... - zapis 29.08.2026 14-05-53.json`); the program always reads the newest one and keeps the 10 latest versions as backups. Old names (`asa_config.json`, `asa_tabs/`…) migrate automatically on first run.

**License: MIT** (`LICENSE` file included) — the program is and will remain 100% free.
Source & releases: https://github.com/hotstrixi3-wq/asaonly-modrefresher Full changelog: `README - ASAonly - (AUTO)Manual - ModRefresher (RCON).txt` in the archive.

**[↑](#asaonly--manual-mod-refresher)**

---

## Przeprosiny za tłumaczenie / Apology for the translation

**PL:** Część tekstów w programie i dokumentach była generowana przez AI,
która nie specjalizuje się w języku polskim — stąd dziwne odmiany,
„kwiatki" i literówki. Przepraszamy. Znaczenie zawsze wynika z kontekstu,
a tłumaczenie zostanie poprawione w kolejnych wersjach.

**EN:** Some texts were generated by an AI that does not specialize in
Polish — hence odd wording and typos. We apologize. The meaning is always
clear from context, and the translation will be improved in future versions.
