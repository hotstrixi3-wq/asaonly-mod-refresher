# MAPA PROGRAMU — ASAonly - (AUTO)Manual - ModRefresher (RCON)

> Mapa kodu dla praktyków: co gdzie mieszka, kto kogo woła, jak płyną
> dane. Uzupełnia MANUAL (jak obsługiwać) od strony "jak to jest
> zbudowane". Wersja mapy: 3.72, sekcja 5 (procedura) zaktualizowana
> w 3.81 i 3.85 · stdlib-only, tkinter. Od 3.75 program to plik .py + pakiet
> `asaonly/` + `PLUGINY/` — numery linii i część nazw niżej są historyczne.

---

## 0. JEDNO PODEJŚCIE DO CZYTANIA

Program = **warstwy**, od dołu (narzędzia) do góry (interfejs). Każda
warstwa zna tylko sąsiadów: UI nie grzebie w sieci, wątki nie dotykają
Tk bez pośrednika. Kluczowa zasada komunikacji: **wątki → UI wyłącznie
przez kolejkę** (`post_ui`), a **UI → wątki przez flagi**.

```
 WARSTWA 6  UI: App._build_ui, ModTile, ModBadge, BadgeFlow, Led, ToolTip
 WARSTWA 5  LOGIKA APLIKACJI: App._tick, check_now, _exec_pending, watch
 WARSTWA 4  TAB MAPY: ServerTab (poleceń RCON, modów, statusu)
 WARSTWA 3  ŹRÓDŁA ZEWNĘTRZNE: LogTail (log serwera), RCONClient,
            cf_request/cf_get_mods_batch (CurseForge)
 WARSTWA 2  PAMIĘĆ TRWAŁA: save_versioned/newest_matching/migrate_old_file,
            write_json_atomic (pliki samoopisujące, rotacja 10)
 WARSTWA 1  NARZĘDZIA: tr (słownik PL/EN) + t() z asaonly/jezyk.py (3.84), sanitize_name,
            open_log_shared (odczyt bez blokowania), write_debug_log
```

---

## 1. START PROGRAMU (co się dzieje po uruchomieniu)

| Krok | Funkcja | Co robi praktycznie |
|---|---|---|
| 1 | `App.__init__` | wykrywa język (`_detect_lang`), ładuje config/sekrety/taby |
| 2 | `_load_server_tabs` → `_restore_tabs` → `add_server` | wskrzesza każde `CONFIG_MAPS_TABS/<mapa>/` jako żywy tab |
| 3 | `_show_first_run_hint` | pierwsza uruchomienie: szybki start w KONSOLI (nie okienko) |
| 4 | `ServerTab.__init__` → `after(500, _start_tail)` | każdy tab odpala swojego LogTail |
| 5 | `App._tick` (co 500 ms, wiecznie) | serce: patrz sekcja 2 |

Migracja starych nazw plików: `migrate_old_file` (po dacie modyfikacji).

## 2. ZEGAR = `App._tick` (co 500 ms)

Po kolei w każdym tyknięciu:
1. **drukuje dziennik** batchem z `_log_queue` (wątki wrzucają, tik zbiera; od 3.85.2 do konsoli
   pisze osobny wątek `asaonly/konsola.py` — zaznaczenie w konsoli nie zatrzymuje okna),
2. **3.71: karmi maszynę** — init raz (`_monitor_init`, flaga `_mon`), potem
   cykl 10 s w wątku (`_monitor_worker` → `post_ui(_monitor_apply)`; snapshot
   `list(self.tabs.items())` — lekcja 3.71.1), `_cf_tick` (dioda CF + sonda)
   i `_auto_next_tick` (auto-kolejna tura po GOTOWY),
3. co ~2 s odświeża diody tabów (`_refresh_badges` — tania siatka bezpieczeństwa),
3. koloruje diody wg `_tail_status` (`_update_led_color`),
4. pilnuje osi restartu (`_tick_restart_timeline`) i czuwania (`_tick_return_watch`),
5. gdy czas: `check_now()` (sprawdzenie modów),
6. mruga statusem + zegar „Następne sprawdzenie: 299 s" (format %d s, od 3.59) (`_update_pending_ui_blink`).

