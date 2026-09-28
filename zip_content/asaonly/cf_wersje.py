# -*- coding: utf-8 -*-
"""Task 2a: CurseForge polling, detection and pending creation."""
import os
import time

from .jezyk import t
from .siec import cf_request, cf_get_mods_batch, CF_MODS_BATCH_URL
from .monitor import rytm_fazowy_s

DEFAULT_CHECK_INTERVAL=300
MIN_CHECK_INTERVAL=30
CF_REQUEST_DELAY=1.0

class CurseForgeMixin:
    @staticmethod
    def _classify_map_versions(mid, latest_fid, map_versions):
            targets, unknown = [], []
            for map_name, versions in map_versions.items():
                if mid not in versions:  # mapa nie używa tego moda
                    continue
                row = versions[mid]
                if row is None or not str(row.get("fid", "")).isdigit():
                    unknown.append(map_name)
                elif int(row["fid"]) < int(latest_fid):
                    targets.append(map_name)
            return targets, unknown

    def _cf_blad(self, err=""):
            """3.71: CF padl - od teraz sonda w rytmie fazowym 1/3/15 min."""
            if not hasattr(self, "_cf_st"):
                self._monitor_init()
            if self._cf_st != "blad":
                self._cf_st = "blad"
                self._cf_t0 = time.time()
                self._cf_next = self._cf_t0 + 60

    def _cf_ok(self):
            if not hasattr(self, "_cf_st"):
                self._monitor_init()
            if self._cf_st != "ok":
                self._cf_st = "ok"
                self._cf_t0 = 0.0
                self._cf_next = 0.0

    def _cf_tick(self, now):
            """3.71: dioda CF + harmonogram sondy CF (wywolywane z _tick UI)."""
            led = getattr(self, "_leds", {}).get("__cf__")
            st = getattr(self, "_cf_st", "ok")
            if led:
                led.set_color("#207020" if st == "ok" else "#b00020")
            if st == "blad" and now >= self._cf_next:
                self._cf_next = now + rytm_fazowy_s(max(0.0, now - self._cf_t0))
                self._cf_sonda_run()

    def _cf_sonda_run(self):
            """3.71: sonda CF - JEDEN mod (najmniejszy ID), read-only."""
            ids = set()
            for tab in self.tabs.values():
                if tab.var_map_on.get():
                    try:
                        ids.update(int(m) for m in tab.get_effective_mod_ids())
                    except Exception as exc:
                        self.log_warn(t("[%s] Nie udało się odczytać modów do sondy CF: %s",
                                        "[%s] Could not read the mods for the CF probe: %s")
                                      % (tab.name, exc))
            if not ids:
                return
            mid = min(ids)
            t0 = time.time()
            self.log(self.tr("cf_sonda_start", mod=mid))

            def rob():
                key = self.var_api_key.get().strip()
                ok = False
                try:
                    if key:
                        cf_request(CF_MODS_BATCH_URL, key, payload={"modIds": [mid]})
                        ok = True
                except Exception:
                    ok = False
                s = int(time.time() - t0)
                if ok:
                    self.post_ui(lambda: (self._cf_ok(),
                                          self.log(self.tr("cf_sonda_ok", mod=mid, s=s))))
                else:
                    self.post_ui(lambda: self.log(self.tr("cf_sonda_nie", mod=mid, s=s)))
            self.run_async(rob)

    def _wykryj_mody(self):
            """3.71: WYKRYJ - skan logow wszystkich map + dopasowanie modow
            do CurseForge (reuzywa istniejacego weryfikatora startowego)."""
            n = 0
            self.log(self.tr("wykryj_start"))
            for tab in self.tabs.values():
                if tab.var_map_on.get():
                    tab._mods_unverified = True
                    n += 1
                    try:
                        tab.after_idle(tab._verify_mods_after_boot)
                    except Exception as exc:
                        self.log_warn(t("[%s] Nie udało się zaplanować wykrywania modów: %s",
                                        "[%s] Could not schedule mod detection: %s")
                                      % (tab.name, exc))
            self.log(self.tr("wykryj_done", n=n))

    def _auto_next_tick(self, now):
            """3.71: auto-kolejna tura po GOTOWY (karencja 60 s, bez okienka)."""
            t = getattr(self, "_auto_next_t", None)
            if not t:
                return
            zlecenia = self.__dict__.get("_zlecenia_restartu")
            if (not self.pending_updates and not zlecenia) or not self.auto_rcon.get() \
                    or self.restart_active:
                self._auto_next_t = None
                self.log(self.tr("auto_kolejna_stop"))
                return
            if now >= t:
                self._auto_next_t = None
                self._exec_pending()

    def _cf_worker(self, api_key, mod_ids, cf_delay, map_versions=None):
            """Batch CF plus per-map qualification prepared on the UI thread.

            map_versions = {map: {mid: {fid, source}}}.  The worker never reads
            Tk or disk and never treats mere mod membership as restart proof.
            """
            if map_versions is None:
                map_versions = {}
            try:
                self.post_ui(lambda: self.log(self.tr("cf_check_start")))
                updates_found = []

                # Zapytanie Batch
                batch_results = cf_get_mods_batch(mod_ids, api_key, chunk_delay=cf_delay)

                for mid in mod_ids:
                    if self._destroying:
                        return

                    self.post_ui(lambda m=mid: self._set_mod_state(m, "checking"))

                    if mid not in batch_results:
                        self.post_ui(lambda m=mid, err=t("Brak w CF API", "Missing in the CF API"):
                                     self._handle_cf_error(m, err))
                        continue

                    data = batch_results[mid]
                    # latestFiles bywa listą plików klienta. Jest sygnałem nowej
                    # wersji; server_artifact nie jest warunkiem wykrywania.
                    name = data["name"]
                    page = data["page"]
                    fid = data["fid"]
                    fname = data["fname"]

                    # Worker nie modyfikuje współdzielonego stanu aplikacji.
                    # Metadane trafiają do niego tylko przez kolejkę głównego wątku.
                    self.post_ui(lambda m=mid, n=name, p=page, f=fid, fn=fname:
                                 self._apply_cf_metadata(m, n, p, f, fn))

                    targets, unknown = self._classify_map_versions(
                        mid, fid, map_versions)
                    if unknown:
                        self.post_ui(lambda m=mid, maps=tuple(unknown): self.log_warn(
                            t("Mod %s: brak potwierdzonej wersji map: %s — bez automatycznej procedury",
                              "Mod %s: no confirmed version on maps: %s — no automatic procedure")
                            % (m, ", ".join(maps))))
                    if targets:
                        self.post_ui(lambda m=mid: self._set_mod_state(m, "update"))
                        updates_found.append((mid, name, fid, targets))
                    elif unknown:
                        # Stan nieznany nie jest zgodą na restart ani fałszywym OK.
                        self.post_ui(lambda m=mid: self._set_mod_state(m, "error"))
                    else:
                        self.post_ui(lambda m=mid, f=fid: self._mark_cf_current(m, f))

                    # Zapis stanu po kazdym przemielonym idku w pamieci
                    self.post_ui(self.request_save)

                self.post_ui(lambda u=updates_found: self._cf_done(u))
            except Exception as e:
                # Worker never touches Tk/log buffers directly.
                self.post_ui(lambda err=str(e): self.log(self.tr("worker_err") + err))
                self.post_ui(self._cf_cleanup)

    def _apply_cf_metadata(self, mid, name, page, fid, fname):
            self.mod_names[mid] = name
            self.mod_pages[mid] = page
            self.mod_latest[mid] = {"fid": fid, "name": fname}

    def _mark_cf_current(self, mid, fid):
            self.known_versions[mid] = fid
            self._set_mod_state(mid, "ok")

    def _handle_cf_error(self, mid, err):
            self.log(self.tr("cf_error", mid=mid, err=err))
            self._set_mod_state(mid, "error")
            self._cf_blad(str(err))

    def _set_mod_state(self, mid, state):
            self.mod_states[mid] = state
            tile = self._mod_rows.get(mid)
            if tile:
                tile.refresh()
            # 3.42: diody w tabach map zyja razem ze stanem moda
            for tab in self.tabs.values():
                tab._refresh_badges()

    def _cf_done(self, updates):
            self.log(self.tr("cf_done", n=len(updates)))
            self._cf_cleanup()
            self._cf_ok()  # 3.71: plyta CF wrocila do normy

            iv = int(self.var_interval.get().strip() or DEFAULT_CHECK_INTERVAL)
            if iv < MIN_CHECK_INTERVAL:
                iv = MIN_CHECK_INTERVAL
            # 3.41 FIX "CF HAMMER": next_check przesuwamy ZAWSZE, takze gdy check
            # cos znalazl. Wczesniej w tej galezi next_check zostawal w przeszlosci,
            # a _tick (0,5 s) odpytywal CurseForge w petli przez caly czas procedury
            # i zaleglosci (11 zapytan w 7 s przy interwale 30 s - dowod: telemetria
            # symulacji, run D). W produkcji grozilo to limitami API.
            self.next_check = time.time() + iv

            if not updates:
                self._verify_local_mods()
                return

            fresh = False
            for mid, name, fid, targets in updates:
                if mid not in self.monitor_off:
                    existing = next((p for p in self.pending_updates if isinstance(p, dict) and p.get("mid") == mid), None)
                    if existing is None or int(fid) > int(existing.get("fid", 0)):
                        fresh = True
                        self.log(self.tr("cf_update", mid=mid, name=name,
                                         fname=self.mod_latest.get(mid, {}).get("name", fid)))
                    self._add_or_update_pending(mid, name, fid, targets=targets)

            self._refresh_pending_ui()
            self.request_save()

            if self.auto_rcon.get():
                if self.watch_active:
                    if fresh:
                        self.log(self.tr("watch_park_log"))
                else:
                    self._exec_pending()
            else:
                self.log(self.tr("auto_off_log"))

    def _cf_cleanup(self):
            self.check_in_progress = False
            self._update_mods_panel()

    def schedule_immediate_mod_check(self):
            """Pull the CF check forward after a map is added/imported.

            Startup may perform its first tick while there are no tabs yet and
            postpone the next check by the full interval.  Importing running
            servers must cancel that wait so their configured mods are adapted
            immediately, as in earlier releases.
            """
            due = time.time() + 0.1
            current = getattr(self, "next_check", due)
            self.next_check = min(current, due)

    def check_now(self, manual=False):
            if self.check_in_progress:
                return

            # 3.52: NAJPIERW sprawdzamy, czy w ogole jest CO sprawdzac.
            # Bez tabow / bez modow program nie interesuje sie kluczem API
            # (wczesniej klucz byl sprawdzany pierwszy i program "uparcie
            # zadal" API nie majac zadnego moda do sprawdzenia).
            mod_ids = set()
            for tab in self.tabs.values():
                if tab.var_map_on.get():
                    mod_ids.update(tab.get_effective_mod_ids())

            try:
                iv = int(self.var_interval.get().strip() or DEFAULT_CHECK_INTERVAL)
            except Exception:
                iv = DEFAULT_CHECK_INTERVAL

            if not mod_ids:
                # Nic do sprawdzenia: auto-tik milczy, reczny przycisk odpowiada.
                self.next_check = time.time() + iv
                if manual:
                    self.log(self.tr("cf_no_mods"))
                return

            api_key = self.var_api_key.get().strip()
            if not api_key:
                # 3.51 FIX "spam konsoli": wczesniej return BEG odroczenia
                # next_check -> auto-tik (500 ms) strzalal co tik, po 2 logi/s
                # "Brak klucza API". Teraz: odroczamy o caly interwal i logujemy
                # RAZ (reczny przycisk zawsze odpowiada).
                self.next_check = time.time() + iv
                if manual or not self._no_key_warned:
                    self.log(self.tr("cf_no_key"))
                    self._no_key_warned = True
                return
            self._no_key_warned = False

            self.check_in_progress = True
            try:
                cf_delay = float(self.var_cf_delay.get().strip() or CF_REQUEST_DELAY)
            except Exception:
                cf_delay = CF_REQUEST_DELAY

            # Snapshot per mapa na wątku UI. Najmocniejszy dowód to wersja
            # raportowana przez bieżący proces w logu; registry/dysk jest tylko
            # dowodem ukończonej instalacji używanym, gdy log nie podał par.
            map_versions = {}
            for tab in self.tabs.values():
                if not tab.var_map_on.get():
                    continue
                configured = set(tab.get_effective_mod_ids())
                rows = {mid: {"fid": None, "source": "unknown"}
                        for mid in configured}
                observed = dict(getattr(tab, "_server_versions", {}))
                installed = {}
                mods_dir = self._mods_dir_for_tab(tab)
                if mods_dir and os.path.isdir(mods_dir):
                    installed = dict(self._installed_file_ids(mods_dir))
                for mid in configured:
                    if str(observed.get(mid, "")).isdigit():
                        rows[mid] = {"fid": str(observed[mid]), "source": "loaded_log"}
                    elif str(installed.get(mid, "")).isdigit() and str(installed[mid]) != "0":
                        rows[mid] = {"fid": str(installed[mid]), "source": "registry"}
                map_versions[tab.name] = rows

            self.run_async(self._cf_worker, api_key, list(mod_ids), cf_delay, map_versions)
