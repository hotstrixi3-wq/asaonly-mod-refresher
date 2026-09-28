# -*- coding: utf-8 -*-
"""Zadanie 3: procedura RCON na mapach — V3.81: aksjomat akceleratora + inteligentna kolejka."""
import copy
import math
import os
import time
import uuid
from tkinter import messagebox

from .jezyk import t
from .server_tab import duplicate_enabled_ports
from .kontrola import DLUGIE_CZEKANIE_S, PRZESUNIECIE_STAREGO_ZEGARA_S
from .kolejka import (Kolejka, Mapa, ZAJMUJE_DYSK, wzorce_pusto_z_konfiguracji,
                      parsuj_listplayers, przewidywany_czas_startu,
                      dopisz_czas_startu, jest_komunikatem)

DEFAULT_WATCH_TIMEOUT=20
KARENCJA_PO_GOTOWY_S=60


def rename_pending_target(records, old_name, new_name):
    """Keep qualified/verified pending work attached to a renamed map."""
    changed = False
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in ("targets", "verified"):
            values = record.get(key)
            if not isinstance(values, list):
                continue
            replaced = [new_name if value == old_name else value for value in values]
            # Preserve order while removing duplicates created by legacy data.
            replaced = list(dict.fromkeys(replaced))
            if replaced != values:
                record[key] = replaced
                changed = True
    return changed


