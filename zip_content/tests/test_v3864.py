"""27 September round: evidence preservation, process identity, mod grace, timeout."""
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from asaonly import archiwum_padow as A
from asaonly.logtail import LogTail
from asaonly.monitor_plugin import MonitorMixin
from tests.test_v3862 import AppMonitora, ZakladkaMonitora
from symulacja.test_cluster import FakeApp, FakeTab, Var, pending

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.logs = self.root / 'server' / 'Saved' / 'Logs'; self.logs.mkdir(parents=True)
        self.dest = self.root / 'program' / 'WIEDZA_O_PROGRAMIE'
        self.log = self.logs / 'ShooterGame.log'
        self.log.write_bytes(b'FIRST BOOT\r\nRequested mods failed to load on server\r\n')

    def test_snapshot_survives_manager_deleting_and_recreating_log(self):
        crash = self.logs/'09.27.crashstack'; crash.write_bytes(b'Fatal\xff\x00')
        (self.logs/'crashcallstack.txt').write_bytes(b'callstack')
        dumps = self.logs.parent/'Crashes'/'UECC'; dumps.mkdir(parents=True)
        (dumps/'minidump.dmp').write_bytes(b'\x00\xffDUMP')
        (self.logs/'secret.ini').write_text('do not capture')
        old = self.log.read_bytes()
        r = A.zapisz_dowody(self.dest, '../Extinction', self.logs, 'trace', [24540, 11])
        self.log.unlink(); self.log.write_text('SECOND BOOT')
        saved = pathlib.Path(r['path'])
        self.assertTrue(saved.is_relative_to(self.dest))
        self.assertEqual((saved/'Logs'/'ShooterGame.log').read_bytes(), old)
        self.assertEqual((saved/'Logs'/'09.27.crashstack').read_bytes(), crash.read_bytes())
        self.assertEqual((saved/'Crashes'/'UECC'/'minidump.dmp').read_bytes(), b'\x00\xffDUMP')
        self.assertFalse((saved/'Logs'/'secret.ini').exists())
        self.assertEqual(r['report']['errors'], [])

    def test_tail_captures_before_ui_callback_and_before_pad_window(self):
        events = []
        app = types.SimpleNamespace(knowledge_dir=str(self.dest), post_ui=lambda cb: cb(), log=lambda s: events.append('saved'))
        tab = types.SimpleNamespace(app=app, name='Extinction')
        tail = LogTail(tab, str(self.logs), lambda *a: events.append('status'))
        tail._emit('crash', 'Fatal')
        self.assertEqual(events, ['saved', 'status'])
        self.assertEqual(len(list(self.dest.rglob('ShooterGame.log'))), 1)
        tail._emit('crash', 'Fatal')
        self.assertEqual(len(list(self.dest.rglob('ShooterGame.log'))), 1)

    def test_missing_log_and_limit_are_explicit_not_silent_success(self):
        with patch.object(A, 'MAX_FILE', 4):
            r = A.zapisz_dowody(self.dest, 'A', self.logs, 'trace')
        self.assertTrue(r['report']['files'][0]['truncated'])
        self.assertIn('NIEPEŁNA', r['message'])
        self.log.unlink()
        r = A.zapisz_dowody(self.dest, 'A', self.logs, 'trace')
        self.assertTrue(r['report']['errors'])
        self.assertTrue((pathlib.Path(r['path'])/'metadata.json').is_file())

    def test_manager_replacement_during_copy_keeps_original_crash_identity(self):
        from asaonly.server_tab import ServerTab
        queued = []
        app = types.SimpleNamespace(knowledge_dir=str(self.dest), post_ui=queued.append, log=Mock())
        tab = types.SimpleNamespace(app=app, name='Extinction', _monitor_identity=(24540, 10), _apply_tail=Mock())
        def copy_and_replace(*args, **kwargs):
            self.assertEqual(args[-1], (24540, 10))
            tab._monitor_identity = (24296, 20)
            return {'message': 'saved'}
        tail = LogTail(tab, str(self.logs), lambda *a: ServerTab._on_tail(tab, *a))
        with patch.object(A, 'zapisz_dowody', side_effect=copy_and_replace):
            tail._emit('crash', 'Fatal')
        for callback in queued:
            callback()
        tab._apply_tail.assert_called_once_with('crash', 'Fatal', crash_identity=(24540, 10))


