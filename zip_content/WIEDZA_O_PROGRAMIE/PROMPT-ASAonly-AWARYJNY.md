<!-- AWARYJNY PROMPT NA PRZYSZŁOŚĆ — kopia PROMPT-ASAonly-KONTEKST.md
     Wgraj ten plik nowemu asystentowi jako kontekst na start sesji. -->
# ============================================================================
# PLIK KONTEKSTOWY PROJEKTU: "ASAonly - Manual Mod Refresher"
# ============================================================================
# DO CZEGO TEN PLIK JEST (instrukcja dla asystenta, który go dostaje):
# Ten plik przywraca PEŁNY kontekst projektu w nowej sesji. Przeczytaj go
# CAŁY zanim cokolwiek zrobisz. Potwierdź userowi krótkim podsumowaniem,
# że kontekst przyjęły. Nie zadawaj pytań, na które odpowiedź jest niżej.
# Plik utrzymuje asystent (aktualizuje na końcu każdej tury, w której
# coś się zmieniło). User może go w każdej chwili pobrać i wrzucić
# w nowej sesji razem z aktualnym .py / README / .bat.
# ============================================================================

## 0. KIM JEST UŻYTKOWNIK I JAK SIĘ Z NIM PRACUJE
- User = **@Magus** — pomysłodawca i koncepcja programu. Kod pisze asystent
  (Arena.ai Agent Mode do 3.80.35; od 3.81 Claude, Anthropic — tak też
  w oknie „O programie” od 3.85.4). Program jest **w 100% DARMOWY** (za próbę
  zarabiania na nim "należy się wielka, tłusta ślina na sweterku" — cytat
  z programu, tak trzymać).
- Pisze po polsku, luźno, CZĘSTO WIELKIMI LITERAMI. POWÓD PRAKTYCZNY (user:
  "kiedyś miałem wzrok snajpera, teraz jestem ślepy"): wielkie litery pozwalają
  siedzieć DALEJ od ekranu. Czytamy praktykę i logikę, nie filozofię.
  Odpowiedzi po polsku, konkretnie, czytelnie sformatowane (nagłówki, listy),
  bez ścian drobnego tekstu.
- User jest świadomym użytkownikiem (prowadzi klaster serwerów ASA przez
  ASA Dedicated Manager), ale NIE jest programistą Pythona — od nas chce
  działający kod i jasne wyjaśnienia.
- Rozmowy umierają (limit kontekstu), dlatego istnieje ten plik. User może
  wrzucić kilka wiadomości materiałów z poprzednich sesji — przyjmujemy,
  zapisujemy, weryfikujemy, nie marudzimy.

## 1. CZYM JEST PROGRAM (misja w 3 zdaniach)
Lekki monitor aktualizacji modów **ARK: Survival Ascended** przez CurseForge
API. Gdy mod dostaje nową wersję, program wysyła ZAPLANOWANE komendy RCON
(ogłoszenia dla graczy, na końcu DoExit). Mody pobiera i instaluje SAM SERWER
przy KAŻDYM starcie (wbudowany klient CFCore), a proces po DoExit podnosi
ASA Dedicated Manager (ASM; manager aktualizuje też samą grę, modów nie).
Program NIE jest menedżerem serwera: nie pobiera modów, nie stawia procesów
— czuwa, sygnalizuje, kolejkuje restarty (od 3.81) i kończy. Jest
AKCELERATOREM: update i tak wejdzie przy najbliższym starcie serwera.
Program .py + pakiet asaonly/ + PLUGINY/, wyłącznie stdlib (tkinter), Windows.

## 2. PLIKI PROJEKTU (workspace / u usera)
| Plik | Rola |
|---|---|
| `ASAonly - (AUTO)Manual - ModRefresher (RCON).py` | CAŁY program (jeden plik, ~200 KB). Wersja w `app_title` (PL/EN), docstringu i show_about(). |
| `README - ASAonly - (AUTO)Manual - ModRefresher (RCON).txt` | Historia zmian (sekcja nowej wersji NA GÓRZE) + instrukcja. **Aktualizować przy każdej wersji.** |
| `STARTER plus Python installer - ASAonly - (AUTO)Manual - ModRefresher (RCON).bat` | Launcher: szuka Pythona, w razie czego instaluje, testuje tkinter, odpala .py. |
| `PROMPT-ASAonly-AWARYJNY.md` | **Ten plik.** Kanoniczny kontekst do odzyskiwania sesji. |
| `pewniaki/NOTATKI-PROJEKT.md` | Dziennik sesji (pełny); root/NOTATKI to tylko pointer. |
| `CONFIG_PROGRAM/CONFIG_PROGRAM - zapis <data>.json` | Ustawienia globalne (bez haseł), rotacja 10. |
| `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis <data>.json` | TYLKO klucz API CurseForge. |
| `CONFIG_MAPS_TABS/<mapa>/CONFIG_MAP <mapa> - zapis <data>.json` | Konfig mapy BEZ hasła; obok podkatalog `CONFIG_SECRET_RCON/` z sekretem RCON (nazwa mapy w nazwach plików — 3.64/3.66). |
| `WIEDZA_O_PROGRAMIE/` | Dokumentacja (README/MANUAL/MAPA/PROMPT/REPORT) + `asa_debug.log` + `dziennik-modow.txt` (3.71). |

## 3. MAPA FUNKCJI — CO OFERUJE I PO CO (perspektywa usera)
**Monitoring:** automatyczne sprawdzanie CF co interwał (min 30 s, batch POST
/v1/mods, chunki po 50 ID = O(1) zapytań); pierwsze widzenie moda = zapamiętanie
wersji (bez restartu); slot "Monitoruj" ON/OFF per mod; kafelki z LED i wersją
znaną vs najnowszą.
**Reakcja (od 3.81):** linie RCON per mapa, czas = sekundy od początku
odliczania TEJ mapy (lokalny zegar; do 3.80 był globalny od wykrycia);
KOLEJKA: jeden start naraz (dysk), sonda ListPlayers — pusta mapa od razu
bez komunikatów, gracze/niepewność = harmonogram człowieka, puste pierwsze,
ogłoszenia równolegle „na styk” wg zmierzonych czasów startu;
procedura tylko na mapach używających zaktualizowanego
moda (reszta skip z wpisem); Automat RCON WŁ = procedura od razu (w trakcie czuwania: parkowanie;
po GOTOWY klastra: od 3.71 auto-kolejna tura po 60 s — bez okienka),
WYŁ = parkowanie w zaległości; ręczne pole admina + schowek komend.
**Bezpieczniki:** crash guard (mapa CRASH/OFFLINE → pomijamy jej linie);
twarda blokada DoExit gdy serwer wstaje (starting/loading_mods/engine);
czuwanie powrotu po DoExit (timeout domyślnie 20 min, potem alarm); alarm
crashloop (3 krachy/15 min); weryfikacja folderów Mods\83374 po powrocie;
uzgodnienie — zaległość znika, gdy serwery mają już docelowy FileID.
**Strażnik (3.71):** monitor procesów+portów co 10 s (PAD pewny, PAD4 okno
90 s), WISI (15 min → sonda RCON listplayers, 20 min → alarm), samorestarty,
utknięte „Downloading mod", sonda CF 1 mod w rytmie 1/3/15 min gdy CF leży,
dziennik modów przed procedurą (15×10 KB), przycisk WYKRYJ.
**Widoczność:** diody map w pasku statusu; niezależne okna MODY (kafelki) i
DZIENNIK (pamiętają pozycje/rozmiar); log kolorowany, spam per-mod wycięty.
**Dane:** tab = prywatny katalog z backupami; secrets tylko klucz API; zaległości
przeżywają restart programu; "Mody z serwera" wczytuje ID z folderów serwera.
**Hygiena:** RCON retry 3× z backoff 2 s (kolejka per tab), logowanie przez
_log_queue (thread-safe), atomowe zapisy JSON (+.bak), PL/EN toggle, tooltipy,
launcher .bat z autoinstalacją Pythona.

## 4. ARCHITEKTURA (skrót techniczny)
- **App(tk.Tk)** — główne okno; tick co 500 ms (kolejka logów → diody →
  procedura → watch → check CF → blink statusu).