class ProcedureMixin:
    def _mod_wait_minutes(self):
            var = self.__dict__.get("var_mod_wait")
            raw = var.get() if var is not None else self._cfg("mod_wait_min", 0)
            try:
                return max(0, min(60, int(raw)))
            except (ValueError, TypeError):
                return 5

    @staticmethod
    def _first_seen(value, now):
            try:
                value = float(value)
                if math.isfinite(value) and value > 0:
                    return min(value, now)
            except (TypeError, ValueError):
                pass
            return now

    def _mod_wait_remaining(self, pending, now):
            wait = self._mod_wait_minutes() * 60
            for p in pending:
                p["first_seen"] = self._first_seen(p.get("first_seen"), now)
            return max([0] + [p["first_seen"] + wait - now for p in pending])

    def _rcon_plugin(self):
            host = self.__dict__.get("plugin_host")
            return host.get("rcon_admin") if host else None

    def _rcon_enqueue(self, tab, command, callback=None):
            plugin = self._rcon_plugin()
            if plugin:
                return plugin.enqueue(tab, command, callback)
            # Wyłącznie dla izolowanych symulacji bez hosta pluginów.
            if not self.__dict__.get("plugin_host"):
                return tab.enqueue_rcon(command, callback)
            raise RuntimeError(t("brak wymaganego pluginu RCON", "required RCON plugin missing"))

    def _rcon_flush(self, tab):
            plugin = self._rcon_plugin()
            if plugin:
                return plugin.flush(tab)
            if not self.__dict__.get("plugin_host"):
                return tab.flush_rcon_queue()

    def _rcon_validate(self, tab):
            plugin = self._rcon_plugin()
            if plugin:
                lines, err = plugin.validate(tab)
                if err == "host":
                    return None, t("brak adresu RCON", "no RCON address")
                if err == "port":
                    return None, t("nieprawidłowy port RCON", "invalid RCON port")
                if err == "time":
                    return None, self.tr("line_time_invalid")
                if err == "command":
                    return None, self.tr("line_cmd_empty")
                return lines, None
            return tab.validate_lines()

    def _coordinator_plugin(self):
            host = self.__dict__.get("plugin_host")
            return host.get("koordynator_procedur") if host else None

    def _targets_for_mid(self, mid):
            return sorted(tab.name for tab in self.tabs.values()
                          if tab.var_map_on.get() and mid in tab.get_effective_mod_ids())

    def _normalize_pending_updates(self):
            """Migrate legacy [name, fid] pending records to the safe 3.75 schema."""
            normalized = []
            for raw in list(self.pending_updates):
                if isinstance(raw, dict):
                    mid = str(raw.get("mid", ""))
                    name = str(raw.get("name") or self.mod_names.get(mid) or ("Mod " + mid))
                    fid = str(raw.get("fid", "0"))
                    targets = list(dict.fromkeys(raw.get("targets") or self._targets_for_mid(mid)))
                    verified = [n for n in raw.get("verified", []) if n in targets]
                elif isinstance(raw, (list, tuple)) and len(raw) == 2:
                    name, fid = str(raw[0]), str(raw[1])
                    mid = next((k for k, v in self.mod_names.items() if v == name), "")
                    if not mid:
                        self.log_warn(t("Nie można bezpiecznie odtworzyć ID zaległości: %s",
                                       "Cannot safely recover the mod ID of a pending update: %s") % name)
                        continue
                    targets = self._targets_for_mid(mid)
                    verified = []
                else:
                    continue
                if mid and fid.isdigit():
                    rekord = {"mid": mid, "name": name, "fid": fid,
                              "targets": targets, "verified": verified,
                              "qualified": bool(raw.get("qualified", False)) if isinstance(raw, dict) else False}
                    rekord["first_seen"] = self._first_seen(raw.get("first_seen") if isinstance(raw, dict) else None, time.time())
                    # V3.81: „jedna automatyczna próba na (mapę, wersję)” przeżywa
                    # restart programu — inaczej każdy restart dawał nową pętlę.
                    proby = raw.get("nieudane_proby") if isinstance(raw, dict) else None
                    if isinstance(proby, dict):
                        proby = {str(k): str(v) for k, v in proby.items() if k in targets}
                        if proby:
                            rekord["nieudane_proby"] = proby
                    normalized.append(rekord)
            self.pending_updates = normalized

    def _add_or_update_pending(self, mid, name, fid, targets=None):
            # targets pochodzi z per-mapowego porównania CF z wersją serwera.
            # Sam fakt używania moda nie może kwalifikować mapy do restartu.
            if targets is None:
                targets = self._targets_for_mid(mid)  # zgodność ze starym zapisem/testami
            targets = list(dict.fromkeys(targets))
            if not targets:
                return
            for p in self.pending_updates:
                if p["mid"] == mid:
                    if int(fid) > int(p["fid"]):
                        p.update(fid=fid, name=name, targets=targets, verified=[], qualified=True)
                        p["first_seen"] = time.time()
                        p.pop("nieudane_proby", None)   # nowa wersja = nowa próba
                    else:
                        p["targets"] = list(dict.fromkeys(p.get("targets", []) + targets))
                        p["qualified"] = True
                    return
            self.pending_updates.append({"mid": mid, "name": name, "fid": fid,
                                         "targets": targets, "verified": [],
                                         "qualified": True, "first_seen": time.time()})

    def _requalify_legacy_pending(self):
            """Fail closed for pending saved by versions that targeted every mod user."""
            kept = []
            for pending in self.pending_updates:
                if pending.get("qualified"):
                    kept.append(pending); continue
                targets, unknown = [], []
                for name in pending.get("targets", []):
                    tab = self.tabs.get(name)
                    if tab is None or not tab.var_map_on.get():
                        continue
                    mid = pending["mid"]; actual = getattr(tab, "_server_versions", {}).get(mid)
                    if not (actual and str(actual).isdigit()):
                        mods_dir = self._mods_dir_for_tab(tab)
                        installed = dict(self._installed_file_ids(mods_dir)) if mods_dir and os.path.isdir(mods_dir) else {}
                        actual = installed.get(mid)
                    if not (actual and str(actual).isdigit()):
                        unknown.append(name)
                    elif int(actual) < int(pending["fid"]):
                        targets.append(name)
                if unknown:
                    self.log_warn(t("Pending mod %s: brak wersji map %s — bez automatycznego restartu",
                                    "Pending mod %s: no known version on maps %s — no automatic restart") %
                                  (pending["mid"], ", ".join(unknown)))
                if targets:
                    pending["targets"] = targets
                    pending["verified"] = [n for n in pending.get("verified", []) if n in targets]
                    pending["qualified"] = True
                    kept.append(pending)
            self.pending_updates = kept

    def _verify_local_mods(self):
            """Verify each target map independently; clear only fully verified mods."""
            changed = False
            for tab in self.tabs.values():
                if not tab.var_map_on.get():
                    continue
                mods_dir = self._mods_dir_for_tab(tab)
                installed = {}
                if mods_dir and os.path.isdir(mods_dir):
                    for mid, fid in self._installed_file_ids(mods_dir):
                        if fid and fid != "0":
                            old = installed.get(mid)
                            if old is None or int(fid) > int(old):
                                installed[mid] = fid
                result = self.__dict__.get("_proc_map_results", {}).get(tab.name, {})
                post_boot = bool(result.get("doexit_ok"))
                fresh_ready = self._ready_since(tab, result, allow_rcon=False) if post_boot else False
                loaded = dict(getattr(tab, "_server_versions", {}))
                for p in self.pending_updates:
                    if tab.name not in p.get("targets", []) or tab.name in p.get("verified", []):
                        continue
                    # Po DoExit i nowym boocie przejście kolejki wymaga wersji
                    # faktycznie raportowanej przez nowy proces. Registry/dysk
                    # służy tylko do wstępnej kwalifikacji przed procedurą.
                    actual_fid = (loaded.get(p["mid"]) if fresh_ready else None) if post_boot else installed.get(p["mid"])
                    if actual_fid and int(actual_fid) >= int(p["fid"]):
                        p.setdefault("verified", []).append(tab.name)
                        changed = True
            kept = []
            for p in self.pending_updates:
                targets = set(p.get("targets", []))
                verified = set(p.get("verified", []))
                if targets and targets.issubset(verified):
                    self.known_versions[p["mid"]] = p["fid"]
                    self._set_mod_state(p["mid"], "ok")
                    changed = True
                else:
                    kept.append(p)
            self.pending_updates = kept
            if changed:
                self._refresh_pending_ui()
                self.request_save()

    # =====================================================================
    # V3.81 — procedura wg aksjomatu akceleratora + inteligentna kolejka.
    #
    # Każdy update i tak wejdzie przy najbliższym starcie serwera. Dlatego:
    #  * jedna mapa nigdy nie zatrzymuje reszty,
    #  * na ścieżce automatycznej nie ma okienek (tylko dziennik),
    #  * po restarcie refreshera przerwana procedura jest porzucana, nie
    #    blokuje automatu.
    # Planowanie kolejności i czasów jest w asaonly/kolejka.py (czysta logika).
    # =====================================================================

    def _persist_procedure_run(self):
            """Zapis informacyjny: po awarii refreshera dziennik powie, co przerwano.

            Nieudany zapis NIGDY nie blokuje procedury.
            """
            if not self.__dict__.get("plugin_host"):
                return True
            save = getattr(self, "save_procedure_state", None)
            if save is None:
                save = getattr(self, "save_global_state", None)
            try:
                return bool(save and save())
            except Exception:
                return False

    def _checkpoint_procedure(self, stage, **details):
            run = copy.deepcopy(self.__dict__.get("procedure_run") or {})
            run.update(details)
            run["stage"] = str(stage)
            run["updated_at"] = time.time()
            self.procedure_run = run
            ok = self._persist_procedure_run()
            if not ok and not self.__dict__.get("_checkpoint_warned"):
                self._checkpoint_warned = True
                self.log_warn(t("Nie udało się zapisać informacyjnego stanu procedury — "
                                "procedura trwa dalej (to tylko zapis do dziennika awarii).",
                                "Could not save the informational procedure state — "
                                "the procedure continues (this is only a crash-log record)."))
            return ok

    def _porzuc_przerwana_procedure(self):
            """Wołane przy starcie programu. Nigdy nie blokuje automatu."""
            run = self.__dict__.get("procedure_run")
            if not run:
                return
            self.log_warn(t(
                "[PROCEDURA] Poprzednie uruchomienie przerwało procedurę %s "
                "(etap: %s, mapa: %s). Porzucam ją. Mapy, które dostały DoExit, same "
                "podniosły mody przy starcie; pozostałe obsłuży najbliższe sprawdzenie.",
                "[PROCEDURE] The previous run interrupted procedure %s "
                "(stage: %s, map: %s). Abandoning it. Maps that received DoExit picked up "
                "the mods themselves at start; the next check will handle the rest.")
                % (run.get("run_id", "?"), run.get("stage", "?"), run.get("map") or "-"))
            self.procedure_run = None
            self._persist_procedure_run()

    # -- ustawienia V3.81 --------------------------------------------------------
    def _metoda_aplikacji(self, nazwa):
            """Metoda pełnej aplikacji albo None (atrapy testowe mają tylko część).

            Blizna V3.81: metod NIE szukamy w self.__dict__ — tam ich nie ma, więc
            w prawdziwej aplikacji wywołanie cicho się nie wykonywało (V3.80.35:
            koniec kolejki nie zapisywał konfiguracji i nie odświeżał zaległości).
            Najpierw patrzymy na klasę, bo getattr brakującej nazwy na obiekcie Tk
            potrafi wpaść w rekurencję __getattr__.
            """
            if getattr(type(self), nazwa, None) is None:
                return None
            return getattr(self, nazwa)

    def _cfg(self, key, default=None):
            data = self.__dict__.get("config_data")
            return data.get(key, default) if isinstance(data, dict) else default

    def _wzorce_pusto(self):
            return wzorce_pusto_z_konfiguracji(self._cfg("listplayers_pusto"))

    def _sondy_graczy(self):
            """Czy sprawdzać graczy przed restartem (wymaga odpowiedzi RCON)."""
            if not bool(self._cfg("pusty_serwer_od_razu", True)):
                return False
            plugin = self._rcon_plugin()
            return bool(plugin is not None and hasattr(plugin, "enqueue_raw"))

    def _czasy_startu(self):
            hist = self._cfg("czasy_startu", {})
            if not isinstance(hist, dict):
                return {}
            return {name: przewidywany_czas_startu(values)
                    for name, values in hist.items()}

    def _zapisz_czas_startu(self, nazwa, sekundy):
            data = self.__dict__.get("config_data")
            if not isinstance(data, dict):
                return
            hist = data.get("czasy_startu")
            if not isinstance(hist, dict):
                hist = {}
            hist[nazwa] = dopisz_czas_startu(hist.get(nazwa), sekundy)
            data["czasy_startu"] = hist

    def _mapa_ma_zaleglosc(self, nazwa):
            return any(nazwa in p.get("targets", []) and nazwa not in p.get("verified", [])
                       for p in self.pending_updates if isinstance(p, dict))

    def _oznacz_nieudana_probe(self, nazwa):
            """Wersja niepotwierdzona po restarcie: bez automatycznej pętli restartów.

            Ta sama wersja moda nie wywoła drugiego automatycznego restartu tej
            mapy. Nowsza wersja albo ręczny przycisk — tak.
            """
            for p in self.pending_updates:
                if not isinstance(p, dict) or nazwa not in p.get("targets", []):
                    continue
                if nazwa in p.get("verified", []):
                    continue
                proby = p.setdefault("nieudane_proby", {})
                proby[nazwa] = str(p.get("fid", "0"))

    def _proba_juz_byla(self, p, nazwa):
            proby = p.get("nieudane_proby", {}) if isinstance(p, dict) else {}
            return proby.get(nazwa) == str(p.get("fid", "0"))

    def _return_alarms(self):
            data = self.__dict__.setdefault("config_data", {})
            if not isinstance(data.get("return_failures"), dict):
                data["return_failures"] = {}
            return data["return_failures"]

    def _rcon_alarms(self):
            data = self.__dict__.setdefault("config_data", {})
            if not isinstance(data.get("rcon_failures"), dict):
                data["rcon_failures"] = {}
            return data["rcon_failures"]

    def _record_rcon_failure(self, name, reason):
            self._oznacz_nieudana_probe(name)
            self._rcon_alarms()[name] = {"time": time.time(), "reason": reason}
            self.log_warn(t("[%s] ALARM RCON: %s. Popraw połączenie i wykonaj zaległości ręcznie; "
                            "tej samej wersji nie ponawiam automatycznie.",
                            "[%s] RCON ALERT: %s. Fix the connection and run pending updates manually; "
                            "this version will not be retried automatically.") % (name, reason))
            self._save_return_alarms()

    def _clear_rcon_failure(self, name):
            if self._rcon_alarms().pop(name, None) is not None:
                self._save_return_alarms()

    @staticmethod
    def _rcon_connection_problem(err):
            if str(err).lower().startswith("auth failed"):
                return t("serwer odrzucił logowanie — sprawdź hasło i port RCON",
                         "server rejected authentication — check the RCON password and port")
            if isinstance(err, ConnectionRefusedError) or getattr(err, "winerror", None) == 10061:
                return t("połączenie odrzucone — sprawdź adres, port RCON i czy serwer działa",
                         "connection refused — check the address, RCON port and whether the server is running")
            return None

    @staticmethod
    def _new_boot_since(tab, record):
            before = record.get("identity")
            current = getattr(tab, "_monitor_identity", None)
            if before is not None and current is None:
                return False  # missing process information is not a new process
            if before is not None and current is not None:
                return tuple(before) != tuple(current)
            return tab._boot_seq > int(record.get("boot_seq", tab._boot_seq))

    @staticmethod
    def _ready_since(tab, record, allow_rcon=True):
            if tab._tail_status != "ready" or not ProcedureMixin._new_boot_since(tab, record):
                return False
            current = getattr(tab, "_monitor_identity", None)
            rcon = tab.__dict__.get("_rcon_ready_identity")
            if (allow_rcon and record.get("identity") is not None and current is not None
                    and rcon is not None and tuple(rcon) == tuple(current)):
                return True  # fresh probe validated against this PID + creation time
            proof = tab.__dict__.get("_ready_proof")
            if not proof or proof == record.get("ready_proof"):
                return False
            identity = getattr(tab, "_monitor_identity", None)
            if identity is not None:
                # Windows GetProcessTimes: 100 ns ticks since 1601. A queued
                # READY observed before this process existed belongs to an older
                # process, even if the monitor has already advanced twice.
                started = int(identity[1]) / 10_000_000 - 11_644_473_600
                if tab.__dict__.get("_ready_observed_at", 0.0) < started:
                    return False
            return True

    def _refresh_return_alarm(self):
            label = self.__dict__.get("lbl_return_alarm")
            if label is not None:
                names = ", ".join(sorted(self._return_alarms()))
                messages = []
                if names:
                    messages.append(t("ALARM — mapy nie wróciły: %s. Sprawdź managera i WIEDZA_O_PROGRAMIE/PADY. Refresher nie uruchamia serwerów.",
                                      "ALARM — maps did not return: %s. Check the manager and WIEDZA_O_PROGRAMIE/PADY. Refresher does not start servers.") % names)
                for name, record in sorted(self._rcon_alarms().items()):
                    messages.append(t("ALARM RCON — %s: %s. Po poprawieniu połączenia wykonaj zaległości ręcznie.",
                                      "RCON ALERT — %s: %s. After fixing the connection, run pending updates manually.") % (name, record.get("reason", "RCON")))
                label.configure(text="\n".join(messages))

    def _save_return_alarms(self):
            self._refresh_return_alarm()
            save = getattr(type(self), "request_save", None)
            if save is not None:
                self.request_save()

    def _check_return_alarm(self, tab, alive):
            record = self._return_alarms().get(tab.name)
            identity = getattr(tab, "_monitor_identity", None)
            if not record or not alive or tab._tail_status != "ready" or identity is None:
                return
            if not self._ready_since(tab, record):
                return  # stale READY must neither finish a watch nor clear an alert
            del self._return_alarms()[tab.name]
            self.log(t("[%s] Alarm powrotu skasowany: działający proces i GOTOWY potwierdzone.",
                       "[%s] Return alarm cleared: running process and READY confirmed.") % tab.name)
            self._save_return_alarms()

    # -- V3.85: zlecenia restartu od pluginów --------------------------------------
    # Plugin (np. aktualizacja serwera przez SteamCMD) prosi o restart mapy.
    # Mapa idzie tą samą kolejką co update modów: ogłoszenia z jej harmonogramu,
    # pusta = od razu, jeden start naraz. Właściciel zlecenia dostaje wywołania:
    #   przed_doexit(mapa) -> ("ok" | "zbedne" | "blad", powód) — tuż przed DoExit,
    #   po_doexit(mapa)          — DoExit przyjęty (serwer się wyłącza),
    #   doexit_nieudany(mapa)    — DoExit nie przeszedł.
    def _zlecenia(self):
            return self.__dict__.setdefault("_zlecenia_restartu", {})

    def zlec_restart(self, nazwy, powod, wlasciciel):
            """Przyjmij zlecenie restartu map. Zwraca listę nowo przyjętych map."""
            zlecenia = self._zlecenia()
            przyjete = []
            for nazwa in nazwy:
                tab = self.tabs.get(nazwa)
                if tab is None or not tab.var_map_on.get():
                    continue
                if nazwa not in zlecenia:
                    przyjete.append(nazwa)
                zlecenia[nazwa] = {"powod": str(powod), "wlasciciel": str(wlasciciel),
                                   "t": time.time()}
            if przyjete:
                self.log(t("[KOLEJKA] Zlecenie restartu (%s): %s — %s",
                           "[QUEUE] Restart request (%s): %s — %s")
                         % (wlasciciel, ", ".join(przyjete), powod))
                if not self.auto_rcon.get():
                    self.log(self.tr("auto_off_log"))
                elif not self.restart_active and not self.watch_active:
                    self._auto_next_t = time.time() + 2.0
            return przyjete

    def odwolaj_zlecenia(self, wlasciciel):
            """Usuń czekające zlecenia pluginu (np. wyłączonego). Zwraca nazwy map.

            Mapy już w trwającej kolejce pyta jeszcze przed_doexit — plugin może
            wtedy odmówić i mapa nie jest restartowana."""
            zlecenia = self._zlecenia()
            nazwy = sorted(n for n, z in zlecenia.items()
                           if isinstance(z, dict) and z.get("wlasciciel") == str(wlasciciel))
            for nazwa in nazwy:
                zlecenia.pop(nazwa, None)
            if nazwy:
                self.log(t("[KOLEJKA] Zlecenie restartu odwołane (%s): %s",
                           "[QUEUE] Restart request withdrawn (%s): %s")
                         % (wlasciciel, ", ".join(nazwy)))
            return nazwy

    def _blokada_kolejki(self):
            """Powód, dla którego kolejka nie może teraz ruszyć, albo None.

            Plugin z metodą blokada_kolejki() zgłasza pracę na serwerach, przy
            której nowa kolejka by przeszkadzała (np. wstrzymany manager — DoExit
            innej mapy czekałby wtedy na jego wznowienie). Pytany niezależnie od
            ON/OFF: rozpoczęta praca kończy się także po wyłączeniu pluginu."""
            host = self.__dict__.get("plugin_host")
            if host is None:
                return None
            for plugin in list(getattr(host, "plugins", ())):
                if getattr(plugin, "blokada_kolejki", None) is None:
                    continue
                powod = host.call_one(plugin.nazwa, "blokada_kolejki")
                if powod:
                    return str(powod)
            return None

    def _wolaj_zlecenie(self, zlecenie, hook, nazwa):
            host = self.__dict__.get("plugin_host")
            if host is None:
                return None
            return host.call_one(zlecenie.get("wlasciciel", ""), hook, nazwa)

    # -- start procedury ------------------------------------------------------
    def _exec_pending(self, manual=False):
            """Zbuduj kolejkę i uruchom procedurę.

            manual=True tylko z przycisku. Na ścieżce automatycznej (CF, kolejna
            tura) NIE MA żadnych okienek — wszystko idzie do dziennika.
            """
            if any(not p.get("qualified", False) for p in self.pending_updates if isinstance(p, dict)):
                self._requalify_legacy_pending()
            zlecenia = self._zlecenia()
            for nazwa in list(zlecenia):
                tab = self.tabs.get(nazwa)
                if tab is None or not tab.var_map_on.get():
                    zlecenia.pop(nazwa, None)          # mapa usunięta albo wyłączona
            if not self.pending_updates and not zlecenia:
                self._refresh_pending_ui()
                return
            if self.restart_active:
                self.log(self.tr("restart_already"))
                return
            blokada = self._blokada_kolejki()
            if blokada:
                # Ten sam powód nie jest powtarzany co minutę (ręcznie — zawsze).
                if manual or blokada != self.__dict__.get("_ostatnia_blokada"):
                    self._komunikat(t("Kolejka restartów czeka — %s.", "The restart queue waits — %s.")
                                    % blokada, manual)
                self._ostatnia_blokada = blokada
                if self.auto_rcon.get():
                    self._auto_next_t = time.time() + 60.0
                return
            self._ostatnia_blokada = None
            if self.__dict__.get("plugin_host") and self._rcon_plugin() is None:
                self._komunikat(t("Brak wymaganego pluginu RCON — procedura nie rusza.",
                                  "Required RCON plugin missing — the procedure does not start."), manual)
                return

            # Wspólny port RCON = niejednoznaczna tożsamość procesu. Pomijamy
            # TYLKO mapy z konfliktem, reszta klastra idzie dalej.
            dup = duplicate_enabled_ports([
                (tab.name, tab.var_map_on.get(), tab.var_port.get())
                for tab in self.tabs.values()])
            konflikt = {name for names in dup.values() for name in names}

            self.watch_active = False
            self.watch_maps.clear()
            self._auto_next_t = None
            self.log(self.tr("dziennik_proc"))
            self._dziennik_modow()
            self.schedule.clear()
            self._proc_incidents.clear()
            self._proc_map_results.clear()

            mapy = []
            pominiete = []
            pominiete_proby = []
            czekanie_do = []
            for tab in self.tabs.values():
                if not tab.var_map_on.get():
                    continue
                pending_for_tab = [p for p in self.pending_updates
                                   if tab.name in p.get("targets", [])
                                   and tab.name not in p.get("verified", [])]
                if not manual:
                    pomijane = [p for p in pending_for_tab if self._proba_juz_byla(p, tab.name)]
                    for p in pomijane:
                        self.log_warn(t("[%s] %s: poprzednia próba tej wersji nie powiodła się "
                                        "— bez kolejnej automatycznej próby tej "
                                        "samej wersji (ręcznie: przycisk zaległości).",
                                        "[%s] %s: the previous attempt for this version failed "
                                        "— no further automatic attempt for the same "
                                        "version (manually: the 'Run pending updates' button).")
                                      % (tab.name, p.get("name", p.get("mid"))))
                    pending_for_tab = [p for p in pending_for_tab if p not in pomijane]
                zlecenie = zlecenia.get(tab.name)
                pozostalo = self._mod_wait_remaining(pending_for_tab, time.time())
                if pending_for_tab and pozostalo > 0 and not zlecenie:
                    czekanie_do.append(time.time() + pozostalo)
                    stamp = tuple((p["mid"], p["fid"], p["first_seen"]) for p in pending_for_tab)
                    shown = self.__dict__.setdefault("_mod_wait_shown", {})
                    if manual or shown.get(tab.name) != stamp:
                        self.log(t("[%s] Nowa wersja moda: odczekanie jeszcze %d s przed restartem (ustawienie: %d min).",
                                   "[%s] New mod version: waiting another %d s before restart (setting: %d min).") %
                                 (tab.name, math.ceil(pozostalo), self._mod_wait_minutes()))
                        shown[tab.name] = stamp
                    continue
                if not pending_for_tab and not zlecenie:
                    if not manual and pomijane:
                        pominiete_proby.append(tab.name)
                        continue
                    path_check = getattr(type(tab), "log_path_problem", None)
                    problem = path_check(tab) if path_check else None
                    if problem:
                        self.log_warn(t("[%s] Bez kwalifikacji do restartu: %s", "[%s] Not qualified for restart: %s") % (tab.name, problem))
                    else:
                        self.log(self.tr("restart_skip_map", tab=tab.name))
                    continue
                if zlecenie:
                    self.log(t("[%s] w kolejce także: %s", "[%s] also queued: %s")
                             % (tab.name, zlecenie["powod"]))
                wynik = {"doexit_ok": False, "boot_seq": tab._boot_seq}
                if tab.name in konflikt:
                    wynik["result"] = "deferred_port_conflict"
                    self._proc_map_results[tab.name] = wynik
                    pominiete.append((tab.name, t("port RCON %s współdzielony z inną mapą",
                                                   "RCON port %s shared with another map")
                                      % tab.var_port.get()))
                    continue
                lines, err = self._rcon_validate(tab)
                if err:
                    wynik["result"] = "deferred_invalid"
                    self._proc_map_results[tab.name] = wynik
                    pominiete.append((tab.name, t("błędny harmonogram: %s", "invalid schedule: %s") % err))
                    continue
                if not lines:
                    wynik["result"] = "deferred_no_commands"
                    self._proc_map_results[tab.name] = wynik
                    pominiete.append((tab.name, t("brak aktywnych linii RCON", "no active RCON lines")))
                    continue
                mapa = Mapa(tab.name, lines)
                if mapa.koncowa():
                    wynik["result"] = "deferred_no_doexit"
                    self._proc_map_results[tab.name] = wynik
                    pominiete.append((tab.name, mapa.powod))
                    continue
                if mapa.po:
                    self.log_warn(t("[%s] linie po DoExit nie zostaną wysłane (serwera już nie ma): %s",
                                    "[%s] lines after DoExit will not be sent (the server is already gone): %s")
                                  % (tab.name, ", ".join("%ss %s" % (ts, c) for ts, c in mapa.po)))
                # Ten sam próg co kontrola czasu (asaonly/kontrola.py): krótkie
                # czekanie bez komunikatu jest nieszkodliwe.
                if (int(mapa.t_wyjscia_ludzie or 0) >= DLUGIE_CZEKANIE_S and
                        not any(jest_komunikatem(c) for _, c in mapa.przed)):
                    self.log_warn(t("[%s] harmonogram czeka %ss przed DoExit, ale nie ma w nim "
                                    "komunikatu dla graczy — to czekanie nic graczom nie daje. "
                                    "Czasy są lokalne dla mapy; odstępy między mapami robi kolejka.",
                                    "[%s] the schedule waits %ss before DoExit but has no message "
                                    "for players — that wait gives players nothing. Times are "
                                    "local to the map; the queue handles the spacing between maps.")
                                  % (tab.name, mapa.t_wyjscia_ludzie))
                elif mapa.przed and int(mapa.przed[0][0]) >= PRZESUNIECIE_STAREGO_ZEGARA_S:
                    # Typowy ślad zapisu sprzed 3.81 (wspólny zegar, przesunięcie
                    # o numer mapy): odstępy komunikatów są dobre, ale pierwsza
                    # linia niepotrzebnie czeka.
                    self.log_warn(t("[%s] pierwsza linia harmonogramu dopiero po %ss. Od 3.81 czasy "
                                    "są lokalne dla mapy — jeśli to przesunięcie ze starego wspólnego "
                                    "zegara, odejmij je od wszystkich linii tej mapy.",
                                    "[%s] the first schedule line comes only after %ss. Since 3.81 "
                                    "times are local to the map — if this is an offset from the old "
                                    "shared clock, subtract it from all lines of this map.")
                                  % (tab.name, mapa.przed[0][0]))
                wynik["result"] = "scheduled"
                self._proc_map_results[tab.name] = wynik
                mapy.append(mapa)

            if czekanie_do and self.auto_rcon.get():
                self._auto_next_t = min(czekanie_do)
            for name, why in pominiete:
                self.log_warn(t("[%s] pominięta — %s; pozostałe mapy idą dalej.",
                                "[%s] skipped — %s; the other maps continue.") % (name, why))
                # Zlecenie pluginu dla mapy, której kolejka nie przyjmie (zły harmonogram,
                # wspólny port…) — nie wraca w kółko; plugin zleci ponownie przy
                # następnym sprawdzeniu.
                zlecenia.pop(name, None)
            if pominiete and manual:
                messagebox.showwarning(
                    self.tr("app_title"),
                    t("Pominięto mapy (pozostałe idą dalej):\n\n", "Maps skipped (the others continue):\n\n") +
                    "\n".join("%s: %s" % x for x in pominiete), parent=self)
            if not mapy:
                if not pominiete and not czekanie_do and not pominiete_proby:
                    self.log(self.tr("restart_no_lines"))
                return

            rcon_plugin = self._rcon_plugin()
            busy = [m.nazwa for m in mapy
                    if rcon_plugin and not rcon_plugin.is_idle(self.tabs[m.nazwa])]
            if busy:
                self.log_warn(t("RCON zajęty dla map: %s — procedura odroczona o 5 s.",
                                "RCON busy for maps: %s — procedure postponed by 5 s.") % ", ".join(busy))
                if self.auto_rcon.get():
                    self._auto_next_t = time.time() + 5.0
                return

            self.procedure_run = {
                "run_id": uuid.uuid4().hex, "stage": "prepared", "created_at": time.time(),
                "maps": [m.nazwa for m in mapy], "map": None,
                "targets": copy.deepcopy(self.pending_updates),
                "zlecenia": {m.nazwa: dict(zlecenia[m.nazwa]) for m in mapy
                             if m.nazwa in zlecenia}}
            # Zlecenia map, które weszły do TEJ kolejki (reszta czeka na następną turę).
            self._zlecenia_w_kolejce = {m.nazwa: dict(zlecenia[m.nazwa]) for m in mapy
                                        if m.nazwa in zlecenia}
            self._bez_pomiaru_startu = set()
            self._checkpoint_warned = False
            self._persist_procedure_run()
            for tab in self.tabs.values():
                tab.set_lines_editable(False)
            self.btn_cancel.configure(state="normal")
            self.updated_mods = [dict(p) for p in self.pending_updates]
            sondy = self._sondy_graczy()
            self._kolejka = Kolejka(mapy, czasy_startu=self._czasy_startu(), sondy=sondy)
            self._kontrola_samostartow_t = 0.0
            self.restart_active = True
            self.restart_t0 = time.time()
            self.log(self.tr("restart_start"))
            self.log(t("[KOLEJKA] Mapy: %s. Jeden start naraz; %s.",
                       "[QUEUE] Maps: %s. One start at a time; %s.")
                     % (", ".join(m.nazwa for m in mapy),
                        t("przed restartem sprawdzam graczy (pusta mapa = bez ogłoszeń)",
                          "checking players before the restart (empty map = no announcements)")
                        if sondy else t("bez sprawdzania graczy — pełne harmonogramy",
                                        "no player check — full schedules")))
            self._tick_restart_timeline()

    def _komunikat(self, tekst, manual):
            self.log_warn(tekst)
            if manual:
                messagebox.showerror(self.tr("app_title"), tekst, parent=self)

    # -- główna pętla procedury (co tik UI) -----------------------------------------
    def _tick_restart_timeline(self):
            q = self.__dict__.get("_kolejka")
            if not self.restart_active or q is None:
                return
            now = time.time()
            # Mapa, która w międzyczasie wstała sama (manager, krach) i ma już
            # nową wersję, wypada z kolejki — bez drugiego restartu.
            if now - self.__dict__.get("_kontrola_samostartow_t", 0.0) >= 5.0:
                self._kontrola_samostartow_t = now
                self._verify_local_mods()
                for m in q.mapy:
                    if m.koncowa() or m.stan in ZAJMUJE_DYSK:
                        continue
                    tab = self.tabs.get(m.nazwa)
                    if tab is None or not tab.var_map_on.get():
                        q.pomin(m.nazwa, t("mapa usunięta albo wyłączona", "map removed or disabled"))
                    elif not self._mapa_ma_zaleglosc(m.nazwa) and \
                            m.nazwa not in self.__dict__.get("_zlecenia_w_kolejce", {}):
                        q.pomin(m.nazwa, t("wstała sama z nowymi modami — bez drugiego restartu",
                                            "came up on its own with the new mods — no second restart"))
                        self._proc_map_results.setdefault(m.nazwa, {})["result"] = "self_restarted"
                        self.log(t("[%s] wstała sama z nowymi modami — pomijam jej restart.",
                                   "[%s] came up on its own with the new mods — skipping its restart.") % m.nazwa)
            if self.watch_active:
                self._tick_return_watch()
            for akcja in q.tick(now):
                self._wykonaj_akcje(q, akcja)
            self._opublikuj_kolejke()
            if q.gotowe() and not self.watch_active:
                self._finish_coordinator()

    def _wykonaj_akcje(self, q, akcja):
            rodzaj, nazwa = akcja[0], akcja[1]
            tab = self.tabs.get(nazwa)
            if tab is None:
                q.pomin(nazwa, t("brak mapy", "map not found"))
                return
            if rodzaj == "sonda":
                self._wyslij_sonde(tab)
                return
            status = tab._tail_status
            if status in ("crash", "offline"):
                self._proc_incidents.add(nazwa)
                self._proc_map_results.setdefault(nazwa, {})["result"] = "deferred_incident"
                q.pomin(nazwa, t("serwer w stanie %s", "server in state %s") % status)
                self.log(self.tr("guard_skip", tab=nazwa, t=0, cmd=akcja[-1],
                                 status=self.tr("st_" + status)))
                return
            if rodzaj == "wyslij":
                self._wyslij_linie(tab, akcja[2], akcja[3])
            elif rodzaj == "doexit":
                if status != "ready":
                    self._proc_map_results.setdefault(nazwa, {})["result"] = "deferred_not_ready"
                    q.pomin(nazwa, t("DoExit zablokowany — serwer nie jest GOTOWY (%s)",
                                      "DoExit blocked — the server is not READY (%s)") % status)
                    key = "st_" + status if status in (
                        "starting", "loading_mods", "engine", "unknown") else "st_unknown"
                    self.log(self.tr("guard_block_doexit", tab=nazwa, t=0, status=self.tr(key)))
                    return
                zlecenie = self.__dict__.get("_zlecenia_w_kolejce", {}).get(nazwa)
                if zlecenie is not None:
                    odp = self._wolaj_zlecenie(zlecenie, "przed_doexit", nazwa)
                    kod, powod = odp if isinstance(odp, tuple) and len(odp) == 2 else \
                        ("blad", t("plugin %s nie odpowiedział", "plugin %s did not respond")
                         % zlecenie.get("wlasciciel"))
                    zlecenie["aktywne"] = (kod == "ok")
                    if kod != "ok":
                        if not self._mapa_ma_zaleglosc(nazwa):
                            self._proc_map_results.setdefault(nazwa, {})["result"] = "request_" + str(kod)
                            q.pomin(nazwa, powod)
                            self.log(t("[%s] bez restartu — %s", "[%s] no restart — %s") % (nazwa, powod))
                            return
                        self.log_warn(t("[%s] %s — restart tylko dla modów.",
                                        "[%s] %s — restart for the mods only.") % (nazwa, powod))
                m = q.mapa(nazwa)
                if m is not None and m.tryb == "pusto":
                    self.log(t("[%s] pusta mapa — restart od razu, bez ogłoszeń.",
                               "[%s] empty map — restart right away, no announcements.") % nazwa)
                self._checkpoint_procedure("doexit_armed", map=nazwa, command=akcja[2])
                self._wyslij_doexit(tab, akcja[2])

    def _wyslij_sonde(self, tab):
            nazwa = tab.name

            def cb(err, response):
                self.post_ui(lambda: self._wynik_sondy(nazwa, err, response))
            try:
                self._rcon_plugin().enqueue_raw(tab, "ListPlayers", cb, owner="automatic")
            except Exception as exc:
                self._wynik_sondy(nazwa, exc, None)

    def _wynik_sondy(self, nazwa, err, response):
            q = self.__dict__.get("_kolejka")
            if q is None:
                return
            if err:
                problem = self._rcon_connection_problem(err)
                if problem:
                    self._record_rcon_failure(nazwa, problem)
                    q.wynik_sondy(nazwa, "nieznane", None, time.time(), blad=problem)
                    return
                stan, liczba = "nieznane", None
                self.log(t("[%s] ListPlayers: błąd (%s) — zakładam, że są gracze.",
                           "[%s] ListPlayers: error (%s) — assuming there are players.") % (nazwa, err))
            else:
                self._clear_rcon_failure(nazwa)
                stan, liczba = parsuj_listplayers(response, self._wzorce_pusto())
                surowa = " ".join(str(response or "").split())[:160]
                opis = {"pusto": t("pusto", "empty"),
                        "gracze": t("graczy: %s", "players: %s") % liczba,
                        "nieznane": t("nierozpoznana odpowiedź — zakładam, że są gracze",
                                      "unrecognized response — assuming there are players")}[stan]
                self.log(t("[%s] ListPlayers → %s (odpowiedź serwera: \"%s\")",
                           "[%s] ListPlayers → %s (server response: \"%s\")") % (nazwa, opis, surowa))
                tab = self.tabs.get(nazwa)
                if tab is not None:
                    # Działająca odpowiedź RCON potwierdza żywy serwer (UNKNOWN → READY).
                    tab.confirm_ready_by_rcon()
            q.wynik_sondy(nazwa, stan, liczba, time.time())

    def _wyslij_linie(self, tab, indeks, cmd):
            nazwa = tab.name

            def cb(err):
                self.post_ui(lambda: self._wynik_linii(nazwa, indeks, cmd, err))
            try:
                self._rcon_enqueue(tab, cmd, cb)
            except Exception as exc:
                self._wynik_linii(nazwa, indeks, cmd, exc)

    def _wynik_linii(self, nazwa, indeks, cmd, err):
            q = self.__dict__.get("_kolejka")
            m = q.mapa(nazwa) if q is not None else None
            t = m.harmonogram[indeks]["t"] if m is not None and 0 <= indeks < len(m.harmonogram) else 0
            if err:
                self.log(self.tr("restart_line_err", tab=nazwa, t=t, r=3, err=err))
            else:
                self.log(self.tr("restart_line_send", tab=nazwa, t=t, cmd=cmd))
            if q is not None:
                q.wynik_komendy(nazwa, indeks, err, time.time())

    def _wyslij_doexit(self, tab, cmd):
            nazwa = tab.name
            self.__dict__.setdefault("_proc_map_results", {}).setdefault(nazwa, {}).update(
                identity=getattr(tab, "_monitor_identity", None), boot_seq=tab._boot_seq,
                ready_proof=tab.__dict__.get("_ready_proof"))

            def cb(err):
                self.post_ui(lambda: self._wynik_doexit(nazwa, cmd, err))
            try:
                self._rcon_enqueue(tab, cmd, cb)
            except Exception as exc:
                self._wynik_doexit(nazwa, cmd, exc)

    def _wynik_doexit(self, nazwa, cmd, err):
            q = self.__dict__.get("_kolejka")
            if q is None:
                return
            zlecenie = self.__dict__.get("_zlecenia_w_kolejce", {}).get(nazwa)
            if err and not getattr(err, "retry_safe", True) and zlecenie and zlecenie.get("aktywne"):
                host = self.__dict__.get("plugin_host")
                if host is not None and host.call_one(
                        zlecenie.get("wlasciciel", ""), "rozstrzygnij_doexit", nazwa,
                        lambda wynik: self._wynik_doexit(nazwa, cmd, wynik)):
                    return  # kolejka nadal czeka; bez ponownego wysyłania DoExit
            m = q.mapa(nazwa)
            offset = m.t_wyjscia if m is not None else 0
            wynik = self._proc_map_results.setdefault(nazwa, {"doexit_ok": False})
            q.wynik_doexit(nazwa, err, time.time())
            zlecenie = self.__dict__.get("_zlecenia_w_kolejce", {}).get(nazwa)
            if err:
                wynik["result"] = "deferred_rcon_error"
                self._record_rcon_failure(nazwa, self._rcon_connection_problem(err) or
                    t("DoExit niepotwierdzony — sprawdź RCON i stan mapy", "DoExit unconfirmed — check RCON and the map state"))
                self.log(self.tr("restart_line_err", tab=nazwa, t=offset, r=3, err=err))
                if zlecenie is not None and zlecenie.get("aktywne"):
                    zlecenie["aktywne"] = False
                    self._wolaj_zlecenie(zlecenie, "doexit_nieudany", nazwa)
                return
            wynik["doexit_ok"] = True
            self._clear_rcon_failure(nazwa)
            wynik["result"] = "awaiting_restart"
            self.log(self.tr("restart_line_send", tab=nazwa, t=offset, cmd=cmd))
            if zlecenie is not None and zlecenie.get("aktywne"):
                # Czas tego startu zawiera pracę pluginu (np. SteamCMD) — nie jest
                # pomiarem startu serwera i nie może psuć planowania kolejki.
                self.__dict__.setdefault("_bez_pomiaru_startu", set()).add(nazwa)
                self._wolaj_zlecenie(zlecenie, "po_doexit", nazwa)
            self._checkpoint_procedure("doexit_sent", map=nazwa, command=cmd)
            self._start_return_watch([nazwa])

    # -- czuwanie nad mapą, która startuje ------------------------------------------
    def mapa_w_restarcie(self, nazwa):
            """V3.86.2: mapa po udanym DoExit z kolejki, jeszcze nie z powrotem GOTOWA.

            Wtedy zniknięcie procesu to plan, nie pad (monitor procesów), OFFLINE nie
            jest na czerwono, a plugin CPU milczy do READY."""
            info = (self.__dict__.get("watch_maps") or {}).get(nazwa)
            return bool(info) and not info.get("done") and not info.get("failed")

    def _start_return_watch(self, map_names):
            self.watch_maps.clear()
            self.watch_t0 = time.time()
            try:
                wt_min = int(self.var_watch.get().strip() or DEFAULT_WATCH_TIMEOUT)
            except Exception:
                wt_min = DEFAULT_WATCH_TIMEOUT
            self.watch_deadline = self.watch_t0 + wt_min * 60
            for name in map_names:
                tab = self.tabs.get(name)
                if tab is None:
                    continue
                base_seq = self._proc_map_results.get(name, {}).get("boot_seq", tab._boot_seq)
                advanced = tab._boot_seq > base_seq
                self.watch_maps[name] = {"done": False, "failed": False, "tab": tab,
                                         "ready_t": 0.0, "departed": advanced,
                                         "new_boot": advanced, "boot_seq": base_seq,
                                         "ready_proof": self._proc_map_results.get(name, {}).get("ready_proof", tab.__dict__.get("_ready_proof")),
                                         "identity": self._proc_map_results.get(name, {}).get("identity", getattr(tab, "_monitor_identity", None))}
            self.watch_active = bool(self.watch_maps)
            if self.watch_active:
                self.log(self.tr("watch_armed", n=len(self.watch_maps)))

    def _tick_return_watch(self):
            if not self.watch_active:
                return
            q = self.__dict__.get("_kolejka")
            tabs = self.__dict__.get("tabs") or {}
            now = time.time()
            for name, info in list(self.watch_maps.items()):
                if info["done"] or info["failed"]:
                    continue
                tab = tabs.get(name, info["tab"])
                info["tab"] = tab
                status = tab._tail_status
                if self._new_boot_since(tab, info):
                    info["departed"] = True
                    info["new_boot"] = True
                elif status != "ready":
                    info["departed"] = True
                if self._ready_since(tab, info):
                    info["done"] = True
                    info["ready_t"] = now - self.watch_t0
                    self.log(self.tr("watch_map_ready", name=name, t="%ds" % int(info["ready_t"])))
                    self._verify_local_mods()
                    potwierdzona = not self._mapa_ma_zaleglosc(name)
                    if not potwierdzona:
                        self._oznacz_nieudana_probe(name)
                        self.log_warn(t("[%s] wróciła, ale nowa wersja moda nie została potwierdzona "
                                        "w logu serwera. Następna mapa rusza; tej samej wersji nie "
                                        "restartuję automatycznie drugi raz.",
                                        "[%s] is back, but the new mod version was not confirmed "
                                        "in the server log. The next map goes ahead; the same version "
                                        "is not restarted automatically a second time.") % name)
                    czas = None
                    if q is not None:
                        czas = q.zakoncz(name, potwierdzona,
                                         "" if potwierdzona else t("wersja niepotwierdzona po starcie",
                                                                  "version not confirmed after start"),
                                         now, wrocila=True)
                    if czas and name in self.__dict__.get("_bez_pomiaru_startu", ()):
                        self.log(t("[%s] start z aktualizacją serwera trwał %d s (nie zapisuję "
                                   "jako czasu startu).",
                                   "[%s] start with a server update took %d s (not stored as "
                                   "a start time).") % (name, int(czas)))
                    elif czas:
                        self._zapisz_czas_startu(name, czas)
                        self.log(t("[%s] start trwał %d s (zapamiętane do planowania kolejki).",
                                   "[%s] start took %d s (remembered for queue planning).")
                                 % (name, int(czas)))
                    self._checkpoint_procedure("map_verified" if potwierdzona else "map_unverified",
                                               map=name, command=None)
                elif now > self.watch_deadline:
                    info["failed"] = True
                    try:
                        wt_min = int(self.var_watch.get().strip() or DEFAULT_WATCH_TIMEOUT)
                    except Exception:
                        wt_min = DEFAULT_WATCH_TIMEOUT
                    self.log(self.tr("watch_timeout_map", name=name, m=wt_min))
                    self._oznacz_nieudana_probe(name)
                    identity = info.get("identity")
                    self._return_alarms()[name] = {"time": now, "minutes": wt_min,
                        "identity": list(identity) if identity else None, "boot_seq": info["boot_seq"],
                        "ready_proof": info.get("ready_proof")}
                    self._save_return_alarms()
                    self.log_warn(t("[%s] ALARM: mapa nie wróciła. Sprawdź managera i WIEDZA_O_PROGRAMIE/PADY; "
                                    "jeśli manager wyczerpał próby, potrzebna jest interwencja administratora. "
                                    "Refresher nie uruchamia serwera. Następna mapa rusza dalej.",
                                    "[%s] ALARM: map did not return. Check the manager and WIEDZA_O_PROGRAMIE/PADY; "
                                    "if the manager exhausted its attempts, administrator action is required. "
                                    "Refresher does not start the server. The next map goes ahead.") % name)
                    if q is not None:
                        q.zakoncz(name, False, t("nie wróciła w %d min", "did not come back within %d min") % wt_min,
                                  now, wrocila=False)
            for name in [n for n, info in self.watch_maps.items() if info["done"] or info["failed"]]:
                del self.watch_maps[name]
            self.watch_active = bool(self.watch_maps)

    # -- koniec procedury ------------------------------------------------------------
    def _opublikuj_kolejke(self):
            q = self.__dict__.get("_kolejka")
            plugin = self._coordinator_plugin()
            if q is None or plugin is None or not hasattr(plugin, "opublikuj"):
                return
            try:
                plugin.opublikuj(q.podsumowanie())
            except Exception:
                pass

    def _finish_coordinator(self, anulowano=False):
            """Koniec całej kolejki: podsumowanie, porządek, ewentualna kolejna tura."""
            q = self.__dict__.get("_kolejka")
            if q is not None:
                self._opublikuj_kolejke()
                for nazwa, stan, tryb, powod in q.podsumowanie():
                    opis = {"zrobiona": t("zrobiona", "done"), "nieudana": t("NIEUDANA", "FAILED"),
                            "pominieta": t("pominięta", "skipped")}.get(stan, stan)
                    self.log(t("[KOLEJKA] %s: %s%s", "[QUEUE] %s: %s%s")
                             % (nazwa, opis, (" — " + powod) if powod else ""))
            self._kolejka = None
            self.restart_active = False
            self.watch_active = False
            self.watch_maps.clear()
            self.__dict__.get("schedule", []).clear()
            # Zlecenia map z tej kolejki są wykonane (albo pominięte) — plugin
            # zleci ponownie, jeśli nadal trzeba. Zlecenia spoza kolejki czekają.
            zlecenia = self._zlecenia()
            for nazwa in self.__dict__.pop("_zlecenia_w_kolejce", {}) or {}:
                zlecenia.pop(nazwa, None)
            self.__dict__.pop("_bez_pomiaru_startu", None)
            if not anulowano:
                # Aktualizacja CF mogła przyjść w trakcie kolejki — osobna tura
                # z karencją, tylko dla nowego moda albo nowszego file ID.
                attempted = {str(p.get("mid")): int(p.get("fid", 0))
                             for p in self.__dict__.get("updated_mods", [])
                             if isinstance(p, dict) and str(p.get("fid", "0")).isdigit()}
                newer_pending = any(
                    str(p.get("mid")) not in attempted or
                    (str(p.get("fid", "0")).isdigit() and
                     int(p.get("fid", 0)) > attempted.get(str(p.get("mid")), -1))
                    for p in self.__dict__.get("pending_updates", [])
                    if isinstance(p, dict))
                if (newer_pending or zlecenia) and self.auto_rcon.get():
                    self._auto_next_t = time.time() + KARENCJA_PO_GOTOWY_S
                    self.log(self.tr("auto_kolejna"))
            self.__dict__.get("updated_mods", []).clear()
            for tab in self.__dict__.get("tabs", {}).values():
                tab.set_lines_editable(True)
            button = self.__dict__.get("btn_cancel")
            if button is not None:
                button.configure(state="disabled")
            self.log(self.tr("restart_cancel") if anulowano else self.tr("watch_done"))
            refresh = self._metoda_aplikacji("_refresh_pending_ui")
            if refresh:
                refresh()
            self.procedure_run = None
            self._persist_procedure_run()
            save = self._metoda_aplikacji("save_config")
            if save:
                save(silent=True)

    def cancel_restart(self):
            """Ręczne anulowanie (przycisk) — tu okienko jest na miejscu."""
            if not self.restart_active and not self.watch_active:
                return
            rcon_plugin = self._rcon_plugin()
            cancellation = (rcon_plugin.cancel_pending(self.tabs)
                            if rcon_plugin else {"ok": True, "inflight": ()})
            if not cancellation["ok"]:
                messagebox.showwarning(
                    self.tr("app_title"),
                    t("Nie można potwierdzić anulowania: komenda RCON jest już wysyłana dla map: %s. "
                      "Poczekaj na jej wynik; rozpoczętego wywołania sieciowego nie można cofnąć.",
                      "Cannot confirm the cancellation: an RCON command is already being sent for "
                      "maps: %s. Wait for its result; a network call that has started cannot be undone.")
                    % ", ".join(cancellation["inflight"]), parent=self)
                return
            q = self.__dict__.get("_kolejka")
            if q is not None:
                q.anuluj(t("anulowano ręcznie", "cancelled manually"))
            if not rcon_plugin:
                for tab in self.tabs.values():
                    self._rcon_flush(tab)
            self._finish_coordinator(anulowano=True)

    def build_mod_name_text(self):
            return "\n".join(p["name"] for p in self.updated_mods)
