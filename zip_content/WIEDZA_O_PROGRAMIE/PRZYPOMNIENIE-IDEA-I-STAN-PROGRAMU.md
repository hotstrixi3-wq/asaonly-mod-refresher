# ASAonly ModRefresher — przypomnienie idei, zasad i rzeczywistego stanu

**Dokument bazowy przed diagnozą wsteczną.**  
Stan roboczy: V3.80.3 po ponownym audycie Koordynatora i Managera Pluginów. Dokument nie jest reklamą ani listą życzeń. Rozdziela ideę programu, zasady bezpieczeństwa, fakty potwierdzone na Windowsie, testy automatyczne oraz elementy nadal niepotwierdzone.

---

## 1. Główna idea programu

ASAonly ModRefresher nie jest wyłącznie sprawdzaczem CurseForge ani prostym programem do restartowania serwerów. Ma trzy równorzędne obowiązki:

1. **Skutecznie monitorować aktualny stan serwerów.**
2. **Kontrolować wersje modów na CurseForge i na serwerach.**
3. **Wykonywać zaprogramowane w czasie procedury przez linie RCON w tabach map.**

Żaden z tych trzech obowiązków nie może zostać potraktowany jako dodatek kosztem pozostałych.

Program współpracuje wyłącznie z **ASADedicatedManager** ze strony `https://asadedicatedmanager.eu/` (projekt Olrik-WP). Nie wolno utożsamiać go z produktem Cryptek/AASM ze strony `arkascendedservermanager.com` ani przenosić z tamtego produktu żadnych ustawień, interwałów, nazw plików, numerów wersji lub zasad działania. Rzeczywisty log Genesis potwierdza: po zniknięciu monitorowanego PID manager trzy razy sprawdza brak procesu w odstępach około 15 sekund, uznaje serwer za nieobecny i uruchamia nowy proces. Refresher nadaje wtedy stan `NIE MA / OFFLINE`, nie uruchamia procesu za managera i dalej obserwuje nowy cykl aż do GOTOWY.

---

## 2. Model użytkownika i konfiguracji

- Jeden tab odpowiada jednej mapie/serwerowi.
- Tab istnieje dopiero po ręcznym dodaniu go przez użytkownika lub świadomym imporcie.
- Każda mapa ma własną konfigurację i własny sekret RCON.
- Użytkownik nie powinien ręcznie edytować JSON-ów.
- Wszystkie normalne ustawienia muszą być dostępne z GUI.
- Przycisk ręcznego dodawania nowej mapy pozostaje w głównym oknie.
- Import dawnych konfiguracji jest funkcją pluginu Importera.

Aktualny układ katalogów obejmuje między innymi:

```text
CONFIG_PROGRAM/
CONFIG_SECRET_API/
CONFIG_MAPS_TABS/<nazwa mapy>/
CONFIG_MAPS_TABS/<nazwa mapy>/CONFIG_SECRET_RCON/
WIEDZA_O_PROGRAMIE/
PLUGINY/
```

Konfiguracje i sekrety są wersjonowane oraz rotowane. Sekrety mają pozostać oddzielone od zwykłej konfiguracji.

---

## 3. Zasady procedur RCON

- Procedury są celowo mapowe, ponieważ różne serwery potrzebują różnych czasów startu i różnych komunikatów.
- Tab może zawierać do 20 linii czasowych.
- Linia może zawierać wiadomość, komendę administracyjną lub końcowe `DoExit`.
- Zaznaczona, ale całkowicie pusta linia jest ignorowana.
- Linia wypełniona tylko częściowo jest błędem.
- Brak linii `ServerChat` może być świadomą konfiguracją użytkownika, a nie ograniczeniem programu.
- Procedura bez skutecznego `DoExit` nie może udawać, że serwer został zrestartowany.
- Błąd RCON nie może usuwać oczekującej aktualizacji ani otwierać fałszywego oczekiwania na powrót serwera.
- GOTOWY istniejący jeszcze przed procedurą nie jest dowodem powrotu. Najpierw musi wystąpić odejście procesu/stanu, a później nowy powrót do GOTOWY.

