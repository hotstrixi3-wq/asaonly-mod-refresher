"""Regressions reported by the isolated 3.86.4 supertest."""
import os
import pathlib
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch
from asaonly.logtail import LogTail
from asaonly.server_tab import ServerTab
from asaonly.cf_wersje import CurseForgeMixin
from asaonly.kolejka import SONDA, NIEUDANA
from symulacja.test_cluster import FakeApp, FakeTab, Var, pending


class ReturnWatch(unittest.TestCase):
    def make(self):
        tab=FakeTab('A',['111'],[('0','DoExit')],47021)
        tab._monitor_identity=(123,10)
        app=FakeApp([tab],[pending()]); app.config_data={}
        with patch('asaonly.procedura.time.time',return_value=1000):
            app._exec_pending(); app._tick_restart_timeline()
        return app,tab

    def finish(self,app,tab):
        tab._server_versions={'111':'203'}; tab.installed={'111':'100'}
        with patch('asaonly.procedura.time.time',return_value=1030), patch('asaonly.procedura.os.path.isdir',return_value=True):
            app._tick_return_watch()

    def test_crash_during_shutdown_then_ready_is_accepted_before_timeout(self):
        app,tab=self.make()
        tab.app=app; tab._set_status=Mock(); tab._crash_times=[]; tab._crashloop_alarm=False
        app._pad4_start=Mock(); app.log_status=Mock(); app._samorestart_zlicz=Mock()
        for status in ('crash','starting','ready'):
            ServerTab._apply_tail(tab,status,'')
        self.assertEqual(tab._boot_seq,1)
        tab._monitor_identity=(456,20)
        tab._ready_proof='new-log-ready'; tab._ready_observed_at=1020
        self.finish(app,tab)
        self.assertFalse(app.watch_active)
        self.assertEqual(app.pending_updates,[])
        self.assertTrue(any('watch_map_ready' in s for s in app.logs))
        self.assertFalse(app.config_data.get('return_failures'))

    def test_new_identity_recovers_missing_lifecycle_transition(self):
        app,tab=self.make(); tab._monitor_identity=(456,20)
        self.assertEqual(tab._boot_seq,0)
        # A real new log can contain READY in the first batched read.
        tab._ready_proof='new-log-ready'; tab._ready_observed_at=1020
        self.finish(app,tab)
        self.assertFalse(app.watch_active)
        self.assertEqual(app.pending_updates,[])

    def test_same_process_ready_after_trace_is_not_a_new_boot(self):
        app,tab=self.make(); tab._boot_seq=1
        self.finish(app,tab)
        self.assertTrue(app.watch_active)
        self.assertTrue(app.pending_updates)

    def test_reused_pid_requires_different_creation_time(self):
        app,tab=self.make(); tab._monitor_identity=(123,20)
        tab._ready_proof='new-log-ready'; tab._ready_observed_at=1020
        self.finish(app,tab)
        self.assertFalse(app.watch_active)


class CrashBaseline(unittest.TestCase):
    def test_existing_crashstack_does_not_replace_initial_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            crash=pathlib.Path(folder)/'old.crashstack'; crash.write_text('Fatal')
            os.utime(crash,(time.time()-60,time.time()-60))
            cb=Mock(); tab=types.SimpleNamespace(app=types.SimpleNamespace(tr=lambda x:x))
            for _ in range(2):  # reopening the tail (e.g. language / monitoring toggle)
                tail=LogTail(tab,folder,cb)
                tail._infer_initial_state('Server has completed startup and is now advertising')
                tail._poll_crashstack(time.time())
                self.assertEqual(tail._status,'ready')
            self.assertFalse(any(call.args[1]=='crash' for call in cb.call_args_list))

    def test_new_or_rewritten_crashstack_is_still_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            cb=Mock(); tab=types.SimpleNamespace(app=types.SimpleNamespace(tr=lambda x:x))
            tail=LogTail(tab,folder,cb)
            crash=pathlib.Path(folder)/'new.crashstack'; crash.write_text('Fatal')
            tail._poll_crashstack(time.time()); self.assertEqual(tail._status,'crash')
            tail._status='ready'; crash.write_text('New fatal, same path')
            tail._poll_crashstack(time.time()); self.assertEqual(tail._status,'crash')

    def test_fatal_in_current_log_is_not_hidden_by_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder)/'old.crashstack').write_text('Fatal')
            tail=LogTail(types.SimpleNamespace(),folder,Mock())
            tail._infer_initial_state('Log file open\nFatal error: mods failed')
            self.assertEqual(tail._status,'crash')


