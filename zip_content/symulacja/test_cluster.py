# -*- coding: utf-8 -*-
"""Deterministic integration simulation for the V3.75 procedure."""
import unittest
from unittest.mock import patch

from asaonly.procedura import ProcedureMixin


class Var:
    def __init__(self, value): self.value=value
    def get(self): return self.value


class Button:
    def configure(self, **kwargs): pass


class FakeTab:
    def __init__(self, name, mods, lines, port, status="ready", rcon_error=None):
        self.name=name; self.mods=list(mods); self.lines=list(lines)
        self.var_map_on=Var(True); self.var_port=Var(str(port)); self.var_log=Var(name)
        self._tail_status=status; self._boot_seq=0; self.rcon_error=rcon_error
        self.sent=[]; self.editable=True; self.installed={}; self._server_versions={}
    def get_effective_mod_ids(self): return list(self.mods)
    def raw_line_count(self): return len(self.lines)
    def validate_lines(self):
        from asaonly.server_tab import validate_rcon_line_values
        rows,err=validate_rcon_line_values(self.lines)
        return rows, ("bad "+err if err else None)
    def set_lines_editable(self, value): self.editable=value
    def enqueue_rcon(self, cmd, cb=None):
        self.sent.append(cmd)
        if cb: cb(self.rcon_error)
    def flush_rcon_queue(self): pass


class FakeApp(ProcedureMixin):
    def __init__(self, tabs, pending):
        self.tabs={t.name:t for t in tabs}; self.pending_updates=list(pending)
        self.restart_active=False; self.watch_active=False; self.watch_maps={}
        self.schedule=[]; self._proc_incidents=set(); self._proc_map_results={}
        self._auto_next_t=None; self.updated_mods=[]; self.restart_t0=None
        self.btn_cancel=Button(); self.auto_rcon=Var(True); self.var_watch=Var("20")
        self.known_versions={}; self.mod_states={}; self.monitor_off=set()
        self.logs=[]; self.saved=0; self._now=1000.0
    def tr(self,key,**kw): return key
    def log(self,msg): self.logs.append(str(msg))
    def log_warn(self,msg): self.logs.append("WARN "+str(msg))
    def _dziennik_modow(self): pass
    def _refresh_pending_ui(self): pass
    def save_config(self,silent=False): self.saved+=1
    def request_save(self): pass
    def post_ui(self,cb): cb()
    def _set_mod_state(self,*a): pass
    def _mods_dir_for_tab(self,tab): return tab.name
    def _installed_file_ids(self,path): return list(self.tabs[path].installed.items())


def pending(mid="111", fid="200", targets=("A",)):
    return {"mid":mid,"name":"Test Mod","fid":fid,
            "targets":list(targets),"verified":[],"qualified":True}