class Identity(unittest.TestCase):
    def scenario(self, old, new, survived):
        tab = ZakladkaMonitora('Extinction', '27021')
        app = AppMonitora(tab)
        tab._monitor_identity = old
        app._pad4[tab.name] = {'t0': 1000, 'identity': old}
        app.zywe = {new[0]}
        app._process_identity = lambda pid: new
        app._identity_alive = lambda identity: survived
        with patch('asaonly.monitor_plugin.time.time', return_value=1100):
            app._monitor_apply({'pid': {'27021': new[0]}, 'wiek': {tab.name: 0}})
        return app, tab

    def test_round_24540_to_24296_is_crash_not_survival(self):
        app, tab = self.scenario((24540, 10), (24296, 20), False)
        self.assertTrue(any('pad_crash' in x for x in app.logi))
        self.assertFalse(any('pad4_koniec' in x for x in app.logi))
        self.assertEqual(tab.stany, [])  # replacement process is not marked offline

    def test_reused_pid_with_new_creation_time_is_not_survival(self):
        app, _ = self.scenario((24540, 10), (24540, 20), False)
        self.assertTrue(any('pad_crash' in x for x in app.logi))
        self.assertFalse(any('pad4_koniec' in x for x in app.logi))

    def test_same_identity_alive_can_survive_trace(self):
        app, _ = self.scenario((24540, 10), (24540, 10), True)
        self.assertTrue(any('pad4_koniec' in x for x in app.logi))

    def test_unknown_identity_cannot_claim_survival(self):
        app, _ = self.scenario(None, (24296, 20), None)
        self.assertFalse(any('pad4_koniec' in x for x in app.logi))
        self.assertTrue(any('niepewny' in x for x in app.logi))

    def test_cached_identity_detects_reuse_after_port_disappears(self):
        tab = ZakladkaMonitora('A', '27021')
        app = AppMonitora(tab); app._last_pid_by_port={'27021': 55}
        app._last_identity_by_port={'27021': (55, 10)}
        app._identity_alive=lambda identity: False
        app.zywe={55}
        self.assertEqual(app._tab_alive(tab, {}), (False, 55))

    def test_unreadable_new_identity_does_not_reuse_previous_identity(self):
        tab = ZakladkaMonitora('A', '27021'); tab._monitor_identity = (55, 10)
        app = AppMonitora(tab); app.zywe = {56}
        app._last_identity_by_port = {'27021': (55, 10)}
        app._process_identity = lambda pid: None
        self.assertEqual(app._tab_alive(tab, {'27021': 56}), (True, 56))
        self.assertIsNone(tab._monitor_identity)
        self.assertNotIn('27021', app._last_identity_by_port)

    @unittest.skipUnless(os.name == 'nt', 'Windows path lookup')
    def test_startup_process_is_found_by_exact_exe_without_rcon_port(self):
        from asaonly.zamrazanie import ApiWindows
        tab=types.SimpleNamespace(var_log=Var(r'C:\Synthetic\Map\ShooterGame\Saved\Logs'))
        with patch.object(ApiWindows, 'procesy', return_value=[1,2]), \
             patch.object(ApiWindows, 'sciezka_exe', side_effect=[r'C:\Other\ArkAscendedServer.exe', r'C:\Synthetic\Map\ShooterGame\Binaries\Win64\ArkAscendedServer.exe']):
            self.assertEqual(MonitorMixin()._server_pid_for_tab(tab), 2)


