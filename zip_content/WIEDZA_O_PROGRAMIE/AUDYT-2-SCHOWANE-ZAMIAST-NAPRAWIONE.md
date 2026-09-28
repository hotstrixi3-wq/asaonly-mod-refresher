# Audyt 2: miejsca nadal przedstawione lepiej, niż są naprawione

Data: 2026-09-21

Ten dokument koryguje zbyt mocne twierdzenia z V3.80.24–V3.80.26. Punkty poniżej nie mogą być oznaczone jako zamknięte.

## 1. Wyścig anulowania RCON — NAPRAWIONE W KODZIE

Plugin ma teraz jedną operację `cancel_pending()`, współdzielącą `dispatch_lock` z przejęciem komendy przez worker. Każda komenda otrzymuje numer generacji mapy. Anulowanie pod jedną blokadą:

- odmawia, jeśli wysyłanie już rozpoczęto;
- zwiększa generację wszystkich anulowanych map;
- usuwa elementy nadal oczekujące.

Element pobrany z kolejki tuż przed anulowaniem, ale jeszcze niewysłany, ma starą generację i `_claim_dispatch()` nie pozwoli go uruchomić. Koordynator zmienia swój stan dopiero po udanym wyniku tej atomowej operacji. Regresja sprawdza również przypadek elementu już wyjętego z kolejki ze starą generacją.

## 2. V3.80.26 — „transakcyjny zapis RCON” jest rollbackiem best-effort, nie transakcją gwarantowaną

**Co ogłosiłem:** że wcześniejsze zapisy są cofane i wszystkie katalogi są odtwarzane.

**Co jest naprawdę:** zapisuje mapy kolejno, a po błędzie usuwa katalogi i kopiuje migawki z katalogu tymczasowego. Sam rollback może zawieść z powodu uprawnień, blokady antywirusa, braku miejsca albo błędu kopiowania. Kod rollbacku nie ma drugiego poziomu ochrony ani raportu częściowego odtworzenia.

Dodatkowo kopia katalogu jest oparta na `app.server_files`. Jeśli ta mapa wskazuje brakującą albo nieaktualną ścieżkę, rzeczywisty katalog użyty później przez `save_tab()` może nie zostać zabezpieczony przed zapisem.

**Wymagana naprawa:** przygotować komplet nowych plików obok plików docelowych, zweryfikować je, a zatwierdzać atomowymi podmianami. Nie usuwać aktualnego katalogu przed potwierdzeniem, że odtworzenie jest możliwe. Raportować osobno błąd zapisu i błąd rollbacku.

## 3. V3.80.25 — „transakcyjna zmiana nazwy mapy” również jest rollbackiem best-effort

**Co ogłosiłem:** że błąd odtwarza pamięć, pendingi i pliki.

**Co jest naprawdę:** rollback usuwa katalog docelowy i globalny katalog konfiguracji, a następnie kopiuje migawki. Jeśli kopiowanie migawki zawiedzie po usunięciu bieżącego katalogu, stan może pozostać gorszy niż przed rollbackiem. Błąd wewnątrz rollbacku nie jest obsłużony jako osobny incydent.

**Wymagana naprawa:** etap przygotowania nowego katalogu bez niszczenia starego, atomowa zmiana nazw katalogów na tym samym woluminie, dziennik transakcji i odtwarzanie przy następnym uruchomieniu, jeśli proces zostanie przerwany.

## 4. Testy V3.80.25/V3.80.26 częściowo sprawdzają tekst źródła zamiast działania awarii

Testy `test_map_rename_never_deletes_preexisting_destination_directory`, `test_rcon_bulk_save_has_memory_and_disk_rollback` oraz test anulowania zawierają asercje typu `assertIn()` na tekście kodu.

Takie testy potwierdzają obecność instrukcji, ale nie wykonują kontrolowanego błędu w połowie zapisu, błędu samego rollbacku ani wyścigu worker–cancel. Przedstawienie ich jako dowodu transakcyjności było nierzetelne.

**Wymagana naprawa:** testy fault-injection z błędem na każdym kroku zapisu i odtwarzania oraz deterministyczny test bariery wątku dla wyścigu anulowania.

## 5. V3.80.24 — `prepare()` jest kontraktem umownym, którego host nie weryfikuje

Host nie wywołuje `start()` dla zapisanego OFF, co naprawia wcześniejszy konkretny problem. Jednak `prepare()` jest zwykłą metodą Pythona. Wadliwy plugin może uruchomić worker już w `prepare()`, a host nie potrafi tego wykryć ani zatrzymać.

Dla obecnych produkcyjnych pluginów `prepare()` zostało ręcznie ograniczone do konfiguracji, ale ogólne twierdzenie, że każdy plugin OFF „nie może uruchomić workera”, było za szerokie.

**Wymagana korekta:** gwarancja dotyczy wyłącznie sprawdzonych pluginów dostarczanych z programem. Dla pluginów zewnętrznych host gwarantuje tylko, że nie wywoła `start()` i nie przekaże wejść operacyjnych. Projekt nie wymaga ochrony przed pluginem złośliwym, ale nie wolno obiecywać technicznej niemożliwości pracy w `prepare()`.

## 6. Pełne scalenie i porządek pluginów nadal nie zostały wykonane

Backup/Przywracanie i Status/Historia są połączone, ale nie wykonano kompletnej macierzy migracji starych nazw, kafelków i wpisów konfiguracyjnych. Ten punkt został przesunięty przez kolejne paczki bezpieczeństwa zamiast zakończony.

## Wynik uczciwy

- **2 nowe konkretne błędy implementacyjne:** wyścig anulowania RCON i niegwarantowane rollbacki zapisu RCON.
- **1 analogiczna wada zmiany nazwy:** rollback best-effort przedstawiony jako transakcja.
- **1 wada metodologii testów:** asercje tekstowe zamiast fault-injection.
- **1 zbyt szeroka obietnica kontraktu `prepare()`.**
- **1 nadal pominięty zakres:** pełne porządkowanie/scalanie pluginów.

V3.80.25 i V3.80.26 nie mogą być przedstawiane jako ostatecznie transakcyjne ani jako zamykające tę listę.
