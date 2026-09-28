# V3.77.3 — opisy przeznaczenia pluginów

Diagnostyczny `status_json` jest prawdziwym, opcjonalnym pluginem i pozostaje w Managerze Pluginów. Wcześniejsze ukrycie było błędną interpretacją pytania użytkownika i zostało cofnięte.

Każdy plugin deklaruje teraz `manager_description`. Opis jest wyświetlany bezpośrednio w kaflu, dzięki czemu nazwa techniczna nie wymaga zgadywania. `status_json` wyjaśnia miejsce zapisu, zakres danych, interwał oraz brak haseł i kluczy API.

Testy automatyczne: 46/46 PASS.
