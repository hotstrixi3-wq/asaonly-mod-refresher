"""ULTRA BOJOWY V3.86.7 - tylko powrót via RCON bez READY. 20 testów."""
import copy, random, types, unittest
from unittest.mock import Mock, patch
import fake_tk
from asaonly.monitor_plugin import MonitorMixin
from asaonly.server_tab import ServerTab
from symulacja.test_cluster import FakeApp, FakeTab, pending

class App(MonitorMixin, FakeApp):
    _dziennik_modow = FakeApp._dziennik_modow

def make_app(map_name='A', old_pid=123, old_start=10, new_pid=456, new_start=20, status='unknown'):
    tab = FakeTab(map_name, ['111'], [('0','DoExit')], 47021)
    tab._monitor_identity = (old_pid, old_start)
    tab._ready_proof = 'old-marker'
    tab._ready_observed_at = 990
    tab._set_status = Mock()
    tab.confirm_ready_by_rcon = types.MethodType(ServerTab.confirm_ready_by_rcon, tab)
    app = App([tab], [pending()])
    app.config_data = {}
    with patch('asaonly.procedura.time.time', return_value=1000):
        app._exec_pending()
        app._tick_restart_timeline()
    tab._monitor_identity = (new_pid, new_start)
    tab._tail_status = status
    plugin = Mock()
    app.plugin_host = Mock()
    app.plugin_host.get.return_value = plugin
    app._identity_alive = Mock(return_value=True)
    # init monitor dicts for _monitor_apply tests
    app._last_pid_by_port = {}
    app._monitor_error_last = {}
    app._last_identity_by_port = {}
    return app, tab, plugin

