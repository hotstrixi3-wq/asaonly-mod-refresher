# PRZYKŁAD: HARMONOGRAM RESTARTÓW KLASTRA („GODZINA ZERO”) — V3.81

> Praktyczny wzór dla admina klastra ARK. Od **V3.81** czasy w tabie są
> **LOKALNE** (sekundy od początku odliczania TEJ mapy), a rozjazd między
> mapami robi **KOLEJKA**. Poprzednia wersja tego dokumentu (≤ 3.80: jeden
> wspólny zegar T0 i czasy „przesunięte o 180 × numer mapy”) jest nieaktualna —
> takie czasy w 3.81 oznaczałyby wielominutowe czekanie przed pierwszym
> komunikatem.

## 1. ZASADA

- **Każda mapa dostaje TEN SAM szablon** ogłoszeń. Nie liczysz przesunięć.
- **Kolejka pilnuje dysku:** od `DoExit` do GOTOWY startuje najwyżej JEDNA
  mapa. O to chodzi w rozjeździe — restarty nie mogą zajechać SSD.
- **Pusta mapa** (`ListPlayers` = nikogo) idzie od razu, bez komunikatów
  i bez czekania. Mapa z graczami (albo gdy nie wiadomo) — pełny szablon.
- **Ogłoszenia „na styk”:** kolejna mapa zaczyna ogłaszać tak, żeby jej
  zegar skończył się, gdy dysk się zwolni. Czas startu program mierzy sam
  (od `DoExit` do GOTOWY, 5 ostatnich pomiarów na mapę, bierze najdłuższy).

## 2. SZABLON (15 minut ostrzeżeń)

| Czas [s] | Komenda | Wł. |
|---|---|---|
| 0 | `ServerChat RESTART SERWERA za 15 minut - aktualizacja modów, zapisz się!` | ✔ |
| 300 | `ServerChat Restart za 10 minut.` | ✔ |
| 600 | `ServerChat Restart za 5 minut.` | ✔ |
| 780 | `ServerChat Restart za 2 minuty.` | ✔ |
| 870 | `ServerChat Restart za 30 sekund - do zobaczenia!` | ✔ |
| 900 | `DoExit` | ✔ |

Wyciąg z zapisu taba (pole `lines`):

```json
"lines": [
  {"time": "0",   "cmd": "ServerChat RESTART SERWERA za 15 minut - aktualizacja modów, zapisz się!", "on": true},
  {"time": "300", "cmd": "ServerChat Restart za 10 minut.", "on": true},
  {"time": "600", "cmd": "ServerChat Restart za 5 minut.", "on": true},
  {"time": "780", "cmd": "ServerChat Restart za 2 minuty.", "on": true},
  {"time": "870", "cmd": "ServerChat Restart za 30 sekund - do zobaczenia!", "on": true},
  {"time": "900", "cmd": "DoExit", "on": true}
]
```

Wskazówki:
- Na pustej mapie komunikaty i czekanie wypadają same; inne komendy
  (np. `SaveWorld` przed `DoExit`) zostają.
- Linie po `DoExit` nie są wysyłane (serwera już nie ma).
- `DoExit` = „zapisz i wyjdź”. Proces stawia z powrotem ASA Dedicated Manager,
  a mody podnosi SAM SERWER przy starcie (CFCore). Program plików gry nie dotyka.

## 3. JAK TO WYGLĄDA W CZASIE (symulacja planisty `asaonly/kolejka.py`)

Klaster 8 map, update moda BAZOWEGO (wszystkie mapy), szablon z punktu 2.
Czasy startu map PRZYJĘTE DO PRZYKŁADU: 105–135 s (to nie są dane z żadnego
prawdziwego klastra — program mierzy je sam na Twojej instalacji).

### A) Pierwsza fala — program nie zna jeszcze żadnych czasów startu

| Mapa | Ogłoszenia od | DoExit | GOTOWY |
|---|---|---|---|
| TheIsland | 0:00 | 15:00 | 16:50 |
| Ragnarok | 16:50 | 31:50 | 33:50 |
| Extinction | 18:40 | 33:50 | 35:55 |
| Aberration | 20:30 | 35:55 | 37:50 |
| Valguero | 22:20 | 37:50 | 39:50 |
| CrystalIsles | 24:10 | 39:50 | 41:55 |
| Fjordur | 26:00 | 41:55 | 44:10 |
| TheCenter | 27:50 | 44:10 | 45:55 |