Rozsunięcie restartów służy przede wszystkim ochronie SSD przed jednoczesnym obciążeniem wielu serwerów.

---

## 4. Zasady kontroli modów

- Monitor agreguje mody ze wszystkich aktywnych tabów.
- Procedurę wykonuje się wyłącznie na serwerach, które rzeczywiście jej wymagają.
- Sam fakt, że serwer ma dany mod na liście, jest tylko jednym z danych wejściowych. Nie wolno automatycznie utożsamiać „serwer używa moda” z „serwer wymaga teraz wykonania procedury”. Decyzja musi wynikać z rzeczywistego stanu aktualizacji i serwera.
- Serwer, który nie wymaga procedury, nie może zostać objęty restartem tylko dlatego, że należy do klastra.
- Oczekujące aktualizacje są identyfikowane przez `mod_id`, nie przez nazwę.
- CurseForge ma nietypowe pole `iD`; parser musi je obsługiwać.
- Nie wolno przywracać reguły polegającej na dodawaniu `+3` do identyfikatora pliku. Artefakt Windows Server musi być wybierany semantycznie, a nie przez zgadywanie numeru.
- Konto/subskrypcje CurseForge użytkownika nie powinny być traktowane jako mechanizm sterujący CFCore serwera.
- Według obserwacji użytkownika i logów serwer sprawdza oraz pobiera mody podczas startu. Nie wolno zakładać innego zachowania bez dowodu.
- Zachowanie przy niemożności pobrania moda podczas startu nadal nie jest potwierdzone.
- Zachowanie klienta i serwera przy niezgodności wersji jest zmienne oraz zależne od czasu; nie wolno opisywać go jedną uniwersalną regułą.
- Operacyjny cel użytkownika: instalować aktualizacje możliwie szybko, a nie pozostawiać rozjazdu przez wiele godzin.
- Trzeba nadal odróżniać wersję oczekiwaną, zaobserwowaną na serwerze i wersję faktycznie zainstalowaną.
- Kwestia, czy log serwera jest ostatecznym autorytetem wersji, nie została formalnie zamknięta. CFCore library jest używana jako ważne źródło ukończonych instalacji, ale nie należy rozszerzać tego na niepotwierdzone twierdzenia.

---

## 5. Monitorowanie serwerów

Monitor obejmuje między innymi:

- statusy startu, ładowania modów, działania silnika i GOTOWY,
- crash/fatal markers,
- procesy i porty,
- wiek logu,
- przypadki `WISI`,
- sondy RCON tylko do odczytu,
- wykrywanie samorestartów,
- obserwację powrotu po procedurze.

Monitor ma unikać fałszywych alarmów. Brak pierwszego snapshotu procesów nie jest dowodem braku procesu.

---

## 6. Pluginy — idea i reguły

Główny program ma znać uniwersalny PluginHost oraz Manager Pluginów, a nie osobne przyciski i warunki dla każdego przyszłego pluginu.

Manager Pluginów **nie jest pluginem**. Jest częścią infrastruktury potrzebnej do załadowania pluginów.

Plugin deklaruje między innymi:

- nazwę,
- wersję,
- opis przeznaczenia,
- widoczność w Managerze,
- typ konieczny/opcjonalny,
- panel,
- test,
- stan ON/OFF,
- opcjonalną akcję w głównym pasku.

Program i pluginy należą do użytkownika. Nie budujemy ochrony przed „złośliwym właścicielem”. Izolacja wyjątków ma chronić działanie Refreshera przed zwykłym błędem programistycznym pluginu.

### Znaczenie ON/OFF

- **ON** — plugin jest aktywny i może wykonywać swoją deklarowaną pracę.
- **OFF** — brak automatycznej pracy w tle; ustawienia pozostają zapisane.
- Panel może nadal służyć do konfiguracji lub świadomej operacji ręcznej, zależnie od pluginu.
- Plugin konieczny nie ma przełącznika OFF.

Po zgłoszeniu użytkownika poprawiono CPU: CPU OFF nie powinien wykonywać cyklicznych skanów ani pisać cyklicznych logów.

---

## 7. Obecna lista pluginów

