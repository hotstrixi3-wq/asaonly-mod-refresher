# Test administratora serwerów — V3.80.7

## Zakres

Symulacja obserwuje program od strony administratora pięciu już działających serwerów. Każdy serwer ma własny, rozłączny zestaw czterech syntetycznych modów, osobny port RCON i inny ręczny harmonogram. CurseForge publikuje częste losowe serie od 1 do 7 aktualizacji, także podczas trwającej kolejki restartów.

Wykonano 20 deterministycznych seedów po 25 cykli, łącznie 500 cykli administracyjnych.

## Sprawdzane zachowania

- restart otrzymują wyłącznie serwery używające zaktualizowanego moda;
- procedury serwerów nie nakładają się;
- ręczne czasy każdego taba pozostają niezmienione;
- samo STARTING nie jest uznawane za powrót;
- wymagany jest nowy boot, GOTOWY i lokalna wersja;
- nowy update CF podczas kolejki nie miesza się do aktywnego planu;
- po zakończeniu pierwszej kolejki nowy update pozostaje widoczny i dostaje osobną turę po karencji;
- po końcu kolejki edycja tabów wraca, a pending jest pusty dopiero po potwierdzeniu wszystkich wersji;
- serwery bez potrzeby aktualizacji nie otrzymują RCON.

## Znaleziony i naprawiony błąd

Koordynator kończył kolejkę bez odtworzenia starego mechanizmu auto-next dla aktualizacji, która pojawiła się w jej trakcie. Taki update pozostawał pending, ale nie dostawał automatycznie kolejnej tury. V3.80.7 porównuje migawkę `mid/file ID` aktywnej kolejki z aktualnym pending i planuje osobną turę po 60 sekundach dla nowego moda lub nowszego file ID. Nie ponawia starych nieudanych wpisów.

## Wynik

Test stresowy administratora: 500/500 cykli poprawnych. Pełny zestaw automatyczny i symulacyjny: 79 testów.
