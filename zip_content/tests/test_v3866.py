"""Fresh READY evidence, transactional alert rename and bounded crash archives.

No operational App is started: real log parsing, procedure methods and filesystem
transactions operate on synthetic maps and temporary files.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from asaonly.archiwum_padow import zapisz_dowody
from asaonly.logtail import LogTail
from asaonly.server_tab import ServerTab
from asaonly.retencja_padow import maintain, limit_mib
from symulacja.test_cluster import FakeApp, FakeTab, pending

READY = 'Server has completed startup and is now advertising'


class FreshReady(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='asaonly-ready-')
        self.addCleanup(self.tmp.cleanup)
        self.logs = Path(self.tmp.name)
        self.path = self.logs/'ShooterGame.log'
        self.tab = FakeTab('A', ['111'], [('0','DoExit')], 47021)
        self.tab._monitor_identity = (123, 10)
        self.app = FakeApp([self.tab], [pending()])
        self.app.config_data = {}
        self.tab.app = self.app
        self.tab._set_status = Mock()
        self.tab._crash_times = []
        self.tab._crashloop_alarm = False
        self.app.log_status = Mock()
        self.app._samorestart_zlicz = Mock()
        self.app._pad4_start = Mock()
        self.tab._on_server_event = lambda event: ServerTab._apply_server_event(self.tab,event)
        self.open_log('Log file open\r\n'+READY+'\r\n')
        self.before_proof = self.tab._ready_proof
        with patch('asaonly.procedura.time.time',return_value=1000):
            self.app._exec_pending(); self.app._tick_restart_timeline()

    def open_log(self, text=None):
        if text is not None:
            # Keep the previous inode alive so replacement is deterministic.
            if self.path.exists():
                self.path.rename(self.logs/('old-'+str(time.time_ns())))
            self.path.write_bytes(text.encode('utf-8'))
        tail = LogTail(self.tab,str(self.logs),lambda tab,status,line: ServerTab._apply_tail(tab,status,line))
        fh = tail._open_latest()
        self.assertIsNotNone(fh)
        fh.close()
        return tail

    def tick(self):
        with patch('asaonly.procedura.time.time',return_value=1030), patch('asaonly.procedura.os.path.isdir',return_value=True):
            self.app._tick_return_watch()

    def versions(self):
        self.tab._server_versions={'111':'203'}
        self.tab.installed={'111':'203'}

    def test_changed_pid_with_old_ready_does_not_finish_or_verify(self):
        self.tab._monitor_identity=(456,20); self.versions()
        self.tick(); self.app._verify_local_mods()
        self.assertTrue(self.app.watch_active)
        self.assertTrue(self.app.pending_updates)
        self.assertFalse(any('watch_map_ready' in s for s in self.app.logs))
        self.assertFalse(self.app._proba_juz_byla(self.app.pending_updates[0],'A'))

    def test_pid_first_then_complete_new_log_finishes(self):
        self.tab._monitor_identity=(456,20)
        self.tick(); self.assertTrue(self.app.watch_active)
        self.open_log('Log file open\n'+READY+'\n'); self.versions(); self.tick()
        self.assertFalse(self.app.watch_active); self.assertEqual(self.app.pending_updates,[])

    def test_new_log_first_then_pid_finishes(self):
        self.open_log('Log file open\n'+READY+'\n'); self.versions(); self.tick()
        self.assertTrue(self.app.watch_active)
        self.tab._monitor_identity=(456,20); self.tick()
        self.assertFalse(self.app.watch_active)

    def test_missing_current_process_identity_does_not_confirm_return(self):
        self.open_log('Log file open\n'+READY+'\n')
        self.tab._monitor_identity=None
        self.tick(); self.assertTrue(self.app.watch_active)

    def test_reopening_the_same_log_is_not_new_ready(self):
        self.tab._monitor_identity=(456,20)
        observed=self.tab._ready_observed_at
        self.open_log()
        self.assertEqual(self.tab._ready_proof,self.before_proof)
        self.assertEqual(self.tab._ready_observed_at,observed)
        self.tick(); self.assertTrue(self.app.watch_active)

    def test_ordinary_activity_does_not_refresh_evidence(self):
        tail=self.open_log()
        self.tab._monitor_identity=(456,20)
        tail._handle_line('ordinary player activity')
        tail._emit('ready','ordinary player activity')
        self.assertEqual(self.tab._ready_proof,self.before_proof)
        self.tick(); self.assertTrue(self.app.watch_active)

    def test_incremental_ready_and_replay_have_identical_proof_with_crlf(self):
        self.open_log('Log file open\r\nzażółć\r\n')
        tail=LogTail(self.tab,str(self.logs),lambda *a:None)
        tail._fh=tail._open_latest()
        try:
            with self.path.open('ab') as out: out.write((READY+'\r\n').encode())
            tail._handle_line(tail._fh.readline().rstrip('\n'))
            proof=self.tab._ready_proof
        finally: tail._fh.close()
        self.open_log()
        self.assertEqual(proof,self.tab._ready_proof)

    def test_ready_from_previous_attempt_does_not_confirm_later_pid(self):
        self.open_log('Log file open\n'+READY+'\n')
        observed=self.tab._ready_observed_at
        self.tab._monitor_identity=(789,int((observed+10+11644473600)*10000000))
        self.tick(); self.assertTrue(self.app.watch_active)

    def test_alarm_survives_stale_ready_and_clears_only_with_new_evidence(self):
        self.app.config_data['return_failures']={'A':copy.deepcopy(self.app._proc_map_results['A'])}
        self.tab._monitor_identity=(456,20)
        self.app._check_return_alarm(self.tab,True)
        self.assertIn('A',self.app.config_data['return_failures'])
        self.open_log('Log file open\n'+READY+'\n')
        self.app._check_return_alarm(self.tab,True)
        self.assertEqual(self.app.config_data['return_failures'],{})

    def test_serialized_alarm_still_rejects_replayed_old_marker(self):
        record=json.loads(json.dumps(self.app._proc_map_results['A']))
        self.app.config_data['return_failures']={'A':record}
        self.tab._ready_proof=None; self.tab._boot_seq=0
        self.tab._monitor_identity=(456,20); self.open_log()
        self.app._check_return_alarm(self.tab,True)
        self.assertIn('A',self.app.config_data['return_failures'])


class RenameAlerts(unittest.TestCase):
    def run_rename(self, save_ok=True, collision=False):
        from tests.test_safety_v375 import asa
        with tempfile.TemporaryDirectory(prefix='asaonly-rename-test-') as folder:
            root=Path(folder); maps=root/'maps'; cfg=root/'global'
            (maps/'Old').mkdir(parents=True); cfg.mkdir()
            (maps/'Old'/'keep.txt').write_text('map data')
            (cfg/'keep.txt').write_text('global data')
            app=object.__new__(asa.App)
            tab=types.SimpleNamespace(name='Old')
            app.restart_active=False; app.watch_active=False; app.plugin_host=None
            app.tabs={'Old':tab}; app.pending_updates=[dict(pending(targets=('Old',)), verified=['Old'])]
            app.server_files={'Old':str(maps/'Old')}
            app.config_data={'return_failures':{'Old':{'identity':[1,2],'ready_proof':'old'}},
                             'rcon_failures':{'Old':{'reason':'password'}}}
            if collision: app.config_data['rcon_failures']['New']={'reason':'preserve me'}
            before=copy.deepcopy(app.config_data)
            app.notebook=Mock(); app.notebook.index.return_value=1
            app.notebook.tab.return_value='Old'
            app.tr=lambda key,**kwargs:key; app.log=Mock()
            app._update_leds_frame=Mock(); app._refresh_return_alarm=Mock()
            app._global_config_data=lambda:copy.deepcopy(dict(app.config_data,pending_updates=app.pending_updates))
            app.save_tab=lambda tab,**kwargs: (maps/tab.name/'saved.json').write_text(tab.name) or True
            saved=[]
            def save_global(folder,base,data):
                saved.append(data)
                (Path(folder)/'saved.json').write_text(json.dumps(data))
                return save_ok
            with patch.object(asa,'TABS_DIR',str(maps)), patch.object(asa,'CONFIG_DIR',str(cfg)), \
                 patch('tkinter.simpledialog.askstring',return_value='New'), \
                 patch.object(asa,'save_versioned',side_effect=save_global), patch.object(asa.messagebox,'showerror'):
                asa.App.rename_server(app,tab)
            if save_ok and not collision:
                self.assertEqual(tab.name,'New')
                for key in ('return_failures','rcon_failures'):
                    self.assertEqual(app.config_data[key],{'New':before[key]['Old']})
                    self.assertEqual(saved[-1][key],app.config_data[key])
                self.assertEqual(app.pending_updates[0]['verified'],['New'])
                app._refresh_return_alarm.assert_called_once()
            else:
                self.assertEqual(tab.name,'Old'); self.assertEqual(app.config_data,before)
                self.assertTrue((maps/'Old'/'keep.txt').exists())
                self.assertFalse((maps/'New').exists())
                self.assertEqual(sorted(p.name for p in cfg.iterdir()),['keep.txt'])
    def test_both_alerts_move_and_persist(self): self.run_rename()
    def test_failed_global_save_restores_both_alerts_and_files(self): self.run_rename(save_ok=False)
    def test_destination_alert_is_not_overwritten(self): self.run_rename(collision=True)


class Retention(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='asaonly-retention-'); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.dest=self.root/'program'
        self.logs=self.root/'server'/'Saved'/'Logs'; self.logs.mkdir(parents=True)
        (self.logs/'ShooterGame.log').write_bytes(b'LOG'*1000)
        self.serial=time.time()
    def capture(self,name='A',limit=0):
        self.serial+=1
        return zapisz_dowody(self.dest,name,self.logs,'test',now=self.serial,limit_bytes=limit)
    def size(self,path): return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())

    def test_oldest_removed_only_until_budget_and_latest_per_map_retained(self):
        a1=self.capture(); a2=self.capture(); b=self.capture('B'); a3=self.capture()
        budget=self.size(a2['path'])+self.size(a3['path'])+self.size(b['path'])+10
        result=maintain(self.dest/'PADY',a3['path'],budget)
        self.assertEqual(result['removed'],[a1['path']])
        self.assertLessEqual(result['bytes'],budget)
        self.assertTrue(Path(b['path']).exists()); self.assertTrue(Path(a2['path']).exists())

    def test_newest_and_latest_complete_survive_over_budget(self):
        good=self.capture()
        (self.logs/'ShooterGame.log').unlink()
        bad=self.capture(limit=1)
        self.assertTrue(Path(good['path']).exists()); self.assertTrue(Path(bad['path']).exists())
        self.assertTrue(bad['warning']); self.assertIn('UWAGA',bad['message'])

    def test_rotation_disabled_keeps_all_copies(self):
        a=self.capture(); b=self.capture()
        self.assertEqual(b['usage']['removed'],[]); self.assertTrue(Path(a['path']).exists())

    def test_legacy_and_operator_added_files_are_retained(self):
        legacy=self.capture(); foreign=self.capture(); newest=self.capture()
        p=Path(legacy['path'])/'metadata.json'; data=json.loads(p.read_text()); data.pop('format')
        p.write_text(json.dumps(data))
        (Path(foreign['path'])/'user-note.txt').write_text('keep')
        result=maintain(self.dest/'PADY',newest['path'],1)
        self.assertEqual(result['removed'],[])
        self.assertTrue((Path(foreign['path'])/'user-note.txt').exists())

    def test_reparse_point_stops_cleanup_and_reports_uncertain_count(self):
        from asaonly import retencja_padow as retention
        old=self.capture(); new=self.capture()
        linked=Path(old['path'])/'Logs'
        real=retention._linked
        with patch.object(retention,'_linked',side_effect=lambda p: p==linked or real(p)):
            result=maintain(self.dest/'PADY',new['path'],1)
        self.assertTrue(result['errors']); self.assertEqual(result['removed'],[])
        self.assertTrue(Path(old['path']).exists())

    def test_deletion_failure_is_reported_without_losing_latest(self):
        old=self.capture(); new=self.capture()
        with patch('asaonly.retencja_padow.shutil.rmtree',side_effect=PermissionError('locked')):
            result=maintain(self.dest/'PADY',new['path'],1)
        self.assertTrue(result['errors']); self.assertTrue(Path(new['path']).exists())
        self.assertTrue(Path(old['path']).exists())

    def test_capture_precedes_rotation_even_if_manager_deletes_source(self):
        from asaonly import archiwum_padow as archive
        real=archive.maintain
        def rotate(root,current,limit):
            (self.logs/'ShooterGame.log').unlink()
            self.assertEqual((Path(current)/'Logs'/'ShooterGame.log').read_bytes(),b'LOG'*1000)
            return real(root,current,limit)
        with patch.object(archive,'maintain',side_effect=rotate): result=self.capture()
        self.assertEqual(result['report']['errors'],[])

    def test_limit_validation(self):
        for bad in ('bad','-1','1','999999',None): self.assertEqual(limit_mib(bad),2048)
        for good in (0,256,2048,65536): self.assertEqual(limit_mib(str(good)),good)

    def test_concurrent_captures_preserve_latest_of_both_maps(self):
        from concurrent.futures import ThreadPoolExecutor
        def capture(name): return zapisz_dowody(self.dest,name,self.logs,'parallel test',limit_bytes=1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(capture,['A','B']))
        for result in results:
            self.assertTrue(Path(result['path'],'Logs','ShooterGame.log').is_file())
            self.assertTrue(Path(result['path'],'metadata.json').is_file())
            self.assertTrue(result['warning'])

    def test_redirected_destination_is_rejected_before_any_copy(self):
        from asaonly import archiwum_padow as archive
        self.dest.mkdir()
        with patch.object(archive,'_linked',return_value=True): result=self.capture()
        self.assertTrue(result['warning']); self.assertTrue(result['report']['errors'])
        self.assertFalse((self.dest/'PADY').exists())


if __name__=='__main__': unittest.main()