## 3. TAB MAPY = `ServerTab` (serce użytkownika)

- **Pola** ↔ plik: `to_config` / `App.save_tab` / `save_tab_secrets`
  (3.85.3: przycisk „Zapisz tab” pod polami — `ServerTab._zapisz`; znacznik
  zmian `_odswiez_zapis` ← `App._tab_niezapisany`, porównanie z `_saved_tabs`,
  które `save_tab` aktualizuje po udanym zapisie)
  (konfiguracja i sekret to OSOBNE pliki w `CONFIG_MAPS_TABS/<nazwa>/`; sekret we własnym podkatalogu `CONFIG_SECRET_RCON/` — od 3.64).
- **Mody tabu**: `var_tab_mods` → `get_effective_mod_ids`; edycja pola
  (`_on_mods_edited`) gasi flagę `mods_unverified` (ręczna decyzja wygrywa).
- **Status mapy**: `_apply_tail` (z LogTail) → `_set_status` (kolor/dioda);
  przy „ładuje mody/gotowa" + flaga → `_verify_mods_after_boot`
  (jednorazowa korekta listy modów wg logu — dla importów z backupu).
- **Mody z serwera**: `mods_from_server` — log = prawda, katalog = fallback,
  różnice logowane; ścieżki kandydackie z `mods_dir_candidates` (4 layouty).
- **Linie RCON**: `RconLineRow` (czas/komenda/włącznik) → `get_lines`
  → harmonogram restartów (sekcja 5).
- **RCON na żądanie**: `test_rcon`/`admin_send`/`send_rcon` → kolejka
  `enqueue_rcon` → `_rcon_worker` (jedno połączenie na tab, seryjnie).

## 4. CURSEFORGE = cykl sprawdzenia modów

```
_tick → check_now (manual=True z przycisku)
         1. zbierz mody z tabów (mapy włączone)      ← hierarchia 3.52
         2. brak modów? → milczeć / cf_no_mods (manual)
         3. brak klucza? → 1 ostrzeżenie + odrocenie  ← 3.51/3.52
         4. installed_max (wersje na dysku, wątek UI) ← anty-pętla 3.41
         5. run_async(_cf_worker)
              └─ cf_get_mods_batch → paczki po 50 modów (1 POST na paczkę);
                 między paczkami drzemka chunk_delay (3.73: pole z UI,
                 domyślnie 1 s, cap 60 s, tylko gdy jest następna paczka)
              └─ porównanie wersji → pending_updates
              └─ post_ui(_cf_done)
         6. _cf_done → _verify_local_mods (co naprawdę na dysku)
                      → _update_mods_panel → kafelki/diody
```

Klucz: `check_now` NIGDY nie dotyka sieci (tylko UI i decyzje);
`_cf_worker` NIGDY nie dotyka Tk. Łączy je `post_ui`/`run_async`.

## 5. AKTUALIZACJA I RESTART MAPY (automatyka)