### Konieczne

1. **Guard konfiguracji**  
   Kontrola spójności aktywnych map, portów RCON i katalogów logów.

2. **Audyt wersji modów**  
   Wykrywanie sprzeczności w stanie wersji; bez zmieniania wersji.

### Opcjonalne

3. **CPU / Priority / Affinity**  
   Odczyt i opcjonalne egzekwowanie ustawień procesów serwerów.

4. **Status i historia serwerów**  
   Jeden plugin obserwacyjny: eksport aktualnego `status.json` dla zewnętrznych integracji oraz opcjonalna, rotowana historia zmian statusu/PID. Obie funkcje mają osobne ustawienia w panelu.

5. **Importer starych konfiguracji**  
   Skan całego wskazanego katalogu, wykrywanie map, sekretów RCON i klucza CurseForge API oraz wybór importu.

6. **Backup / Przywracanie**  
   Ręczne archiwa konfiguracji; sekrety tylko po jawnym zaznaczeniu.

7. **Pakiet diagnostyczny**  
   Bezpieczny ZIP do analizy bez haseł i kluczy API.

8. **Dysk / Katalogi serwerów**  
   Odczyt ścieżek, rozmiarów i wolnego miejsca; bez usuwania.

9. **Analizator logów ASA**  
   Ręczna analiza ogonów logów; bez sterowania serwerami.

10. **Narzędzia administratora RCON**  
    Ręczny `ListPlayers` i ręczne komendy z potwierdzeniem. Nie zastępuje procedur mapowych.

---

## 8. Plugin CPU — wymagania i stan

CPU pozostaje osobnym pluginem.

### Potwierdzone na rzeczywistym Windowsie

Dla trzech serwerów wykryto prawdziwe procesy i wartości:

- Extinction — PID 26440,
- Genesis 1 — PID 476,
- Ragnarok — PID 5636,
- aktualny priority był odczytywany jako `High`,
- affinity obejmowało CPU 0–23,
- odczytano wielogodzinny uptime,
- statusy były GOTOWY.

Potwierdzono rzeczywiste operacje:

```text
High → RealTime
RealTime → High
```

Po zapisie plugin ponownie odczytał Windows i raportował `POPRAWIONO I POTWIERDZONO`.

### Reguły CPU

- brak zapisu, gdy stan aktualny zgadza się z celem,
- zapis tylko włączonej właściwości,
- oddzielne włączniki priority i affinity na mapę,
- globalny ON/OFF pluginu,
- warunek GOTOWY,
- karencja po uruchomieniu procesu,
- ustawienia wyłącznie przez GUI,
- zamknięcie panelu nie zmienia stanu pluginu,
- rzeczywisty ponowny odczyt po setterze Windows,
- jawne błędy dostępu/API,
- kontrolka `ADMIN: TAK/NIE` w głównym oknie.

### Trzy zakładki CPU

1. `SERWERY` — odczyt i konfiguracja procesów.
2. `TOPOLOGIA CPU` — model i podstawowe dane fizyczne/logiczne.
3. `TESTER CPU` — ręczny benchmark logicznych CPU i propozycje affinity.

Tester nie zmienia serwerów. Przenosi propozycje jedynie do pól GUI; użytkownik musi je sprawdzić, włączyć affinity i zapisać.

### Nadal niepotwierdzone terenowo

- wiarygodność rankingu benchmarku na komputerze użytkownika,
- poprawność propozycji pod kątem SMT/P-core/E-core,
- wygląd i ergonomia wszystkich trzech zakładek na Windowsie,
- zachowanie długiego testu podczas obciążonych serwerów.

Nie wolno przedstawiać tych punktów jako potwierdzonych tylko dlatego, że testy sandboxa przechodzą.

---

## 9. Importer — wymagania, stan i incydent

Importer jest domyślnie ON, ponieważ przydaje się na początku. Samo ON nie uruchamia skanowania w tle. Po skonfigurowaniu map można go wyłączyć.

Powinien:

- przyjąć główny katalog starego Refreshera,
- rekurencyjnie skanować JSON-y tylko do odczytu,
- znaleźć mapy i rotowane backupy,
- rozbić stare konfiguracje globalne na mapy,
- wybrać najnowszą poprawną wersję,
- wykryć sekrety RCON bez pokazywania hasła,
- wykryć klucz CurseForge API bez pokazywania wartości,
- pozwolić wybrać mapy i API,
- importować dopiero po potwierdzeniu,
- nie zmieniać katalogu źródłowego.

### Incydent Drag & Drop

W V3.79.1 zastosowano ręczne przejęcie Windows `WndProc`. Upuszczenie katalogu zamknęło cały Refresher. Była to poważna wada implementacji.

W V3.79.2 mechanizm został całkowicie usunięty. Test regresji zabrania obecności:

```text
SetWindowLongPtr
WNDPROC
DragAcceptFiles
```

Obecnie bezpiecznym wejściem jest przycisk wyboru całego katalogu. Drag & Drop nie może wrócić przez ręczne podmienianie procedury okna Tk.

### Znany dług techniczny Importera

Plugin nadal korzysta z historycznych metod znajdujących się w klasie głównej aplikacji, między innymi normalizacji i tworzenia importowanego taba. To znaczy, że ręczny interfejs jest pluginem, ale całe stare zaplecze importu nie zostało jeszcze naprawdę wycięte z głównego pliku. Ten punkt musi wejść do diagnozy wstecznej.

---

## 10. Manager Pluginów — stan UI

Manager został przebudowany na gęste kafelki:

- nagłówek i akcje w jednym wierszu,
- opis w drugim,
- STATUS i TEST w trzecim,
- małe marginesy,
- przewijana lista.

Było kilka iteracji, ponieważ wcześniejsze zmniejszanie samych liczb nie usuwało pustej wysokości wymuszanej przez układ. Ostatni zrzut potwierdził znaczną poprawę gęstości.

---

## 11. Testy i ich prawidłowa interpretacja

Ostatnia flota automatyczna raportowała **70/70 PASS**.

Testy obejmują między innymi:

- bezpieczeństwo procedur,
- routing modów do map,
- rozstawienie `DoExit`,
- puste i częściowe linie,
- oczekiwanie na prawdziwy powrót serwera,
- parser CFCore,
- wybór artefaktu serwerowego,
- plugin host i izolację wyjątków,
- CPU no-op i rzeczywiste rozjazdy w symulacji,
- brak pracy CPU w tle przy OFF,
- skan Importera,
- grupowanie backupów,
- wykrywanie API,
- brak modyfikacji źródła,
- wybrane scenariusze użytkownika i administratora.

Testy automatyczne **nie dowodzą**:

- że każdy panel GUI wygląda dobrze na Windowsie,
- że natywne Windows API działa na każdym komputerze,
- że benchmark CPU daje dobrą decyzję operacyjną,
- że RCON zadziała na prawdziwych portach i hasłach,
- że backup/przywracanie zostały już bezpiecznie przećwiczone terenowo,
- że nowe pluginy administracyjne są produkcyjnie dojrzałe.

Po incydencie Drag & Drop liczba PASS nie może być używana jako zamiennik testu terenowego funkcji systemowych.

---

## 12. Nowe pluginy administracyjne — status ostrożności

Backup, diagnostyka, dysk, analizator logów, historia i ręczne RCON zostały dodane szybko w jednej serii. Mają testy ładowania i podstawowych stanów, ale nie przeszły jeszcze pełnego testu użytkownika na Windowsie.

Szczególnej diagnozy wymagają:

- przywracanie ZIP i odporność na kolizje istniejących plików,
- kompletność redakcji sekretów w pakiecie diagnostycznym,
- możliwość zamrożenia GUI przez liczenie rozmiaru dużych katalogów,
- jakość analizy logów i ryzyko fałszywych wniosków,
- rotacja pliku historii,
- walidacja portu i obsługa błędów w ręcznym RCON,
- konsekwencja semantyki ON/OFF,
- zamykanie paneli podczas wyłączania pluginów,
- zachowanie przy zmianie języka i przebudowie GUI.

---

## 13. Elementy, których nie należy przenosić do opcjonalnych pluginów

