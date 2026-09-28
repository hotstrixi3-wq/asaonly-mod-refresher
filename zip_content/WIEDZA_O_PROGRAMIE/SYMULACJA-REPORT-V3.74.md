# RAPORT SYMULACJI — ASAonly V3.74 (klaster 8 map)

Data: 2026-08-30 23:09:22

## Wynik: 62/62 PASS

| Metryka | Wartosc |
|---|---|
| Mapy (taby) | 8 |
| Mody w unionie | 10 (4 bazowe + 6 specyficznych) |
| Zapytania CF (batch) | 13 |
| Komendy RCON dostarczone | 21 (DoExit: 9) |

## V3.74 „BIBLIOTEKA WIEDZY” — wydanie wiedzowe (logika kodu bez zmian)

- **Do zipa wchodzi PRZYKLAD-HARMONOGRAMU-RESTARTOW-KLASTRA.md** (komplecik
  8 → 9 plików): pełna arytmetyka harmonogramu restartów klastra
  (najwolniejsza mapa 2:15 → rozjazd 3 min → jedna mapa pada naraz),
  tabela 8 map z przesunięciami, gotowe linie + JSON, opis zachowań
  programu i warunki braku startu procedury.
- **debug27 „ADMIN GODZINA ZERO” (nowy, 28/28, dwa deterministyczne biegi):**
  zalożenia admina co do sekundy — pierwszy RCON o T+5, 5 komunikatów
  na mapę (T+5/300/600/780/870 + przesunięcie 180·i), DoExit o T+900+180·i
  (±12 s, zmierzone odstępy 180,6 s), każda mapa wstaje w swoim slocie,
  zero PAD/KRACHLOOP/alarmów wisy, zero drugiej tury, czuwanie domknięte.
- **Harness po konsultacjach AI (inżynier + audyt narzędzi):** kanarki RCON
  (koniec fałszywych zielonych), auto-odkrywanie testów we flocie, checki
  czystości (UID, miejsce na dysku, zapis profil/), FakeClock — zegar
  przyspieszony ×20 (scenariusz 36 minut w ~2,5 minuty realnie).
- **Reguła wiedzy (user):** WIEDZA_O_PROGRAMIE i GitHub trzymają wyłącznie
  materiały o OSTATNIEJ sprawdzonej wersji — stary raport V3.73 wycofany
  z WIEDZY (historia: archiwum/wydania + GitHub wersje/ i Releases).

**Rytuał V3.74: kompilacja OK · środowisko 15 OK/0 BLAD · jednostkowe 39/39 ·
symulacja 62/62 · debug24 8/8 · debug25 54/54 · debug26 18/18 · debug27 28/28.**

## Testy (sterownik, klaster 8 map)

