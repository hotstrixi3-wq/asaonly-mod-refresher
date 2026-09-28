# PEŁNA ANALIZA WSTECZNA — ASAonly ModRefresher V3.74.1

**Data analizy:** 2026-09-20  
**Repozytorium:** `hotstrixi3-wq/asaonly-modrefresher`  
**Commit:** `ee67d028f3cf76ad3b5940b7890d5468df06a965`  
**Kod:** pojedynczy plik Python, 4530 linii; nagłówek i UI podają V3.74, repo opisuje V3.74.1.  
**Metoda:** analiza statyczna całego kodu i dokumentacji repozytorium. Informacje o logach oraz zachowaniu ASA/Managera przyjęto z dostarczonych obserwacji użytkownika. Bieżącej konfiguracji produkcyjnej nie ma w repozytorium, więc nie rekonstruowano nazw map, portów ani harmonogramów.

---

## 1. Werdykt wykonawczy

Program ma sensowny rdzeń operacyjny i wiele zabezpieczeń powstałych po realnych awariach, ale jego model wersji modów i potwierdzania powodzenia procedury jest niespójny.

### Najważniejsze fakty

1. Refresher **nie pobiera modów i nie zarządza procesami**. Wysyła RCON, czyta logi, odpytuje CurseForge i ogląda katalog modów.
2. Serwer ASA przy starcie sam obsługuje paczki przez CFCore; manager odpowiada za uruchomienie i ponowne postawienie procesu.
3. Program realizuje trzy zadania: monitor stanu, kontrola wersji oraz procedura RCON.
4. Monitorowanie stanu jest rozbudowane, lecz tożsamość procesu opiera na porcie RCON i nie sprawdza duplikatów.
5. Lista używanych modów pochodzi z logu, ale wersje nie: parser świadomie wyrzuca drugi numer pary `mod (fileId)`.
6. Wersja z CF jest wybierana jako `max(id)` ze wszystkich `latestFiles`, bez wyboru paczki `-windowsserver`.
7. Stan lokalny jest odczytywany z nazw katalogów/plików `.mod`; program nie czyta `library.json` CFCore.
8. Detektor pobierania szuka tekstu `Downloading mod`, którego nie ma w dostarczonych rzeczywistych logach CFCore.
9. Zaznaczony pusty wiersz RCON unieważnia mapę, a błąd jednej mapy zatrzymuje całą procedurę.
10. **Błąd krytyczny:** po przejściu osi czasu program podnosi `known_versions` i kasuje zaległość nawet wtedy, gdy `DoExit` został zablokowany, pominięty lub RCON zwrócił błąd.
11. Czuwanie obejmuje wszystkie aktywne mapy z logiem, również mapy niedotknięte daną procedurą. Mapa już GOTOWA może zostać natychmiast uznana za „powróconą”.
12. Dokumentacja błędnie przypisuje managerowi pobieranie modów i zbyt mocno utożsamia „log = prawda” ze stanem wersji.

### Ocena ryzyka

| Obszar | Ocena |
|---|---|
| Odczyt logu i podstawowy status | dobry, z ważnymi heurystykami |
| RCON i izolacja map | dobry fundament |
| Wykrycie aktualizacji na CF | działa jako detektor zdarzeń, ale śledzi niewłaściwy artefakt |
| Weryfikacja wersji na serwerze | niepełna i logicznie niespójna |
| Potwierdzenie sukcesu restartu | krytycznie niewystarczające |
| Współpraca z harmonogramem managera | brak koordynacji |
| Ochrona SSD | pośrednia; zależy wyłącznie od ręcznych czasów RCON |
| Refaktoryzowalność | niska przez klasę `App` liczącą ok. 2275 linii |
| Dokumentacja blizn | wartościowa, ale częściowo oparta na błędnym modelu managera |

---

## 2. Rzeczywisty podział odpowiedzialności

### CurseForge

Publiczne API mówi, jakie pliki są dostępne dla moda. Nie jest źródłem wiedzy o tym, co konkretny serwer zainstalował lub załadował.

### Serwer ASA / CFCore

Na podstawie dostarczonych logów:

- inicjalizuje CFCore przy starcie,
- używa własnego klucza API,
- porównuje rejestr lokalny z wydaniem,
- instaluje paczkę serwerową,
- dopiero później wywołuje `UShooterEngine::LoadGameMods`,
- nie aktualizuje załadowanych modów podczas normalnej pracy.

Wniosek operacyjny: nowa wersja wchodzi do działającej rozgrywki dopiero przez ponowne uruchomienie procesu.

### ASA Dedicated Manager

Według danych użytkownika:

- uruchamia swoje procesy,
- monitoruje je i stawia po zakończeniu,
- aktualizuje build serwera,
- nakłada priorytet CPU około 25 sekund po starcie,
- ma własne harmonogramy restartów,
- nie kontroluje wersji modów na CurseForge.

### Refresher

Kod potwierdza, że:

- nie wywołuje `kill`, `taskkill`, SteamCMD ani instalatora modów,
- nie zapisuje do katalogów gry,
- wysyła komendy RCON,
- czyta `ShooterGame.log`, procesy/porty oraz katalogi modów,
- odpytuje publiczne API CF,
- utrzymuje swój stan `known_versions` i `pending_updates`.

---

## 3. Architektura aktualnej wersji

### Moduły faktyczne w monolicie

| Zakres | Linie orientacyjne | Odpowiedzialność |
|---|---:|---|
| stałe i tłumaczenia | 1–716 | konfiguracja, teksty PL/EN |
| RCON | 717–796 | protokół Source RCON |
| CurseForge/HTTP | 803–874 | batch `/v1/mods` |
| odczyt współdzielony i ścieżki modów | 877–942 | log Windows, kandydaci katalogów |
| `LogTail` | 945–1167 | śledzenie logu i status mapy |
| widgety | 1174–1484 | wiersze, diody, kafelki |
| `ServerTab` | 1487–2052 | model/UI mapy, kolejka RCON, linie procedury |
| zapis i funkcje czyste | 2059–2241 | JSON, rotacje, netstat, dziennik |
| `App` | 2244–4518 | UI, konfiguracja, monitor, CF, procedura, watch |

`App` skupia około połowy programu i miesza stan domenowy, Tk, wątki, I/O, harmonogram oraz reguły biznesowe.

### Wątki

- Tk/UI: tik co 500 ms, decyzje procedury, większość zmian UI.
- Jeden `LogTail` na mapę.
- Jeden worker RCON na mapę — ważna izolacja.
- Worker monitora co 10 s.
- Worker CurseForge.
- Dodatkowe krótkie workery sond i ręcznych operacji.

Kontrakt wątkowy nie jest formalny. Są miejsca odczytujące Tk lub modyfikujące wspólne słowniki poza wątkiem UI.

---

## 4. Zadanie 1 — monitorowanie aktualnego stanu serwerów

### 4.1 Status z logu

`LogTail` rozpoznaje:

- `Log file open` → STARTING,
- update/install według `LOG_PATTERNS["mod_update"]` → LOADING_MODS,
- `UShooterEngine::LoadGameMods` → LOADING_MODS,
- `has successfully started!` → ENGINE,
- `advertising` → READY,
- fatal/unhandled exception → CRASH,
- brak pliku poza okresem łaski → OFFLINE.

Przy otwarciu czyta ostatnie 2 MiB. Jeśli nie znajduje markera, a plik przekracza 256 KiB, zakłada READY.

**Ocena:** praktyczny mechanizm, lecz fallback „duży log = READY” jest heurystyką, nie dowodem gotowości. Należy zachować go jako jawny stan `READY_HEURISTIC` lub uzupełnić sondą RCON.

### 4.2 Rotacja i blokowanie logu

Na Windows `open_log_shared()` używa:

- `FILE_SHARE_READ`,
- `FILE_SHARE_WRITE`,
- `FILE_SHARE_DELETE`.

To jest potwierdzona blizna. Zastąpienie zwykłym `open()` może uniemożliwić managerowi skasowanie/rotację logu i zakłócić start serwera. Fallback do zwykłego `open()` istnieje, ale tylko po niepowodzeniu API Win32.

### 4.3 Proces i port

`_pid_map()` parsuje `netstat -ano`; `_tab_alive()` bierze PID przez skonfigurowany port RCON. Jeśli portu nie ma w mapie, kod zwraca `(True, None)`, czyli „zakładamy, że żyje”. To celowo unika fałszywych alarmów, lecz powoduje ślepotę.

**Problem K6 potwierdzony:** brak walidacji unikalności portów. Dwie mapy z tym samym portem mogą dostać ten sam PID lub niepoprawne wnioski.

**Dodatkowy problem:** port nie jest pełną tożsamością procesu. Lepsze źródła na Windows:

1. PID z portu,
2. weryfikacja nazwy obrazu `ArkAscendedServer.exe`,
3. odczyt command line procesu i dopasowanie unikalnych portów/mapy/katalogu,
4. dopiero potem przypisanie PID do taba.

### 4.4 WISI i sonda

Po 15 minutach ciszy program wysyła `listplayers`; po 20 minutach loguje alarm. To nie zmienia procesu i jest bezpieczne. Jednak callback sondy tylko loguje wynik; nie aktualizuje formalnego statusu zdrowia mapy.

### 4.5 Detektor pobierania

Kod w `ServerTab._apply_tail()` sprawdza wyłącznie:

```python
if "Downloading mod" in (line or ""):
```

Ponadto callback `LogTail` nie przekazuje każdej linii osobno. `_emit()` zwykle przekazuje ostatnią linię po całej paczce odczytu. Nawet gdyby właściwy tekst wystąpił wcześniej w paczce, może zostać zgubiony.

Rzeczywiste markery z dostarczonych logów to m.in.:

- `Request to Install mod`,
- `Starting download`,
- `Successfully installed mod`,
- `requires upgrade/downgrade`,
- prawdopodobnie komunikaty błędów/hash/temp.