Podstawowy rdzeń lub obowiązkowe moduły muszą zachować:

- monitorowanie rzeczywistego stanu serwerów,
- kontrolę modów i wersji,
- mapowe procedury RCON,
- bezpieczeństwo `DoExit`,
- oczekiwanie na powrót,
- bieżący zapis tabów i sekretów,
- ręczne dodawanie nowej mapy,
- główną pętlę i kolejki UI,
- minimalny odczyt aktualnej konfiguracji potrzebny do startu.

Rozdzielenie kodu na moduły jest pożądane, ale nie każda część ma być opcjonalnym pluginem.

---

## 14. Znane stare brudy do późniejszej diagnozy wstecznej

Ta lista nie jest jeszcze diagnozą; jest indeksem miejsc, które trzeba zbadać:

1. Główny plik nadal jest duży i zawiera historyczne metody importu.
2. Importer używa bezpośredniego dostępu do aplikacji przez zaufane API.
3. Semantyka plugin OFF była niespójna; CPU poprawiono, pozostałe pluginy trzeba sprawdzić osobno.
4. Nowe pluginy administracyjne dodano szybciej niż wykonano testy terenowe.
5. GUI i logika bywają splecione w tych samych klasach.
6. Nie wszystkie operacje kosztowne są przeniesione poza wątek UI.
7. Obsługa zamykania paneli i wątków wymaga audytu.
8. Dokumentacja wersji narosła w wielu plikach i może zawierać historyczne, nieaktualne stwierdzenia.
9. `show_about` oraz część historii wersji mogą nadal raportować stare numery.
10. Część nazw i tekstów jest wpisana bezpośrednio po polsku zamiast korzystać z tłumaczeń.
11. Trzeba sprawdzić, czy pakiety ZIP nie zawierają starych, sprzecznych dokumentów.
12. Trzeba sprawdzić wszystkie ścieżki sekretów i redakcję danych.
13. Trzeba sprawdzić realne zachowanie po zmianie języka, gdy pluginy i panele są otwarte.
14. Trzeba sprawdzić, czy OFF wszystkich opcjonalnych pluginów naprawdę zatrzymuje ich pracę.
15. Trzeba sprawdzić, czy test pluginu jest zawsze bezpieczny i nie wykonuje właściwej operacji.
16. Trzeba sprawdzić backup/przywracanie pod kątem zip-slip, nadpisania i rollbacku.
17. Trzeba sprawdzić ręczne RCON pod kątem walidacji oraz blokowania GUI.
18. Trzeba sprawdzić historię i analizator logów pod kątem nieograniczonego wzrostu i wydajności.
19. Trzeba sprawdzić CPU Tester pod kątem topologii grup procesorów powyżej 64 logicznych CPU.
20. Trzeba zachować ślad incydentu Drag & Drop i nie przywracać podobnego hooka.

---

## 15. Wdrożony Koordynator procedur klastra / SSD

Obecne taby mieszają lokalny czas procedury z przesunięciem potrzebnym tylko podczas restartu wielu serwerów. Powoduje to, że pojedynczy serwer może niepotrzebnie czekać na slot przygotowany dla całego klastra.

Docelowy podział odpowiedzialności:

1. **Rdzeń Refreshera ustala, które serwery rzeczywiście wymagają procedury.**
2. **Tab mapy przechowuje wyłącznie lokalną procedurę RCON zaczynającą się od czasu zero.**
3. **Konieczny plugin `Koordynator procedur klastra / SSD` otrzymuje listę wymagających map i ich zwalidowane lokalne harmonogramy.**
4. **Plugin ustala kolejność, przesunięcia i aktualnie obsługiwaną mapę.**
5. **Rdzeń nadal wykonuje RCON, sprawdza statusy, blokuje niebezpieczny `DoExit`, obsługuje błędy i obserwuje powrót.**

Plugin koordynujący nie może dodawać do procedury map, które nie zostały wskazane przez rdzeń jako wymagające działania.

Dla jednej wymagającej mapy jej lokalna procedura zaczyna się od razu. Dla kilku map koordynator nie musi używać stałych przesunięć czasowych. Bezpieczniejszy model to **kolejka sterowana rzeczywistym stanem serwerów**.

