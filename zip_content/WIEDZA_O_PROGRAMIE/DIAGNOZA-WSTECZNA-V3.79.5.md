# Pełna diagnoza wsteczna przed dalszym rozwojem — V3.79.5

Data: 2026-09-20

## Zakres i zasada

Najpierw identyfikacja i ranking ryzyka, bez wdrażania Koordynatora i bez maskowania problemów zmianami kodu. Zielone testy nie są dowodem poprawności integracji Windows, Tk, RCON, ASADedicatedManagera ani operacji na prawdziwych danych.

Wynik bazowy: kompilacja Python OK; testy 70/70 PASS.

## P0 — ryzyko krytyczne

### P0.1 Przywracanie ZIP zapisuje bezpośrednio do aktywnej konfiguracji

`PLUGINY/81_backup_restore.py` testuje ZIP, filtruje nazwy i następnie wykonuje `extractall()` bez katalogu staging, kopii bezpieczeństwa, transakcji, walidacji JSON ani rollbacku. Częściowa awaria może pozostawić mieszaninę starej i nowej konfiguracji. Przywracanie jest opisane jako dopisywanie plików, więc stare nowsze pliki mogą nadal wygrać wybór `newest_matching()` i sprawić, że użytkownik zobaczy sukces, ale program nie załaduje przywróconych danych.

Wymagane: staging, ścisła walidacja wszystkich wpisów i JSON, plan zmian, snapshot aktualnego stanu, atomowa podmiana, rollback oraz raport, co faktycznie będzie aktywne po restarcie.

### P0.2 Koordynacja procedury — NAPRAWIONE W V3.80.3

Globalny zegar i stałe przesunięcia między mapami zostały zastąpione wymaganą kolejką stanową. Każdy tab ma lokalną oś czasu rebazowaną do zera, aktywna jest jedna mapa, a następna czeka na nowy cykl startowy, GOTOWY i weryfikację wersji poprzedniej.

## P1 — wysokie ryzyko operacyjne

### P1.1 Diagnostyczny ZIP nie wykonuje rzeczywistej redakcji

`PLUGINY/82_diagnostyka_zip.py` deklaruje usunięcie sekretów, ale po prostu dołącza wszystkie pliki JSON z `CONFIG_PROGRAM`. Dzisiaj sekret API jest w innym katalogu, lecz brak redaktora kluczy oznacza, że przyszła/legacy konfiguracja albo dane pluginów mogą wyciec. Pakiet ujawnia również pełne lokalne ścieżki logów, host systemu, porty i rozkład modów.

Wymagane: rekursywna redakcja nazw kluczy (`password`, `token`, `secret`, `api_key`, itp.), redakcja argumentów i logów, jawny manifest zawartości ZIP oraz test z zasianymi sekretami.

### P1.3 Migracje potrafią kasować legacy bez porównania danych

`asaonly/zapis.py:migrate_old_file()` usuwa stary plik, jeśli istnieje już dowolny plik wersjonowany. Nie porównuje zawartości ani nie archiwizuje konfliktu. To może bezpowrotnie usunąć jedyną poprawną konfigurację/sekret podczas migracji.

Wymagane: nigdy nie kasować konfliktu automatycznie; przenieść do kwarantanny i raportować.

### P1.4 Zbyt szerokie, nieme `except Exception`

W rdzeniu występuje wiele miejsc, gdzie błąd odczytu, migracji, monitoringu albo zatrzymania wątków jest ignorowany. Program może wystartować z pustą konfiguracją lub bez sekretu bez wiarygodnego alarmu. Szczególnie ryzykowne są `_load_config`, `_load_server_tabs`, migracje i `_on_close`.

Wymagane: rozdzielenie spodziewanych błędów od uszkodzeń danych, log z kontekstem i widoczny stan DEGRADED zamiast cichego przejścia dalej.

### P1.5 Kontrakt powrotu procedury — NAPRAWIONE W V3.80.3

Koordynator nie uznaje upływu czasu ani chwilowej zmiany statusu. Po dokładnej komendzie `DoExit` wymaga wzrostu `_boot_seq`, stanu GOTOWY opartego o marker startu serwera oraz lokalnej weryfikacji wersji. Refresher nie przejmuje od managera uruchamiania procesu.

## P2 — średnie ryzyko

### P2.1 Skan rozmiaru katalogów blokuje wątek Tk

`PLUGINY/83_dysk_katalogi.py` uruchamia rekurencyjny `os.walk()` bez limitu bezpośrednio z przycisku i automatycznie przy otwarciu panelu. Duży katalog logów może zamrozić GUI na długo.