Koniec fali: **~46 min**. Druga mapa czeka na powrót pierwszej (brak danych);
od tej chwili mapy bez własnego pomiaru biorą pomiar innej mapy i ogłoszenia
się nakładają. Kilka sekund spóźnienia `DoExit` (np. Extinction) = start
poprzedniej mapy trwał dłużej niż przewidywanie; dysk i tak nigdy nie dostaje
dwóch startów naraz.

### B) Kolejne fale — czasy startu już zmierzone

| Mapa | Ogłoszenia od | DoExit | GOTOWY |
|---|---|---|---|
| TheIsland | 0:00 | 15:00 | 16:50 |
| Ragnarok | 1:50 | 16:50 | 18:50 |
| Extinction | 3:50 | 18:50 | 20:55 |
| Aberration | 5:55 | 20:55 | 22:50 |
| Valguero | 7:50 | 22:50 | 24:50 |
| CrystalIsles | 9:50 | 24:50 | 26:55 |
| Fjordur | 11:55 | 26:55 | 29:10 |
| TheCenter | 14:10 | 29:10 | 30:55 |

Koniec fali: **~31 min**. Każda mapa jest niedostępna tylko przez swój start.

### C) Kolejna fala, Ragnarok i Valguero puste

| Mapa | Ogłoszenia od | DoExit | GOTOWY |
|---|---|---|---|
| Ragnarok (pusta) | — | 0:00 | 2:00 |
| Valguero (pusta) | — | 2:00 | 4:00 |
| TheIsland | 0:00 | 15:00 | 16:50 |
| Extinction | 1:50 | 16:50 | 18:55 |
| Aberration | 3:55 | 18:55 | 20:50 |
| CrystalIsles | 5:50 | 20:50 | 22:55 |
| Fjordur | 7:55 | 22:55 | 25:10 |
| TheCenter | 10:10 | 25:10 | 26:55 |

Puste mapy przeszły, zanim pierwsza mapa z graczami skończyła ogłoszenia.

Chcesz szybszej pierwszej fali? Podaj czasy startu z góry: klucz
`czasy_startu` w `CONFIG_PROGRAM` (przy zamkniętym programie), np.
`"czasy_startu": {"Fjordur": [135], "TheIsland": [110]}`.

## 4. CO JESZCZE ROBI PROGRAM

- **Przed procedurą** zapisuje stan modów do dziennika
  (`WIEDZA_O_PROGRAMIE/dziennik-modow.txt`, rotacja 15×10 KB).
- **Przed ogłoszeniami i przed `DoExit` pustej mapy** pyta o graczy jeszcze raz
  (odpowiedź młodsza niż 30 s wystarcza). Ktoś wszedł na pustą mapę = pełny
  szablon od tej chwili.
- **Strażnik stanów:** mapa w crashu/offline wypada z kolejki (mody i tak
  podniesie przy starcie); `DoExit` nie pójdzie na mapę, która nie jest GOTOWA.
- **Mapy nieużywające update'owanego moda są pomijane.**
- **Czuwanie:** po `DoExit` program czeka na nowy start i GOTOWY, sprawdza
  w logu serwera, czy wstał z nową wersją, i dopiero wtedy zwalnia dysk.
  Mapa, która nie wróciła w czasie czuwania, jest oznaczona jako nieudana —
  kolejka idzie dalej.
- **Mapa, która wstała sama** (manager, krach) z nową wersją, wypada z kolejki
  bez drugiego restartu.

## 5. KIEDY HARMONOGRAM NIE RUSZY

- **Automat RCON wyłączony** — update czeka w zaległościach na przycisk.
- Mapa **nie używa** update'owanego moda — pomijana.
- Mapa **bez `DoExit`** w harmonogramie, z błędnym harmonogramem albo
  z portem RCON współdzielonym z inną mapą — pomijana pojedynczo, reszta idzie.
- Procedura/czuwanie **już trwa** — nowy update czeka na kolejną turę.
