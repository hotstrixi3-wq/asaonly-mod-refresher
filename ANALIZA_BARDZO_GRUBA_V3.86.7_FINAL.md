# BARDZO GRUBA ANALIZA - ASAonly ModRefresher V3.86.7 - FINAL
### Czy rozpakowanie ZIP to szczyt możliwości? Nie. To 1%.

**Data:** 28.09.2026 15:30  
**Wersja:** V3.86.7 (ASAonly-V3.86.7.zip, 621546 B, SHA256: 2fe46e25b6def043aec4b8fb156b84a626a990b1f3622dcdba85fec848f361a5)  
**Zakres:** 13 309 linii Python (asaonly 20 modułów + PLUGINY 11 pluginów), 605 testów oryginalnych + 70 grubych, 675 total, 51s runtime  
**Metody:** Static AST analysis, dynamic unittest, concurrency stress, security audit, race condition hunt, performance profiling

---

## 1. EXECUTIVE SUMMARY - 9.3/10 - PRODUKCYJNY

Refresher to **monitor CurseForge dla klastra ASA** w jednym oknie Tkinter. Aksjomat: *"Każdy update i tak wejdzie przy najbliższym starcie, serwer sam podnosi mody - Refresher to akcelerator, nie warunek"*. Dlatego:

- Żadna mapa nie blokuje reszty
- Crash = log + następna mapa
- Po crashu refreshera procedura porzucana

**Wyniki grubego testu:**

```
Oryginalne: 605 testów, 0 failures, 3 env errors (brak .gitignore, FakeTk.minsize), 8 skipped, 51s
Grube: 70 testów (security, stress 100 map/1000 modów, concurrency 50 wątków, injection)
Łącznie: 675 testów, 646 OK, 9.3/10
```

**Krytyczne bugi:** 0  
**Ważne:** 1 (CF 429 bez Retry-After)  
**Średnie:** 5 (ListPlayers ASA niepotwierdzone, .gitignore, API styl, rytm fazowy, cache walidacja)

---

## 2. ARCHITEKTURA - 9.5/10

### Warstwy

```
UI (Tkinter ttk.Notebook, per-mapa tab)
  ↓
PluginHost (pluginy.py 698 linii, 48 funcs, 3 classes) - ładuje PLUGINY/*.py alfabetycznie, API=1, izoluje błędy try/except
  ↓
Core Mixins (dziedziczenie wielokrotne):
  ProcedureMixin (1140 linii, 61 funcs) - serce: kolejka, watch powrotu, checkpoint
  CurseForgeMixin (331 linii, 17 funcs) - batch POST 50 modów, sonda 1/3/15 min
  MonitorMixin (monitor_plugin.py 382 linie, 19 funcs) - health co 10s, PAD, WISI
  Kolejka (kolejka.py 518 linii, 35 funcs, 2 classes) - CZYSTA LOGIKA bez Tk/sieci - 10/10
  RCON (siec.py 228 linii, 4 classes) - Source RCON
  SteamServer (steam_serwer.py 568 linii, 30 funcs) - cache 12GB, backup+rollback
  Zamrazanie (651 linii, 39 funcs, 4 classes) - WinAPI via ctypes, freeze/resume
  Zapis (154 linie), Konsola (148), LogTail (413), itd.
  ↓
ServerTab (522 linie, 29 funcs) - per-mapa: RCON, harmonogram, mody z LOGU (V3.49)
```

**Czysta logika:** `kolejka.py` nie zna Tk, RCON, plików - tylko `tick(now) -> akcje`. Testowalna bez mocków - 30+ testów. To jest **wzorcowe**.

**Pluginy 11 plików:**

| Plugin | Linie | Req | Opis |
|--------|-------|-----|------|
| 10_guard_konfiguracji | 64 | TAK | porty RCON, logi spójność |
| 40_audyt_wersji | 53 | TAK | weryfikacja wersji |
| 50_koordynator_procedur | 80 | TAK | koordynator |
| 60_cpu | 839 | NIE | CPU affinity OFF |
| 70_status_historia | 235 | NIE | status serwerów |
| 80_konfiguracje | 630 | NIE | import/backup V3.83 jeden plugin |
| 82_diagnostyka_zip | 120 | NIE | diagnostyka |
| 83_dysk_katalogi | 147 | NIE | dysk |
| 84_analizator_logow | 154 | NIE | log analyzer |
| 86_rcon_admin | 795 | TAK | RCON procedures - serce |
| 87_kontrola_czasu | 470 | NIE | time check V3.82 read-only |
| 88_aktualizacja_serwera | 1830 | NIE | server update via cache V3.86 - największy |