Wymagane: worker, anulowanie, postęp, limity oraz odporność na symlinki/reparse points.

### P2.2 Historia JSONL — NAPRAWIONE W V3.80.12

Historia została połączona ze statusem w `70_status_historia_serwerow.py`. Ma rotację pięciu plików po 2 MB, a panel czyta ograniczony ogon 500 wierszy zamiast całego pliku.

### P2.3 RCON admin ma niepełną walidację i ryzyko blokowania operacyjnego

`PLUGINY/86_rcon_admin.py` konwertuje port przez `int()` poza workerem i bez obsługi błędu. Nie blokuje wielokrotnego wysłania tej samej komendy i nie pokazuje timeoutu/identyfikatora operacji. Potwierdzenie istnieje, ale `DoExit` nie jest traktowany specjalnie względem aktywnej procedury.

### P2.4 Analizator logów składa obietnice szersze niż analiza

`PLUGINY/84_analizator_logow.py` liczy proste regexy w ostatnich 4 MB. `Warning/Error` może obejmować tekst historyczny i fałszywe trafienia, a brak fatalu w ogonie nie oznacza zdrowego serwera. UI powinno mówić „licznik dopasowań w ogonie”, nie „Analiza OK”.

### P2.5 Status „Server has restarted OK” nie oznacza READY

Rzeczywisty log managera pokazuje, że ten komunikat pojawia się po odnalezieniu procesu, przed zakończeniem ładowania. Jedynym mocnym markerem gotowości w dostarczonym logu jest `Server has completed startup and is now advertising for join`.

### P2.6 Manager może nadpisywać priorytet CPU

Log Genesis pokazuje ustawianie `Normal`, `AboveNormal`, `High` i `RealTime` przy startach. Plugin CPU musi pokazywać aktualny stan i pochodzenie; nie może obiecywać trwałości ustawienia po restarcie serwera.

## P3 — dług techniczny i jakość

- Główny plik nadal ma około 1930 linii; rozdzielenie monolitu jest nieukończone.
- Styl wielu nowych pluginów jest skrajnie skompresowany, co utrudnia audyt i bezpieczne poprawki przez agentów.
- Self-testy pluginów często sprawdzają tylko dostępność funkcji/katalogu, nie prawdziwą operację.
- Brak testów integracyjnych Windows dla PID/StartTime, log watcherów, Tk, backup/restore i RCON.
- `save_versioned()` może nadpisać rewizję utworzoną w tej samej sekundzie; historia nie gwarantuje osobnej wersji dla każdej zmiany.
- Część logów zawiera pełne ścieżki, identyfikatory klastra, adresy i argumenty startowe; pakiety diagnostyczne wymagają polityki prywatności.

## Potwierdzenia z rzeczywistego Genesis_WP_management.log

- Crash aktywnego procesu: 3 nieudane kontrole co około 15 sekund, potem restart.
- Po restarcie powstaje nowy PID.
- Marker pełnego READY: `Server has completed startup and is now advertising for join`.
- Crash detection jest ponownie włączane 10 sekund po READY.
- Startup monitor deklaruje timeout 10 minut i jedną próbę automatycznego restartu.
- Manager potrafi ponownie podpiąć się po PID + StartTime + SessionName.
- Planowane zatrzymanie managera najpierw wyłącza crash detection.

## Kolejność napraw

1. Zabezpieczyć backup/restore i migracje danych przed częściowym zapisem lub utratą konfiguracji.
2. Dodać rzeczywistą redakcję sekretów w diagnostycznym ZIP.
3. Zaimplementować stanowy Koordynator: po zniknięciu serwera flaga `NIE MA / OFFLINE`, następnie ciągły monitoring aż manager podniesie nowy proces i serwer osiągnie GOTOWY.
4. Przenieść ciężkie operacje dyskowe poza Tk i dodać rotację historii.
5. Dopiero potem dalsze funkcje i kosmetyka.

## Decyzja bramkowa

Koordynator ma bazować na ustalonym kontrakcie stanu, bez dodatkowej wymyślonej bramki dla zewnętrznego `DoExit`: brak procesu oznacza `NIE MA / OFFLINE`; manager potwierdza brak swoimi kontrolami i podnosi serwer; Refresher obserwuje jego powrót do GOTOWY i dopiero wtedy przepuszcza następną mapę. Projekt przechodzi testy jednostkowe, ale integracja Windows nadal wymaga uczciwego oznaczenia jako niezweryfikowana automatycznie.
