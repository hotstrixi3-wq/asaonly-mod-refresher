"""Abrupt termination of an isolated copy worker; no real manager is touched."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from asaonly import synchronizacja as SYNC, zamrazanie as Z

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AbruptWorkerExit(unittest.TestCase):
    def exercise(self, during_copy):
        with tempfile.TemporaryDirectory(prefix='asa-crash-test-') as folder:
            root = pathlib.Path(folder)
            source, target = root / 'cache', root / 'map'
            source.mkdir(); target.mkdir()
            for name in ('a.bin', 'b.bin'):
                (source / name).write_bytes(b'NEW-LONGER')
                (target / name).write_bytes(b'OLD')
            lease = str(root / 'lease.json')
            journal = SYNC.sciezka_dziennika(str(target))
            code = (
                'import os,sys; from asaonly import synchronizacja as S; '
                'src,dst,mode=sys.argv[1:]; '
                'callback=(lambda *a: os._exit(17)) if mode == "during" else None; '
                'S.wykonaj(S.plan(src,dst),src,dst,na_postep=callback,zachowaj_dziennik=True); '
                'os._exit(18)'
            )
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            result = subprocess.run([sys.executable, '-c', code, str(source), str(target),
                                     'during' if during_copy else 'after'], cwd=str(ROOT),
                                    timeout=20, capture_output=True, creationflags=flags)
            self.assertEqual(result.returncode, 17 if during_copy else 18, result.stderr)
            self.assertTrue(os.path.exists(journal))
            Z.zapisz_dzierzawe(lease, {'manager': [{'pid': 10, 'start': 1}],
                                     'kopia': journal, 'faza': 'kopiowanie'})
            expected = b'OLD' if during_copy else b'NEW-LONGER'
            test = self

            class FakeManager:
                resumes = 0
                def zyje(self, pid, start=None): return pid == 10
                def odmroz(self, pid):
                    for name in ('a.bin', 'b.bin'):
                        test.assertEqual((target / name).read_bytes(), expected)
                    self.resumes += 1

            manager = FakeManager()
            recovery = Z.Zamrazarka(lease, 'synthetic.exe', api=manager)
            self.assertEqual(recovery.odzyskaj_po_awarii().stan, 'RECOVERED')
            self.assertEqual(manager.resumes, 1)
            self.assertFalse(os.path.exists(lease))

    def test_process_dies_after_first_file_old_build_restored_before_resume(self):
        self.exercise(during_copy=True)

    def test_process_dies_after_commit_new_build_preserved_before_resume(self):
        self.exercise(during_copy=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