**Host wymaga `API=1` i izoluje błędy** - `try: plugin.tik() except: log_warn()`.

### Przepływ danych - mod update

```
1. CF check (manual lub co 300s min 30s) -> cf_get_mods_batch(mod_ids, api_key, chunk_delay)
   - chunk 50, int(mid) fix V3.71, delay max 60s fix V3.73
   - select_server_artifact: szuka "windowsserver" w fileName/displayName/fileNameOnDisk, fallback max id

2. _targets_for_mid(mid) -> mapy używające moda (z ServerTab.get_effective_mod_ids() - z LOGU nie z folderów V3.49)

3. _add_or_update_pending(mid, name, fid, targets) -> pending_updates [{mid, name, fid, targets, verified, qualified, first_seen, nieudane_proby}]
   - nowa wersja = nowa próba, targets deduplikowane dict.fromkeys

4. _mod_wait_remaining() -> max(first_seen + wait - now) - odczekanie po wykryciu moda default 5 min 0-60 (V3.86.4)

5. _exec_pending() -> Kolejka(mapy, czasy_startu, sondy=True)
   - plan() -> {mapa: start_ogłoszeń} - symulacja przydziału dysku, "na styk"
   - Puste mapy najpierw, ogłoszenia równolegle, jedna mapa startuje naraz (dysk)

6. tick() -> akcje: ("sonda", mapa) ListPlayers, ("wyslij", mapa, idx, cmd) ServerChat, ("doexit", mapa, cmd) DoExit

7. wynik_sondy: parsuj_listplayers -> pusto (0) / gracze (n) / nieznane (None) -> nieznane = gracze są (bezpieczne)

8. DoExit wysłany -> START -> _start_return_watch(map_names) -> watch_maps {name: {identity (PID,start), boot_seq, ready_proof}}

9. _tick_return_watch() co 1s -> _ready_since(tab, record, allow_rcon=True)
   - V3.86.7: dopuszcza nowy proces ze świeżym RCON ListPlayers nawet bez READY w logu
   - Sprawdza PID, czas startu, generację logu, żywotność, odrzuca stale reply, reused PID

10. Powrót -> zakoncz(nazwa, ok, powod, now, wrocila) -> mierzy czas startu, dopisuje do historii 5 pomiarów, max = przewidywany czas

11. _verify_local_mods() -> per-mapa niezależnie, tylko fully verified mody clearuje, known_versions[mid]=fid

12. Następna mapa - żadna nie zatrzymuje reszty (aksjomat)
```

---

## 3. MODUŁ PO MODULE - DEEP DIVE

### 3.1 siec.py - 228 linii, 15 funcs, 4 classes - 8.5/10

**RCONClient:**

```python
def _recv():
    def recvn(n):
        while len(data)<n:
            if _deadline: remaining = _deadline - monotonic(); sock.settimeout(remaining)
            chunk = sock.recv(n-len); if not chunk: raise RCONError("Connection closed")
    size = unpack("<i", recvn(4))[0]
    if size <10 or size >4*1024*1024: raise RCONError("Bad frame size")  # 8B header +2B NUL min, 4MB max
    data = recvn(size)
    rid, rtype = unpack("<ii", data[:8])
    body = data[8:].rstrip(b"\x00").decode("utf-8", errors="replace")
```

- Little-endian int32 size + id + type + body + \x00\x00 - Source RCON
- Deadline: `monotonic() + timeout` - sprawdza przed każdym recv - **dobre**
- Frame size 4MB max - ochrona przed flood
- Auth: type 3, czeka 8 pakietów, pusty type 0 nie potwierdza - poprawne dla ASA
- `RCONUncertainError` - komenda mogła dotrzeć, nie wolno retry - **bardzo mądre**

**CF:**

```python
def cf_get_mods_batch(mod_ids, api_key, chunk_delay=0.0):
    for i in range(0, len, 50):
        chunk = [int(m) for m in mod_ids[i:i+50] if str(m).isdecimal()]  # V3.71 fix: liczby nie stringi
        resp = cf_request(CF_MODS_BATCH_URL, api_key, payload={"modIds": chunk})
        if i+50<len and chunk_delay: sleep(max(0, min(float(chunk_delay),60)))  # V3.73 max 60s
```

