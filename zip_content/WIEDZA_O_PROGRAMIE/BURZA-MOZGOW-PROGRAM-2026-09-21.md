# Burza mózgów nad ASAonly ModRefresher

Data: 2026-09-21

To jest zbiór hipotez, ryzyk i możliwych rozwiązań — nie lista rzeczy już wykonanych. Priorytetem pozostają trzy główne obowiązki programu: monitoring serwerów, kontrola wersji modów oraz bezpieczne sekwencyjne procedury RCON.

---

## 1. Najważniejsze pytanie architektoniczne

Program powinien być traktowany jako kontroler stanów, nie zestaw przycisków i timerów.

Dla każdej mapy powinien istnieć jawny stan operacyjny, np.:

- `UNKNOWN` — brak wystarczających danych;
- `OFFLINE` — potwierdzona nieobecność;
- `STARTING`;
- `LOADING_MODS`;
- `READY`;
- `UPDATE_REQUIRED`;
- `RCON_PROCEDURE`;
- `EXIT_SENT`;
- `WAITING_FOR_DEPARTURE`;
- `WAITING_FOR_RETURN`;
- `VERIFYING_VERSION`;
- `PAUSED_ERROR`.

Każde przejście powinno mieć:

1. wymagany dowód wejściowy;
2. dozwolone akcje;
3. zapisany powód;
4. jednoznaczny rezultat;
5. zachowanie po restarcie Refreshera.

To ograniczyłoby ukryte zależności między flagami `restart_active`, `watch_active`, kolejką, logiem, PID i pendingami.

---

## 2. Rozdzielenie trzech równych odpowiedzialności

### A. Monitoring

Odpowiada wyłącznie za fakty:

- proces/PID;
- port;
- stan logu;
- READY;
- odejście;
- powrót;
- aktualnie załadowane wersje modów;
- jakość i źródło dowodu.

Nie powinien decydować o restarcie ani wysyłać komend administracyjnych poza wyraźnie oznaczoną sondą read-only.

### B. Kontrola wersji

Odpowiada za:

- wersję CurseForge;
- wersję zainstalowaną;
- wersję potwierdzoną jako załadowana przez konkretną mapę;
- kwalifikację mapy do procedury;
- stan niepewny bez automatycznej zgody na restart.

Nie powinna wysyłać RCON ani sama zmieniać stanu serwera.

### C. RCON i koordynator

RCON odpowiada za transport, kolejki, połączenia, procedury i administrację ręczną. Koordynator odpowiada za kolejność map i przejścia między etapami. Żaden z nich nie powinien sam uznawać wersji moda za potwierdzoną.

---

## 3. Jedno źródło prawdy

Obecnie część stanu jest rozproszona między:

- obiektami zakładek;
- pluginem RCON;
- koordynatorem;
- `pending_updates`;
- logami;
- słownikami wersji;
- stanem Managera pluginów.

Pomysł: wprowadzić centralny, serializowalny model:

```text
MapRuntimeState
  identity
  configured
  monitor_evidence
  version_evidence
  rcon_state
  procedure_state
  pending_targets
  last_error
  revision
```

GUI wyświetla model, ale nie jest jego właścicielem. Worker produkuje zdarzenia, a jeden reducer na wątku głównym aktualizuje model.

---

## 4. Dziennik zdarzeń zamiast części ukrytych flag

Każda ważna decyzja mogłaby być zdarzeniem:

- `PROCESS_OBSERVED`;
- `PORT_OBSERVED`;
- `READY_OBSERVED`;
- `MOD_VERSION_OBSERVED`;
- `CF_VERSION_OBSERVED`;
- `MAP_QUALIFIED`;
- `RCON_COMMAND_QUEUED`;
- `RCON_COMMAND_STARTED`;
- `RCON_COMMAND_RESULT`;
- `SERVER_DEPARTED`;
- `SERVER_RETURNED`;
- `VERSION_VERIFIED`;
- `PROCEDURE_PAUSED`.

Korzyści:

- łatwiejsze odtworzenie przyczyny;
- możliwość testowania bez Tk;
- brak fałszywego „OK” bez dowodu;
- łatwiejsze wznowienie po restarcie programu;
- łatwiejszy audyt użytkownika.

Nie musi to być rozbudowany event sourcing. Wystarczy jawny dziennik ostatnich zdarzeń i deterministyczne przejścia.

---

## 5. RCON — pomysły bezpieczeństwa

### Konieczne