| # | Test | Wynik |
|---|---|---|
| 1 | 8/8 map GOTOWE po starcie (wstepny skan logu - INITIAL_SCAN_BYTES) | PASS |
| 2 | 'TheIsland' Mody z serwera = baza+- | PASS |
| 3 | 'Ragnarok' Mody z serwera = baza+[9000015] | PASS |
| 4 | 'Extinction' Mody z serwera = baza+[9000010, 9000011] | PASS |
| 5 | 'Aberration' Mody z serwera = baza+[9000012] | PASS |
| 6 | 'Valguero' Mody z serwera = baza+- | PASS |
| 7 | 'CrystalIsles' Mody z serwera = baza+[9000014] | PASS |
| 8 | 'Fjordur' Mody z serwera = baza+[9000013] | PASS |
| 9 | 'TheCenter' Mody z serwera = baza+- | PASS |
| 10 | pierwsze sprawdzenie CF zakonczone | PASS |
| 11 | 10/10 modow stan 'ok' (pierwsze widzenie = baseline, zero restartow) | PASS |
| 12 | dokladnie 1 zapytanie CF na 10 modow (batch) | PASS |
| 13 | zero zaleglosci po pierwszym widzeniu | PASS |
| 14 | Test RCON: OK dla TheIsland | PASS |
| 15 | Test RCON: blad Auth dla TheCenter (zle haslo) | PASS |
| 16 | reczna komenda admina dotarla do serwera | PASS |
| 17 | automat wykryl update i procedura ruszyla | PASS |
| 18 | procedura zakonczona | PASS |
| 19 | wykryto update Better Horde | PASS |
| 20 | 7 map pominietych (nie uzywaja Better Horde) | PASS |
| 21 | DoExit poszedl TYLKO na Extinction | PASS |
| 22 | ogloszenie T+1 wyslane na Extinction | PASS |
| 23 | czuwanie powrotu uzbrojone | PASS |
| 24 | klaster wrocil do GOTOWY | PASS |
| 25 | znana wersja Better Horde = 2002 | PASS |
| 26 | CFCore serwera zainstalowal Better Horde 2002 na Extinction | PASS |
| 27 | zero zaleglosci po procedurze | PASS |
| 28 | V3.41: CF NIE hameruje - 0 zapytan w trakcie procedury (interwal 30 s) | PASS |
| 29 | procedura bazowa ruszyla | PASS |
| 30 | procedura BH (druga) wystartowala po zakonczeniu czuwania #2 | PASS |
| 31 | update w trakcie czuwania #3 ZAPARKOWANY | PASS |
| 32 | czuwanie #3 zakonczone TIMEOUTM (TheCenter nie wrocil) | PASS |
| 33 | po timeout: auto-kolejna tura zapowiedziana (karencja 60 s) | PASS |
| 34 | procedura Ragnarok (czwarta) wystartowala | PASS |
| 35 | ROZJEZDZ restartow (PTK 11): DoExit map rozlozony >= 10 s | PASS |
| 36 | ogloszenia T+1 zsynchronizowane (zywe mapy w < 2 s) | PASS |
| 37 | TheCenter: 2 komendy po 3 probach bledu (zle haslo RCON) | PASS |
| 38 | DoExit NIE poszedl na TheCenter (auth fail) | PASS |
| 39 | CRASH GUARD: Aberration pominieta (T+13s) | PASS |
| 40 | CRASH GUARD: incydent mapy zalogowany | PASS |
| 41 | KRACHLOOP: alarm 3 krachy/15 min | PASS |
| 42 | Extinction: 3x DoExit lacznie (faza2 + baza + BH) | PASS |
| 43 | Ragnarok: 2x DoExit (baza + mod wlasny) | PASS |
| 44 | Ultra Stacks 1005 zainstalowany na WSZYSTKICH 8 mapach | PASS |
| 45 | Better Horde 2003 na Extinction (druga procedura) | PASS |
| 46 | Ragnarok Dilo Party 2502 po procedurze wlasnego moda | PASS |
| 47 | znane wersje po burzy: US=1005, BH=2003, RAG=2502 | PASS |
| 48 | Aberration wrocila do GOTOWY (po krachloopie) | PASS |
| 49 | TheCenter wrocil do GOTOWY (reczny restart) | PASS |
| 50 | lacznie pominietych map: 21 (7+7+7) | PASS |
| 51 | DoExit PORZUCONY gdy mapa laduje mody (audyt3) | PASS |
| 52 | automat WYL.: update zaparkowany (zaleglosc) | PASS |
| 53 | przycisk 'Wykonaj zalegle' aktywny | PASS |
| 54 | V3.41: po recznym restartu z instalacja - GODZENIE (petla usunieta) | PASS |
| 55 | wylaczona mapa: jej mod POZA zapytaniami CF (okno czasowe) | PASS |
| 56 | wylaczona mapa: brak zaleglosci od jej moda | PASS |
| 57 | po restarcie: 8 tabow wczytanych z taby/ | PASS |
| 58 | po restarcie: 8/8 map GOTOWY z samego skanu logu | PASS |
| 59 | po restarcie: klucz API zachowany | PASS |
| 60 | po restarcie: znane wersje zachowane (US=1005, BH=2003) | PASS |
| 61 | po restarcie: godzenie przetrwalo (Fjordur 2302, bez zaleglosci) | PASS |
| 62 | po restarcie: automat WYL. zachowany | PASS |