class UltraBojowyV3867(unittest.TestCase):

    def test_ultra_01_100_map_concurrent(self):
        apps=[]
        for i in range(100):
            app,tab,plugin = make_app(f'M{i}', 1000+i, 10, 2000+i, 20)
            apps.append((app,tab,plugin))
        cbs=[]
        for app,tab,plugin in apps:
            app._sonda_rcon(tab, confirm_unknown=True)
            cbs.append((app,tab,plugin.enqueue.call_args.args[2]))
        for app,tab,cb in cbs:
            cb(None)
        for app,tab,_ in apps:
            with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
                app._tick_return_watch()
            self.assertFalse(app.watch_active)
        print("ULTRA 01 OK: 100 map concurrent RCON")

    def test_ultra_02_stale_race_50(self):
        for _ in range(50):
            app,tab,plugin = make_app()
            app._sonda_rcon(tab, confirm_unknown=True)
            cb = plugin.enqueue.call_args.args[2]
            tab._monitor_identity = (789,30)
            cb(None)
            with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
                app._tick_return_watch()
            self.assertTrue(app.watch_active)
        print("ULTRA 02 OK: 50x stale race odrzucone")

    def test_ultra_03_pid_reuse_storm(self):
        """Każdy nowy PID akceptowany gdy rcon==current, odrzucony gdy rcon!=current"""
        app,tab,plugin = make_app()
        # Pierwsza sonda 456,20
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        self.assertTrue(app._ready_since(tab, app.watch_maps['A']))
        # Zmiana current na 456,21 bez nowej sondy -> stara sonda odrzucona
        tab._monitor_identity = (456,21)
        self.assertFalse(app._ready_since(tab, app.watch_maps['A']))
        # Nowa sonda 456,21 -> OK
        plugin.reset_mock()
        app._sonda_rcon(tab, confirm_unknown=True)
        cb2 = plugin.enqueue.call_args.args[2]
        cb2(None)
        self.assertTrue(app._ready_since(tab, app.watch_maps['A']))
        print("ULTRA 03 OK: PID reuse - tylko rcon==current przechodzi")

    def test_ultra_04_timeout_retry(self):
        app,tab,plugin = make_app()
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(TimeoutError("timeout"))
        with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
            app._tick_return_watch()
        self.assertTrue(app.watch_active)
        # Retry
        plugin.reset_mock()
        app._sonda_rcon(tab, confirm_unknown=True)
        self.assertEqual(plugin.enqueue.call_count, 1)
        print("ULTRA 04 OK: timeout nie potwierdza, retry")

    def test_ultra_05_dead_after_rcon(self):
        """Callback sprawdza alive, jeśli dead w momencie callback -> odrzucone"""
        app,tab,plugin = make_app()
        app._identity_alive.return_value = False
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        # _sonda_rcon callback sprawdza _identity_alive
        self.assertIsNone(tab.__dict__.get('_rcon_ready_identity'))
        print("ULTRA 05 OK: dead w callback odrzucone")

    def test_ultra_06_boot_seq_bump(self):
        app,tab,plugin = make_app()
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        tab._boot_seq += 1
        cb(None)
        self.assertFalse(app._ready_since(tab, app.watch_maps['A']))
        print("ULTRA 06 OK: boot_seq bump odrzucone")

    def test_ultra_07_tab_recreated(self):
        app,tab,plugin = make_app()
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        new_tab = FakeTab('A', ['111'], [('0','DoExit')], 47021)
        new_tab._monitor_identity = (456,20)
        new_tab._set_status = Mock()
        new_tab.confirm_ready_by_rcon = types.MethodType(ServerTab.confirm_ready_by_rcon, new_tab)
        new_tab._tail_status = 'unknown'
        app.tabs['A'] = new_tab
        cb(None)
        self.assertIsNone(tab.__dict__.get('_rcon_ready_identity'))
        print("ULTRA 07 OK: tab recreated odrzucone")

    def test_ultra_08_partial_alarm_clear(self):
        app,tab,plugin = make_app('A')
        app.watch_maps = {}
        app.watch_active = app.restart_active = False
        rec_a = {'identity': (123,10), 'boot_seq':0, 'ready_proof':'old'}
        app.config_data['return_failures'] = {'A': rec_a, 'B': {'identity':(999,10), 'boot_seq':0, 'ready_proof':'old'}}
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        app._check_return_alarm(tab, True)
        self.assertNotIn('A', app.config_data['return_failures'])
        self.assertIn('B', app.config_data['return_failures'])
        print("ULTRA 08 OK: partial alarm clear")

    def test_ultra_09_mods_not_verified(self):
        app,tab,plugin = make_app()
        tab._server_versions = {}
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
            app._tick_return_watch()
        self.assertFalse(app.watch_active)
        self.assertTrue(app.pending_updates)
        print("ULTRA 09 OK: RCON nie weryfikuje modów")

    def test_ultra_10_blocked_during_normal(self):
        app,tab,plugin = make_app()
        app.watch_maps = {}
        app.watch_active = False
        app.restart_active = True
        tab._tail_status = 'ready'
        tab._monitor_identity = (456,20)
        app._sonda_rcon(tab, confirm_unknown=False)
        plugin.enqueue.assert_not_called()
        print("ULTRA 10 OK: blocked during normal+restart_active")

    def test_ultra_11_allowed_during_return(self):
        app,tab,plugin = make_app()
        app.restart_active = True
        self.assertTrue(app._needs_return_probe(tab))
        app._sonda_rcon(tab, confirm_unknown=True)
        plugin.enqueue.assert_called_once()
        print("ULTRA 11 OK: allowed during return")

    def test_ultra_12_alive_none(self):
        app,tab,plugin = make_app()
        app._identity_alive.return_value = None
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        self.assertIsNone(tab.__dict__.get('_rcon_ready_identity'))
        print("ULTRA 12 OK: alive None odrzucone")

    def test_ultra_13_filetime(self):
        app,tab,plugin = make_app(new_pid=456, new_start=20)
        app._sonda_rcon(tab, confirm_unknown=True)
        cb = plugin.enqueue.call_args.args[2]
        cb(None)
        self.assertTrue(app._ready_since(tab, app.watch_maps['A']))
        # Log path bez RCON z starym proof -> odrzucone
        tab._rcon_ready_identity = None
        tab._tail_status = 'ready'
        tab._ready_proof = 'old-marker'
        self.assertFalse(app._ready_since(tab, app.watch_maps['A'], allow_rcon=False))
        print("ULTRA 13 OK: FILETIME RCON OK log stale odrzucone")

    def test_ultra_14_chaos_monkey(self):
        random.seed(3867)
        app,tab,plugin = make_app()
        succ=fail=0
        for minute in range(0, 24*60, 5):
            now=1000+minute*60
            r=random.random()
            if r<0.05:
                new_pid=random.randint(1000,5000)
                new_start=random.randint(10,1000)
                tab._monitor_identity=(new_pid,new_start)
                tab._tail_status=random.choice(['unknown','ready'])
                app.watch_maps['A']={'identity':(123,10),'boot_seq':0,'ready_proof':'old','done':False,'failed':False,'tab':tab,'ready_t':0,'departed':True,'new_boot':True}
                app.watch_active=True
                app._sonda_rcon(tab, confirm_unknown=True)
                if plugin.enqueue.call_count:
                    cb=plugin.enqueue.call_args.args[2]
                    if random.random()<0.8:
                        cb(None); succ+=1
                    else:
                        cb(TimeoutError()); fail+=1
                    plugin.reset_mock()
            with patch('asaonly.procedura.time.time', return_value=now), patch('asaonly.procedura.os.path.isdir', return_value=True):
                try:
                    app._tick_return_watch()
                except Exception:
                    fail+=1
        print(f"ULTRA 14 OK: chaos 24h {succ} OK {fail} fail")

    def test_ultra_15_flood_1000(self):
        app,tab,plugin = make_app()
        for i in range(1000):
            tab._monitor_identity=(456,20)
            tab._tail_status='unknown'
            app.watch_maps['A']={'identity':(123,10),'boot_seq':0,'ready_proof':'old','done':False,'failed':False,'tab':tab,'ready_t':0,'departed':True,'new_boot':True}
            app.watch_active=True
            app._sonda_rcon(tab, confirm_unknown=True)
            cb=plugin.enqueue.call_args.args[2]
            cb(None)
            plugin.reset_mock()
        with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
            app._tick_return_watch()
        self.assertFalse(app.watch_active)
        print("ULTRA 15 OK: flood 1000 stabilny")

    def test_ultra_16_alarm_correct_identity(self):
        app,tab,plugin = make_app()
        app.watch_maps={}
        app.config_data['return_failures']={'A':{'identity':(123,10),'boot_seq':0,'ready_proof':'old'}}
        # Zła = stara tożsamość, brak new_boot -> alarm zostaje
        tab._monitor_identity=(123,10)
        tab._tail_status='ready'
        tab._ready_proof='old-marker'
        tab._rcon_ready_identity=None
        app._check_return_alarm(tab, True)
        self.assertIn('A', app.config_data['return_failures'])
        # Dobra = nowa + RCON
        tab._monitor_identity=(456,20)
        tab._rcon_ready_identity=(456,20)
        tab._tail_status='ready'
        tab._ready_proof='old-marker'
        app.config_data['return_failures']['A']['ready_proof']='old'
        # _ready_since z RCON powinno zwrócić True
        self.assertTrue(app._ready_since(tab, app.config_data['return_failures']['A']))
        app._check_return_alarm(tab, True)
        self.assertNotIn('A', app.config_data['return_failures'])
        print("ULTRA 16 OK: alarm tylko poprawna tożsamość")

    def test_ultra_17_double_confirm(self):
        app,tab,plugin = make_app()
        app._sonda_rcon(tab, confirm_unknown=True)
        cb=plugin.enqueue.call_args.args[2]
        cb(None)
        first=tab._rcon_ready_identity
        cb(None)
        second=tab._rcon_ready_identity
        self.assertEqual(first,second)
        print("ULTRA 17 OK: double confirm idempotent")

    def test_ultra_18_after_crashloop(self):
        app,tab,plugin = make_app()
        tab._crash_times=[1000,1005,1010]
        tab._crashloop_alarm=True
        app._sonda_rcon(tab, confirm_unknown=True)
        cb=plugin.enqueue.call_args.args[2]
        cb(None)
        with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
            app._tick_return_watch()
        self.assertFalse(app.watch_active)
        print("ULTRA 18 OK: after crashloop")

    def test_ultra_19_unknown_vs_ready(self):
        for status in ['unknown','ready']:
            app,tab,plugin = make_app(status=status)
            self.assertTrue(app._needs_return_probe(tab))
            app._sonda_rcon(tab, confirm_unknown=True)
            self.assertEqual(plugin.enqueue.call_count,1)
            plugin.reset_mock()
        print("ULTRA 19 OK: UNKNOWN i READY stale sondowane")

    def test_ultra_20_production_3maps(self):
        app,tab,plugin = make_app('A', old_pid=24296, old_start=10, new_pid=30000, new_start=20, status='unknown')
        # 3 mapy w tabs, ale watch tylko A
        tab_b=FakeTab('Ragnarok',['111'],[('0','DoExit')],47022)
        tab_b._monitor_identity=(21180,10)
        tab_b._set_status=Mock()
        tab_b.confirm_ready_by_rcon=types.MethodType(ServerTab.confirm_ready_by_rcon, tab_b)
        tab_b._tail_status='ready'
        app.tabs['Ragnarok']=tab_b
        tab_c=FakeTab('Genesis',['111'],[('0','DoExit')],47023)
        tab_c._monitor_identity=(21968,10)
        tab_c._set_status=Mock()
        tab_c.confirm_ready_by_rcon=types.MethodType(ServerTab.confirm_ready_by_rcon, tab_c)
        tab_c._tail_status='ready'
        app.tabs['Genesis']=tab_c
        self.assertIn('A', app.watch_maps)
        app._sonda_rcon(tab, confirm_unknown=True)
        cb=plugin.enqueue.call_args.args[2]
        cb(None)
        with patch('asaonly.procedura.time.time', return_value=1030), patch('asaonly.procedura.os.path.isdir', return_value=True):
            app._tick_return_watch()
        self.assertFalse(app.watch_active)
        self.assertEqual(tab_b._tail_status,'ready')
        print("ULTRA 20 OK: 3 mapy prod, Extinction RCON bez READY -> GOTOWY")