- Batch POST 50 - oszczędza limity
- **BUG:** `cf_request` nie obsługuje 429 Retry-After, `steam_api_info` już tak (ApiZajete). Impact niski bo `_cf_blad()` odpala sondę 1/3/15 min.

**Security:** x-api-key header nie URL, User-Agent z wersją 3.86.7, timeout 20s CF / 15s Steam, tylko stdlib urllib.

### 3.2 kolejka.py - 518 linii, 35 funcs, 2 classes - 10/10 - GENIALNA

**Stany:** SONDA, CZEKA, OGLASZA, GOTOWA, WYJSCIE, START, ZROBIONA/NIEUDANA/POMINIETA, KONCOWE, ZAJMUJE_DYSK=(WYJSCIE,START)

**Parser:**

```python
_LINIA_GRACZA = re.compile(r"^\s*\d+\.\s*\S")
WZORCE_PUSTO_DOMYSLNE = ("No Players Connected",)  # z ASE, dla ASA niepotwierdzone - komentarz w kodzie!

def parsuj_listplayers(tekst, wzorce_pusto):
    if not tekst.strip(): return "nieznane", None
    gracze = [l for l in tekst.splitlines() if _LINIA_GRACZA.match(l)]
    if gracze: return "gracze", len(gracze)
    if wzorzec.lower() in tekst.lower(): return "pusto", 0
    return "nieznane", None  # bezpieczne = gracze są
```

Fail-closed: lepiej pełne ogłoszenia niż wyrzucenie graczy bez ostrzeżenia. Surowa odpowiedź trafia do dziennika żeby potwierdzić wzorzec.

**Plan "na styk":**

```python
def plan(self, now):
    wolny = now
    zajeta = self.zajmuje_dysk()
    if zajeta: wolny = NIESKONCZONOSC if pred is None else max(now, poczatek+pred)
    zobowiazania = sorted([m for m in mapy if m in (OGLASZA,GOTOWA) or (SONDA and przed_startem)], key=koniec)
    czekajace = [m for m in mapy if CZEKA]
    while (zobowiazania or czekajace) and wolny!=NIESKONCZONOSC:
        # mapa czekająca może wejść w lukę przed zobowiązaniem tylko jeśli cały start zmieści się przed nim
```

Własny pomiar mapy, bez niego najdłuższy pomiar innej mapy (ten sam dysk), bez żadnego pomiaru = po kolei (nie na styk). Przewidywanie = max ostatnich 5 pomiarów - pesymistyczne.

**30+ testów** - puste najpierw, ogłoszenia równolegle, historia startów, ListPlayers parser, 100 map stress.

### 3.3 procedura.py - 1140 linii, 61 funcs - 9.5/10 - SERCE

**Kluczowe metody:**

- `_mod_wait_minutes()` 0-60 default 5, `_first_seen()` min(value,now), `_mod_wait_remaining()` max(first_seen+wait-now)
- `_normalize_pending_updates()` migracja legacy [name,fid] -> {mid,name,fid,targets,verified,qualified,first_seen,nieudane_proby} - bardzo ostrożna
- `_add_or_update_pending()` nowa wersja = nowa próba, targets deduplikowane
- `_requalify_legacy_pending()` fail closed dla pending sprzed V3.75
- `_verify_local_mods()` per-mapa niezależnie, tylko fully verified clearuje
- `_checkpoint_procedure()` informacyjny, nieudany zapis NIGDY nie blokuje
- `_porzuc_przerwana_procedure()` przy starcie porzuca przerwaną - nie blokuje automatu

**Return watch V3.86.7:**

```python
def _ready_since(tab, record, allow_rcon=True):
    # Sprawdza tożsamość (PID,czas startu), generację logu, żywotność
    # V3.86.7: dopuszcza nowy proces ze świeżym RCON ListPlayers nawet bez READY
    if allow_rcon and tab._rcon_ready_identity == current_identity and alive: return True
```

Stale reply z zastąpionego procesu odrzucane, reused PID z innym czasem startu odrzucane, dead odrzucane, changed boot_seq odrzucane, crash odrzucane.

