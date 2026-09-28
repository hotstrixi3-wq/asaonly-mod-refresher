# CPU PRIORITY / AFFINITY — V3.76

## Obsługa

W głównym oknie znajdują się:

- przycisk **CPU** otwierający panel,
- checkbox **CPU ON/OFF** sterujący ingerencją,
- skrócony status globalny.

Panel **Wykryj aktywne serwery** pokazuje dla każdej aktywnej mapy:

- stan mapy,
- PID i rzeczywisty uptime procesu,
- aktualny priority odczytany z Windows,
- aktualną maskę affinity odczytaną z Windows,
- osobny checkbox i cel priority,
- osobny checkbox i cel affinity,
- jednoznaczny wynik porównania,
- przycisk **Zapisz ustawienia**.

## Zasady bezpieczeństwa

1. Brak zapisanych ustawień oznacza wyłącznie obserwację.
2. Wyłączony checkbox właściwości oznacza, że plugin jej nie dotyka.
3. Globalny CPU OFF pokazuje stan i rozjazdy, ale niczego nie zmienia.
4. Zmiany są możliwe dopiero, gdy mapa jest GOTOWA.
5. Proces musi mieć minimum 30 s uptime (minimum kodowe 26 s), aby manager zdążył nałożyć własne ustawienia.
6. Najpierw odczyt, później porównanie; zgodna wartość nie wywołuje Windows API zapisu.
7. Przy rozjeździe zmieniana jest tylko zaznaczona i różniąca się właściwość.
8. Po restarcie nowy PID jest ponownie odczytywany i porównywany.
9. Panel kontroluje stan co 5 s, ale nie zapisuje cyklicznie zgodnych ustawień.
10. Zapis z GUI jest natychmiast trwały — użytkownik nie edytuje JSON-a.

## Statusy

- Brak procesu
- Odczytano aktualny stan
- Serwer STARTING/LOADING — bez ingerencji
- GOTOWY — czekam na managera
- TYLKO ODCZYT
- ZGODNE — bez ingerencji
- ROZJAZD (plugin OFF)
- POPRAWIONO
- Błąd odczytu / brak praw administratora

## Affinity — pozycje menu

- Wszystkie
- Pierwsza połowa
- Druga połowa
- Parzyste
- Nieparzyste
- pojedynczy CPU 0..N

## Testy

Cała flota: **42/42 PASS**. Dodatkowe testy potwierdzają:

- brak zapisu przy zgodnym stanie,
- zmianę tylko priority, gdy affinity jest wyłączone,
- pokazanie rozjazdu bez ingerencji przy globalnym CPU OFF.
