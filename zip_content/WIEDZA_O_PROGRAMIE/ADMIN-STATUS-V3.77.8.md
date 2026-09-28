# V3.77.8 — kontrolka administratora

Przy starcie Windows program wywołuje `shell32.IsUserAnAdmin()`. Główne okno stale pokazuje zielone `ADMIN: TAK` albo czerwone `ADMIN: NIE`; wynik jest również logowany. Brak administratora nie blokuje funkcji odczytowych ani nie zamyka aplikacji, ale ostrzega, że Windows może odrzucić ustawianie priority/affinity.

Plugin API udostępnia `is_admin()`. Test CPU raportuje stan administratora i pozostaje testem bez zapisu.

Na systemie innym niż Windows kontrolka pokazuje `ADMIN: N/D`.

Testy automatyczne: 49/49 PASS.
