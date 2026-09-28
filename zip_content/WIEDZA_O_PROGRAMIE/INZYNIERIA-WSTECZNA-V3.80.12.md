# Dokładna inżynieria wsteczna ASAonly ModRefresher V3.80.12

Data audytu: 2026-09-20  
Punkt Git: `830d126` + kod V3.80.12  
Zakres: rdzeń, monitor, CurseForge, wersje serwerowe, procedury RCON, koordynator, zapis konfiguracji i pluginy.

## 1. Rzeczywisty model programu

Program jest aplikacją Tk uruchamianą z jednego pliku wejściowego, ale część zachowania deleguje do modułów `asaonly/`. Główne pętle są wywoływane co 500 ms. Co około 10 s worker monitora zbiera mapę port→PID i wiek logów. Osobny `LogTail` na każdy tab śledzi `ShooterGame.log`. Kontrola CurseForge działa okresowo w workerze. Pluginy są ładowane dynamicznie z `PLUGINY/` i otrzymują ograniczone API, ale pluginy repozytoryjne mogą pobrać aplikację.

Ścieżka aktualizacji jest następująca:

1. Z aktywnych tabów zbierane są wszystkie ID modów.
2. Batch CurseForge zwraca najnowszy file ID.
3. Wynik jest porównywany przede wszystkim z globalnym `known_versions`.
4. Dla wykrytej różnicy powstaje `pending` z listą wszystkich aktywnych tabów używających moda.
5. Koordynator buduje kolejkę map z pending.
6. Każda mapa wykonuje własne, niezmieniane czasy RCON.
7. Po skutecznym `DoExit` program czeka na wzrost `_boot_seq` i READY.
8. Po READY `_verify_local_mods()` porównuje pending z rejestrem/plikiem na dysku.
9. Dopiero po usunięciu pending bieżącej mapy rusza następna.

## 2. Założenia główne — wynik

| Założenie | Wynik | Uzasadnienie |
|---|---|---|
| Monitoring jest równorzędną funkcją programu | CZĘŚCIOWO | Istnieją log tail, PID/port, WISI, crash i RCON probe, ale zniknięcie wcześniej widzianego portu nie daje pewnego OFFLINE. |
| Kontrola CurseForge i wersji serwerowych jest skuteczna | NIE | Pierwszy odczyt CF zapisuje najnowszy file ID jako `known` bez porównania z wersją serwera. Parametr `installed_max` jest liczony i przekazywany, ale worker go nie używa. |
| Procedury RCON są równorzędną funkcją | TAK, Z ZASTRZEŻENIAMI | Harmonogram, walidacja, kolejka i RCON istnieją. Decyzja, która mapa wymaga procedury, jest jednak zbyt szeroka. |
| Procedura działa tylko na serwerze, który jej wymaga | NIE | `targets` jest tworzone z każdego aktywnego taba zawierającego ID moda. Sam fakt używania moda staje się kwalifikacją do procedury. |
| Serwer niewymagający procedury nie jest restartowany | NIEGWARANTOWANE | Brakuje per-mapowego porównania wersji przed utworzeniem kolejki. |
| Czasy wpisane przez użytkownika pozostają lokalne i niezmienione | TAK | V3.80.5 usunęła błędne rebazowanie. Test 205 s potwierdza zachowanie czasu. |
| Tylko jedna mapa wykonuje ciężką procedurę naraz | TAK | Wymagany koordynator jest właścicielem queue/current; następna mapa nie rusza przed terminalnym wynikiem poprzedniej. |
| Upływ czasu lub samo DoExit nie oznacza sukcesu | TAK | Wymagany jest nowy `_boot_seq`, READY i weryfikacja lokalna. |
| READY pochodzi z wiarygodnego stanu serwera | NIE ZAWSZE | Przy inicjalnym skanie duży log bez rozpoznanego markera jest uznawany za READY wyłącznie z powodu rozmiaru pliku. |
| Refresher nie uruchamia procesu za managera | TAK | Nie znaleziono wywołania uruchamiającego proces ASA. |
| Martwy serwer dostaje NIE MA/OFFLINE i monitoring trwa | NIEGWARANTOWANE | Gdy port znika z bieżącego `netstat`, `_tab_alive()` zwraca `(True, None)`. Monitor nie pamięta ostatniego PID/portu. Log może nadal istnieć i pozostać READY. |
| Pusta zaznaczona linia RCON jest ignorowana, półpełna jest błędem | TAK | `validate_rcon_line_values()` realizuje dokładnie tę politykę. |
| Plugin OFF nie wykonuje pracy automatycznej | W WIĘKSZOŚCI TAK | Tiki i hooki pluginów opcjonalnych sprawdzają enabled. Panele ręczne są rozdzielone od tła. |
| Importer nie działa w tle i skanuje dopiero na żądanie | TAK | ON tylko udostępnia panel. Skan jest jawny i źródło tylko do odczytu. |
| Diagnostyka pluginów nie udaje testu funkcjonalnego | TAK | Wynik jest opisany jako diagnostyka techniczna, uruchamiana po starcie i zmianie języka. |

