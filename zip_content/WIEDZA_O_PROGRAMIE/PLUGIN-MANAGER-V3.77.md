# V3.77 — Manager Pluginów

## Główne okno

Główny interfejs ma jeden stały przycisk `MANAGER PLUGINÓW`. Dedykowane kontrolki CPU zostały usunięte z głównego klocka.

## Deklaracja pluginu

Plugin sam deklaruje `manager_visible`, `manager_name`, `version` i `required`. Nowy plugin nie wymaga dodawania własnych przycisków ani warunków do głównego programu.

## Typy

- konieczny: status, test i opcjonalny panel; brak ON/OFF,
- opcjonalny: status, test, ON/OFF i opcjonalny panel.

Aktualnie: Guard konfiguracji i Audyt wersji modów są konieczne; CPU oraz diagnostyczny eksport status.json są opcjonalne. Każdy plugin wyświetla opis swojego przeznaczenia.

## Testy

Manager testuje import/API/nazwę/start oraz opcjonalny `self_test()`. Test CPU jest tylko do odczytu: sprawdza Windows API i odczyt aktywnych PID, nigdy nie wywołuje setterów. Test status.json sprawdza katalog bez nadpisania pliku. Wynik trafia do GUI i konsoli.

## Bezpieczeństwo działania

Wyjątki jednego pluginu pozostają izolowane i zapisywane w `PLUGINY/plugin-errors.log`. Nie dodano sandboxa ani ochrony przed własnymi pluginami użytkownika.

Testy automatyczne: 45/45 PASS.
