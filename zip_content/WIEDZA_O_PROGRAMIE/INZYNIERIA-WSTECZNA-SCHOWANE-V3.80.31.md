# Inżynieria wsteczna: co było schowane zamiast naprawione

Stan po analizie V3.80.31 i zrzutu użytkownika z 07:42:41.

## 1. POTWIERDZONE: zapis OFF mógł nie być najnowszym odczytanym zapisem

`save_versioned()` tworzy przy kilku zapisach w tej samej sekundzie pliki:

- `... 07-42-40.json`
- `... 07-42-40 (2).json`
- `... 07-42-40 (3).json`

Jednak `_ts_key()` ignorował `(2)`, `(3)` itd. Wszystkie rewizje miały identyczny klucz czasu. `newest_matching()` mógł więc ponownie otworzyć wcześniejszy plik z `enabled: true`, mimo że późniejszy plik zawierał `enabled: false`.

Skutek dokładnie odpowiada zrzutowi: po restarcie program uznawał Importer, Backup, Diagnostykę ZIP i Dysk za ON i uruchamiał ich diagnostykę. Filtry diagnostyki działały na źle wczytanym stanie.

V3.80.22–V3.80.31 naprawiały zachowanie hosta po otrzymaniu OFF, ale nie naprawiały selektora, który czasami nie dostarczał hostowi najnowszego OFF. To była naprawa niższej warstwy pominięta przez wcześniejsze testy.

Naprawa: numer rewizji jest częścią klucza sortowania. Dodano regresję `ON` → `OFF` w tej samej sekundzie → reopen, która wymaga wczytania OFF.

## 2. POTWIERDZONE: test reopen pluginów nie używał prawdziwego wersjonowanego odczytu konfiguracji

Dotychczasowy test wpisywał `app.config_data` bezpośrednio do pamięci. Omijał `save_versioned()`, `newest_matching()` i `_load_config()`. Dlatego potwierdzał host pluginów, ale nie pełny przepływ dysk → wybór najnowszej rewizji → host → diagnostyka.

Nowa regresja obejmuje brakujące ogniwo wyboru rewizji, ale nadal nie jest testem pełnego GUI Windows.

## 3. OTWARTE: RCON `stop()` może ogłosić zatrzymanie przed końcem komendy w locie

`stop()` czyści `inflight`, kolejki i słowniki workerów bez oczekiwania na zakończenie aktywnego `rcon_send()`. Stary worker może zakończyć się później. Po zmianie języka/start-stop pluginu może już istnieć nowa kolejka tej samej mapy.

Ryzyko: chwilowo dwa pokolenia transportu, spóźniony callback i fałszywy stan idle. Wymagane jest `quiesce`, odmowa nowych zadań, oczekiwanie/join z limitem oraz identyfikator generacji całego lifecycle.

## 4. OTWARTE: zmiana nazwy mapy nie blokuje aktywnego ręcznego RCON/sondy

`rename_server()` blokuje procedurę i watch, ale `prepare_tab_rename()` sprawdza przede wszystkim niezapisany edytor. Nie ma twardej bariery `is_idle(old_name)` przed zmianą tożsamości mapy.

Ryzyko: komenda pod starą nazwą kończy się po zmianie nazwy; callback i kolejka odnoszą się do starej tożsamości.

## 5. OTWARTE: wieloplikowy zapis RCON nadal nie ma trwałego journalu

Rollback działa tylko, gdy proces nadal żyje. `TemporaryDirectory` znika po zakończeniu procesu. Zabicie programu między zapisami pozostawia częściowy stan bez automatycznego odzyskania.

## 6. OTWARTE: zmiana nazwy mapy nadal nie ma trwałego journalu

Analogicznie: kopie istnieją tylko podczas działania operacji. Brak prądu lub zabicie procesu może przerwać zmianę bez procedury recovery przy następnym starcie.

## 7. OTWARTE: checkpoint procedury nie obsługuje wyjątku samego enqueue po udanym `command_armed`

Po trwałym zapisie `command_armed` `_rcon_enqueue()` może zgłosić wyjątek, np. gdy plugin jest zatrzymywany. Obecnie wyjątek może wyjść do pętli UI, a element harmonogramu pozostać `inflight`. Dyskowy checkpoint pozostaje bezpiecznie niejednoznaczny, ale bieżąca sesja nie przechodzi kontrolowanie do pauzy.

## 8. OTWARTE: uszkodzony typ `procedure_run` może zepsuć start

Kod zakłada, że zapisany `procedure_run` jest słownikiem i wywołuje `.get()`. Ręcznie uszkodzony lub częściowo zapisany stary format może spowodować wyjątek podczas komunikatu startowego. Potrzebna jest walidacja schematu i kwarantanna niepoprawnego rekordu.

## 9. OTWARTE: `prepare()` nie jest sandboxem

Host nie wywołuje `start()` dla OFF, ale dostarczony lub zewnętrzny plugin może wykonać pracę w `prepare()`. Dla pluginów produkcyjnych trzeba utrzymywać test braku workerów/plików; wobec dowolnego kodu zewnętrznego nie wolno obiecywać izolacji.

## 10. OTWARTE: szerokie wyjątki nadal mogą ukrywać błędy

Największa koncentracja pozostaje w `logtail.py`, `widgety.py`, głównej aplikacji i operacjach pomocniczych. Nie każdy `pass` jest błędem, ale brak klasyfikacji nadal utrudnia odróżnienie bezpiecznego sprzątania od utraty dowodu operacyjnego.

## 11. OTWARTE: scalenie i migracja pluginów nie są zakończone

Backup/Restore oraz Status/Historia są scalone. Brak kompletnej macierzy starych nazw, stanów ON/OFF i pozostałych kandydatów do wspólnego panelu.

## 12. OTWARTE: brak realnej walidacji Windows/Tk/ASA/RCON/Manager

Automatyczne testy nie potwierdzają zachowania prawdziwego klastra, ASADedicatedManager Olrik-WP ani realnego restartu po `DoExit`.

## Bilans

- Nowa potwierdzona przyczyna zrzutu: błędny wybór rewizji zapisanej w tej samej sekundzie.
- Naprawiona w kodzie: sortowanie po numerze rewizji i regresja ON→OFF→reopen.
- Nadal otwarte: 10 punktów od lifecycle RCON do journalu, walidacji schematu, wyjątków, pluginów i realnej integracji.