## 3. Usterki krytyczne

### P0.1 Pierwszy odczyt CurseForge może ukryć realnie nieaktualne serwery

W `_cf_worker()` brak `known_versions[mid]` powoduje zapisanie najnowszego CF file ID jako stanu znanego i ustawienie moda na OK. Nie następuje porównanie tego file ID z każdą mapą. `check_now()` oblicza `installed_max`, a następnie przekazuje je do workera, lecz worker nie wykorzystuje tej wartości.

Skutek: świeża instalacja, import bez wcześniejszego `known_versions` albo utrata konfiguracji może uznać stary serwer za zgodny z CF i nigdy nie utworzyć pending.

Wymagana naprawa: pierwszy odczyt CF ma być baseline tylko dla metadanych CF. Stan każdej mapy musi być osobno porównany z dowodem wersji załadowanej/ukończonej instalacji. `known_versions` nie może zastępować stanu serwerów.

### P0.2 Mapa jest kwalifikowana do restartu tylko dlatego, że używa moda

`_targets_for_mid()` zwraca wszystkie aktywne taby zawierające ID. `_add_or_update_pending()` zapisuje tę listę bez wcześniejszego per-mapowego sprawdzenia, czy dana mapa już ma oczekiwany file ID albo w ogóle wymaga bieżącej procedury.

Skutek: aktualizacja jednego moda może skierować do kolejki każdy serwer używający moda, wbrew głównemu założeniu „restart tylko tam, gdzie wymagany”.

Wymagana naprawa: pending musi przechowywać wyłącznie mapy z potwierdzoną różnicą `loaded/installed < CF`. Stan nieznany nie może automatycznie oznaczać restartu; ma być jawnie oznaczony jako wymagający diagnostyki/decyzji.

### P0.3 Zniknięcie portu nie oznacza OFFLINE

`_tab_alive(tab, pid_map)` zwraca `(True, None)`, gdy portu nie ma w bieżącym wyniku. To jest bezpieczne przy pierwszym niepełnym skanie, ale błędne po wcześniejszym autorytatywnym wykryciu procesu. Monitor nie zachowuje ostatniego PID per mapa.

Dowód charakterystyczny bieżącego kodu: pusta mapa PID dla portu 27020 daje `(True, None)`.

Skutek: martwy proces może pozostać w GUI jako GOTOWY, jeżeli istniejący plik logu nie znika i nie dostaje nowej linii.

Wymagana naprawa: pamiętać ostatni autorytatywny PID/StartTime. Po zniknięciu wcześniej widzianego portu pokazać NIE MA/OFFLINE, nadal monitorować i nie próbować uruchamiać procesu. Nie dodawać bramki recovery poza zachowaniem managera.

### P0.4 Duży log może zostać uznany za READY bez markera

`LogTail._infer_initial_state()` przy braku rozpoznanego markera ustawia READY, jeśli plik przekracza `BIG_LOG_BYTES`.

Dowód charakterystyczny: tekst bez markera + rozmiar większy od progu daje `ready`.

Skutek: stary, duży lub nietypowy log może fałszywie pokazać GOTOWY. W połączeniu z P0.3 osłabia to bramkę koordynatora.

Wymagana naprawa: brak markera oznacza UNKNOWN/STARTING, nigdy READY na podstawie samego rozmiaru.

## 4. Wysokie ryzyko

### P1.1 Weryfikacja po restarcie potwierdza dysk, niekoniecznie wersję załadowaną przez nowy proces

`_verify_local_mods()` korzysta z `_installed_file_ids()`. Funkcja preferuje `library.json`, ale scala go z nazwami katalogów i plików `.mod`, wybierając wyższy file ID. Tymczasem `ServerTab` zbiera również `_server_versions` z rzeczywistych zdarzeń startowych, lecz weryfikator ich nie używa.

Skutek: obecność nowszego artefaktu na dysku może wyczyścić pending nawet wtedy, gdy nowy proces nie potwierdził załadowania tej wersji.

Zalecenie: po nowym boocie priorytetem ma być para mod/file ID z bieżącego logu procesu. `library.json` może być dowodem instalacji, nie dowodem załadowania. Fallback dyskowy musi być jawnie oznaczony jako niepewny i nie powinien sam otwierać następnej mapy.

### P1.2 `_boot_seq` jest statusem logowym, a nie tożsamością procesu

