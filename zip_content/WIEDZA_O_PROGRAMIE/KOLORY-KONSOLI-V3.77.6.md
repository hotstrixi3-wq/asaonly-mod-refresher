# V3.77.6 — semantyczne kolory konsoli

Kolory opisują znaczenie wpisu: zielony = zgodność/ON/test OK; cyan = odczyt; jasny pogrubiony cyan = zmiana procesu; żółty = oczekiwanie/karencja; szary = OFF/tylko odczyt; fioletowy = zapis konfiguracji; niebieski = diagnostyka; czerwony = błąd lub rozjazd.

Plugin API `log(message, tag=None)` obsługuje tag semantyczny. ANSI jest dodawane wyłącznie podczas drukowania na interaktywnej konsoli. Bufor, logi tekstowe i komunikaty przekazywane do testów pozostają bez kodów sterujących.

Testy automatyczne: 47/47 PASS.