class RconFailures(unittest.TestCase):
    def make(self):
        tab=FakeTab('A',['111'],[('405','DoExit')],47021)
        app=FakeApp([tab],[pending()]); app.config_data={}
        app._exec_pending()
        m=app._kolejka.mapa('A'); m.stan=SONDA; m.sonda_cel='wstepna'
        return app,tab,m

    def test_auth_rejection_skips_wait_and_blocks_automatic_retry(self):
        app,tab,m=self.make()
        app._wynik_sondy('A',ConnectionError('Auth failed (wrong password or port).'),None)
        self.assertEqual(m.stan,NIEUDANA); self.assertEqual(tab.sent,[])
        self.assertIn('hasło',app.config_data['rcon_failures']['A']['reason'])
        self.assertTrue(app._proba_juz_byla(app.pending_updates[0],'A'))
        app._tick_restart_timeline(); app._exec_pending()
        self.assertFalse(app.restart_active); self.assertEqual(tab.sent,[])
        self.assertFalse(any('restart_no_lines' in s or 'restart_skip_map' in s for s in app.logs))
        app.lbl_return_alarm=Mock(); app._refresh_return_alarm()
        self.assertIn('ALARM RCON',app.lbl_return_alarm.configure.call_args.kwargs['text'])

    def test_closed_port_is_reported_without_claiming_wrong_password(self):
        app,tab,m=self.make()
        app._wynik_sondy('A',ConnectionRefusedError(10061,'refused'),None)
        self.assertEqual(m.stan,NIEUDANA)
        reason=app.config_data['rcon_failures']['A']['reason']
        self.assertIn('port',reason); self.assertNotIn('hasło',reason)

    def test_unrecognized_players_response_remains_conservative(self):
        app,tab,m=self.make(); tab.confirm_ready_by_rcon=Mock()
        app._wynik_sondy('A',None,'unexpected player format')
        self.assertNotEqual(m.stan,NIEUDANA); self.assertEqual(m.tryb,'gracze')
        self.assertEqual(m.t_wyjscia,405)

    def test_failed_doexit_marks_attempt_and_alarm_survives_reload(self):
        import json
        tab=FakeTab('A',['111'],[('0','DoExit')],47021,rcon_error=TimeoutError('timeout'))
        app=FakeApp([tab],[pending()]); app.config_data={}
        app._exec_pending(); app._tick_restart_timeline()
        self.assertEqual(tab.sent,['DoExit'])
        restored=FakeApp([tab],json.loads(json.dumps(app.pending_updates)))
        restored.config_data=json.loads(json.dumps(app.config_data))
        restored._exec_pending()
        self.assertFalse(restored.restart_active); self.assertEqual(tab.sent,['DoExit'])
        self.assertIn('A',restored.config_data['rcon_failures'])

    def test_successful_manual_retry_clears_rcon_alarm(self):
        app,tab,m=self.make(); tab.confirm_ready_by_rcon=Mock()
        app.config_data['rcon_failures']={'A':{'reason':'auth'}}
        app._wynik_sondy('A',None,'No Players Connected')
        self.assertEqual(app.config_data['rcon_failures'],{})


class Messages(unittest.TestCase):
    def test_mod_wait_does_not_report_missing_rcon_lines(self):
        tab=FakeTab('A',['111'],[('0','DoExit')],47021)
        app=FakeApp([tab],[dict(pending(),first_seen=1000)]); app.var_mod_wait=Var('5')
        with patch('asaonly.procedura.time.time',return_value=1000): app._exec_pending()
        self.assertFalse(any('restart_no_lines' in x for x in app.logs))

    def test_bad_log_folder_warns_on_card_and_in_journal(self):
        tab=types.SimpleNamespace(name='A',var_log=Var(r'C:\nonexistent-asa-test\Saveed\Logs'),
            lbl_log_warning=Mock(),app=Mock(),_stop_tail=Mock())
        tab.log_path_problem=lambda: ServerTab.log_path_problem(tab)
        ServerTab._start_tail(tab)
        self.assertIn('folder nie istnieje',tab.lbl_log_warning.configure.call_args.kwargs['text'])
        tab.app.log_warn.assert_called_once()

    def test_same_cf_version_is_not_announced_as_new_during_watch(self):
        class App(CurseForgeMixin,FakeApp):
            def _cf_cleanup(self): pass
            def _cf_ok(self): pass
        app=App([],[]); app.mod_latest={}; app.mod_names={}; app.var_interval=Var('30')
        app.watch_active=True
        updates=[('111','M','200',['A'])]
        app._cf_done(updates); app._cf_done(updates)
        self.assertEqual(app.logs.count('cf_update'),1)
        self.assertEqual(app.logs.count('watch_park_log'),1)


if __name__=='__main__': unittest.main()