**K7 potwierdzony i szerszy niż pierwotnie opisano.** Detektor powinien być parserem zdarzeń logu, a nie analizą tylko ostatniej linii statusowej.

### 4.6 Crash guard

Podczas osi czasu:

- CRASH/OFFLINE oznacza incydent mapy,
- pozostałe komendy tej mapy są pomijane,
- reszta map działa dalej,
- `DoExit` jest porzucany przy STARTING/LOADING_MODS/ENGINE.

To realizuje zasadę „jedna mapa nie blokuje klastra”. Nie realizuje jej jednak walidacja linii przed rozpoczęciem procedury — patrz sekcja 6.

---

## 5. Zadanie 2 — wersje modów na CF i na serwerach

### 5.1 Co dokładnie śledzi strona CF

`cf_get_mods_batch()` pobiera do 50 modów jednym POST i wybiera:

```python
latest = max(latest_files, key=lambda f: f.get("id", 0))
```

Nie filtruje po:

- nazwie `-windowsserver`,
- `gameVersions`,
- typie wydania,
- platformie,
- relacji rodzeństwa plików jednego wydania.

Dlatego `known_versions[mid]` jest identyfikatorem najwyższego publicznego pliku, a niekoniecznie pliku instalowanego przez serwer.

### 5.2 Wyjaśnienie punktu 7 i różnicy `+3`

Jedna publikacja autora może utworzyć grupę plików. Serwer wybiera wariant `-windowsserver`; API zwraca kilka wariantów. Refresher bierze najwyższe ID bez rozpoznania wariantu. Stałe `+3` w obserwowanej próbce oznacza regularną kolejność utworzenia plików, nie gwarantowany kontrakt API.

**Wniosek:** nie wolno kodować reguły „dodaj 3”. Należy wybierać właściwy plik semantycznie albo mapować wydanie na paczkę serwerową przez `library.json`/metadane CF.

### 5.3 `known_versions` nie jest wersją zainstalowaną

To lokalny kursor obserwacji publicznego API. Na pierwszym odczycie program robi baseline i nie restartuje. Po wykryciu większego `fid` tworzy zaległość. Po końcu osi czasu podnosi `known_versions` — nawet bez potwierdzonej instalacji.

Nazwa pola jest myląca. Powinno zostać rozdzielone na co najmniej:

- `cf_seen_file_id`,
- `server_installed_file_id[map][mod]`,
- `server_loaded_file_id[map][mod]`,
- `pending_release/mod artifact`,
- `procedure_result[map]`.

### 5.4 Lista modów z logu

`_loaded_mods_from_log()` czyta ostatnie 512 KiB i dla każdej części linii bierze pierwszą liczbę. To naprawia wcześniejsze liczenie `modId` i `fileId` jako dwóch modów, ale świadomie wyrzuca wersję.

W efekcie log jest używany jako źródło pytania **które mody**, nie **jakie wersje**.

Dodatkowe ryzyka parsera:

- warunek `(load in low and mod in low)` jest szeroki,
- bierze dowolną liczbę 6–12 cyfr z tokenu,
- brak strukturalnego powiązania `modId -> fileId`,
- tylko 512 KiB może nie objąć sekwencji startowej po dłuższej pracy.

### 5.5 Stan katalogu

`_installed_file_ids()` analizuje foldery `<ModID>_<FileID>` i pliki `.mod`. To dobry fallback fizyczny, ale:

- może zobaczyć pozostałości starej lub częściowej instalacji,
- `dict()` zachowuje ostatni znaleziony wpis, a kolejność `os.listdir()` nie jest gwarantowana,
- w `_verify_local_mods()` nie wybiera jawnie maksimum przy duplikatach,
- folder mówi o dysku, nie o wersji aktualnie załadowanej do procesu.

W `check_now()` budowane jest `installed_max`, co częściowo łagodzi duplikaty, ale późniejsza weryfikacja używa zwykłego `dict`.

### 5.6 Nieużywane źródło `library.json`

Kod nigdzie nie czyta rejestru CFCore `ModsUserData/83374/library.json`. Jest to najważniejsza luka zadania 2b.

Rekomendowany model źródeł:

| Pytanie | Źródło główne | Fallback |
|---|---|---|
| Co jest dostępne publicznie? | API CurseForge | brak/cache |
| Co CFCore uważa za zainstalowane? | `library.json` | katalog |
| Co serwer faktycznie załadował w tym starcie? | ustrukturyzowany parser logu startowego | rejestr + znacznik startu |
| Czy instalacja się rozpoczęła/zakończyła? | zdarzenia logu CFCore | zmiana `library.json`/katalogu |
| Jakie mody dotyczą mapy? | linia `LoadGameMods` z konkretnego startu | konfiguracja taba oznaczona jako niezweryfikowana |

Log nie jest jedyną prawdą dla wszystkich pytań. Jest najlepszym źródłem przebiegu i faktycznego ładowania; `library.json` jest najlepszym źródłem stanu instalatora.

### 5.7 Krytyczna niespójność `+3`

