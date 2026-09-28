# SYMULACJA V3.75 — 3 SERWERY, 5 OSTRZEŻEŃ, ROZJAZD 200 S

Data: 2026-09-20

## Harmonogram

| Serwer | Ostrzeżenia | DoExit |
|---|---|---:|
| Extinction | T+0, 60, 120, 180, 240 | T+300 |
| Genesis 1 | T+200, 260, 320, 380, 440 | T+500 |
| Ragnarok | T+400, 460, 520, 580, 640 | T+700 |

Każda mapa dostaje dokładnie pięć `ServerChat`: 5, 4, 3, 2 i 1 minutę przed własnym `DoExit`. Kolejne `DoExit` są oddalone dokładnie o 200 sekund.

## Zestawy modów

Zestawy utworzono z wszystkich 9 wpisów dostarczonego `library.json`:

- **Extinction (3):** 928548, 940975, 941450
- **Genesis 1 (4):** 928548, 929684, 933099, 974884
- **Ragnarok (4):** 931874, 929420, 929785, 941450

Każdy zestaw jest inny. Mod 928548 sprawdza aktualizację wspólną Extinction/Genesis, 941450 wspólną Extinction/Ragnarok, a 940975 aktualizację wyłącznie Extinction.

## Nowe testy — 8/8 PASS

1. Fixture wykorzystuje wszystkie 9 prawdziwych modów.
2. Każdy serwer ma inny zestaw.
3. Każdy ma pięć ostrzeżeń rozpoczynających się 300 s przed restartem.
4. `DoExit` wypada T+300/T+500/T+700.
5. Pełna oś wysyła 18 komend: 15 ostrzeżeń i 3 `DoExit`.
6. Mod unikalny restartuje tylko Extinction.
7. Mod wspólny 928548 restartuje tylko Extinction i Genesis.
8. Mod wspólny 941450 restartuje tylko Extinction i Ragnarok.

## Cała flota

```bash
python symulacja/run_all.py
```

**39/39 PASS**.

Fixture’y:

- `symulacja/fixtures/library_9_compact.json`
- `symulacja/fixtures/cluster_3_servers.json`

Test integracyjny:

- `symulacja/test_three_server_cluster.py`