Licznik rośnie przy przejściu READY→STARTING/LOADING/ENGINE/OFFLINE. Nie przechowuje PID ani StartTime. Jest lepszy od samego statusu, ale może zostać zwiększony przez nietypową sekwencję linii w tym samym procesie.

Zalecenie: dowód nowego bootu powinien łączyć co najmniej zmianę PID/StartTime albo autorytatywne zniknięcie starego procesu z markerami startu nowego procesu.

### P1.3 Diagnostyczny ZIP nie wykonuje rekursywnej redakcji wartości

Plugin nie dołącza katalogów sekretów, ale kopiuje wszystkie JSON-y `CONFIG_PROGRAM` bez rekursywnego filtrowania kluczy. Obecny układ przechowuje API i RCON osobno, więc aktualnie typowe sekrety są poza paczką, jednak deklaracja „po usunięciu sekretów” jest szersza niż implementacja.

### P1.4 Przywracanie ZIP jest znacznie bezpieczniejsze, ale brak testu realnej awarii pomiędzy podmianami katalogów

Jest staging, walidacja i rollback. Nadal nie ma terenowego testu przerwania procesu/utraty zasilania w każdej fazie wielokatalogowej podmiany.

## 5. Ryzyka użytkowe i techniczne

- `Dysk / Katalogi` wykonuje pełny `os.walk()` w wątku GUI i automatycznie przy otwarciu panelu; duży katalog może zamrozić okno.
- `RCON Admin` wykonuje `int(port)` przed workerem bez obsługi błędu; błędny port może wyrzucić wyjątek w callbacku Tk.
- `Analizator logów` pokazuje „Analiza OK”, mimo że analizuje tylko ostatnie 4 MB i proste regexy.
- W kodzie pozostaje około 108 szerokich `except Exception`, część bez widocznego raportu. Zwiększa to ryzyko pracy w stanie zdegradowanym bez informacji.
- Plik wejściowy nadal ma około 1942 linii, a plugin CPU około 704; podział monolitu jest częściowy.
- Testy Linux/symulacyjne nie wykonują rzeczywistych operacji Windows API, Tk pod obciążeniem, netstat/tasklist, RCON ani ASADedicatedManager.

## 6. Elementy potwierdzone jako zgodne

- Manualne czasy RCON nie są rebazowane ani modyfikowane.
- Dokładna komenda `DoExit` jest odróżniana od tekstu czatu zawierającego to słowo.
- Koordynator uruchamia jedną mapę naraz i zatrzymuje kolejkę przy błędzie/niepotwierdzonym powrocie.
- Błędna wymagana mapa nie blokuje automatycznie pozostałych, zgodnie z decyzją użytkownika.
- Pusta linia jest ignorowana, półpełna blokuje daną mapę.
- Refresher nie uruchamia procesu ASA.
- Importer jest funkcją jawną, nie skanuje w tle i po imporcie czyści wyniki.
- CPU pozostaje osobnym pluginem, pokazuje stan i nie zapisuje, gdy korekta nie jest potrzebna.
- Opcjonalne pluginy mają prawdziwe ON/OFF, a required nie można wyłączyć.
- Status i historia są połączone w jeden plugin z migracją ustawień i rotacją.

## 7. Ocena testów

Bieżący zestaw: 82 testy zaliczone. Test stresowy obejmuje 500 syntetycznych cykli aktualizacji i kolejki. Zestaw dobrze chroni mechanikę kolejki, czasy RCON, routing syntetycznych pending, importer i część CPU.

Nie chroni czterech P0 opisanych wyżej, ponieważ fake serwery dostają gotowe pending oraz sztucznie ustawiane wersje. Symulacja zaczyna się po decyzji, że mapa wymaga procedury, więc nie testuje poprawności tej decyzji. Nie symuluje też utraty portu po wcześniejszym PID ani dużego logu bez markera.

## 8. Wniosek

V3.80.12 nie powinna być uznana za w pełni zgodną z głównymi założeniami produkcyjnymi. Koordynacja po utworzeniu pending jest znacznie bezpieczniejsza, ale wcześniejsza decyzja „kto naprawdę wymaga procedury” oraz monitorowanie śmierci procesu mają krytyczne luki.

Kolejność napraw:

1. Per-mapowy model wersji i poprawny pierwszy odczyt CF.
2. Pending tylko dla map z potwierdzoną potrzebą procedury.
3. Pamięć PID/StartTime i prawdziwy OFFLINE po zniknięciu.
4. Usunięcie heurystyki „duży log = READY”.
5. Weryfikacja wersji załadowanej w nowym procesie przed przejściem kolejki.
6. Dopiero potem terenowe testy Windows/ASADedicatedManager/RCON.