Kod porównuje lokalny `windowsserver fileId` z publicznym `max(latestFiles.id)` jak liczby z jednej przestrzeni:

```python
if inst and int(inst) >= int(fid): ...
```

Przy obserwowanym `installed = api + 3` warunek przypadkiem przechodzi. To maskuje błąd modelu. Gdy kolejność plików zmieni się lub wariant serwerowy dostanie mniejsze ID, godzenie może nie zadziałać albo dać fałszywy wynik.

### 5.8 Tożsamość zaległości po nazwie moda

`pending_updates` przechowuje `(name, fid)`, nie `(mod_id, artifact/release)`. Aby znaleźć mapy, kod odwraca `mod_names`, szukając pierwszej zgodnej nazwy.

Ryzyka:

- dwie pozycje o tej samej nazwie,
- zmiana nazwy moda,
- brak mapowania nazwy powoduje `if not mid`, czyli aktualizacja zostaje uznana za dotyczącą każdej mapy,
- kasowanie zaległości w `_verify_local_mods()` odbywa się również po nazwie.

Stan domenowy musi być kluczowany `mod_id`, nigdy nazwą prezentacyjną.

---

## 6. Zadanie 3 — procedura zaprogramowana liniami RCON

### 6.1 Walidacja pustych wierszy — K3

`add_line()` tworzy zaznaczony pusty wiersz. `get_lines()` zwraca każdy zaznaczony wiersz. `validate_lines()` odrzuca pusty czas lub komendę. `_exec_pending()` po błędzie wykonuje `return`.

Skutki:

- świeżo dodana mapa może zablokować cały klaster,
- zaznaczone puste wiersze są minami,
- decyzja użytkownika „puste pomijamy” nie jest zaimplementowana.

Poprawna reguła:

- `t == "" and cmd == ""` → pomiń,
- dokładnie jedno puste → błąd tej mapy,
- błędna mapa → zaparkuj/pomiń mapę, nie cały klaster,
- pokaż zbiorcze ostrzeżenie przed startem.

Samo `return -> continue` nie wystarczy, bo trzeba zachować informację o mapie pominiętej oraz nie uznać jej później za zaktualizowaną.

### 6.2 Wybór map dotkniętych modem

Program dla każdego taba sprawdza przecięcie jego modów z pendingami. Sama intencja jest poprawna. Implementacja po nazwach jest krucha, jak opisano wyżej.

### 6.3 Kolejki RCON

Każdy `ServerTab` ma osobną kolejkę i worker. To ważne: timeout jednej mapy nie blokuje pozostałych ani UI.

Komenda jest ponawiana trzy razy co dwie sekundy. Zachowuje względną terminowość i nie przesuwa całej osi czasu.

### 6.4 Guard startu i crashu

`DoExit` przy statusie startowym jest blokowany i oznaczany jako wysłany, czyli faktycznie porzucony. To zgodne z aksjomatem, że update wejdzie przy następnym starcie. Problemem jest późniejsze uznanie całej aktualizacji za obsłużoną.

### 6.5 BŁĄD KRYTYCZNY: sukces osi czasu ≠ sukces restartu

Po oznaczeniu wszystkich elementów `sent=True`, `_complete_procedure()`:

1. uruchamia watch,
2. wpisuje nowe `fid` do `known_versions`,
3. usuwa wszystkie `updated_mods` z `pending_updates`,
4. zapisuje konfigurację.

Dzieje się to niezależnie od:

- błędu uwierzytelnienia RCON,
- trzech timeoutów,
- blokady `DoExit` podczas startu,
- CRASH/OFFLINE i pominięcia mapy,
- braku jakiegokolwiek `DoExit` w harmonogramie,
- faktycznego zakończenia procesu,
- ponownego startu,
- instalacji właściwej wersji,
- załadowania właściwej wersji.

Callback RCON tylko loguje wynik; nie wpływa na stan procedury.

**To jest najgroźniejszy błąd logiczny programu.** Zaległość globalna nie może zniknąć na podstawie zakończenia zegara.

### 6.6 Czuwanie powrotu

`_start_return_watch()` dodaje wszystkie aktywne mapy mające ścieżkę logu, nie tylko mapy zaplanowane lub takie, które dostały skuteczne `DoExit`.

Jeżeli mapa ma już status READY w chwili rozpoczęcia watch, w następnym tiku zostanie uznana za powracającą, bez zaobserwowania sekwencji:

`READY -> STARTING/OFFLINE/LOADING -> READY`.

W rezultacie watch nie dowodzi restartu.

Poprawny automat per mapa powinien znać:

- czy mapa była dotknięta,
- czy miała `DoExit`,
- czy RCON potwierdził wysłanie,
- czy po komendzie opuściła READY / zmienił się plik lub identyfikator startu,
- czy pojawił się nowy `Log file open`,
- czy przeszła do READY,
- jakie wersje załadowała.

### 6.7 Brak `DoExit`

Mapa może mieć tylko `ServerChat`. Oś czasu zakończy się i aktualizacja zostanie uznana za obsłużoną, choć restart nie wystąpił. Przed startem należy klasyfikować harmonogram:

