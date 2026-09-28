# Wieloperspektywiczna weryfikacja ASAonly ModRefresher V3.80.17

Data: 2026-09-20

## Metoda

Sprawdzono cały przepływ, a nie tylko pojedyncze funkcje: start i import działających serwerów, pierwszy oraz kolejny odczyt CF, kwalifikację każdej mapy, pending, lokalne harmonogramy RCON, OFFLINE, nowy boot, READY, wersję załadowaną przez nowy proces, kolejkę następnych map, aktualizację przychodzącą w trakcie kolejki, zapis i migrację konfiguracji, backup/rollback, pluginy ON/OFF, zmianę języka oraz zachowanie paneli.

Perspektywy: administrator klastra, bezpieczeństwo serwera, spójność danych, operator GUI, plugin aktywny, plugin wyłączony, awaria pliku/ZIP, świeża instalacja, migracja ze starszej wersji i agent utrzymujący kod.

## Wynik względem trzech obowiązków

### Monitoring

- istniejący serwer jest adaptowany z ogona logu;
- READY wymaga markera, nie rozmiaru logu;
- monitor pamięta wcześniej widziany PID portu;
- zniknięcie portu przy martwym PID daje OFFLINE;
- Refresher nie uruchamia procesu za managera;
- stan UNKNOWN nie pozwala na automatyczne DoExit.

Ograniczenie terenowe: testy Linux nie potwierdzają prawdziwego `netstat/tasklist` ani PID StartTime na Windows.

### Wersje CurseForge i serwerów

- pierwszy check CF nie tworzy fałszywego baseline;
- porównanie odbywa się per mapa;
- mapa nieużywająca moda nie bierze udziału;
- mapa aktualna nie trafia do pending;
- mapa starsza trafia do pending;
- mapa o nieznanej wersji dostaje ostrzeżenie i nie jest restartowana;
- legacy pending jest ponownie kwalifikowany przed jakimkolwiek RCON;
- po nowym boocie sam dysk nie wystarcza: wymagana jest wersja raportowana przez nowy proces.

### Procedury RCON

- czasy użytkownika są zachowane, w tym 205 sekund;
- puste linie są ignorowane, półpełne odrzucane;
- dokładne DoExit jest odróżnione od tekstu czatu;
- automatyczne DoExit działa tylko z READY;
- tylko mapy z potwierdzoną potrzebą procedury trafiają do kolejki;
- jedna mapa działa naraz;
- następna czeka na nowy boot, READY i wersję procesu;
- aktualizacja CF podczas kolejki dostaje osobną turę po karencji.

## Perspektywa GUI i pluginów

- OFF nie wykonuje tła ani diagnostyki i ma puste pole diagnostyki;
- niedostępny PANEL jest wyszarzony;
- panel pozostaje dostępny przy OFF tylko tam, gdzie służy do konfiguracji (CPU, Status i historia);
- diagnostyka aktywnych pluginów uruchamia się po starcie i po zmianie języka;
- Importer nie skanuje sam, po imporcie czyści wyniki;
- Status i Historia są jednym pluginem;
- skan dysku nie startuje przy otwarciu i działa w workerze;
- RCON Admin waliduje port i blokuje podwójne wysłanie;
- Analizator nie obiecuje pełnego „OK”, tylko brak Fatal/Exception w ogonie 4 MB.

## Perspektywa danych i awarii

- różne zapisy w tej samej sekundzie tworzą osobne rewizje;
- konflikt legacy trafia do kwarantanny zamiast usunięcia;
- restore waliduje ścieżki i JSON, używa stagingu i rollbacku;
- zasymulowana awaria podczas drugiego katalogu przywraca pierwszy i pozostawia drugi bez zmian;
- diagnostyczny ZIP rekursywnie redaguje klucze JSON i typowe sekrety tekstowe oraz ma manifest;
- sekrety backupu pozostają opt-in.

## Testy

Zestaw obejmuje testy modułów, pluginów, bezpieczeństwa i symulacje klastra. Stress test administratora wykonuje 500 cykli na pięciu serwerach z rozłącznymi zestawami modów, losowymi seriami aktualizacji oraz aktualizacjami w trakcie kolejki.

Nowe testy po audycie sprawdzają między innymi:

- pełny pierwszy check CF: stara/aktualna/nieznana mapa oraz mapa nieużywająca moda;
- legacy pending przed RCON;
- dysk-only kontra wersja raportowana po boocie;
- duży log bez READY;
- martwy wcześniej widziany PID;
- UNKNOWN blokujący DoExit;
- redakcję diagnostycznego ZIP;
- walidację portu RCON;
- brak automatycznego skanu katalogów;
- rollback przy przerwaniu restore;
- dwie rewizje w tej samej sekundzie;
- kwarantannę konfliktu legacy;
- całkowity brak pracy Status/Historia przy OFF.

## Uczciwe ograniczenia

Automatyczne testy nie zastępują rzeczywistego testu Windows z prawdziwym ASADedicatedManagerem, procesami ASA, CurseForge i RCON. Nie ma podstaw, aby nazywać taki test wykonanym. Kod fail-closed ogranicza skutki braku dowodu: stan nieznany nie wywołuje automatycznego restartu ani przejścia kolejki.
