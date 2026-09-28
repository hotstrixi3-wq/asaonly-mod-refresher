# Lista rzeczy zapomnianych, niedokończonych lub nieudowodnionych

Data: 2026-09-21

Ta lista jest obowiązkową kolejką pracy. Nie wolno usuwać punktu na podstawie samego przejścia testów. Punkt można zamknąć dopiero po naprawie przyczyny, regresji odpowiadającej wymaganiu oraz uczciwym oddzieleniu testu automatycznego od integracji rzeczywistej.

## A. Rzeczy, o których zapomniałem w bieżącej kolejce

### 1. Pełny przegląd i scalenie pluginów o wspólnej odpowiedzialności

W ostatniej kolejce napraw skupiłem się na OFF, migracji RCON, zmianie nazwy mapy i wyjątkach. Nie wpisałem jako osobnego zadania przeglądu wszystkich pluginów pod kątem scalania.

Stan obecny:

- Backup i Przywracanie są jednym pluginem `81_backup_restore.py`;
- Status i Historia są jednym pluginem `70_status_historia_serwerow.py`;
- nie powstała udokumentowana macierz wszystkich pluginów: odpowiedzialność, panel, stan ON/OFF, konfiguracja, zależności i decyzja „zostaje osobno / zostaje scalony”;
- nie udowodniłem, że po wcześniejszych wersjach nie pozostały stare kafelki, wpisy konfiguracyjne, migracje albo zdublowane ścieżki funkcjonalne;
- nie odtworzyłem z wcześniejszych ustaleń kompletnej listy par/grup, które użytkownik chciał połączyć. Nie wolno zgadywać i scalać niepowiązanych funkcji.

### 2. Nie dokończyłem pełnego audytu szerokich `except Exception`

Naprawiono część krytycznych przypadków w monitoringu i CurseForge, ale w kodzie nadal istnieją szerokie wyjątki. Trzeba każdy sklasyfikować jako:

- oczekiwany błąd środowiska z jawnym stanem;
- bezpieczne sprzątanie GUI;
- izolacja pluginu z raportem;
- rzeczywisty błąd programu, którego nie wolno zamieniać na `pass`, `None`, „brak danych” lub fałszywy stan OK.

Szczególnie wymagają przeglądu: `logtail.py`, `monitor.py`, `monitor_plugin.py`, `server_tab.py`, `widgety.py`, `procedura.py`, główna aplikacja i pluginy administracyjne.

## B. Znane otwarte problemy techniczne

### 3. Zapis całego panelu RCON — NAPRAWIONE W KODZIE, OCZEKUJE NA TEST WINDOWS/TK

`_save_all()` waliduje wszystkie mapy przed zmianą pamięci i dysku, wykonuje migawki stanu każdej mapy i kopie jej katalogu, stosuje wszystkie zmiany bez zapisu, a następnie zapisuje konfiguracje i sekrety. Awaria dowolnej mapy odtwarza wartości połączenia, hasła, komendę administratora, presety, wiersze, stan migracji, katalogi wszystkich map i `server_files`.

### 4. Semantyka `flush()` i komendy RCON w locie — NAPRAWIONE W KODZIE

`flush()` zwraca teraz osobno liczbę usuniętych elementów kolejki i stan `inflight`; nie udaje anulowania rozpoczętego wywołania. Próba anulowania procedury jest blokowana, gdy jakakolwiek mapa ma komendę w locie, z jawnym komunikatem, że rozpoczętego wywołania sieciowego nie można cofnąć.

### 5. Rollback zmiany nazwy mapy nie ma rzeczywistego testu Windows/Tk

Kod tworzy migawki i odtwarza pamięć/dysk, ale dotychczasowa regresja kontroluje głównie strukturę kodu i funkcje pomocnicze. Nie wykonano kontrolowanego testu z rzeczywistym Tk/notebookiem i wymuszonym błędem zapisu na Windows.

### 6. Świadoma migracja uszkodzonych/nadmiarowych wierszy RCON nie ma testu GUI

