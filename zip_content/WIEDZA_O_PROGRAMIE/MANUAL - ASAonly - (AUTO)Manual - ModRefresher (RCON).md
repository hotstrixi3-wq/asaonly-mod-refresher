# MANUAL — ASAonly - (AUTO)Manual - ModRefresher (RCON)

> Instrukcja „dla opornych" — program rozbity na czynniki pierwsze.
> Ten sam plik służy jako KONTEKST dla asystenta AI (sekcja 8 na końcu).
> Wersja dokumentu: 3.86.7 (aktualizowana przy każdej wersji programu).

### Powrót w 3.86.7 i archiwum od 3.86.6

Powrót po DoExit wymaga nowego uruchomienia oraz świeżego potwierdzenia GOTOWY.
Od 3.86.7 potwierdzeniem jest nowy znacznik READY w logu albo udana sonda RCON
ListPlayers dla nowego procesu. Ścieżka RCON wymaga znanej tożsamości procesu
przed DoExit i po nim (PID oraz czas startu); odpowiedź jest sprawdzana ponownie
przed zastosowaniem. Sonda może działać podczas czuwania, także gdy na ekranie
został stary GOTOWY. Jest ponawiana nie częściej niż co 30 sekund.
Stary log lub spóźniona odpowiedź poprzedniego procesu nie są dowodem powrotu.
Samo potwierdzenie RCON nie zatwierdza wersji załadowanych modów: bez świeżego
dowodu z logu zaległość pozostaje niezweryfikowana. Bez potwierdzenia powrotu mapa
po limicie czasu dostaje alarm; Refresher jej sam nie uruchamia.

Pole „Archiwum PADY — limit” w głównym oknie: 256–65536 MiB, domyślnie 2048;
0 wyłącza rotację. Zmienioną wartość zapisz tak jak inne ustawienia programu.
Nieprawidłowa wartość oznacza domyślne 2048 MiB. Wątek kopiujący czyta bezpieczną
migawkę tej wartości, bez wywołań interfejsu z obcego wątku.

Najpierw powstaje kopia padu, dopiero potem działa rotacja. Usuwane są najstarsze
rozpoznane kopie w formacie 3.86.6. Najnowsza oraz ostatnia pełna kopia każdej mapy
są chronione. Dlatego limit jest miękki: chronione kopie mogą go przekroczyć.
Stare archiwa 3.86.4/3.86.5 i obce pliki są liczone, ale nie są automatycznie
usuwane. W dzienniku widać zajęte MiB, limit, liczbę usuniętych kopii i ostrzeżenia
o przekroczeniu lub niepełnym pomiarze. Zmniejszenie limitu uruchomi rotację przy
następnym zapisie dowodów. Dowiązania i junctions powodują zachowawcze pominięcie
rotacji z ostrzeżeniem. Archiwum nie ma gwarancji wolnego miejsca na całym dysku.

Zmiana nazwy mapy przenosi jej alarm braku powrotu i alarm RCON. Błąd zapisu
przywraca poprzednią nazwę i alarmy. Jeśli nowa nazwa już ma osierocony alarm,
program nie nadpisuje go i prosi o inną nazwę.

### Alarmy RCON i powrót mapy w 3.86.5

Odrzucone logowanie RCON lub odrzucone połączenie kończy próbę dla tej mapy bez
czekania całego harmonogramu. Pozostałe mapy mogą iść dalej. Czerwony alarm wskazuje
sprawdzenie hasła, adresu i portu; odrzucenie połączenia może też oznaczać wyłączony
serwer. Błąd nie dowodzi, że na mapie nie ma graczy.

Po nieudanym DoExit ta sama wersja moda nie jest ponawiana automatycznie.
Popraw dane w panelu RCON, zapisz je i użyj „Wykonaj zaległe aktualizacje”.
Udana sonda w ponowionej procedurze usuwa alarm RCON. Samo zamknięcie lub ponowne
otwarcie programu go nie usuwa, jeśli konfiguracja została zapisana poprawnie.
Ręczne wysłanie DoExit nadal wymaga potwierdzenia, teraz z ostrzeżeniem o wyłączeniu
mapy. Refresher sam jej nie uruchamia.

Nowy proces po crashu podczas zamykania może zakończyć czuwanie, bez czekania na
timeout. Znany ten sam PID i czas startu nie jest traktowany jako nowy proces.
Crashstack obecny przed włączeniem śledzenia jest punktem odniesienia; nowe pliki,
zmiany pliku i fatalny błąd w aktualnym logu nadal są wykrywane.

### Pady i odczekanie w 3.86.4

- **Odczekanie po wykryciu moda [min]**: domyślnie 5, zakres 0–60. Zero wyłącza.
  Czas biegnie od pierwszego wykrycia danego file ID i jest zapisywany z zaległością.
  Powtórne sprawdzenie CF go nie wydłuża; nowsza wersja zaczyna nowe odczekanie.
  Dotyczy również pustych map i ręcznego przycisku zaległości. Po odczekaniu
  zaczyna się zwykły harmonogram ogłoszeń. Zlecenie aktualizacji samego serwera
  jest niezależną przyczyną restartu i nie czeka na ten licznik.
