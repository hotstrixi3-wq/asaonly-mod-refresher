# Zasady ciągłej pracy podczas bieżącego audytu

Do zakończenia bieżącego audytu nie wolno traktować poniższych zdarzeń jako powodu do przerwania pracy:

1. przejście pojedynczego zestawu testów;
2. wzrost liczby testów;
3. przejście `compileall`;
4. utworzenie commitu;
5. utworzenie archiwum ZIP;
6. naprawienie jednego znalezionego błędu;
7. zakończenie jednego podsystemu lub jednego pliku;
8. przygotowanie raportu albo podsumowania;
9. brak natychmiast widocznego błędu w kolejnym wyszukiwaniu;
10. chęć przedstawienia użytkownikowi postępu;
11. poprzednia deklaracja numeru wersji;
12. potrzeba uzasadniania wcześniejszych pomyłek.

Kolejność pracy:

- prześledzić trzy główne obowiązki programu;
- sprawdzić granice odpowiedzialności modułów;
- prześledzić start, działanie, zmianę konfiguracji, restart GUI i zamknięcie;
- sprawdzić błędy, przerwania, współbieżność i trwałość danych;
- dopisać test reprodukujący każdy potwierdzony problem;
- naprawić problem;
- ponowić testy źródła i paczki dopiero po zakończeniu audytu;
- nie ogłaszać ukończenia na podstawie samych testów.
