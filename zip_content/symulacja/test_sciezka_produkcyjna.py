# -*- coding: utf-8 -*-
"""V3.81: procedura przez PRAWDZIWĄ ścieżkę produkcyjną.

W przeciwieństwie do test_cluster.py (FakeApp bez hosta pluginów — gałąź
„wyłącznie dla symulacji”) ten test używa:
  * prawdziwego PluginHost ładującego katalog PLUGINY,
  * prawdziwego pluginu 86 (kolejki RCON, właściciele, retry, rcon_send),
  * prawdziwego pluginu 50 (kafelek stanu kolejki),
  * prawdziwych gniazd TCP — atrapa serwera Source RCON na 127.0.0.1.
Czas płynie naprawdę (harmonogramy w sekundach), a pętla testu gra rolę
wątku UI: odbiera callbacki z kolejki post_ui, tak jak Tk w programie.
"""
import pathlib
import queue
import socket
import struct
import threading
import time
import unittest

from asaonly.pluginy import PluginHost
from asaonly.procedura import ProcedureMixin

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Atrapa serwera Source RCON (protokół jak ASA: auth typ 3 → odpowiedź typ 2)
# --------------------------------------------------------------------------
class AtrapaRcon(object):
    def __init__(self, nazwa, haslo, listplayers, port=0):
        self.nazwa = nazwa
        self.haslo = haslo
        self.listplayers = listplayers
        self.odebrane = []            # [(czas, komenda)]
        self.lock = threading.Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        threading.Thread(target=self._accept, daemon=True).start()

    def zamknij(self):
        self._stop = True
        try:
            self.sock.close()
        except Exception:
            pass

    def komendy(self):
        with self.lock:
            return [c for _, c in self.odebrane]

    def _accept(self):
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._obsluz, args=(conn,), daemon=True).start()

    @staticmethod
    def _recvn(conn, n):
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return data

    @staticmethod
    def _wyslij(conn, rid, typ, body):
        payload = struct.pack("<ii", rid, typ) + body.encode("utf-8") + b"\x00\x00"
        conn.sendall(struct.pack("<i", len(payload)) + payload)

    def _obsluz(self, conn):
        try:
            while True:
                size = struct.unpack("<i", self._recvn(conn, 4))[0]
                data = self._recvn(conn, size)
                rid, typ = struct.unpack("<ii", data[:8])
                body = data[8:].rstrip(b"\x00").decode("utf-8", "replace")
                if typ == 3:
                    self._wyslij(conn, rid if body == self.haslo else -1, 2, "")
                    continue
                with self.lock:
                    self.odebrane.append((time.time(), body))
                if body.lower() == "listplayers":
                    self._wyslij(conn, rid, 0, self.listplayers)
                elif body.lower().startswith("doexit"):
                    self._wyslij(conn, rid, 0, "Exiting...")
                else:
                    self._wyslij(conn, rid, 0, "Server received, But no response!!")
        except (ConnectionError, OSError, struct.error):
            pass
        finally:
            conn.close()


# --------------------------------------------------------------------------
# Minimalny tab i aplikacja — procedura z asaonly/procedura.py bez zmian
# --------------------------------------------------------------------------
class Var(object):
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Tab(object):
    def __init__(self, name, port, haslo, linie, mody):
        self.name = name
        self.var_map_on = Var(True)
        self.var_ip = Var("127.0.0.1")
        self.var_port = Var(str(port))
        self.var_pass = Var(haslo)
        self.var_log = Var(name)
        self.rows = [{"time": str(t), "cmd": c, "on": True} for t, c in linie]
        self.mods = list(mody)
        self._tail_status = "ready"
        self._boot_seq = 0
        self._server_versions = {}
        self.installed = {}
        self.editable = True

    def get_effective_mod_ids(self):
        return list(self.mods)

    def set_lines_editable(self, value):
        self.editable = value

    def confirm_ready_by_rcon(self):
        if self._tail_status == "unknown":
            self._tail_status = "ready"
            return True
        return False


class Button(object):
    def configure(self, **kw):
        pass


