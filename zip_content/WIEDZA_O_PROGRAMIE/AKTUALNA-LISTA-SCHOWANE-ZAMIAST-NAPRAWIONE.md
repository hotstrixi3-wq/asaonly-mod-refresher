# Aktualna lista: schowane albo przedstawione jako naprawione zbyt wcześnie

Stan na 2026-09-21 po V3.80.28.

Lista zawiera wyłącznie punkty nadal otwarte. Naprawiony wyścig anulowania RCON i rozdzielenie właścicieli `automatic/manual/monitor` nie są tu ponownie liczone.

## 1. „Transakcyjny” zapis wszystkich map RCON nie jest prawdziwą transakcją

### Co zostało przedstawione zbyt mocno

V3.80.26 opisałem jako transakcyjny zapis panelu RCON.

### Stan rzeczywisty

Program:

1. kopiuje katalogi do tymczasowych kopii;
2. zapisuje mapy kolejno do katalogów roboczych;
3. po błędzie usuwa zmienione katalogi;
4. próbuje skopiować stare katalogi z powrotem.

To jest rollback best-effort, nie transakcja odporna na przerwanie procesu i błąd samego rollbacku.

### Nadal możliwe problemy

- brak prądu albo zabicie procesu między zapisami;
- błąd podczas usuwania katalogu zmienionego;
- błąd kopiowania migawki po usunięciu katalogu;
- brak miejsca podczas odtwarzania;
- blokada antywirusa albo innego procesu;
- `server_files` wskazujące nieaktualną ścieżkę;
- brak trwałego journalu umożliwiającego odzyskanie po kolejnym uruchomieniu.

### Właściwa naprawa

Staging na tym samym woluminie, zapis i weryfikacja wszystkich nowych plików przed zatwierdzeniem, atomowe `os.replace`, journal etapów oraz odzyskanie niedokończonej transakcji przy starcie.

## 2. „Transakcyjna” zmiana nazwy mapy również jest rollbackiem best-effort

### Co zostało przedstawione zbyt mocno

V3.80.25 opisałem jako transakcyjną zmianę nazwy mapy.

### Stan rzeczywisty

Kod tworzy kopie, wykonuje zmianę, a po błędzie usuwa bieżące katalogi i kopiuje migawki. Sam rollback może się nie udać. Błąd rollbacku może zastąpić pierwotny wyjątek i pozostawić częściowy stan.

### Brakujące elementy

- journal zmiany nazwy;
- przygotowanie docelowego katalogu bez niszczenia starego;
- atomowa zamiana katalogów na tym samym woluminie;
- wznowienie lub cofnięcie operacji po restarcie programu;
- osobny raport błędu operacji i błędu odzyskiwania.

## 3. Testy transakcji nadal częściowo sprawdzają tekst kodu

### Problem

Część regresji używa `assertIn()` na treści plików źródłowych. To sprawdza obecność wybranych instrukcji, ale nie wykonuje rzeczywistej awarii.

### Nieprzetestowane przypadki

- błąd drugiej mapy po zapisaniu pierwszej;
- błąd sekretu po zapisaniu konfiguracji;
- błąd `copytree` podczas rollbacku;
- błąd usuwania katalogu;
- przerwanie procesu między etapami;
- restart programu z niedokończoną operacją;
- błąd aktualizacji `server_files` i stanu pamięci.

### Właściwa naprawa

Fault-injection na każdym kroku plus test odzyskania w nowym procesie. Test tekstu źródłowego może pozostać jedynie kontrolą pomocniczą, nie dowodem działania.

## 4. Obsługa każdego wyjątku `_save_all()` — NAPRAWIONE W KODZIE

Zewnętrzna granica callbacku przechwytuje teraz każdy `Exception`, zawsze zwraca kontrolowane `False`, próbuje pokazać błąd, a awarię samego okna błędu przekazuje do logu przez kolejkę UI. Rollback map wykonuje wszystkie kroki mimo błędu jednego odtworzenia i raportuje razem błąd pierwotny oraz listę nieudanych elementów rollbacku.

Dodano wykonawczy fault-injection: druga mapa zawodzi po zapisaniu pierwszej; test sprawdza odtworzenie pamięci, obu katalogów i `server_files`. Nie usuwa to nadal otwartego wymagania journalu odpornego na przerwanie procesu.

## 5. `prepare()` pluginu jest kontraktem, nie techniczną izolacją

### Co zostało przedstawione zbyt mocno

Twierdziłem, że plugin zapisany OFF nie może uruchomić workera.

### Stan rzeczywisty

Host nie wywołuje operacyjnego `start()` dla OFF. To jest poprawa. Jednak `prepare()` pozostaje zwykłym kodem pluginu i technicznie może uruchomić wątek albo wykonać operację.

Dostarczone pluginy zostały ręcznie sprawdzone pod tym kątem, ale host nie zapewnia izolacji dowolnego pluginu zewnętrznego.

### Uczciwa gwarancja

