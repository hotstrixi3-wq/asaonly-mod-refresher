import importlib.util
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
spec = importlib.util.spec_from_file_location("asaonly", PROGRAM)
asa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asa)


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value


class Tab:
    def __init__(self, name, port="27020", status="ready", mods=()):
        self.name = name
        self.var_map_on = Var(True)
        self.var_port = Var(port)
        self.var_log = Var("x")
        self._tail_status = status
        self._boot_seq = 0
        self._mods = list(mods)
    def get_effective_mod_ids(self): return self._mods
    def set_lines_editable(self, value): pass


class SafetyTests(unittest.TestCase):
    def test_procedure_checkpoint_uses_one_authoritative_file_not_config_backups(self):
        with tempfile.TemporaryDirectory() as td, patch.object(asa, 'CONFIG_DIR', td):
            app=object.__new__(asa.App); app._save_pending=False
            app.log=lambda *a,**k: None; app.tr=lambda key,**kw:key
            for stage in range(40):
                app.procedure_run={'run_id':'r1','stage':'s%d'%stage}
                self.assertTrue(asa.App.save_procedure_state(app))
            files=list(pathlib.Path(td).iterdir())
            self.assertEqual([p.name for p in files],[asa.PROCEDURE_STATE_NAME])
            self.assertEqual(asa.App._load_procedure_state(app)['stage'],'s39')

    def test_invalid_procedure_checkpoint_blocks_fail_closed(self):
        with tempfile.TemporaryDirectory() as td, patch.object(asa, 'CONFIG_DIR', td):
            pathlib.Path(td,asa.PROCEDURE_STATE_NAME).write_text(
                '{"procedure_run":"broken"}',encoding='utf-8')
            app=object.__new__(asa.App)
            run=asa.App._load_procedure_state(app)
            self.assertEqual(run['stage'],'invalid_checkpoint')
            self.assertTrue(bool(run))

    def test_rename_migrates_pending_targets_and_verified_names(self):
        from asaonly.procedura import rename_pending_target
        records=[{'mid':'1','targets':['Old','Other'],'verified':['Old']},
                 {'mid':'2','targets':['Old','New'],'verified':[]}]
        self.assertTrue(rename_pending_target(records,'Old','New'))
        self.assertEqual(records[0]['targets'],['New','Other'])
        self.assertEqual(records[0]['verified'],['New'])
        self.assertEqual(records[1]['targets'],['New'])

    def test_checkpoint_failure_does_not_block_doexit(self):
        # V3.81 (aksjomat akceleratora): zapis stanu procedury jest tylko
        # informacyjny. Nieudany zapis ostrzega raz i NIE zatrzymuje RCON.
        app=object.__new__(asa.App)
        app.plugin_host=object(); app.procedure_run={'run_id':'r1'}
        app.save_procedure_state=lambda: False
        warnings=[]; sent=[]
        app.log_warn=warnings.append
        app._rcon_enqueue=lambda tab,cmd,cb=None: sent.append(cmd)
        self.assertFalse(asa.App._checkpoint_procedure(app,'doexit_armed',map='A'))
        self.assertFalse(asa.App._checkpoint_procedure(app,'doexit_sent',map='A'))
        self.assertEqual(len(warnings),1)
        asa.App._wyslij_doexit(app,Tab('A'),'DoExit')
        self.assertEqual(sent,['DoExit'])

    def test_interrupted_procedure_is_abandoned_not_blocking(self):
        app=object.__new__(asa.App)
        app.plugin_host=object(); app.procedure_run={'run_id':'r1','stage':'doexit_sent','map':'A'}
        saved=[]; warnings=[]
        app.save_procedure_state=lambda: saved.append(app.procedure_run) or True
        app.log_warn=warnings.append
        asa.App._porzuc_przerwana_procedure(app)
        self.assertIsNone(app.procedure_run)
        self.assertEqual(saved,[None])
        self.assertTrue(any('Porzucam' in w for w in warnings))
        self.assertNotIn('_procedure_recovery_blocked',app.__dict__)

    def test_save_config_propagates_map_or_secret_failure(self):
        class Fake:
            lang='pl'; var_interval=Var('60'); var_cf_delay=Var('1')
            var_watch=Var('20'); auto_rcon=Var(True); pending_updates=[]
            var_mod_wait=Var('5')
            _mod_wait_minutes=asa.App._mod_wait_minutes
            known_versions={}; mod_names={}; mod_pages={}; monitor_off=set()
            config_data={'plugins':{}}; _core_w=800; _panel_w={'mods':400}
            _win_open={'mods':False}; _win_pos={'mods':(None,None)}; tabs={'A':object()}
            _save_pending=False
            def save_tab(self,tab,silent=False): return False
            def save_tab_secrets(self,tab,silent=False): return True
            def save_secrets(self,silent=False): return True
            def tr(self,key,**kwargs): return key
            def log(self,*args,**kwargs): pass
        fake=Fake()
        fake.var_mod_wait=Var('5')
        # V3.81: save_config zapisuje też PROCEDURE_RUN_STATE.json — test nie może
        # pisać do prawdziwego CONFIG_PROGRAM obok programu (V3.80.35 tak robił
        # i plik trafiał do paczki).
        with tempfile.TemporaryDirectory() as td, patch.object(asa, 'CONFIG_DIR', td), \
                patch.object(asa,'save_versioned',return_value=True):
            self.assertFalse(asa.App.save_config(fake,silent=True))
        self.assertTrue(fake._save_pending)

    def test_cf_worker_does_not_mutate_shared_version_dicts_directly(self):
        source=(ROOT/'asaonly'/'cf_wersje.py').read_text(encoding='utf-8')
        worker=source.split('def _cf_worker(',1)[1].split('def _apply_cf_metadata',1)[0]
        self.assertNotIn('self.mod_names[mid] =',worker)
        self.assertNotIn('self.mod_pages[mid] =',worker)
        self.assertNotIn('self.mod_latest[mid] =',worker)
        self.assertNotIn('self.known_versions[mid] =',worker)
        self.assertIn('self.post_ui',worker)

    def test_first_cf_check_end_to_end_does_not_baseline_old_server(self):
        from asaonly.cf_wersje import CurseForgeMixin
        class Bool:
            def get(self): return True
        class Text:
            def __init__(self,v): self.v=v
            def get(self): return self.v
        class T:
            var_map_on=Bool()
            def __init__(self,name,mods,versions): self.name=name; self.mods=mods; self._server_versions=versions
            def get_effective_mod_ids(self): return self.mods
        class App(CurseForgeMixin):
            def __init__(self):
                self.tabs={'Old':T('Old',['111'],{'111':'90'}),'Current':T('Current',['111'],{'111':'100'}),
                           'Other':T('Other',['222'],{'222':'50'}),'Unknown':T('Unknown',['111'],{})}
                self.var_interval=Text('300'); self.var_api_key=Text('key'); self.var_cf_delay=Text('0')
                self.check_in_progress=False; self._destroying=False; self._no_key_warned=False
                self.mod_names={}; self.mod_pages={}; self.mod_latest={}; self.known_versions={}
                self.completed=None; self.logs=[]
            def _mods_dir_for_tab(self,tab): return None
            def _installed_file_ids(self,path): return []
            def run_async(self,fn,*args): fn(*args)
            def post_ui(self,fn): fn()
            def _set_mod_state(self,*args): pass
            def request_save(self): pass
            def log(self,msg,*args): self.logs.append(str(msg))
            def log_warn(self,msg): self.logs.append(str(msg))
            def tr(self,key,**kwargs): return key
            def _cf_done(self,updates): self.completed=updates; self.check_in_progress=False
            def _cf_cleanup(self): self.check_in_progress=False
            def _handle_cf_error(self,*args): pass
        app=App()
        batch={'111':{'name':'M','page':'p','fid':'100','fname':'f'},
               '222':{'name':'N','page':'p','fid':'50','fname':'f'}}
        with patch('asaonly.cf_wersje.cf_get_mods_batch',return_value=batch): app.check_now()
        update=next(x for x in app.completed if x[0]=='111')
        self.assertEqual(update[3],['Old'])
        self.assertNotIn('Current',update[3]); self.assertNotIn('Other',update[3]); self.assertNotIn('Unknown',update[3])
        self.assertTrue(any('Unknown' in line and 'bez automatycznej procedury' in line for line in app.logs))

    def test_cf_qualifies_only_maps_with_confirmed_older_version(self):
        from asaonly.cf_wersje import CurseForgeMixin
        versions={
            'Old':{'111':{'fid':'90','source':'loaded_log'}},
            'Current':{'111':{'fid':'100','source':'loaded_log'}},
            'Newer':{'111':{'fid':'110','source':'registry'}},
            'Unknown':{'111':{'fid':None,'source':'unknown'}},
            'DoesNotUseMod':{},
        }
        targets,unknown=CurseForgeMixin._classify_map_versions('111','100',versions)
        self.assertEqual(targets,['Old'])
        self.assertEqual(unknown,['Unknown'])

    def test_large_log_without_ready_marker_stays_unknown(self):
        from asaonly.logtail import LogTail
        class Tab:
            name='A'
            class App:
                def tr(self,key): return key
            app=App()
        tail=object.__new__(LogTail); tail.tab=Tab(); tail._status='unknown'
        emitted=[]; tail.callback=lambda tab,status,line: emitted.append(status)
        # Rozmiar logu nie jest już w ogóle argumentem (BIG_LOG usunięty w 3.80).
        tail._infer_initial_state('ordinary line without marker')
        self.assertEqual(tail._status,'unknown')
        self.assertEqual(emitted[-1],'unknown')

    def test_monitor_marks_missing_previously_seen_dead_pid_offline(self):
        from asaonly.monitor_plugin import MonitorMixin
        class Var:
            def get(self): return '27020'
        class Tab: var_port=Var()
        class App(MonitorMixin):
            def _proc_zyje(self,pid): return False
        app=App(); app._last_pid_by_port={'27020':123}
        self.assertEqual(app._tab_alive(Tab(),{}),(False,123))

    def test_imported_map_pulls_delayed_cf_check_forward(self):
        from asaonly.cf_wersje import CurseForgeMixin
        obj = object.__new__(type('CFApp', (CurseForgeMixin,), {}))
        obj.next_check = 10_000.0
        with patch('asaonly.cf_wersje.time.time', return_value=100.0):
            obj.schedule_immediate_mod_check()
        self.assertEqual(obj.next_check, 100.1)

    def test_immediate_cf_schedule_never_postpones_earlier_check(self):
        from asaonly.cf_wersje import CurseForgeMixin
        obj = object.__new__(type('CFApp', (CurseForgeMixin,), {}))
        obj.next_check = 50.0
        with patch('asaonly.cf_wersje.time.time', return_value=100.0):
            obj.schedule_immediate_mod_check()
        self.assertEqual(obj.next_check, 50.0)

    def test_selects_windows_server_artifact_without_plus_three_rule(self):
        files = [
            {"id": 103, "fileName": "mod-client.zip"},
            {"id": 101, "fileName": "mod-windowsserver.zip"},
            {"id": 105, "fileName": "mod-console.zip"},
        ]
        selected, confident = asa.select_server_artifact(files)
        self.assertEqual(selected["id"], 101)
        self.assertTrue(confident)

    def test_artifact_selector_has_explicit_fallback(self):
        selected, confident = asa.select_server_artifact([
            {"id": 10, "fileName": "unknown-a"},
            {"id": 12, "fileName": "unknown-b"}])
        self.assertEqual(selected["id"], 12)
        self.assertFalse(confident)

    def test_parses_real_cfcore_events(self):
        e = asa.parse_cfcore_event("LogCFCore: Mod: Cybers QoL (940975) requires upgrade/downgrade (8673705 -> 8837561)")
        self.assertEqual((e["type"], e["mod_id"], e["file_id"]),
                         ("upgrade_required", "940975", "8837561"))
        e = asa.parse_cfcore_event("Successfully installed mod 'Tools' (modId=941450, fileId=8828067)")
        self.assertEqual((e["type"], e["mod_id"], e["file_id"]),
                         ("install_succeeded", "941450", "8828067"))
        self.assertEqual(asa.parse_cfcore_event("Starting download - 1 parts for https://example")["type"],
                         "download_started")

    def test_parses_loaded_mod_version_pairs(self):
        e = asa.parse_cfcore_event("UShooterEngine::LoadGameMods with: 940975 (8837561), 941450 (8828067)")
        self.assertEqual(e["mods"], {"940975":"8837561", "941450":"8828067"})

    def test_reads_real_cfcore_library_schema_and_weird_id_casing(self):
        path = ROOT / "tests" / "fixtures" / "library_cfcore_real_schema.json"
        self.assertEqual(asa.read_cfcore_library(str(path)), {
            "928548": "7005633", "940975": "8837561"})

    def test_reads_full_attached_library(self):
        # Optional local integration fixture supplied by the server owner.
        path = pathlib.Path("/home/user/uploads/library.json")
        if not path.exists():
            self.skipTest("attached production library not available")
        rows = asa.read_cfcore_library(str(path))
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows["928548"], "7005633")
        self.assertEqual(rows["940975"], "8837561")

    def test_doexit_detection_does_not_match_chat_text(self):
        # V3.84: jedyna reguła DoExit mieszka w asaonly/kolejka.py.
        from asaonly.kolejka import jest_doexit
        self.assertTrue(jest_doexit("DoExit"))
        self.assertTrue(jest_doexit("  doexit  "))
        self.assertFalse(jest_doexit("ServerChat DoExit za minutę"))
        self.assertFalse(jest_doexit("NotDoExit"))

    def test_empty_enabled_row_is_ignored(self):
        rows, err = asa.validate_rcon_line_values([("", ""), ("5", "DoExit")])
        self.assertIsNone(err)
        self.assertEqual(rows, [(5, "DoExit")])

    def test_half_empty_row_is_error(self):
        self.assertEqual(asa.validate_rcon_line_values([("", "DoExit")])[1], "time")
        self.assertEqual(asa.validate_rcon_line_values([("5", "")])[1], "command")

    def test_negative_and_non_numeric_time_are_errors(self):
        self.assertEqual(asa.validate_rcon_line_values([("-1", "DoExit")])[1], "time")
        self.assertEqual(asa.validate_rcon_line_values([("abc", "DoExit")])[1], "time")

    def test_duplicate_ports_only_among_enabled_maps(self):
        got = asa.duplicate_enabled_ports([
            ("A", True, "27020"), ("B", True, 27020),
            ("C", False, "27020"), ("D", True, "27021")])
        self.assertEqual(got, {"27020": ["A", "B"]})

    def test_pending_is_keyed_by_mod_id_not_name(self):
        app = object.__new__(asa.App)
        app.pending_updates = []
        app.tabs = {"A": Tab("A", mods=["111"]), "B": Tab("B", mods=["222"])}
        asa.App._add_or_update_pending(app, "111", "Same name", "100")
        asa.App._add_or_update_pending(app, "222", "Same name", "200")
        self.assertEqual([p["mid"] for p in app.pending_updates], ["111", "222"])
        self.assertEqual(app.pending_updates[0]["targets"], ["A"])
        self.assertEqual(app.pending_updates[1]["targets"], ["B"])

    def test_newer_pending_resets_verification(self):
        app = object.__new__(asa.App)
        app.tabs = {"A": Tab("A", mods=["111"])}
        app.pending_updates = [{"mid":"111", "name":"M", "fid":"100",
                                "targets":["A"], "verified":["A"]}]
        asa.App._add_or_update_pending(app, "111", "M", "101")
        self.assertEqual(app.pending_updates[0]["fid"], "101")
        self.assertEqual(app.pending_updates[0]["verified"], [])

    def test_watch_does_not_accept_already_ready_map(self):
        app = object.__new__(asa.App)
        tab = Tab("A", status="ready")
        app.watch_active = True
        app.watch_t0 = time.time()
        app.watch_deadline = time.time() + 100
        app.watch_maps = {"A": {"done":False, "failed":False, "tab":tab,
                                "ready_t":0, "departed":False, "boot_seq":0}}
        app.pending_updates = []
        app.updated_mods = []
        app.auto_rcon = Var(False)
        app.log = lambda *a, **k: None
        app.tr = lambda key, **kw: key
        app._verify_local_mods = lambda: None
        asa.App._tick_return_watch(app)
        self.assertFalse(app.watch_maps["A"]["done"])

    def test_watch_accepts_ready_only_after_departure(self):
        app = object.__new__(asa.App)
        tab = Tab("A", status="starting")
        app.watch_active = True
        app.watch_t0 = time.time()
        app.watch_deadline = time.time() + 100
        app.watch_maps = {"A": {"done":False, "failed":False, "tab":tab,
                                "ready_t":0, "departed":False, "boot_seq":0}}
        app.pending_updates = []
        app.updated_mods = []
        app.auto_rcon = Var(False)
        app.log = lambda *a, **k: None
        app.tr = lambda key, **kw: key
        app._verify_local_mods = lambda: None
        asa.App._tick_return_watch(app)
        self.assertTrue(app.watch_maps["A"]["departed"])
        tab._tail_status = "ready"
        tab._boot_seq = 1
        tab._ready_proof = "new-log-ready"
        asa.App._tick_return_watch(app)
        self.assertFalse(app.watch_active)

    def test_doexit_success_does_not_clear_pending_or_advance_known(self):
        # Udany DoExit tylko uzbraja czuwanie. Zaległość znika dopiero po
        # prawdziwym nowym starcie i potwierdzeniu wersji.
        from asaonly.kolejka import Kolejka, Mapa, START
        app = object.__new__(asa.App)
        app.pending_updates = [{"mid":"111", "name":"M", "fid":"100",
                                "targets":["A"], "verified":[]}]
        app.known_versions = {"111":"99"}
        app.tabs = {"A": Tab("A")}
        app._proc_map_results = {"A":{"doexit_ok":False,"boot_seq":0}}
        app.log = lambda *a, **k:None
        app.tr = lambda key, **kw:key
        watched=[]
        app._start_return_watch = lambda names: watched.extend(names)
        q = Kolejka([Mapa("A",[(0,"DoExit")])], sondy=False)
        app._kolejka = q
        self.assertEqual(q.tick(1000.0), [("doexit","A","DoExit")])
        asa.App._wynik_doexit(app, "A", "DoExit", None)
        self.assertEqual(q.mapa("A").stan, START)
        self.assertEqual(watched, ["A"])
        self.assertTrue(app._proc_map_results["A"]["doexit_ok"])
        self.assertEqual(app.known_versions["111"], "99")
        self.assertEqual(len(app.pending_updates), 1)

    def test_legacy_pending_is_requalified_per_map_before_any_restart(self):
        app=object.__new__(asa.App)
        old,current,unknown=Tab('Old'),Tab('Current'),Tab('Unknown')
        for tab in (old,current,unknown): tab.var_map_on=Var(True); tab._server_versions={}
        old._server_versions={'111':'90'}; current._server_versions={'111':'100'}
        app.tabs={'Old':old,'Current':current,'Unknown':unknown}
        app.pending_updates=[{'mid':'111','name':'M','fid':'100','targets':['Old','Current','Unknown'],'verified':[]}]
        app._mods_dir_for_tab=lambda tab:None; app._installed_file_ids=lambda path:[]; warnings=[]
        app.log_warn=warnings.append
        asa.App._requalify_legacy_pending(app)
        self.assertEqual(app.pending_updates[0]['targets'],['Old'])
        self.assertTrue(app.pending_updates[0]['qualified'])
        self.assertTrue(any('Unknown' in text for text in warnings))

    def test_post_boot_verification_rejects_disk_only_version_without_loaded_log_proof(self):
        app=object.__new__(asa.App); tab=Tab('A'); tab._boot_seq=1; tab._server_versions={}
        app.tabs={'A':tab}; app.pending_updates=[{'mid':'111','name':'M','fid':'100','targets':['A'],'verified':[]}]
        app.known_versions={'111':'99'}; app._proc_map_results={'A':{'doexit_ok':True,'boot_seq':0}}
        app._mods_dir_for_tab=lambda tab:'A'; app._installed_file_ids=lambda path:[('111','103')]
        app._refresh_pending_ui=lambda:None; app.request_save=lambda:None; app._set_mod_state=lambda *a:None
        with patch('asaonly.procedura.os.path.isdir',return_value=True): asa.App._verify_local_mods(app)
        self.assertEqual(app.pending_updates[0]['verified'],[])
        tab._server_versions={'111':'103'}
        tab._ready_proof = "new-log-ready"
        with patch('asaonly.procedura.os.path.isdir',return_value=True): asa.App._verify_local_mods(app)
        self.assertEqual(app.pending_updates,[])

    def test_local_verification_requires_every_target(self):
        app = object.__new__(asa.App)
        a, b = Tab("A"), Tab("B")
        app.tabs = {"A":a, "B":b}
        app.monitor_off = set()
        app.pending_updates = [{"mid":"111", "name":"M", "fid":"100",
                                "targets":["A","B"], "verified":[]}]
        app.known_versions = {"111":"99"}
        app._mods_dir_for_tab = lambda tab: tab.name
        app._installed_file_ids = lambda path: [("111","103")] if path == "A" else []
        app._refresh_pending_ui = lambda: None
        app.request_save = lambda: None
        app._set_mod_state = lambda *a: None
        old_isdir = asa.os.path.isdir
        asa.os.path.isdir = lambda p: True
        try:
            asa.App._verify_local_mods(app)
        finally:
            asa.os.path.isdir = old_isdir
        self.assertEqual(app.pending_updates[0]["verified"], ["A"])
        self.assertEqual(app.known_versions["111"], "99")


if __name__ == "__main__":
    unittest.main()