class ClusterSimulation(unittest.TestCase):
    def run_due(self, app, seconds=999):
        with patch("asaonly.procedura.time.time", return_value=1000.0+seconds):
            app._tick_restart_timeline()

    def start(self, app):
        with patch("asaonly.procedura.time.time", return_value=1000.0), \
             patch("asaonly.procedura.messagebox.showerror"), \
             patch("asaonly.procedura.messagebox.showwarning"), \
             patch("asaonly.procedura.messagebox.askyesno", return_value=True):
            app._exec_pending()

    def test_shared_mod_runs_maps_sequentially_with_local_timelines(self):
        a=FakeTab("A",["111"],[("5","DoExit")],27020)
        b=FakeTab("B",["111"],[("5","DoExit")],27021)
        app=FakeApp([a,b],[pending(targets=("A","B"))])
        self.start(app)
        self.run_due(app,5)
        self.assertEqual(a.sent,["DoExit"]); self.assertEqual(b.sent,[])
        self.assertEqual(set(app.watch_maps),{"A"})
        # Nawet bardzo późny zegar nie uruchamia B, dopóki A nie wróci READY.
        self.run_due(app,999); self.assertEqual(b.sent,[])
        a._tail_status="starting"
        with patch("asaonly.procedura.time.time",return_value=2001): app._tick_return_watch()
        a._ready_proof="new-log-ready"; a._ready_observed_at=2002; a._tail_status="ready"; a._boot_seq=1; a.installed={"111":"203"}; a._server_versions={"111":"203"}
        with patch("asaonly.procedura.time.time",return_value=2002), patch("asaonly.procedura.os.path.isdir",return_value=True):
            app._tick_return_watch()
            # V3.81: kolejka rusza następną mapę w najbliższym tiku (co 0,5 s).
            app._tick_restart_timeline()
        # Druga mapa dostaje własny T+0; jej ręczne 5 s nie może wykonać się
        # natychmiast przy przejściu kolejki.
        self.assertEqual(b.sent,[])
        with patch("asaonly.procedura.time.time",return_value=2007): app._tick_restart_timeline()
        self.assertEqual(b.sent,["DoExit"])
        self.assertEqual(set(app.watch_maps),{"B"})
        self.assertEqual(app._kolejka.mapa("B").t_wyjscia,5)

    def test_manual_205_second_doexit_is_not_rebased_to_zero(self):
        tab=FakeTab("A",["111"],[("205","DoExit")],27020)
        app=FakeApp([tab],[pending()]); self.start(app)
        self.assertEqual(app._kolejka.mapa("A").t_wyjscia,205)
        self.run_due(app,204)
        self.assertEqual(tab.sent,[])
        self.run_due(app,205)
        self.assertEqual(tab.sent,["DoExit"])

    def test_rcon_failure_on_one_map_does_not_stop_queue(self):
        # V3.81 (aksjomat akceleratora): błąd RCON jednej mapy = ta mapa nieudana,
        # kolejka kończy się normalnie, zaległość tej mapy zostaje.
        a=FakeTab("A",["111"],[("5","DoExit")],27020,rcon_error="auth")
        b=FakeTab("B",["111"],[("6","DoExit")],27021)
        app=FakeApp([a,b],[pending(targets=("A","B"))])
        self.start(app); self.run_due(app,10)
        self.assertEqual(app._proc_map_results["A"]["result"],"deferred_rcon_error")
        with patch("asaonly.procedura.time.time",return_value=1011): app._tick_restart_timeline()
        with patch("asaonly.procedura.time.time",return_value=1017): app._tick_restart_timeline()
        self.assertEqual(b.sent,["DoExit"])
        b._tail_status="starting"
        with patch("asaonly.procedura.time.time",return_value=1018): app._tick_return_watch()
        b._ready_proof="new-log-ready"; b._ready_observed_at=1019; b._tail_status="ready"; b._boot_seq=1; b.installed={"111":"203"}; b._server_versions={"111":"203"}
        with patch("asaonly.procedura.time.time",return_value=1019), patch("asaonly.procedura.os.path.isdir",return_value=True):
            app._tick_restart_timeline()
        self.assertFalse(app.watch_active); self.assertFalse(app.restart_active)
        self.assertEqual(len(app.pending_updates),1)
        self.assertEqual(app.pending_updates[0]["verified"],["B"])

    def test_unknown_map_doexit_is_blocked_fail_closed(self):
        tab=FakeTab("A",["111"],[("0","DoExit")],27020,status="unknown")
        app=FakeApp([tab],[pending()]); self.start(app); self.run_due(app,1)
        self.assertEqual(tab.sent,[])
        self.assertEqual(app._proc_map_results["A"]["result"],"deferred_not_ready")

    def test_starting_map_doexit_is_blocked_without_retry_loop(self):
        a=FakeTab("A",["111"],[("5","DoExit")],27020,status="starting")
        app=FakeApp([a],[pending()]); self.start(app); self.run_due(app,10)
        self.assertEqual(a.sent,[]); self.assertFalse(app.watch_active)
        self.assertEqual(app._proc_map_results["A"]["result"],"deferred_not_ready")
        self.assertEqual(len(app.pending_updates),1)

    def test_empty_row_is_noop_and_invalid_other_map_does_not_block(self):
        a=FakeTab("A",["111"],[("", ""),("5","DoExit")],27020)
        b=FakeTab("B",["111"],[("x","DoExit")],27021)
        app=FakeApp([a,b],[pending(targets=("A","B"))])
        self.start(app); self.run_due(app,10)
        self.assertEqual(a.sent,["DoExit"]); self.assertEqual(b.sent,[])
        self.assertEqual(app._proc_map_results["B"]["result"],"deferred_invalid")

    def test_duplicate_ports_skip_only_conflicting_maps(self):
        # V3.81: konflikt portu wyłącza tylko mapy z konfliktem, reszta idzie.
        a=FakeTab("A",["111"],[("5","DoExit")],27020)
        b=FakeTab("B",["111"],[("6","DoExit")],27020)
        c=FakeTab("C",["111"],[("1","DoExit")],27021)
        app=FakeApp([a,b,c],[pending(targets=("A","B","C"))])
        self.start(app)
        self.assertTrue(app.restart_active)
        self.assertEqual([m.nazwa for m in app._kolejka.mapy],["C"])
        self.assertEqual(app._proc_map_results["A"]["result"],"deferred_port_conflict")
        self.run_due(app,1)
        self.assertEqual(a.sent+b.sent,[]); self.assertEqual(c.sent,["DoExit"])

    def test_ready_without_departure_is_not_return(self):
        a=FakeTab("A",["111"],[("0","DoExit")],27020)
        app=FakeApp([a],[pending()]); self.start(app); self.run_due(app,1)
        with patch("asaonly.procedura.time.time",return_value=1002): app._tick_return_watch()
        self.assertFalse(app.watch_maps["A"]["done"])
        a._tail_status="starting"
        with patch("asaonly.procedura.time.time",return_value=1003): app._tick_return_watch()
        a._ready_proof="new-log-ready"; a._ready_observed_at=2002; a._tail_status="ready"; a._boot_seq=1; a.installed={"111":"203"}; a._server_versions={"111":"203"}
        with patch("asaonly.procedura.time.time",return_value=1004), \
             patch("asaonly.procedura.os.path.isdir",return_value=True):
            app._tick_return_watch()
        self.assertFalse(app.watch_active); self.assertEqual(app.pending_updates,[])
        self.assertEqual(app.known_versions["111"],"200")

    def test_update_for_one_map_does_not_touch_other_map(self):
        a=FakeTab("A",["111"],[("1","DoExit")],27020)
        b=FakeTab("B",["222"],[("1","DoExit")],27021)
        app=FakeApp([a,b],[pending(targets=("A",))]); self.start(app); self.run_due(app,2)
        self.assertEqual(a.sent,["DoExit"]); self.assertEqual(b.sent,[])

    def test_no_doexit_never_opens_watch_or_clears_pending(self):
        # V3.81: bez DoExit mapa jest pomijana w całości — nie ogłaszamy graczom
        # restartu, który się nie odbędzie.
        a=FakeTab("A",["111"],[("1","ServerChat restart soon")],27020)
        app=FakeApp([a],[pending()]); self.start(app); self.run_due(app,2)
        self.assertEqual(a.sent,[])
        self.assertFalse(app.watch_active); self.assertFalse(app.restart_active)
        self.assertEqual(len(app.pending_updates),1)
        self.assertEqual(app._proc_map_results["A"]["result"],"deferred_no_doexit")
        self.assertTrue(any("DoExit" in x for x in app.logs))


if __name__=="__main__": unittest.main(verbosity=2)
