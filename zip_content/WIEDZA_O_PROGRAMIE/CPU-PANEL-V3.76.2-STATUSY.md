# CPU PANEL V3.76.2 — prawdziwe statusy

Poprzedni tekst `ZGODNE — bez ingerencji` był nieprecyzyjny: oznaczał brak zapisu w bieżącym cyklu, ale po wcześniejszej zmianie wykonanej przez plugin sugerował, że plugin nigdy nie ingerował.

Nowe statusy rozróżniają:

- `GLOBAL OFF — aktualny stan odpowiada zapisanemu celowi; plugin go nie egzekwuje`,
- `ZGODNE — stan zastany na tym PID; plugin nie wykonywał zmiany`,
- `ZGODNE — ostatnia zmiana tego PID wykonana przez plugin o HH:MM:SS (priority/affinity)`,
- `POPRAWIONO I POTWIERDZONO`,
- `ZAPIS WINDOWS NIE UTRZYMAŁ SIĘ`.

Pochodzenie zmiany jest pamiętane per mapa i dokładny PID. Po zmianie PID historia nie jest przypisywana nowemu procesowi.

Flota: 43/43 PASS.
