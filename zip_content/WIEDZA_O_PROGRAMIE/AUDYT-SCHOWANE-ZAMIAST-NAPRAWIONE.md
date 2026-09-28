# Audyt: rzeczy schowane zamiast naprawione

Data audytu: 2026-09-21

Ta lista rozdziela przypadki potwierdzone historią zmian od miejsc podejrzanych wymagających dalszego dowodu. Nie zaliczam do „schowania” poprawnych zabezpieczeń fail-closed ani celowego braku diagnostyki pluginu rzeczywiście OFF.

## Potwierdzone

### 1. V3.80.22 — schowanie niespójnego stanu pluginu OFF

**Co było zepsute:** zapisana konfiguracja mogła mówić `enabled: false`, podczas gdy obiekt pluginu nadal miał `enabled=True`.

**Co zrobiłem źle:** `_diagnostic_eligible()` wycinało taki plugin z diagnostyki, wyników, cache i logów, ale nie wyłączało jego stanu wykonawczego. Test celowo ustawiał nieaktualne `enabled=True` i sprawdzał wyłącznie, czy plugin zniknął z diagnostyki. W ten sposób test utrwalał ukrycie niespójności.

**Wersja wadliwa:** V3.80.22, commit `bf36435`.

**Stan obecny:** poprawione w V3.80.23 przez wspólną egzekucję stanu efektywnego, wywołanie `set_enabled(False)` oraz blokadę `tick`, hooków i zdarzeń. Pozostaje ograniczenie opisane w punkcie 4.

### 2. V3.80.15 — zastąpienie problemu etykietą „POMINIĘTY — PLUGIN OFF”

**Co było zepsute:** nie było jeszcze pełnego dowodu, że zapisany stan OFF po ponownym uruchomieniu jest stanem rzeczywistym pluginu.

**Co zrobiłem źle:** uznałem bieżący wynik `is_enabled()` za wystarczający, nie sprawdzając ponownego uruchomienia i rozjazdu konfiguracja–runtime. Dodałem za to widoczny wynik „POMINIĘTY — PLUGIN OFF”. To opisywało decyzję diagnostyki, ale nie dowodziło braku pracy pluginu.

**Wersja wadliwa:** V3.80.15, commit `085f5e8`.

**Stan obecny:** sama fałszywa etykieta została usunięta w V3.80.16, a egzekucję OFF dodano dopiero w V3.80.23.

### 3. Przed V3.80.21 — błędy zapisu przy zamykaniu były połykane

**Co było zepsute:** błąd zapisu konfiguracji mógł wystąpić podczas zamykania.

**Co robił program źle:** wyjątek/błąd nie blokował zamknięcia; aplikacja mogła się zamknąć i sprawiać wrażenie, że dane zapisano.

**Stan obecny:** poprawione w V3.80.21 — nieudany zapis blokuje zamknięcie i przebudowę GUI przy zmianie języka.

## Nadal niezamknięte albo tylko częściowo naprawione

### 4. Kontrakt startu pluginów OFF — NAPRAWIONE W KODZIE, OCZEKUJE NA TEST WINDOWS/TK

Host rozdziela teraz `prepare()` od aktywacji operacyjnej. Dla pluginu zapisanego jako OFF:

- wolno wykonać wyłącznie `prepare()` potrzebne do odczytu konfiguracji i panelu dostępnego podczas OFF;
- host nie wywołuje operacyjnego `start()`;
- plugin nie trafia do zbioru `_active`;
- nie dostaje `tick`, hooków, zdarzeń ani diagnostyki;
- plugin bez bezpiecznego `prepare()` nie jest w ogóle inicjalizowany podczas OFF.

Wszystkie produkcyjne pluginy opcjonalne otrzymały jawne `prepare()`. Test regresyjny używa pluginu, którego `start()` symuluje uruchomienie workera, i potwierdza, że przy zapisanym OFF `start()` nie zostaje wywołane ani razu. Test wszystkich produkcyjnych pluginów potwierdza również, że żaden zapisany OFF nie trafia do `_active`.

Ograniczenie: brak realnego uruchomienia Windows/Tk nadal pozostaje ograniczeniem walidacji, ale wcześniejsza luka architektoniczna „najpierw start, potem wyłącz” została usunięta.