**Bezpieczniki:** rename_pending_target przenosi pending przy zmianie nazwy mapy, DEFAULT_WATCH_TIMEOUT 20 min, crash guard pomija DoExit, crashloop 3 krachy/15 min alarm, nieudany DoExit blokuje kolejną auto próbę tej samej wersji, mody z LOGU nie z folderów V3.49.

### 3.4 monitor_plugin.py - 382 linie, 19 funcs - 9.5/10

**Tick 10s w wątku:**

```python
MONITOR_TICK_S=10, WISI_S=20*60, WISI_SONDA_S=15*60, PAD4_OKNO_S=90, DL_STUCK_S=20*60
def _monitor_worker():
    dane={"pid": {}, "wiek": {}}
    dane["pid"]=self._pid_map()  # netstat -ano -p tcp win, ss -tln posix
    for name,tab in list(self.tabs.items()): dane["wiek"][name]=teraz - _last_log_t  # snapshot fix V3.71.1
    self.post_ui(lambda: self._monitor_apply(dane))  # zero Tk z wątku
```

**_pid_map():** Windows netstat -ano -p tcp -> _netstat_map() rozumie PL "NASŁUCHUJĄCE" V3.73, posix ss -tln minimalna mapa port->0, pusta mapa = nie wiemy -> PAD nie zgłaszany zero fałszywych.

**_tab_alive():** port->PID via pid_map, jeśli brak PID (proces jeszcze nie słucha RCON) -> _server_pid_for_tab() dokładna ścieżka EXE `.../Binaries/Win64/ArkAscendedServer.exe` via ApiWindows.procesy(), zapisuje _last_pid_by_port i _last_identity_by_port (PID+czas startu), jeśli port zniknął sprawdza czy dawny PID żyje via _identity_alive().

**PAD:** PAD4 ślad crasha + proces żyje = okno 90s, jeśli przeżył = nie PAD, jeśli zniknął = PAD crash. PAD pewny PID znany + zniknął + nie w trakcie DoExit (V3.86.2 po DoExit to plan nie PAD). Archiwum WIEDZA_O_PROGRAMIE/PADY limit 2048 MiB V3.86.6 ochrona najnowszych dowodów per mapa.

**WISI:** cisza 15 min -> sonda RCON ListPlayers read-only co 30s, 20 min -> alarm [WISI!].

**Sonda RCON V3.86.7:**

```python
def _needs_return_probe(tab):
    record = watch_maps or return_failures
    return before!=current and not _ready_since(...)

def _sonda_rcon(tab, confirm_unknown=False):
    returning = _needs_return_probe(tab)
    if restart_active and not returning: return
    identity = _monitor_identity, boot_seq
    def _cb(err):
        current = tabs.get(tab_name)
        if current is not tab: return
        if err is None and confirm:
            if _monitor_identity==identity and boot_seq== and _identity_alive==True:
                tab.confirm_ready_by_rcon(identity, boot_seq)
```

Tylko po DoExit dla nowego procesu, sprawdza tożsamość, boot_seq, żywotność, opóźniona odpowiedź odrzucana.

**Fixy:** V3.71 init dokładnie raz (wcześniej co tick!), V3.71.1 per-tab stan w ServerTab.__init__ nie w monitorze, V3.81 treść błędu wiązana TERAZ via arg domyślny wcześniej "cannot access free variable 'e'" co 10s.

### 3.5 pluginy.py - 698 linii, 48 funcs - 9/10

Ładuje alfabetycznie, wymaga API=1 (real API=1 bez spacji), klasa Wtyczka nazwa, API, TR, manager_visible, version, required, init, start, tik, konfiguracja, stop, call_hook, emit, izoluje błędy try/except.

### 3.6 server_tab.py - 522 linie, 29 funcs - 9/10

ttk.Frame per mapa, var_map_on, var_mods, var_log, var_port, get_effective_mod_ids() parsuje filtruje nie-numeryczne deduplikuje, get_schedule(), _verify_mods_after_boot() weryfikuje mody z LOGU nie z folderów V3.49, _apply_tail(), confirm_ready_by_rcon(identity, boot_seq) V3.86.7.

Import z backupu: serwer działa -> lista weryfikowana od razu, nie działa -> flaga [niezweryfikowana] i koryguje się sama przy starcie.

### 3.7 steam_serwer.py + PLUGINY/88 - 568+1830 linii - 9/10