- **ServerTab(ttk.Frame)** — zakładka mapy: RCON, ścieżka logów, mody mapy,
  linie RCON (RconLineRow), admin, schowek; `_tail_status` stan mapy.
- **LogTail(thread)** — tail `ShooterGame.log`: statusy starting →
  loading_mods → engine → ready / crash / offline; rotacja logu z grace;
  crashstacki co 10 s. `open_log_shared` = FILE_SHARE_READ|WRITE|DELETE.
- **CF batch**: `_cf_worker` (wątek) → `cf_get_mods_batch` → porównanie
  `known_versions[mid]` z `latestFiles` (max file id) → pending → procedura.
- **Procedura (3.81)**: `_exec_pending` buduje `Kolejka` z obiektów `Mapa`
  (`asaonly/kolejka.py` — czysta logika bez Tk/RCON/plików) →
  `_tick_restart_timeline` co tik woła `Kolejka.tick(now)` i wykonuje akcje
  („sonda” = ListPlayers przez `enqueue_raw`, „wyslij”, „doexit”) → wyniki
  wracają `wynik_*()` → `_start_return_watch`/`_tick_return_watch` (nowy
  boot + GOTOWY + wersja z logu) → `Kolejka.zakoncz` → `_finish_coordinator`.
- **Config**: `save_config` (global) + `save_tab` (per tab, backup) +
  `save_secrets`; zapisy ręczne przyciskami + auto przy zamknięciu;
  snapshoty `_saved_*` do wykrywania niezapisanych zmian.
- **Monitor 3.71**: `_tick` → `_monitor_worker` (wątek, netstat/ss →
  port→PID, wiek logów, snapshot `list(self.tabs)`) → `post_ui(_monitor_apply)`;
  stan per-tab (_wisi_st/_sonda_t/_dl_last/_dl_alarm) nadaje ServerTab.__init__.
- Stałe konfigurowalne w UI: interwał, cf_delay, watch_timeout_min.

## 4a. RATIONALE PROJEKTU — "blizny" (odzyskane z martwej sesji 2026-08-28)
Warto znać PRZYCZYNY dziwnych decyzji, żeby ich nie "uprościć" przy refaktorze:
- open_log_shared/FILE_SHARE_DELETE: manager kasuje log przed startem; zwykły
  open() blokuje plik i przerywa start serwera.
- INITIAL_SCAN_BYTES=2 MB skan OGONA logu OD TYŁU: logi ważą GB; 2 MB łapie
  CAŁĄ sekwencję startową zmodowanego serwera i daje stan w ułamek sekundy.
- BIG_LOG_BYTES=256 KB („duży log bez markera = GOTOWY”) ŚWIADOMIE USUNIĘTE
  w 3.80: zgadywało GOTOWY bez dowodu. Stan UNKNOWN podnosi do READY dopiero
  udana odpowiedź RCON (confirm_ready_by_rcon). ROTATION_GRACE_S=15 s łaski
  na rotację loga zostaje (asaonly/logtail.py).
- Kolejka RCON per mapa (nie globalna): wisnący serwer (world save ignoruje
  RCON) nie blokuje komend innych map ani GUI.
- Retry RCON 3x co 2 s: world save 5-10 s ignoruje RCON, ale harmonogram
  wobec graczy nie może się rozjechać (stąd krótki odstęp).
- Guardy (DoExit blokowany przy wstającym serwerze; crash/offline = skip
  linii): DoExit w trakcie ładowania = proces zombie blokujący port.
- Watch 20 min: ASM ma crash-detection ~10 min + start zmodowanego serwera
  5-8 min => 20 min pokrywa scenariusz pesymistyczny.
- Crashloop 3/15 min = circuit breaker (mod zabija serwer w pętli ASM).
- known_versions = event sourcing (baseline przy 1. widzeniu, zdarzenie przy
  zmianie) — porównywanie z dyskiem dawałoby fałszywe alarmy (serwer przez CFCore pobiera
  dopiero przy restarcie).
- _verify_local_mods = "zaufaj, ale weryfikuj": admin/ASM mogli zrobić
  restart za plecami programu; program sam wykreśla zaległości.
- Separacja sekretów: klucz API (jeden globalny) w asa_secrets.json; hasła
  RCON per mapa w jej configu. Zapis ręczny = "explicit consent" (crash
  nie psuje haseł).
- flush_rcon_queue zamiast kill wątku: graceful shutdown (socket dokończy
  send; wątek śpi na kolejnej komendzie).
- map_on = feature flag: jedno kliknięcie wyłącza mapę z 4 systemów naraz
  (linie, diody, panel modów, zapytania CF), config zostaje.
- Kolory diod = semafory drogowe (UX pod stres o 3:00 w nocy).
- DECYZJA USERA (PTK 10): SERWER przez wbudowany CFCore przy każdym starcie robi update
  modów => program to AKCELERATOR, nie warunek; wykryty update i tak wjedzie
  przy najbliższym starcie. Dlatego guard_skip/incident są bezpieczne.
- DECYZJA USERA (PTK 11): rozjazd restartów (stagger), NIE synchronizacja.
  Cel wprost od usera: „ŻEBY RESTARTY NIE ZAJECHAŁY SSD”. Do 3.80 robił to
  admin czasami na globalnym zegarze; od 3.81 robi to KOLEJKA (jeden start
  naraz, czasy startu mierzone na tej instalacji), a czasy w tabie są
  lokalne dla mapy (ogłoszenia dla graczy).
- ZASADA UI (lekcja uciętych kafelków): geometria Tk ZAWSZE w JEDNĄ stronę:
  okno -> canvas (<Configure>) -> ramka (itemconfig width) -> kafelek
  (pack fill="x" + własny <Configure>). ZERO ręcznego liczenia szerokości
  z event.width okna. Tak zrobione w 3.39.2.
- PANELE "W BRYLE" (PTK 15): 6 iteracji dokowania (3.27-3.33) upadło,
  3.33 = kapitulacja na niezależne Toplevel; poprzedni asystent padł na 7.
  próbie. NIE zaczynać bez jawnego specu od usera. Środek pokładowy do
  zaproponowania: wm_transient (okna log/mody zawsze NAD bryłą +
  minimalizują się razem z nią) — bez wojen o geometrię.

### 4b. BLIZNY V3.81 (dowody z żywego klastra, 2026-09)
- MODY TYLKO PRZY STARCIE: `Log file open` → ~1,6 s → `LogCFCore` (własny
  klucz API serwera, gameId 83374) sprawdza i podnosi mody → dopiero potem
  `UShooterEngine::LoadGameMods`. W trakcie pracy nic nie aktualizuje.
  Trzy dowody (szczegóły: `ANALIZA-COMBO-I-ROZBICIE.md`, rozdz. 0):
  (1) silnik wczytuje mody RAZ (`LoadGameMods`) — podmiana plików pod żywym
  serwerem nie zmienia pamięci; (2) 3 h 41 min pracy Extinction bez żadnej
  aktywności CFCore po starcie (ShooterGame.log i log CFCore); (3) mod
  „Mod Updater” z CurseForge rozwiązuje ten sam problem restartem.
  Linii „Downloading mod” prawdziwy log ASA NIE wypisuje.
- PLIK `windowsserver`: release moda w CF ma kilka plików; serwer instaluje
  plik Windows-serwer. 3.74 śledziła max(latestFiles) → stały rozjazd wersji
  (+3 w file ID). `siec.py` (3.80) wybiera plik windowsserver — nie cofać.
- AKSJOMAT AKCELERATORA: nigdy nie zatrzymywać klastra przez jedną mapę,
  nigdy nie czekać na kliknięcie na ścieżce automatycznej, przerwaną
  procedurę PORZUCIĆ (3.80.35 blokowała automat do ręcznego odblokowania).
- `Log file open` = nowy proces: dowody wersji zerujemy W KOLEJNOŚCI LINII
  (zdarzenie `log_open`), nie przy zmianie statusu — status przychodzi po
  zdarzeniach całego odczytanego fragmentu (3.80.35 kasował nowe wersje
  i weryfikacja po restarcie nigdy nie przechodziła).
