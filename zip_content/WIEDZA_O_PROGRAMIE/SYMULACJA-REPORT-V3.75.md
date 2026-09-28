# RAPORT SYMULACJI — V3.75-safety

Data: 2026-09-20

Uruchomienie:

```bash
python symulacja/run_all.py
```

## Wynik

**31/31 PASS** — 23 testy modułów i bezpieczeństwa oraz 8 scenariuszy integracyjnych klastra.

## Scenariusze klastra

| # | Scenariusz | Wynik |
|---:|---|---|
| 1 | wspólny mod restartuje obie mapy w rozjeździe 5/205 s | PASS |
| 2 | błąd RCON jednej mapy nie blokuje drugiej i nie kasuje pendingu | PASS |
| 3 | `DoExit` mapy w STARTING jest porzucony bez pętli retry | PASS |
| 4 | pusty wiersz jest no-op, błędna druga mapa nie blokuje pierwszej | PASS |
| 5 | duplikat portu RCON blokuje automat przed komendami | PASS |
| 6 | samo GOTOWY bez opuszczenia GOTOWY nie jest powrotem | PASS |
| 7 | mod jednej mapy nie restartuje mapy, która go nie używa | PASS |
| 8 | harmonogram bez `DoExit` nie otwiera watch i nie kasuje pendingu | PASS |

## Rzeczywisty `library.json`

Pełny załączony plik ma 9 wpisów. Parser potwierdził pary `mod_id → installedFile.iD`, status `Normal` i pliki `-windowsserver`. Wykryta i naprawiona została nietypowa pisownia klucza `iD`.

## Pluginy do oceny

1. `10_guard_konfiguracji.py` — read-only, aktywny domyślnie; wykrywa złe/zdublowane porty, brak logu i współdzielony folder logu.
2. `40_audyt_wersji.py` — read-only; wykrywa sprzeczne pendingi i nieprawidłowe pary wersji.
3. `60_cpu.py` — domyślnie wyłączony; priority/affinity po minimum 26 s.
4. `70_status_json.py` — aktywny domyślnie; co 30 s zapisuje zanonimizowany `WIEDZA_O_PROGRAMIE/status.json`, bez haseł i kluczy.

Wszystkie cztery pluginy zostały załadowane przez prawdziwy host w teście dymnym.

## Czego symulator jeszcze nie dowodzi

- zachowania prawdziwego Source RCON przy utracie pakietu,
- współpracy z Tk na Windows,
- zachowania ASA przy niedostępnym CurseForge,
- reakcji managera i realnych czasów startu,
- obciążenia SSD.