- informacyjny,
- restartujący (ma aktywne `DoExit`),
- niepoprawny dla automatycznej aktualizacji.

### 6.8 Auto-kolejna tura

Po pełnym watch i gdy nadal istnieją pendingi, program planuje kolejną turę po 60 s. Mechanizm jest sensowny, ale obecny kod zwykle usuwa pendingi wcześniej w `_complete_procedure()`. Kolejna tura ma znaczenie głównie dla aktualizacji wykrytych podczas watch lub zaparkowanych z innych powodów.

---

## 7. Kolizje z managerem i SSD

### 7.1 Dwa niezależne harmonogramy

Kod refreshera nie zna harmonogramu managera. Nie czyta jego konfiguracji, nie ma maintenance window ani blokady kolizji. K4 jest potwierdzony jako luka architektoniczna.

Minimalne rozwiązania, od najlepszego:

1. jedna władza nad restartami — wyłączyć restart schedule managera,
2. importer/read-only adapter konfiguracji managera i blokada okna,
3. ręcznie zdefiniowane blackout windows w refresherze,
4. plik/lock koordynacyjny, jeśli manager potrafi uruchamiać hooki.

### 7.2 Ochrona SSD

Aktualny program nie mierzy:

- aktywnego downloadu,
- rozpakowywania `.temp`,
- kolejki CFCore,
- IOPS/transferu dysku,
- startu ładowania świata jako zasobu.

Chroni SSD wyłącznie pośrednio, przez ręcznie ustawione czasy. Ponieważ K7 nie działa, program nie ma dynamicznego sprzężenia zwrotnego.

Docelowa procedura powinna mieć semafor zasobu „ciężki start”:

- nie uruchamiaj kolejnej mapy, dopóki poprzednia nie zakończy fazy instalacji/ładowania lub nie minie limit,
- ręczne minimalne odstępy pozostają jako dolna granica,
- sygnały z logu/`library.json` sterują zwolnieniem semafora,
- pominięcie jest bezpieczne; nie stosować agresywnego retry.

### 7.3 Priorytet CPU

W obecnej V3.74 nie ma kodu ustawiającego priority/affinity. Planowany plugin może używać uprawnień administratora. Powinien:

- identyfikować właściwy PID silniej niż portem,
- czekać co najmniej 30 s albo wykryć, że manager nałożył ustawienie,
- nakładać idempotentnie,
- raportować odmowę uprawnień,
- nie wykonywać pętli walki z managerem.

---

## 8. Trwałość, konfiguracja i bezpieczeństwo

### Mocne strony

- atomowy zapis przez plik tymczasowy i `os.replace`,
- wersjonowane snapshoty,
- rotacja dziesięciu kopii,
- oddzielenie klucza CF i haseł RCON od zwykłej konfiguracji,
- migracje starszych nazw,
- brak zewnętrznych zależności Python.

### Ograniczenia

- „sekrety” są oddzielone organizacyjnie, ale pozostają zwykłym tekstem JSON,
- Source RCON nie szyfruje hasła/komend na poziomie aplikacji; zalecany localhost/VLAN/firewall,
- `save_versioned()` używa dokładności jednej sekundy; kolizje są obsługiwane przez `.bak`, ale model jest skomplikowany,
- wiele `except Exception: pass` ukrywa błędy i utrudnia diagnozę,
- brak schematu konfiguracji i formalnej migracji wersji danych.

Nie ma oznak złośliwego kodu, pobierania wykonywalnych plików ani arbitralnego wykonywania odpowiedzi z sieci.

---

## 9. Współbieżność i Tkinter

### Potwierdzone dobre praktyki

- większość aktualizacji UI wraca przez `post_ui`,
- snapshot `list(self.tabs.items())` ogranicza błąd zmiany słownika,
- kolejki RCON izolują mapy,
- zamykanie próbuje zatrzymać tailery i workerów.

### Ryzyka

1. `_cf_sonda_run()` w funkcji workera wywołuje `self.var_api_key.get()` poza wątkiem Tk. To nie jest bezpieczne dla Tkintera.
2. `_cf_worker()` poza UI modyfikuje `mod_names`, `mod_pages` i `mod_latest`, podczas gdy UI może je czytać.
3. `_monitor_worker()` ustawia `_mon_busy=False` w swoim wątku; proste przypisanie jest mało ryzykowne, ale kontrakt nie jest czysty.
4. Callbacki i lambdy zamykają obiekty tabów, które mogą zostać zniszczone przy zmianie języka/przebudowie UI.
5. Brak centralnego anulowania workerów przy przebudowie języka lub konfiguracji.

Refaktor powinien wprowadzić niezmienne snapshoty wejścia do workera i pojedynczy obiekt wyniku wracający do UI.

---

## 10. Dokumentacja — potwierdzone nieścisłości

Do poprawy:

1. Root `README.md` PL sugeruje „serwer (ASM)”, a EN wprost mówi, że manager pobiera i instaluje mody.
2. `MANUAL` linie 14–16 przypisują czynność managerowi w nawiasie.
3. `MANUAL` słownik określa manager jako pobierający mody.
4. `PROMPT-ASAonly-AWARYJNY.md` PTK 10 przypisuje pełny update managerowi.
5. Raport symulacji zawiera scenariusze typu „ASM zainstalował mod”, co utrwala błędny model.
6. „LOG SERWERA = PRAWDA” jest poprawne dla listy faktycznie ładowanych modów, lecz nie opisuje dziś pełnej wersji zainstalowanej/załadowanej.
7. Watchdog `Downloading mod` jest reklamowany jako działający, choć parser nie odpowiada rzeczywistym markerom.
8. Repo nie zawiera `symulacja/`, mimo raportów 62/62 i dodatkowych zestawów debug. Wyniki są nieodtwarzalne z samego repozytorium.

---

## 11. „Blizny” — co znaczą i jak je traktować

Blizna nie oznacza „nigdy nie zmieniaj”. Oznacza: istnieje znany tryb awarii, który musi mieć test regresyjny przed zmianą implementacji.

| Blizna | Chroni przed | Wymagany test |
|---|---|---|
| `FILE_SHARE_DELETE` | manager nie może skasować logu, start pada | otwarty tail + rotacja/usunięcie pliku |
| ogon 2 MiB | skan GB logu / brak sekwencji startowej | duży log i markery blisko granicy |
| grace 15 s | fałszywy OFFLINE przy rotacji | zniknięcie i powrót logu w oknie |
| kolejka RCON per mapa | jedna mapa blokuje klaster/UI | timeout A, sukces B w terminie |
| `next_check` zawsze przesuwany | CF hammer | update + aktywna procedura + wiele tików |
| retry 3 × 2 s | chwilowy brak RCON bez przesuwania osi | dwa błędy, trzeci sukces |
| stan monitora w `ServerTab.__init__` | nowy tab nie ma pól | tab utworzony po starcie monitora |
| geometria kafelków | regresje UI | test/manualny snapshot wielu szerokości |

Do tej tabeli należy dodać nowe blizny:

- nie zdejmuj pendingu bez potwierdzenia per mapa,
- nie uznawaj READY za „powrót”, jeśli nie widziano wyjścia z poprzedniego READY,
- identyfikuj zaległość po `mod_id`, nie po nazwie,
- nie porównuj fileId różnych artefaktów jak tej samej wersji,
- pusty zaznaczony wiersz jest no-op.

---

## 12. Weryfikacja tez 1–39

### Potwierdzone lub zgodne z modelem

**1–6:** tak, na podstawie danych użytkownika i logów; kod nie przeczy.  
**8–12:** tak według danych użytkownika; repo nie zawiera kodu managera, więc to obserwacja zewnętrzna.  
**14:** tak — restart przy najbliższym starcie pozostaje aksjomatem operacyjnym.  
**15:** tak, jeśli „bezpieczne” znaczy „update może się opóźnić”; program musi zachować pending zamiast udawać sukces.  
**16–17:** tak — czasy są ręcznym rozjazdem zależnym od realnych startów map.  
**19:** intencja tak; implementacja ma ryzyko przez mapowanie po nazwie.  
**20–21:** tak — brak zapisu do gry i brak zabijania procesu; automatycznie tylko RCON.  
**22–26:** częściowo tak; patrz zastrzeżenia o walidacji, fałszywym watch i przedwczesnym kasowaniu pendingu.  
**33–34:** tak.  
**36:** program/plugin może wymagać admina; obecna wersja nie ma pluginu CPU.  
**39:** subskrypcja konta użytkownika jest nieistotna dla opisanego CFCore serwera.

### Wymagające korekty

**7:** tak w obserwowanym środowisku, ale nie jako gwarantowane `+3`; refresher wybiera `max(latestFiles)`, serwer wariant `-windowsserver`.  
**13:** nie „wyłącznie kiedy”; program ma trzy zadania wskazane przez użytkownika.  
**18:** nie. Log jest prawdą o przebiegu i faktycznym ładowaniu, lecz obecny parser wersje wyrzuca. `library.json` powinien być źródłem stanu instalacji, katalog fallbackiem.  
**23:** guard istnieje, ale wynik jest błędnie uznawany za sukces.  
**24:** timeout domyślnie 20 min istnieje, ale watch nie dowodzi restartu.  
**26:** auto 60 s istnieje tylko gdy pending nadal istnieje; obecny kod często usuwa go za wcześnie.  
**35:** blizny trzeba zachować jako wymagania regresyjne, niekoniecznie jako identyczny kod.

### Nie do ustalenia z repozytorium

**27–32:** bieżąca konfiguracja produkcyjna nie jest wersjonowana.  
**37:** zależy od zachowania klienta/moda/serwera i chwili publikacji; potrzebne logi eksperymentalne.  
**38:** brak materiału dowodowego. Trzeba odtworzyć awarię pobierania lub zebrać następny przypadek.

---

## 13. Lista usterek według priorytetu