```
pending_updates (lista mody→nowe wersje)
  → auto RCON wł.? → _exec_pending          (asaonly/procedura.py)
       1. per mapa: walidacja linii (validate_rcon_line_values), konflikt
          portu, brak DoExit → mapa POMINIĘTA pojedynczo, reszta idzie
       2. Kolejka(mapy, czasy_startu, sondy)  (asaonly/kolejka.py — czysta
          logika, bez Tk/RCON/plików; testy: tests/test_kolejka.py)
       3. restart_active: _tick_restart_timeline co tik:
            _verify_local_mods co 5 s (mapa wstała sama z nową wersją →
              wypada z kolejki)
            Kolejka.tick(now) → akcje:
              ("sonda", mapa)   → ListPlayers (enqueue_raw) → wynik_sondy
                                  pusto / gracze / nieznane(=gracze)
              ("wyslij", ...)   → linia harmonogramu (czas LOKALNY mapy)
              ("doexit", ...)   → tylko gdy dysk wolny i status GOTOWY
       4. _wynik_doexit → _start_return_watch([mapa])
  → czuwanie: _tick_return_watch — nowy boot + GOTOWY + wersja z logu
    (zdarzenia CFCore/LoadGameMods) → Kolejka.zakoncz (czas startu →
    config czasy_startu); timeout → mapa NIEUDANA, następna rusza.
  → _finish_coordinator: podsumowanie per mapa, zapis configu; nowszy
    update w trakcie = AUTO-kolejna tura (karencja 60 s, `_auto_next_t`).
  → Na ścieżce automatycznej ZERO okienek; przerwana procedura (restart
    programu) jest porzucana przy starcie (_porzuc_przerwana_procedure).
  → 3.82: KONTROLA CZASU (PLUGINY/87_kontrola_czasu.py → asaonly/kontrola.py)
    czyta te same dane (tab.rows, porty, czasy_startu) i woła te same funkcje
    walidacji + Kolejkę na symulowanym czasie; tylko odczyt.
  → 3.85: ZLECENIA RESTARTU OD PLUGINÓW (asaonly/procedura.py):
    plugin: app.zlec_restart(mapy, powód, właściciel) → _zlecenia_restartu
      → automat (_auto_next_t, cf_wersje._auto_next_tick) → _exec_pending:
        _blokada_kolejki() (plugin.blokada_kolejki → kolejka czeka 60 s)
        mapa ze zleceniem wchodzi do kolejki także bez zaległych modów
      → przed DoExit: plugin.przed_doexit(mapa) → "ok" | "zbedne" | "blad"
        (nie-ok: mapa bez restartu albo „restart tylko dla modów”)
      → _wynik_doexit: po_doexit(mapa) albo doexit_nieudany(mapa);
        mapa w _bez_pomiaru_startu (czas startu NIE trafia do czasy_startu)
      → _finish_coordinator: zlecenia z tej kolejki usunięte.
    plugin OFF → app.odwolaj_zlecenia(właściciel).
  → 3.86: AKTUALIZACJA SERWERA PRZEZ CACHE (PLUGINY/88_aktualizacja_serwera.py 2.0.0):
    tik → sprawdz(zrodlo="api" co 60 s | "steamcmd": zapas co 5 min / kontrola
      co 60 min | "lokalne" po gotowym cache) → wątek _sprawdz_praca:
      czytaj_lokalny(mapy) + czytaj_lokalny(cache) + updater_managera(user.config)
      + siec.steam_api_info (api.steamcmd.net) albo _zapytaj_steam (SteamCMD)
    → _po_sprawdzeniu (UI) → _decyduj:
      updater managera ON → nic (ostrzeżenie); konflikt folderu cache → nic;
      cache_do_aktualizacji → _aktualizuj_cache → wątek _cache_praca_fn:
        SteamCMD app_update TYLKO do cache (serwery działają; odmowa manifestu
        cache → drugi raz bez appmanifest) → _po_cache: OK → sprawdz("lokalne");
        błąd → powód z content_log.txt, przerwa 5/15/30 min, ZERO restartów;
      mapy_do_przeniesienia (cache gotowy i nie starszy niż Steam) →
        _zaplanuj → wątek SYNC.plan(cache, mapa) → _po_planowaniu:
        nic do kopiowania → _tylko_manifest (bez restartu); reszta → _zlec_mapy:
        GOTOWA → zlec (kolejka powyżej); OFFLINE/CRASH/30 min → aktualizuj_bez_serwera
    → przed_doexit/_przygotuj: plan aktualny? miejsce? → Zamrazarka.zamroz()
    → po_doexit → _aktualizuj_praca (wątek): serwer wyłączony? →
      zamrazarka.ustaw_kopie(dziennik) → SYNC.wykonaj (kopie tymczasowe, stare do
      .refresher-kopia, appmanifest na końcu; błąd → wycofanie) → appmanifest =
      build cache? → finally: odmroz()
    → _po_aktualizacji (UI): próby/build, plan usunięty, dziennik, wskaźnik.
    Czysta logika: asaonly/steam_serwer.py (parsery, API, content_log, user.config,
    decyzje cache), asaonly/synchronizacja.py (plan, wykonanie, wycofanie z
    dziennika — używa go też strażnik asaonly/zamrazanie.py po awarii).
```