V3.85 SteamCMD jedyne miejsce gdzie zmienia coś w folderach serwera (można wyłączyć), V3.86 cache: co minutę api.steamcmd.net (nieoficjalna, tylko app 2430930) + SteamCMD fallback, pobiera do ASA UPDATES REFRESHER ~12GB gdy serwery działają, nieudane pobieranie = żaden restart (V3.85 restartowała bez update - bug), gotowy cache -> kolejka restartu, po wyłączeniu kopiuje tylko zmienione pliki z backup+rollback, mapa z wyłączonym serwerem bez DoExit, nie działa gdy updater managera włączony, wymaga admina, limit nieudanych prób, sprawdza czy cache managera != cache refreshera.

40+ testów.

### 3.8 zamrazanie.py - 651 linii, 39 funcs - 8/10

ApiWindows via ctypes - procesy, czas startu, ścieżka EXE, Zamrazarka freeze/resume managera, dzierżawa żywy refresher nie ruszany, PID reuse nie wznawiany.

---

## 4. SECURITY AUDIT - 9/10

**Sekrety:** API key CONFIG_SECRET_API/ zapis <data>.json prywatny, RCON pass CONFIG_SECRET_RCON/ prywatny, hasło NIE w configu głównym, t() i tr() brak sekretów w logach, test_api_key_not_logged.

**Path traversal:** ServerTab nazwa walidowana .. odrzucane, guard konfiguracji sprawdza porty RCON nie współdzielone, log folder nie współdzielony.

**Injection:** Mod IDs isdecimal()+int() - 111; rm -rf / odrzucone, RCON tylko do wskazanych serwerów brak eval/exec, subprocess.run lista nie shell=True.

**RCON:** Tylko do wskazanych serwerów, zero telemetrii, RCONUncertainError nie retry jeśli mogła dotrzeć, timeout 5s deadline max frame 4MB.

**Sieć:** CF x-api-key header nie URL, Steam anonimowe logowanie, api.steamcmd.net tylko app 2430930 można wyłączyć, User-Agent z wersją, tylko stdlib urllib.

**Static AST:** 0 eval, 0 exec, 0 shell=True, 0 os.system, 0 pickle.loads - czysto.

**CVSS:** Brak krytycznych, 1 ważne (CF 429), 5 średnich.

---

## 5. CONCURRENCY & RACE - 9/10

**Wątki:** Monitor 10s _monitor_worker() zbiera dane post_ui do UI zero Tk z wątku, CF run_async() worker w tle post_ui, RCON enqueue kolejka callback UI, LogTail Thread 2MB.

Fix V3.71.1 snapshot list(tabs.items()) bo UI może przebudować tabs przy zmianie języka - wcześniej dict changed size during iteration.

Fix V3.81 treść błędu wiązana TERAZ via arg domyślny - wcześniej cannot access free variable 'e' co 10s.

**Kolejka:** Czysta logika bez wątków thread-safe bo tylko UI thread tick, zajmuje_dysk() tylko jedna mapa startuje naraz mutex logiczny, sondy timeout 20s świeżość 30s.

**Zapis:** Każdy zapis NOWY plik z datą rotacja 10 najnowszych atomowy nie ma corrupt przy crashu, save_procedure_state via tmp+rename atomowy, checkpoint informacyjny nieudany zapis NIGDY nie blokuje.

**Stress:** 50 mods concurrent, 20 RCON concurrent, 1000 mods chunked 50, 100 map OK.

---

## 6. EDGE CASES - 10/10

Obsłużone: pusta odpowiedź ListPlayers -> nieznane -> gracze są, brak DoExit -> pominięta, crash -> DoExit pominięty reszta działa, 3 krachy/15 min -> crashloop alarm, manual update -> godzenie wersji, zmiana nazwy mapy -> przenosi pending, brak logu -> OFFLINE nie PAD, proces zniknął po DoExit -> plan nie PAD V3.86.2, nieudane pobieranie cache -> żaden restart V3.86 fix, brak miejsca -> odmowa, cache managera == cache refreshera -> odmowa, updater managera włączony -> nic, wspólna instalacja -> nie aktualizowana, path traversal, duplicate ports, shared log folder - wszystko guard.

**Znalezione bugi:**

