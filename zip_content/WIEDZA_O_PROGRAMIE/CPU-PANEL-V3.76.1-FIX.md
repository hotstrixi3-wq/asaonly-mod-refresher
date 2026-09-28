# CPU PANEL V3.76.1 — poprawka testu Windows

Zrzut produkcyjny wykazał, że odczyt High działał poprawnie, ale zapis nie był wykonywany, ponieważ globalny plugin pozostawał OFF. Panel pokazywał to tekstem `ROZJAZD (plugin OFF)`, lecz przełącznik globalny znajdował się wyłącznie w głównym oknie. Przycisk `Zapisz ustawienia` zapisywał cel, ale nie oznaczał włączenia wykonawcy.

## Zmiany

1. Duży `PLUGIN CPU GLOBAL ON/OFF` znajduje się również w panelu CPU.
2. Przełączniki panelu i głównego okna są synchronizowane.
3. Zapis przy globalnym OFF pokazuje wyraźne ostrzeżenie, że proces nie zostanie zmieniony.
4. Zapis przy globalnym ON natychmiast odczytuje i stosuje wyłącznie rozjazd.
5. Po `SetPriorityClass`/`SetProcessAffinityMask` plugin ponownie odczytuje Windows; nie ufa samemu kodowi powodzenia API.
6. Wynik rozróżnia `POPRAWIONO I POTWIERDZONO` od `ZAPIS WINDOWS NIE UTRZYMAŁ SIĘ`.
7. Przycisk nazywa się `Wykryj / odczytaj ponownie` i zawsze wykonuje świeży odczyt.
8. Log zawiera PID, stan serwera, aktualny priority/affinity, cel oraz decyzję.
9. Zapis ustawień z GUI jest natychmiast zapisywany na dysk.
10. Uchwyty WinAPI i maski affinity mają jawne typy 64-bitowe.

Cała flota: 42/42 PASS. Konieczny jest ponowny test na Windows, bo sandbox nie udostępnia Windows API.