### P0 — przed dalszą automatyzacją

1. Nie podnosić `known_versions` i nie kasować pendingów po samym końcu osi czasu.
2. Wprowadzić wynik per `(mod_id, mapa)` oraz potwierdzenie nowego startu i wersji.
3. Watch tylko map dotkniętych i tylko po zaobserwowaniu cyklu restartu.
4. Pending kluczować `mod_id`, nie nazwą.

### P1 — bezpieczeństwo operacyjne

5. Puste zaznaczone wiersze pomijać; błąd jednej mapy nie blokuje reszty.
6. Walidować unikalność portów RCON i tożsamość PID.
7. Rozpoznać prawdziwe markery CFCore i przekazywać każde zdarzenie logu.
8. Czytać `library.json` oraz rozdzielić available/installed/loaded.
9. Koordynować lub blokować okna harmonogramu managera.
10. Wymagać aktywnego `DoExit` dla automatycznego uznania mapy za restartowaną.

### P2 — poprawność i odporność

11. Wybierać wariant `-windowsserver` albo modelować wydanie niezależnie od fileId.
12. Naprawić obsługę wielu katalogów tego samego moda (jawne maksimum/stan aktywny).
13. Usunąć operacje Tk z workerów.
14. Wprowadzić jawne stany `UNKNOWN` zamiast optymistycznego „alive”.
15. Poprawić dokumentację i odtwarzalne testy.

### P3 — rozwój

16. Plugin CPU po stabilizacji identyfikacji PID.
17. Dynamiczny semafor ochrony SSD.
18. Telemetria czasu faz startu map do podpowiadania harmonogramu.

---

## 14. Docelowy model stanu

### Mod

```text
ModState
  mod_id
  display_name
  cf_release
  cf_artifacts[]
  selected_server_artifact
  maps:
    map_id:
      configured
      loaded_file_id
      installed_file_id
      source
      observed_boot_id
      pending
      verification
```

### Mapa

```text
MapState
  stable_id
  display_name
  rcon_endpoint
  log_path
  pid
  process_identity_confidence
  boot_id
  phase: OFFLINE/STARTING/DOWNLOADING/INSTALLING/LOADING/READY/CRASH/UNKNOWN
  phase_since
  last_log_event
```

### Procedura

```text
ProcedureRun
  run_id
  detected_updates[mod_id]
  target_maps
  per_map:
    validation
    scheduled_commands
    doexit_required
    doexit_delivery
    departure_observed
    boot_observed
    ready_observed
    mods_verified
    result: SUCCESS/SKIPPED/FAILED/TIMEOUT/DEFERRED
```

Globalny kursor CF może zostać przesunięty niezależnie od pendingu, ale pending per mapa znika dopiero po `mods_verified=TRUE` albo po jawnej decyzji operatora.

---

## 15. Ocena propozycji rozbicia na pluginy

Podział według trzech zadań użytkownika jest dobry. Wymaga jednak korekty kontraktu.

### Rdzeń powinien posiadać

- Tk i główny zegar,
- niezmienny rejestr map (`stable_id`),
- magazyn konfiguracji,
- szynę zdarzeń,
- wykonawcę workerów,
- lifecycle pluginów,
- centralny model procedury i trwałe pendingi.

Procedura nie może być luźnym pluginem, jeśli tylko ona ma prawo zmieniać globalny stan zaległości. Może być pluginem domenowym, ale przez transakcyjny kontrakt rdzenia.

### Proponowane pluginy

1. `10_logtail` — surowe zdarzenia logu i boot ID.
2. `20_monitor` — proces/PID/port/RCON health.
3. `30_cf_wersje` — dostępne wydania i artefakty.
4. `40_serwer_wersje` — `library.json`, katalog, parser loaded versions, reconciler.
5. `50_procedura` — plan i wyniki per mapa.
6. `60_cpu` — priority/affinity po stabilnym PID i opóźnieniu.
7. `70_mody_okno` — wyłącznie prezentacja.

### Kontrakt zdarzeń wymagany ponad pierwotne minimum

- `map.phase_changed`
- `map.boot_started(boot_id)`
- `map.ready(boot_id)`
- `map.process_bound(pid, confidence)`
- `mod.download_started(map_id, mod_id, file_id)`
- `mod.install_succeeded(...)`
- `mod.loaded(...)`
- `cf.release_observed(...)`
- `rcon.command_result(run_id, map_id, command_id, result)`
- `procedure.map_result(...)`

Każde zdarzenie powinno być prostym, niezmiennym obiektem danych bez widgetów Tk.

---

## 16. Bezpieczna kolejność prac

### Etap 0 — odzyskanie testów

Przed cięciem logiki należy umieścić w repozytorium `symulacja/` albo stworzyć nowy zestaw. Raport wyników bez kodu testów nie jest flotą regresyjną.

Minimalne fixture’y:

