"""Return via process-bound RCON, without real sockets, GUI or server processes."""
import copy
import types
import unittest
from unittest.mock import Mock, patch

from asaonly.monitor_plugin import MonitorMixin
from asaonly.server_tab import ServerTab
from symulacja.test_cluster import FakeApp, FakeTab, pending


class App(MonitorMixin, FakeApp):
    _dziennik_modow = FakeApp._dziennik_modow


class ReturnRcon(unittest.TestCase):
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

    def test_new_process_rcon_without_ready_finishes_return_watch(self):
        self.assertTrue(self.app.restart_active)
        self.probe()(None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        self.assertTrue(any('watch_map_ready' in x for x in self.app.logs))
        self.assertFalse(self.app.config_data.get('return_failures'))
        self.assertEqual(self.tab._ready_proof, 'old-marker')

    def test_monitor_probes_new_process_even_with_stale_ready_status(self):
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

    def test_same_original_process_is_not_probed_during_restart(self):
        self.tab._monitor_identity = (123, 10)
        self.app._sonda_rcon(self.tab, confirm_unknown=True)
        self.plugin.enqueue.assert_not_called()
        self.tick()
        self.assertTrue(self.app.watch_active)

    def test_failed_probe_does_not_confirm_return(self):
        self.probe()(TimeoutError('synthetic'))
        self.tick()
        self.assertTrue(self.app.watch_active)
        self.assertEqual(self.tab._tail_status, 'unknown')

    def test_delayed_reply_from_replaced_process_is_rejected(self):
        cb = self.probe()
        self.tab._monitor_identity = (789, 30)
        cb(None)
        self.tick()
        self.assertTrue(self.app.watch_active)

    def test_reused_pid_with_different_start_time_is_rejected(self):
        cb = self.probe()
        self.tab._monitor_identity = (456, 30)
        cb(None)
        self.tick()
        self.assertTrue(self.app.watch_active)

    def test_dead_or_unverifiable_process_is_rejected(self):
        cb = self.probe()
        for alive in (False, None):
            with self.subTest(alive=alive):
                self.app._identity_alive.return_value = alive
                cb(None)
                self.assertFalse(self.app._ready_since(self.tab, self.record))

    def test_changed_boot_sequence_is_rejected(self):
        cb = self.probe()
        self.tab._boot_seq += 1
        cb(None)
        self.assertFalse(self.app._ready_since(self.tab, self.record))

    def test_crash_while_probe_queued_is_rejected(self):
        cb = self.probe()
        self.tab._tail_status = 'crash'
        cb(None)
        self.assertIsNone(self.tab.__dict__.get('_rcon_ready_identity'))

    def test_removed_or_replaced_tab_does_not_receive_reply(self):
        cb = self.probe()
        self.app.tabs['A'] = object()
        cb(None)
        self.assertIsNone(self.tab.__dict__.get('_rcon_ready_identity'))

    def test_return_alarm_clears_after_late_rcon_recovery(self):
        self.app.watch_maps = {}
        self.app.watch_active = self.app.restart_active = False
        self.app.config_data['return_failures'] = {'A': self.record}
        self.probe()(None)
        self.app._check_return_alarm(self.tab, True)
        self.assertEqual(self.app.config_data['return_failures'], {})

    def test_rcon_does_not_verify_mods_from_previous_boot(self):
        self.tab._server_versions = self.tab.installed = {'111': '203'}
        self.probe()(None)
        self.tick()
        self.assertFalse(self.app.watch_active)
        self.assertTrue(self.app.pending_updates)
        self.assertEqual(self.app.pending_updates[0]['verified'], [])
        self.assertFalse(self.app._ready_since(self.tab, self.record, allow_rcon=False))

    def test_unbound_legacy_confirmation_is_ui_only(self):
        self.tab.confirm_ready_by_rcon()
        self.tick()
        self.assertTrue(self.app.watch_active)

    def test_missing_original_identity_does_not_enable_return_probe(self):
        self.app.watch_maps['A']['identity'] = None
        self.assertFalse(self.app._needs_return_probe(self.tab))

    def test_losing_ready_clears_rcon_proof(self):
        self.probe()(None)
        self.tab.app = self.app
        self.tab._wisi_st = 0
        self.tab._dl_last = 0
        self.tab._dl_alarm = False
        ServerTab._apply_tail(self.tab, 'unknown', 'log reopened')
        self.assertIsNone(self.tab._rcon_ready_identity)


if __name__ == '__main__':
    unittest.main()
