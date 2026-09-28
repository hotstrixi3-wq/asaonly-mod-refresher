================================================================================
 ASAonly - (AUTO)Manual - ModRefresher (RCON)  (wersja 3.86.7)
================================================================================

ZMIANY W 3.86.7 "Powrót przez RCON" (28.09.2026):
- Korekta regresji 3.86.6: powrót potwierdza świeży READY albo świeża odpowiedź
  ListPlayers przypisana do nowego PID i czasu startu, sprawdzonych po odpowiedzi.
- Sonda działa także podczas czuwania kolejki i przy starym statusie GOTOWY.
- Spóźniona odpowiedź starego procesu, zmiana startu przy tym samym PID, crash,
  błąd RCON i niepotwierdzona tożsamość nie zamykają oczekiwania.
- Potwierdzenie przez RCON nie zatwierdza wersji modów ze starego logu.
- Szczegóły: V3.86.7-POWROT-RCON.md. Osobna kopia, bez wdrożenia.

ZMIANY W 3.86.6 "GOTOWY, alarmy i PADY" (28.09.2026):
- Sam nowy PID + czas startu nie potwierdza powrotu: potrzebny nowy znacznik READY.
- Ponowny odczyt starego logu i zwykła aktywność ze statusem GOTOWY nie wystarczają.
- Alarmy powrotu i RCON zmieniają nazwę razem z mapą; błąd zapisu wycofuje całą zmianę.
- PADY: domyślnie 2048 MiB; 0 wyłącza rotację; najnowsza i ostatnia pełna kopia
  każdej mapy są chronione. Stare formaty/obce pliki pozostają, z ostrzeżeniem o limicie.
- Notatka: V3.86.6-GOTOWY-ALARMY-PADY.md. Kopia robocza, bez wdrożenia.

ZMIANY W 3.86.5 "Po superteście" (27.09.2026):
- Powrót po DoExit także po crashu przy zamykaniu; PID + czas startu przy weryfikacji.
- Crashstack istniejący przy starcie śledzenia nie oznacza nowego padu.
- Alarmy RCON: odrzucone logowanie/połączenie pomija mapę; nieudany DoExit nie tworzy
  pętli automatycznych prób tej samej wersji. Po korekcie: ręczne wykonanie zaległości.
- Poprawione opisy odczekania, złej ścieżki logu i ponownego wykrycia tej samej wersji.
- Widoczne przyciski panelu RCON, pełny wiersz zaległości, kolory modów osobno dla map.
- Wyraźniejsze potwierdzenie ręcznego DoExit; zapisane komendy i harmonogramy zachowane.
- Notatka: V3.86.5-SUPERTEST.md. Bez wdrożenia na serwerze.

ZMIANY W 3.86.4 "Runda i dowody padu" (27.09.2026):
- Zapis ShooterGame.log i świeżych plików crash do WIEDZA_O_PROGRAMIE/PADY.
- PAD4 porównuje PID i czas utworzenia; nowy proces nie dowodzi przeżycia starego.
- Odczekanie po nowej wersji moda: domyślnie 5 min, ustawienie 0-60 min.
- Trwały czerwony alarm braku powrotu mapy; kolejka kontynuuje, bez uruchamiania
  serwerów przez Refresher. Potwierdzona na żywo obsługa RCON pozostaje bez zmian.
- Notatka: V3.86.4-RUNDA-I-PADY.md.

ZMIANY W 3.86.3 "Odzyskiwanie po recenzji" (27.09.2026):
- Bez wznowienia managera po niepełnym rollbacku; zachowanie dzierżawy przy błędzie.
- Obowiązkowy checkpoint, ponowienia strażnika i przycisk PONÓW ODZYSKIWANIE.
- Zachowany fallback CF; niepewny DoExit aktualizacji serwera rozstrzyga proces.
- Backup bez sekretów pomija także zagnieżdżone katalogi sekretów.
- Notatka: V3.86.3-RECOVERY.md. Pierwsza runda modów na żywo 27.09 potwierdziła
  ListPlayers oraz DoExit z odpowiedzią Exiting... na trzech mapach.

ZMIANY W 3.86.2 "Dziennik w pliku i spokojny restart" (po analizie logów z 26.09.2026,
opis: WIEDZA_O_PROGRAMIE/V3.86.2-DZIENNIK-W-PLIKU-I-SPOKOJNY-RESTART.md):
- DZIENNIK W PLIKU: cały dziennik zdarzeń (to, co widać w oknie konsoli, bez
  kolorów) trafia też do WIEDZA_O_PROGRAMIE\dziennik-zdarzen.txt - z datą na
  starcie i przy zmianie dnia, najwyżej 5 plików po 5 MB. Dotąd napis przy starcie
  mówił "zapis też w asa_debug.log", ale tam idą tylko ukryte błędy programu -
  przebieg aktualizacji z 26.09 dało się odtworzyć tylko ze zrzutu ekranu.
  Plik jest też w ZIP-ie diagnostyki.
- SPOKOJNY RESTART: po DoExit wysłanym przez kolejkę zniknięcie procesu to plan,
  nie awaria - "serwer zamknięty po DoExit (planowy restart)" zamiast "PAD: proces
  zniknął bez śladu crasha (zdechł cicho)", OFFLINE na żółto zamiast na czerwono.
  Plugin CPU pisze do dziennika dopiero przy GOTOWY (zmiany robił i tak tylko po
  GOTOWY i karencji) - koniec czerwonych "[CPU] ... brak procesu" przy każdej
  fazie startu. Ślad crasha w logu nadal daje PAD. Druga linia wpisu [CPU]
  zaczyna się od "→" zamiast znaku U+21B3 (w oknie cmd był prostokątem).
- OKNO KONSOLI BEZ ZATRZYMAŃ: program wyłącza w swoim oknie tryb szybkiej edycji
  (kliknięcie nie włącza zaznaczania, więc nic nie wstrzymuje wypisywania),
  przy zamknięciu przywraca poprzedni tryb. Kopiowanie: menu okna -> Edytuj ->
  Zaznacz albo plik dziennika.

ZMIANY W 3.86.1 "Pierwsze uruchomienie 3.86 na żywo" (26.09.2026):
- PIERWSZA RUNDA NA ŻYWO: cache 25535041 pobrany w ok. 1,5 min, potem Extinction,
  Genesis 1 i Ragnarok po kolei: po 40 plików (11238.7 MB) skopiowanych w 9-10 s,
  manager wstrzymany najwyżej ok. 40 s na mapę i sam podniósł serwery na nowym
  buildzie.
- "MISSING CONFIGURATION": świeżo pobrany SteamCMD za pierwszym razem nie miał
  jeszcze danych o serwerze ASA (pusta appcache) i skończył się błędem; 3.86.0
  czekała 5 min do następnej próby (ta się udała). Teraz ponowienie od razu,
  do 2 razy co 10 s. Inne błędy - jak dotąd: przerwa 5/15/30 min, zero restartów.
- DZIENNIK: linia "Failed installing AppID ..." z content_log.txt jest
  rozpoznawana (3.86.0 pisało "no entries in content_log.txt", choć wpis był);
  gdy nic nie pasuje: "brak rozpoznanej linii błędu". Liczba plików przed
  i w trakcie kopiowania liczy appmanifest (było "39 plików", potem "40/40").

ZMIANY W 3.86.0 "Aktualizacja serwera przez własny cache" (opis: WIEDZA_O_PROGRAMIE/V3.86-AKTUALIZACJA-SERWERA-PRZEZ-CACHE.md):
- DLACZEGO: 25.09.2026 wersja 3.85 zrestartowała serwery 9 razy (3 mapy po 3
  razy) i ani razu ich nie zaktualizowała. SteamCMD refreshera uruchamiany na
  katalogu mapy potrzebował spisu plików (manifestu) buildu, który leżał na
  mapie; miał go tylko SteamCMD managera, który te mapy instalował. Steam
  odmawiał go anonimowo ("Access Denied"), a plugin po wyłączeniu serwera
  i tak wznawiał managera - ten podnosił serwer na starym buildzie.
- WYKRYWANIE CO MINUTĘ: api.steamcmd.net (nieoficjalna usługa, nie Valve;
  można wyłączyć w panelu). Gdy nie odpowiada - SteamCMD co 5 min; przy
  działającym API SteamCMD raz na godzinę kontrolnie.
- WŁASNY CACHE: nowy build od razu trafia SteamCMD-em do folderu
  "ASA UPDATES REFRESHER" obok serwerów, gdy serwery dalej działają.
  Pierwsze pobranie to cały serwer (ok. 12 GB, program sprawdza miejsce),
  potem tylko różnice. Błąd pobierania = ŻADEN restart; w dzienniku
  prawdziwy powód z content_log.txt SteamCMD i następna próba po 5/15/30 min.
- PODMIANA TYLKO ZMIENIONYCH PLIKÓW: gotowy cache -> plan różnic jeszcze przy
  działającym serwerze -> zwykła kolejka (gracze, ogłoszenia, jeden start
  naraz) -> po wyłączeniu serwera kopia tylko różniących się plików, każdy
  przez plik tymczasowy, stare do kopii zapasowej, appmanifest na końcu.
  Błąd = wszystko wraca, serwer wstaje na dotychczasowym buildzie. Awaria
  refreshera w trakcie = strażnik najpierw cofa kopiowanie, potem wznawia
  managera. Światy i konfiguracje (ShooterGame\Saved) nigdy nie są ruszane.
- JEDEN UPDATER: włączone w managerze "Enable automatic update checking" =
  plugin nic nie robi i pisze dlaczego (manager przed swoją aktualizacją
  zabija każdy steamcmd.exe). Z user.config managera czytane są tylko te
  ustawienia - bez haseł i tokenów.
- JEDEN RESTART, NIE DWA: gdy Steam ma już nowszy build niż cache, mapy
  czekają, aż cache go dogoni; w trakcie rundy restartów cache nie jest ruszany.
- Testy: python symulacja/run_all.py - 330 testów (329 OK, 1 pominięty); nowe
  tests/test_synchronizacja.py, przepisane testy pluginu 88 i ścieżki
  produkcyjnej (w tym regresja: nieudane pobieranie = zero komend RCON).

ZMIANY W 3.85.4 "Autorzy kodu w O programie":
- "O programie" wymienia obu autorów kodu: Arena.ai Agent Mode (do wersji
  3.80.35) i Claude (Anthropic) od wersji 3.81 - kolejka restartów, kontrola
  czasu, pełna wersja angielska, aktualizacja serwera przez SteamCMD i dalsze
  poprawki. Pomysł i koncepcja: @Magus - bez zmian.

ZMIANY W 3.85.3 "Porządek w górnej części okna":
- PASEK "PLUGINY": przyciski pluginów (RCON, KONTROLA CZASU, UPDATE SERWERA,
  IMPORT / BACKUP) i MANAGER PLUGINÓW mają własny pasek pod górnym rzędem;
  w wąskim oknie zawijają się do drugiej linii. Wcześniej jeden rząd wypychał
  je - razem z "Wykonaj zaległe aktualizacje" i "Anuluj procedurę" - poza
  okno o domyślnej szerokości.
- PROCEDURA W RAMCE STATUS: "Sprawdź mody teraz", "Wykonaj zaległe
  aktualizacje" i "Anuluj procedurę" stoją razem; przełączniki automatu
  zostają na swoim miejscu.
- "ZAPISZ TAB" POD POLAMI MAPY: każdy tab miał własny przycisk, ale stał
  w górnym rogu i wyglądał na wspólny. Teraz jest pod polami mapy, które
  zapisuje, a obok znacznik "● niezapisane zmiany" tej mapy.
- POLE KLUCZA API zwęża się w wąskim oknie, zamiast chować "Zapisz klucz".
- Testy: python symulacja/run_all.py - 291 testów (290 OK, 1 pominięty);
  nowy tests/test_uklad_okna.py uruchamia prawdziwe okno programu.

ZMIANY W 3.85.2 "Okno nie staje po kliknięciu w konsolę":
- PRZYCZYNA "BRAK ODPOWIEDZI": dziennik drukował wątek okna programu. Kliknięcie
  w czarne okno konsoli włącza w Windows zaznaczanie i od tej chwili każdy zapis
  do konsoli czeka na koniec zaznaczania - stawało całe okno, automat, kolejka
  i pluginy. Teraz konsolę pisze osobny wątek: przy zaznaczaniu wstrzymuje się
  tylko wypisywanie, a zaległe linie pojawiają się po Esc / Enter / prawym
  przycisku myszy. Błędy zdarzeń okna trafiają do dziennika i asa_debug.log.
- AKTUALIZACJA SERWERA: bezpiecznik "brak DoExit przez 300 s" działa z osobnego
  licznika czasu, nie z wątku okna - wstrzymany manager wraca nawet wtedy, gdy
  okno programu stoi.
- Testy: python symulacja/run_all.py - 287 testów (286 OK, 1 pominięty).

ZMIANY W 3.85.1 "Poprawka po pierwszym uruchomieniu na Windows" (opis: WIEDZA_O_PROGRAMIE/V3.85-AKTUALIZACJA-SERWERA-STEAMCMD.md):
- NA WINDOWS DZIAŁA: pobranie SteamCMD, sprawdzenie buildu na Steamie (build
  25489097, manifest 8699400601246504390 - ten sam, który widziało API w managerze),
  dostęp do procesu managera. Mapy miały już ten build (zaktualizowane w nocy
  ręcznie w managerze), więc plugin słusznie nic nie robił.
- POPRAWKA: host pluginów woła activate(), nie start() - plugin 88 nie miał
  activate(), więc przy starcie nie wznawiał managera wstrzymanego przez
  poprzednie uruchomienie, a pierwsze sprawdzenie szło od razu zamiast po minucie.
- POPRAWKA: zmiana języka w trakcie instalacji podmieniała zamrażarkę - manager
  zostałby wstrzymany po instalacji. Odzyskanie po awarii nie rusza dzierżawy
  żywego refreshera.