- **Dowody padu**: `WIEDZA_O_PROGRAMIE/PADY/map_<nazwa>/<data-id>/`. Zapis obejmuje
  ShooterGame.log i świeże pliki crash z Logs oraz Saved/Crashes. `metadata.json`
  mówi, czego zabrakło albo co przekroczyło limit. Kopia jest próbą natychmiastową,
  nie gwarancją, że program zdąży przed usunięciem logu przez managera.
- **Mapa nie wróciła**: po czasie z pola czuwania (domyślnie 20 min) pojawia się
  trwały czerwony alarm. Kolejka idzie dalej. Sprawdź managera i zapisane dowody;
  jeśli manager wyczerpał próby startu, administrator musi rozwiązać przyczynę.
  Refresher nie uruchamia serwera. Alarm znika po potwierdzeniu nowego działającego
  procesu i GOTOWY. Przetrwa restart aplikacji, jeśli zapis konfiguracji się powiedzie.

Pełny opis: [V3.86.4-RUNDA-I-PADY.md](V3.86.4-RUNDA-I-PADY.md).

### Odzyskiwanie w 3.86.3

Gdy UPDATE SERWERA zgłasza odzyskiwanie, sprawdź wskazany błąd dostępu/dysku,
usuń jego przyczynę i wybierz **PONÓW ODZYSKIWANIE** w tym panelu. Program próbuje
też sam, do 10 razy co 30 sekund, gdy nie trwa kopiowanie ani oczekiwanie na DoExit.
Restart Refreshera uruchamia kolejną próbę. Treść alarmu strażnika jest w panelu i dzienniku.
Nie kasuj `zamrozenie_managera.json` ani `.refresher-kopia`: zawierają dane potrzebne
do naprawy. Uszkodzony/brakujący dziennik wymaga przywrócenia kompletnej instalacji
z zachowanego backupu; samo przeniesienie folderu nie naprawia plików.

Po 150 minutach trwającej podmiany pojawia się ostrzeżenie. Zamknięcie procesu
Refreshera pozwala strażnikowi spróbować cofnięcia plików. Wznowienie managera
nastąpi dopiero po udanym odzyskaniu. Jeden Refresher ma wyłączną kontrolę nad
wstrzymaniem managera — nie wstrzymuj go równolegle innym programem.

Przy niepewnym wyniku DoExit aktualizacji serwera program czeka do 300 sekund
na rzeczywiste wyjście procesu mapy. Nie wysyła komendy ponownie. Jeśli procesu
nie da się potwierdzić jako wyłączonego, nie kopiuje plików i liczy nieudaną próbę.
Szczegóły: [V3.86.3-RECOVERY.md](V3.86.3-RECOVERY.md).

---

## 0. JEDNYM ZDANIEM

Program siedzi obok Twojego serwera ARK: Survival Ascended, co kilka minut
sprawdza w CurseForge, czy Twoje mody mają nowe wersje, a w razie potrzeby
restartuje mapy przez RCON — w kolejce, jedna mapa startuje naraz (od 3.81):
mapa pusta idzie od razu i bez komunikatów, mapa z graczami dostaje Twój
harmonogram ogłoszeń. Mody pobiera i instaluje SAM SERWER podczas
uruchamiania, przez wbudowany klient CFCore. ASA Dedicated Manager ponownie
stawia proces po `DoExit` — program niczego nie grzebie w folderach gry
z jednym wyjątkiem od 3.85: plugin „Aktualizacja serwera” podmienia pliki
samego serwera ASA na nowy build — od 3.86 kopiuje je z własnego cache,
pobranego wcześniej przez SteamCMD (M15).
Program tylko PRZYSPIESZA: update i tak wejdzie przy najbliższym starcie
serwera, więc żadna pojedyncza mapa nie zatrzymuje reszty.

---

## 1. SZYBKI START (5 kroków)

1. **Klucz API**: pole u góry (gwiazdki) → wklej klucz z
   https://console.curseforge.com/?#/api-keys (darmowy) → **Zapisz klucz**.
   Masz backup starego programu? **Załaduj API z backupu** i wskaż plik.
2. **+ Dodaj mapę**, potem przycisk **RCON**: IP, port RCON i hasło RCON
   serwera (to hasło administratora serwera, NIE hasło gracza!) oraz
   harmonogram komend → **ZAPISZ WSZYSTKIE**.
3. **Folder logu**: wskaż `...ShooterGame/Saved/Logs` na serwerze —
   stąd program czyta status mapy i prawdziwą listę modów.
4. **Mody z serwera**: kliknij — lista wypełni się tym, co serwer
   NAPRAWDĘ ładuje (nie tym, co leży w folderze Mods).
5. **Zapisz tab**. Gotowe. Reszta dzieje się sama.

---

## 2. PIĘĆ FIARÓW PROGRAMU (zrozum to, zrozumiesz wszystko)

1. **TAB = MAPA.** Każda mapa serwera to osobna zakładka (tab) z własnymi
   ustawieniami, modami i harmonogramem. Nie ma mapy bez taba.
2. **LOG SERWERA = PRAWDA.** O tym, jakie mody serwer ładuje, decyduje
   wyłącznie jego log — nie zawartość folderu Mods (tam bywa bajzel).
