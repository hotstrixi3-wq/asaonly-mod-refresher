import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
CPU=load('cpu_admin_sim',ROOT/'PLUGINY'/'60_cpu.py')
IMP=load('import_admin_sim',ROOT/'PLUGINY'/'80_konfiguracje.py')  # V3.83: importer w „Konfiguracje”

class PluginUserAdminSimulation(unittest.TestCase):
    def test_user_selects_old_root_not_a_specific_file(self):
        with tempfile.TemporaryDirectory() as td:
            deep=Path(td)/'old-refresher'/'taby'/'MapA'; deep.mkdir(parents=True)
            (deep/'config.json').write_text(json.dumps({'name':'MapA','lines':[]}),encoding='utf-8')
            r=IMP.Wtyczka.scan_directory(td)
            self.assertEqual([x['name'] for x in r['candidates']],['MapA'])

    def test_admin_sees_malformed_json_count_but_valid_maps_survive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); (p/'bad.json').write_text('{',encoding='utf-8')
            (p/'good.json').write_text(json.dumps({'name':'Good','lines':[]}),encoding='utf-8')
            r=IMP.Wtyczka.scan_directory(td)
            self.assertEqual(len(r['errors']),1); self.assertEqual(len(r['candidates']),1)

    def test_unrelated_json_is_not_offered_as_map(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); (p/'status.json').write_text(json.dumps({'maps':{},'mods':{}}),encoding='utf-8')
            self.assertEqual(IMP.Wtyczka.scan_directory(td)['candidates'],[])

    def test_secret_is_detected_without_being_exposed_in_summary_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); tab=root/'CONFIG_MAPS_TABS'/'MapA'; sec=tab/'CONFIG_SECRET_RCON'; sec.mkdir(parents=True)
            (tab/'map.json').write_text(json.dumps({'name':'MapA','lines':[]}),encoding='utf-8')
            (sec/'secret.json').write_text(json.dumps({'password':'TOPSECRET'}),encoding='utf-8')
            item=IMP.Wtyczka.scan_directory(td)['candidates'][0]
            self.assertTrue(item['secret_found']); self.assertNotIn('TOPSECRET',item['path'])

    def test_newest_valid_backup_is_recommended(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for stamp,port in ((100,'1'),(300,'3'),(200,'2')):
                p=root/('map-%s.json'%stamp); p.write_text(json.dumps({'name':'A','lines':[],'rcon_port':port}),encoding='utf-8'); os.utime(p,(stamp,stamp))
            item=IMP.Wtyczka.scan_directory(td)['candidates'][0]
            self.assertEqual(item['config']['rcon_port'],'3'); self.assertEqual(item['versions'],3)

    def test_affinity_recommendation_never_uses_cpu_twice(self):
        p=CPU.Wtyczka(); p.benchmark_maps=['A','B','C']; p.benchmark_results={i:1000-i for i in range(24)}; p._make_recommendations()
        values=[cpu for group in p.benchmark_recommendations.values() for cpu in group]
        self.assertEqual(len(values),len(set(values))); self.assertEqual(len(values),24)

    def test_three_servers_receive_more_than_one_cpu(self):
        p=CPU.Wtyczka(); p.benchmark_maps=['A','B','C']; p.benchmark_results={i:1000-i for i in range(24)}; p._make_recommendations()
        self.assertEqual([len(p.benchmark_recommendations[x]) for x in ['A','B','C']],[8,8,8])

    def test_no_servers_means_no_dangerous_recommendation(self):
        p=CPU.Wtyczka(); p.benchmark_maps=[]; p.benchmark_results={0:1}; p._make_recommendations()
        self.assertEqual(p.benchmark_recommendations,{})

    def test_benchmark_math_returns_positive_score_without_touching_server(self):
        score=CPU.Wtyczka._bench_one(0,0.01)
        self.assertGreater(score,0)

if __name__=='__main__': unittest.main()