class GraceAndReturn(unittest.TestCase):
    def make(self):
        tab=FakeTab('A',['111'],[('0','DoExit')],27020)
        app=FakeApp([tab],[]); app.mod_names={}; app.config_data={}; app.var_mod_wait=Var('5')
        return app, tab

    def test_wait_for_concrete_version_does_not_reset_on_repeated_detection(self):
        app, tab=self.make()
        with patch('asaonly.procedura.time.time', return_value=1000):
            app._add_or_update_pending('111','M','509',['A']); app._exec_pending()
        self.assertFalse(app.restart_active); self.assertEqual(app._auto_next_t, 1300)
        with patch('asaonly.procedura.time.time', return_value=1200):
            app._add_or_update_pending('111','M','509',['A']); app._exec_pending()
        self.assertEqual(app.pending_updates[0]['first_seen'], 1000)
        self.assertEqual(tab.sent, [])
        with patch('asaonly.procedura.time.time', return_value=1300):
            app._exec_pending(); app._tick_restart_timeline()
        self.assertEqual(tab.sent, ['DoExit'])

    def test_newer_version_restarts_wait_and_timestamp_survives_normalization(self):
        app, _=self.make()
        with patch('asaonly.procedura.time.time', return_value=1000):
            app._add_or_update_pending('111','M','509',['A'])
        with patch('asaonly.procedura.time.time', return_value=1200):
            app._add_or_update_pending('111','M','510',['A'])
        saved=json.loads(json.dumps(app.pending_updates))
        other,_=self.make(); other.pending_updates=saved
        with patch('asaonly.procedura.time.time', return_value=1250):
            other._normalize_pending_updates()
            self.assertEqual(other._mod_wait_remaining(other.pending_updates,1250),250)

    def test_zero_disables_wait_and_bad_setting_falls_back_to_five(self):
        app,_=self.make(); app.pending_updates=[pending()]
        app.var_mod_wait=Var('0')
        self.assertEqual(app._mod_wait_remaining(app.pending_updates,1000),0)
        app.var_mod_wait=Var('invalid'); self.assertEqual(app._mod_wait_minutes(),5)

    def test_wait_does_not_reset_player_announcement_schedule(self):
        app,tab=self.make(); tab.lines=[('10','ServerChat update'),('20','DoExit')]
        app.pending_updates=[dict(pending(),first_seen=1000)]
        with patch('asaonly.procedura.time.time', return_value=1300): app._exec_pending()
        self.assertEqual(app._kolejka.mapa('A').t_wyjscia,20)

    def test_timeout_warns_persists_alarm_and_prevents_same_version_loop(self):
        app,tab=self.make(); app.var_mod_wait=Var('0'); app.var_watch=Var('1')
        app.pending_updates=[pending()]; tab._monitor_identity=(24540,10)
        with patch('asaonly.procedura.time.time',return_value=1000):
            app._exec_pending(); app._tick_restart_timeline()
        tab._tail_status='crash'
        with patch('asaonly.procedura.time.time',return_value=1061):
            app._tick_return_watch()
        self.assertIn('A',app.config_data['return_failures'])
        self.assertTrue(app._proba_juz_byla(app.pending_updates[0],'A'))
        self.assertTrue(any('ALARM' in x and 'managera' in x for x in app.logs))
        self.assertEqual(tab.sent,['DoExit'])
        self.assertFalse(app.watch_active)
        label=Mock(); app.lbl_return_alarm=label; app._refresh_return_alarm()
        self.assertIn('ALARM',label.configure.call_args.kwargs['text'])
        # Same old READY does not clear; replacement READY does.
        tab._tail_status='ready'; app._check_return_alarm(tab,True)
        self.assertIn('A',app.config_data['return_failures'])
        tab._monitor_identity=(24296,20); tab._boot_seq=1
        tab._ready_proof='new-log-ready'; tab._ready_observed_at=1070
        app._check_return_alarm(tab,True)
        self.assertEqual(app.config_data['return_failures'],{})

    def test_failed_queue_remains_red(self):
        spec=importlib.util.spec_from_file_location('coordinator3864',ROOT/'PLUGINY'/'50_koordynator_procedur.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        plugin=mod.Wtyczka(); plugin.core=Mock()
        plugin.opublikuj([('A','nieudana','','timeout'),('B','zrobiona','','')])
        self.assertIn('ALARM',plugin.core.set_indicator.call_args.args[1])
        self.assertEqual(plugin.core.set_indicator.call_args.args[2],'#b00020')


if __name__=='__main__': unittest.main()
