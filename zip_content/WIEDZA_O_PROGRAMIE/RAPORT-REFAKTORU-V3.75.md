# RAPORT REFAKTORU V3.75-safety

Data: 2026-09-20

## Wynik

Monolit został zmniejszony z **4530 do 1883 linii**. Nowa logika nie została tylko poprzenoszona: najgroźniejsze błędy procedury naprawiono przed cięciem.

## Klocki

| Klocek | Linie | Odpowiedzialność |
|---|---:|---|
| `asaonly/tr.py` | 549 | czyste dane PL/EN |
| `asaonly/widgety.py` | 307 | widgety prezentacyjne |
| `asaonly/siec.py` | 179 | RCON i HTTP CurseForge |
| `asaonly/zapis.py` | 125 | atomowy, wersjonowany zapis i migracje |
| `asaonly/logtail.py` | 326 | współdzielony odczyt logu, rotacja, status |
| `asaonly/monitor.py` | 71 | czyste parsery i klasyfikatory monitora |
| `asaonly/monitor_plugin.py` | 208 | zadanie 1: procesy, porty, WISI, sondy |
| `asaonly/cf_wersje.py` | 272 | zadanie 2a: CurseForge i wykrywanie update |
| `asaonly/serwer_wersje.py` | 73 | zadanie 2b: CFCore, library.json |
| `asaonly/procedura.py` | 349 | zadanie 3: RCON, guardy, watch i wyniki per mapa |
| `asaonly/server_tab.py` | 631 | model/UI jednej mapy i kolejka RCON |
| `asaonly/pluginy.py` | 168 | host, API=1, izolacja błędów, event bus |
| `PLUGINY/60_cpu.py` | 98 | opcjonalny priority/affinity po 30 s |

`server_tab.py` przekracza pierwotny cel 485 linii, ponieważ nadal łączy model taba z jego UI. To kolejny kandydat do podziału na `mapa_model.py` i `mapa_panel.py`; nie wykonano tego mechanicznie bez testów Tk.

## Host pluginów

- ładowanie alfabetyczne z `PLUGINY/`,
- wymuszenie `API == 1`,
- plugin dostaje ograniczony `CoreAPI`, nie obiekt `App`,
- snapshot tabów jest niemutowalny i nie wypuszcza zmiennych Tk,
- każde `start/tik/hook/event/stop` ma izolację wyjątków,
- identyczny błąd tika jest ograniczony do jednego wpisu na 60 s,
- dostępna szyna zdarzeń,
- konfiguracja pluginu trafia do `config["plugins"]`.

## CPU

Plugin jest domyślnie wyłączony. Przykładowa konfiguracja:

```json
"plugins": {
  "cpu": {
    "enabled": true,
    "delay_s": 30,
    "priority": "high",
    "affinity_mask": 0
  }
}
```

Minimalne opóźnienie jest wymuszone na 26 sekund, aby nie przegrać z managerem nakładającym priorytet około 25 s po starcie. `affinity_mask: 0` oznacza brak zmiany affinity. Brak uprawnień administratora jest raportowany.

## Naprawy bezpieczeństwa

1. Puste zaznaczone linie RCON są no-op.
2. Błąd jednej mapy nie blokuje pozostałych.
3. Duplikaty portów RCON blokują automat.
4. Pending jest kluczowany `mod_id` i weryfikowany per mapa.
5. Koniec zegara nie oznacza sukcesu i nie usuwa pendingu.
6. Błąd/pominięcie/zablokowanie `DoExit` nie jest sukcesem.
7. Watch obejmuje tylko mapy z pomyślnym `DoExit`.
8. GOTOWY liczy się dopiero po opuszczeniu poprzedniego GOTOWY.
9. Ta sama odłożona tura nie jest automatycznie młócona co 60 s.
10. Artefakt CF jest wybierany po `windowsserver`, bez reguły `+3`.
11. Parser rozpoznaje rzeczywiste zdarzenia CFCore.
12. Czytany jest `ModsUserData/83374/library.json`; katalog jest fallbackiem.
13. Usunięto klastrowe godzenie na podstawie jednego zaktualizowanego dysku/mapy.

## Weryfikacja

- `python -m py_compile ...` — PASS,
- `python -m unittest discover -s tests -v` — **23/23 PASS**, w tym pełny dostarczony `library.json` z 9 modami,
- `git diff --check` — PASS.

## Granice obecnego wyniku

1. Nie odnaleziono dawnego katalogu `symulacja/`; powstała nowa, mniejsza flota regresyjna.
2. Nie wykonano prawdziwego testu GUI na Windows z aktywnymi serwerami.
3. Nie potwierdzono zachowania ASA przy awarii CF/DNS.
4. Manager nadal ma niezależny harmonogram; brak adaptera jego konfiguracji.
5. Monitor procesu nadal zaczyna identyfikację od portu RCON, choć duplikaty są już blokowane.
6. Rzeczywisty `library.json` został dostarczony i ujawnił nietypowe klucze `iD`; parser został poprawiony i potwierdzony na wszystkich 9 wpisach. Nadal warto zebrać plik z trwającym lub nieudanym pobieraniem.
7. Moduły zadaniowe są obecnie mixinami hosta; CPU jest pierwszym prawdziwie dynamicznym pluginem. Przeniesienie monitor/CF/procedury do dynamicznych pluginów wymaga najpierw pełnego modelu zdarzeń i testów integracyjnych Tk.

## Następny bezpieczny etap

- fixture rzeczywistych logów i `library.json`,
- test automatu całej procedury z fałszywym zegarem i RCON,
- rozdzielenie `ServerTab` na model i panel,
- identyfikacja PID przez port + nazwę procesu + command line,
- blackout window harmonogramu managera,
- dynamiczny semafor SSD oparty o fazy CFCore.