- Testy: python symulacja/run_all.py - 283 testy (282 OK, 1 pominięty).

ZMIANY W 3.85 "Aktualizacja serwera przez SteamCMD" (opis: WIEDZA_O_PROGRAMIE/V3.85-AKTUALIZACJA-SERWERA-STEAMCMD.md):
- NOWY PLUGIN "AKTUALIZACJA SERWERA (STEAMCMD)" (przycisk UPDATE SERWERA).
  Powód: updater managera (metoda CDN) potrafi twierdzić "up to date", choć
  Steam ma nowy build - w jego logach 24.09 o 22:56:46 sprawdzenie przez API
  Steama widziało nowy manifest, a o 22:57:12 updater CDN: "Server is up to date".
- CO ROBI: co 20 min pyta Steama własnym SteamCMD (bez starego appinfo.vdf)
  o najnowszy build serwera ASA i porównuje z appmanifest_2430930.acf każdej
  mapy. Mapa GOTOWA ze starszym buildem idzie zwykłą kolejką restartu
  (sprawdzenie graczy, ogłoszenia z jej harmonogramu, pusta = od razu, jeden
  start naraz). Tuż przed DoExit plugin WSTRZYMUJE proces managera (inaczej
  podniósłby serwer po ~30 s, w trakcie instalacji), SteamCMD instaluje nowy
  build, plugin sprawdza appmanifest i WZNAWIA managera - manager sam podnosi
  zaktualizowany serwer, jak po każdym DoExit. Refresher nadal nie uruchamia
  serwerów.
- MAPA Z WYŁĄCZONYM SERWEREM (OFFLINE/CRASH albo od 30 min nie GOTOWA, np.
  pętla krachów po modzie, który wymaga nowego serwera) i bez działającego
  procesu serwera: aktualizacja bez DoExit; kolejka restartów czeka w tym
  czasie. Gdy proces serwera działa - manager nie jest wstrzymywany, a
  aktualizacja idzie kolejką, gdy mapa będzie GOTOWA.
- BEZPIECZNIKI: plik dzierżawy + osobny strażnik (manager zostaje wznowiony
  nawet po awarii refreshera), limity czasu, najwyżej 3 nieudane próby na build,
  warunki sprawdzane PRZED ogłoszeniami, mapy ze wspólnej instalacji i katalogi
  bez appmanifest pomijane.
- WYMAGANIA: refresher jako administrator; manager musi działać; w managerze
  nic nie zmieniać (AutoApplyUpdates = False zostaje). SteamCMD pobiera się sam
  od Valve do katalogu STEAMCMD obok programu.
- RDZEŃ: zlecenia restartu od pluginów (plugin może dać mapę do kolejki i dostaje
  wywołanie przed/po DoExit); start z pracą pluginu nie jest zapisywany jako czas
  startu mapy.
- NIE SPRAWDZONE NA PRAWDZIWYM WINDOWS: SteamCMD i wstrzymanie managera (testy na
  atrapach). Pierwsze sprawdzenie minutę po starcie pokaże w dzienniku, czy
  SteamCMD podaje build.
- Testy: python symulacja/run_all.py - 280 testów (279 OK, 1 pominięty).

ZMIANY W 3.84 "Pełna wersja angielska i porządki" (opis: WIEDZA_O_PROGRAMIE/V3.84-ANGIELSKI-I-PORZADKI.md):
- WERSJA ANGIELSKA KOMPLETNA: po przełączeniu EN po angielsku są okna, Manager
  Pluginów, wszystkie 11 pluginów (nazwy, opisy, panele, okienka), kolejka
  procedury, kontrola czasu i wpisy dziennika. Wcześniej po angielsku był tylko
  słownik głównego okna. Nowy moduł asaonly/jezyk.py: t("polski", "English").
  Test tests/test_i18n.py nie przepuści polskiego tekstu poza t()/TR.
- PORZĄDKI: usunięty martwy kod po przenosinach 3.75-3.83 (dawny import taba
  z pliku, edytor linii RCON sprzed pluginu 86, stare API koordynatora kolejki,
  40 nieużywanych kluczy TR, nieużywane importy i plik testowy).
- DOKUMENTACJA: README i MANUAL bez przycisków, których już nie ma ("+ Tab
  z backupu", "Zapisz sekret"); dane RCON wpisuje się w panelu RCON (także
  w podpowiedzi pierwszego uruchomienia).
- POPRAWKI: CPU - cel affinity spoza komputera (np. "CPU 12" przy 8 CPU) nie
  jest już pokazywany jako ZGODNE; zamknięcie panelu CPU w trakcie testu i okna
  dysku w trakcie skanu nie daje błędów; RCON - nieudane wstawienie ręcznej
  komendy do kolejki nie blokuje mapy.
- CPU: preset affinity zapisuje się jako identyfikator (all, first_half...).
  Stare zapisy działają; wersje 3.83 i starsze nie rozpoznają nowego zapisu.
- STARTER .bat: końce linii CRLF, same znaki ASCII.
- Testy: python symulacja/run_all.py - 225 testów (224 OK, 1 pominięty).

ZMIANY W 3.83 "Jeden plugin konfiguracji" (opis: WIEDZA_O_PROGRAMIE/V3.83-KONFIGURACJE-JEDEN-PLUGIN.md):
- IMPORTER STARYCH KONFIGURACJI I BACKUP / PRZYWRACANIE TO TERAZ JEDEN PLUGIN
  "Konfiguracje — import, backup, przywracanie": jeden przycisk IMPORT / BACKUP,
  jeden panel z dwiema zakładkami, jeden przełącznik ON/OFF. Działanie obu części
  bez zmian.
- ZAPISANE WYBORY PRZECHODZĄ SAME: plugin jest ON, jeśli którykolwiek ze starych
  był ON; oba wyłączone = OFF.
- STARE PLIKI (80_importer_starych_konfigow.py, 81_backup_restore.py) - jeśli
  zostaną w PLUGINY po rozpakowaniu na starą wersję, program ich nie ładuje
  (wpis w dzienniku); można je usunąć.
- NAPRAWA: po przywróceniu backupu program zamyka się BEZ zapisu. Wcześniej
  zwykłe zamknięcie zapisywało stary stan z pamięci i przywrócona konfiguracja
  znikała przy następnym uruchomieniu. Przywracanie jest zablokowane w trakcie
  procedury restartu.
- Testy: python symulacja/run_all.py - 216 testów (215 OK, 1 pominięty).

ZMIANY W 3.82 "Kontrola czasu" (pełny opis: WIEDZA_O_PROGRAMIE/V3.82-KONTROLA-CZASU.md):
- NOWY PLUGIN "KONTROLA CZASU RCON" (przycisk KONTROLA CZASU): sprawdza ręczne
  ustawienia czasu w harmonogramach RCON tymi samymi regułami co procedura.
  BŁĄD = mapa, którą procedura pominie (zły port, wiersz w pół wypełniony,
  brak DoExit...). UWAGA = czekanie bez komunikatu, komunikat "za 15 minut"
  niezgodny z czasem do DoExit, linie po DoExit, ślad starego wspólnego zegara.
- PODGLĄD FALI: kiedy każda mapa odlicza, dostaje DoExit i wraca - liczone
  PRAWDZIWYM planistą kolejki; scenariusze map pustych i z graczami.
- TYLKO ODCZYT: niczego nie wysyła do serwerów. Nowe błędy i uwagi trafiają
  do dziennika (bez powtórzeń). Domyślnie włączony.
- POPRAWKI: cyfra typu "²" w czasie albo porcie nie wywraca już procedury;
  ostrzeżenie o czekaniu bez komunikatu dopiero od 60 s.
- Testy: python symulacja/run_all.py - 206 testów (205 OK, 1 pominięty).

ZMIANY W 3.81 "Kolejka i gracze" (pełny opis: WIEDZA_O_PROGRAMIE/V3.81-KOLEJKA-I-GRACZE.md):
- AKSJOMAT: MODY PODNOSI SAM SERWER przy każdym starcie (wbudowany CFCore),
  manager podnosi procesy. Refresher to AKCELERATOR: żadna mapa nie zatrzymuje
  reszty, na ścieżce automatycznej zero okienek, przerwana procedura jest
  porzucana (nie blokuje automatu jak w 3.80.35).
- WYKRYWANIE GRACZY: przed odliczaniem mapy program pyta serwer przez RCON
  "ListPlayers". PUSTO = restart OD RAZU, bez komunikatów i bez czekania
  (inne komendy, np. SaveWorld, zostają). GRACZE albo NIE WIADOMO = Twój
  harmonogram bez zmian. Przed DoExit pustej mapy - drugie pytanie.
  Przełącznik "Pusta mapa: restart od razu" obok Automatu RCON.
  UWAGA: tekst pustego serwera "No Players Connected" nie jest potwierdzony
  dla ASA - surowa odpowiedź serwera idzie do dziennika (klucz
  "listplayers_pusto" w CONFIG_PROGRAM, gdyby trzeba było go poprawić).
- INTELIGENTNA KOLEJKA: STARTUJE NAJWYŻEJ JEDNA MAPA NARAZ (dysk SSD).
  Puste mapy pierwsze, ogłoszenia równolegle i "na styk" według czasów startu
  ZMIERZONYCH na Twojej instalacji (5 ostatnich pomiarów na mapę; mapa bez
  pomiaru bierze pomiar innej mapy; zero pomiarów = kolejna mapa po powrocie
  pierwszej). Mapa, która wstała sama z nową wersją, wypada z kolejki;
  mapa nieudana = następna mapa.
- CZASY W TABIE SĄ LOKALNE DLA MAPY (od początku jej odliczania), nie od
  wykrycia update'u. Rozjazd między mapami robi kolejka.
- ZAZNACZONE PUSTE WIERSZE RCON SĄ POMIJANE (3.74 zatrzymywała przez nie
  procedurę całego klastra). Mapy z błędem (port, harmonogram, brak DoExit)
  są pomijane pojedynczo.
- WERYFIKACJA WERSJI Z PRAWDZIWEGO LOGU ASA (LoadGameMods .../83374/<ModID>_<FileID>/);
  "Log file open" zeruje dowody starego procesu.
- NAPRAWY: błąd monitora co 10 s ("free variable 'e'") i pusty tekst błędu;
  koniec kolejki znów zapisuje konfigurację; alarm utkniętego pobierania mówi
  o pobieraniu przez serwer (CFCore); analizator logów zna prawdziwe linie CFCore.
- MIGRACJA Z 3.74: skopiuj CONFIG_PROGRAM, CONFIG_SECRET_API i CONFIG_MAPS_TABS
  do nowego folderu. Przejrzyj czasy w tabach (teraz lokalne).
- Testy: python symulacja/run_all.py - 176 testów (175 OK, 1 pominięty)
  + próba PRAWDZIWEJ aplikacji (symulacja/e2e_prawdziwy_app.py).
- Wersje 3.75-3.80.35 (pluginy, koordynator, admin RCON) są opisane w osobnych
  notatkach w WIEDZA_O_PROGRAMIE (pliki V3.7x-*.md i V3.80*.md).

ZMIANY W 3.74.1 "MIT i GitHub" (licencja + publikacja, kod bez zmian):
- LICENCJA MIT - plik LICENSE w korzeniu archiwum. Program jest i będzie
  100% darmowy; każda kopia niesie copyright Piotra (GAF).
- PUBLIKACJA NA GITHUBIE - źródło żyje na https://github.com/hotstrixi3-wq/asaonly-modrefresher
  (zip do pobrania w zakładce Releases).
- LOGIKA PROGRAMU BEZ ZMIAN - wszystkie teksty kompletu certyfikowane
  przez PogromcaKwiatkow (skan całego zipa: 0 kwiatków).

ZMIANY W 3.74 "Biblioteka wiedzy" (wiedza w komplecie, kod bez zmian):
- DO ZIPA WCHODZI PRZYKLAD-HARMONOGRAMU-RESTARTOW-KLASTRA.md - gotowy
  wzor konfiguracji dla admina klastra: pelna tabela 8 map (komunikaty
  dla graczy T+5/300/600/780/870, restart 15 min po wykryciu update'u,
  rozjazd co 3 min - najdluzszy restart 2:15 miesci sie z zapasem).
  Poparty testem "ADMIN GODZINA ZERO" (debug27, 28/28).
- SWIEZY RAPORT Z TESTOW w zipie (SYMULACJA-REPORT-V3.74) - pelny rytual
  wydania 3.74 z nowym testem godziny zero.
- LOGIKA PROGRAMU BEZ ZMIAN - zmiana typu bibliotecznego (dokumentacja
  + metadane wersji 3.74; nic w mechanice programu).

ZMIANY W 3.73 "Polski słuch" (naprawy z podwójnego audytu AI):
- WYKRYWANIE PADÓW DZIAŁA TEŻ NA POLSKIM WINDOWSIE. Windows z polskim
  językiem wypisuje w netstat stan "NASŁUCHUJĄCE" zamiast angielskiego
  "LISTENING" — przez tę różnicę detekcja PAD-ów CICHO NIE DZIAŁAŁA
  u adminów z polskim systemem. Teraz program rozumie oba słowa,
  a nawet warianty z utraconymi ogonkami (np. "NAS?UCHUJ?CE" po
  złym dekodowaniu pliku).
- OPÓŹNIENIE CF DZIAŁA NAPRAWDĘ: przy listach powyżej 50 modów zapytania
  do CurseForge jadą w paczkach po 50, a MIĘDZY PACZKAMI program czeka
  wskazaną liczbę sekund (pole w ustawieniach, domyślnie 1 s,
  maksymalnie 60 s). Wcześniej to pole było ozdobą.
- UTKNIĘTE POBIERANIE MODA: próg ostrzeżenia podniesiony z 10 do 20
  minut — duże mody ściągają się długo bez postępu w logu, było za
  dużo fałszywych alarmów.
