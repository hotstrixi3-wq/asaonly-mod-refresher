# -*- coding: utf-8 -*-
"""V3.85: zlecenia restartu od pluginów przez PRAWDZIWĄ ścieżkę produkcyjną.

Prawdziwy PluginHost, prawdziwy plugin RCON (86), prawdziwe gniazda TCP.
Plugin testowy gra rolę „Aktualizacji serwera”: dostaje przed_doexit /
po_doexit / doexit_nieudany i zwalnia serwer dopiero po swojej „instalacji”.
"""
import time
import unittest

from symulacja.test_sciezka_produkcyjna import App, AtrapaRcon, Tab, zalegla


class PluginZlecen(object):
    nazwa = "test_zlecen"
    API = 1
    manager_visible = False
    required = False

    def __init__(self, odpowiedz=("ok", "")):
        self.odpowiedz = odpowiedz
        self.zdarzenia = []
        self.gotowe = set()

    def przed_doexit(self, mapa):
        self.zdarzenia.append(("przed_doexit", mapa))
        return self.odpowiedz

    def po_doexit(self, mapa):
        self.zdarzenia.append(("po_doexit", mapa))

    def doexit_nieudany(self, mapa):
        self.zdarzenia.append(("doexit_nieudany", mapa))


class ZleceniaRestartu(unittest.TestCase):
    def przebieg(self, plugin, pending=(), limit_s=20.0, czas_pracy_s=0.6):
        srv_a = AtrapaRcon("A", "pw", "No Players Connected")
        srv_b = AtrapaRcon("B", "pw", "No Players Connected")
        self.addCleanup(srv_a.zamknij)
        self.addCleanup(srv_b.zamknij)
        tab_a = Tab("A", srv_a.port, "pw", [(0, "ServerChat A"), (1, "DoExit")], ["111"])
        tab_b = Tab("B", srv_b.port, "pw", [(0, "DoExit")], ["111"])
        app = App([tab_a, tab_b], list(pending))
        app.plugin_host.plugins.append(plugin)
        przyjete = app.zlec_restart(["A", "Nieznana"], "aktualizacja serwera", plugin.nazwa)
        self.assertEqual(przyjete, ["A"])
        app._exec_pending()
        koniec = time.time() + limit_s
        powrot = None
        while (app.restart_active or app.watch_active) and time.time() < koniec:
            app.obsluz_ui()
            app._tick_restart_timeline()
            if powrot is None and "DoExit" in srv_a.komendy():
                tab_a._tail_status = "starting"
                # Manager podnosi serwer dopiero po „instalacji” pluginu.
                powrot = time.time() + czas_pracy_s
            if powrot is not None and time.time() >= powrot and tab_a._tail_status == "starting":
                tab_a._ready_proof = str(tab_a._boot_seq + 1); tab_a._ready_observed_at = time.time(); tab_a._boot_seq += 1
                tab_a._server_versions = {"111": "200"}
                tab_a._tail_status = "ready"
            time.sleep(0.02)
        app.obsluz_ui()
        self.assertFalse(app.restart_active)
        return app, srv_a, srv_b

    def test_mapa_ze_zleceniem_przechodzi_kolejke_bez_zaleglych_modow(self):
        plugin = PluginZlecen()
        app, srv_a, srv_b = self.przebieg(plugin)
        # Pusta mapa: bez ogłoszeń, sam DoExit; B nie ma zlecenia ani zaległości.
        self.assertEqual(srv_a.komendy(), ["ListPlayers", "DoExit"])
        self.assertEqual(srv_b.komendy(), [])
        self.assertEqual(plugin.zdarzenia, [("przed_doexit", "A"), ("po_doexit", "A")])
        # Start z pracą pluginu nie jest pomiarem startu serwera.
        self.assertNotIn("A", app.config_data["czasy_startu"])
        self.assertTrue(any("nie zapisuję" in x for x in app.logs))
        # Zlecenie wykonane — znika, kolejna tura go nie powtórzy.
        self.assertEqual(app._zlecenia(), {})
        self.assertEqual(app.procedure_run, None)

    def test_zbedne_zlecenie_to_brak_restartu(self):
        plugin = PluginZlecen(("zbedne", "serwer ma już build 2"))
        app, srv_a, _ = self.przebieg(plugin)
        self.assertEqual(srv_a.komendy(), ["ListPlayers"])          # żadnego DoExit
        self.assertEqual(plugin.zdarzenia, [("przed_doexit", "A")])
        self.assertTrue(any("bez restartu" in x and "build 2" in x for x in app.logs))
        self.assertEqual(app._zlecenia(), {})

    def test_odwolanie_zlecen_jednego_pluginu(self):
        tabs = [Tab(n, 1 + i, "pw", [(0, "DoExit")], ["111"]) for i, n in enumerate("ABC")]
        app = App(tabs, [])
        self.assertEqual(app.zlec_restart(["A", "C"], "x", "plugin1"), ["A", "C"])
        self.assertEqual(app.zlec_restart(["B"], "y", "plugin2"), ["B"])
        self.assertEqual(app.odwolaj_zlecenia("plugin1"), ["A", "C"])
        self.assertEqual(list(app._zlecenia()), ["B"])
        self.assertEqual(app.odwolaj_zlecenia("plugin1"), [])
        self.assertTrue(any("odwołane (plugin1): A, C" in x for x in app.logs))

    def test_blokada_pluginu_wstrzymuje_start_kolejki(self):
        class Blokada(object):
            nazwa = "test_blokady"
            API = 1
            manager_visible = False
            required = False
            powod = "trwa aktualizacja serwera mapy B"

            def blokada_kolejki(self):
                return self.powod
        srv = AtrapaRcon("A", "pw", "No Players Connected")
        self.addCleanup(srv.zamknij)
        app = App([Tab("A", srv.port, "pw", [(0, "DoExit")], ["111"])], [zalegla("111", "200", ["A"])])
        blokada = Blokada()
        app.plugin_host.plugins.append(blokada)
        app._exec_pending()
        self.assertFalse(app.restart_active)
        self.assertIsNotNone(app._auto_next_t)                        # automat spróbuje za minutę
        self.assertTrue(any("Kolejka restartów czeka — trwa aktualizacja serwera mapy B" in x
                            for x in app.logs))
        ile = len(app.logs)
        app._exec_pending()                                           # ten sam powód — cisza
        self.assertFalse(any("czeka" in x for x in app.logs[ile:]))
        self.assertEqual(srv.komendy(), [])
        blokada.powod = None
        app._exec_pending()
        self.assertTrue(app.restart_active)
        app._kolejka.anuluj("test")
        app._finish_coordinator(anulowano=True)

    def test_blad_pluginu_przy_zaleglym_modzie_restart_tylko_dla_modow(self):
        plugin = PluginZlecen(("blad", "manager nie działa"))
        app, srv_a, _ = self.przebieg(plugin, pending=[zalegla("111", "200", ["A"])])
        self.assertEqual(srv_a.komendy(), ["ListPlayers", "DoExit"])
        self.assertEqual(plugin.zdarzenia, [("przed_doexit", "A")])  # bez po_doexit
        self.assertTrue(any("restart tylko dla modów" in x for x in app.logs))
        self.assertEqual(app.pending_updates, [])                    # mod zaktualizowany
        self.assertIn("A", app.config_data["czasy_startu"])          # zwykły start = pomiar


if __name__ == "__main__":
    unittest.main(verbosity=2)