- Metod aplikacji NIE szukać w `self.__dict__` (tam ich nie ma — wywołanie
  cicho się nie wykonuje): `_metoda_aplikacji()` w procedura.py.
- Zaznaczone puste wiersze RCON = pomijane (3.74 blokowała przez nie cały
  klaster; tak było na żywym Extinction).
- Serwery usera są puste (gra tylko on) — jego klaster to „lekka sugestia”,
  nie wyznacznik. Czasy startu program MIERZY SAM; nic z jego klastra nie
  jest wpisane na sztywno.
- Manager (z jego logów): usuwa ShooterGame.log przed startem, priorytet CPU
  ustawia ~25 s po starcie procesu, zaplanowane restarty wszystkich map
  w tych samych minutach (nakładające się starty) — decyzja usera, refresher
  tego nie rozjedzie.

## 5. KONWENCJE PRACY (umowa z userem — NIE ŁAMAĆ)
1. **Każda zmiana = nowa wersja** (3.39 → 3.40 dla feature'ów, 3.39.1 dla
   poprawek) + **wpis na GÓRZE README** (styl: `ZMIANY W X.Y "nazwa":`).
   Wersja liczona w `app_title` (PL i EN) oraz `show_about()`.
2. **Tylko stdlib** — zero zależności zewnętrznych (user nie chce pip dla
   samego programu; launcher instaluje tylko samego Pythona).
3. User najpierw OPISUJE zmianę, asystent może dopytać, potem kod. Przy
   dużych zmianach UI — potwierdzać zakres przed wykonaniem.
4. Pliki usera z poprzednich sesji przyjmujemy bez marudzenia i weryfikujemy
   (py_compile, parzystość TR).
5. README to jedyne miejsce historii zmian (nagłówek .py jest krótki).
6. Program darmowy — o tym nie dyskutujemy.
7. **ZASADA "TO TYLKO OKNO"** (lekcja usera, 2026-08-28): gdy naprawa UI
   się nie klei — PORZUCIĆ koncepcję i zbudować od zera PROŚCIEJ. Nie
   dokładać logiki do zepsutej. Historycznie: 7 iteracji kafelków/paneli
   (3.27-3.39) przez "dokładanie logiki" — tak padł poprzedni wcielenie
   asystenta. Przy UI najpierw USUWAĆ kod, dopiero potem dodawać.

## 6. AKTUALNY STAN (ostatnia aktualizacja: 2026-09-27)
- **V3.86.7** — korekta regresji powrotu z finalnej 3.86.6. Nowy proces może wrócić
  przez świeżą odpowiedź RCON bez READY w logu. Przed i po sondzie sprawdzane PID
  i czas startu; odpowiedź starszej generacji jest odrzucana. Dotyczy czuwania
  i usuwania trwałego alarmu. RCON nie potwierdza wersji modów ze starego logu.
  Szczegóły: `V3.86.7-POWROT-RCON.md`. Bez wdrożenia i bez uruchamiania GUI.
- **V3.86.6** — osobna kopia po dodatkowej ocenie 3.86.5, bez wdrożenia.
  Świeży znacznik READY identyfikowany plikiem i pozycją w logu; nowy PID ze starym
  GOTOWY nie zamyka czuwania ani nie usuwa alarmu. Oba alarmy przenoszone w rename
  z rollbackiem. PADY: miękki limit 2048 MiB, ochrona najnowszej/ostatniej pełnej
  kopii każdej mapy, formaty starsze i pliki obce bez automatycznego usuwania.
  Szczegóły: `V3.86.6-GOTOWY-ALARMY-PADY.md`. Nie uruchamiano drugiej operacyjnej
  instancji: GUI testowane offline z zablokowanymi workerami/siecią/procesami.
- **V3.86.5** — kandydat po weryfikacji supertestu z C:/AAA/TEST_3.86.4_2026-09-27.
  Naprawione Z1–Z3, komunikaty i panel RCON; patrz `V3.86.5-SUPERTEST.md`.
  Paczka przygotowana bez wdrożenia. Manager i trzy serwery ASA działały podczas
  testów; produkcyjny Refresher został zamknięty przez użytkownika. Testy używały
  atrap i portów 47020–47022, bez uprawnień do sterowania rzeczywistymi procesami.
  Nie zmieniano konfiguracji ani harmonogramów użytkownika.
- **V3.86.4** — wersja zastana na pulpicie użytkownika; funkcje: archiwum PADY
  (ShooterGame.log + świeże crash), tożsamość PID+czas startu w PAD4, odczekanie
  nowych modów domyślnie 5 min (ustawienie 0–60), trwały alarm mapy, która nie
  wróciła. Refresher nadal nie uruchamia serwerów. RCON bez zmiany zachowania.
  Szczegóły, ograniczenia i testy: `V3.86.4-RUNDA-I-PADY.md`.
- **V3.86.3** — wdrożona przez użytkownika 27.09 od 10:23 do Desktop/ASAonly-V3.86.3.
  Poprawki odzyskiwania opisano w `V3.86.3-RECOVERY.md`. Dowody rundy Cybers 509
  10:33–10:43 są w C:/AAA/RUNDA_3.86.3_2026-09-27. ListPlayers i DoExit działały
  na wszystkich mapach (DoExit: Exiting..., ok. 0,1 s). Pierwszy start Extinction
  padł z Requested mods failed to load on server; drugiego dotyczy zachowany log
  pobrania pliku windowsserver 509. Brak logu pierwszego startu nie pozwala wskazać
  konkretnej przyczyny błędu modów; opóźnienie publikacji pliku to hipoteza.
- **V3.86.2** — po analizie logów z 26.09 (user wybrał wszystkie 3 propozycje; opis:
  `V3.86.2-DZIENNIK-W-PLIKU-I-SPOKOJNY-RESTART.md`). (1) Dziennik zdarzeń także w pliku
  `WIEDZA_O_PROGRAMIE\dziennik-zdarzen.txt` (`asaonly/dziennik_plik.py`, osobny wątek,
  data sesji/dnia, rotacja 5 × 5 MB, w ZIP-ie diagnostyki; `App._oproznij_dziennik`;
  testy → `ASAONLY_EVENT_LOG_DIR`); napis o asa_debug.log był nieprawdziwy. (2) Spokojny
  restart: `ProcedureMixin.mapa_w_restarcie` (czuwanie powrotu po DoExit) → monitor pisze
  `zamkniety_po_doexit` zamiast `pad_bez_sladu` (ślad crasha nadal PAD), OFFLINE żółty
  (`log_status(…, nazwa=)`), `TabSnapshot.restart`, CPU 1.3.2 loguje tylko przy GOTOWY.
  (3) `konsola.wylacz_szybka_edycje()` / `przywroc_tryb()` (SetConsoleMode, QuickEdit
  0x0040 off + EXTENDED 0x0080). `WERSJA_PROGRAMU` = jedna stała. CPU po READY było już
  wcześniej; High w trakcie ładowania ustawia manager (priorytet w managerze → Normal).
  Cache managera nie da się wyłączyć (SteamCMD/CDN, każda z własną ścieżką) — nie trzeba,
  przy wyłączonym „Enable automatic update checking” manager go sam nie używa.
- **V3.86.1** (plugin 88 2.0.1) — po pierwszej rundzie V3.86.0 na żywo (26.09, sprawdzone
  w logach: cache 25535041 w ok. 1,5 min, Extinction/Genesis 1/Ragnarok po 40 plików
  11238.7 MB w 9–10 s, manager wstrzymany najwyżej ok. 40 s na mapę, serwery wstały na
  „ARK Version: 93.38”, mody „valid”). Poprawki: „Missing configuration” (pierwszy przebieg
  świeżo pobranego SteamCMD, pusta appcache) = ponowienie od razu, do 2 razy co 10 s
  (zamiast 5 min); `Failed installing …`/`Missing configuration` rozpoznawane
  w content_log (V3.86.0 pisało „no entries”, choć wpis był); liczba plików przed
  kopiowaniem liczy appmanifest (było „39”, potem „40/40”). Testy: 336 (335 OK,
  1 pominięty) + 29 mutacji. Do decyzji usera (26.09): zapis dziennika zdarzeń do pliku
  (podpowiedź „zapis też w asa_debug.log” jest nieprawdziwa — tam idą tylko ukryte błędy),
  „PAD: … died quietly” po zaplanowanym DoExit, ciche [CPU] przed READY.
