import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from asaonly.pluginy import PluginHost, PLUGIN_API

ROOT = pathlib.Path(__file__).resolve().parents[1]
_program_spec = importlib.util.spec_from_file_location(
    "asaonly_program_plugin_integration",
    ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py")
program_module = importlib.util.module_from_spec(_program_spec)
_program_spec.loader.exec_module(program_module)
_cpu_spec = importlib.util.spec_from_file_location("cpu_plugin_test", ROOT / "PLUGINY" / "60_cpu.py")
cpu_module = importlib.util.module_from_spec(_cpu_spec)
_cpu_spec.loader.exec_module(cpu_module)
# V3.83: importer i backup to jeden plugin „Konfiguracje” (80_konfiguracje.py).
_import_spec = importlib.util.spec_from_file_location("import_plugin_test", ROOT / "PLUGINY" / "80_konfiguracje.py")
import_module = importlib.util.module_from_spec(_import_spec)
_import_spec.loader.exec_module(import_module)
_status_spec = importlib.util.spec_from_file_location("status_history_plugin_test", ROOT / "PLUGINY" / "70_status_historia_serwerow.py")
status_history_module = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(status_history_module)
_diag_spec = importlib.util.spec_from_file_location("diagnostic_plugin_test", ROOT / "PLUGINY" / "82_diagnostyka_zip.py")
diagnostic_module = importlib.util.module_from_spec(_diag_spec); _diag_spec.loader.exec_module(diagnostic_module)
_disk_spec = importlib.util.spec_from_file_location("disk_plugin_test", ROOT / "PLUGINY" / "83_dysk_katalogi.py")
disk_module = importlib.util.module_from_spec(_disk_spec); _disk_spec.loader.exec_module(disk_module)
_rcon_spec = importlib.util.spec_from_file_location("rcon_plugin_test", ROOT / "PLUGINY" / "86_rcon_admin.py")
rcon_module = importlib.util.module_from_spec(_rcon_spec); _rcon_spec.loader.exec_module(rcon_module)


class FakeApp:
    def __init__(self):
        self.logs=[]; self.log_tags=[]; self.tabs={}; self.config_data={}; self.saved=False
        self.is_admin=True
    def log(self, x, tag=None): self.logs.append(str(x)); self.log_tags.append(tag)
    def log_warn(self, x): self.logs.append(str(x))
    def tr(self, key, **kw): return key
    def post_ui(self, cb): cb()
    def run_async(self, fn, *args): fn(*args)
    def request_save(self): self.saved=True


class PluginTests(unittest.TestCase):
    def test_alphabetical_loading_and_api_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)
            (p/'20_b.py').write_text('class Wtyczka:\n API=1\n nazwa="b"\n def start(self, core): pass\n')
            (p/'10_a.py').write_text('class Wtyczka:\n API=1\n nazwa="a"\n def start(self, core): pass\n')
            (p/'30_bad.py').write_text('class Wtyczka:\n API=999\n nazwa="bad"\n')
            app=FakeApp(); host=PluginHost(app,td)
            host.load_all()
            self.assertEqual([x.nazwa for x in host.plugins],['a','b'])
            self.assertTrue(any('niezgodne API' in x for x in app.logs))

    def test_tick_failure_isolated_and_throttled(self):
        class Bad:
            API=PLUGIN_API; nazwa='bad'; default_enabled=True
            def start(self, core): self.core=core
            def tik(self, now): raise RuntimeError('boom')
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); host.plugins=[Bad()]; host.start_all()
            host.tick(1); host.tick(2)
            self.assertEqual(sum('boom' in x for x in app.logs),1)

    def test_event_failure_does_not_block_other_listener(self):
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); got=[]
            host.subscribe('x',lambda p: (_ for _ in ()).throw(ValueError('bad')),'bad')
            host.subscribe('x',lambda p: got.append(p['n']),'good')
            host.emit('x',n=7)
            self.assertEqual(got,[7])

    def test_plugin_api_exposes_program_admin_state(self):
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td)
            self.assertIs(host.core.is_admin(),True)
            app.is_admin=False
            self.assertIs(host.core.is_admin(),False)

    def test_plugin_config_is_copied(self):
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td)
            host.core.save_plugin_config('cpu',{'delay':30})
            cfg=host.core.plugin_config('cpu'); cfg['delay']=1
            self.assertEqual(app.config_data['plugins']['cpu']['delay'],30)
            self.assertTrue(app.saved)

    def test_selected_admin_plugins_are_loaded_and_visible(self):
        app=FakeApp(); host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        visible={p.nazwa for p in host.visible_plugins()}
        expected={'konfiguracje','diagnostyka_zip','dysk_katalogi','analizator_logow',
                  'status_historia_serwerow','rcon_admin','cpu','kontrola_czasu',
                  'aktualizacja_serwera'}
        self.assertTrue(expected.issubset(visible))
        for name in expected:
            info=host.plugin_info(host.get(name))
            self.assertTrue(info['description'])
            self.assertTrue(info['panel'])

    def test_diagnostic_zip_recursively_redacts_json_and_log_secrets(self):
        source={'api_key':'ABC','nested':{'password':'PW','safe':1},'items':[{'token':'T'}]}
        redacted=diagnostic_module.Wtyczka._redact_json(source)
        self.assertEqual(redacted['api_key'],'[REDACTED]')
        self.assertEqual(redacted['nested']['password'],'[REDACTED]')
        self.assertEqual(redacted['nested']['safe'],1)
        self.assertEqual(redacted['items'][0]['token'],'[REDACTED]')
        text=diagnostic_module.Wtyczka._redact_text('password=abc api_key:xyz Authorization=BearerSecret')
        self.assertNotIn('abc',text); self.assertNotIn('xyz',text); self.assertNotIn('BearerSecret',text)

    def test_rcon_bulk_save_converts_unexpected_failure_to_controlled_false(self):
        plugin=rcon_module.Wtyczka()
        class App:
            restart_active=False; watch_active=False; server_files={}
        class Core:
            def application(self): return App()
            def post_ui(self,fn): fn()
            def log(self,*args): pass
        plugin.core=Core(); plugin.window=None; plugin.editors={'A':{}}
        plugin._collect=lambda _name: (_ for _ in ()).throw(RuntimeError('unexpected'))
        with patch.object(rcon_module.messagebox,'showerror') as shown:
            self.assertFalse(plugin._save_all(show_success=False))
            self.assertIn('unexpected',shown.call_args.args[1])

    def test_rcon_bulk_save_fault_injection_restores_first_map_after_second_fails(self):
        plugin=rcon_module.Wtyczka()
        class Var:
            def __init__(self,v): self.v=v
            def get(self): return self.v
            def set(self,v): self.v=v
        class Tab:
            def __init__(self,name):
                self.name=name; self.var_ip=Var('old-'+name); self.var_port=Var('1')
                self.var_pass=Var('pw'); self.var_admin=Var('admin'); self.var_map_on=Var(True)
                self.stash=[]; self.rows=[]; self._rcon_original_lines=[]
                self._rcon_migration_issues=[]; self._rcon_rows_replaced=False
        with tempfile.TemporaryDirectory() as td:
            tabs={n:Tab(n) for n in ('A','B')}; paths={}
            for n in tabs:
                p=os.path.join(td,n); os.mkdir(p); pathlib.Path(p,'marker').write_text('old-'+n)
                paths[n]=p
            class App:
                restart_active=False; watch_active=False
                def __init__(self): self.server_files=dict(paths); self.calls=[]
                def save_tab(self,tab,silent=True):
                    pathlib.Path(self.server_files[tab.name],'marker').write_text('new-'+tab.name)
                    self.calls.append(('cfg',tab.name))
                    return tab.name!='B'
                def save_tab_secrets(self,tab,silent=True): return True
            app=App()
            class Core:
                def application(self): return app
                def post_ui(self,fn): fn()
                def log(self,*args): pass
            plugin.core=Core(); plugin.window=None
            plugin.editors={n:{'tab':tab,'host':Var('new-'+n),'port':Var('2' if n=='A' else '3'),
                'password':Var('newpw'),'command':Var('newcmd'),'presets':[], 'rows':[]}
                for n,tab in tabs.items()}
            with patch.object(rcon_module.messagebox,'showerror'):
                self.assertFalse(plugin._save_all(show_success=False))
            self.assertEqual(tabs['A'].var_ip.get(),'old-A')
            self.assertEqual(tabs['B'].var_ip.get(),'old-B')
            self.assertEqual(pathlib.Path(paths['A'],'marker').read_text(),'old-A')
            self.assertEqual(pathlib.Path(paths['B'],'marker').read_text(),'old-B')
            self.assertEqual(app.server_files,paths)

    def test_rcon_bulk_save_has_memory_and_disk_rollback(self):
        plugin=rcon_module.Wtyczka()
        class Var:
            def __init__(self,v): self.v=v
            def get(self): return self.v
            def set(self,v): self.v=v
        class Tab: pass
        tab=Tab(); tab.var_ip=Var('old'); tab.var_port=Var('1'); tab.var_pass=Var('secret')
        tab.var_admin=Var('cmd'); tab.stash=['a']; tab.rows=[{'time':'1','cmd':'x','on':True}]
        tab._rcon_original_lines=['legacy']; tab._rcon_migration_issues=[{'index':0}]
        tab._rcon_rows_replaced=False
        snap=plugin._tab_snapshot(tab)
        tab.var_ip.set('new'); tab.rows=[]; tab.stash=[]; tab._rcon_migration_issues=[]
        plugin._restore_tab(tab,snap)
        self.assertEqual(tab.var_ip.get(),'old')
        self.assertEqual(tab.rows,[{'time':'1','cmd':'x','on':True}])
        self.assertEqual(tab._rcon_original_lines,['legacy'])
        self.assertEqual(tab._rcon_migration_issues,[{'index':0}])
        source=(ROOT/'PLUGINY'/'86_rcon_admin.py').read_text(encoding='utf-8')
        save=source.split('def _save_all(',1)[1].split('def _set_busy(',1)[0]
        self.assertIn('self._apply(name, persist=False)',save)
        self.assertIn('shutil.copytree(path, backup)',save)
        self.assertIn('self._restore_tab(editor["tab"], snapshots[name])',save)
        self.assertIn('app.server_files.update(old_server_files)',save)

    def test_rcon_admin_validates_port_without_throwing_in_tk_callback(self):
        valid=rcon_module.Wtyczka._valid_port
        self.assertEqual(valid('27020'),27020)
        for value in ('', 'x', '0', '65536', None): self.assertIsNone(valid(value))

    def test_rcon_plugin_rejects_missing_host_and_invalid_port_before_procedure(self):
        class Var:
            def __init__(self,value): self.value=value
            def get(self): return self.value
        class Tab:
            rows=[]; var_map_on=Var(True); var_ip=Var(''); var_port=Var('27020')
        self.assertEqual(rcon_module.Wtyczka.validate(Tab())[1],'host')
        Tab.var_ip=Var('127.0.0.1'); Tab.var_port=Var('70000')
        self.assertEqual(rcon_module.Wtyczka.validate(Tab())[1],'port')

    def test_rcon_is_required_workspace_not_optional_single_command_addon(self):
        plugin=rcon_module.Wtyczka()
        self.assertTrue(plugin.required)
        self.assertEqual(plugin.main_action_text,'RCON')
        self.assertIn('lokalne procedury czasowe',plugin.manager_description)
        source=(ROOT/'PLUGINY'/'86_rcon_admin.py').read_text(encoding='utf-8')
        self.assertIn('MAX_RCON_LINES',source)
        self.assertIn('validate_rcon_line_values',source)
        self.assertIn('ZAPISZ WSZYSTKIE',source)

    def test_rcon_plugin_owns_queue_send_and_callback(self):
        import threading
        class Var:
            def __init__(self,value): self.value=value
            def get(self): return self.value
        class Tab:
            name='A'; var_ip=Var('127.0.0.1'); var_port=Var('27020'); var_pass=Var('pw')
        plugin=rcon_module.Wtyczka(); calls=[]; done=threading.Event(); old=rcon_module.rcon_send
        try:
            rcon_module.rcon_send=lambda host,port,password,command: calls.append((host,port,password,command))
            plugin.enqueue(Tab(),'ListPlayers',lambda error: (calls.append(('callback',error)),done.set()))
            self.assertTrue(done.wait(2))
            self.assertEqual(calls[0],('127.0.0.1','27020','pw','ListPlayers'))
            self.assertEqual(calls[1],('callback',None))
        finally:
            plugin.stop(); rcon_module.rcon_send=old

    def test_rcon_manual_and_automatic_commands_share_map_queue_order(self):
        import threading
        plugin=rcon_module.Wtyczka(); calls=[]; done=threading.Event(); old=rcon_module.rcon_send
        try:
            rcon_module.rcon_send=lambda h,p,pw,cmd: calls.append(cmd) or cmd+' response'
            plugin.enqueue_values('A','host','1','pw','automatic',None)
            plugin.enqueue_values('A','host','1','pw','manual',lambda error,response: done.set())
            self.assertTrue(done.wait(2))
            self.assertEqual(calls,['automatic','manual'])
        finally:
            plugin.stop(); rcon_module.rcon_send=old

    def test_rcon_worker_retries_twice_then_reports_success_response(self):
        import threading
        plugin=rcon_module.Wtyczka(); attempts=[]; result=[]; done=threading.Event()
        old_send,old_sleep=rcon_module.rcon_send,rcon_module.time.sleep
        def flaky(*args):
            attempts.append(args[-1])
            if len(attempts)<3: raise OSError('drop')
            return 'players'
        try:
            rcon_module.rcon_send=flaky; rcon_module.time.sleep=lambda _s: None
            plugin.enqueue_values('A','host','1','pw','ListPlayers',
                                  lambda error,response:(result.append((error,response)),done.set()))
            self.assertTrue(done.wait(2))
            self.assertEqual(attempts,['ListPlayers']*3)
            self.assertEqual(result,[(None,'players')])
        finally:
            plugin.stop(); rcon_module.rcon_send=old_send; rcon_module.time.sleep=old_sleep

    def test_rcon_cancel_is_atomic_against_worker_dispatch_generation(self):
        plugin=rcon_module.Wtyczka()
        plugin.queues['A']=__import__('queue').Queue()
        old_generation=plugin.cancel_generation.get(('A','automatic'),0)
        plugin.queues['A'].put(('automatic',old_generation,'cmd','h','1','p',None))
        result=plugin.cancel_pending(['A'])
        self.assertTrue(result['ok'])
        self.assertEqual(result['removed'],1)
        # Even an item already dequeued before cancellation cannot start later.
        self.assertFalse(plugin._claim_dispatch('A','automatic',old_generation))
        self.assertNotIn('A',plugin.inflight)

        manual_generation=plugin.cancel_generation.get(('A','manual'),0)
        manual_item=('manual',manual_generation,'status','h','1','p',None)
        plugin.queues['A'].put(manual_item)
        self.assertTrue(plugin.cancel_pending(['A'])['ok'])
        self.assertEqual(plugin.queues['A'].get_nowait(),manual_item)

        plugin.inflight.add('B'); plugin.inflight_owner['B']='automatic'
        refused=plugin.cancel_pending(['B'])
        self.assertFalse(refused['ok'])
        self.assertEqual(refused['inflight'],('B',))
        procedure=(ROOT/'asaonly'/'procedura.py').read_text(encoding='utf-8')
        cancel=procedure.split('def cancel_restart(self):',1)[1].split('def ',1)[0]
        self.assertIn('cancel_pending(self.tabs)',cancel)
        self.assertIn('rozpoczętego wywołania sieciowego nie można cofnąć',cancel)

    def test_rcon_plugin_reports_nonidle_while_command_is_inflight(self):
        import threading
        plugin=rcon_module.Wtyczka(); entered=threading.Event(); release=threading.Event()
        done=threading.Event(); old=rcon_module.rcon_send
        def blocked(*args):
            entered.set(); release.wait(2); return 'ok'
        try:
            rcon_module.rcon_send=blocked
            plugin.enqueue_values('A','h','1','p','cmd',lambda e,r:done.set())
            self.assertTrue(entered.wait(2))
            self.assertFalse(plugin.is_idle('A'))
            release.set(); self.assertTrue(done.wait(2))
            self.assertTrue(plugin.is_idle('A'))
        finally:
            release.set(); plugin.stop(); rcon_module.rcon_send=old

    def test_rcon_plugin_can_restart_after_language_ui_rebuild(self):
        import threading
        class Core:
            def set_indicator(self,*args): pass
        plugin=rcon_module.Wtyczka(); calls=[]; old=rcon_module.rcon_send
        try:
            rcon_module.rcon_send=lambda h,p,pw,cmd: calls.append(cmd)
            plugin.start(Core()); first=threading.Event()
            plugin.enqueue_values('A','h','1','p','before',lambda e,r:first.set())
            self.assertTrue(first.wait(2)); plugin.stop()
            plugin.start(Core()); second=threading.Event()
            plugin.enqueue_values('A','h','1','p','after',lambda e,r:second.set())
            self.assertTrue(second.wait(2))
            self.assertEqual(calls,['before','after'])
        finally:
            plugin.stop(); rcon_module.rcon_send=old

    def test_malformed_legacy_rcon_rows_are_reported_and_preserved_losslessly(self):
        from asaonly.server_tab import MAX_RCON_LINES, analyze_rcon_lines
        rows=[None,'bad',{'time':205,'cmd':'DoExit','on':1}]+[
            {'time':i,'cmd':'x'} for i in range(30)]
        normalized,issues,original=analyze_rcon_lines(rows)
        self.assertLessEqual(len(normalized),MAX_RCON_LINES)
        self.assertEqual(normalized[0],{'time':'205','cmd':'DoExit','on':True})
        self.assertTrue(all(isinstance(row,dict) for row in normalized))
        self.assertEqual(original,rows)
        self.assertEqual([i['index'] for i in issues[:2]],[0,1])
        self.assertTrue(any('limitem 20' in i['reason'] for i in issues))

    def test_automatic_tab_save_keeps_unparsed_rcon_source_until_explicit_replacement(self):
        from asaonly.server_tab import ServerTab
        class Var:
            def __init__(self,value): self.value=value
            def get(self): return self.value
        tab=ServerTab.__new__(ServerTab)
        tab.var_ip=Var('h'); tab.var_port=Var('1'); tab.var_log=Var(''); tab.var_tail=Var(False)
        tab.var_tab_mods=Var(''); tab.var_map_on=Var(True); tab.var_admin=Var('')
        tab._mods_unverified=False; tab.stash=[]; tab.rows=[{'time':'1','cmd':'x','on':True}]
        tab._rcon_migration_issues=[{'index':1,'reason':'bad','value':'BROKEN'}]
        tab._rcon_original_lines=[{'time':'1','cmd':'x','on':True},'BROKEN']
        tab._rcon_rows_replaced=False
        self.assertEqual(tab.to_config()['lines'],tab._rcon_original_lines)
        tab._rcon_rows_replaced=True
        self.assertEqual(tab.to_config()['lines'],tab.rows)

    def test_server_tab_no_longer_owns_rcon_transport(self):
        source=(ROOT/'asaonly'/'server_tab.py').read_text(encoding='utf-8')
        self.assertNotIn('def enqueue_rcon',source)
        self.assertNotIn('def send_rcon',source)
        self.assertNotIn('def validate_lines',source)
        self.assertNotIn('def get_lines',source)
        self.assertNotIn('_rcon_q',source)

    def test_map_rename_never_deletes_preexisting_destination_directory(self):
        source=(ROOT/'ASAonly - (AUTO)Manual - ModRefresher (RCON).py').read_text(encoding='utf-8')
        rename=source.split('def rename_server(self, tab):',1)[1].split('def save_tab(',1)[0]
        self.assertIn('if not same_dir and os.path.exists(new_dir)',rename)
        self.assertIn('Docelowy katalog mapy już istnieje',rename)
        self.assertIn('shutil.copytree(old_dir, map_backup)',rename)
        self.assertIn('self.pending_updates[:] = old_pending',rename)
        self.assertIn('shutil.copytree(map_backup, old_dir)',rename)

    def test_app_close_and_language_change_account_for_open_rcon_editor(self):
        source=(ROOT/'ASAonly - (AUTO)Manual - ModRefresher (RCON).py').read_text(encoding='utf-8')
        lang=source.split('def toggle_lang(self):',1)[1].split('def ',1)[0]
        close=source.split('def _on_close(self):',1)[1]
        self.assertIn('has_unsaved_editor',lang)
        self.assertIn('save_open_editor',lang)
        self.assertIn('has_unsaved_editor',close)
        self.assertIn('save_open_editor',close)
        self.assertIn('plugin_host.stop_all()',close)

    def test_post_ui_uses_queue_instead_of_calling_tk_from_worker(self):
        source=(ROOT/'ASAonly - (AUTO)Manual - ModRefresher (RCON).py').read_text(encoding='utf-8')
        method=source.split('def post_ui(self, func):',1)[1].split('def log(',1)[0]
        self.assertIn('_ui_queue.put(func)',method)
        self.assertNotIn('after_idle',method)
        tick=source.split('def _tick(self):',1)[1].split('def ',1)[0]
        self.assertIn('_ui_queue.get_nowait()',tick)

    def test_map_tab_build_has_no_rcon_editor_or_manual_console(self):
        source=(ROOT/'asaonly'/'server_tab.py').read_text(encoding='utf-8')
        build=source.split('def _build(self):',1)[1].split('def _on_map_toggle',1)[0]
        self.assertNotIn('rcon_lines',build)
        self.assertNotIn('admin_rcon',build)
        self.assertNotIn('test_rcon',build)
        self.assertIn('RCON UI intentionally lives only',build)

    def test_disk_panel_does_not_start_scan_automatically(self):
        source=(ROOT/'PLUGINY'/'83_dysk_katalogi.py').read_text(encoding='utf-8')
        panel_body=source.split('def panel(self, parent):',1)[1].split('def _scan(self):',1)[0]
        self.assertNotIn('self._scan()',panel_body)
        self.assertIn('Kliknij SKANUJ TERAZ',panel_body)

    def test_backup_restore_rejects_unsafe_members_and_invalid_json(self):
        import importlib.util, tempfile
        spec=importlib.util.spec_from_file_location('backup_restore_test',ROOT/'PLUGINY'/'80_konfiguracje.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        plugin=mod.Wtyczka()
        self.assertEqual(plugin._safe_member('CONFIG_PROGRAM/ustawienia.json'),'CONFIG_PROGRAM/ustawienia.json')
        for name in ('../x','/CONFIG_PROGRAM/x','CONFIG_PROGRAM/../x','OTHER/x','CONFIG_PROGRAM\\..\\x'):
            self.assertIsNone(plugin._safe_member(name),name)
        with tempfile.TemporaryDirectory() as directory:
            folder=pathlib.Path(directory)/'CONFIG_PROGRAM'; folder.mkdir()
            (folder/'bad.json').write_text('{',encoding='utf-8')
            with self.assertRaises(Exception): plugin._validate_staging(directory)

    def test_backup_restore_rolls_back_if_second_root_install_fails(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('backup_restore_rollback',ROOT/'PLUGINY'/'80_konfiguracje.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory)/'base'; stage=pathlib.Path(directory)/'stage'; rollback=pathlib.Path(directory)/'rollback'
            for root in ('CONFIG_PROGRAM','CONFIG_MAPS_TABS'):
                (base/root).mkdir(parents=True); (base/root/'value.txt').write_text('old-'+root)
                (stage/root).mkdir(parents=True); (stage/root/'value.txt').write_text('new-'+root)
            rollback.mkdir()
            real_replace=mod.os.replace; calls={'n':0}
            def failing_replace(src,dst):
                calls['n']+=1
                if calls['n']==3: raise OSError('simulated interruption')
                return real_replace(src,dst)
            with patch.object(mod.os,'replace',side_effect=failing_replace):
                with self.assertRaises(OSError):
                    mod.Wtyczka._apply_roots(str(base),str(stage),str(rollback),['CONFIG_PROGRAM','CONFIG_MAPS_TABS'])
            self.assertEqual((base/'CONFIG_PROGRAM'/'value.txt').read_text(),'old-CONFIG_PROGRAM')
            self.assertEqual((base/'CONFIG_MAPS_TABS'/'value.txt').read_text(),'old-CONFIG_MAPS_TABS')

    def test_required_coordinator_publishes_queue_state(self):
        app=FakeApp(); host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        plugin=host.get('koordynator_procedur')
        self.assertIsNotNone(plugin)
        self.assertTrue(plugin.required)
        plugin.opublikuj([('A','oglasza','gracze',''),('B','czeka','pusto',''),
                          ('C','zrobiona','pusto','')])
        tekst,_=host.runtime_status['koordynator_procedur']
        self.assertTrue(tekst.startswith('TRWA'))
        self.assertIn('A:',tekst); self.assertIn('B:',tekst); self.assertNotIn('C:',tekst)
        plugin.opublikuj([('A','zrobiona','gracze','')])
        self.assertIn('kolejka zakończona',host.runtime_status['koordynator_procedur'][0])
        for martwe in ('configure','pop_next','has_next','complete_current','pause','snapshot'):
            self.assertFalse(hasattr(plugin,martwe),martwe)

    def test_admin_plugin_default_modes_are_deliberate(self):
        app=FakeApp(); host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        self.assertIsNone(host.get('backup_restore'))            # V3.83: w „Konfiguracje”
        self.assertIsNone(host.get('importer_starych_konfigow'))
        self.assertFalse(host.get('diagnostyka_zip').is_enabled())
        self.assertFalse(host.get('dysk_katalogi').is_enabled())
        self.assertTrue(host.get('konfiguracje').is_enabled())
        self.assertFalse(host.get('analizator_logow').is_enabled())
        self.assertFalse(host.get('status_historia_serwerow').is_enabled())
        rcon=host.get('rcon_admin')
        self.assertTrue(rcon.required)
        self.assertTrue(rcon.is_enabled())

    def test_missing_choice_defaults_only_importer_on_and_diagnoses_no_other_optional(self):
        # V3.82: także „Kontrola czasu RCON” — tylko odczyt, włączona na prośbę
        # użytkownika. V3.85: „Aktualizacja serwera (SteamCMD)” — serwery mają się
        # aktualizować bez człowieka (prośba użytkownika). Każdy inny opcjonalny
        # plugin bez zapisanego wyboru = OFF.
        domyslnie_on={'konfiguracje','kontrola_czasu','aktualizacja_serwera'}
        app=FakeApp(); host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        results=host.run_startup_diagnostics()
        optional={p.nazwa for p in host.visible_plugins() if not p.required}
        self.assertEqual(optional.intersection(host._active),domyslnie_on)
        self.assertEqual(optional.intersection(results),domyslnie_on)
        for name in optional-domyslnie_on:
            self.assertFalse(any('[DIAGNOSTYKA PLUGINU] %s:'%name in line
                                 for line in app.logs),name)

    def test_real_manager_lists_diagnostic_status_plugin(self):
        app=FakeApp(); host=PluginHost(app,str(ROOT/'PLUGINY'))
        host.load_all()
        visible=[p.nazwa for p in host.visible_plugins()]
        self.assertIn('cpu',visible)
        self.assertIn('status_historia_serwerow',visible)
        self.assertNotIn('status_json',visible)
        self.assertNotIn('historia_serwerow',visible)
        status_plugin=host.get('status_historia_serwerow')
        info=host.plugin_info(status_plugin)
        self.assertIn('aktualna migawka',info['description'])
        self.assertIn('historia',info['description'])
        self.assertFalse(status_plugin.is_enabled())

    def test_status_history_plugin_migrates_both_old_plugin_choices(self):
        app=FakeApp()
        app.config_data={'plugins':{
            'status_json':{'enabled':True,'interval_s':17},
            'historia_serwerow':{'enabled':False}}}
        host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        plugin=host.get('status_historia_serwerow')
        self.assertTrue(plugin.is_enabled())
        self.assertTrue(plugin.export_enabled)
        self.assertFalse(plugin.history_enabled)
        self.assertEqual(plugin.interval,17)
        saved=app.config_data['plugins']['status_historia_serwerow']
        self.assertEqual(saved['export_enabled'],True)
        self.assertEqual(saved['history_enabled'],False)

    def test_status_history_off_performs_no_file_work(self):
        plugin=status_history_module.Wtyczka(); plugin.enabled=False
        class Core:
            def tabs(self): raise AssertionError('OFF must not read tabs')
            def mods(self): raise AssertionError('OFF must not read mods')
        plugin.core=Core()
        with tempfile.TemporaryDirectory() as directory:
            plugin.status_path=str(pathlib.Path(directory)/'status.json')
            plugin.history_path=str(pathlib.Path(directory)/'history.jsonl')
            plugin.tik(100); plugin.dane_monitora({'pid':{}})
            self.assertFalse(pathlib.Path(plugin.status_path).exists())
            self.assertFalse(pathlib.Path(plugin.history_path).exists())

    def test_status_history_tail_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'history.jsonl'
            path.write_text(''.join('%d\n' % i for i in range(800)),encoding='utf-8')
            lines=status_history_module.Wtyczka._tail(str(path),500)
            self.assertEqual(len(lines),500)
            self.assertEqual(lines[0],'300\n')

    def test_destroyed_manager_widget_cannot_abort_off_diagnostics(self):
        class DeadLabel:
            def configure(self,**kw): raise RuntimeError('invalid command name')
        class Plugin:
            API=PLUGIN_API; nazwa='off'; manager_visible=True; required=False
            def is_enabled(self): return False
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); plugin=Plugin(); host.plugins=[plugin]
            host.manager_rows['off']={'test':DeadLabel()}
            self.assertEqual(host.run_tests(),{})
            self.assertNotIn('off',host.manager_rows)

    def test_stop_all_discards_all_destroyed_ui_bindings(self):
        class Plugin:
            API=PLUGIN_API; nazwa='p'; required=True
            def start(self,core): pass
        with tempfile.TemporaryDirectory() as td:
            host=PluginHost(FakeApp(),td); host.plugins=[Plugin()]; host.start_all()
            host.manager_window=object(); host.manager_rows={'p':object()}
            host.main_action_buttons={'p':object()}
            host.stop_all()
            self.assertIsNone(host.manager_window)
            self.assertEqual(host.manager_rows,{})
            self.assertEqual(host.main_action_buttons,{})

    def test_off_plugin_is_not_diagnosed_or_given_fake_result(self):
        class Plugin:
            API=PLUGIN_API; nazwa='off'; manager_visible=True; required=False
            calls=0
            def is_enabled(self): return False
            def self_test(self): self.calls+=1; return {'ok':True}
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); plugin=Plugin(); host.plugins=[plugin]
            result=host.run_tests()
            self.assertEqual(plugin.calls,0)
            self.assertNotIn('off',result)
            self.assertNotIn('off',host.last_diagnostics)

    def test_persisted_off_plugins_stay_out_of_startup_diagnostics_after_reopen(self):
        optional_off={
            'konfiguracje','diagnostyka_zip',
            'dysk_katalogi','analizator_logow','status_historia_serwerow','cpu'}
        app=FakeApp()
        app.config_data={'plugins':{name:{'enabled':False} for name in optional_off}}
        host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
        host.load_all(); host.start_all()
        # Even a stale runtime flag must not override the durable OFF choice.
        for name in optional_off:
            plugin=host.get(name)
            if plugin is not None and hasattr(plugin,'enabled'):
                plugin.enabled=True
        results=host.run_startup_diagnostics()
        self.assertTrue(optional_off.isdisjoint(results))
        self.assertTrue(optional_off.isdisjoint(host._active))
        for name in optional_off:
            plugin=host.get(name)
            if plugin is not None:
                self.assertFalse(plugin.is_enabled(),name)
            self.assertNotIn(name,host.last_diagnostics)
            self.assertFalse(any('[DIAGNOSTYKA PLUGINU] %s:'%name in line
                                 for line in app.logs))

    def test_real_disk_reopen_keeps_all_optional_off_out_of_real_startup_diagnostics(self):
        """Behavioral chain: versioned disk -> App loader -> real plugins -> startup diagnostics."""
        from asaonly import zapis
        optional_off={
            'konfiguracje','diagnostyka_zip',
            'dysk_katalogi','analizator_logow','status_historia_serwerow','cpu'}
        with tempfile.TemporaryDirectory() as td, patch(
                'asaonly.zapis.file_stamp', return_value='21.09.2026 07-42-40'):
            enabled={'plugins':{name:{'enabled':True} for name in optional_off}}
            disabled={'plugins':{name:{'enabled':False} for name in optional_off}}
            zapis.save_versioned(td,program_module.CONFIG_BASE,enabled,keep=10)
            off_path=zapis.save_versioned(td,program_module.CONFIG_BASE,disabled,keep=10)
            loader=object.__new__(program_module.App)
            with patch.object(program_module,'CONFIG_DIR',td), \
                 patch.object(program_module,'migrate_old_base'), \
                 patch.object(program_module,'migrate_old_file'):
                loaded=program_module.App._load_config(loader)
            self.assertEqual(zapis.newest_matching(td,program_module.CONFIG_BASE),off_path)
            self.assertEqual(loaded,disabled)

            app=FakeApp(); app.config_data=loaded
            host=PluginHost(app,str(ROOT/'PLUGINY')); app.plugin_host=host
            host.load_all(); host.start_all()
            results=host.run_startup_diagnostics()
            self.assertTrue(optional_off.isdisjoint(results))
            self.assertTrue(optional_off.isdisjoint(host._active))
            for name in optional_off:
                self.assertNotIn(name,host.last_diagnostics)
                self.assertFalse(any(
                    '[DIAGNOSTYKA PLUGINU] %s:'%name in line for line in app.logs),name)
                plugin=host.get(name)
                self.assertIsNotNone(plugin,name)
                self.assertFalse(plugin.is_enabled(),name)

    def test_persisted_off_plugin_never_reaches_operational_start_or_callbacks(self):
        class Broken:
            API=PLUGIN_API; nazwa='broken'; manager_visible=True; required=False
            def __init__(self): self.enabled=True; self.calls=[]
            def start(self,core):
                self.calls.append(('start',))
                self.calls.append(('worker_started',))
            def is_enabled(self): return self.enabled
            def set_enabled(self,value): self.calls.append(('set',value))
            def tik(self,now): self.calls.append(('tick',now))
            def event_hook(self): self.calls.append(('hook',))
        app=FakeApp(); app.config_data={'plugins':{'broken':{'enabled':False}}}
        with tempfile.TemporaryDirectory() as td:
            host=PluginHost(app,td); app.plugin_host=host; plugin=Broken(); host.plugins=[plugin]
            host.start_all()
            host.subscribe('event',lambda payload:plugin.calls.append(('event',payload)),'broken')
            host.tick(1); host.call_hook('event_hook'); host.emit('event',x=1)
            self.assertEqual(plugin.calls,[])
            self.assertNotIn('broken',host._prepared)
            self.assertNotIn('broken',host._active)
            self.assertFalse(host.plugin_info(plugin)['enabled'])

    def test_panel_button_is_disabled_when_off_unless_panel_configures_off_state(self):
        class Button:
            def __init__(self): self.state=None
            def configure(self,**kw): self.state=kw.get('state',self.state)
        class Label:
            def configure(self,**kw): pass
        class Plugin:
            API=PLUGIN_API; nazwa='p'; manager_visible=True; required=False
            enabled=False
            def is_enabled(self): return self.enabled
            def panel(self,parent): pass
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); plugin=Plugin(); host.plugins=[plugin]
            panel=Button(); host.manager_rows['p']={
                'status':Label(),'on_button':Button(),'off_button':Button(),
                'panel_button':panel}
            host._refresh_manager_row('p')
            self.assertEqual(panel.state,'disabled')
            plugin.panel_available_when_off=True
            host._refresh_manager_row('p')
            self.assertEqual(panel.state,'normal')

    def test_manager_uses_real_on_off_buttons_not_checkbox_toggle(self):
        source = (ROOT / 'asaonly' / 'pluginy.py').read_text(encoding='utf-8')
        self.assertIn('actions, text="ON", width=4', source)
        self.assertIn('actions, text="OFF", width=4', source)
        self.assertNotIn('ttk.Checkbutton(actions', source)

    def test_manager_lists_only_user_visible_plugins(self):
        class Hidden:
            API=PLUGIN_API; nazwa='hidden'
        class CpuLike:
            API=PLUGIN_API; nazwa='cpu'; manager_visible=True; required=False; default_enabled=True
            def start(self, core): self.core=core
            def is_enabled(self): return True
            def self_test(self): return {'ok':True,'details':'read-only OK'}
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td)
            host.plugins=[Hidden(),CpuLike()]; host.start_all()
            self.assertEqual([p.nazwa for p in host.visible_plugins()],['cpu'])
            result=host.run_tests('cpu')
            self.assertEqual(result['cpu']['level'],'info')
            self.assertIn('read-only OK',result['cpu']['text'])
            self.assertIn('NIE POTWIERDZA PEŁNEGO DZIAŁANIA',result['cpu']['text'])

    def test_startup_plugin_diagnostics_run_once_and_are_remembered(self):
        class Plugin:
            API=PLUGIN_API; nazwa='diag'; manager_visible=True; required=False; default_enabled=True
            calls=0
            def start(self, core): self.core=core
            def self_test(self):
                self.calls+=1
                return {'ok':True,'details':'odczyt'}
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); plugin=Plugin(); host.plugins=[plugin]; host.start_all()
            first=host.run_startup_diagnostics(); second=host.run_startup_diagnostics()
            self.assertEqual(plugin.calls,1)
            self.assertEqual(first,second)
            host.run_language_change_diagnostics()
            self.assertEqual(plugin.calls,2)
            self.assertEqual(host.last_diagnostics['diag']['level'],'info')
            self.assertTrue(any('Automatyczna kontrola po starcie' in x for x in app.logs))
            self.assertTrue(any('Ponowna kontrola po zmianie języka' in x for x in app.logs))

            # Zmiana języka przed upływem 3 s wyprzedza timer startowy;
            # spóźniony timer nie może wykonać diagnostyki drugi raz.
            app2=FakeApp(); host2=PluginHost(app2,td); plugin2=Plugin(); host2.plugins=[plugin2]; host2.start_all()
            host2.run_language_change_diagnostics()
            host2.run_startup_diagnostics()
            self.assertEqual(plugin2.calls,1)

    def test_main_importer_button_tracks_plugin_on_off(self):
        class Plugin:
            nazwa='importer'; enabled=True; default_enabled=True
            def start(self, core): self.core=core
            def is_enabled(self): return self.enabled
        class Button:
            def __init__(self): self.state=None
            def configure(self,**kw): self.state=kw.get('state')
        with tempfile.TemporaryDirectory() as td:
            host=PluginHost(FakeApp(),td); plugin=Plugin(); button=Button()
            plugin.main_action_requires_enabled=True
            host.plugins=[plugin]; host.start_all(); host.main_action_buttons={'importer':button}
            host._refresh_main_action('importer'); self.assertEqual(button.state,'normal')
            plugin.enabled=False
            host._refresh_main_action('importer'); self.assertEqual(button.state,'disabled')

    def test_required_plugin_cannot_be_disabled_by_manager(self):
        class Required:
            API=PLUGIN_API; nazwa='required'; manager_visible=True; required=True
            def __init__(self): self.calls=[]
            def set_enabled(self,value): self.calls.append(value)
        with tempfile.TemporaryDirectory() as td:
            app=FakeApp(); host=PluginHost(app,td); plugin=Required()
            host.plugins=[plugin]
            host.set_enabled_from_manager('required',False)
            self.assertEqual(plugin.calls,[])

    def test_importer_clears_stale_scan_results_after_import(self):
        class Var:
            def __init__(self, value): self.value=value
            def set(self, value): self.value=value
        class Child:
            def __init__(self): self.destroyed=False
            def destroy(self): self.destroyed=True
        class Frame:
            def __init__(self, children): self.children=children
            def winfo_children(self): return self.children
        plugin=import_module.Wtyczka()
        children=[Child(),Child()]
        plugin.candidates=[{'name':'A'}]; plugin.vars=[Var(True)]
        plugin.api_candidate={'value':'secret'}; plugin.api_var=Var(True)
        plugin.root_var=Var('C:/old'); plugin.summary_var=Var('wyniki')
        plugin.results_frame=Frame(children)
        plugin._clear_after_import()
        self.assertEqual(plugin.candidates,[]); self.assertEqual(plugin.vars,[])
        self.assertIsNone(plugin.api_candidate); self.assertIsNone(plugin.api_var)
        self.assertEqual(plugin.root_var.value,'')
        self.assertIn('Import zakończony',plugin.summary_var.value)
        self.assertTrue(all(child.destroyed for child in children))

    def test_importer_defaults_on_and_explains_when_to_disable(self):
        plugin=import_module.Wtyczka()
        self.assertTrue(plugin.is_enabled())
        self.assertEqual(plugin.main_action_text,'IMPORT / BACKUP')
        self.assertTrue(plugin.main_action_requires_enabled)
        for slowo in ('IMPORT','BACKUP','PRZYWRACANIE'):
            self.assertIn(slowo,plugin.manager_description)
        self.assertIn('można go wyłączyć',plugin.manager_description)
        self.assertIn('nie uruchamia niczego w tle',plugin.manager_description)

    def test_importer_scans_whole_folder_groups_backups_and_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); tab=root/'taby'/'Extinction'; tab.mkdir(parents=True)
            old=tab/'config-old.json'; new=tab/'config-new.json'
            old.write_text(json.dumps({'name':'Extinction','lines':[],'rcon_port':'1'}),encoding='utf-8')
            new.write_text(json.dumps({'name':'Extinction','lines':[],'rcon_port':'2'}),encoding='utf-8')
            os.utime(old,(10,10)); os.utime(new,(20,20))
            before={p:str(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
            report=import_module.Wtyczka.scan_directory(td)
            after={p:str(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after)
            self.assertEqual(len(report['candidates']),1)
            self.assertEqual(report['candidates'][0]['versions'],2)
            self.assertEqual(report['candidates'][0]['config']['rcon_port'],'2')

    def test_importer_has_no_unsafe_native_wndproc_hook(self):
        source=(ROOT/'PLUGINY'/'80_konfiguracje.py').read_text(encoding='utf-8')
        self.assertNotIn('SetWindowLongPtr',source)
        self.assertNotIn('WNDPROC',source)
        self.assertNotIn('DragAcceptFiles',source)

    def test_importer_finds_newest_curseforge_api_key_separately(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); a=root/'old-api.json'; b=root/'new-api.json'
            a.write_text(json.dumps({'api_key':'OLD-SECRET'}),encoding='utf-8')
            b.write_text(json.dumps({'api_key':'NEW-SECRET'}),encoding='utf-8')
            os.utime(a,(10,10)); os.utime(b,(20,20))
            report=import_module.Wtyczka.scan_directory(td)
            self.assertEqual(report['api_versions'],2)
            self.assertEqual(report['api_candidate']['value'],'NEW-SECRET')
            self.assertEqual(report['candidates'],[])
            self.assertNotIn('NEW-SECRET',report['api_candidate']['path'])

    def test_importer_splits_old_global_configuration_into_maps(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'asa_config.json'
            p.write_text(json.dumps({'mod_ids':'11,22','servers':{
                'A':{'lines':[]},'B':{'lines':[]}}}),encoding='utf-8')
            report=import_module.Wtyczka.scan_directory(td)
            self.assertEqual([x['name'] for x in report['candidates']],['A','B'])
            self.assertTrue(all(x['config']['mod_ids']=='11,22' for x in report['candidates']))

    def test_cpu_custom_affinity_accepts_multiple_logical_cpus(self):
        plugin=cpu_module.Wtyczka(); original=cpu_module.os.cpu_count
        try:
            cpu_module.os.cpu_count=lambda:8
            self.assertEqual(plugin._affinity_value('CPU 0,2,3'),(1<<0)|(1<<2)|(1<<3))
        finally:
            cpu_module.os.cpu_count=original

    def test_cpu_recommendations_give_multiple_cpus_per_server(self):
        plugin=cpu_module.Wtyczka(); plugin.benchmark_maps=['A','B','C']
        plugin.benchmark_results={i:100-i for i in range(12)}
        plugin._make_recommendations()
        self.assertEqual(set(plugin.benchmark_recommendations),{'A','B','C'})
        self.assertTrue(all(len(v)==4 for v in plugin.benchmark_recommendations.values()))
        flattened=[x for values in plugin.benchmark_recommendations.values() for x in values]
        self.assertEqual(sorted(flattened),list(range(12)))

    def test_cpu_waits_for_first_monitor_snapshot_before_pid_missing(self):
        class Tab:
            enabled=True; name='A'; rcon_port='7777'; status='ready'
        class Core:
            def __init__(self): self.logs=[]
            def tabs(self): return {'A':Tab()}
            def log(self,msg,tag=None): self.logs.append(str(msg))
            def warn(self,msg): self.logs.append(str(msg))
            def set_indicator(self,*args): pass
        core=Core(); plugin=cpu_module.Wtyczka(); plugin.core=core
        plugin.cfg={'enabled':True,'delay_s':30,'maps':{}}
        plugin._scan(0,apply_changes=True)
        self.assertEqual(core.logs,[])
        self.assertEqual(plugin.states,{})
        plugin.dane_monitora({'pid':{}})
        plugin._scan(1,apply_changes=True)
        self.assertTrue(any('Brak procesu' in line for line in core.logs))

    def test_cpu_state_log_wraps_before_target(self):
        core=FakeApp(); plugin=cpu_module.Wtyczka(); plugin.core=core
        plugin.cfg={'enabled':True,'maps':{'A':{
            'priority_on':True,'priority':'High','affinity_on':False}}}
        state={'pid':12,'server_status':'ready','priority':'High',
               'affinity':'CPU 0,1','result':'ZGODNE','color':'#207020'}
        plugin._log_state_if_changed('A',state)
        self.assertIn('affinity=CPU 0,1\n      → cel:',core.logs[-1])
        self.assertEqual(core.log_tags[-1],'cpu_ok')

    def test_cpu_does_not_write_when_current_state_matches(self):
        plugin=cpu_module.Wtyczka(); plugin.core=FakeApp()
        plugin.cfg={'enabled':True,'delay_s':30,'maps':{'A':{
            'priority_on':True,'priority':'High','affinity_on':True,'affinity':'Wszystkie'}}}
        mask=(1 << (__import__('os').cpu_count() or 1))-1
        state={'pid':7,'priority_value':cpu_module.PRIORITIES['High'],
               'priority':'High','affinity_mask':mask,'affinity':plugin._mask_text(mask)}
        calls=[]; plugin._apply_process=lambda *a: calls.append(a)
        plugin._compare_and_apply('A',state)
        self.assertEqual(calls,[])
        self.assertIn('ZGODNE',state['result'])
        self.assertIn('stan zastany',state['result'])
        self.assertIn('w tej sesji',state['result'])

    def test_cpu_equal_while_global_off_does_not_claim_enforcement(self):
        plugin=cpu_module.Wtyczka(); plugin.core=FakeApp()
        plugin.cfg={'enabled':False,'delay_s':30,'maps':{'A':{
            'priority_on':True,'priority':'High','affinity_on':False,'affinity':'Wszystkie'}}}
        state={'pid':70,'priority_value':cpu_module.PRIORITIES['High'],
               'priority':'High','affinity_mask':3,'affinity':'CPU 0,1'}
        plugin._apply_process=lambda *a: self.fail('must not write')
        plugin._compare_and_apply('A',state)
        self.assertIn('GLOBAL OFF',state['result'])
        self.assertIn('nie egzekwuje',state['result'])

    def test_cpu_changes_only_mismatched_enabled_property(self):
        plugin=cpu_module.Wtyczka(); plugin.core=type('C',(),{'log':lambda self,x,tag=None:None})()
        plugin.cfg={'enabled':True,'delay_s':30,'maps':{'A':{
            'priority_on':True,'priority':'High','affinity_on':False,'affinity':'Wszystkie'}}}
        state={'pid':8,'priority_value':cpu_module.PRIORITIES['RealTime'],
               'priority':'RealTime','affinity_mask':3,'affinity':'CPU 0,1'}
        calls=[]; plugin._apply_process=lambda *a: calls.append(a)
        plugin._read_process=lambda pid:{'priority_value':cpu_module.PRIORITIES['High'],
                                         'affinity_mask':3,'uptime':100,'system_mask':3}
        plugin._compare_and_apply('A',state)
        self.assertEqual(calls,[(8,cpu_module.PRIORITIES['High'],None)])
        self.assertIn('priority',state['result'])
        # A later equal check must disclose that the plugin changed this PID.
        plugin._compare_and_apply('A',state)
        self.assertIn('wykonana przez plugin',state['result'])

    def test_cpu_manager_off_stops_background_scan_and_logs(self):
        plugin=cpu_module.Wtyczka(); plugin.cfg={'enabled':False,'delay_s':30,'maps':{}}
        plugin._scan=lambda *a,**k:self.fail('CPU OFF must not scan in background')
        plugin.tik(100)
        self.assertEqual(plugin.next_check,0.0)

    def test_cpu_manager_on_runs_background_scan(self):
        plugin=cpu_module.Wtyczka(); plugin.cfg={'enabled':True,'delay_s':30,'maps':{}}
        calls=[]; plugin._scan=lambda *a,**k:calls.append((a,k))
        plugin.tik(100)
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0][1]['apply_changes'])

    def test_cpu_global_off_reports_drift_without_writing(self):
        plugin=cpu_module.Wtyczka(); plugin.core=FakeApp()
        plugin.cfg={'enabled':False,'delay_s':30,'maps':{'A':{
            'priority_on':True,'priority':'Normal','affinity_on':False,'affinity':'Wszystkie'}}}
        state={'pid':9,'priority_value':cpu_module.PRIORITIES['RealTime'],
               'priority':'RealTime','affinity_mask':3,'affinity':'CPU 0,1'}
        calls=[]; plugin._apply_process=lambda *a: calls.append(a)
        plugin._compare_and_apply('A',state)
        self.assertEqual(calls,[])
        self.assertIn('plugin OFF',state['result'])

if __name__=='__main__': unittest.main()
