# V3.77.7 — synchronizacja startu CPU z monitorem

Plugin CPU nie interpretuje już braku pierwszego snapshotu monitora jako braku procesów. Przed otrzymaniem pierwszego zakończonego skanu nie tworzy wpisów `PID=brak`; wskaźnik pokazuje oczekiwanie na monitor. Po otrzymaniu snapshotu nawet pusta mapa PID jest autorytatywna i wtedy `Brak procesu` jest prawdziwym wynikiem.

Rozwiązanie jest synchronizacją zdarzeń, nie arbitralnym opóźnieniem czasowym.

Testy automatyczne: 48/48 PASS.