- **V3.86.0 „Aktualizacja serwera przez własny cache”** (prośba usera: updater ma
  działać poprawnie i nie czekać 20 min). Diagnoza 25.09 (logi): build 25535041
  o 21:29:43; 9 prób (3 mapy × 3) SteamCMD refreshera na katalogach map padło po
  ~3 s: `Failed to get manifest request code, 'Access Denied'` dla manifestu
  8699400601246504390 (zainstalowany na mapach) — ten manifest miał tylko
  SteamCMD managera (to on instalował mapy 25.09 00:42–00:48); po każdej porażce
  plugin wznawiał managera, a jego CRASH DETECTION podnosił serwer na starym
  buildzie. Updater managera (kod 3.8.2.3 przejrzany lokalnie): API
  api.asadedicatedmanager.com → cache `ASA UPDATES` jego SteamCMD (delty działają)
  → kopia CAŁEGO cache do serwerów; „Enable automatic update checking” (min.
  20 min) + pole „Update all servers … Only update cache !”; przed aktualizacją cache
  `taskkill /F /IM steamcmd.exe /T`. Teraz plugin 88 2.0.0: api.steamcmd.net co
  60 s (zapas SteamCMD co 5 min, kontrola co 60 min) → cache refreshera
  `<folder serwerów>\ASA UPDATES REFRESHER` (serwery działają, błąd = zero
  restartów, powód z content_log) → plan różnic (`asaonly/synchronizacja.py`) →
  kolejka → podmiana tylko zmienionych plików z kopią zapasową i wycofaniem
  (dziennik; po awarii cofa strażnik) → appmanifest na końcu. Updater managera
  włączony = plugin stoi (czyta tylko te klucze z user.config). Testy: 330 (329 OK,
  1 pominięty) + 23 mutacje kluczowych warunków (23 złapane). NIESPRAWDZONE na
  Windows: pierwsze pobranie cache i podmiana plików na żywo.
- **V3.85.4**: „O programie” — obaj autorzy kodu (klucze TR `about_code_desc`,
  `about_code_claude`), na prośbę usera.
- **V3.85.3**: porządek w górnej części okna (prośba usera). Pasek „Pluginy”
  (`frm_pluginy`: `btn_plugins` + `frm_plugin_actions` = `BadgeFlow`; host
  `build_main_actions` zawija, gdy ramka ma `set_badges`); „Wykonaj zaległe
  aktualizacje”/„Anuluj procedurę” w ramce Status (`frm_status_akcje`);
  „Zapisz tab” pod polami mapy (`ServerTab.btn_zapisz`) + znacznik
  `lbl_zapis` (`App._tab_niezapisany`, `_saved_tabs` aktualizowane w
  `save_tab`). Test prawdziwego okna: `tests/test_uklad_okna.py` (na 3.85.2
  „Wykonaj zaległe aktualizacje” nie była nawet zmapowana przy 900 px).
- **V3.85.2**: user zgłosił „refresher > brak odpowiedzi”. Na dysku: ostatnie zapisy
  06:45:49 (zapis ustawień CPU), brak sprawdzenia Steama o 07:02 (tik stał), manager
  działał normalnie. `_tick` drukował dziennik do konsoli z wątku Tk — zaznaczenie
  w konsoli Windows (QuickEdit) blokuje zapis, więc stawało okno i automat
  (najbardziej prawdopodobna przyczyna; konsoli usera nie widziałem). Teraz
  `asaonly/konsola.py` (`PisarzKonsoli`, osobny wątek), `App.report_callback_exception`
  → dziennik + asa_debug.log. Plugin 88: bezpiecznik fazy „zamrozony” na
  `threading.Timer` + blokada `_stan` na przejściach fazy (UI/timer/wątek pracy).
  Testy: 287 (286 OK, 1 pominięty).
- **V3.85.1**: pierwsze uruchomienie V3.85 na Windows u usera — SteamCMD pobrany,
  build 25489097 / manifest 8699400601246504390 ze Steama, „manager: dostępny”; mapy
  już aktualne (ręcznie w managerze w nocy). Poprawka: `PluginHost._activate_plugin`
  dla pluginu z `prepare()` woła `activate()`, NIE `start()` — plugin 88 dostał
  `activate()` (odzyskanie po awarii + pierwsze sprawdzenie za 60 s); `prepare()`
  nie podmienia aktywnej zamrażarki (zmiana języka = stop_all + start_all na tych
  samych instancjach); `odzyskaj_po_awarii` pomija dzierżawę żywego refreshera.
  NIESPRAWDZONE nadal: sama instalacja na Windows. Testy: 283 (282 OK, 1 pominięty).
- **V3.85 „Aktualizacja serwera przez SteamCMD”**: plugin 88
  (`PLUGINY/88_aktualizacja_serwera.py`, logika `asaonly/steam_serwer.py`,
  wstrzymanie managera `asaonly/zamrazanie.py`). Powód (logi managera usera):
  API Steama w managerze widziało nowy manifest (24.09 22:56:46), a jego updater
  CDN 26 s później „up to date”. Plugin co 20 min pyta Steama własnym SteamCMD
  (bez starego appinfo.vdf; zapas: binarny appinfo.vdf), porównuje z
  appmanifest_2430930.acf mapy; mapa GOTOWA → zlecenie restartu w kolejce;
  przed DoExit NtSuspendProcess managera, SteamCMD `app_update 2430930 validate`,
  sprawdzenie appmanifest, ZAWSZE wznowienie managera (on podnosi serwer).
  Mapa OFFLINE/CRASH albo 30 min nie GOTOWA → aktualizacja bez DoExit, kolejka
  czeka (`blokada_kolejki`). Bezpieczniki: dzierżawa JSON + strażnik
  `python -m asaonly.zamrazanie`, odzyskanie przy starcie, limity (SteamCMD 2 h,
  manager 2,5 h), 3 próby/build, wspólne instalacje pomijane. Rdzeń: zlecenia
  restartu od pluginów (`zlec_restart`, `odwolaj_zlecenia`, haki `przed_doexit`/
  `po_doexit`/`doexit_nieudany`), start z pracą pluginu bez pomiaru czasu startu.
  NIESPRAWDZONE na prawdziwym Windows: SteamCMD i wywołania ctypes (testy na
  atrapach). Szczegóły: `WIEDZA_O_PROGRAMIE/V3.85-AKTUALIZACJA-SERWERA-STEAMCMD.md`.
  Testy: 280 (279 OK, 1 pominięty) + e2e.
- **V3.84**: pełna wersja angielska — teksty spoza TR jako `t("polski", "English")`
  (`asaonly/jezyk.py`, język ustawia `App.lang`); pilnuje `tests/test_i18n.py`.
  Usunięty martwy kod po przenosinach 3.75–3.83; drobne poprawki w pluginach
  60/83/86 (`tests/test_v384.py`). Preset affinity CPU zapisywany jako id.
  Szczegóły: `WIEDZA_O_PROGRAMIE/V3.84-ANGIELSKI-I-PORZADKI.md`.
  Testy: 225 (224 OK, 1 pominięty).
- **V3.83**: plugin „Konfiguracje” (`PLUGINY/80_konfiguracje.py`) = dawny importer
  (80) + backup/przywracanie (81); przejęte wybory ON/OFF; host pomija pluginy
  wymienione w atrybucie `zastepuje` następcy (stare pliki po rozpakowaniu na
  starą wersję). Po przywróceniu backupu `App._zamknij_teraz()` — bez zapisu.
- **V3.82 „Kontrola czasu”**: plugin 87 (`PLUGINY/87_kontrola_czasu.py`,
  logika `asaonly/kontrola.py`) — kontrola ręcznych ustawień czasu tymi samymi
  regułami co procedura + podgląd fali prawdziwym planistą. Tylko odczyt,
  domyślnie ON. Szczegóły: `WIEDZA_O_PROGRAMIE/V3.82-KONTROLA-CZASU.md`.
  Testy: 206 (205 OK, 1 pominięty).