- KAFELKI MAP na pasku statusu pokazują stan sondy: [SONDA] = program
  właśnie sonduje mapę przez RCON, [WISI!] = podejrzenie wisy.
- KOMUNIKAT AUTOMATU RCON MÓWI PRAWDĘ: "update'y startują same (kolejna
  tura 60 s po GOTOWY)" — wcześniej tekst obiecywał pytanie, którego
  nie było (poprawione w PL i EN).

ZMIANY W 3.72 "Marsz przyciskowy" (testy od strony użytkownika):
- KAZDY PRZYCISK PROGRAMU PRZETESTOWANY KILKUKROTNIE JAK U PRAWDZIWEGO
  UŻYTKOWNIKA (debug25, 54 checki): także anulowania wyboru pliku/folderu,
  duplikaty nazw map, złe hasło RCON, śmieci w polu interwału, pusta
  komenda admina, klik w trakcie sprawdzania, przełączniki po 3-4 razy.
  Całość: zero błędów Tk, zero wiszących okien dialogowych.
- Nowe testy w flocie: debug24 (fix 3.71.1) i debug25 (marsz przyciskowy).

ZMIANY W 3.71 "MASZYNA" + poprawka 3.71.1 (mapa-logiki):
- Monitor procesów i portów (skan co 10 s): PAD pewny (proces zniknął),
  PAD4 (śląd crasha w logu, a proces żyje - okno 90 s), samorestarty
  serwera (GOTOWY->STARTUJE bez człowieka), "Downloading mod" bez postępu.
- WISI: cisza w logu 15 min -> sonda RCON (listplayers, tylko odczyt),
  20 min -> alarm "serwer chyba wisi"; powrót logu = informacja.
- Moduł CurseForge: dioda stanu CF; gdy CF pada - sonda jednego moda
  (najmniejszy ID) w rytmie 1/3/15 min zamiast spamu.
- Dziennik stanu modów przed każdą procedurą (rotacja 15x10 KB).
- Okienko "wykonać zaległe?" po powrocie klastra ZASTĄPIONE automatyczną
  kolejną turą z karencją 60 s (odwołanie: wyłączenie automatu).
- Przycisk WYKRYJ (skan logów + dopasowanie modów), kafelki map klikalne
  (wybór zakładki), chipy NOWY dla niezweryfikowanych list modów.
- 3.71.1: naprawa crasu monitora po zmianie języka EN/PL lub dodaniu
  mapy po starcie (stan per-tab od urodzenia; snapshot w wątku; koniec
  pytań o "niezapisane zmiany" zaraz po przełączeniu języka).
- Testy: symulacja klastra 62/62, debug24 8/8, fuzz 11/11.

ZMIANY W 3.70 "Przyciski same mówią, co robią" (zgłoszenie usera):
- PYTANIE O NIEZAPISANE ZMIANY PRZY ZAMYKANIU DOSTAŁO WŁASNE TRZY PRZYCISKI
  z pełnymi opisami (zamiast oklejanego Tak/Nie/Anuluj, gdzie trzeba było
  czytać legendę w treści):
    [ Zapisz i zamknij ]
    [ Zamknij i nic nie zapisuj ]
    [ Nie zapisuj i nie zamykaj ]
  Esc i krzyżyk okna dialogu = "Nie zapisuj i nie zamykaj".
- Treść pytania skrócona do jednego zdania (legendy nie potrzeba,
  skoro przyciski mówią same za siebie). Wersja PL i EN.
- Testy: debug19 ma 5 checków — w tym FAZA 5 na PRAWDZIWYM dialogu
  (klik w "Zamknij i nic nie zapisuj" przez invoke — program zamyka się,
  katalog taba nie powstaje). Cała flota 262/262.
- Wersja 3.70 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.69 "Zamknij bez zapisywania" (zgłoszenie usera):
- PYTANIE O NIEZAPISANE ZMIANY PRZY ZAMYKANIU MA TERAZ TRZY PRZYCISKI:
    [Tak = zapisz i zamknij]  [Nie = zamknij BEZ zapisywania]  [Anuluj = zostań]
  Dotąd było tylko "zapisz i zamknij" albo "zostań" — zamknięcie
  programu bez zapisu wymagało zabicia procesu.
- "Nie" zamyka program, nie dotykając NICZEGO na dysku (również geometria
  okna zostaje jak w ostatnim zapisie). "Anuluj" = zostań w programie.
- Testy: debug19 przepisany na 4 checki (Anuluj = program żyje / Nie =
  zamknięty bez śladu / Tak = zapisany i zamknięty / czyste zamknięcie =
  zero pytań), cała flota 261/261.
- Wersja 3.69 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.68 "Zmiana języka pyta o niezapisane" (znalazł kozak-AI, potwierdził kod):
- PRZEŁĄCZANIE JĘZYKA PL/EN PRZED ZMIANĄ PYTA o niezapisane zmiany — dotąd
  niedokończony tab (bez kliknięcia 'Zapisz tab') znikał BEZ PYTANIA.
  Teraz: [Tak = przełącz i wczytaj mapy z dysku] / [Nie = zostań, nic nie tracisz].
  Zgodne z resztą programu: zamykanie okna też pyta (od 3.62).
- ŹRÓDŁO: analiza CAŁOŚCIOWA kodu przez AI (Gemini 3.6 Flash, Google AI Studio,
  cały program jednym strzałem, 0 zł) — wykrył niespójność, którą potwierdził
  nasz własny komentarz 3.61 w toggle_lang. Człowiek-AI weryfikował w źródle.
- Testy: debug18 rozszerzony do 9 checków (guard pyta przy obu przełączeniach;
  NIE = jezyk i taby nietknięte; TAK = przełącza), cała flota 260/260.
- Wersja 3.68 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.67 "Ogonki na miejscu" (redakcja językowa po ekspertyzie AI):
- CAŁA POLSKA WARSTWA TEKSTÓW (213 komunikatów interfejsu) poszła pod lupę
  zewnętrznego modelu językowego (Qwen 3.6 35B przez API ARK Labs), a każda
  propozycja przeszła drugą weryfikację zasadami: sens, długość, placeholdery
  ({name}, %d), terminologia techniczna (CurseForge, RCON, nazwy plików).
- Z 92 propozycji przyjęto 3 (reszta odrzucona - np. "usuwanie" spacji, do
  których program dokleja wartości, albo wyjęcie uśmiechu z easter egga):
    "(brak sciezki do logu)"  ->  "(brak ścieżki do logu)"
    "Laduje mody - serwer laduje mody"  ->  "Ładuje mody - serwer ładuje mody"
    "RCON błąd"  ->  "Błąd RCON" (poprawny szyk; we wszystkich 3 komunikatach)
- Zero zmian logiki programu; teksty angielskie bez zmian.
- Weryfikacja: jednostkowe 37/37, gruby test admina 32/32, cała flota 256/256.
- Wersja 3.67 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.66 "Nazwa mapy także w sekretu" (KOREKTA USERA - to pominąłem):
- PLIK SEKRETU RCON MAPY DOSTAŁ NAZWĘ MAPY (równość z CONFIG_MAP):
    CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON <mapa> - zapis ....json
  Oba pliki mapy (konfiguracja i sekret) mówią teraz SAMA, czyjej mapy są.
- Automigracja z 3.64/3.65 (plik bez nazwy zostaje przemianowany), zmiana
  nazwy taba przemianowuje i konfigurację, i sekret; import taba z backupu
  czyta obie konwencje (z nazwą i bez).
- Weryfikacja: debug20 5/5, debug21 6/6 (sekret z nazwą + rename), gruby
  test admina 32/32, cała flota 256/256.
- Wersja 3.66 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.65 "Stary dziennik też schodzi" (dokładka do czystego roota):
- FIX znaleziony WERYFIKACJĄ PRZYKŁADÓW USERA (demo 1:1 z jego folderu):
  nowy asa_debug.log od 3.64 zapisywał się w WIEDZA_O_PROGRAMIE/, ale
  STARY asa_debug.log zostawał w katalogu głównym. Teraz przy starcie
  stary dziennik jest doklejany do WIEDZA_O_PROGRAMIE/asa_debug.log
  i znika z roota - w katalogu głównym zostaje DOSŁOWNIE tylko program
  (.py) i starter (.bat).
- Weryfikacja: debug21 6/6 (dodany check 2b: marker starego logu
  zachowany w WIEDZY), gruby test admina 32/32, cała flota 256/256.
- Wersja 3.65 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.64 "Czysty katalog główny" (kosmetyka struktury, cd. zgłoszenia usera):
- W KATALOGU GŁÓWNYM ZOSTAJE TYLKO PROGRAM (.py) I STARTER (.bat).
  Wszystko inne schodzi do własnych podkatalogów (automigracja przy
  pierwszym uruchomieniu - daty i backupy zostają):
    CONFIG_PROGRAM/CONFIG_PROGRAM - zapis ....json          (ustawienia)
    CONFIG_SECRET_API/CONFIG_SECRET_API - zapis ....json    (klucz API)
    CONFIG_MAPS_TABS/<mapa>/CONFIG_MAP <mapa> - zapis ....json
    CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON - zapis ....json
    WIEDZA_O_PROGRAMIE/  (README, MANUAL, MAPA, PROMPT, raporty testów,
                          asa_debug.log - cała wiedza o programie w jednym miejscu)
- NAZWA MAPY W NAZWIE PLIKU KONFIGURACJI: backup wyjęty z katalogu sam
  mówi, czyjej mapy jest ("CONFIG_MAP Genesis 1 - zapis ....json").
  Zmiana nazwy taba w programie przemianowuje też jego pliki.
- SEKRET RCON MAPY we własnym podkatalogu CONFIG_SECRET_RCON/ (poza
  plikami konfiguracji mapy).
- Import taba z backupu podciąga hasło z podkatalogu sekretu, a ze
  starszych backupów (plik luźno obok) - jak wcześniej.
- Weryfikacja: nowy test debug21 5/5 (czysty root, WIEDZA, rename),
  debug20 5/5 (migracja przed-3.63 -> 3.64), gruby test admina 32/32,
  cała flota 255/255.
- Wersja 3.64 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.63 "Konwencja CONFIG_*" (kosmetyka struktury katalogowej, zgłoszenie usera):
- NOWE NAZWY PLIKÓW KONFIGURACJI (czytelne na pierwszy rzut oka):
    konfiguracja programu - zapis ....json   ->   CONFIG_PROGRAM - zapis ....json
    sekrety programu (klucz API) - zapis ...  ->   CONFIG_SECRET_API - zapis ....json
    taby/<mapa>/konfiguracja mapy - zapis ..  ->   CONFIG_MAPS_TABS/<mapa>/CONFIG_MAP - zapis ....json
    taby/<mapa>/sekret mapy (hasło RCON) ...  ->   CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON - zapis ....json
- AUTOMATYCZNA MIGRACJA: przy pierwszym uruchomieniu 3.63 program SAM
  zmienia stare nazwy na nowe (zachowując daty i historię backupów) -
  nic nie ginie, folder od razu wygląda wg nowej konwencji.
- PLIKI NADAL OBOK PROGRAMU: to świadoma zasada projektu (przenośność -
  kopiujesz folder i masz wszystko; nic nie ląduje w AppData).
- Rotacja 10 backupów, zapis atomowy, najnowszy plik wygrywa - bez
  zmian. Weryfikacja: nowy test debug20 5/5 (migracja+odczyt+zapis),
  gruby test admina 32/32, cała flota 250/250.
- Wersja 3.63 w nazwie okna (app_title PL/EN), o programie, User-Agent.

ZMIANY W 3.62 "„Nie" znaczy NIE" (FIX zamknięcia programu, zgłoszenie usera):
- FIX: nowa mapa bez "Zapisz tab" -> zamknięcie programu -> pytanie ->
  "Nie" ... i program i tak się ZAMYKAŁ i ZAPISYWAŁ mapę. Odpowiedź
  "Nie" była kompletnie ignorowana (kod po pytaniu leciał dalej:
  zapis wszystkiego + zamknięcie). Teraz działa dokładnie tak, jak
  czyta to człowiek:
    [Tak]    = zapisz zmiany i zamknij program
    [Nie]    = ZOSTAŃ w programie, nic nie zapisuj
  Nowa treść pytania mówi to wprost (PL/EN).
- FIX (wykopany przy okazji, fałszywy alarm): przy KAŻDYM starcie
  programu flaga "niezapisane zmiany" była zapalona przez samą
  procedurę ładowania map - pytanie o zapis strzelało przy każdym
  zamknięciu, nawet gdy nic nie zmieniono. Teraz: czyste zamknięcie
  = zero pytań.
- Weryfikacja: nowy test debug19 3/3 ("Nie" zostaje, "Tak" zapisuje
  i zamyka, czyste zamknięcie bez pytania), gruby test admina 32/32,
  cała flota 245/245.
- Wersja 3.62 w nazwie okna (app_title PL/EN), "o programie", User-Agent.

ZMIANY W 3.61 "Język nie zabija okna modów" (FIX zgłoszenia usera):
- FIX: okno modów otwarte + zmiana języka (EN/PL) = okno "martwe" do
  restartu programu. Przyczyna X2: przebudowa UI niszczyła okno modów,
  a _last_mod_ids trzymało starą listę modów, więc panel "odświeżał"
  kafelki, których już nie było (pusty ekran). Teraz: kafelki budują
  się od zera, a okno modów WRACA OD RAZU - już w nowym języku.
- FIX (znaleziony przy okazji, głębszy): po zmianie języka świeżo
  dodane (niezapisane) taby ZNIKAŁY, a niezapisane edycje wracały do
  stanu z ostatniego zapisu. Teraz przebudowa czyta stan z dysku
  (zapis następuje automatycznie przed przełączeniem) - jak przy
  starcie programu.
- Weryfikacja: nowy test debug18 5/5 (PL -> EN -> PL, zamykanie i
  otwieranie okna), gruby test admina 32/32, cała flota 242/242.
- Wersja 3.61 w nazwie okna (app_title PL/EN), "o programie", User-Agent.