### 5a. MASZYNA 3.71 (monitor — mapa-logiki)
```
_tick (UI) --co 10 s--> _monitor_worker (wątek: netstat/ss -> port->PID,
  3.73: _netstat_map(tekst) — CZYSTA funkcja testowalna (przed
  pad_klasyfikuj): port z ADRESU LOKALNEGO, stan w linii LISTENING
  lub NASLUCHUJACE (NFKD->ascii upper) + fallback NAS+UCHUJ (ogonki
  utracone); _pid_map (nt) deleguje do _netstat_map
                          wiek logow per tab, snapshot tabs)
                   -> post_ui(_monitor_apply): decyzje w UI
  PAD4: slad crasha + proces zyje -> okno 90 s, potem wyrok (pad4_*)
  PAD pewny: PID znany i proces zniknal -> pad_klasyfikuj (crash_slad?)
  WISI: wiek loga >= 15 min -> _sonda_rcon (listplayers, cb(err));
        >= 20 min -> alarm wisi_info; powrot -> wisi_wrocil
  samorestarty: ready->starting bez czlowieka (licznik per mapa)
  pobieranie modow przez serwer (zdarzenia LogCFCore) bez postepu 20 min
        (3.73, bylo 10) -> dl_stuck; "Log file open" zeruje stan (3.81)
_cf_blad/_cf_ok (haki w _handle_cf_error/_cf_done) -> _cf_tick:
  sonda JEDNEGO moda (najmniejszy ID) w rytmie rytm_fazowy_s 1/3/15 min
_dziennik_modow: przed procedura stan modow do WIEDZA/dziennik-modow.txt
  (dziennik_dopisz, rotacja 15x10 KB, PRZED dopisaniem)
_wykryj_mody: WYKRYJ - flaga _mods_unverified + _verify_mods_after_boot
_chip_label(name, tab) (3.73): etykieta kafelka = status + [NOWY]
  (_mods_unverified) + [SONDA]/[WISI!] wg _wisi_st (1=sonda, 2=wisa);
  _update_leds_frame i _update_led_color(name, tab) buduja etykiete przez nia
Stan per-tab (_wisi_st/_sonda_t/_dl_last/_dl_alarm/_last_log_t) nadaje
ServerTab.__init__ (od 3.71.1 — wlasciciel stanu = konstruktor wlasciciela;
_monitor_init NIE dotyka tabow).
```

`cancel_restart` przerywa (przycisk + `flush_rcon_queue`).
Aktualizacja moda, którego mapa NIE używa → brak restartu (`_tabs_for_mod`).

## 6. LOG SERWERA = `LogTail` (wątek na tab)

- `run`: otwiera `ShooterGame.log` shared (`open_log_shared` — nie blokuje
  serwera), czyta nową treść, wykrywa rotację (grace 1 s),
- `_infer_initial_state` / `_handle_line` → statusy:
  `starting / loading_mods / engine / ready / crash / offline`,