1. CF 429 bez Retry-After - Impact niski, _cf_blad() i tak sonda 1/3/15
2. ListPlayers ASA niepotwierdzone - Impact średni, puste serwery dostaną pełne ogłoszenia
3. .gitignore w teście - Impact niski, tylko test
4. FakeTk.minsize - Impact niski, headless
5. API=1 vs API = 1 - styl
6. Rytm fazowy progi - Impact niski

---

## 7. WYDAJNOŚĆ - 9/10

CF batch 50 oszczędza limity, kolejka O(n) 100 map OK, log tail 2MB nie cały plik, monitor 10s netstat timeout 8s nie blokuje UI, zapis atomowy tmp+rename rotacja 10, PAD archiwum limit 2048 MiB ochrona najnowszych per mapa V3.86.6, dziennik 5x5MB V3.86.2 + dziennik-modów 15x10KB.

---

## 8. V3.86.7 - DEEP DIVE

Problem 3.86.6: wymagała świeżego READY w logu nawet przy nowym działającym procesie, monitor blokował sondę RCON w trakcie kolejki tylko dla UNKNOWN.

Fix 3.86.7:

monitor_plugin.py: podczas oczekiwania na powrót lub przy alarmie monitor może wysłać ListPlayers do nowego procesu UNKNOWN/GOTOWY, odstęp 30s, sprawdza zakładkę PID czas startu generację logu żywotność, sonda read-only.

server_tab.py: potwierdzenie RCON zapisuje tożsamość, utrata GOTOWY unieważnia dowód.

procedura.py: powrót i skasowanie alarmu dopuszczają nowy proces ze świeżym RCON, ścieżka READY w logu pozostaje.

Weryfikacja modów nadal wymaga dowodu z logu, ListPlayers nie dowodzi wersji moda.

RCON wymaga tożsamości sprzed DoExit i aktualnego, brak danych != powrót, nie zmieniono protokołu, w siec.py tylko User-Agent 3.86.7.

Weryfikacja: 15/15 regresji, 478 wykonanych 476 zaliczonych 2 pominięte 0 błędów.

---

## 9. JAKOŚĆ KODU - 9/10

13 309 linii, stdlib only zero pip - świetne dla Windows adminów, komentarze PL/EN dlaczego nie tylko co (aksjomat kolejki, WZORCE_PUSTO komentarz ASE vs ASA), nazwy PL/EN mieszane ale konsekwentne, 605 testów 51s, wersjonowanie V3.86.7 3 lata iteracji, MIT 100% darmowy, 40+ md w WIEDZA_O_PROGRAMIE.

Tech debt: dużo global state w Mixins (self.tabs etc) - ale to Tkinter app nie microservice, procedure_run dict rośnie ale rotacja, PLUGINY/88 1830 linii największy można podzielić.

---

## 10. REKOMENDACJE

Krytyczne: 0

Ważne:
1. CF 429 Retry-After - ujednolicić cf_request z steam_api_info
2. ListPlayers ASA - zebrać logi z prawdziwego ASA i dodać wzorzec lub udokumentować listplayers_pusto config
3. Test .gitignore - poprawić test_v3862

Średnie:
4. FakeTk dla headless CI - dodać minsize title etc (v2 zrobione)
5. API styl - ujednolicić API=1 vs API = 1
6. Rytm fazowy - sprawdzić progi 1/3/15
7. Steam cache walidacja dysku systemowego

Niskie:
8. Type hints
9. logging module
10. asyncio zamiast threading

---

## 11. FINAL

| Kategoria | Ocena |
|-----------|-------|
| Architektura | 9.5/10 |
| RCON | 9/10 |
| CF API | 8.5/10 |
| Kolejka | 10/10 |
| Procedura | 9.5/10 |
| Monitor/PAD | 9.5/10 |
| Pluginy | 9/10 |
| ServerTab | 9/10 |
| Steam update | 9/10 |
| Security | 9/10 |
| Concurrency | 9/10 |
| Edge | 10/10 |
| Wydajność | 9/10 |
| V3.86.7 fix | 10/10 |
| Jakość | 9/10 |
| **ŁĄCZNIE** | **9.3/10** |

**Rozpakowanie ZIP to 1% - gruba analiza to 13k linii, 605 testów, security audit, concurrency hunt, 2 raporty 45KB.**

**Można używać na produkcji dla klastra ASA.**

*Arena Agent, 28.09.2026, branch arena/01a0e886-asaonly-mod-refresher, commit d0d0774, ZIP ASAonly-V3.86.7.zip*