3. **SEKRETY OSOBNO.** Hasła RCON i klucz API nigdy nie lądują w zwykłych
   plikach konfiguracji — mają własne pliki „sekret…" i nigdy nie opuszczają
   Twojego komputera (idą tylko do CurseForge / Twojego serwera).
4. **WSZYSTKO WERSJONOWANE.** Każdy zapis to NOWY plik z datą i godziną
   w nazwie; program trzyma 10 ostatnich — masz wbudowaną historię/backup.
5. **PROGRAM NIE WYCHYLA SIĘ ZA PŁOT.** Pisze własne pliki obok siebie,
   gada z serwerem przez RCON, z CurseForge, (od 3.85) ze Steamem przez
   SteamCMD i (od 3.86) z api.steamcmd.net. Niczego nie instaluje w systemie
   i nie zabija serwerów — restart serwera to zawsze uprzejme DoExit. Wyjątek
   (M15): na czas podmiany plików serwera program WSTRZYMUJE (nie zamyka)
   proces managera; od 3.86 pliki przychodzą z cache refreshera
   (`ASA UPDATES REFRESHER` obok serwerów), a nie z SteamCMD na mapie.

---

## 3. MECHANIZMY NA CZYNNIKI PIERWSZE

### M1. TAB MAPY (serce wszystkiego)
Pola tabu: nazwa mapy, IP i port serwera, folder logu, lista modów tabu,
przełącznik „mapa włączona" (wyłączony tab = mapy nie monitorujemy),
harmonogram linii (M6). Zmiany mapy zapisuje przycisk **Zapisz tab** pod jej
polami — zapisuje tylko tę mapę; obok znacznik „● niezapisane zmiany” pokazuje,
że coś czeka na zapis (od 3.85.3). Dane RCON zapisuje panel RCON (**ZAPISZ
WSZYSTKIE**). Przy zamykaniu program pyta o niezapisane zmiany.

### M2. PLIKI NA DYSKU (co gdzie leży)
Wszystko obok programu:
- `CONFIG_PROGRAM/CONFIG_PROGRAM - zapis ….json` — ustawienia ogólne (od 3.64 w osobnym katalogu)
- `CONFIG_SECRET_API/CONFIG_SECRET_API - zapis ….json` — klucz API CurseForge
- `CONFIG_MAPS_TABS/<nazwa mapy>/CONFIG_MAP <nazwa mapy> - zapis ….json` — ustawienia tabu (nazwa mapy w pliku — od 3.64)
- `CONFIG_MAPS_TABS/<nazwa mapy>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON <nazwa mapy> - zapis ….json` — hasło RCON w osobnym podkatalogu (nazwa mapy w pliku — od 3.66)
- `WIEDZA_O_PROGRAMIE/` — dokumentacja (README, MANUAL, MAPA, PROMPT, raporty), `dziennik-zdarzen.txt` (cały dziennik z okna konsoli, od 3.86.2), `asa_debug.log` (ukryte błędy programu) i dziennik stanu modów (od 3.71)

W katalogu głównym leżą: program (.py), starter (.bat), pakiet `asaonly/`
(części programu), `PLUGINY/`, testy (`tests/`, `symulacja/`), `LICENSE`
i `README.md`. Dokumenty schodzą do `WIEDZA_O_PROGRAMIE/`.
Zasady: nowy plik tylko przy realnej zmianie; rotacja 10 sztuk
(starsze stają się backupami); stare nazwy plików migrują same.

### M3. LISTA MODÓW (którą widzą diody)
Mody wchodzi do programu WYŁĄCZNIE przez taby. Lista główna = suma list
tabów. Dioda nad/pod polem = numer moda na liście; jej kolor mówi status
(niebieska = nie sprawdzono [od 3.59], zielona OK, żółta czeka, czerwona
do aktualizacji itd.). Aktualizacja moda,\nktórego dana mapa NIE używa, NIE restartuje tej mapy.

### M4. SPRAWDZANIE W CURSEFORGE
Kolejność sprawdzania (ważne!): (1) czy w ogóle są mody do sprawdzenia —
bez modów program nie interesuje się kluczem; (2) czy jest klucz.
Interwał (domyślnie 300 s) odlicza zegar na pasku statusu
„Monitoruje · Następne sprawdzenie: 299 s" (odliczanie w sekundach, od 3.59).
Pod spodem, w OSOBNEJ linii, kafelki statusów map (od 3.60): kropka + nazwa
+ status słowami („Genesis 1 · GOTOWY", „Ragnarok · CRASH"); najechanie
pokazuje dymek z wyjaśnieniem, a przy wielu mapach kafelki zawijają się
do kolejnych linii. Od 3.71 kafelki są KLIKALNE (przenoszą do mapy),
przy niezweryfikowanej liście modów dopisują chip [NOWY], a gdy strażnik
sonduje mapę albo podejrzewa wisę — chip [SONDA] / [WISI!] (od 3.73),
na początku paska siedzi przycisk **WYKRYJ** (skan logów + dopasowanie modów)
i dioda **CF** (stan CurseForge). Zapytania idą PACZKAMI — zwykle JEDNO zbiorcze na całą listę,
co samo w sobie oszczędza limity API. (Od 3.73 lista powyżej 50 modów jedzie w PACZKACH po 50 modów — jedno
zbiorcze zapytanie na paczkę — a między paczkami program robi przerwę:
tyle sekund, ile masz w polu opóźnienia CF (domyślnie 1 s, maksymalnie
60 s). Pole opóźnienia działa naprawdę — chroni limity API CurseForge.)
Brak klucza = JEDNO ostrzeżenie w dzienniku (nie spam — od 3.51).