- osobna kolejka każdej mapy;
- jeden właściciel transportu;
- numer generacji/anulowania;
- identyfikator każdej komendy;
- stan `queued`, `claimed`, `inflight`, `done`, `failed`, `cancelled`;
- wynik i odpowiedź zachowane przy komendzie;
- `DoExit` oznaczone semantycznie, nie wyszukiwane w dowolnym tekście;
- brak automatycznego `DoExit` bez READY;
- brak rozpoczęcia następnej mapy bez odejścia, powrotu, READY i wersji.

### Do rozważenia

- osobne kolejki logiczne: automatyczna procedura, manualna administracja, sonda;
- jeden arbiter łączący je w transportową kolejkę mapy;
- priorytety bez możliwości wejścia manualnej komendy w środek procedury;
- jawna blokada ręcznych komend podczas procedury;
- możliwość ręcznego odczytu kolejki bez jej modyfikowania;
- historia ostatnich odpowiedzi RCON na mapę;
- timeout połączenia widoczny jako konfiguracja techniczna, nie część harmonogramu użytkownika.

---

## 6. Procedura RCON jako plan niezmienny

Po rozpoczęciu procedury warto tworzyć snapshot:

```text
ProcedureRun
  run_id
  map
  qualified_mods
  version_target
  local_timeline
  connection_snapshot
  started_at
  command_results
  departure_evidence
  return_evidence
  version_evidence
```

Zmiana konfiguracji GUI nie powinna zmieniać już działającego planu. Edycja dotyczy następnego uruchomienia.

Każda mapa zachowuje własną, nieprzesuniętą lokalną oś czasu. Sekwencyjność dotyczy rozpoczęcia map, a nie modyfikowania zapisanych czasów.

---

## 7. Prawdziwa trwałość i transakcje

### Problem

Kopie i rollback wykonywany po błędzie nie gwarantują odporności na:

- brak prądu;
- zabicie procesu;
- blokadę pliku;
- błąd podczas samego rollbacku;
- przerwę między dwiema mapami.

### Pomysł

Dla operacji wieloplikowych:

1. utworzyć katalog transakcji na tym samym woluminie;
2. zapisać `journal.json` z identyfikatorem i etapem;
3. przygotować wszystkie nowe pliki;
4. wykonać `fsync`, jeśli platforma pozwala;
5. zweryfikować JSON i kompletność;
6. atomowo podmieniać pliki przez `os.replace`;
7. oznaczyć transakcję jako zatwierdzoną;
8. przy starcie wykryć niedokończony journal i dokończyć albo odtworzyć.

Dla katalogów map lepsze mogą być atomowe zmiany nazw katalogów na tym samym woluminie niż kopiowanie po błędzie.

---

## 8. Scalenie i porządek pluginów

Najpierw potrzebna jest macierz odpowiedzialności, nie mechaniczne zmniejszanie liczby plików.

### Już logicznie połączone

- Backup + Przywracanie;
- Status + Historia.

### Kandydaci do wspólnego panelu administracyjnego, ale niekoniecznie jednego pluginu

- Pakiet diagnostyczny;
- Analizator logów;
- Dysk/Katalogi.

Mogłyby tworzyć jeden plugin „Narzędzia diagnostyczne” z trzema kartami, jednym stanem ON/OFF i jedną migracją ustawień. Ryzyko: połączenie ręcznych narzędzi z analizą okresową może utrudnić zasadę OFF. Należy najpierw ustalić, czy wszystkie mają wspólny cykl życia.

### Powinny pozostać osobno

- RCON — główna odpowiedzialność operacyjna;
- Koordynator — logika sekwencyjna;
- CPU — osobny zakres i ryzyko systemowe;
- Importer — jednorazowa migracja na żądanie.

### Do sprawdzenia

- Guard konfiguracji i audyt wersji: czy są wymaganymi kontrolami rdzenia, czy pluginami widocznymi dla użytkownika;
- stare nazwy pluginów w JSON;
- stare kafelki i opisy;
- podwójne domyślne stany ON/OFF;
- migracja ustawień po scaleniu;
- brak ładowania usuniętych plików pluginów.

---

## 9. Cykl życia pluginów

Proponowany jawny kontrakt:

```text
load()       import kodu, bez core i bez działań
prepare()    odczyt konfiguracji i budowa modelu, bez pracy operacyjnej
activate()   start pracy ON
quiesce()    przestań przyjmować nowe zadania
stop()       zakończ workery i zasoby
unload()     usuń subskrypcje i UI
```

