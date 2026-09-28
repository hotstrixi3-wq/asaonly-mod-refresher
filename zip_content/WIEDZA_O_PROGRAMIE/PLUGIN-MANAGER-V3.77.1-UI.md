# V3.77.1 — poprawiony interfejs Managera Pluginów

Manager Pluginów jest częścią stałej infrastruktury PluginHost, nie pluginem. Musi istnieć przed załadowaniem pluginów i dlatego nie występuje na zarządzanej liście.

Poprzedni tabelaryczny układ oparty na stałych szerokościach został zastąpiony responsywnymi kaflami. Każdy kafel ma osobne: nazwę i wersję, oznaczenie typu, pełny status, pełny zawijany wynik testu oraz prawą sekcję operacji. Lista jest przewijana i wykorzystuje szerokość okna. Plugin konieczny pokazuje `ZAWSZE AKTYWNY`; opcjonalny pokazuje `WŁĄCZONY/WYŁĄCZONY`.

Testy automatyczne: 45/45 PASS.