- log rzeczywistego startu bez update,
- log z update trzech modów,
- rotacja/kasowanie logu,
- crash i crashloop,
- timeout RCON,
- duplikat portu,
- kilka katalogów jednego moda,
- `library.json`,
- puste linie,
- blokowany `DoExit`,
- mapa już READY przy starcie watch,
- dwa mody o tej samej nazwie.

### Etap 1 — poprawki P0 w monolicie

Najpierw naprawić semantykę sukcesu w istniejącym kodzie. Refaktoryzacja wadliwego modelu tylko rozsieje błąd po pluginach.

### Etap 2 — czyste ekstrakcje

Wydzielić bez zmiany zachowania:

- `tr.py`,
- `zapis.py`,
- `siec.py`,
- widgety prezentacyjne.

Każda ekstrakcja: compile, import smoke test, test zapisu/RCON parsera/CF parsera.

### Etap 3 — parser zdarzeń i `server_versions`

Wprowadzić `library.json`, pary `modId/fileId`, prawdziwe zdarzenia CFCore oraz boot ID. To fundament poprawnego watch i ochrony SSD.

### Etap 4 — monitor i tożsamość procesu

Walidacja portów, PID + image + command line, jawna pewność przypisania.

### Etap 5 — procedura jako automat

Per-map state machine, brak globalnego „sukcesu” na końcu zegara, trwałe deferred/pending.

### Etap 6 — host pluginów

Dopiero po ustaleniu modeli danych. Inaczej kontrakt pluginów utrwali przypadkowe słowniki obecnego `App`.

### Etap 7 — CPU i dynamiczna ochrona SSD

CPU po identyfikacji PID; SSD po wiarygodnych sygnałach faz pobierania/instalacji/ładowania.

---

## 17. Kryteria akceptacji następnej wersji

1. Pusty zaznaczony wiersz nie zgłasza błędu.
2. Błędna mapa nie blokuje prawidłowych map.
3. Dwa identyczne porty powodują głośny konflikt i brak automatycznej procedury dla tych map.
4. Błąd RCON nie usuwa pendingu.
5. Zablokowany `DoExit` nie usuwa pendingu mapy.
6. Mapa bez `DoExit` nie jest uznawana za zrestartowaną.
7. READY bez wcześniejszego opuszczenia READY nie liczy się jako powrót.
8. Watch obejmuje tylko mapy celu.
9. Aktualizacja moda o tej samej nazwie co inny mod nie miesza identyfikatorów.
10. Program raportuje osobno wersję dostępną, zainstalowaną i załadowaną.
11. `library.json` jest używany, a katalog jest fallbackiem.
12. Parser rozpoznaje `Request to Install`, `Starting download`, `Successfully installed` i `requires upgrade/downgrade`.
13. Nie istnieje reguła arytmetyczna `+3`.
14. Rotacja logu działa przy aktywnym odczycie współdzielonym.
15. CF check nie wykonuje lawiny zapytań podczas procedury.
16. Wszystkie testy są w repozytorium i uruchamiane jednym poleceniem.

---

## 18. Ostateczna odpowiedź na otwarte decyzje

### Kto powinien rządzić restartami?

Najbezpieczniej: refresher rządzi restartami modowymi, manager tylko stawia proces po `DoExit`; harmonogram restartów managera powinien być wyłączony albo jawnie importowany jako blackout window. Dwóch niezależnych planistów bez koordynacji nie należy dopuszczać.

### Czy `continue` zamiast `return`?

Kierunek **tak**, ale nie jako samotna zmiana jednej linii. Najpierw puste-puste jako no-op, potem błąd per mapa, oznaczenie mapy `DEFERRED_INVALID_CONFIG`, kontynuacja pozostałych i zachowanie pendingu tej mapy.

### Gdzie jest `symulacja/`?

Nie ma jej w analizowanym repozytorium. Jest wyłącznie raport. Kroki ingerujące w logikę są bez niej nieodtwarzalne.

### Czy program może używać administratora?

Tak, jeśli funkcja tego wymaga. Uprawnienia nie rozwiązują jednak błędnej identyfikacji PID. Najpierw poprawna tożsamość procesu, potem elevation i operacja CPU po działaniu managera.

### Co z punktami 37–38?

Pozostają hipotezami. Należy dodać rejestrację pełnych zdarzeń następnego realnego przypadku i nie budować automatyki na założeniu, czy serwer wstaje na starej wersji.

---

## 19. Konkluzja

V3.74.1 nie jest prostym „restartowaczem”. Ma wartościowy monitoring, izolowane RCON-y, trwałość i wiele dobrych zabezpieczeń. Największy problem nie leży w rozmiarze pliku, lecz w pomieszaniu czterech różnych pojęć:

1. plik zauważony na publicznym CF,
2. plik zainstalowany przez CFCore,
3. plik załadowany przez konkretny start mapy,
4. aktualizacja uznana przez refresher za obsłużoną.

Obecny kod potrafi przejść od punktu 1 bezpośrednio do punktu 4 po upływie osi czasu. Dopiero rozdzielenie tych stanów i potwierdzenie per mapa pozwoli bezpiecznie rozbić program na pluginy i rzeczywiście chronić SSD.
