# RAPORT PRAC — V3.75-safety

Data: 2026-09-20

## Zrealizowane zabezpieczenia

1. Puste zaznaczone linie RCON są pomijane; częściowo wypełnione nadal są błędem.
2. Błędna mapa jest odkładana, a poprawne mapy mogą kontynuować procedurę.
3. Duplikaty aktywnych portów RCON blokują automat z czytelnym komunikatem.
4. Zaległości są kluczowane `mod_id`, zawierają mapy docelowe i weryfikację per mapa.
5. Koniec osi czasu nie podnosi już `known_versions` i nie kasuje zaległości.
6. Wynik każdego RCON wraca do automatu; błąd, guard i pominięcie nie są sukcesem.
7. Watch obejmuje tylko mapy z pomyślnie wysłanym `DoExit`.
8. Stan GOTOWY jest sukcesem dopiero po zaobserwowaniu opuszczenia poprzedniego GOTOWY.
9. Automatyka nie ponawia co 60 s tej samej nieudanej/odłożonej tury.
10. Globalny skrót „jeden dysk ma nową wersję, więc cały klaster uzgodniony” został usunięty.
11. Publiczny plik CF jest wybierany semantycznie jako `windowsserver`; nie istnieje reguła `+3`.
12. Dodano parser prawdziwych komunikatów CFCore: upgrade, request, download, install success, loaded mods.
13. Dodano odczyt `ModsUserData/83374/library.json`, z katalogiem jako fallbackiem.
14. Detektor pobierania dostaje każde istotne zdarzenie, a nie tylko ostatnią linię paczki logu.
15. Poprawiono dokumentację błędnie przypisującą pobieranie modów managerowi.

## Pierwsze rozbicie

- `asaonly/tr.py` — czyste tłumaczenia PL/EN (549 linii),
- `asaonly/siec.py` — RCON i HTTP CurseForge (179 linii),
- `asaonly/serwer_wersje.py` — parser logu CFCore i `library.json` (73 linie),
- `asaonly/widgety.py` — widgety prezentacyjne bez stanu klastra (307 linii).

Plik główny zmniejszył się z 4530 do 3677 linii mimo dodania nowej logiki bezpieczeństwa.

## Testy

`python -m unittest discover -s tests -v`

15 testów: walidacja RCON, porty, pending per mod/mapa, brak fałszywego sukcesu, cykl watch, wybór artefaktu windowsserver, parser CFCore i library.json.

## Nadal otwarte

- fixture'y z pełnych rzeczywistych logów i prawdziwego `library.json`,
- zachowanie serwera przy niedostępnym CF/DNS,
- koordynacja harmonogramu managera,
- silniejsza tożsamość procesu niż sam port,
- pełna ekstrakcja monitora i procedury do pluginów,
- plugin CPU po stabilnej identyfikacji PID,
- dynamiczny semafor ochrony SSD.