- **V3.81 „Kolejka i gracze”** (Claude, na bazie V3.80.35 z arena.ai):
  aksjomat akceleratora, sonda ListPlayers (pusta mapa od razu, bez
  komunikatów), kolejka „jeden start naraz” z ogłoszeniami „na styk”,
  czasy w tabie lokalne. Szczegóły: `WIEDZA_O_PROGRAMIE/V3.81-KOLEJKA-I-GRACZE.md`.
  Testy: `python symulacja/run_all.py` (stdlib) lub `python -m pytest`:
  176 testów, 175 OK / 1 pominięty + `symulacja/e2e_prawdziwy_app.py`.
  OTWARTE: potwierdzić odpowiedź ListPlayers pustego serwera ASA.
- Poniżej historia do 3.74 (sesje arena.ai).
- Skrót odcinka 3.67→3.72: 3.67 redakcja językowa TR; 3.68 pytanie
  o niezapisane zmiany przed przełączeniem EN/PL; 3.69/3.70 trzy JASNE
  przyciski zamykania; **3.71 „MASZYNA"** (mapa-logiki): monitor procesów
  i portów 10 s, WISI+sondy RCON, PAD4 90 s, CF-sonda 1/3/15, dziennik
  modów, WYKRYJ, klikalne kafelki, auto-kolejna tura po GOTOWY (okienko
  watch_ask wycofane), _log_buffer przywrócony (to interfejs sterownika
  symulacji — audyt3 się mylił); 3.71.1 fix crasha monitora po EN/PL
  (stan per-tab od urodzenia); 3.72 testy od strony użytkownika (debug25,
  marsz przyciskowy 54/54); 3.73 naprawy z dualnego audytu AI (inżynier
  wsteczny + admin klastra): netstat rozumie NASŁUCHUJĄCE, cf_delay między
  chunkami działa, auto_on_log PL/EN prawdziwe, DL_STUCK 20 min, chipy
  [SONDA]/[WISI!] na kafelkach (debug26 18/18); 3.74 "Biblioteka wiedzy"
  (PRZYKLAD harmonogramu w zipie, swiezy raport; logika bez zmian, debug27
  28/28). Wydane na GitHub: V3.71, V3.72, V3.73 i V3.74 (tagi -s,
  Release + zip, rotacja wersje/ trzyma 4 ostatnie; starsze w archiwum/
  w workspace).