### 5. Migracja wierszy RCON — NAPRAWIONE W KODZIE, OCZEKUJE NA TEST WINDOWS/TK

`analyze_rcon_lines()` zwraca teraz osobno bezpieczny model wykonawczy, pełną listę problemów z indeksami i przyczynami oraz niezmienioną kopię oryginalnych danych. Rekordy niebędące obiektami i rekordy ponad limit 20 nie znikają.

Automatyczny/globalny zapis mapy zachowuje oryginalną listę `lines` bez zmian, dopóki operator nie zastąpi jej świadomie w panelu RCON. Panel pokazuje czerwone ostrzeżenie, a zapis wymaga osobnego potwierdzenia zawierającego mapy i liczbę problematycznych rekordów. Dopiero potwierdzony zapis zastępuje stare dane poprawnym modelem widocznym w GUI. Wersjonowane stare pliki pozostają w katalogu mapy.

Regresje sprawdzają raport indeksów/przyczyn, zachowanie pełnego oryginału oraz to, że automatyczny `to_config()` nie nadpisuje go modelem skróconym.

### 6. Zmiana nazwy mapy — NAPRAWIONE W KODZIE, OCZEKUJE NA TEST WINDOWS/TK

Operacja wykonuje teraz migawki katalogu mapy i globalnego katalogu konfiguracji przed pierwszą zmianą. Zapis globalny został oddzielony od zbędnego ponownego zapisywania wszystkich map.

Jeżeli przeniesienie, migracja nazw plików, zapis mapy, zapis pendingów albo aktualizacja UI zgłosi błąd, program odtwarza:

- klucz i nazwę mapy w `tabs`;
- nazwę obiektu zakładki i tekst notebooka;
- pełną listę pendingów wraz z `targets` i `verified`;
- `server_files`;
- oryginalny katalog mapy z migawki;
- globalny katalog konfiguracji z migawki.

Hook RCON `on_tab_renamed` jest wywoływany dopiero po trwałym zatwierdzeniu, więc rollback nie próbuje odtwarzać wcześniej zatrzymanej kolejki pod starą nazwą. Istniejący katalog docelowy nadal blokuje operację przed jakimkolwiek usunięciem.

### 7. Część wyjątków odczytu monitoringu/logów jest zamieniana na „brak danych” lub ignorowana

**Miejsca:** przede wszystkim `asaonly/logtail.py`, `asaonly/monitor.py`, fragmenty `asaonly/monitor_plugin.py` i `asaonly/cf_wersje.py`.

**Problem:** występują szerokie `except Exception`, miejscami zakończone `pass`, `return None` albo ogólnym „brak danych”. Nie każdy taki przypadek jest błędem — część chroni pętlę monitorującą — ale bez klasyfikacji nie wiadomo, czy przyczyną jest normalny brak pliku, błąd uprawnień, błąd parsera czy błąd programu.

**Stan audytu:** podejrzenie, nie twierdzę jeszcze, że wszystkie te miejsca ukrywają defekt. Trzeba przejść każde wywołanie i oddzielić oczekiwane błędy środowiska od błędów kodu; te drugie muszą mieć jawny stan i ograniczony częstotliwościowo log.

## Czego nie wpisuję jako „schowanie błędu”

- brak diagnostyki dla pluginu rzeczywiście OFF — to wymagane zachowanie;
- blokowanie `DoExit` bez READY — poprawne fail-closed;
- brak restartu przy niepotwierdzonej wersji mapy — poprawne fail-closed;
- izolacja wyjątku jednego pluginu, o ile wyjątek jest raportowany przez `_report()`;
- pomijanie mapy, która nie używa zaktualizowanego moda — poprawna kwalifikacja.

## Uczciwy wynik

Potwierdzone historycznie przypadki schowania zamiast naprawy: **3**.

Otwarte problemy lub ryzyka wymagające naprawy/dowodu: **1**.

Następny punkt kolejki: sklasyfikować szerokie `except Exception`, usunąć ciche `pass` z przepływów operacyjnych i pozostawić je wyłącznie przy bezpiecznym sprzątaniu/UI.