ZMIANY W 3.60 "Kafelki statusów map" (strefa Status czytelna dla każdego):
- KAFELKI ZAMIAŚĆ GOŁYCH KROPEK: strefa Status ma teraz DWIE linie - góra
  bez zmian (Monitoruje + zegar + przyciski), a POD NIĄ osobna linia
  kafelków: kropka + NAZWA MAPY + STATUS SŁOWAMI, np. "Genesis 1 · GOTOWY",
  "Ragnarok · CRASH". Użytkownik nie musi znać znaczenia kolorów - status
  jest napisany (kolor tekstu = kolor kropki, dla szybkości oka).
- DYMKI TŁUMACZĄCE: najechanie na kafelek pokazuje wyjaśnienie, np.
  "GOTOWY - serwer działa, gracze mogą wchodzić", "CRASH - mapa padła;
  program pilnuje, aż wróci" (PL/EN).
- ZAWIJANIE: przy wielu mapach kafelki przechodzą do kolejnych linii
  (ten sam mechanizm co diody modów w tabach, od 3.44).
- ZERO ZMIAN DZIAŁANIA: te same statusy z logów serwera, te same kolory,
  ta sama logika - to wyłącznie poprawa czytelności (zgłoszenie usera).
- Wersja 3.60 w nazwie okna (app_title PL/EN), "o programie" i User-Agent.