- Nazwa programu (od 3.48): **ASAonly - (AUTO)Manual - ModRefresher (RCON)**; wersja w pliku: **3.74 "Biblioteka wiedzy"** (skrót 3.67→3.72 niżej; szczegóły 3.66 w dalszej części punktu jako historia) (3.66: tab_sec_base(name)="CONFIG_SECRET_RCON <name> - zapis" — równość z CONFIG_MAP; pętla tabów przemianowuje rodzinę sekretów po ustaleniu name; lookup po prefiksie "CONFIG_SECRET_RCON" (z nazwą i bez — import też); rename_server przemianowuje i cfg, i sec; KOREKTA usera: 3.64/3.65 dały nazwę mapy tylko w CONFIG_MAP; 3.65: _tidy_docs dokleja STARY root/asa_debug.log do WIEDZA_O_PROGRAMIE/asa_debug.log i usuwa go z roota — 3.64 zostawiał go w rootcu; wykryte DEMEM 1:1 z folderu usera; debug21 6/6 z checkiem 2b; 3.64: CONFIG_DIR/SECRET_API_DIR/KNOW_DIR + TAB_SEC_DIR_NAME="CONFIG_SECRET_RCON"; tab_cfg_base(name)="CONFIG_MAP <name> - zapis" (nazwa mapy w pliku; rename_server przemianowuje rodzinę); migrate_old_base 4-arg (przenosi do katalogu); pętla tabów: czytaj name z newest "CONFIG_MAP" → przemianuj rodzinę → sekret do podkatalogu; save_config→CONFIG_DIR, save_secrets→SECRET_API_DIR; write_debug_log→WIEDZA_O_PROGRAMIE/asa_debug.log; _tidy_docs (README/MANUAL/MAPA/PROMPT/REPORT → WIEDZA) wołane po _load_server_tabs (init + toggle_lang); import: sekret z podkatalogu LUB plik obok; ZIP: root=.py+.bat+WIEDZA_O_PROGRAMIE/; testy: debug21 5/5, debug20 5/5 (legacy→3.64); 3.63: kosmetyka struktury — stałe CONFIG_BASE="CONFIG_PROGRAM - zapis", SECRETS_BASE="CONFIG_SECRET_API - zapis", TAB_CFG_BASE="CONFIG_MAP - zapis", TAB_SEC_BASE="CONFIG_SECRET_RCON - zapis", TABS_DIR="CONFIG_MAPS_TABS"; helper migrate_old_base(directory, old_base, new_base) przemianowuje CAŁĄ rodzinę plików z zachowaniem dat; migracje w _load_config/_load_secrets + _load_server_tabs (taby→CONFIG_MAPS_TABS + per-tab); pliki NADAL obok programu; teksty TR PL/EN podmienione; test debug20 5/5; LEKCJA: testy z hardcode starych ścieżek pęknęły (debug5/6/19 + cleanup sterownika); 3.62: FIX _on_close — askyesno „Nie" było ignorowane: po pytaniu kod leciał dalej (save_config na wszystkich tabach + destroy); teraz „Nie" = return (zostań, nic nie zapisuj), „Tak" = zapisz+zamknij; treść pytania wprost deklaruje semantykę [Tak/Nie] PL/EN; FIX2: _restore_tabs po starcie zostawiało _save_pending=True (add_server podbija flagę) → pytanie o zapis przy KAŻDYM zamknięciu bez zmian; fix: _save_pending=False na końcu _restore_tabs; test debug19 3/3; 3.61: FIX toggle_lang — destroy dzieci niszczyło win_mods, a _last_mod_ids trzymało starą listę → panel modów martwy do restartu; fix: _last_mod_ids=None + _win_open["mods"]=False po _build_ui + _toggle_win przywraca okno od razu w nowym języku; FIX2 (głębszy): _restore_tabs czytało self.servers z pamięci startupu → świeże taby ZNIKAŁY po zmianie języka, edycje wracały do starego zapisu; fix: po save_config przeładować _load_server_tabs z dysku; test debug18 5/5 harness=łańcuch after na wątku głównym (odczyty Tk z wątku testowego = STALE!); 3.60: frm_status = dwa rzędy — góra frm_status_top (lbl_status/lbl_updated/chk_auto/btn_check_now, bez zmian), dół frm_leds = BadgeFlow z kafelkami "nazwa · STATUS" (Led + _chip_text tr st_* + kolor tekstu = kolor diody + ToolTip tip_map_* PL/EN, tekst tipu podmieniany w _update_led_color); _update_leds_frame buduje chipy i set_badges; zgłoszenie usera: ludzie nie rozumieli samych kolorów kropki; test debug17 8/8; 3.59: badge wait = #3d6db5 + tr "nie sprawdzono"/"not checked yet" — diody NIEBIELSKIE zapalone od razu w tabach, nie szare; zegar paska "%d s" malejąco (299 s), nie M:SS; potwierdzone grubyadmin 32/32 + live usera z kluczem API; 3.58 "Pary w logu": _loaded_mods_from_log PIERWSZA liczba z każdego fragmentu po przecinku — realny serwer wypisuje pary "mod (wersja)" → było 18 "modów", jest 9; formaty: nawiasy/podkreślnik/płaska lista/pojedyncza linia — jedna reguła dla wszystkich; GitHub: katalog wersje/ z rotacją min. 4 wersji każdego pliku + Releases nigdy nie kasowane; 3.57 "Zaczyt starych bakapów": (import_tab_from_file → dispatch: stary globalny {"servers":{nazwa:cfg}, globalne mod_ids} → _legacy_global_tabs rozbić na taby + hasła ze starego {"passwords":{}} obok; _normalize_legacy_tab (mod_ids lista→string, linie bez "on"/pary → słowniki on=True); ciało importu = _import_one_tab (zwraca True); 3.56 "Generator CF-API": (przycisk w rzędzie klucza API otwiera CF_API_KEYS_URL = https://console.curseforge.com/?#/api-keys — jedna stała dla przycisku/tooltipów/intro; 3.55 "Prosty link do kluczy": (wszędzie pełny deep link https://console.curseforge.com/?#/api-keys — goły domen w 3.53 prowadził na pulpit Studios; 3.54 "Prawdziwy serwer": (REALNY layout ASA: mody w ShooterGame/Binaries/Win64/ShooterGame/Mods/83374, foldery <ModID>_<FileID> — mods_dir_candidates() [funkcja modułowa, 4 kandydatów] + _installed_file_ids czyta oba formaty; parser loga: linia "Loading mod: X (version Y)" → tylko 1. liczba, listy z przecinkami w całości; ostrzeżenia sync_none_log {paths}/sync_empty_log; fakesrv na realnym layoucie; 3.53 "Intro w konsoli": (pierwsze uruchomienie: konsola, nie okienko — _show_first_run_hint loguje linie first_run_steps, showinfo usunięte; przycisk Załaduj-API-z-backupu = _load_api_from_backup wczytuje api_key ze wskazanego JSON; FIX open_mod_page: bez adresu z API → search?search=<id>, NIGDY cyfrowe ID w ścieżce; 3.52 "Zegar i hierarchia": (check_now zbiera mody PRZED kluczem: bez tabów/modów program nie interesuje się kluczem API, manual bez modów → cf_no_mods, ostrzeżenie o kluczu tylko gdy mody są; pasek statusu pokazuje licznik "Następne sprawdzenie: M:SS" gdy są mody — st_next_check był sierotą w słownikach, nic go nie renderowało; 3.51 "Cisza w konsoli": fix spamu "Brak klucza API" ~2/s: check_now bez klucza odrocza next_check o interwał + loguje RAZ — flaga _no_key_warned, reset przy kluczu; przycisk woła check_now(manual=True) i loguje zawsze; root cause: wczesny return omijał CF-HAMMER-fix 3.41; 3.50 "Import pod lupę": import taba weryfikuje listę modów: serwer działa → korekta wg logu od razu; serwer stoi → trwała flaga mods_unverified + jednorazowa autokorekta po starcie w _apply_tail; edycja pola / "Mody z serwera" gaszą flagę; 3.49: mody z serwera wg logu) (bajzel w katalogu Mods niewidoczny dla listy: mods_from_server czyta log serwera — App._loaded_mods_from_log, ogon 512 KB, linie load+mod → ID 6-10 cyfr; pominięte/dodatkowe logowane; fallback = folder z ostrzeżeniem; update nieużywanego moda NIE restartuje mapy; 3.48: nowa nazwa programu) (standard nazewnictwa: .py i "STARTER plus Python installer - ....bat" i "README - ....txt" pod pełną nazwą; komplecik "V<x> ASAonly - (AUTO)Manual - ModRefresher (RCON).zip" — wersja ZAWSZE w nazwie i NA POCZĄTKU (korekta usera 2026-08-29), stary zip kasowany; nazwa w app_title PL/EN, about, User-Agent; 3.47: świadomy import) (import taba z backupu z matrycą konfliktów: gdzie indziej = klasyczny import; miejsce standardowe bez taba = restore bez restartu z dedupe; tab działa = pytanie TAK/NIE, duplikat "(2)" w OSOBNYM katalogu; taby/ ładują się auto przy starcie — do tego import niepotrzebny) (3.45: czytelne nazwy plików; 3.46: przycisk "+ Tab z backupu" — import taba z pliku konfiguracji mapy: hasło z pliku sekretu obok (priorytet) lub starego pola <3.43, kolizje nazw → sufiks (2)/(3), walidacja "lines" w JSON — konfiguracja programu odrzucona; import zapisuje tab+sekret od razu; add_server(name, config) to reuse) (nazwy konfigów/sekretów: co-to-jest + data/godzina zapisu w nazwie, bez przedrostka asa; każdy zapis = nowy plik, czytany najnowszy, rotacja 10 = backupy; migracja starych nazw automatyczna; naprawiony ukryty bug 3.43: lang i _log_buffer muszą być initowane PRZED _load_server_tabs, inaczej tab pomijany po cichu) (3.43: sekrety tabów; 3.44: walidacja pozycji okna modów — śmieciowe pozycje z configu powodowały "mrugnięcie i zniknięcie", teraz centrowanie + log geometry; BadgeFlow: diody modów w tabach zawijają się do kolejnych linii przy zmianie szerokości; sekcja "Mody mapy" = 2 pełne wiersze, NIE pakować side=left obok pola wpisów — pack zabiera cały pasek)
- Wersja wcześniejsza 3.43 "Sekrety tabów" (3.42: okno logów usunięte — dziennik w konsoli ANSI + diody-chipy "numer moda" w tabach; 3.43: hasła RCON w asa_tabs/<mapa>/secrets.json + przycisk "Zapisz sekret" + backupy rotacyjne tab/globalne, migracja starych haseń automatyczna)
- Wersja wcześniejsza 3.41 "Koniec młota na API" — naprawy z grubej symulacji
  8 serwerów (baza wspólna + mody per mapa): CF HAMMER (next_check przesuwany
  zawsze — było 11 zapytań CF w 7 s przy interwale 30 s) + pętla uzgodnienia
  po ręcznym restarcie admina (nowa wersja na dysku => "godzę wersje",
  zaległość zdjęta, bez procedury). Skan dysku przy checku na wątku UI
  (installed_max przekazywany do workera — worker bez Tk/dysku).
- Pakiet na GitHub: `V3.74 ASAonly - (AUTO)Manual - ModRefresher (RCON).zip` — 9 plików (root: .py + .bat; reszta w WIEDZA_O_PROGRAMIE/; od 3.74
  z PRZYKLAD-HARMONOGRAMU-RESTARTOW-KLASTRA.md) (od 3.57 z MAPA-PROGRAMU.md): program .py, launcher .bat, MANUAL (od 3.53: dla opornych + kontekst AI),
  README.txt (pełna historia zmian), **README.md (dwujęzyczny PL/EN z
  przełącznikiem w nagłówku — pod GitHub)**, **PROMPT-ASAonly-AWARYJNY.md**
  (awaryjny prompt na przyszłość = kopia tego pliku), **SYMULACJA-REPORT-V<x>.md**.
- Wiedza o modach (doprecyzowanie usera, tura 6): **Better Horde = event
  HORD na Extinction, na innych mapach nic nie robi** (mod specyficzny
  Extinction). Ragnarok Dilo Party = tylko Ragnarok. Baza = mody QoL wszystkich
  map (Awesome Spyglass+, Ultra Stacks, Dino Storage V3, Death Helper).
- Testy (rytuał wydania): kompilacja; jednostkowe 39/39; srodowisko.py 13 OK
  (sync profil/); sterownik v6 62/62 (3 asercje dostosowane do 3.71: auto-tura,
  DoExit porzucany); debug24 8/8 (fix 3.71.1); debug25 54/54 (marsz przyciskowy);
  FUZZ debug23 11/11; pewniaki 32/32; czystość 6/6. Flota w tescior.py
  (debug5–25). Lekcja sterownikowa: krachy ŁAŃCUCHOWO, czekać na STAN DYSKU
  nie status (grace trzyma "ready" przez rotację).

## 7. ZNANE BŁĘDY / TODO
1. [NAPRAWIONE DEFINITYWNIE w 3.40] ucinane kafelki modów — stara koncepcja
   (Canvas + ręczna geometria) PORZUCONA; kafelek = zwykłe widżety.
2. [NAPRAWIONE w 3.39.1, skorygowane w 3.39.2] stałe LogTail: 2 MB / 256 KB / 15 s.
3. [NAPRAWIONE w 3.41] CF HAMMER: next_check nieprzesuwany w gałęzi "są
   update'y" => odpytywanie CF co tick przez całą procedurę/zaległość.
4. [NAPRAWIONE w 3.41] pętla uzgodnienia: known_versions niepodbite przy
   wersji zainstalowanej ręcznie przez admina => "ma nową wersję" w kółko.
5. [OTWARTE] RCON retry nie łapie zerwania PO auth (pusta odpowiedź =
   sukces); retry 3x tylko dla connect/auth.
6. [OTWARTE] uzgodnienie ciche: recon_log/parked_log nieużywane, brak
   komunikatu "mapa X wróciła / zaległość zdjęta" (kosmetyka).
7. [OTWARTE] kosmetyka czuwania: mapa bez restartu = "GOTOWY 0 s" od razu;
   "KLASTRA GOTOWY" logowane także przy FAILED mapy (grace może zamaskować
   śmierć mapy w czuwanie).
8. [ZAMKNIĘTE JAKO PROJEKTOWA DECYZJA] known_versions globalne per mod
   (spójne z PTK 10 — serwer przez CFCore dogrywa przy starcie).
9. [NAPRAWIONE w 3.73] `_cf_worker` przekazuje cf_delay do
   `cf_get_mods_batch` — między chunkami po 50 modów jest drzemka
   (cap 60 s, tylko gdy kolejny chunk istnieje).
10. [NAPRAWIONE w 3.71] martwy kod `extract_version()` usunięty (z audytu 1).
11. [OTWARTE — DECYZJA USERA] panele "w bryle" (PTK 15; propozycja:
   wm_transient; NIE ruszać bez specu usera).
12. [NAPRAWIONE w 3.73] tekst TR `auto_on_log` PL/EN mówi teraz wprost,
   że update'y startują same (kolejna tura 60 s po GOTOWY) — zgodnie
   ze stanem faktycznym od 3.71 (auto-tura bez pytania).
13. [ROZWIĄZANE w 3.81] plugin RCON ma `enqueue_raw` — callback dostaje
   (błąd, odpowiedź); kolejka liczy graczy z ListPlayers. Tekst pustego
   serwera ASA NIEPOTWIERDZONY („No Players Connected” znane z ASE) —
   surowa odpowiedź w dzienniku, wzorce w `listplayers_pusto`.


## 8. NOTY ŚRODOWISKOWE (dla asystenta)
- Sandbox asystenta = Linux bez GUI: programu tkinter NIE uruchamiamy
  graficznie; weryfikacja = `python3 -m py_compile` + analiza AST +
  ewentualne testy logiki bez GUI. Docelowe środowisko usera = Windows.
- User pytał o formaty: **.webp = obrazek** (ok dla zrzutów ekranu UI),
  **PDF czytelny ale "zamrożony"** (zły na żywe notatki), **.md/.txt =
  właściwy format** notatek/kontekstu. Ten plik trzymamy w .md.
- Linia bazowa kodu V3.39 jest w workspace jako
  `ASAonly - ManualModRefresher.py` (1:1 z sesji poprzedniej).
- EDYCJE PLIKÓW (lekcja z 2026-08-28): NIGDY wiele równoległych edit_file na
  TYM SAMYM pliku (wzajemne nadpisywanie + korupcja). Zmiany w .py robić
  sekwencyjnie albo JEDNYM skryptem python z asercjami liczności wzorców
  przed zapisem (i ZIP budować dopiero po zielonej weryfikacji).

## 9. HISTORIA SESJI (skrót; pełna w NOTATNIK-PROJEKT.md)
- 2026-08-28 (sesja 1 kontynuacji): przejęcie projektu po śmierci poprzedniej
  rozmowy. Przeniesiono .py/.bat/README, weryfikacja OK, znaleziono bug
  3 stałych, założono pliki kontekstowe. Zmian w kodzie NIE robiono.
- 2026-08-28 (tura 3): WYDANIE 3.39.1 — stałe LogTail przywrócone, wersje
  podbite (tytuł/About/UA), README uzupełnione (3.39 + 3.39.1), zip
  ASAonly-v3.39.1.zip. Awaria równoległych edycji zdiagnozowana i naprawiona
  skryptem z asercjami; pełna weryfikacja po naprawie.
- 2026-08-28 (tura 4): user ręcznie odzyskał materiały z martwej sesji
  (analiza architektury "blizn", PTK 10/11/15, diagnoza kafelków). WYDANIE
  3.39.2: kafelki naprawione (jednokierunkowa geometria), stałe LogTail do
  oryginału (2 MB / 256 KB / 15 s), README + zip v3.39.2. Rationale i zasady
  wchłonięte do sekcji 4a.
- 2026-08-28 (tura 5): WYDANIE 3.40 "To tylko okno" — okno modów zbudowane
  OD NOWA na zwykłych widżetach (porzucona koncepcja Canvas, nie "naprawiona");
  kółko myszy; README + zip v3.40. User ujawnił: utknięcie na oknie = moje
  wcześniejsze wcielenie; przyjęta zasada 7 ("porzucaj, nie pogłębiaj").

## 8. ROZUMIENIE PROGRAMU (rozbudowane na życzenie usera — "co robiłem
   z poprzednim konsultantem"; mapa dla każdej przyszłej sesji)

### 8.1 Czym program JEST (jedno zdanie)
Monitor modów CurseForge dla wielu serwerów ARK: Survival Ascended z JEDNEGO
okna — gdy CurseForge pokaże nową wersję moda, program ogłasza graczom
(ServerChat), w kolejce restartuje mapy przez RCON (DoExit), a właściwe
pobieranie/instalację modów robi SAM SERWER przy starcie (wbudowany CFCore;
proces po DoExit podnosi ASA Dedicated Manager). Program NIE pobiera modów
sam — jest "dyspozytorem" i AKCELERATOREM (PTK 10).

### 8.2 Model wątków (krytyczny — tu łatwo o pomyłkę)
- Tk mainloop biegnie w WĄTKU GŁÓWNYM (jak w produkcji). `update()` wołane
  z obcego wątku łamie `after_idle` — NIE robić tego.
- Workery sieciowe/dyskowe: `App.run_async` (daemon threading.Thread).
- Powroty do UI: `App.post_ui(f)` = `after_idle(f)` — sprawdzono na żywu
  (debug1.py): wywołanie after_idle z wątku działa.
- Log w 100% bezpieczny dla wątków (Queue, od 3.39).
- Druga instancja App (testy): po DoExit pierwszej wymaga `after(0, _on_close)`.

### 8.3 Mapa pliku (jeden .py, ~200 KB, stdlib only; numery linii orientacyjne, stan ≈ 3.7x)
- `write_debug_log` (94), `sanitize_name` — pomocnicze.
- TR: dwa pełne słowniki PL/EN (klucz → tekst, `tr()` formatuje kwargsami).
  Nowy tekst = DODAJ OBA KLUCZE (PL i EN) — inaczej w dzienniku wyświetli się
  goły klucz (tak było z `cf_synced` — lekcja z tury 6).
- Sieć: `RCONClient` (530) — prawdziwy protokół Source RCON; `rcon_send`
  (600); `cf_request` (User-Agent: ModRefresher(RCON)/3.74,
  klucz API CurseForge); `cf_get_mods_batch` (636) — JEDEN POST /v1/mods,
  chunki po 50 ID; latest = max(id) z latestFiles.
- `open_log_shared` (702) — otwieranie logu zajętego przez serwer (Windows).
- `LogTail` (746, threading.Thread) — ogon logu serwera: przy starcie skan
  ostatnich INITIAL_SCAN_BYTES=2 MB (heurystyka BIG_LOG_BYTES usunięta
  w 3.80 — patrz 4a); poll stały 0,5 s (po rotacji
  loga drzemka 1 s); grace
  15 s (w trakcie rotacji logu status się nie zmienia — stąd "ready" trzyma
  się przez restart!); statusy: starting / loading_mods / engine / ready /
  crash; KRACHLOOP: 3 krachy w 15 min (CRASHLOOP_COUNT/WINDOW_S), licznik
  transition-coś→crash (nie wystąpienia!), reset przy ready.
- Klocki UI: `RconLineRow` (971), `Led` (1029), `ToolTip` (1044),
  `ModTile` (1095; 3.40 — ZWYKŁE widżety, zero canvasowej geometrii),
  `ModBadge` (1192).
- `ServerTab` (1212) — jedna MAPA: katalog logu, RCON (host/port/hasło),
  pole "mody własne" (puste = lista globalna; `get_effective_mod_ids`),
  przełącznik map_on, `_crash_times`, własny katalog configu.
- `write_json_atomic` (1671) — zapisy konfigu bez ryzyka połówki pliku.
- `App` (1693):
  * trwałość (od 3.63/3.64): `CONFIG_PROGRAM/` (globalne),
    `CONFIG_SECRET_API/` (klucz API — NIE do repo), `CONFIG_MAPS_TABS/<mapa>/
    CONFIG_MAP <mapa> - zapis <data>.json` (BEZ hasła) + `CONFIG_SECRET_RCON/
    CONFIG_SECRET_RCON <mapa> - zapis <data>.json` (hasło); pliki z datą
    w nazwie, rotacja 10 = backupy; migracja starych nazw automatyczna;
    wszystko obok programu, root czysty (tylko .py i .bat).
  * `_tick` (2535, co 0,5 s): auto-check gdy `now >= next_check` i nie
    trwa check; `_tick_restart_timeline` (2555) realizuje harmonogram.
  * `check_now` (2674): zbiera mod_ids z tabów z map_on; skan dysku
    `installed_max` (3.41, NA WĄTKU UI — worker nie dotyka Tk/dysku);
    `run_async(_cf_worker, ...)`.
  * `_cf_worker`: batch → per mod: first-see (zapamiętano) / update
    (ma nową wersję) / `cf_synced` (3.41: wersja już na dysku → godzenie) /
    ok; wynik przez `post_ui(_cf_done)`.
  * `_cf_done`: next_check przesuwany ZAWSZE (3.41 — CF HAMMER);
    pending_updates; automat: watch trwa → PARKUJ, else `_exec_pending`;
    automat wył. → log "trafią do ZALEGŁOŚCI".
  * `_verify_local_mods`: zdejmuje zaległości, gdy na dysku leży wersja
    ≥ znanej (działa przy "brak update'ów").
  * `_exec_pending` (procedura): per mapa używająca update'owanych modów —
    niesiągające mapy dostają "pominięto — mapa nie używa"; od 3.81 linie
    harmonogramu lokalne dla mapy, rozjazd robi Kolejka; guard: mapa CRASH →
    "POMINIĘTO", mapa niegotowa → "WSTRZYMANO DoExit" (wraca przy następnym
    sprawdzeniu CF); known_versions podbijane dopiero po weryfikacji,
    `_start_return_watch` (czuwanie powrotu: watch_maps, timeout w MINUTACH,
    domyślnie 20 — pole "Czuwanie (min)"; "NIE wrócił … sprawdź serwer!").
- Stałe: MIN_CHECK_INTERVAL=30 s, DEFAULT_CHECK_INTERVAL=300 s,
  MAX_RCON_LINES=20, chunk CF=50, CRASHLOOP=3/15 min, LogTail 2 MB/256 KB/15 s.

### 8.4 Dekompozycja mody↔mapy (doprecyzowanie usera, tura 6)
- BAZOWE (QoL, wszystkie mapy): Awesome Spyglass+, Ultra Stacks, Dino
  Storage V3, Death Helper Reloaded. Update moda bazowego = procedura na
  WSZYSTKICH żywych mapach.
- SPECYFICZNE per mapa: np. **Better Horde = EVENT HORD na Extinction,
  na innych mapach NIC nie robi**; Ragnarok Dilo Party = tylko Ragnarok.
  Update moda specyficznego = procedura TYLKO na jego mapie, reszta
  "pominięto". Pole "mody własne" w tabie mapy to obsługuje.

### 8.5 Infrastruktura testowa (katalog symulacja/)
- `fakesrv.py`: FakeCF (atrapa CurseForge; `.requests` = co PRZYSZŁO,
  `.served` = co ODDAŁA i kiedy — telemetria niezbędna do debugu detekcji),
  FakeRCON (prawdziwy Source RCON po stronie serwera), FakeArk (folder
  serwera: logi + Mods/83374/<ModID>/<FileID>.mod; boot z quick_fatal ma
  okno ładowania 2,6 s > backoff LogTail 2,0 s, inaczej krachy znikają
  z licznika; pliki modów lądują na dysku PRZED linią READY — jak w prawdziwym
  serwerze (CFCore); grace trzyma "ready" przez rotację loga → w testach czekać na STAN
  DYSKU, nie na status).
- `jednostkowe.py` — 39/39; `sterownik.py` (v6) — GRUBA SYMULACJA 62/62;
  `debug23.py` FUZZ 11/11; `debug24.py` 8/8 (3.71.1); `debug25.py` marsz
  przyciskowy 54/54
  (8 serwerów, fazy 1-6 + X; krachy ŁAŃCUCHOWO: kolejny dopiero po
  zarejestrowaniu poprzedniego przez program).
- Uruchomienie: `cd symulacja && xvfb-run -a python3 -u jednostkowe.py`
  oraz `xvfb-run -a -s "-screen 0 1600x1000x24" python3 -u sterownik.py`
  (wyjście → plik, potem czytać $? — nie przez tail|echo).
- `profil/` = kopia programu pod testy — PO KAŻDEJ edycji oryginału
  skopiować i usunąć profil/__pycache__.

### 8.6 Żelazne zasady techniczne (zebrane z wpadek)
1. Równoległe edit_file na JEDNYM pliku = race i utrata edycji (cf_synced!) —
   edycje sekwencyjnie albo skrypt z asercjami.
2. Mainloop Tk w wątku głównym; z wątku tylko post_ui/after_idle.
3. Test mierzy STAN (dysk/telemetria), nie sam status UI (grace kłamie).
4. Przerwany bash NIE zabija procesu — przed runem sprawdzić ps aux |
   grep sterownik; sterownik ma .sterownik.lock (pid), dwa równoległe
   runy = fałszywe faile (dowód: "godzenie" zamiast parkowania, 2026-08-28).
5. Debugi GUI: pompowanie update() gubi after_idle z wątków (LogTail) —
   używać mainloop + wątek scenariusza (jak sterownik); showinfo hint 1.
   uruchomienia blokuje headless (neutralizować w harnessie).
6. Zdarzenia symulacji planować względem STANÓW programu, nie sztywnych
   czasów (t59 liczył się od końca poprzedniego wait_for — stąd "zagadka
   parkowania" z runu C).

## 10. INFRASTRUKTURA WYDAWANIA I NARZĘDZIA (workspace asystenta, od tur 40+)
- **Rytuał wydania** (każda wersja): py_compile → jednostkowe 39 →
  `symulacja/srodowisko.py` (sync profil/) → sterownik v6 62 → debugy
  (23/24/25) → `pewniaki/test-pewniakow.py` 32 → `pewniaki/test-czystosci.py`
  6 (po biegach `--sprzataj`) → raport `SYMULACJA-REPORT-V<x>.md` →
  komplecik 9 do zipa → `wydawacz.py V<x> --dry-run` → pełne wydanie.
- **wydawacz.py**: klon repo → komplecik na main + `wersje/V<x>` → tag -s
  (GPG, FPR 0135EAD0…) → Release + zip → rotacja `wersje/` (max 4) →
  plakietka Verified. Komplecik 8: .py, .bat, README.txt, README.md, MANUAL,
  MAPA-PROGRAMU, PROMPT-AWARYJNY, SYMULACJA-REPORT (root zipa: .py + .bat,
  reszta w WIEDZA_O_PROGRAMIE/).
- **archiwizator.py** (żywe archiwum w `archiwum/`): `stan "opis"`
  (migawka produktu + raport + METRYKA, rotacja 30), `wydanie V<x>`
  (rozpakowany zip), `historia` (mirror tagów z GitHuba), `indeks`
  (INDEKS.md z sha256). NAWYK: stan po zielonym rytuale i PRZED serią łatek.
- **Wersjonowanie**: V3.71.1 dozwolone (3 człony) — test-pewniakow i
  archiwizator rozumieją pełny ciąg.
- **KOZAK** (gemini-3.5-flash, `kozak.py`): druga para oczu przy audytach;
  przekaz znak w znak zdania usera; propozycje WERYFIKOWAĆ przed wdrożeniem
  (bilans: 24 twierdzenia → 18 prawd); zakaz bibliotek zewnętrznych
  (stdlib-only), gpt-oss zabroniony.