### M5. AKTUALIZACJA MODA
Nowa wersja w CF → mod trafia do kolejki oczekających (miga na liście).
Jeśli mapa używa moda, wchodzi procedura restartu (M6) — a SERWER ARK
sam pobiera i instaluje nową wersję moda przy swoim starcie (robi to
wbudowany w serwer klient CFCore; program nie dotyka plików gry). Jeśli nowa wersja leży na dysku
już wcześniej (aktualizacja ręczna), program sam godzi wersje
i zdejmuje zaległość (od 3.41).

### M6. HARMONOGRAM RESTARTÓW (linie)
Każdy tab ma listę linii: **czas w sekundach od początku odliczania TEJ
mapy** (od 3.81; wcześniej: od wykrycia update'u, wspólny zegar) + komenda
RCON (np. `ServerChat restart za 5 minut`, `DoExit` — „zapisz i wyjdź") +
przełącznik wł./wył. Odstępy między mapami robi kolejka (M13) — nie trzeba
ich już ustawiać czasami. Na pustej mapie komunikaty i czekanie są pomijane.
Linie po `DoExit` nie są wysyłane (serwera już nie ma), a zaznaczone puste
wiersze są pomijane. Procedura w trakcie = pasek „PROCEDURA RESTARTU (T+Xs)"
+ przycisk Anuluj.

### M7. CZUWANIE PO RESTARTU (watch) I AUTO-TURA
Po restarcie mapy program czuwa: czeka, aż mapa wstanie (statusy z logu)
i sprawdza w logu nowego procesu, czy serwer załadował nową wersję moda.
Dopiero wtedy dysk jest wolny dla następnej mapy z kolejki. Mapa, która nie
wróciła w czasie czuwania, jest oznaczona jako nieudana — kolejka idzie dalej. Pasek pokazuje postęp czuwania. Gdy cały
klaster wróci do GOTOWY, a czekają jeszcze inne update'y — od 3.71 program
**sam rusza z kolejną turą po 60 sekundach karencji** (log: „automatycznie
kolejna tura za 60 s"; odwołanie: wyłączysz Automat RCON albo ruszysz
ręcznie). Wcześniej wyskakiwało okienko z pytaniem.

### M8. OGON LOGU (LogTail) — statusy mapy
Program czyta końcówkę logu serwera na żywo. Statusy: start / ładuje
mody / silnik / gotowa / crash / offline. Kolor diody tabu i kafelka
= aktualny status. Log czytany jest shared (nie blokuje serwera),
skan startowy ogona 2 MB.

### M9. RCON
Kanał rozmowy z serwerem: komendy administratora (DoExit, broadcast…).
Połączenie, harmonogram i ręczną konsolę ma wymagany plugin RCON (przycisk
**RCON** na pasku **Pluginy**). Hasło trzymane w sekretach tabu. Program ponawia próby przy potknięciu
(3 próby z odstępem). Od 3.71 używa go też bezbolesna sonda
„czy serwer żyje" (M12), a od 3.81 pytanie o graczy `ListPlayers` (M13).

### M10. IMPORT, BACKUP I PRZYWRACANIE (od 3.83 — jeden plugin „Konfiguracje”)
Przycisk **IMPORT / BACKUP** na pasku **Pluginy** otwiera jeden panel z dwiema zakładkami:
- **IMPORT ZE STAREGO REFRESHERA** — wskazujesz cały stary katalog programu
  (albo rozpakowany backup). Skan tylko czyta: pokazuje mapy (najnowszy zapis
  każdej), sekrety RCON i klucz CurseForge API; importujesz zaznaczone. Import
  weryfikuje listę modów z logu: serwer działa → korekta od razu; serwer stoi →
  lista czeka z flagą „niezweryfikowana” i koryguje się sama po pierwszym
  starcie serwera (od 3.50).
- **BACKUP I PRZYWRACANIE** — ZIP zapisanej konfiguracji programu i map
  (sekrety tylko po zaznaczeniu). Przywracanie sprawdza archiwum, podmienia
  konfigurację z rollbackiem i zamyka program BEZ zapisu (inaczej nadpisałby
  przywrócone pliki) — uruchom go ponownie. Niedostępne w trakcie procedury.

### M11. START PROGRAMU
Taby ładują się same. Pierwsze uruchomienie = szybki start w konsoli
(od 3.53, bez okienek). Stare nazwy plików migrują automatycznie.
Zegar wewnętrzny tyka co 500 ms: drukuje dziennik, odświeża diody,
pilnuje restartów, czuwania, sprawdzania modów — a od 3.71 także
strażnika (M12).

### M12. STRAŻNIK (monitor 3.71–3.73 — nic nie przeoczy)
Co 10 sekund program zerka na procesy i porty Twoich serwerów
(i na wiek wpisów w logach):
- **PAD** — proces mapy zniknął: program mówi, czy po śladzie crasha
  w logu, czy „zdechł cicho"; jeśli log pokazał crash, ale proces
  jeszcze żyje, czeka 90 s z wyrokiem (to może być tylko zapis dumpu).
  Od 3.73 odczyt portów rozumie polski Windows (stan „NASŁUCHUJĄCE”
  zamiast „LISTENING”, także z utraconymi ogonkami) — wcześniej
  detekcja PAD-ów u adminów z polskim systemem cicho nie działała.
  Od 3.86.2 zniknięcie procesu po `DoExit` wysłanym przez kolejkę to nie PAD:
  w dzienniku „serwer zamknięty po DoExit (planowy restart)”, OFFLINE nie na
  czerwono, a plugin CPU odzywa się dopiero przy GOTOWY (ślad crasha w logu
  nadal daje PAD).
- **WISI** — log milczy 15 minut (a autosave leci co kwadrans)?
  Program wysyła przez RCON bezpieczną sondę „listplayers" (tylko
  odczyt) — jeśli i RCON milczy, po 20 minutach alarm „serwer chyba
  wisi". Od 3.73 — w trakcie sondy i wisy kafelek mapy na pasku statusu
  pokazuje chip [SONDA] / [WISI!].
  Powrót życia w logu = informacja „serwer jednak działa”.
- **Samorestarty** — mapa wróciła do STARTUJE bez udziału człowieka?
  Program to liczy i zgłasza.
- **Utknięte pobieranie** — serwer zaczął pobierać mody (linie `LogCFCore`
  w logu), a przez 20 minut nie ma postępu (od 3.73; wcześniej 10) =
  ostrzeżenie.
- **Dziennik modów** — przed każdą procedurą zapisuje stan modów
  (ile, na których mapach, ile miejsca) do `WIEDZA_O_PROGRAMIE/
  dziennik-modow.txt` (rotacja 15 plików po 10 KB).
- **Sonda CurseForge** — gdy CF ma awarię, program nie spamuje:
  pyta o JEDEN mod w rytmie 1/3/15 min; dioda CF w pasku statusu
  pokazuje, czy CurseForge żyje (czerwona = awaria).

### M13. KOLEJKA I GRACZE (od 3.81)
- **Pytanie o graczy.** Przed odliczaniem mapy program wysyła przez RCON
  `ListPlayers`. PUSTO = mapa idzie od razu, bez komunikatów i bez czekania
  (inne komendy, np. `SaveWorld`, zostają). SĄ GRACZE albo NIE WIADOMO =
  Twój harmonogram bez zmian. Przed `DoExit` pustej mapy — drugie pytanie;
  ktoś wszedł = pełny harmonogram od tej chwili. Wyłącznik: „Pusta mapa:
  restart od razu" obok Automatu RCON.
- **Jeden start naraz.** Od `DoExit` do GOTOWY dysk należy do jednej mapy
  (o to chodzi w rozjeździe: restarty nie mogą zajechać SSD). Puste mapy
  idą pierwsze.
- **Ogłoszenia „na styk".** Ogłoszenia nie obciążają dysku, więc mogą lecieć
  równolegle — tak, żeby zegar mapy skończył się, gdy dysk się zwolni.
  Czas startu program mierzy sam (5 ostatnich pomiarów na mapę). Mapa bez
  własnego pomiaru bierze najdłuższy pomiar innej mapy; zupełnie bez pomiarów
  (pierwsza fala) kolejna mapa zaczyna ogłoszenia dopiero po powrocie
  pierwszej — potem program już wie. Pomiary możesz podać z góry: klucz
  `czasy_startu` w `CONFIG_PROGRAM`, np. `{"Ragnarok": [150]}` (sekundy od
  `DoExit` do GOTOWY; przy zamkniętym programie).
- **Nikt nie blokuje.** Mapa, która padła, ma zły harmonogram albo nie
  wróciła, jest pomijana z wpisem w dzienniku — reszta idzie dalej. Mapa,
  która wstała sama z nową wersją (manager, krach), wypada z kolejki.
- **Do sprawdzenia:** odpowiedź pustego serwera ASA na `ListPlayers` nie jest
  potwierdzona. Dziennik pokazuje surową odpowiedź; wzorzec pustego serwera
  to lista `listplayers_pusto` w `CONFIG_PROGRAM` (zmieniaj przy zamkniętym
  programie). Nierozpoznana odpowiedź = „są gracze".

### M14. KONTROLA CZASU (od 3.82, plugin 87)
Przycisk **KONTROLA CZASU** na pasku **Pluginy**. Sprawdza ręczne ustawienia czasu
w harmonogramach RCON tymi samymi regułami co procedura — tylko odczyt:
- **BŁĄD** = procedura pominie tę mapę (zły port, ten sam port na kilku mapach,
  wiersz w pół wypełniony — z numerem wiersza, brak `DoExit`).
- **UWAGA** = zadziała, ale wygląda na pomyłkę: czekanie ≥ 60 s bez komunikatu,
  komunikat „za 15 minut” wysłany w innym momencie niż 15 minut przed `DoExit`,
  komunikat razem z `DoExit`, linie po `DoExit`, pierwsza linia po ≥ 60 s
  (ślad starego wspólnego zegara).
- **INFO** = jak mapa zachowa się pusta i z graczami, pomiary czasu startu.
- **PODGLĄD FALI**: kiedy każda mapa odlicza, dostaje `DoExit` i wraca —
  liczone prawdziwym planistą kolejki. Zaznaczasz, które mapy są puste; dla map
  bez pomiaru wpisujesz zakładany czas startu.
Gdy plugin jest ON, nowe błędy i uwagi trafiają do dziennika (bez powtórzeń).

### M15. AKTUALIZACJA SERWERA (od 3.85, plugin 88; od 3.86 przez własny cache)
Przycisk **UPDATE SERWERA** na pasku **Pluginy**. Serwery mają się aktualizować bez
człowieka, a nieudane pobieranie nie może restartować serwerów (tak było 25.09.2026 w 3.85).
- **Wykrywanie:** co minutę api.steamcmd.net (nieoficjalna usługa, nie Valve; można
  wyłączyć w panelu). Gdy API nie odpowiada — SteamCMD co 5 min; przy działającym API
  SteamCMD raz na godzinę kontrolnie. Pierwsze sprawdzenie 30 s po starcie programu.
- **Cache:** nowy build od razu trafia SteamCMD-em do folderu `ASA UPDATES REFRESHER`
  obok serwerów (np. `C:\ARKservers\ASA UPDATES REFRESHER`; inny folder ustawisz
  w panelu). Pierwsze pobranie to cały serwer (ok. 12 GB; program sprawdza wolne
  miejsce), potem tylko różnice. Serwery w tym czasie DZIAŁAJĄ. Błąd = żaden restart;
  w dzienniku prawdziwy powód z `STEAMCMD\logs\content_log.txt` i następna próba po
  5, 15, 30 min. SteamCMD nigdy nie jest uruchamiany na katalogu mapy.
  Wyjątek (3.86.1): „Missing configuration” — SteamCMD nie ma jeszcze danych o serwerze
  ASA (tak kończy się zwykle pierwszy przebieg świeżo pobranego SteamCMD) — ponowienie
  od razu, do 2 razy co 10 s.
- **Plan:** gotowy cache (appmanifest: StateFlags 4) → program porównuje pliki cache
  z plikami mapy jeszcze przy działającym serwerze: które się różnią (rozmiar, czas,
  a przy samym innym czasie — treść). `steamapps`, `steamcmd` i `ShooterGame\Saved`
  (światy, konfiguracje) nigdy nie są kopiowane. Pliki identyczne, a brakuje tylko
  appmanifestu = sam appmanifest, bez restartu.
- **Mapa GOTOWA ze starszym buildem niż cache** → zwykła kolejka (M13): gracze,
  ogłoszenia, jeden start naraz. Tuż przed `DoExit` program sprawdza plan i miejsce
  na dysku i wstrzymuje proces managera; po wyłączeniu serwera kopiuje TYLKO różniące
  się pliki (każdy przez plik tymczasowy, stary do `.refresher-kopia\` w katalogu
  mapy), appmanifest na końcu, potem wznawia managera — manager sam podnosi serwer.
  Błąd kopiowania = wszystko wraca, serwer wstaje na dotychczasowym buildzie.
- **Jeden restart, nie dwa:** gdy Steam ma już nowszy build niż cache, mapy czekają,
  aż cache go dogoni. W trakcie rundy restartów cache nie jest ruszany.
- **Mapa z wyłączonym serwerem** (OFFLINE/CRASH albo od 30 min nie GOTOWA) i bez
  działającego procesu serwera — to samo bez `DoExit` i bez kolejki; kolejka restartów
  czeka w tym czasie.
- **Jeden updater:** plugin czyta z `user.config` managera tylko jego ustawienia
  aktualizacji. Włączone „Enable automatic update checking” = plugin nic nie robi i pisze
  dlaczego (manager przed swoją aktualizacją zabija każdy `steamcmd.exe`). Cache
  refreshera nie może być cache managera (`ASA UPDATES`) ani katalogiem mapy.
- **Bezpieczniki:** `CONFIG_PROGRAM\zamrozenie_managera.json` + osobny strażnik —
  manager zostaje wznowiony także po awarii refreshera, a przerwane kopiowanie jest
  najpierw WYCOFANE z dziennika (`.refresher-kopia\dziennik.json`); najwyżej 3 nieudane
  podmiany na build (co najmniej 30 min odstępu), potem tylko ręcznie.
- **Panel:** automatycznie ON/OFF, weryfikacja plików cache, API ON/OFF i co ile
  sekund, SteamCMD co ile minut, folder cache, proces managera, własna ścieżka SteamCMD;
  **SPRAWDŹ TERAZ**, **AKTUALIZUJ TERAZ** (także mimo limitu prób); tabela CACHE + map
  i ostatnie wyjście SteamCMD.
- **Wymagania:** program uruchomiony jako administrator; manager działa; w managerze
  „Enable automatic update checking” WYŁĄCZONE.
- Szczegóły, dowody z logów i z kodu managera: `V3.86-AKTUALIZACJA-SERWERA-PRZEZ-CACHE.md`
  (historia 3.85: `V3.85-AKTUALIZACJA-SERWERA-STEAMCMD.md`).

---

## 4. TRZY PRZYKŁADY (krok po kroku)

### P1. Pierwsza mapa od zera
Szybki start (sekcja 1) → w dzienniku widzisz „Śledzenie logu [Mapa]" →
dioda tabu zmienia kolory wraz ze startem serwera → po pierwszym
sprawdzeniu CF lista modów dostaje numery i diody. Koniec.

### P2. Nocą wychodzi nowa wersja moda
02:00 CF pokazuje nową wersję → dziennik: znaleziono aktualizację →
mapy używające moda wchodzą do kolejki → program pyta każdą o graczy
(`ListPlayers`) → puste idą pierwsze, od razu i bez komunikatów; mapa
z graczami dostaje Twoje ogłoszenia, a `DoExit` dopiero, gdy dysk jest
wolny → SERWER sam pobiera nową wersję moda przy starcie → czuwanie, aż
wstanie z nową wersją → następna mapa; jeśli w trakcie przyszedł kolejny
update — następna tura sama rusza po 60 s.
Rano czytasz w konsoli, co się działo (nic nie musisz robić).

### P3. Padł dysk — odtwarzanie u kolegi
Z backupu masz folder `CONFIG_MAPS_TABS/` (starsze kopie: `taby/`) i pliki zapisów. Nowy komputer:
1. Rozpakuj komplecik, uruchom starter (.bat sam dograje Pythona).
2. Klucz API: **Załaduj API z backupu** → wskaż `CONFIG_SECRET_API - zapis ….json`.
3. **IMPORT / BACKUP** → zakładka IMPORT → wskaż katalog z backupem i zaimportuj mapy (albo PRZYWRÓĆ Z ZIP, jeśli masz backup ZIP z tego programu).
4. Program sam zweryfikuje listę modów z logu serwera (M10) i po
   starcie serwera wszystko wróci do normy. Hasło RCON? Jeśli w backupie
   był plik sekretu mapy — weźmie z niego; jeśli nie — wpisz raz.

---

## 5. PROBLEMY I ROZWIĄZANIA

- **Windows: „nieautoryzowane zmiany"/dostęp do folderu** — to standardowa
  ochrona Windows (Kontrolowany dostęp do folderów), nie wirus. Kliknij
  **Zezwól/Tak**. Najprościej trzymać program w zwykłym folderze
  (np. `C:\ASAonly`), nie w Dokumentach/OneDrive.
- **„Brak klucza API CurseForge"** raz w dzienniku — program czeka na klucz
  (pole u góry). Nie powtarza, nie nagli.
- **Lista modów niezgodna z logiem po imporcie** — normalne przy imporcie
  z backupu; patrz M10 (samokorekta po starcie serwera).
- **Czerwona dioda CF w pasku statusu** — CurseForge ma awarię; program
  sam sonduje co 1/3/15 min i wróci do normy, gdy CF wstanie.
- **Alarm „serwer chyba wisi"** — log milczy 20 min i sonda RCON bez
  odpowiedzi; zajrzyj na maszynę (mapa może wisieć z graczami w środku).
- **„ListPlayers → nierozpoznana odpowiedź"** — pusta mapa jest traktowana
  jak mapa z graczami (pełny harmonogram). Sprawdź w dzienniku, co odpowiada
  Twój pusty serwer, i dopisz ten tekst do `listplayers_pusto` (M13).
- **„harmonogram czeka Xs przed DoExit, ale nie ma w nim komunikatu"** —
  czasy są lokalne (M6); dodaj `ServerChat …` albo skróć czas.
- **Nie wiesz, czy harmonogram jest dobry?** Kliknij KONTROLA CZASU (M14) —
  BŁĄD pokaże mapy, które procedura pominie, a PODGLĄD FALI — jak pójdzie restart.
- **„[SERWER] Aktualizacja czeka: brak dostępu do procesu managera”** — uruchom
  program jako administrator (M15). „…manager … nie działa” — uruchom managera.
- **„[SERWER] Nie znam najnowszego buildu ze Steama: …”** — SteamCMD nie podał
  buildu; panel UPDATE SERWERA pokazuje ostatnie wyjście SteamCMD.
- **Manager „zamarł” i nie wraca** — strażnik wznawia go sam (najpóźniej po
  limicie z M15); ponowne uruchomienie programu też go wznawia.
- **Kliknięcie w czarne okno konsoli** włącza w Windows zaznaczanie (tytuł okna
  zaczyna się od „Zaznacz”) — konsola wstrzymuje wtedy wypisywanie. Od 3.85.2
  program działa dalej, a zaległe linie pojawiają się po zakończeniu zaznaczania
  (Esc, Enter albo prawy przycisk myszy). Do 3.85.1 w takiej chwili stawało całe
  okno programu („Brak odpowiedzi”) razem z automatem. Od 3.86.2 program wyłącza
  w swoim oknie tryb szybkiej edycji — zwykłe kliknięcie już nic nie wstrzymuje;
  tekst kopiujesz przez menu okna (ikona w lewym górnym rogu) → Edytuj → Zaznacz
  albo z pliku `WIEDZA_O_PROGRAMIE\dziennik-zdarzen.txt` (cały dziennik, od 3.86.2).
- **Kwiatki zamiast polskich liter w konsoli** — przepraszamy; patrz
  przeprosiny w README. Treść zawsze zrozumiesz z kontekstu.

---

## 6. SŁOWNIK

- **TAB** — zakładka mapy w programie; całe jej życie.
- **RCON** — kanał komend administratora serwera gry.
- **CurseForge (CF)** — sklep/modohost, skąd program czyta wersje modów.
- **Klucz API** — Twój identyfikator w CF (https://console.curseforge.com/?#/api-keys).
- **Slug** — „ładna" nazwa moda w adresie strony CF.
- **Pending / zaległość** — kolejka modów czekających na aktualizację/restart.
- **DoExit** — komenda RCON: „zapisz świat i zamknij serwer".
- **Ogon logu (tail)** — czytanie końcówki pliku logu na żywo.
- **Sekret** — plik z hasłem/kluczem; NIE zwykła konfiguracja.
- **Rotacja** — trzymanie N ostatnich zapisów; starsze = backupy.
- **PAD / WISI / sonda** (3.71) — proces zniknął / log umilkł / bezpieczny
  test „listplayers" przez RCON.
- **ASM / ASA Dedicated Manager** — menedżer, który uruchamia, monitoruje
  i podnosi procesy serwerów (także po `DoExit`) i aktualizuje samą grę.
  Modów NIE pobiera — robi to klient CFCore wbudowany w serwer, przy każdym
  starcie. Program współpracuje z managerem. Od 3.85 aktualizację samego
  serwera może robić plugin „Aktualizacja serwera” (M15) — wtedy updater
  managera musi być wyłączony.
- **SteamCMD** — narzędzie Valve (wiersz poleceń) do instalowania
  i aktualizowania serwerów gier ze Steama.
- **Build** — numer wersji serwera ASA na Steamie (`buildid`); ten
  zainstalowany jest w `steamapps\appmanifest_2430930.acf` katalogu serwera.
- **Cache** (3.86) — folder z kompletnym serwerem ASA, który aktualizuje tylko
  SteamCMD refreshera; stąd pliki trafiają do map.
- **Manifest depotu** — spis plików jednego buildu. SteamCMD aktualizuje
  instalację tylko wtedy, gdy ma u siebie manifest buildu, który na niej leży;
  bez niego prosi o niego Steam, a ten anonimowo odmawia („Access Denied”).
- **Kolejka** (3.81) — kolejność restartów map: jedna mapa startuje naraz,
  puste pierwsze (M13).

---

## 7. PRZEPROSINY ZA „KWIATKI" (TŁUMACZENIE)

Część tekstów w programie i dokumentach była generowana przez AI, która
nie specjalizuje się w języku polskim — stąd dziwne odmiany, „kwiatki"
i literówki. Za przeoczenia przepraszamy. Znaczenie zawsze wynika
z kontekstu, a tłumaczenie zostanie poprawione w kolejnych wersjach.

---

## 8. DLA ASYSTENTA AI (ten plik jako kontekst)

Jeśli jesteś asystentem AI i dostajesz ten plik razem ze źródłem
`ASAonly - (AUTO)Manual - ModRefresher (RCON).py`:

- Cel: pomóc użytkownikowi-adminowi serwera ASA. Odpowiadaj po polsku,
  konkretnie, z pozycji praktyka (użytkownik czyta logikę, nie filozofię).
- Architektura: stdlib-only, tkinter; program `.py` + pakiet `asaonly/`
  (m.in. `procedura.py` — wykonanie, `kolejka.py` — czysty planista kolejki
  bez Tk i sieci) + wtyczki `PLUGINY/` (RCON 86 jest wymagany). Wątki:
  LogTail, CF worker, RCON (kolejka per mapa), monitor 3.71. Configi JSON
  wersjonowane z rotacją 10; dziennik modów z rotacją 15×10 KB (3.71).
- Niełamalne zasady źródła: (1) log serwera = prawda o modach;
  (2) mody wchodzą tylko przez taby; (3) sekrety osobno; (4) każda zmiana
  = nowa wersja + wpis w README; (5) program 100% darmowy; (6) program
  NIE pobiera modów (robi to serwer przez CFCore przy każdym starcie)
  i NIE zabija serwerów (proces po `DoExit` podnosi ASA Dedicated Manager;
  od 3.85 plugin 88 wstrzymuje managera na czas podmiany plików i ZAWSZE go
  wznawia; od 3.86 pobieranie idzie do cache przy działających serwerach,
  a jego błąd nie może wywołać restartu);
  (7) program jest AKCELERATOREM: żadna mapa nie zatrzymuje reszty, na
  ścieżce automatycznej nie ma okienek, przerwana procedura jest porzucana.
- Przed edycją: przeczytaj sekcje 2–3 (filary i mechanizmy M1–M15) — one
  odzwierciedlają faktyczny stan programu. Testy: `python symulacja/run_all.py`
  (sama biblioteka standardowa; albo `python -m pytest`) — katalogi `tests/`
  i `symulacja/`; `symulacja/e2e_prawdziwy_app.py` uruchamia PRAWDZIWĄ
  aplikację na atrapach serwerów.
- Język (od 3.84): każdy tekst dla człowieka to `t("polski", "English")`
  z `asaonly/jezyk.py` albo klucz słownika TR (`asaonly/tr.py`). Identyfikatory
  (stany, klucze konfiguracji, nazwy plików) bez tłumaczenia. Pilnuje tego
  `tests/test_i18n.py` — polski tekst poza `t()`/TR nie przejdzie testów.