Testy potwierdzają zachowanie oryginału przez `to_config()`, raport problemów i model wykonawczy. Nie wykonano rzeczywistego testu okna pokazującego ostrzeżenie, anulowanie migracji i potwierdzone zastąpienie danych.

### 7. Pełny przepływ włączenia/wyłączenia każdego pluginu nie został sprawdzony w prawdziwym GUI

Automatyczne regresje sprawdzają host, `prepare`, `_active`, ticki, hooki, zdarzenia i diagnostykę. Nie wykonano rzeczywistego cyklu Windows/Tk dla każdego pluginu:

OFF → zamknięcie → uruchomienie → brak pracy → ON → działanie → OFF → zatrzymanie → ponowne uruchomienie.

## C. Główne wymagania operacyjne nadal nieudowodnione w rzeczywistym środowisku

### 8. Brak realnej integracji RCON z działającymi serwerami ASA

Nie sprawdzono na prawdziwych mapach:

- testu połączenia;
- ręcznych komend;
- odpowiedzi komend;
- retry;
- lokalnych harmonogramów;
- końcowego `DoExit`;
- sekwencji wielu map;
- konfliktu sondy, ręcznej komendy i procedury automatycznej.

### 9. Brak realnej integracji z ASADedicatedManager Olrik-WP

Nie sprawdzono pełnego cyklu:

DoExit → zniknięcie serwera → trzy kontrole nieobecności wykonywane przez Manager → restart wykonywany przez Manager → log startowy → READY → potwierdzenie wersji.

Refresher nie może uruchamiać procesu ani udawać zachowania Managera.

### 10. Brak realnej integracji CurseForge–dysk serwera–log ASA

Testy sprawdzają kwalifikację wersji, ale nie wykonano realnego przebiegu z siecią CurseForge i rzeczywistymi artefaktami serwera. Nie potwierdzono w środowisku użytkownika, że identyfikatory plików i dowody z logu odpowiadają wszystkim używanym modom.

### 11. Rozpoznanie serwerów już działających przy starcie nie zostało sprawdzone na Windows

Logika i testy automatyczne istnieją, ale nie wykonano uruchomienia Refreshera przy już działającym klastrze z prawdziwymi PID, portami i logami.

### 12. Brak rzeczywistego testu awarii i powrotu serwera

Nie wymuszono kontrolowanie:

- braku procesu;
- ponownego startu przez Manager;
- timeoutu;
- READY bez wcześniejszego odejścia;
- odejścia bez późniejszego READY;
- READY bez potwierdzonej wersji;
- zewnętrznego restartu podczas procedury.

## D. Wymagania jakościowe, których nie wolno ponownie zgubić

### 13. Diagnostyka nadal nie jest testem funkcjonalnym

Wynik „DOSTĘPNY” potwierdza tylko bezpieczny test techniczny. Nie wolno przedstawiać go jako potwierdzenia działania RCON, backupu, CPU, importu ani monitoringu.

### 14. Wyniki automatyczne nie dowodzą kompletności operacyjnej

Liczba testów, kompilacja, commit i ZIP nie zastępują działania na Windows/Tk/ASA/RCON/ASADedicatedManager/CurseForge.

### 15. Nie wolno kończyć na schowaniu objawu

Każda przyszła poprawka musi odpowiedzieć osobno:

- jaki był stan rzeczywisty;
- jaka była przyczyna;
- czy praca nadal mogła odbywać się w tle;
- czy dane mogły zostać częściowo zapisane;
- czy UI tylko przestało pokazywać problem;
- jaki test wykazuje usunięcie przyczyny, a nie wyłącznie zmianę komunikatu.

## Kolejność dalszej pracy

1. macierz i scalenie pluginów według rzeczywistych wspólnych odpowiedzialności;
2. transakcyjny zapis wszystkich map i sekretów z panelu RCON;
3. jawna semantyka anulowania kolejki i komendy RCON w locie;
4. dokończenie klasyfikacji szerokich wyjątków;
5. testy GUI Windows/Tk dla OFF, migracji i zmiany nazwy;
6. pełna integracja z ASA, RCON, CurseForge i ASADedicatedManager Olrik-WP.