class App(ProcedureMixin):
    def __init__(self, tabs, pending, czasy_startu=None):
        self.tabs = {t.name: t for t in tabs}
        self.pending_updates = list(pending)
        self.config_data = {"plugins": {}, "czasy_startu": dict(czasy_startu or {})}
        self.restart_active = False
        self.watch_active = False
        self.watch_maps = {}
        self.schedule = []
        self._proc_incidents = set()
        self._proc_map_results = {}
        self._auto_next_t = None
        self.updated_mods = []
        self.restart_t0 = None
        self.btn_cancel = Button()
        self.auto_rcon = Var(True)
        self.var_watch = Var("1")
        self.known_versions = {}
        self.mod_latest = {}
        self.mod_names = {}
        self.mod_states = {}
        self.monitor_off = set()
        self.is_admin = True
        self.procedure_run = None
        self.logs = []
        self._ui = queue.Queue()
        self.plugin_host = PluginHost(self, str(ROOT / "PLUGINY"))
        self.plugin_host.load_all()
        self.plugin_host.start_all()

    # interfejs aplikacji używany przez procedurę i hosta pluginów
    def tr(self, key, **kw):
        return key + (" " + " ".join("%s=%s" % x for x in sorted(kw.items())) if kw else "")

    def log(self, msg, tag=None):
        self.logs.append(str(msg))

    def log_warn(self, msg):
        self.logs.append("WARN " + str(msg))

    def post_ui(self, cb):
        self._ui.put(cb)

    def run_async(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def request_save(self):
        pass

    def save_config(self, silent=False):
        return True

    def save_procedure_state(self):
        return True

    def _dziennik_modow(self):
        pass

    def _refresh_pending_ui(self):
        pass

    def _set_mod_state(self, *a):
        pass

    def _mods_dir_for_tab(self, tab):
        return None

    def _installed_file_ids(self, path):
        return []

    def obsluz_ui(self):
        while True:
            try:
                cb = self._ui.get_nowait()
            except queue.Empty:
                return
            cb()


def zalegla(mid, fid, cele):
    return {"mid": mid, "name": "Mod " + mid, "fid": fid,
            "targets": list(cele), "verified": [], "qualified": True}


class SciezkaProdukcyjna(unittest.TestCase):
    CZAS_STARTU_S = 0.4

    def uruchom(self, konfiguracja, pending, czasy_startu=None, limit_s=25.0):
        """konfiguracja: [(nazwa, odpowiedź ListPlayers, linie)]."""
        serwery = {}
        tabs = []
        for nazwa, odp, linie in konfiguracja:
            srv = AtrapaRcon(nazwa, "pw", odp)
            serwery[nazwa] = srv
            tabs.append(Tab(nazwa, srv.port, "pw", linie, ["111"]))
        self.addCleanup(lambda: [s.zamknij() for s in serwery.values()])
        app = App(tabs, pending, czasy_startu)
        rcon = app.plugin_host.get("rcon_admin")
        self.assertIsNotNone(rcon, "plugin 86 musi być załadowany")
        self.assertTrue(hasattr(rcon, "enqueue_raw"))

        app._exec_pending()
        self.assertTrue(app.restart_active)
        widziane_doexit = set()
        w_starcie = {}            # nazwa -> czas końca startu
        naraz = []
        t_konca = time.time() + limit_s
        while (app.restart_active or app.watch_active) and time.time() < t_konca:
            app.obsluz_ui()
            app._tick_restart_timeline()
            now = time.time()
            for nazwa, srv in serwery.items():
                if nazwa not in widziane_doexit and any(
                        c.lower().startswith("doexit") for c in srv.komendy()):
                    widziane_doexit.add(nazwa)
                    naraz.append(len(w_starcie))
                    tab = app.tabs[nazwa]
                    tab._tail_status = "starting"
                    w_starcie[nazwa] = now + self.CZAS_STARTU_S
            for nazwa, koniec in list(w_starcie.items()):
                if now >= koniec:
                    del w_starcie[nazwa]
                    tab = app.tabs[nazwa]
                    tab._ready_proof = "ready-" + str(time.time_ns())
                    tab._ready_observed_at = time.time()
                    tab._boot_seq += 1
                    tab._server_versions = {"111": "200"}
                    tab._tail_status = "ready"
            time.sleep(0.02)
        app.obsluz_ui()
        self.assertFalse(app.restart_active, "kolejka nie skończyła się w %ss" % limit_s)
        # Nigdy dwa starty naraz: w chwili każdego DoExit żadna mapa nie startuje.
        self.assertEqual(naraz, [0] * len(naraz))
        return app, serwery

    def test_puste_bez_ogloszen_z_graczami_pelny_harmonogram(self):
        konfig = [
            ("A", "No Players Connected", [(0, "ServerChat A"), (1, "DoExit")]),
            ("B", "0. Magus, 0002a1b2c3d4", [(0, "ServerChat B za 2 s"), (2, "DoExit")]),
            ("C", "No Players Connected", [(3, "SaveWorld"), (4, "ServerChat C"), (5, "DoExit")]),
        ]
        app, srv = self.uruchom(konfig, [zalegla("111", "200", ["A", "B", "C"])])
        # Odpowiedź młodsza niż 30 s nie jest powtarzana przed DoExit/ogłoszeniami.
        self.assertEqual(srv["A"].komendy(), ["ListPlayers", "DoExit"])
        self.assertEqual(srv["C"].komendy(), ["ListPlayers", "SaveWorld", "DoExit"])
        self.assertEqual(srv["B"].komendy(), ["ListPlayers", "ServerChat B za 2 s", "DoExit"])
        self.assertEqual(app.pending_updates, [])
        self.assertEqual(app.known_versions, {"111": "200"})
        # Surowa odpowiedź serwera trafia do dziennika (do potwierdzenia wzorca ASA).
        self.assertTrue(any("No Players Connected" in x and "[A] ListPlayers" in x for x in app.logs))
        # Zmierzone czasy startu zapisane do planowania kolejnych kolejek.
        self.assertEqual(set(app.config_data["czasy_startu"]), {"A", "B", "C"})

    def test_nierozpoznana_odpowiedz_to_gracze(self):
        konfig = [("A", "Server received, But no response!!",
                   [(0, "ServerChat A"), (1, "DoExit")])]
        app, srv = self.uruchom(konfig, [zalegla("111", "200", ["A"])])
        # „Nieznane” nie jest świeżą pewnością — sonda powtórzona przed ogłoszeniami.
        self.assertEqual(srv["A"].komendy(), ["ListPlayers", "ListPlayers", "ServerChat A", "DoExit"])
        self.assertTrue(any("nierozpoznana odpowiedź" in x for x in app.logs))

    def test_ostrzezenie_o_przesunieciu_ze_starego_zegara(self):
        # Zapis sprzed 3.81 (wspólny zegar): pierwsza linia po 185 s. Odstępy
        # komunikatów są poprawne, ale program podpowiada, że czekanie jest zbędne.
        srv = AtrapaRcon("A", "pw", "0. Gracz, 0002")
        self.addCleanup(srv.zamknij)
        tab = Tab("A", srv.port, "pw", [(185, "ServerChat za 15 min"), (1080, "DoExit")], ["111"])
        app = App([tab], [zalegla("111", "200", ["A"])])
        app._exec_pending()
        self.assertTrue(app.restart_active)
        self.assertTrue(any("pierwsza linia harmonogramu dopiero po 185s" in x for x in app.logs))
        app._kolejka.anuluj("test")
        app._finish_coordinator(anulowano=True)
        self.assertFalse(app.restart_active)

    def test_kontrola_czasu_przewiduje_dokladnie_te_mapy_ktore_procedura_pominie(self):
        # V3.82: BŁĄD w kontroli = mapa pominięta przez PRAWDZIWĄ procedurę.
        from asaonly import kontrola
        konfig = {
            "OK": (27101, [(0, "ServerChat za 1 min"), (60, "DoExit")]),
            "PolWiersza": (27102, [(10, ""), (20, "DoExit")]),
            "BezDoExit": (27103, [(0, "ServerChat samo ogloszenie")]),
            "Port1": (27104, [(0, "DoExit")]),
            "Port2": (27104, [(0, "DoExit")]),
            "Pusta": (27105, [("", "")]),
        }
        tabs = []
        for nazwa, (port, linie) in konfig.items():
            tab = Tab(nazwa, port, "pw", [], ["111"])
            tab.rows = [{"time": str(t), "cmd": c, "on": True} for t, c in linie]
            tabs.append(tab)
        wejscie = [kontrola.MapaWe(t.name, True, t.var_ip.get(), t.var_port.get(), t.rows)
                   for t in tabs]
        _, wynik = kontrola.sprawdz_klaster(wejscie)
        przewidziane = {n for n, (u, linie) in wynik.items() if linie is None}
        app = App(tabs, [zalegla("111", "200", list(konfig))])
        app._exec_pending()
        pominiete = {n for n, r in app._proc_map_results.items()
                     if str(r.get("result", "")).startswith("deferred")}
        self.assertEqual(przewidziane, {"PolWiersza", "BezDoExit", "Port1", "Port2", "Pusta"})
        self.assertEqual(pominiete, przewidziane)
        self.assertEqual(app._kolejka.aktywne_nazwy(), ["OK"])
        app._kolejka.anuluj("test")
        app._finish_coordinator(anulowano=True)

    def test_zle_haslo_jednej_mapy_nie_zatrzymuje_klastra(self):
        # Mapa A ma złe hasło w tabie: RCON odrzuci auth, retry 3× co 2 s.
        pending = [zalegla("111", "200", ["A", "B"])]
        srv_a = AtrapaRcon("A", "inne", "No Players Connected")
        srv_b = AtrapaRcon("B", "pw", "No Players Connected")
        self.addCleanup(srv_a.zamknij)
        self.addCleanup(srv_b.zamknij)
        tab_a = Tab("A", srv_a.port, "pw", [(0, "DoExit")], ["111"])
        tab_b = Tab("B", srv_b.port, "pw", [(0, "DoExit")], ["111"])
        app = App([tab_a, tab_b], pending)
        app._exec_pending()
        koniec = time.time() + 30
        boot = None
        while (app.restart_active or app.watch_active) and time.time() < koniec:
            app.obsluz_ui()
            app._tick_restart_timeline()
            if boot is None and "DoExit" in srv_b.komendy():
                tab_b._tail_status = "starting"
                boot = time.time() + 0.3
            if boot is not None and time.time() >= boot and tab_b._tail_status == "starting":
                tab_b._ready_proof = "ready-" + str(time.time_ns())
                tab_b._ready_observed_at = time.time()
                tab_b._boot_seq += 1
                tab_b._server_versions = {"111": "200"}
                tab_b._tail_status = "ready"
            time.sleep(0.02)
        app.obsluz_ui()
        self.assertFalse(app.restart_active)
        self.assertEqual(srv_a.komendy(), [])              # auth odrzucony — nic nie dotarło
        self.assertEqual(srv_b.komendy()[-1], "DoExit")    # B przeszła mimo awarii A
        self.assertEqual(app.pending_updates[0]["verified"], ["B"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
