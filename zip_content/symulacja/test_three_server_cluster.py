# -*- coding: utf-8 -*-
import json
import pathlib
import unittest
from unittest.mock import patch

from symulacja.test_cluster import FakeApp, FakeTab

ROOT=pathlib.Path(__file__).resolve().parents[1]
FIX=ROOT/"symulacja"/"fixtures"


def load_cluster():
    return json.loads((FIX/"cluster_3_servers.json").read_text(encoding="utf-8"))


def make_tabs(cluster):
    return [FakeTab(s["name"],s["mods"],[(str(t),cmd) for t,cmd in s["lines"]],
                    s["rcon_port"])
            for s in cluster["servers"]]


def targets(cluster,mid):
    return [s["name"] for s in cluster["servers"] if mid in s["mods"]]


def update(mid,fid,cluster):
    return {"mid":mid,"name":"Mod "+mid,"fid":fid,
            "targets":targets(cluster,mid),"verified":[],"qualified":True}


class ThreeServerSchedule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cluster=load_cluster()

    def start(self,app):
        with patch("asaonly.procedura.time.time",return_value=1000), \
             patch("asaonly.procedura.messagebox.showerror"), \
             patch("asaonly.procedura.messagebox.showwarning"), \
             patch("asaonly.procedura.messagebox.askyesno",return_value=True):
            app._exec_pending()

    def tick(self,app,offset):
        with patch("asaonly.procedura.time.time",return_value=1000+offset):
            app._tick_restart_timeline()

    def test_fixture_uses_only_explicitly_synthetic_mod_ids(self):
        used=set().union(*(set(s["mods"]) for s in self.cluster["servers"]))
        self.assertEqual(used,{"SYN-%02d" % i for i in range(1,10)})

    def test_every_server_has_a_different_mod_set(self):
        sets=[frozenset(s["mods"]) for s in self.cluster["servers"]]
        self.assertEqual(len(set(sets)),3)
        self.assertEqual([len(x) for x in sets],[3,4,4])

    def test_every_tab_has_unshifted_local_timeline(self):
        for server in self.cluster["servers"]:
            lines=server["lines"]; warnings=lines[:-1]; doexit=lines[-1]
            self.assertEqual(len(warnings),5)
            self.assertEqual([x[0] for x in warnings],[0,60,120,180,240])
            self.assertTrue(all(x[1].lower().startswith("serverchat") for x in warnings))
            self.assertEqual(doexit,[300,"DoExit"])
            self.assertEqual(doexit[0]-warnings[0][0],300)

    def test_no_cluster_offsets_are_stored_in_tabs(self):
        exits=[s["lines"][-1][0] for s in self.cluster["servers"]]
        self.assertEqual(exits,[300,300,300])

    def test_only_first_map_timeline_is_active(self):
        pend=[update("SYN-02","1001",self.cluster),
              update("SYN-04","1002",self.cluster),
              update("SYN-07","1003",self.cluster)]
        tabs=make_tabs(self.cluster); app=FakeApp(tabs,pend); self.start(app)
        first_times=[t for t,_ in self.cluster["servers"][0]["lines"]]
        pierwsza=app._kolejka.mapa("Mapa A")
        self.assertEqual([x["t"] for x in pierwsza.harmonogram]+[pierwsza.t_wyjscia],first_times)
        self.assertEqual([m.nazwa for m in app._kolejka.mapy],["Mapa A","Mapa B","Mapa C"])
        self.assertEqual([m.stan for m in app._kolejka.mapy],["oglasza","czeka","czeka"])
        for moment in first_times:self.tick(app,moment)
        self.assertEqual(len(tabs[0].sent),6)
        self.assertEqual(tabs[1].sent,[]); self.assertEqual(tabs[2].sent,[])
        self.assertEqual(set(app.watch_maps),{"Mapa A"})

    def _assert_routes(self,mid,expected):
        tabs=make_tabs(self.cluster)
        app=FakeApp(tabs,[update(mid,"1000",self.cluster)])
        self.start(app)
        planned=[m.nazwa for m in app._kolejka.mapy]
        self.assertEqual(planned,expected)
        # Zanim pierwsza mapa wróci READY, żadna dalsza mapa nie wysyła RCON.
        for moment in (0,60,120,180,240,300,700):self.tick(app,moment)
        self.assertEqual(len(next(t for t in tabs if t.name==expected[0]).sent),6)
        for tab in tabs:
            if tab.name != expected[0]:self.assertEqual(tab.sent,[])

    def test_unique_mod_routes_only_to_map_a(self):
        self._assert_routes("SYN-02",["Mapa A"])

    def test_shared_mod_routes_to_maps_a_and_b(self):
        self._assert_routes("SYN-01",["Mapa A","Mapa B"])

    def test_other_shared_mod_routes_to_maps_a_and_c(self):
        self._assert_routes("SYN-03",["Mapa A","Mapa C"])


if __name__=="__main__": unittest.main(verbosity=2)