Koordynator uruchamia lokalną procedurę tylko dla pierwszej wymagającej mapy. Następna mapa nie zaczyna procedury po umownych 200 czy 400 sekundach. Czeka na potwierdzenie pełnego cyklu poprzedniej mapy.

„Procedura mapy zakończona” nie może oznaczać jedynie, że wysłano `DoExit`. Bezpieczne zakończenie obejmuje:

1. wszystkie wymagane lokalne linie RCON wykonane w prawidłowej kolejności,
2. skutecznie wysłany `DoExit`,
3. potwierdzone odejście starego procesu/stanu GOTOWY,
4. ponowny start przez managera,
5. powrót serwera do nowego stanu GOTOWY,
6. wymaganą weryfikację wersji/modów dla tej mapy.

Dopiero wtedy koordynator ponownie sprawdza kolejkę i uruchamia następną mapę, jeżeli nadal rzeczywiście wymaga procedury. Dzięki temu ciężkie starty serwerów nie nakładają się na SSD bez zgadywania czasu restartu ASA Dedicated Managera.

Panel pluginu powinien umożliwiać przez GUI:

- ustawienie kolejności map,
- podgląd listy map rzeczywiście wymagających procedury,
- podgląd `AKTUALNIE`, `CZEKA NA ODEJŚCIE`, `CZEKA NA GOTOWY`, `WERYFIKACJA`, `NASTĘPNA`, `ZAKOŃCZONA`, `POMINIĘTA/BŁĄD`,
- podgląd kolejki przed uruchomieniem,
- test planowania bez wysyłania RCON,
- świadomą decyzję administratora po błędzie lub timeoutcie: ponów, pomiń albo zatrzymaj całą kolejkę.

Gdy monitorowany proces znika, ASADedicatedManager wykonuje trzy kontrole braku procesu (w rzeczywistym logu Genesis co około 15 sekund), potwierdza, że serwera nie ma, i podejmuje jego podniesienie. Refresher nie uruchamia procesu za managera ani nie ściga się z jego monitoringiem. Oznacza mapę flagą `NIE MA / OFFLINE`, obserwuje pojawienie się nowego PID + czasu startu/boot ID i dalej kontroluje stan aż do GOTOWY. Następna mapa nie rusza, dopóki bieżąca nie wróci i nie przejdzie wymaganej weryfikacji.

Domyślnie błąd, brak odejścia, brak powrotu GOTOWY lub nieudana weryfikacja powinny zatrzymać kolejkę. Nie wolno automatycznie przechodzić do następnego serwera, gdy stan poprzedniego jest nieznany.

Plugin powinien być konieczny i bez przełącznika OFF, jeżeli przejmuje odpowiedzialność za ochronę SSD. Awaria koordynatora wielu map musi zatrzymać procedurę. Dla jednej mapy rdzeń może bezpośrednio wykonać jej lokalną procedurę, ale nadal musi przeprowadzić pełną obserwację odejścia, powrotu i weryfikacji.

Migracji starych tabów nie wolno wykonywać przez zgadywanie bez podglądu i potwierdzenia użytkownika, ponieważ obecne czasy mogą zawierać zarówno lokalne ostrzeżenia, jak i ręcznie zbudowane przesunięcie klastrowe.

---

## 16. Reguła dalszej pracy

Przed następnym rozwojem należy wykonać diagnozę wsteczną:

1. porównać deklarowane zachowanie z rzeczywistym kodem,
2. znaleźć stare ścieżki i martwe funkcje,
3. znaleźć niespójne stany ON/OFF,
4. znaleźć operacje blokujące GUI,
5. prześledzić sekrety od odczytu do zapisu i ZIP-ów,
6. prześledzić każdy zapis RCON/Windows/dysku,
7. oddzielić fakty potwierdzone terenowo od testów sandboxa,
8. stworzyć plan napraw według ryzyka, bez dokładania kolejnych funkcji.

Najważniejsze: **najpierw prawda o obecnym programie, potem dalsza rozbudowa.**
