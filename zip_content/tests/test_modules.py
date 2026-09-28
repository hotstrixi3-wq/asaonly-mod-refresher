import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from asaonly import zapis
from asaonly.siec import select_server_artifact


class ModuleTests(unittest.TestCase):
    def test_atomic_json_failure_keeps_previous_authoritative_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=pathlib.Path(td)/'state.json'
            path.write_text('{"old":true}',encoding='utf-8')
            real_replace=zapis.os.replace
            def fail_only_commit(src,dst):
                if str(src).endswith('.tmp') and str(dst)==str(path):
                    raise OSError('injected commit failure')
                return real_replace(src,dst)
            with patch('asaonly.zapis.os.replace',side_effect=fail_only_commit):
                self.assertFalse(zapis.write_json_atomic(str(path),{'new':True}))
            self.assertEqual(json.loads(path.read_text()),{'old':True})
            self.assertFalse(pathlib.Path(str(path)+'.tmp').exists())

    def test_versioned_save_skips_identical_and_rotates(self):
        with tempfile.TemporaryDirectory() as td:
            first=zapis.save_versioned(td,'cfg',{'a':1},keep=2)
            second=zapis.save_versioned(td,'cfg',{'a':1},keep=2)
            self.assertEqual(first,second)
            self.assertEqual(json.loads(pathlib.Path(first).read_text()),{'a':1})

    def test_two_different_saves_in_same_second_keep_both_revisions(self):
        with tempfile.TemporaryDirectory() as td, patch('asaonly.zapis.file_stamp',return_value='20.09.2026 12-00-00'):
            first=zapis.save_versioned(td,'cfg',{'a':1},keep=10)
            second=zapis.save_versioned(td,'cfg',{'a':2},keep=10)
            self.assertNotEqual(first,second)
            self.assertTrue(pathlib.Path(first).exists())
            self.assertTrue(pathlib.Path(second).exists())
            self.assertEqual(zapis.newest_matching(td,'cfg'),second)
            self.assertEqual(json.loads(pathlib.Path(zapis.newest_matching(td,'cfg')).read_text()),{'a':2})

    def test_same_second_off_revision_is_authoritative_after_reopen(self):
        with tempfile.TemporaryDirectory() as td, patch('asaonly.zapis.file_stamp',return_value='21.09.2026 07-42-40'):
            zapis.save_versioned(td,'program',{'plugins':{'backup_restore':{'enabled':True}}})
            off=zapis.save_versioned(td,'program',{'plugins':{'backup_restore':{'enabled':False}}})
            loaded=json.loads(pathlib.Path(zapis.newest_matching(td,'program')).read_text())
            self.assertEqual(zapis.newest_matching(td,'program'),off)
            self.assertIs(loaded['plugins']['backup_restore']['enabled'],False)

    def test_legacy_conflict_is_quarantined_not_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); old=root/'legacy.json'
            old.write_text('{"legacy":true}',encoding='utf-8')
            zapis.save_versioned(td,'cfg',{'new':True})
            moved=zapis.migrate_old_file(str(old),td,'cfg')
            self.assertFalse(old.exists())
            self.assertTrue(pathlib.Path(moved).exists())
            self.assertIn('LEGACY_KWARANTANNA',moved)

    def test_atomic_write_replaces_json(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'x.json'
            self.assertTrue(zapis.write_json_atomic(str(p),{'x':2}))
            self.assertEqual(json.loads(p.read_text()),{'x':2})

    def test_plain_log_activity_never_promotes_unknown_to_starting(self):
        from asaonly.logtail import status_after_unclassified_activity
        self.assertEqual(status_after_unclassified_activity('unknown'),'unknown')
        self.assertEqual(status_after_unclassified_activity('ready'),'ready')

    def test_server_tab_diagnostic_path_helper_is_imported(self):
        import asaonly.server_tab as server_tab
        self.assertTrue(callable(server_tab.mods_dir_candidates))

    def test_server_artifact_fallback_is_marked_uncertain(self):
        item, certain=select_server_artifact([{'id':1,'fileName':'mystery'}])
        self.assertEqual(item['id'],1)
        self.assertFalse(certain)

if __name__=='__main__': unittest.main()