ZMIANY W 3.59 "Diody od razu + zegar w sekundach" (kosmetyka wg zgłoszenia usera):
- DIODY ZAPALONE OD RAZU: do pierwszego sprawdzenia CurseForge diody modów
  w tabach są NIEBIESKIE (#3d6db5) z podpisem "nie sprawdzono"
  (EN: "not checked yet"), a nie szare/wygaszone. Admin widzi od pierwszej
  sekundy, że program żyje i czeka na 1. check. Potwierdzone w grubym
  teście admina (32/32) I na żywym serwerze usera z prawdziwym kluczem API.
- ZEGAR W SEKUNDACH: pasek statusu pokazuje "Monitoruje · Następne
  sprawdzenie: 299 s" (format %d s, malejąco do zera) zamiast "4:59" -
  liczba sekund czytelniejsza dla admina siedzącego daleko od ekranu.
- Wersja 3.59 w nazwie okna (app_title PL/EN), "o programie" i User-Agent.

ZMIANY W 3.58 "Pary w logu" (parser listy modów):
- FIX ZGŁOSZENIA USERA (log 12:42): po imporcie backupu lista znów miała
  18 pozycji przy 9 modach. Przyczyna: realny serwer ASA wypisuje w
  linii LoadGameMods PARY "mod (wersja)" rozdzielone przecinkami, np.
  "...: 940975, 928548 (7005633), 929684 (8510257)". Poprzednia reguła
  (3.54) mówiła "lista z przecinkami = bierz wszystkie liczby" - więc
  brała obie liczby z każdej pary (9 modów + 9 wersji = 18 "modów").
- NOWA REGUŁA (prostsza i odporna na wszystkie formaty naraz): z każdego
  fragmentu po przecinku bierzemy PIERWSZĄ liczbę - to zawsze mod ID.
  Działa dla: par z nawiasami "mod (wersja)", par z podkreślnikiem
  "mod_plik", płaskich list "a,b,c", pojedynczych linii z wersją.
- HISTORIA WERSJI NA GITHUB: katalog wersje/ w repo przechowuje co
  najmniej 4 ostatnie wersje KAŻDEGO pliku (rotacja przy wydaniu);
  do tego każde Wydanie (Release) z zipem zostaje na GitHubie na
  zawsze - starszych wydań (3.54-3.56) nie da się wskrzesić, bo stare
  zipy kasowaliśmy; od tej wersji nic nie ginie.
- Testy: debug15 7/7 (dokładna linia z logu usera), dotknięte pakiety
  debug8 11/11, debug12 7/7, debug14 12/12, jednostkowe 37/37; pełny
  tescior przed wydaniem.

ZMIANY W 3.57 "Zaczyt starych bakapów" (+ mapa programu i porządki):
- FIX ZGŁOSZENIA USERA: import taba z backupu z BARDZO STAREJ wersji
  programu (do ok. 3.43) kończył się odrzuceniem pliku. Powód: tamte
  wersje zapisywały JEDEN GLOBALNY plik konfiguracji ze słownikiem
  "servers" {nazwa_mapy: ustawienia} i GLOBALNĄ listą modów - dzisiejszy
  importer oczekiwał formatu pojedynczego taba. TERAZ: program rozpoznaje
  stary zapis globalny, ROZBIJA go na taby (po jednej na mapę), przypisuje
  każdej mapie tamtejszą globalną listę modów (Twoje 9 modów trafia do
  każdej mapy), włącza linie (stare nie miały flagi on/off) i podciąga
  hasła RCON ze starego pliku sekretów ("passwords": {nazwa: haslo}),
  jeśli leży obok. Normalizuje też stare pojedyncze taby (lista modów
  jako tablica, linie jako pary, brak nazwy -> nazwa z katalogu).
- MAPA PROGRAMU: nowy dokument "MAPA-PROGRAMU.md" w kompleciku - cały
  program rozłożony na warstwy (narzędzia -> pliki -> źródła zewnętrzne ->
  tab -> logika -> UI), przepływy krok po kroku (start, zegar, cykl
  CurseForge, restart mapy, czuwanie, import), kto kogo woła, co ląduje
  na dysku i lista nietykalnych filarów. KOMPLECIK ROŚNIE DO 8 PLIKÓW.
- PORZĄDKI PO MAPIE (audyt kodu): usunięto 62 martwe klucze tłumaczeń
  (sieroty po usuniętych funkcjach: okno logów z 3.41, kafelki 3.38,
  stary zapis z potwierdzeniem itd.) i 3 nieużywane stałe API. Zero
  zmian zachowania - pełna flota testów zielona po sprzątaniu.
- TESTY: nowy "tescior" (symulacja/tescior.py) - JEDEN NACISK = cała
  flota (jednostkowe + debugi 5-14 + sterownik) z tabelą wyników;
  przywrócono do życia debug5 (wisiał od 3.47: nie łatał dialogu
  kolizji) i debug9 (aktualizacja do semantyki 3.52). Wynik wydania:
  185/185 (12 pakietów testowych, wszystko zielone).

ZMIANY W 3.56 "Generator CF-API" (przycisk w sekcji API):
- NOWY PRZYCISK "Generator CF-API" w rzędzie klucza API (między
  "Załaduj API z backupu" a "Zapisz klucz"): otwiera w przeglądarce
  stronę generowania klucza CurseForge PROSTO pod właściwym adresem
  (https://console.curseforge.com/?#/api-keys). Koniec przepisywania
  adresów z podpowiedzi - jeden klik i jesteś na miejscu.
- Podpowiedź (tooltip) przycisku mówi co robi i gdzie wkleić klucz.
- Adres trzymany w jednej stałej (CF_API_KEYS_URL) - używają go
  przycisk, podpowiedzi i szybki start.
- Testy: debug13 5/5, symulacja 62/62, jednostkowe 37/37.

ZMIANY W 3.55 "Prosty link do kluczy" (deep link do strony API):
- FIX: wszędzie (podpowiedź pola klucza, szybki start w konsoli, MANUAL)
  wskazujemy teraz PEŁNY adres strony kluczy:
  https://console.curseforge.com/?#/api-keys
  Wcześniej (od 3.53) był sam domenowy adres console.curseforge.com -
  po zalogowaniu user lądował na pulpicie "CurseForge for Studios"
  i musiał sam szukać strony kluczy (zgłoszenie usera: w pierwotnej
  wersji programu link prowadził prosto do celu).
- Testy: jednostkowe 37/37, debug11 11/11, symulacja 62/62.

ZMIANY W 3.54 "Prawdziwy serwer" (folder modów i wersje w logu):
- ANALIZA LOGA UŻYTKOWNIKA: dwa serwery po 9 modów, a program krzyczał
  "Nie znaleziono folderu Mods\83374 przy żadnej mapie", i lista z logu
  miała 18 pozycji przy 9 katalogach. Dwie przyczyny, obie naprawione.
- FIX 1 - GDZIE SERWER NAPRAWDĘ TRZYMA MODY: prawdziwe serwery ASA
  mają je w ShooterGame\Binaries\Win64\ShooterGame\Mods\83374
  (potwierdzone poradnikami Steam i listingami administratorów), a
  program szukał w ShooterGame\Mods\83374 i ewentualnie w Content\Mods.
  Teraz sprawdza 4 lokalizacje po kolei: Binaries\Win64\ShooterGame\Mods
  (realny ASA), ShooterGame\Mods (uproszczony), ShooterGame\Content\Mods
  (styl ASE), Content\Mods obok (wariant B). Przy braku - ostrzeżenie
  WYPISUJE szukane ścieżki ("Szukałem w: ..."), więc od razu widać,
  czego program nie widzi.
- FIX 2 - FOLDERY <ModID>_<FileID>: realny serwer nazywa foldery modów
  np. 983782_5274661 (para identyfikatorów), a program rozpoznawał tylko
  gołe cyfry. Teraz czyta oba formaty (<ModID>_<FileID> oraz <ModID>),
  a numer pliku bierze z nazwy folderu albo z pliku .mod w środku.
- FIX 3 - WERSJE W LOGU NIE SĄ MODAMI: linie typu "Loading mod: X
  (version Y)" dawały DWA numery - mod ID i numer wersji. Przy 9 modach
  powstawała lista 18 "modów" (9 ID + 9 wersji). Teraz: z linii pojedynczego
  moda brany jest tylko PIERWSZY numer; listy "LoadGameMods: a,b,c"
  (przecinki) czytane w całości.
- KOMUNIKATY: rozdzielono "folderu nie ma (szukałem tu i tu)" od "folder
  jest, ale nie rozpoznano w nim modów".
- Symulator fakesrv przestawiony na prawdziwy layout serwera (Binaries/
  Win64/ShooterGame/Mods/83374).
- Testy: debug12 7/7 (reprodukcja przypadku użytkownika 1:1), symulacja
  62/62, jednostkowe 37/37, debug7 8/8 (stary layout nadal działa),
  debug8 11/11.

ZMIANY W 3.53 "Intro w konsoli" (pierwsze uruchomienie bez okienek):
- OKIENKO ZNIKA: przy pierwszym uruchomieniu program NIE pokazuje już
  okienka wymagającego "OK" (zgłoszenie usera). Zamiast tego w KONSOLI
  pojawia się rozbudowany SZYBKI START: 5 kroków od zera do działającego
  monitoringu (klucz API -> tab mapy -> log serwera -> "Mody z serwera"
  -> zapis), ze wskazówką o Windows ("Zezwól") i odesłaniem do README
  i MANUAL. Linie krótkie - mieści się i czyta wygodnie.
- NOWY PRZYCISK "Załaduj API z backupu" (obok pola klucza): wskazujesz
  stary plik sekretów ("sekrety programu (klucz API) - zapis ....json")
  i klucz API wraca do pola - np. po przeprowadzce na nowy komputer
  albo przy wracaniu z backupu. Błędny plik = czytelny komunikat.
- FIX LINKI DO STRON MODÓW: gdy program zna adres moda z API - otwiera
  go 1:1. Gdy nie zna (sprawdzenie CF jeszcze nie ruszyło), link prowadził
  DONIKĄD (cyfrowe ID wstawione w ścieżkę, której CurseForge nie
  rozumie - zgłoszenie usera, w 3.21 działało). Teraz: wyszukiwarka
  CurseForge z numerem moda - zawsze coś znajdzie.
- NOWY MANUAL "dla opornych": MANUAL - ASAonly - ... .md - program
  rozbity na czynniki pierwsze (11 mechanizmów), 5 filarów, 3 przykłady
  krok po kroku, słownik, rozwiązywanie problemów + sekcja dla AI
  (plik działa też jako kontekst dla asystenta). KOMPLECIK ROŚNIE do
  7 plików.
- Dokumenty: przeprosiny za "kwiatki" w tłumaczeniu (na końcu README)
  i wskazówka o okienku Windows "nieautoryzowany dostęp do folderu"
  (Kontrolowany dostęp do folderów - kliknąć Zezwól; najlepiej trzymać
  program w zwykłym folderze, nie w Dokumentach).
- Testy: debug11 11/11 (intro w konsoli, 0 okienek; API z backupu;
  linki), symulacja 62/62, jednostkowe 37/37.

ZMIANY W 3.52 "Zegar i hierarchia" (klucz API tylko gdy jest co sprawdzać):
- PROBLEM (zgłoszenie usera): świeżo uruchomiony program BEZ żadnego taba
  i BEZ żadnego moda uporczywie żądał podania klucza API. Absurd: nie było
  czego sprawdzać, a program rościł sobie prawo do klucza.
- PRZYCZYNA: check_now() sprawdzał klucz API jako PIERWSZY, dopiero potem
  zbierał listę modów. Kolejność odwrócona: najpierw "czy jest CO
  sprawdzać", potem "czy jest czym sprawdzać".
- TERAZ: brak tabów / brak modów = temat klucza API w ogóle nie wynika
  (automat milczy). Ręczny przycisk "Sprawdź mody teraz" bez modów
  odpowiada: "Brak modów do sprawdzenia (...)" - reakcja na akcję.
  Ostrzeżenie o kluczu pojawia się tylko wtedy, gdy jakieś mody są.
- ZEGAR WIDOCZNY: pasek statusu pokazuje teraz odliczanie do następnego
  automatycznego sprawdzenia ("Monitoruje · Następne sprawdzenie: 4:59").
  Napis "Następne sprawdzenie:" istniał w tłumaczeniach od dawna, ale NIC
  go nie wyświetlało (sierota) - widać było tylko statyczne "Monitoruje".
  Licznik znika, gdy nie ma modów (nie ma czego odliczać).
- Wewnętrzny zegar programu (pętla _tick co 500 ms) został bez zmian:
  drukuje dziennik, odświeża diody tabów, pilnuje restartów, czuwania
  i harmonogramu automatycznego sprawdzania modów.
- Testy: debug10 7/7, symulacja 62/62, jednostkowe 37/37.

ZMIANY W 3.51 "Cisza w konsoli" (spam hasłem o braku klucza API):
- PROBLEM: świeżo uruchomiony program BEZ klucza API CurseForge zasypywał
  konsolę wpisem "Brak klucza API CurseForge." ok. 2 razy na sekundę.
  Przyczyna: auto-sprawdzenie co interwał jest pilnowane przez tik co
  500 ms, a gałąź "brak klucza" wychodziła WCZEŚNIEJ niż harmonogram
  następnego sprawdzenia — więc następny tik strzelał znowu (i tak w
  kółko; poprawka "przesuwaj zawsze" z 3.41 nie obejmowała tego returnu).
- FIX: brak klucza = JEDNO ostrzeżenie na start (jednorazowa flaga),
  a następne automatyczne sprawdzenie jest odroczone o pełny interwał.
- Ręczny przycisk "Sprawdź mody teraz" bez klucza odpowiada ZAWSZE
  (każde kliknięcie = jedna odpowiedź — reakcja na akcję, nie spam).
- Po wpisaniu klucza flaga się resetuje (jeśli klucz zniknie później,
  znów pojawi się pojedyncze ostrzeżenie).
- Testy: debug9 5/5 (licznik wpisów w czasie), symulacja 62/62,
  jednostkowe 37/37.

ZMIANY W 3.50 "Import pod lupą" (zła lista modów w backupie taba):
- PROBLEM: import taba z backupu mógł wciśnąć listę modów, która nie ma
  nic wspólnego z tym, co serwer naprawdę ładuje (stary backup, inny
  serwer). Skutek: monitoring "duchów" i restarty mapy po update moda,
  którego serwer w ogóle nie używa.
- PRZYPADEK 1 - SERWER JUŻ DZIAŁA: import od razu weryfikuje listę
  względem LOGU serwera. Rozbieżność = pole dostaje to, co serwer ŁADUJE
  (+ wpis w dzienniku); zgodność = wpis "zgodna z logiem".
- PRZYPADEK 2 - SERWER DOPIERO BĘDZIE URUCHAMIANY: log milczy, więc
  lista z backupu zostaje, ale tab dostaje flagę "NIEzweryfikowana"
  (wpis w dzienniku; flaga jest trwała - przeżywa restart programu).
  Gdy serwer wystartuje i log pokaże ładowanie modów, program SAM
  weryfikuje i koryguje listę ("Serwer wystartował: lista modów
  skorygowana wg logu"). Dzieje się to już przy statusie "Ładuje mody".
- Bezpiecznik: korekta tylko raz (jednorazowa flaga); ręcznie wpisana
  lista nie jest nadpisywana.
- Testy: debug8 11/11 (oba przypadki + zgodność + trwałość flagi),
  symulacja 62/62, jednostkowe 37/37.

ZMIANY W 3.49 "Mody z serwera = to, co serwer ładuje" (bajzel w katalogu):
- PROBLEM: użytkownicy często trzymają w katalogu Mods/83374 śmieci po
  testach modów (np. 20 folderów, a serwer startuje z 10 modów). Dotąd
  "Mody z serwera" brało WSZYSTKIE foldery - czyli bajzel trafił do listy,
  CurseForge odpytywał o nieużywane mody, a update NIEUŻYWANEGO moda
  mógł odpalić procedurę restartu mapy, która go w ogóle nie ładuje!
- ROZWIĄZANIE: "Mody z serwera" czyta teraz NAJPIERW LOG SERWERA
  (linia LoadGameMods i kolejne wpisy o ładowaniu modów) i do pola wpisuje
  TYLKO to, co serwer naprawdę ładuje. Rozbieżności są jasno logowane:
  * "Serwer ŁADUJE X modów (lista z logu): ..." - to poszło do pola,
  * "Pominięto N modów z katalogu (serwer ich NIE ładuje - zostały
    z testów): ..." - wykryty bajzel,
  * "Mod z logu bez folderu w katalogu" - rzadki przypadek, też widoczny.
- FALLBACK: gdy log nie zawiera listy ładowanych modów (stary format,
  brak logu), wpisywane są wszystkie mody z folderów - z wyraźnym
  ostrzeżeniem w dzienniku, żeby posprzątać katalog albo sprawdzić log.
- Efekt: aktualizacja moda nieużywanego przez serwer NIE.restartuje mapy;
  zapytania do CurseForge obejmują tylko realnie używane mody.
- Testy: debug7 8/8 (scenariusz 20 folderów / 10 ładowanych + fallback
  + mod bez folderu), symulacja 62/62 (ścieżka z logu), jednostkowe 37/37.

ZMIANY W 3.48 "Nowa nazwa programu" (nowy standard nazewnictwa plików):
- OFICJALNA NAZWA PROGRAMU: ASAonly - (AUTO)Manual - ModRefresher (RCON).
  "(AUTO)Manual" oddaje dualizm: automat RCON działa sam, ale wszystko
  da się robić ręcznie; "(RCON)" mówi, JAK program rozmawia z serwerami.
- STANDARD NAZW PLIKÓW WYDAWNICZYCH:
  * program:    "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
  * launcher:   "STARTER plus Python installer - ASAonly - (AUTO)Manual -
                 ModRefresher (RCON).bat"
  * dokumentacja: "README - ASAonly - (AUTO)Manual - ModRefresher (RCON).txt"
  * manual:      "MANUAL - ASAonly - (AUTO)Manual - ModRefresher (RCON).md"
  * mapa:        "MAPA-PROGRAMU.md" (od 3.57; od 3.74 komplecik = 9 plików)
  * na GitHub:   katalog wersje/ = min. 4 ostatnie wersje każdego pliku
                 (od 3.58) + Wydania (Release) z zipem każdej wersji
  * komplecik:  "V<x> ASAonly - (AUTO)Manual - ModRefresher (RCON).zip"
    (numer wersji ZAWSZE w nazwie zipa i NA POCZĄTKU - korekta usera
    2026-08-29: wersja przeniesiona na początek, widać ją od razu i
    sortuje się po wersjach; przy wydaniu nowej wersji stary zip kasujemy)
- Nazwa w tytule okna (PL i EN), w oknie "O programie" i w User-Agent
  zapytań do CurseForge. Wewnętrzne pliki konfiguracji/sekretnów bez
  zmian (czytelne nazwy z datą zapisu, patrz 3.45).

ZMIANY W 3.47 "Świadomy import" (matryca konfliktów przy imporcie taba):
- Import rozróżnia teraz, GDZIE leży wskazany backup:
  * BACKUP W INNYM MIEJSCU (kopia z pendrive, inna instalacja) ->
    klasyczny import: nowy tab, nowy katalog taby/<mapa>/ (jak w 3.46),
  * BACKUP W MIEJSCU STANDARDOWYM (taby/<mapa>/), ale taba nie ma w
    programie (katalog wgrany/pojawił się PO starcie) -> import działa
    jak PRZYWRÓCENIE bez restartu programu; zapis jest identyczny z
    istniejącym, więc ZERO nowych plików w historii (deduplikacja),
    historia wersji zostaje nienaruszona,
  * TAB O TEJ NAZWIE JUŻ DZIAŁA -> program PYTA (TAK/NIE): backupy w
    jego katalogu to i tak jego własna rotacja, więc import ma sens
    tylko jako świadomy duplikat. "NIE" = koniec, nic nie ruszone.
    "TAK" = duplikat z sufiksem " (2)", zapisywany do WŁASNEGO katalogu
    (historia oryginału pozostaje oddzielna i nietknięta).
- Przypomnienie: taby w standardowym miejscu (taby/<mapa>/) program
  ładuje AUTOMATYCZNIE przy starcie - do tego przypadku przycisk importu
  nie jest potrzebny; służy sytuacjom powyżej.
- Testy: debug6 9/9 (matryca konfliktów), symulacja 62/62, jednostkowe 37/37.

ZMIANY W 3.46 "Tab z backupu" (nowa zdolność - import taba z pliku):
- NOWY PRZYCISK "+ TAB Z BACKUPU" na pasku głównym (obok "+ Dodaj mapę"):
  wskazujesz plik backupu konfiguracji mapy (np. z rotacji w taby/<mapa>/
  albo z kopii całego katalogu z innej instalacji) - program tworzy
  NOWY tab z całą zawartością: RCON (host/port), ścieżka logu, mody mapy,
  harmonogram linii, pole admina.
- HASŁO RCON PODĄGA Z BACKUPEM: jeśli obok wybranego pliku leży plik
  "sekret mapy (hasło RCON) - zapis ....json" (np. przy kopiu całego
  katalogu taba), hasło wsiada do taba automatycznie; w najstarszych
  backupach (sprzed 3.43) hasło ciągnie się z samego pliku konfiguracji.
- KOLIZJE NAZW ROZWIĄZYWANE SAMY: jeśli tab o tej nazwie już działa,
  import dostaje sufiks " (2)", " (3)" itd. (informacja w dzienniku).
- BEZPIECZNICTWO: plik jest sprawdzany - konfiguracja programu lub śmieci
  zostają odrzucone z jasnym komunikatem (szukamy pliku "konfiguracja
  mapy - zapis ....json"). Import od razu zapisuje taba na dysk (z własnym
  sekretem), więc po restarcie programu tab jest na miejscu.
- Typowy scenariusz: działa 3 taby, masz backupy 10 innych serwerów -
  klikasz import 7 razy i masz cały park w jednym oknie.

ZMIANY W 3.45 "Czytelne pliki" (nowe nazwy konfigów i sekretów):
- NOWA KONWENCJA NAZW: każdy plik konfiguracji i sekretu ma w nazwie
  CO TO ZA PLIK oraz DATĘ I GODZINĘ ZAPISU (dokładnie do sekundy).
  Przedrostek "asa" usunięty. Przykład:
  "konfiguracja programu - zapis 29.08.2026 14-05-53.json"
  (godzina z myślnikami: dwukropek jest niedozwolony w nazwach na Windows).
- ZMIENIONE NAZWY:
  * asa_config.json            -> "konfiguracja programu - zapis <data>.json"
  * asa_secrets.json           -> "sekrety programu (klucz API) - zapis <data>.json"
  * asa_tabs/<mapa>/           -> taby/<mapa>/
  * taby/<mapa>/config.json    -> "konfiguracja mapy - zapis <data>.json"
  * taby/<mapa>/secrets.json   -> "sekret mapy (hasło RCON) - zapis <data>.json"
- KAŻDY ZAPIS = NOWY PLIK z datą i godziną (tylko gdy treść się naprawdę
  zmieniła); program czyta zawsze NAJNOWSZY. Rotacja trzyma 10 najnowszych
  wersji - to jednocześnie SYSTEM BACKUPÓW (osobne foldery backups już
  nie są potrzebne). Zerkasz w katalog i od razu widać, co to i kiedy.
- AUTOMATYCZNA MIGRACJA starych nazw przy pierwszym uruchomieniu
  (asa_config.json, asa_tabs/ itd. zmieniają nazwę same; znacznik czasu
  brany z daty modyfikacji starego pliku, nic nie ginie).
- NAPRAWIONE przy okazii (bug od 3.43, ujawniony przez migracje): przy
  jednorazowym przenoszeniu haseł do plików sekretów tab był po cichy
  pomijany (wyjątek w init połykany przez except). Język i bufor loga
  inicjalizowane teraz PRZED wczytywaniem tabów.
- asa_debug.log (czarna skrzynka) - bez zmian, to nie konfig ani sekret.

ZMIANY W 3.44 "Okno na miejscu, diody w linie":
- NAPRAWIONE "mrugnięcie i zniknięcie" okna modów: jeśli w configie zapisana
  była pozycja spoza ekranu (np. -1 z ukrytego okna albo współrzędne
  drugiego monitora), okno pojawiało się na moment w domyślnym miejscu
  i "ucieka" poza ekran. Teraz: pozycja przy wracaniu jest SPRAWDZANA -
  śmieciowa/niewidoczna = okno centruje się nad głównym oknem; pozycje
  z ukrytych okien nie są już w ogóle zapisywane.
- Dziennik konsoli pokazuje przy otwarciu, GDZIE okno wylądowało
  ("Okno modów widoczne: 420x900+X+Y") - gdyby kiedyś znowu uciekało,
  wspólrzędne widać od razu.
- DIODY MODÓW ZAWIJAJĄ SIĘ DO LINII: sekcja "Mody mapy" ma teraz dwa
  pełne wiersze - wpis z przyciskiem "Mody z serwera", a pod nim diody.
  Diody układają się od lewej i SAME przechodzą do kolejnej linii,
  gdy się nie mieszczą; rozciąganie/kurczenie okna przelicza układ.
  (Dotąd diody lądowały w ciasnej smudze OBOK pola wpisów - pack
  side=left zabierał cały pasek; to był źródło "spaprania".)

ZMIANY W 3.43 "Sekrety tabów" (zapis per tab + system backupów):
- HASŁO RCON WYNOŚONE Z CONFIG.JSON: dotąd hasło leżało JAWNYM TEKSTEM
  w config.json taba (i w jego backupach!). Teraz żyje w osobnym,
  prywatnym pliku asa_tabs/<nazwa>/secrets.json.
- NOWY PRZYCISK "ZAPISZ SEKRET" w każdym tabie (obok "Zapisz konfig"):
  zapisuje TYLKO hasło RCON tego taba do jego pliku sekretów.
  "Zapisz konfig" dalej zapisuje TYLKO konfigurację taba (harmonogram,
  RCON host/port, ścieżkę logu, mody mapy) — tak jak dotychczas.
- JEDNORAZOWA MIGRACJA: przy pierwszym uruchomieniu 3.43 hasło znajdzie
  się automatycznie w nowym pliku (wpis w dzienniku), a z config.json
  zniknie przy najbliższym zapisie.
- "ZAPISZ CONFIG" (globalny) zapisuje teraz oprócz konfiguracji także
  sekrety wszystkich tabów — stary nawyk "jeden zapis = wszystko zapisane"
  dalej działa.
- SYSTEM BACKUPÓW (rotacyjnych, po 10 sztuk):
  * asa_tabs/<nazwa>/backups/config_*.json — konfiguracja taba (istniało),
  * asa_tabs/<nazwa>/backups/secrets_*.json — sekret taba (nowe),
  * asa_backups/asa_config_*.json i asa_secrets_*.json przy programie —
    globalna konfiguracja i klucz API (nowe; backup tylko gdy treść
    się naprawdę zmieniła).
- Pytanie o niezapisane zmiany przy zamykaniu pilnuje teraz także haseł.

ZMIANY W 3.42 "Konsola i diody" (na życzenie usera - rewizja okna logów
i sekcji modów w tabach):
- OKNO DZIENNIKA USUNIĘTE - dziennik zdarzeń żyje w KONSOLI, która i tak
  otwiera się razem z programem (poprzednie okno było starej konstrukcji:
  podwójny napis "Dziennik zdarzeń" na belce i w oknie, po latach łatek).
  * log wypisywany batchem do konsoli, z KOLORAMI (ANSI: czerwone ostrzeżenia,
    zielone "GOTOWY", żółte "ładuje") - na Windows 10+ kolory włąaczają się
    same; czyste teksty zostają w buforze i w asa_debug.log jak dotychczas,
  * klik "DZIENNIK" usunięty z paska głównego (okno modów zostaje),
  * zapis konfigu nie zawiera już log_w/log_open/log_x/log_y,
  * uruchomienie przez pythonw (bez konsoli) jest bezpieczne - dziennik
    trafia wtedy tylko do bufora i asa_debug.log.
- DIODY MODÓW W TABACH PRZEBUDOWANE ("dioda = numer moda"):
  * stary patent (Canvas z kółkiem 36 px) czytał kolor stanu RAZ przy
    tworzeniu - diody wyglądały na martwe; do kosza,
  * teraz: chip z NUMEREM moda na kolorze stanu (zwykły Label, zero
    canvasów) - aktualny=zielony, sprawdzanie=niebieski, UPDATE=pomarańcz,
    ZALEGŁY=czerwony, wyłączony=szary,
  * diody odświeżają się NA ŻYWO przy każdej zmianie stanu, zaległości
    i przełączniku monitorowania (plus siatka bezpieczeństwa co 2 s),
  * dymek nad diodą: nazwa moda, stan, najnowsza wersja; klik otwiera
    stronę moda na CurseForge (jak dotychczas),
  * PROSTOTA etykiety: "Mody mapy (puste = lista globalna)" kłamała -
    żadnej listy globalnej nie ma w kodzie; teraz uczciwie:
    "Mody mapy (ID po przecinku)".
- Symulacja 8 serwerów: 62/62 PASS na 3.42; testy jednostkowe: 37/37.

ZMIANY W 3.41 "Koniec młota na API" (naprawy z grubej symulacji 8 serwerów):
- NAPRAWIONY "CF HAMMER" (najpoważniejszy błąd znaleziony w symulacji):
  gdy sprawdzenie CurseForge COŚ znalazło, licznik "następne sprawdzenie"
  nie był przesuwany - a pętla główna (tick co 0,5 s) odpytywała API przez
  CAŁY czas trwania procedury restartu i zaległości. Dowód z symulacji:
  11 zapytań w 7 sekund przy interwale ustawionym na 30 s; w produkcji
  (interwał 300 s, godzina zaległości) wychodziłyby tysiące zapytań
  i ryzyko limitów API. Teraz "następne sprawdzenie" przesuwa się ZAWSZE,
  także gdy check coś znalazł.
- NAPRAWIONA "pętla uzgodnienia" po ręcznym restarcie admina: gdy admin
  sam zaktualizował moda na dysku i zrestartował mapę, program i tak
  co sprawdzenie widział "ma nową wersję" i trzymał zaległość w kółko
  (zapamiętana wersja nie była podbijana). Teraz: jeśli nowa wersja moda
  JUŻ leży na dysku, program godzi wersje (zapisuje ją, loguje
  "już zainstalowana lokalnie — godzę wersje"), zdejmuje zaległość
  i NIE uruchamia procedury restartu.
- Skan "co faktycznie leży na dysku" wykonywany jest przy sprawdzeniu
  na wątku UI i przekazywany do workera sieciowego - worker dalej nie
  dotyka Tkintera ani dysku (bez nowych ryzyk wątkowych).
- Symulacja (8 serwerów, różne mapy, baza wspólna + mody per mapa, np.
  Better Horde TYLKO dla Extinction - mod eventu hord, na innych mapach
  nic nie robi): 62/62 PRZECHODZI na V3.41, młot na API wyeliminowany
  (0 zapytań CF w trakcie procedury), pętla uzgodnienia zdjęta.
  Testy jednostkowe: 37/37 (bez zmian).

ZMIANY W 3.40 "To tylko okno" (okno modów OD NOWA - definitywnie):
- OKNO MODÓW PRZEBUDOWANE OD ZERA, tym razem NAPRAWDĘ od zera: kafelek
  moda to już nie Canvas z ręcznie rysowanym tekstem i ręcznie liczoną
  geometrią (źródło ucinania kafelków w 3.34-3.39), tylko ZWYKŁE WIDŻETY
  (Label / Checkbutton / Button / dioda) pakowane przez pack(fill="x").
  * ZERO ręcznej arytmetyki pikseli w całym oknie - szerokość kafelka
    zawsze pochodzi od rodzica, więc kafelek NIE MOŻE wystawać poza okno
    (tryb awarii przestał istnieć, zamiast być naprawiony);
  * nazwa moda i linia informacji (ID / Znana / Najnowsza / Mapy) zawijają
    się SAME (wraplength podąża za własnym <Configure> kafelka) - długie
    nazwy przechodzą do drugiej linii zamiast znikać;
  * w jednej linii: dioda statusu, NAZWA (bold), kolorowy TEKST STANU
    (aktualny / UPDATE / ZALEGŁY / błąd CF / wył.), checkbox "Monitoruj"
    i przycisk "Strona" - zwykłe widżety, nie "okna wklejone w canvas";
  * KÓŁKO MYSZY przewija listę modów (dotąd nie działało wcale!) - aktywne
    tylko, gdy kursor jest nad oknem modów, reszta aplikacji nietknięta;
  * suwak pionowy pojawia się, gdy modów nie mieszczy się w oknie;
    wysokość i szerokość okna pamiętane w configu (jak dotychczas),
    minimalny sensowny rozmiar okna: 360x200.
- USUNIĘTA ręczna arytmetyka szerokości okna (_on_mods_win_resize) -
  szerokość panelu i tak jest pamiętana przy zamykaniu okna.
- Filozofia naprawy (wniosek z rozmowy): poprzednie podejścia DOKŁADAŁY
  logiki do zepsutej koncepcji; w 3.40 koncepcję porzucono. To tylko okno.

ZMIANY W 3.39.2 "Geometria w jedną stronę" (naprawa kafelków + stałe):
- NAPRAWIONY BUG UCIĘTYCH KAFELKÓW MODÓW (prawa krawędź ucięta niezależnie
  od suwaka — znany z 3.38/3.39). Przyczyna (diagnoza odzyskana z poprzedniej
  sesji): trzy osobne systemy geometrii — sztywna szerokość kafelka liczona
  ręcznie z szerokości OKNA, paddingi oraz suwak zabierający szerokość
  canvasa bez generowania zdarzenia — rozjeżdżały się o piksele.
  Naprawa: JEDEN kierunek przepływu geometrii: okno -> canvas -> ramka
  (itemconfig width) -> kafelek (pack fill="x") -> przerysowanie z własnego
  <Configure>. Kafelek ma zawsze dokładnie tyle miejsca, ile daje mu
  rodzic — nie może wystawać. Pojawienie/zniknięcie suwaka samo przerysowuje
  listę (canvas dostaje <Configure> przy zmianie szerokości).
- STAŁE LOGTAIL SKORYGOWANE DO ORYGINAŁU (odzyskanego z notatek poprzedniej
  sesji): INITIAL_SCAN_BYTES = 2 MB (pełna sekwencja startowa zmodowanego
  serwera mieści się w skanie ogona logu), BIG_LOG_BYTES = 256 KB (log
  większy bez markera w ogonie = serwer od dawna pracuje => GOTOWY),
  ROTATION_GRACE_S = 15 s (łaska na rotację/kasowanie loga przez ASM).
  W 3.39.1 wartości były zgadywane (128 KB / 10 MB / 5 s) — skorygowane.
- Wersja podbita w tytule okna, "O programie" i User-Agent zapytań CF.

ZMIANY W 3.39.1 "Powrót stałych LogTail" (bugfix):
- BUGFIX: przywrócone 3 stałe (INITIAL_SCAN_BYTES / BIG_LOG_BYTES /
  ROTATION_GRACE_S), które wyleciały z kodu przy reorganizacji w 3.39.
  Skutki braku (rozwijane po cichu przez try/except, więc program
  działał, ale gorzej):
  - po starcie programu NIE działał wstępny skan ogona ShooterGame.log
    (status mapy wisi na "---" do pierwszej NOWEJ linii w logu, zamiast
    od razu pokazać GOTOWY / CRASH / startuje...),
  - brak grace-periodu przy rotacji loga (ASM kasuje/przemianowuje log
    przy starcie serwera) - mogło mignąć fałszywe OFFLINE,
  - martwa heurystyka "duży log => serwer raczej gotowy".
- Wartości: skan 128 KB ogona loga; duży log = 10 MB; grace = 5 s.
- Wersja podbita w tytule okna, "O programie" i User-Agent zapytań CF.
- Okno modów i cała mechanika 3.39 - BEZ ZMIAN (czekają na wymianę
  ustaleń dot. kafelków).

ZMIANY W 3.39 "Batch Mode + odporność" (dokumentacja zaległości):
- CURSEFORGE BATCH MODE: zamiast osobnego zapytania per mod - JEDNO
  zapytanie POST /v1/mods dla wszystkich modów naraz (chunki po 50 ID
  na wszelki wypadek). Efekt: O(1) zapytań zamiast O(n) - szybsze
  sprawdzenie, mniej ruchu, mniejsza szansa na limity API CurseForge.
- RCON: kolejka per mapa + automatyczny RETRY 3 próby z backoffem 2 s
  na komendę (zabezpieczenie przed chwilowymi dropami połączenia);
  błąd raportowany dopiero po 3 nieudanych próbach.
- LOGOWANIE THREAD-SAFE: wpisy do dziennika lecą przez kolejkę
  (_log_queue) konsumowaną w głównym wątku - zero wywołań Tk z wątków
  pobocznych (stabilność GUI przy pracy 24/7).
- TELEMETRIA: niewidoczne błędy (LogTail, zapisy JSON, worker CF)
  zapisywane do asa_debug.log obok programu - łatwiej diagnozować
  "coś nie działa" zdalnie.
- Zapis stanu wersji modów po KAŻDYM sprawdzonym modzie (odporność
  na utratę postępu przy zamknięciu programu w trakcie sprawdzania).

================================================================================
 ASAonly - Manual Mod Refresher  (wersja 3.38)
================================================================================

ZMIANY W 3.38 "Kompaktowe kafelki w oknie modow + czyste zamykanie":
- OKNO MODÓW ZBUDOWANE OD NOWA (drugie podejscie - kafelki jak najnizsze):
  - kafelek ma ~44-48 px wysokosci: jedna linia nazwy + linie informacji,
    ZERO paska sterowania na dole;
  - checkbox "[x] Monitoruj" i przycisk "[Strona]" siedza w tej SAMEJ
    linii co nazwa moda, po prawej stronie (koniec z tragicznym
    umieszczeniem "fistaszka" pod spodem);
  - LED statusu na poczatku linii nazwy, informacje (ID / Znana /
    Najnowsza / status / Mapy) w nastepnych liniach na cala szerokosc;
  - okno NIGDY nie ucina kafelkow: wysokosc okna dopasowuje sie do
    tresci (limit = ekran), suwak pojawia sie TYLKO gdy modow jest
    wiecej niz miesci sie na ekranie; reczna zmiana rozmiaru okna nie
    jest nadpisywana (tylko suwak sie odswieza);
  - przy otwarciu okna lista modow odswieza sie natychmiast (unia
    z tabow) - bez czekania na pierwsze sprawdzenie.
- POPRAWKA ZAMYKANIA PROGRAMU: niszczenie okien (dziennik/mody) anuluje
  wszystkie oczekujace zadania `after`, zeby Tk nie rzucal
  "invalid command name" przy zamykaniu; proces konczy sie czysto.
- Zachowane z 3.37: standardowa jedna linia przyciskow
  [EN/PL] [O programie] [Dodaj mape] [Monitorowane mody] [Dziennik logow]
  [Wykonaj zalegle aktualizacje] [Anuluj procedure], bez "Zapisz
  konfiguracje", bez ciemnego paska, bez globalnej listy modow.

================================================================================
 ASAonly - Manual Mod Refresher  (wersja 3.37)
================================================================================

ZMIANY W 3.37 "Standardowa sekcja + okno modow od nowa + prywatne katalogi"
(wg Twojego zgłoszenia):
- KASACJA ciemnego paska: zamiast kafelka - STANDARDOWA SEKCJA przycisków
  w JEDNEJ linii, zwykłe przyciski jak na samym początku programu:
    [EN/PL] [O programie] [Dodaj mapę] [Monitorowane mody]
    [Dziennik logów] [Wykonaj zaległe aktualizacje] [Anuluj procedurę]
  Nazwy przycisków nowe ("EN/PL" zamiast "EN"), przycisk "Zapisz
  konfigurację" WYLECIAŁ (zastąpiły go przyciski zapisu per-tab).
- LINIA LISTY MONITOROWANYCH MODÓW SKASOWANA CAŁKOWICIE z sekcji API
  (pole wpisywania i przycisk "Mody z serwerów" zniknęły z głównego okna).
- OKNO MODÓW ZBUDOWANE OD NOWA (reflow zamiast ucinania kafelków):
  - lista modów = unia z WSZYSTKICH TABÓW (każdy tab zasysa swoją listę
    z serwera ARKa przyciskiem "Mody z serwera" w zakładce),
  - LINK DO STRONY MODA = PRZYCISK "Strona" NA KAFELKU (klik w kafelek
    nic nie robi),
  - KAŻDY KAFELEK ma SLOT MONITOROWANIA (checkbox "Monitoruj" ON/OFF);
    wyłączony mod nie jest sprawdzany (szara dioda, status "wył."),
  - okno NIGDY nie ucina kafelków: gdy się mieszczą - wysokość okna =
    treść i suwak ukryty; gdy nie - suwak; ręczna zmiana rozmiaru
    respektowana.
- KAŻDY TAB: WŁASNY PRZYCISK ZAPISU "Zapisz tab" (w nagłówku linii RCON)
  i WŁASNY PRYWATNY KATALOG asa_tabs/<nazwa>/:
  - config.json (konfiguracja mapy + hasło RCON),
  - backups/ - BACKUP robiony TYLKO gdy zawartość się zmieniła,
    trzymane ostatnie 10 kopii (monitoring kopii zapasowych),
  - zmiana nazwy taba przenosi cały katalog,
  - KASOWANIE taba = ręczne skasowanie jego katalogu asa_tabs/<nazwa>/,
  - asa_secrets.json zawiera tylko klucz API (hasła są w katalogach tabów),
  - migracja automatyczna: stare asa_server_*.json (3.36) i "servers"
    z asa_config.json (3.35) przenoszone do katalogów przy starcie.


- KAFELEK PRZYCISKÓW = DOKŁADNIE TWOJA LISTA, 8 przycisków w DWÓCH
  rzędach (4+4), bez żadnych dodatków:
    rząd 1: [PL/EN] [O programie] [Dodaj mapę] [Zapisz konfigurację]
    rząd 2: [Monitorowane mody] [Dziennik logów]
            [Wykonaj zaległe aktualizacje] [Anuluj procedurę]
- NIE MA PRZYCISKU "USUŃ MAPĘ" - usunięty całkowicie (przycisk,
  tłumaczenia i metoda). KASOWANIE TABA = RECZNE skasowanie jego
  prywatnego pliku asa_server_<nazwa>.json - po restarcie taba nie ma.
- KAŻDY TAB MA SWÓJ PRYWATNY PLIK KONFIGURACJI: asa_server_<nazwa>.json
  obok programu - konfiguracja mapy (IP, port, logi, linie RCON, mody)
  ORAZ hasło RCON. asa_secrets.json zawiera teraz TYLKO klucz API.
  Automatyczny zapis NIGDY nie rusza tych plików - zapisuje je tylko
  przycisk "Zapisz konfigurację". Zmiana nazwy taba przenosi jego plik
  pod nową nazwę (hasło zostaje w pliku).
- MIGRACJA: przy pierwszym uruchomieniu 3.36 stare taby z asa_config.json
  (klucz "servers") i hasła z asa_secrets.json są automatycznie
  przenoszone do osobnych plików tabów; "servers" znika z konfiguracji.
- PRZYCISKI SĄ ZWYKŁE (jak "O programie"): standardowe, bez diod i
  ramek - naprawiony wygląd z 3.35.
- (pozostałe zmiany 3.35 zostają: sekcja RCON w jednej linii, klucz API
  z własnym przyciskiem zapisu, dłuższe pole modów + "Mody z serwerów",
  dymki-tooltipy przy przyciskach, "Sprawdź mody teraz" w pasku statusu)

ZMIANY W 3.35 "PRZEBUDOWA GŁÓWNEGO OKNA"  (wg Twojego zgłoszenia + A1.PNG):
- PASEK Z DWOMA PRZYCISKAMI -> KAFELEK Z PRZYCISKAMI: ciemny pasek
  (taki jak na zdjęciu A1) ma teraz TYTUŁ programu i 9 przycisków w
  3 STALYCH rzędach (na sztywno, jak obstawiałeś - nie zmieszczą się
  w jednym rzędzie): [PL/EN] [O programie] [Dodaj mapę] /
  [Zapisz konfigurację] [Monitorowane mody] [Dziennik logów] /
  [Wykonaj zaległe aktualizacje] [Anuluj procedurę] [Usuń mapę].
  Przyciski wyglądają jak dotychczasowy "O programie" (standardowe).
  Przy DZIENNIKU i MODACH świeci się mała dioda: zielona = okno
  otwarte, szara = zamknięte.
- LINIA KLUCZA API zostaje NA SAMEJ GÓRZE (pod kafelkiem) i ma
  WŁASNY przycisk "Zapisz klucz" w tej samej linii - zapisuje TYLKO
  prywatny plik asa_secrets.json (klucz API + hasła RCON), nigdy
  publicznego asa_config.json. Przycisk "Pokaz" dalej pokazuje/ukrywa
  klucz.
- LINIA MONITOROWANE MODY: dłuższe pole wpisywania + przycisk
  "Mody z serwerów". RESZTA przycisków WYLECIAŁA z tej linii.
- PONIŻEJ (osobna linia): interwał sprawdzania, opóźnienie między
  zapytaniami CF i czuwanie po restarcie. "Sprawdź mody teraz"
  przeniesione do paska statusu (na linii konfiguracji nie mieściło
  się przy szerokości 900 px).
- SEKCJA "POŁĄCZENIE RCON" w JEDNEJ LINII: IP | port | hasło |
  Test RCON. Przycisk "Zmień nazwę zakładki" przeniesiony do
  nagłówka listy linii RCON (dotyczy zakładki, nie połączenia).
- DYMKI (tooltipy): po najechaniu kursorem na przycisk/etykietę
  pojawia się opis, co on robi (po ~0,5 s, znika po odjechaniu).

ZMIANY W 3.34 "Okno modow od nowa"  (wg Twojego zgłoszenia):
- OKNO MODÓW ZBUDOWANE OD ZERA: skasowane stare nagłówki kolumn
  (ID / Znana (FileID) / Najnowsza (FileID) / Stan / Mapy).
- Usunięta DUPLIKACJA legendy diod: opis kolorów diod (zielona =
  aktualny, czerwona = update, ...) był pokazywany 2x - w tytule
  okna i na ramce. Teraz tytuł okna to po prostu "Mody", opis jest
  tylko tam, gdzie trzeba.
- KAFELKI W STYLU TWOJEGO PRZYKŁADU: jasnoniebieska (#80d0f8)
  zaokrąglona ramka (zaokrąglone rogi), biały środek, wysokość
  ~46-56 px - jak zakreślony przykład "Runic Wyverns" na Twoim
  obrazku. Nazwa moda czcionką 9 bold (lekko zmniejszona z 10),
  linia informacji (ID, Znana, Najnowsza, Stan, Mapy) czcionką 8
  (bez zmian - ta miała być dobra). Klik kafelka otwiera stronę
  moda w przeglądarce.
- LINKI DO STRON MODÓW NAPRAWDĘ DZIAŁAJĄ (sprawdzone!): CurseForge
  dla ASA akceptuje TYLKO adres ze slugiem, np.
  https://www.curseforge.com/ark-survival-ascended/mods/runic-wyverns
  (adres z numerem ID zwraca 404). Program pobiera z API CurseForge
  pole links.websiteUrl i zapisuje go dla każdego moda w konfiguracji
  (mod_pages); klik kafelka otwiera zapisany adres. Gdy brak linku,
  otwiera adres z ID jako ostatnią szansę.
- Okno modów dopasowuje wysokość do liczby kafelków (do wysokości
  ekranu; ręczna zmiana rozmiaru jest respektowana).

Lekki monitor aktualizacji modów ARK: Survival Ascended przez CurseForge API.
Gdy mod dostaje nową wersję, program wysyła ZAPLANOWANE komendy RCON (np.
ogłoszenie na czacie, a potem DoExit), a resztą - podniesieniem serwera i
pobraniem modów - zajmuje się ASA Dedicated Manager (ASM).

   Pomysł i koncepcja: @Magus
   Kod: Arena.ai Agent Mode (asystent, który zamienia pomysł użytkownika
        w działający kod)
   Program jest w 100% DARMOWY.

HISTORIA WERSJI
  3.23 "Zdrowie klastra"  - czuwanie powrotu, weryfikacja modów, crashloop
  3.24 "Współdzielenie"   - logi otwierane ze współdzieleniem (FILE_SHARE_
                           DELETE) - ASM może kasować ShooterGame.log
  3.25 "Mapy i diody"     - własne listy modów per mapa + panel modów z
                           diodami zamiast spamu w dzienniku
  3.26 "Porządek"         - skrócony nagłówek kodu; historia zmian tylko
                           tutaj (README), wersja widoczna w "O programie"
  3.27 "Podwójne doki"    - DRUGI zestaw morficznych strzałek: panel modów
                           można dokować lewo/prawo jak dziennik. Oba panele
                           współpracują - na tej samej stronie układają się
                           pionowo, bez kolizji. Strzałki ◀/▶ morfują w ✕
                           (✕ = wróć do pozycji domyślnej)
  3.28 "Start"            - pierwsze uruchomienie: okno dopasowane do
                           ekranu, diody LED OKRĄGŁE
  3.29 "Korekta layoutu"  - dwa rzędy strzałek (górny = mody, dolny =
                           dziennik; ◀ lewa, ▶ prawa); okno startuje w
                           pełnym rozmiarze, pasek strzałek zawsze widoczny
  3.30 "Tylko boczne okna" - lista modów WYJĘTA CAŁKIEM ze środka - to
                           boczne okno dokładnie jak dziennik. Start:
                           OBA boczne okna otwarte (mody lewo, dziennik
                           prawo). ✕ zamyka panel, ◀▶ otwiera na boku.
  3.31 "Układ bez kolizji" - panele i notetnik pozycjonowane wzglednie
                           (place) - boczne okna NIGDY nie nachodza na
                           srodek, nawet po zmniejszeniu okna (minsize).
                           Na wezszych ekranach rdzen i panele sie
                           sciskaja (podlogi 620/300) zamiast chowac;
                           okno = rdzen + otwarte panele, strzalki zawsze
                           widoczne. POPRAWKA: panel modow jest teraz
                           dzieckiem ramki srodkowej (place in_ NIE
                           reparentuje okna X - wczesniej mid zaslania
                           panel modow i byl on NIEWIDOCZNY).
  3.32 "Bryla + okna boczne" - panele to OSOBNE OKNA poza bryłą
                           programu: glowne okno NIE zmienia rozmiaru przy
                           otwieraniu/zamykaniu paneli. Rozciaganie
                           zewnetrznej krawedzi panelu zmienia TYLKO ten
                           panel; rozciaganie bryly w gore/dol ciagnie
                           panele razem (ta sama wysokosc). Strzalki:
                           3 stale przyciski na panel - ◀ otworz lewa,
                           ✕ zamknij, ▶ otworz prawa (bez morfingu).
                           Szerokosc paneli zapamietywana w configu.
                           POPRAWKA: zduplikowany blok startowy usuniety
                           (po zamknieciu program uruchamial sie RAZ
                           ponownie - teraz zamyka sie za pierwszym razem).
  3.33 "Niezalezne okna"  - TOTALNY RESET okien bocznych (wg zyczenia):
                           SKASOWANE strzalki ◀✕▶ i przyklejanie paneli
                           do bryly. Okno logu i okno modow to teraz
                           w PELNI NIEZALEZNE okna - mozesz je
                           przesuwac gdzie chcesz, jak glowne okno;
                           pamietaja swoja pozycje. Na gorze glownego
                           okna stylowy pasek z 2 przyciskami: DZIENNIK
                           i MODY (dioda zielona = okno otwarte) -
                           wlaczaja/wylaczaja okna. Mody w oknie modow
                           to KAFELKI jeden pod drugim: nazwa moda,
                           pod nia informacje (ID, wersje, mapy);
                           KLIK KAFELKA otwiera strone moda na
                           CurseForge w przegladarce. W zakladkach
                           serwerow pole "Mody mapy" dziala jak dawniej,
                           ale dodane mody pokazuja sie jako NUMERY
                           w okraglych kafelkach-diodach (kolory jak
                           diody w oknie modow); klik otwiera strone
                           moda. Konfiguracja: log_open/mods_open +
                           pozycje okien (dock_version=3 zostalo
                           porzucone w 3.34).

--------------------------------------------------------------------------------
WYMAGANIA
--------------------------------------------------------------------------------
- Windows (program testowany pod Windows; logi i ścieżki serwerów są w
  konwencji ASM), Python 3.10+ z python.org (zaznacz "Add to PATH").
- Działające ASA Dedicated Manager (ASM) z włączonym RCON na serwerach.
- Klucz API CurseForge: https://console.curseforge.com/ -> API Keys.
- Zakładki = mapy. Każda mapa musi mieć: IP, port RCON, hasło RCON.

--------------------------------------------------------------------------------
PIERWSZE URUCHOMIENIE
--------------------------------------------------------------------------------
1. Wklej klucz API CurseForge (pole u góry, przycisk "Pokaż").
2. Wpisz ID monitorowanych modów po przecinku. Możesz kliknąć
   "Mody z serwera" - program sam wczyta ID z folderów
   ...\ShooterGame\Binaries\Win64\ShooterGame\Mods\83374 (read-only).
3. Dodaj mapę ("+ Dodaj mapę"), podaj IP/port/hasło RCON, ścieżkę do logów
   (...\ShooterGame\Saved\Logs) i włącz "Monitoruj log na żywo".
4. Zaplanuj linie RCON: czas w sekundach od wykrycia update + komenda.
   Zaznacz ptaszkiem linie aktywne (szkice są szare i nie poleci).
5. (Opcjonalnie) w zakładce mapy możesz wpisać WŁASNE mody - pole
   "Mody mapy (puste = lista globalna)". Puste pole = mapa używa
   globalnej listy z góry okna.
6. Kliknij "Zapisz konfigurację" (to JEDYNY moment zapisu haseł i klucza),
   potem "Sprawdź mody teraz".

PIERWSZE URUCHOMIENIE - LAYOUT (3.33):
- Program = glowne okno (BRYLA) + 2 NIEZALEZNE okna: MODY i DZIENNIK.
  Okna nie sa przypiete do bryly - mozesz je przesuwac i umiescic
  gdzie chcesz (pamietaja swoja pozycje po zamknieciu programu).
- Na gorze glownego okna stylowy pasek z 2 przyciskami: [DZIENNIK]
  i [MODY] (zielona dioda = okno otwarte). Przycisk wlacza/wylacza
  okno. Mozesz tez zamknac okno jego wlasnym ✕ na ramce.
- MODY w oknie modow to KAFELKI jeden pod drugim: nazwa moda, pod
  nia informacje (ID, znana/najnowsza wersja, stan, mapy). KLIK
  KAFELKA otwiera strone moda na CurseForge w przegladarce.
- W zakladkach serwerow pole "Mody mapy" dziala jak dawniej (puste =
  lista globalna, "Mody z serwera" = folder Mods\83374), ale dodane
  mody wyswietlaja sie jako NUMERY w okraglych kafelkach-diodach
  (kolory stanu jak w oknie modow); klik kafelka otwiera strone moda.
- Okno startuje ~900px szerokosci. Diody LED (modów i map) sa okragle.

--------------------------------------------------------------------------------
MODY PER MAPA (3.25)
--------------------------------------------------------------------------------
- Każda zakładka ma własne pole modów. Różne mapy = różne mody.
- Puste pole w zakładce = mapa dziedziczy GLOBALNĄ listę (pole u góry).
- Program sprawdza mody RAZ (unia ID globalnych i per-mapa) - bez
  dublowania zapytań do CurseForge.
- Gdy mod dostaje update, procedura restartu działa TYLKO na mapach,
  które tego moda używają. Pozostałe mapy są pomijane z komentarzem
  w dzienniku ("nie używa zaktualizowanych modów") - bez zbędnych
  restartów serwerów.
- "Mody z serwera" (w zakładce) wypełnia pole modów TEJ mapy z jej
  własnego folderu Mods\83374. Przycisk u góry okna wypełnia listę
  globalną (unia wszystkich map).

--------------------------------------------------------------------------------
PANEL MODÓW Z DIODAMI (3.25)
--------------------------------------------------------------------------------
- Zamiast spamu w dzienniku ("Mod X: nazwa...", "Mod X: bez zmian...")
  stan modów widać w bocznym oknie "Mody" (dokowanym jak dziennik):
    kolumny: ID | Nazwa | Znana (FileID) | Najnowsza (FileID) | Stan | Mapy
- Podczas sprawdzania dioda aktualnie pytanego moda MIGA na niebiesko,
  a pasek statusu pokazuje progres: "Sprawdzanie modów (3/9): Nazwa".
- Po sprawdzeniu dioda zostaje w kolorze stanu:
    zielona      = mod aktualny (bez zmian)
    czerwona     = dostępny update (program zaraz zapyta / wykona)
    pomarańczowa = update ZALEGŁY (czeka w kolejce)
    szara        = błąd CurseForge (problem z API/kluczem)
- Kolumna "Mapy" pokazuje, które mapy danego moda używają.
- W dzienniku zostają tylko ważne wpisy: wykrycie update'u, błędy CF,
  pierwsze widzenie moda i podsumowanie (1 linia na sprawdzenie).

--------------------------------------------------------------------------------
JAK TO DZIAŁA
--------------------------------------------------------------------------------
- Program sprawdza CurseForge co ustawiony interwał (min. 30 s). Pierwsze
  widzenie moda tylko zapamiętuje wersję (bez restartu).
- Gdy mod ma nową wersję: startuje PROCEDURA RESTARTU - komendy lecą na
  wszystkie aktywne mapy wg czasu (globalny zegar od wykrycia update).
  Ostatnia linia = koniec roboty, program wraca do monitorowania.
- {MOD NAME} w komendzie zostaje podmienione na "Nazwa moda wersja"
  (np. ServerChat Uwaga! Update: {MOD NAME}).
- CZUWANIE POWROTU (3.23): jeśli procedura użyła DoExit, program pilnuje
  powrotu map do GOTOWY ("Mapa X: GOTOWY ✓ 2:14 po restarcie", potem
  "KLASTRA GOTOWY"). Timeout domyślny 20 min - ASM restartuje serwery
  uznane za zombie po 10 min, 20 min daje czas na ten restart bez
  fałszywego alarmu (konfigurowalne w polu "Czuwanie (min)").
- WERYFIKACJA MODÓW (3.23): po powrocie program porównuje foldery
  Mods\83374 (nazwy ModID_FileID) ze snapshotem sprzed restartu.
  "✓ na N mapach" = dobrze. Czerwone "ASM nie pobrał?" = coś nie zagrało.
- UZGODNIENIE (3.23): zaległość sama znika, gdy WSZYSTKIE serwery mają już
  docelowy ModID_FileID (np. po ręcznym restarcie przez ASM).
- CRASHLOOP (3.23): 3 krachy mapy w 15 minut = czerwony alarm w dzienniku.

--------------------------------------------------------------------------------
ZALEGŁOŚCI I AUTOMAT RCON (3.22)
--------------------------------------------------------------------------------
- Automat RCON WYŁ.: nowe update'y PARKUJĄ (nic nie poleci). Widać je na
  pasku: "ZALEGŁE UPDATE'Y: ..." + przycisk "Wykonaj zaległe (n)".
- Automat RCON WŁ.: program PYTA (TAK/NIE) przed startem procedury.
  Odmowa jest respektowana - nie zapyta ponownie, dopóki nie zmienisz
  stanu linii/map.
- Update w trakcie trwającej procedury lub czuwania powrotu też parkuje.
- Zaległości przetrwają restart programu (zapis w asa_config.json).

--------------------------------------------------------------------------------
BEZPIECZNIKI
--------------------------------------------------------------------------------
- CRASH GUARD: mapa w stanie CRASH/OFFLINE w trakcie procedury = jej
  pozostałe linie pomijane (update i tak zastosuje się przy restarcie ASM).
- DoExit jest TWARDO blokowany, gdy mapa wstaje (startuje/ładuje/silnik) -
  wyślesz go ręcznie z pola admina, gdy mapa będzie GOTOWY.
- PASEK DIOD: kolorowe diody map w pasku statusu - jeden rzut oka na klaster
  (zielony=GOTOWY, pomarańczowy=startuje, czerwony=CRASH/OFFLINE, szary=---).
- Mapę możesz wyciszyć ptaszkiem "Mapa aktywna" (master) - wtedy żadna jej
  linia nie poleci, ale logi dalej są śledzone.

--------------------------------------------------------------------------------
PLIKI KONFIGURACJI - UWAGA!
--------------------------------------------------------------------------------
- asa_secrets.json  <- hasła RCON + klucz API. NIGDY nikomu nie wysyłaj!
  Zapisuje go WYŁĄCZNIE przycisk "Zapisz konfigurację". Zamknięcie
  programu ani autozapisy go nie ruszają.
- asa_config.json   <- ustawienia (bez haseł). Bezpieczny do udostępniania.

--------------------------------------------------------------------------------
PORADY
--------------------------------------------------------------------------------
- W ASM włącz RCON i ustaw hasło; port RCON to zwykle 27020 (lub wybrany).
- Ścieżka do logów to folder Z plikiem ShooterGame.log, np.:
  C:\ARKservers\Ragnarok_WP\ShooterGame\Saved\Logs
- Dla "Mody z serwera" / weryfikacji potrzebny jest folder Mods\83374 obok:
  C:\ARKservers\Ragnarok_WP\ShooterGame\Binaries\Win64\ShooterGame\Mods\83374
- WSPÓŁDZIELENIE PLIKÓW Z ASM: program otwiera logi serwera z pełnym
  prawem współdzielenia (FILE_SHARE_READ|WRITE|DELETE), więc ASM może
  w każdej chwili usunąć/przemianować ShooterGame.log przy starcie serwera
  - nie zobaczysz już "file is in use and cannot be deleted".
- Przykładowy plan linii (czas: komenda):
     15 : ServerChat Uwaga! Restart za 15 minut!
    900 : ServerChat Restart za 15 minut!...  (dostosuj do własnego planu)
   3600 : DoExit
  (czasy bezwzględne od wykrycia update; linie różnych map lecą równolegle)
- {MOD NAME} podmieni się na np.: Awesome Mod 1.2.3
- Gdy mapa "nie wróci" w czasie czuwania: sprawdź ASM (proces zombie?),
  logi serwera i czy ścieżka logów jest poprawna.

--------------------------------------------------------------------------------
ROZWIĄZYWANIE PROBLEMÓW
--------------------------------------------------------------------------------
- "Brak klucza API CurseForge." -> wpisz klucz i zapisz konfigurację.
- Mod się nie wykrywa -> czy ID jest na liście? Czy interwał min. 30 s?
- "Błąd RCON: Auth failed" -> złe hasło lub port RCON w ASM.
- Dioda szara / status --- -> włącz "Monitoruj log na żywo" i sprawdź
  ścieżkę do logów.
- Weryfikacja pokazuje "ASM nie pobrał?" -> ASM nie zrestartował serwera
  albo mod nie został pobrany - sprawdź ASM ręcznie.

================================================================================
ENGLISH SUMMARY
================================================================================
- Tabs = maps; each has its own RCON + scheduled lines (time in seconds
  since update detection, absolute).
- On CurseForge update: run scheduled RCON lines (e.g. ServerChat + DoExit),
  then ASA Dedicated Manager restarts servers and downloads mods.
- 3.23: return watch (maps must reach READY after DoExit; timeout 20 min,
  configurable), mod verification via Mods\83374 folder names, crash-loop
  alarm (3 crashes / 15 min), "Mods from server" button, pending-update
  reconciliation when all servers already have the new ModID_FileID.
- 3.24: logs opened with FILE_SHARE_READ|WRITE|DELETE - ASM can delete
  ShooterGame.log at server start (no more "file is in use").
- 3.25: per-map mod lists (empty = global list) - only maps using the
  updated mods restart; mods panel with LEDs (green = up to date,
  red = update, orange = pending, gray = CF error, blue = checking),
  per-mod log spam removed, progress in status bar.
- Secrets (asa_secrets.json) are written ONLY by the "Save config" button.
- 3.27: second set of morphic arrows - the MODS panel can be docked
  left/right like the log panel. Both panels cooperate: docked on the
  same side they stack vertically, no collision. ◀/▶ morph into ✕
  (✕ = return to default position: log hidden, mods inline).
- 3.28: first run sizes the window to fit the screen (never shrunk -
  arrows always visible), LEDs are ROUND.
- 3.29: two arrow rows (top = mods, bottom = log; ◀ left, ▶ right);
  window starts full-size, arrow bar always visible.
- 3.30: mods list REMOVED from the middle completely - it is a side
  window exactly like the log. Start: BOTH side windows open (mods
  left, log right). ✕ closes a panel, ◀▶ opens it on the side.
- 3.31: relative positioning - side panels can NEVER overlap the
  center (minsize enforced); on narrow screens the core and panels
  shrink (floors 620/300) instead of hiding; window = core + open
  panels, arrows always visible. FIX: the mods panel is now a child
  of the center frame (place in_ does NOT reparent X windows - mid
  was covering the mods panel, making it INVISIBLE).
- 3.32: THE BLOCK + SIDE WINDOWS - the main window is a solid block;
  panels (mods left, log right) are SEPARATE windows docked OUTSIDE
  it. Opening/closing/resizing panels never changes the block; the
  block's top/bottom resize drags the panels along (same height);
  a panel's outer-edge resize changes only that panel. Arrows are
  now 3 fixed buttons per panel: ◀ open left, ✕ close, ▶ open right.
  Panel widths are remembered in the config.
- 3.33: FULL RESET of the side windows (as requested): ALL arrows
  removed; the log and mods windows are now FULLY INDEPENDENT -
  you can drag them anywhere, like the main window (position is
  remembered). A stylish top bar on the main window has 2 toggle
  buttons: LOG and MODS (green LED = window open). The mods window
  shows mods as TILES stacked vertically: mod name on top, info
  (ID, versions, state, maps) below; CLICKING A TILE opens the
  mod's CurseForge page in your browser. In server tabs, the
  "Map mods" field works as before, but added mods show as NUMBERS
  in round LED tiles (state colors as in the mods window); clicking
  one opens the mod page. Config: dock_version=4, log_open/mods_open
  + window positions.
================================================================================
- 3.40: mods window REBUILT from scratch with PLAIN WIDGETS (no canvas
  text drawing, zero manual pixel math): name + info line wrap themselves,
  LED + colored state text next to the name, "Monitor" checkbox and "Page"
  button as normal widgets, MOUSE-WHEEL scrolling (active only when the
  cursor is over the mods window). Tiles can no longer be clipped - the
  failure mode of 3.34-3.39 is structurally gone, not patched.

================================================================================
 PRZEPROSINY ZA TŁUMACZENIE ("KWIATKI" W TEKSTACH)
================================================================================
Część tekstów w programie i dokumentach była generowana przez AI, która
nie specjalizuje się w języku polskim - stąd dziwne odmiany, "kwiatki"
i literówki. Za te przeoczenia przepraszamy. Znaczenie zawsze wynika
z kontekstu, a tłumaczenie zostanie poprawione w kolejnych wersjach.
================================================================================
