# V3.77.4 — opis celu i decyzji ON/OFF

Plugin przemianowano na `Status dla zewnętrznych narzędzi (status.json)`. Opis odpowiada teraz na: po co istnieje, kto czyta plik, których funkcji programu nie dotyczy oraz kiedy należy go włączyć.

Główny program nie czyta status.json. Plugin jest potrzebny tylko zewnętrznym skryptom, integracjom lub do przekazania snapshotu diagnostycznego. Jeśli użytkownik nie ma takiego odbiorcy, pozostawia OFF. Domyślny stan nowych konfiguracji zmieniono z ON na OFF. Jawnie zapisana wcześniejsza decyzja użytkownika pozostaje zachowana.

Testy automatyczne: 46/46 PASS.