Host powinien znać stan:

- `LOADED`;
- `PREPARED_OFF`;
- `ACTIVE`;
- `QUIESCING`;
- `STOPPED`;
- `FAILED`.

`set_enabled(False)` nie powinno być tylko zmianą flagi. Powinno kończyć się potwierdzonym `PREPARED_OFF` albo jawnym błędem zatrzymania.

---

## 10. Monitoring — dowody i jakość danych

Każdy status powinien zawierać:

- wartość;
- źródło;
- czas obserwacji;
- wiek;
- pewność;
- ostatni błąd odczytu.

Przykład:

```text
READY
źródło: log ASA
obserwacja: 14:03:22
wiek: 8 s
pewność: potwierdzone
```

PID i port nie powinny być tym samym dowodem. Brak możliwości uruchomienia `netstat` nie może wyglądać jak brak procesu. Brak dostępu powinien być osobnym stanem `MONITOR_ERROR`.

---

## 11. CurseForge i wersje

Dla każdego moda i mapy przechowywać osobno:

- `cf_latest_file_id`;
- `disk_file_id`;
- `loaded_file_id`;
- źródło `loaded_file_id`;
- czas obserwacji;
- wynik kwalifikacji;
- powód braku kwalifikacji.

Możliwe stany:

- `CURRENT`;
- `OLDER_CONFIRMED`;
- `UNKNOWN_LOCAL`;
- `UNKNOWN_LOADED`;
- `CF_ERROR`;
- `NOT_USED_BY_MAP`.

Tylko `OLDER_CONFIRMED` może kwalifikować mapę do automatycznej procedury.

---

## 12. Restart Refreshera w trakcie procedury

Pytanie krytyczne: co dzieje się, gdy Refresher zostanie zamknięty lub padnie po `DoExit`?

Pomysł: trwały zapis `ProcedureRun` przed każdą nieodwracalną akcją. Po ponownym uruchomieniu program nie wysyła ponownie `DoExit`, tylko odtwarza stan i szuka dowodów:

- czy serwer odszedł;
- czy wrócił;
- czy READY jest z nowego startu;
- czy wersja została potwierdzona.

Brak wystarczających danych powinien zatrzymać koordynator i wymagać decyzji operatora.

---

## 13. GUI operatora

Najważniejsze widoki:

### Widok klastra

- mapa;
- stan procesu;
- stan logu;
- READY;
- stan wersji;
- etap RCON;
- powód oczekiwania;
- ostatni błąd.

### Widok kolejki RCON

- mapa;
- komenda;
- źródło: automatyczna/manualna/sonda;
- stan;
- planowany czas lokalny;
- rzeczywisty czas rozpoczęcia;
- wynik.

### Widok dowodów

Nie „zielone OK”, tylko konkretne źródła decyzji.

### Widok incydentu

Jedno miejsce pokazujące:

- co zawiodło;
- co zostało wykonane;
- czego nie wykonano;
- czy jakakolwiek komenda może nadal być w locie;
- jaki stan wymaga ręcznej decyzji.

---

## 14. Logowanie

Rozdzielić:

- log operatora;
- log diagnostyczny;
- dziennik zdarzeń stanu;
- odpowiedzi RCON;
- błędy pluginów.

Każdy wpis strukturalny powinien mieć:

- czas;
- mapę;
- komponent;
- `run_id`;
- `command_id`, jeśli dotyczy;
- poziom;
- komunikat;
- wyjątek bez sekretów.

Ograniczanie powtarzalnych błędów jest dobre, ale pierwszy błąd, liczba powtórzeń i informacja o ustąpieniu problemu powinny pozostać widoczne.

---

## 15. Sekrety

- hasła RCON poza zwykłą konfiguracją;
- brak sekretów w diagnostycznym ZIP;
- backup bez sekretów domyślnie;
- jawna zgoda na ich dołączenie;
- tempy transakcyjne z restrykcyjnymi uprawnieniami;
- usuwanie tempów po awarii i przy następnym starcie;
- nigdy nie logować pełnego polecenia, jeśli może zawierać sekret.

---

## 16. Testy, które naprawdę wykrywają błędy

### Fault injection

Błąd na każdym kroku:

- przygotowanie pliku;
- zapis JSON;
- zapis sekretu;
- `os.replace`;
- zmiana nazwy katalogu;
- aktualizacja journalu;
- rollback;
- ponowne uruchomienie po przerwaniu.

### Testy współbieżności

Deterministyczne bariery dla:

- enqueue kontra cancel;
- worker claim kontra cancel;
- manualna komenda kontra procedura;
- sonda kontra procedura;
- stop pluginu kontra callback;
- zmiana języka kontra callback workera;
- zamknięcie aplikacji kontra zapis.

### Testy modelu stanów

Wygenerować niedozwolone kolejności zdarzeń i sprawdzić fail-closed:

- READY bez odejścia;
- wersja bez nowego startu;
- DoExit bez READY;
- CF update bez potwierdzonej starszej wersji mapy;
- druga mapa przed zakończeniem pierwszej;
- callback starej generacji.

### Testy rzeczywiste

Osobny skrypt/checklista Windows/Tk/ASA/RCON/ASADedicatedManager. Wyniki nie mogą mieszać się z pytest.

---

## 17. Symulator klastra

Warto zbudować deterministyczny symulator trzech map:

- fałszywy serwer RCON;
- kontrolowane odpowiedzi i timeouty;
- model Managera wyłącznie do testów;
- generowane logi ASA;
- kontrolowane wersje modów;
- zegar wirtualny.

Symulator nie zastąpi realnej integracji, ale pozwoli sprawdzić tysiące kolejności zdarzeń bez czekania na prawdziwe serwery.

---

## 18. Potencjalne uproszczenia

- mniej flag, więcej jawnych stanów;
- mniej metod dotykających Tk z logiki operacyjnej;
- jeden reducer zdarzeń na głównym wątku;
- nie więcej pluginów niż rzeczywistych odpowiedzialności;
- ręczne narzędzia nie powinny mieć ticków;
- plugin OFF nie powinien istnieć w ścieżce operacyjnej;
- konfiguracja i runtime przechowywane osobno;
- każdy zapis wieloplikowy przez wspólny mechanizm transakcyjny;
- każda nieodwracalna akcja z identyfikatorem i trwałym śladem.

---

## 19. Czego teraz nie dodawać

Dopóki rdzeń nie jest stabilny:

- powiadomienia;
- scheduler ogólny;
- kosmetyczne dashboardy;
- wykresy bez wartości operacyjnej;
- nowe narzędzia systemowe;
- automatyczne uruchamianie serwerów;
- dodatkowe mechanizmy odzyskiwania konkurujące z ASADedicatedManager;
- „inteligentne” zgadywanie wersji bez dowodu.

---

## 20. Proponowana kolejność realizacji

### Etap 1 — bezpieczeństwo

1. zaprojektować trwały model stanu mapy i procedury;
2. zastąpić rollback best-effort mechanizmem journal + staging + atomowe podmiany;
3. fault-injection dla wszystkich kroków;
4. dokończyć audyt wyjątków;
5. jawnie obsłużyć wznowienie po restarcie Refreshera.

### Etap 2 — porządek pluginów

1. macierz odpowiedzialności i cyklu życia;
2. migracja starych nazw i ustawień;
3. scalenie wyłącznie faktycznie wspólnych narzędzi;
4. usunięcie starych kafelków i plików;
5. test OFF/ON/restart każdego pluginu.

### Etap 3 — przepływ operacyjny

1. symulator klastra;
2. pełna sekwencja trzy mapy;
3. awarie RCON, CF, logu i procesu;
4. restart Refreshera w każdym etapie;
5. kontrolowana integracja Windows/Tk.

### Etap 4 — realne środowisko

1. uruchomione serwery rozpoznane przy starcie;
2. ręczne RCON;
3. kwalifikacja realnego moda;
4. pojedyncza mapa;
5. trzy mapy sekwencyjnie;
6. ASADedicatedManager Olrik-WP;
7. dokumentacja dokładnie odpowiadająca wynikowi testu.

---

## 21. Najważniejsze wnioski z burzy mózgów

1. Największym problemem nie jest brak funkcji, tylko rozproszony stan i zbyt szybkie ogłaszanie napraw.
2. Program potrzebuje jawnego modelu stanów i dowodów, nie kolejnych flag.
3. Operacje wieloplikowe potrzebują journalu i stagingu, nie samego rollbacku po błędzie.
4. RCON musi pozostać jednym właścicielem transportu i procedur.
5. Scalenie pluginów powinno wynikać z odpowiedzialności i cyklu życia, nie z podobnych nazw.
6. Test musi wykonywać awarię, a nie sprawdzać, czy odpowiedni tekst istnieje w kodzie.
7. Wynik rzeczywistej integracji musi pozostać oddzielony od testów automatycznych.
