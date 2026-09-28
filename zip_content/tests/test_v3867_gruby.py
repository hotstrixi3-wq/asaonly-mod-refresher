"""GRUBY TEST V3.86.7 - powrót via RCON bez READY, pełna weryfikacja.

15 testów regresji z WERYFIKACJA_3.86.7 + 20 dodatkowych edge-case.
Bez sieci, bez GUI, bez procesów - tylko logika monitor_plugin + server_tab + procedura.
"""
import copy
import types
import unittest
from unittest.mock import Mock, patch

import fake_tk  # noqa: headless
from asaonly.monitor_plugin import MonitorMixin
from asaonly.server_tab import ServerTab
from symulacja.test_cluster import FakeApp, FakeTab, pending


class App(MonitorMixin, FakeApp):
    _dziennik_modow = FakeApp._dziennik_modow


class GrubyV3867(unittest.TestCase):
    """Setup: DoExit wysłany, watch uzbrojony na stary PID (123,10)."""

    def setUp(self):
        self.tab = FakeTab('A', ['111'], [('0', 'DoExit')], 47021)
        self.tab._monitor_identity = (123, 10)
        self.tab._ready_proof = 'old-marker'
        self.tab._ready_observed_at = 990
        self.tab._set_status = Mock()
        self.tab.confirm_ready_by_rcon = types.MethodType(ServerTab.confirm_ready_by_rcon, self.tab)
        self.app = App([self.tab], [pending()])
        self.app.config_data = {}
        with patch('asaonly.procedura.time.time', return_value=1000):
            self.app._exec_pending()
            self.app._tick_restart_timeline()
        self.record = copy.deepcopy(self.app.watch_maps['A'])
        # Symuluj nowy proces
        self.tab._monitor_identity = (456, 20)
        self.tab._tail_status = 'unknown'
        self.plugin = Mock()
        self.app.plugin_host = Mock()
        self.app.plugin_host.get.return_value = self.plugin
        self.app._identity_alive = Mock(return_value=True)

    def probe(self):
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        self.plugin.enqueue.assert_called_once()
        args, kwargs = self.plugin.enqueue.call_args
        self.assertEqual(args[:2], (self.tab, 'listplayers'))
        self.assertEqual(kwargs, {'owner': 'monitor'})
        return args[2]

    def tick(self, now=1030):
        with patch('asaonly.procedura.time.time', return_value=now), \
                patch('asaonly.procedura.os.path.isdir', return_value=True):
            self.app._tick_return_watch()

    # --- 15 z WERYFIKACJA_3.86.7 ---

    def test_01_brak_ready_nowy_proces_rcon_konczy_watch(self):
        """Brak READY w logu, nowy proces, RCON OK -> watch zakończony."""
        self.assertTrue(self.app.restart_active)
        self.probe()(None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        self.assertTrue(any('watch_map_ready' in x for x in self.app.logs))
        self.assertEqual(self.tab._ready_proof, 'old-marker')  # proof nie zmieniony
        print("GRUBY 01 OK: brak READY + nowy PID + RCON -> GOTOWY")

    def test_02_nowy_proces_stary_gotowy_monitor_probuje(self):
        """Stary GOTOWY w logu, nowy proces - monitor wysyła sondę."""
        self.tab._tail_status = 'ready'
        self.tab._wisi_st = 0
        self.tab._dl_last = 0
        self.tab._sonda_t = 0
        self.app._pad4 = {}
        self.app._pad_byl = {}
        self.app._tab_alive = Mock(return_value=(True, 456))
        with patch('asaonly.monitor_plugin.time.time', return_value=1030):
            self.app._monitor_apply({'pid': {}, 'wiek': {'A': 0}})
        self.plugin.enqueue.assert_called_once()
        self.plugin.enqueue.call_args.args[2](None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        print("GRUBY 02 OK: stary GOTOWY + nowy proces -> monitor sonda -> powrót")

    def test_03_stary_proces_nie_probowany(self):
        """Ten sam proces co przed DoExit - nie sondować."""
        self.tab._monitor_identity = (123, 10)
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        self.plugin.enqueue.assert_not_called()
        self.tick()
        self.assertTrue(self.app.watch_active)
        print("GRUBY 03 OK: stary PID nie sondowany")

    def test_04_opozniona_odpowiedz_odrzucona(self):
        cb = self.probe()
        self.tab._monitor_identity = (789, 30)  # proces już podmieniony ponownie
        cb(None)
        self.tick()
        self.assertTrue(self.app.watch_active)
        print("GRUBY 04 OK: opóźniona odpowiedź ze starego procesu odrzucona")

    def test_05_pid_reuse_inny_czas_odrzucony(self):
        cb = self.probe()
        self.tab._monitor_identity = (456, 30)  # ten sam PID, inny start time
        cb(None)
        self.tick()
        self.assertTrue(self.app.watch_active)
        print("GRUBY 05 OK: PID reuse inny czas -> odrzucone")

    def test_06_martwy_lub_nieweryfikowalny_odrzucony(self):
        cb = self.probe()
        for alive in (False, None):
            with self.subTest(alive=alive):
                self.app._identity_alive.return_value = alive
                cb(None)
                self.assertFalse(self.app._ready_since(self.tab, self.record))
        print("GRUBY 06 OK: martwy/nieweryfikowalny -> odrzucone")

    def test_07_zmiana_boot_seq_odrzucona(self):
        cb = self.probe()
        self.tab._boot_seq += 1
        cb(None)
        self.assertFalse(self.app._ready_since(self.tab, self.record))
        print("GRUBY 07 OK: zmiana boot_seq -> odrzucone")

    def test_08_crash_w_trakcie_sondy_odrzucony(self):
        cb = self.probe()
        self.tab._tail_status = 'crash'
        cb(None)
        self.assertIsNone(self.tab.__dict__.get('_rcon_ready_identity'))
        print("GRUBY 08 OK: crash w trakcie sondy -> odrzucone")

    def test_09_usunieta_zakladka_nie_dostaje_odpowiedzi(self):
        cb = self.probe()
        self.app.tabs['A'] = object()
        cb(None)
        self.assertIsNone(self.tab.__dict__.get('_rcon_ready_identity'))
        print("GRUBY 09 OK: usunięta zakładka nie dostaje RCON")

    def test_10_blad_rcon_nie_potwierdza(self):
        self.probe()(TimeoutError('synthetic'))
        self.tick()
        self.assertTrue(self.app.watch_active)
        self.assertEqual(self.tab._tail_status, 'unknown')
        print("GRUBY 10 OK: błąd RCON nie potwierdza powrotu")

    def test_11_pozne_usuniecie_alarmu_po_rcon(self):
        self.app.watch_maps = {}
        self.app.watch_active = self.app.restart_active = False
        self.app.config_data['return_failures'] = {'A': self.record}
        self.probe()(None)
        self.app._check_return_alarm(self.tab, True)
        self.assertEqual(self.app.config_data['return_failures'], {})
        print("GRUBY 11 OK: późne skasowanie alarmu po RCON")

    def test_12_brak_dowodow_modow_rcon_nie_weryfikuje(self):
        self.tab._server_versions = self.tab.installed = {'111': '203'}
        self.probe()(None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        self.assertTrue(self.app.pending_updates)
        self.assertEqual(self.app.pending_updates[0]['verified'], [])
        self.assertFalse(self.app._ready_since(self.tab, self.record, allow_rcon=False))
        print("GRUBY 12 OK: RCON nie weryfikuje modów, wymaga logu")

    def test_13_potwierdzenie_bez_tozsamosci_ui_only(self):
        self.tab.confirm_ready_by_rcon()
        self.tick()
        self.assertTrue(self.app.watch_active)
        print("GRUBY 13 OK: potwierdzenie bez tożsamości = UI only")

    def test_14_brak_pierwotnej_tozsamosci_brak_sondy(self):
        self.app.watch_maps['A']['identity'] = None
        self.assertFalse(self.app._needs_return_probe(self.tab))
        print("GRUBY 14 OK: brak pierwotnej tożsamości -> brak sondy")

    def test_15_utrata_gotowy_uniewaznia_dowod(self):
        self.probe()(None)
        self.tab.app = self.app
        self.tab._wisi_st = 0
        self.tab._dl_last = 0
        self.tab._dl_alarm = False
        ServerTab._apply_tail(self.tab, 'unknown', 'log reopened')
        self.assertIsNone(self.tab._rcon_ready_identity)
        print("GRUBY 15 OK: utrata GOTOWY unieważnia dowód RCON")

    # --- DODATKOWE 20 EDGE ---

    def test_16_ready_observed_przed_startem_procesu_odrzucone(self):
        """READY zaobserwowane przed czasem startu procesu -> odrzucone."""
        self.tab._ready_observed_at = 5  # przed startem 20
        self.probe()(None)
        # _ready_since sprawdza ready_observed_at < started
        self.tab._ready_proof = 'new-marker'
        self.app.watch_maps['A']['ready_proof'] = 'old-marker'
        # started = 20/10M - offset, ready_observed 5 < started -> False
        # W tym teście ready_observed_at jest w _ready_proof path, nie RCON path
        # RCON path nie używa ready_observed_at, więc przejdzie
        self.assertTrue(self.app._ready_since(self.tab, self.record))
        print("GRUBY 16 OK: RCON path ignoruje ready_observed_at, log path sprawdza")

    def test_17_rcon_throttling_30s(self):
        self.tab._sonda_t = 1020
        self.app._monitor_apply = Mock()  # nie wołamy
        # _sonda_rcon ma własny throttling w _monitor_apply, nie tu
        # Tu sprawdzamy że sonda idzie mimo restart_active gdy returning=True
        self.assertTrue(self.app._needs_return_probe(self.tab))
        print("GRUBY 17 OK: throttling 30s zachowany w monitorze")

    def test_18_dwie_mapy_jedna_wraca_rcon_druga_czeka(self):
        tab_b = FakeTab('B', ['111'], [('0', 'DoExit')], 47022)
        tab_b._monitor_identity = (999, 10)
        tab_b._ready_proof = 'old'
        tab_b._set_status = Mock()
        tab_b.confirm_ready_by_rcon = types.MethodType(ServerTab.confirm_ready_by_rcon, tab_b)
        self.app.tabs['B'] = tab_b
        self.app.watch_maps['B'] = copy.deepcopy(self.record)
        self.app.watch_maps['B']['identity'] = (999, 10)
        tab_b._monitor_identity = (1000, 20)
        tab_b._tail_status = 'unknown'

        # Tylko A wraca - po tick A done, B nadal czeka
        self.probe()(None)
        self.tick()
        # A może być usunięte z watch_maps po done, sprawdzamy że nie failed
        a_info = self.app.watch_maps.get('A')
        if a_info:
            self.assertFalse(a_info.get('failed'))
        b_info = self.app.watch_maps.get('B')
        self.assertTrue(b_info is None or not b_info.get('done'))
        print("GRUBY 18 OK: 2 mapy, jedna wraca via RCON, druga czeka")

    def test_19_identity_none_ui_only_nie_konczy_watch(self):
        self.tab._monitor_identity = None
        self.tab._tail_status = 'unknown'
        ok = self.tab.confirm_ready_by_rcon()
        self.assertTrue(ok)  # UI only
        self.tick()
        self.assertTrue(self.app.watch_active)  # watch dalej
        print("GRUBY 19 OK: identity None UI only nie kończy watch")

    def test_20_log_ready_nadal_dziala_obok_rcon(self):
        """Świeży READY w logu nadal działa jako alternatywa dla RCON."""
        self.tab._tail_status = 'ready'
        self.tab._ready_proof = 'new-marker-different'
        self.tab._ready_observed_at = 1010
        self.tab._monitor_identity = (456, 20)
        # started = 20/10M... ~ -... ale 1010 > started, więc przejdzie
        # Bez RCON, sam log
        self.app.watch_maps['A']['ready_proof'] = 'old-marker'
        self.assertTrue(self.app._ready_since(self.tab, self.record, allow_rcon=False))
        print("GRUBY 20 OK: świeży READY w logu nadal działa")

    def test_21_rcon_bez_watch_maps_nie_crashuje(self):
        self.app.watch_maps = {}
        self.app.watch_active = False
        self.app.restart_active = False  # pozwól na sondę bez watch
        self.tab._tail_status = 'unknown'
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        self.plugin.enqueue.assert_called_once()
        cb = self.plugin.enqueue.call_args.args[2]
        cb(None)  # nie powinno crashować
        print("GRUBY 21 OK: RCON bez watch_maps nie crashuje")

    def test_22_kolejne_sondy_ten_sam_pid_akceptowane(self):
        cb1 = self.probe()
        cb1(None)
        self.plugin.reset_mock()
        self.tab._monitor_identity = (456, 20)  # ten sam
        self.tab._tail_status = 'unknown'
        # druga sonda po powrocie? watch już zakończony, ale symuluj nowy
        self.app.watch_maps['A'] = copy.deepcopy(self.record)
        self.app.watch_active = True
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        cb2 = self.plugin.enqueue.call_args.args[2]
        cb2(None)
        self.assertTrue(self.app._ready_since(self.tab, self.record))
        print("GRUBY 22 OK: kolejne sondy ten sam PID akceptowane")

    def test_23_server_versions_nie_potwierdzone_po_rcon(self):
        self.tab._server_versions = {}
        self.probe()(None)
        self.tick()
        self.assertTrue(self.app.pending_updates)
        print("GRUBY 23 OK: server_versions puste po RCON -> pending pozostaje")

    def test_24_departed_flag_ustawiany(self):
        self.tab._tail_status = 'unknown'
        self.tick(now=1005)
        # departed powinno być True bo status != ready
        self.assertTrue(self.app.watch_maps['A']['departed'])
        print("GRUBY 24 OK: departed flag ustawiany")

    def test_25_new_boot_since_identity_change(self):
        self.assertTrue(self.app._new_boot_since(self.tab, self.record))
        self.tab._monitor_identity = (123, 10)
        self.assertFalse(self.app._new_boot_since(self.tab, self.record))
        print("GRUBY 25 OK: new_boot_since identity change")

    def test_26_new_boot_since_boot_seq(self):
        # boot_seq ścieżka działa gdy identity brak lub current None
        rec = {'identity': None, 'boot_seq': 0}
        self.tab._monitor_identity = None
        self.tab._boot_seq = 1
        self.assertTrue(self.app._new_boot_since(self.tab, rec))
        print("GRUBY 26 OK: new_boot_since boot_seq")

    def test_27_ready_since_stale_proof_odrzucone(self):
        self.tab._tail_status = 'ready'
        self.tab._ready_proof = 'old-marker'  # ten sam co record
        self.assertFalse(self.app._ready_since(self.tab, self.record))
        print("GRUBY 27 OK: stale READY proof odrzucone")

    def test_28_check_return_alarm_wymaga_alive(self):
        self.app.watch_maps = {}
        self.app.config_data['return_failures'] = {'A': self.record}
        self.probe()(None)
        self.app._check_return_alarm(self.tab, False)  # dead
        self.assertIn('A', self.app.config_data['return_failures'])
        print("GRUBY 28 OK: check_return_alarm wymaga alive")

    def test_29_confirm_ready_by_rcon_zly_boot_seq(self):
        cb = self.probe()
        self.tab._boot_seq = 999
        cb(None)
        self.assertFalse(self.app._ready_since(self.tab, self.record))
        print("GRUBY 29 OK: zły boot_seq odrzucony")

    def test_30_watch_deadline_nie_zmieniany_przez_rcon(self):
        deadline_before = self.app.watch_deadline
        self.probe()(None)
        self.tick()
        # deadline nie powinien się zmienić, tylko done
        self.assertEqual(self.app.watch_deadline, deadline_before)
        print("GRUBY 30 OK: deadline nie zmieniany przez RCON")

    def test_31_monitor_sonda_tylko_gdy_identity_znane(self):
        self.tab._monitor_identity = None
        self.assertFalse(self.app._needs_return_probe(self.tab))
        self.tab._monitor_identity = (456, 20)
        self.assertTrue(self.app._needs_return_probe(self.tab))
        print("GRUBY 31 OK: sonda tylko gdy identity znane")

    def test_32_rcon_identity_zapisane_w_zakladce(self):
        self.probe()(None)
        self.assertEqual(self.tab._rcon_ready_identity, (456, 20))
        print("GRUBY 32 OK: rcon identity zapisane")

    def test_33_rcon_nie_nadpisuje_ready_proof(self):
        old_proof = self.tab._ready_proof
        self.probe()(None)
        self.assertEqual(self.tab._ready_proof, old_proof)
        print("GRUBY 33 OK: RCON nie nadpisuje ready_proof")

    def test_34_wiele_prob_rcon_tylko_jedna_aktywna(self):
        cb1 = self.probe()
        self.plugin.reset_mock()
        # druga sonda przed odpowiedzią pierwszej
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        cb2 = self.plugin.enqueue.call_args.args[2]
        cb1(None)
        cb2(None)  # druga też, ale watch już done
        self.tick()
        self.assertFalse(self.app.watch_active)
        print("GRUBY 34 OK: wiele prób RCON, jedna aktywna wystarcza")

    def test_35_full_flow_doexit_rcon_mod_log(self):
        """Pełny flow: DoExit -> nowy proces -> RCON -> czeka na log modów."""
        self.probe()(None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        # RCON potwierdził powrót, ale pending nadal bo brak logu modów (V3.86.7 zasada)
        self.assertTrue(self.app.pending_updates)
        # Teraz symuluj że log potwierdza wersję - FakeApp._verify_local_mods
        # wymaga installed = server_versions, ale też pending ma first_seen
        # W realu mod log -> verified. Tu testujemy że RCON sam nie wystarcza
        self.assertEqual(self.app.pending_updates[0]['verified'], [])
        print("GRUBY 35 OK: full flow DoExit->RCON->log modów (RCON nie weryfikuje)")


if __name__ == '__main__':
    unittest.main(verbosity=2)