Host nie wywołuje `start`, `activate`, `tick`, hooków, zdarzeń ani diagnostyki pluginu OFF. Bezpieczeństwo samego `prepare()` jest kontraktem dla dostarczonych pluginów, nie sandboxem.

## 6. Pełny audyt szerokich wyjątków nie jest zakończony

Nadal istnieją szerokie `except Exception`, `pass`, `return None` i zamiany błędów na ogólne „brak danych”. Część jest poprawnym sprzątaniem GUI albo fail-closed, ale część może nadal ukrywać awarie.

Najważniejsze obszary do przejścia instrukcja po instrukcji:

- `asaonly/logtail.py`;
- `asaonly/monitor.py`;
- pozostałe fragmenty `asaonly/monitor_plugin.py`;
- `asaonly/server_tab.py`;
- `asaonly/widgety.py`;
- `asaonly/procedura.py`;
- główna aplikacja;
- callbacki i zamykanie pluginów administracyjnych.

Nie wolno mechanicznie usuwać wyjątków: błąd odczytu środowiska, błąd parsera, błąd Tk i błąd programu wymagają różnych reakcji.

## 7. Pełne scalenie i migracja pluginów nie zostały wykonane

### Stan obecny

Połączone są:

- Backup + Przywracanie;
- Status + Historia.

### Nadal brak

- pełnej macierzy odpowiedzialności wszystkich pluginów;
- decyzji o wspólnym panelu dla diagnostyki ZIP, analizatora logów i dysku;
- przeglądu starych nazw pluginów w zapisanej konfiguracji;
- usunięcia ewentualnych starych kafelków i zdublowanych ścieżek;
- pełnej migracji ON/OFF po scaleniu;
- testu ponownego uruchomienia ze wszystkimi starymi wariantami konfiguracji.

Nie wolno scalać tylko dlatego, że nazwy brzmią podobnie. Wspólny plugin musi mieć wspólną odpowiedzialność i cykl życia.

## 8. Twierdzenia o działaniu pozostają niepotwierdzone w realnym środowisku

Nie są „ukrytym błędem kodu”, ale wcześniej zbyt łatwo zastępowałem je wynikami testów automatycznych.

Nadal brak rzeczywistego potwierdzenia:

- Windows/Tk;
- prawdziwych serwerów ASA;
- rzeczywistego RCON;
- CurseForge wraz z realnymi plikami i logami;
- ASADedicatedManager Olrik-WP;
- klastra wielu map;
- rozpoznania już działających serwerów przy starcie;
- pełnej sekwencji DoExit → odejście → restart Managera → READY → wersja.

## 9. Restart Refreshera w środku procedury — NAPRAWIONE FAIL-CLOSED, BEZ AUTOMATYCZNEGO WZNAWIANIA

Program zapisuje teraz trwały `procedure_run` z `run_id`, mapą, etapem, snapshotem celów i harmonogramem. Checkpoint jest wymagany przed startem mapy oraz przed każdą komendą RCON. Brak trwałego zapisu blokuje wysłanie. Po wyniku zapisywane są etapy `command_done`, `command_failed` albo `doexit_sent`; następnie `waiting_for_return` i `map_verified`.

Po ponownym uruchomieniu istniejący checkpoint blokuje automatyczne RCON. Program nie wysyła ponownie komendy o niejednoznacznym wyniku. Operator musi ręcznie sprawdzić serwery i osobnym pierwszym kliknięciem usunąć blokadę; procedura nie rusza w tym samym kliknięciu. Nieudane trwałe usunięcie pozostawia blokadę.

Nie zaimplementowano automatycznego wznowienia od konkretnego etapu — celowo, ponieważ bez rzeczywistego dowodu ze środowiska byłoby to mniej bezpieczne niż fail-closed. Nadal potrzebny jest test Windows/ASA przerwania procesu po faktycznym `DoExit`.

## 10. Model stanu nadal jest rozproszony

Stan procedury jest rozłożony między flagami aplikacji, harmonogramem, koordynatorem, pluginem RCON, zakładkami, pendingami i dowodami wersji.

Naprawy lokalne mogą naruszyć powiązania, ponieważ nie ma jednego modelu przejść. To jest główna przyczyna kolejnych regresji.

Wymagana naprawa nie oznacza natychmiastowego wielkiego przepisywania. Najpierw trzeba zdefiniować model i adaptery, następnie migrować po jednym przejściu z regresjami zgodności.

## Aktualny bilans

Otwarte konkretne problemy implementacyjne lub architektoniczne: **8**. Punkty 4 i 9 pozostają w dokumencie jako zapis wykonanych napraw i nie są liczone jako otwarte; punkt 9 nadal wymaga rzeczywistej walidacji Windows/ASA.

Najpilniejsze:

1. trwałe transakcje dyskowe z journalem;
2. fault-injection zamiast testów tekstu;
3. trwały stan procedury po restarcie Refreshera;
4. dokończenie audytu wyjątków;
5. macierz i migracja pluginów;
6. centralny model stanu bez jednorazowego ryzykownego przepisywania.

V3.80.28 naprawia rozdzielenie właścicieli kolejki RCON, ale nie zamyka powyższej listy.