- crashstack: `_newest_crashstack` (pętla crashy = osobne ostrzeżenie),
- `_emit` → `_on_tail` → `post_ui(_apply_tail)` —**jedyna droga do UI**,
- **prawda o modach**: `App._loaded_mods_from_log` (ogon 512 KB; linie
  LoadGameMods w całości; „Loading mod: X (version Y)" → tylko ID).

## 7. RCON = `RCONClient` (protokół Source RCON)

`connect → _auth → command → close`; `rcon_send` = opakowanie z retry.
Błędy → `RCONError` → log z retry (3 próby z odstępem 2 s —
backoff siedzi w kolejce RCON per tab; audyt dokumentacji tury 48).

## 8. IMPORT I BACKUPY (trzy formaty)

| Format pliku | Rozpoznawanie | Zachowanie |
|---|---|---|
| dzisiejszy (`lines` + `name`) | klucz `lines` | import 1 taba; kolizja → pytanie TAK/NIE + sufiks „ (2)" |
| stary tab (bez `name`, linie bez `on`, `mod_ids` lista) | `_normalize_legacy_tab` | normalizacja → jak wyżej |
| BARDZO stary globalny (`servers` + globalne `mod_ids`) | `_legacy_global_tabs` | rozbicie na taby; mody globalne każdej mapie; hasła ze starego `passwords{}` |

Każdy import: `_import_one_tab` (hasło: sekret obok > stare pole),
weryfikacja modów wg logu (3.50: działa → korekta; stoi → flaga
`mods_unverified` + samokorekta po starcie serwera).

## 9. PLIKI NA DYSKU (co gdzie ląduje)

```
 <katalog programu>/
   CONFIG_PROGRAM/CONFIG_PROGRAM - zapis ....json           (ustawienia)
   CONFIG_SECRET_API/CONFIG_SECRET_API - zapis ....json       (API key)
   CONFIG_MAPS_TABS/<mapa>/CONFIG_MAP <mapa> - zapis ....json
   CONFIG_MAPS_TABS/<mapa>/CONFIG_SECRET_RCON/CONFIG_SECRET_RCON <mapa> - zapis ....json
   WIEDZA_O_PROGRAMIE/  (dokumentacja + asa_debug.log + dziennik-modow.txt 3.71)
   [root = TYLKO program .py i starter .bat — od 3.64]
```
Zasady (warstwa 2): nowy plik tylko przy zmianie treści; rotacja 10
(starsze = backupy); `newest_matching` czyta najnowszy; migracja starych
nazw automatyczna. Zapis atomowy (`write_json_atomic`) — nie ma
półplików nawet przy crashu.

## 10. UI (warstwa 6) — kto co rysuje

| Element | Klasa/funkcja | Praktycznie |
|---|---|---|
| kafelki modów (okno modów) | `ModTile` + `Led` | nazwa, wersja znana/najnowsza, mapy używające; klik = strona moda |
| diody w tabie | `ModBadge` + `BadgeFlow` | kolor = stan moda (wait `#3d6db5` od razu, ok `#207020`, update `#e0a050`, pending `#d9534f`); zawijanie do linii |
| kafelki statusów map | `BadgeFlow` w `frm_status` + `_update_leds_frame`/`_chip_text`/`_chip_tip` | 3.60: kropka + nazwa + status SŁOWAMI (tr `st_*`), kolor tekstu = kolor diody, dymki `tip_map_*`, zawijanie; górny rząd (`frm_status_top`) = tekst + przyciski bez zmian; 3.71: kafelki KLIKALNE (wybór mapy), chip `[NOWY]` przy niezweryfikowanej liście, w tym samym rzędzie przycisk WYKRYJ i dioda CF (`_leds["__cf__"]`) |
| podpowiedzi | `ToolTip` (`_add_tooltip`) | jednolity słownik TR |
| licznik pending | `_refresh_pending_ui` + blink | mody czekające na restart |

## 11. NIETYKALNE FILARY (dla przyszłych edycji)

1. Log serwera = prawda o modach (katalog tylko fallback).
2. Mody wchodzą wyłącznie przez taby; lista główna = suma tabów.
3. Sekrety osobno od konfiguracji; nie opuszczają komputera.
4. Wątki → UI tylko przez `post_ui`; UI → sieci tylko przez `run_async`.
5. Zawsze przesuwaj `next_check` przy KAŻDYM wyjściu z `check_now`
   (lekcja 3.51: wczesny return = spam).
6. Każda zmiana = nowa wersja + wpis w README + test (debugN).
7. Stan per-tab nadaje WŁAŚCICIEL w konstruktorze (ServerTab.__init__),
   nigdy centralny init raz na starcie (lekcja 3.71.1: taby rodzą się
   też po starcie — EN/PL, import, „+ Dodaj mapę").

## 12. TESTY (standard wydawniczy)

- `symulacja/tescior.py` — bicie serca: odpala CAŁĄ flotę
  (jednostkowe 39 + debug5–25 + sterownik v6) i streszcza wyniki;
  debug23 = FUZZ (10 seedów × 21 operacji), debug24 = fix 3.71.1,
  debug25 = MARSZ PRZYCISKOWY (54 checki, każdy przycisk kilkukrotnie),
- nowa funkcja/fix = nowy debugN z asercjami + wpis tutaj,
- zasady harnessu: mainloop + wątek scenariusza (pompowanie `update()`
  gubi `after_idle` z wątków), neutralizacja dialogów, osobne katalogi
  na "instalacje", display przez `xvfb-run`.
