"""Regressions from the two historical audits and the local Windows audit.

All server files, process identities and credentials are synthetic.
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import types
import unittest
import queue
from unittest.mock import Mock, patch

from asaonly import zamrazanie as Z, synchronizacja as SYNC, siec
from asaonly.cf_wersje import CurseForgeMixin
import tests.test_aktualizacja_serwera as U

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Processes:
    def __init__(self):
        self.live = {10: 1, os.getpid(): 2}
        self.count = {10: 0}
        self.events = []
        self.fail_resume = False
        self.fail_guardian = False

    def procesy(self, name): return [10]
    def czas_startu(self, pid): return self.live[pid]
    def zyje(self, pid, start=None): return pid in self.live and (start is None or self.live[pid] == start)
    def dostep_wstrzymania(self, pid): pass
    def sciezka_exe(self, pid): return os.path.abspath('manager.exe')

    def zamroz(self, pid):
        self.events.append('freeze')
        self.count[pid] += 1

    def odmroz(self, pid):
        self.events.append('resume')
        if self.fail_resume:
            raise PermissionError('simulated resume refusal')
        self.count[pid] = max(0, self.count[pid] - 1)

    def uruchom_straznika(self, path):
        self.events.append('guardian')
        if self.fail_guardian:
            raise OSError('simulated guardian failure')


class Recovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='asa-recovery-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.path = str(self.root / 'lease.json')
        self.api = Processes()
        self.freezer = Z.Zamrazarka(self.path, 'manager.exe', api=self.api)

    def interrupted(self, corrupt=False):
        dest = self.root / 'map'
        backup = dest / SYNC.KATALOG_KOPII
        backup.mkdir(parents=True)
        (dest / 'server.bin').write_bytes(b'NEW')
        (backup / 'server.bin').write_bytes(b'OLD')
        journal = backup / SYNC.PLIK_DZIENNIKA
        state = {'stan': 'w_toku', 'cel': str(dest), 'plan': ['server.bin'],
                 'operacje': [{'rel': 'server.bin', 'istnial': True}]}
        journal.write_text('{' if corrupt else json.dumps(state), encoding='utf-8')
        Z.zapisz_dzierzawe(self.path, {'refresher': {'pid': 999, 'start': 1},
            'manager': [{'pid': 10, 'start': 1}], 'kopia': str(journal), 'faza': 'kopiowanie'})
        self.api.count[10] = 1
        return dest, journal, backup

    def test_guardian_must_start_before_freeze(self):
        self.assertEqual(self.freezer.zamroz(), (True, ''))
        self.assertEqual(self.api.events, ['guardian', 'freeze'])
        self.assertEqual(self.freezer.odmroz(), [])
        self.assertEqual(self.api.count[10], 0)

    def test_guardian_failure_does_not_freeze(self):
        self.api.fail_guardian = True
        self.assertFalse(self.freezer.zamroz()[0])
        self.assertNotIn('freeze', self.api.events)
        self.assertFalse(os.path.exists(self.path))

    def test_existing_lease_cannot_be_replaced(self):
        self.assertTrue(self.freezer.zamroz()[0])
        before = pathlib.Path(self.path).read_bytes()
        other = Z.Zamrazarka(self.path, 'manager.exe', api=self.api)
        self.assertEqual(other.zamroz(), (False, 'recovery'))
        self.assertEqual(pathlib.Path(self.path).read_bytes(), before)
        self.assertEqual(self.api.count[10], 1)

    def test_corrupt_lease_remains_and_blocks(self):
        pathlib.Path(self.path).write_text('{', encoding='utf-8')
        self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(pathlib.Path(self.path).read_text(encoding='utf-8'), '{')
        self.assertFalse(self.freezer.zamroz()[0])
        self.assertEqual(self.api.events, [])

    def test_failed_checkpoint_raises_before_copying(self):
        self.assertTrue(self.freezer.zamroz()[0])
        with patch.object(Z, 'zapisz_dzierzawe', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.freezer.ustaw_kopie('unused-journal')
        self.assertNotIn('kopia', Z.czytaj_dzierzawe(self.path))

    def test_failed_resume_preserves_record_and_can_retry(self):
        self.assertTrue(self.freezer.zamroz()[0])
        self.api.fail_resume = True
        self.assertTrue(self.freezer.odmroz())
        self.assertTrue(os.path.exists(self.path))
        self.assertTrue(self.freezer.aktywna())
        self.api.fail_resume = False
        self.assertEqual(self.freezer.odmroz(), [])
        self.assertEqual(self.api.count[10], 0)

    def test_live_owner_is_not_recovered_after_deadline(self):
        self.assertTrue(self.freezer.zamroz()[0])
        data = Z.czytaj_dzierzawe(self.path)
        self.assertEqual(Z.decyzja_straznika(data, 10**15, self.api.zyje), 'czekaj')
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'OWNER_ALIVE')
        self.assertEqual(self.api.count[10], 1)

    def test_unknown_owner_is_not_treated_as_dead(self):
        data = {'refresher': {'pid': 99, 'start': 1}}
        self.assertEqual(Z.decyzja_straznika(data, 0, Mock(side_effect=PermissionError('denied'))), 'niepewny')

    def test_corrupt_journal_blocks_guardian(self):
        dest, journal, _ = self.interrupted(corrupt=True)
        self.assertEqual(Z.straznik(self.path, api=self.api, spij=lambda _: None), 'zablokowane')
        self.assertEqual(self.api.count[10], 1)
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(journal.read_text(encoding='utf-8'), '{')

    def test_missing_expected_journal_is_not_safe(self):
        _, journal, _ = self.interrupted()
        journal.unlink()
        self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(self.api.count[10], 1)

    def test_rollback_failure_never_resumes(self):
        dest, journal, backup = self.interrupted()
        real = os.replace
        def fail(src, dst):
            if pathlib.Path(src) == backup / 'server.bin':
                raise OSError('simulated storage error')
            return real(src, dst)
        with patch.object(SYNC.os, 'replace', side_effect=fail):
            self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(self.api.count[10], 1)
        self.assertEqual((dest / 'server.bin').read_bytes(), b'NEW')
        self.assertEqual(json.loads(journal.read_text(encoding='utf-8'))['stan'], 'wycofanie_niepelne')

    def test_successful_recovery_restores_then_resumes(self):
        dest, _, _ = self.interrupted()
        orig = self.api.odmroz
        def resume(pid):
            self.assertEqual((dest / 'server.bin').read_bytes(), b'OLD')
            return orig(pid)
        self.api.odmroz = resume
        result = self.freezer.odzyskaj_po_awarii()
        self.assertEqual(result.stan, 'RECOVERED')
        self.assertEqual(self.api.count[10], 0)
        self.assertFalse(os.path.exists(self.path))

    def test_multiple_managers_are_not_frozen(self):
        self.api.procesy = lambda _: [10, 11]
        self.assertFalse(self.freezer.zamroz()[0])
        self.assertEqual(self.api.events, [])

    def test_ambiguous_native_operation_resumes_after_files_are_safe(self):
        Z.zapisz_dzierzawe(self.path, {'manager': [{'pid': 10, 'start': 1, 'stan': 'wznawianie'}],
                                    'faza': 'bezpieczne'})
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'RECOVERED')
        self.assertEqual(self.api.events, ['resume'])

    def test_guardian_crash_before_freeze_does_not_resume_untouched_manager(self):
        Z.zapisz_dzierzawe(self.path, {'manager': [{'pid': 10, 'start': 1, 'stan': 'przygotowany'}]})
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'RECOVERED')
        self.assertEqual(self.api.events, [])

    def test_lease_lock_prevents_two_recoverers(self):
        self.interrupted()
        with Z.blokada_dzierzawy(self.path):
            self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(self.api.events, [])
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'RECOVERED')

    def test_resume_success_followed_by_checkpoint_failure_can_recover(self):
        self.assertTrue(self.freezer.zamroz()[0])
        original = Z.zapisz_dzierzawe
        def fail_after_resume(path, data):
            if path == self.path and data['manager'][0].get('stan') == 'wznowiony':
                raise OSError('checkpoint failed after resume')
            return original(path, data)
        with patch.object(Z, 'zapisz_dzierzawe', side_effect=fail_after_resume):
            self.assertTrue(self.freezer.odmroz())
        self.api.live.pop(os.getpid())
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'RECOVERED')
        self.assertEqual(self.api.events.count('resume'), 2)
        self.assertEqual(self.api.count[10], 0)

    def test_old_journal_error_is_explicitly_unsafe(self):
        dest, journal, _ = self.interrupted(corrupt=True)
        result = SYNC.wykonaj({}, str(self.root / 'unused-cache'), str(dest))
        self.assertFalse(result.ok)
        self.assertFalse(result.safe_to_resume)
        self.assertTrue(journal.exists())

    def test_missing_original_and_backup_blocks_recovery(self):
        dest, _, backup = self.interrupted()
        (dest / 'server.bin').unlink()
        (backup / 'server.bin').unlink()
        self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(self.api.count[10], 1)

    def test_full_path_selects_only_the_configured_manager(self):
        self.api.procesy = lambda _: [10, 11]
        self.api.sciezka_exe = lambda pid: str(self.root / ('a' if pid == 10 else 'b') / 'manager.exe')
        freezer = Z.Zamrazarka(self.path, str(self.root / 'a' / 'manager.exe'), api=self.api)
        self.assertTrue(freezer.zamroz()[0])
        self.assertEqual(self.api.count, {10: 1})

    def test_partial_resume_of_legacy_multi_manager_lease_keeps_failed_pid(self):
        self.api.live[11] = 3
        self.api.count = {10: 1, 11: 1}
        Z.zapisz_dzierzawe(self.path, {'manager': [{'pid': 10, 'start': 1}, {'pid': 11, 'start': 3}]})
        real_resume = self.api.odmroz
        def fail_second(pid):
            if pid == 11:
                raise OSError('second manager inaccessible')
            return real_resume(pid)
        self.api.odmroz = fail_second
        self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertEqual(self.api.count, {10: 0, 11: 1})
        data = Z.czytaj_dzierzawe(self.path)
        self.assertEqual(data['manager'][0]['stan'], 'wznowiony')
        self.api.odmroz = real_resume
        self.assertEqual(self.freezer.odzyskaj_po_awarii().stan, 'RECOVERED')
        self.assertEqual(self.api.count, {10: 0, 11: 0})

    def test_lease_is_flushed_to_disk(self):
        with patch.object(Z.os, 'fsync', wraps=os.fsync) as flush:
            Z.zapisz_dzierzawe(self.path, {'manager': []})
        self.assertEqual(flush.call_count, 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows process handshake')
    def test_real_windows_guardian_handshake_with_empty_manager_list(self):
        # Jedyny rzeczywisty proces w tych testach to strażnik testowego pliku.
        # Lista managerów jest pusta: nie ma procesu do suspend/resume.
        api = Z.ApiWindows()
        data = {'schema': 2, 'lease_id': 'synthetic-native-handshake', 'manager': [],
                'refresher': {'pid': os.getpid(), 'start': api.czas_startu(os.getpid())},
                'faza': 'przygotowany'}
        Z.zapisz_dzierzawe(self.path, data)
        proc = api.uruchom_straznika(self.path)
        try:
            with open(self.path + '.ready', encoding='utf-8') as fh:
                self.assertEqual(json.load(fh)['lease_id'], data['lease_id'])
        finally:
            os.remove(self.path)
            proc.wait(timeout=10)


class UpdaterFailures(U.Baza):
    def setUp(self):
        super().setUp()
        self.sprawdzenie()
        self.assertEqual(self.p.przed_doexit('Ragnarok'), ('ok', ''))
        self.z = dict(self.p._zadanie)

    def test_checkpoint_failure_never_calls_sync(self):
        with patch.object(self.p.zamrazarka, 'ustaw_kopie', side_effect=OSError('checkpoint refused')), \
             patch.object(SYNC, 'wykonaj') as sync:
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda _: None)
        sync.assert_not_called()
        self.assertEqual(self.api.licznik[10], 0)

    def test_explicit_unsafe_result_blocks_resume_and_queue(self):
        result = SYNC.WynikSynchronizacji(False, 'rollback incomplete', {}, False)
        with patch.object(SYNC, 'wykonaj', return_value=result):
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda _: None)
        self.assertEqual(self.api.licznik[10], 1)
        self.assertTrue(os.path.exists(self.p.zamrazarka.sciezka))
        self.assertTrue(self.p.blokada_kolejki())
        self.assertFalse(self.p._warunki_managera()[0])
        self.assertFalse(self.p.zamrazarka.zamroz()[0])

    def test_unexpected_sync_exception_keeps_lease(self):
        with patch.object(SYNC, 'wykonaj', side_effect=RuntimeError('unexpected')):
            self.p._aktualizuj_praca(self.z, dict(self.p.cfg), spij=lambda _: None)
        self.assertEqual(self.api.licznik[10], 1)
        self.assertTrue(self.p.blokada_kolejki())

    def test_pid_reuse_does_not_mean_server_is_running(self):
        self.api.zyje = lambda pid, start=None: pid == 10 or (pid == 77 and start != 5)
        state = {'pid': 77, 'pid_start': 5, 'katalog': self.katalogi['Ragnarok']}
        self.assertEqual(self.p._serwer_dziala(state), (False, True))

    def test_live_worker_timeout_warns_without_resuming(self):
        self.p._zadanie['faza'] = 'instalacja'
        now = self.z['t0'] + U.modul.LIMIT_S + 1
        self.p.tik(now)
        self.p.tik(now + 1)
        self.assertEqual(self.api.licznik[10], 1)
        self.assertEqual(len(self.logi('przekroczono czas podmiany')), 1)


class Protocol(unittest.TestCase):
    def client(self, frames):
        client = siec.RCONClient('unused', 1, 'synthetic')
        client.sock = Mock()
        client._send = Mock(side_effect=[1, 2])
        client._recv = Mock(side_effect=frames)
        return client

    def test_auth_waits_for_auth_response_and_rejects_wrong_password(self):
        client = self.client([(1, 0, ''), (-1, 2, '')])
        self.assertFalse(client._auth('synthetic'))

    def test_auth_accepts_optional_empty_packet(self):
        self.assertTrue(self.client([(1, 0, ''), (1, 2, '')])._auth('synthetic'))

    def test_auth_preserves_legacy_rid_tolerance(self):
        self.assertTrue(self.client([(999, 2, '')])._auth('synthetic'))

    def test_valid_empty_reply_is_success(self):
        self.assertEqual(self.client([(1, 0, '')]).command('SaveWorld'), '')

    def test_disconnect_after_send_is_uncertain_not_success(self):
        client = self.client([siec.RCONError('closed')])
        with self.assertRaises(siec.RCONUncertainError) as caught:
            client.command('DoExit')
        self.assertFalse(caught.exception.retry_safe)

    def test_command_preserves_legacy_rid_and_type_tolerance(self):
        self.assertEqual(self.client([(999, 2, 'OK')]).command('DoExit'), 'OK')

    def test_full_size_response_does_not_send_untested_marker(self):
        client = self.client([(1, 0, 'A' * 4086), (1, 0, 'tail'), (2, 0, '')])
        self.assertEqual(client.command('ListPlayers'), 'A' * 4086)
        self.assertEqual(client._send.call_count, 1)

    def test_uncertain_command_is_not_retried_by_plugin(self):
        spec = importlib.util.spec_from_file_location('rcon_recovery_test', ROOT / 'PLUGINY' / '86_rcon_admin.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin = module.Wtyczka()
        work = queue.Queue()
        completed = []
        work.put(('automatic', 0, 'DoExit', 'unused', '1', 'synthetic',
                  lambda error, response: completed.append((error, response))))
        work.put(None)
        with patch.object(module, 'rcon_send', side_effect=siec.RCONUncertainError('unconfirmed')) as send:
            plugin._worker('TEST', work)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(str(completed[0][0]), 'unconfirmed')
        self.assertFalse(completed[0][0].retry_safe)
        self.assertIsNone(completed[0][1])


class OtherRegressions(unittest.TestCase):
    def test_backup_without_secrets_excludes_quarantine(self):
        spec = importlib.util.spec_from_file_location('backup_recovery_test', ROOT / 'PLUGINY' / '80_konfiguracje.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='asa-backup-test-') as folder:
            base = pathlib.Path(folder)
            secret = base / 'CONFIG_MAPS_TABS' / 'TEST' / 'CONFIG_SECRET_RCON' / 'LEGACY_KWARANTANNA' / 'old.json'
            secret.parent.mkdir(parents=True)
            secret.write_text('{"password":"synthetic"}', encoding='utf-8')
            archive = base / 'backup.zip'
            plugin = module.Wtyczka()
            plugin._base_dir = lambda: folder
            plugin.core = types.SimpleNamespace(log=lambda *args: None)
            with patch.object(module.filedialog, 'asksaveasfilename', return_value=str(archive)), \
                 patch.object(module.messagebox, 'showinfo'), patch.object(module.messagebox, 'showerror') as error:
                plugin._backup(None, secrets=False)
            self.assertFalse(error.called)
            with module.zipfile.ZipFile(archive) as saved:
                self.assertFalse(any('CONFIG_SECRET_RCON' in name for name in saved.namelist()))

    def test_client_only_artifact_can_signal_a_new_version(self):
        class App(CurseForgeMixin):
            _destroying = False
            def __init__(self): self.updates = []; self.errors = []
            def post_ui(self, cb): cb()
            def tr(self, *args, **kwargs): return ''
            def log(self, *args): pass
            def _set_mod_state(self, *args): pass
            def _apply_cf_metadata(self, *args): pass
            def request_save(self): pass
            def _handle_cf_error(self, mid, reason): self.errors.append((mid, reason))
            def _cf_done(self, updates): self.updates = updates
            def _cf_cleanup(self): raise AssertionError('unexpected worker exception')
        app = App()
        data = {'data': [{'id': 111, 'name': 'Synthetic', 'latestFiles': [{'id': 201, 'fileName': 'client.zip'}]}]}
        with patch.object(siec, 'cf_request', return_value=data):
            app._cf_worker('synthetic', ['111'], 0, {'TEST': {'111': {'fid': '200'}}})
        self.assertEqual(app.updates, [('111', 'Synthetic', '201', ['TEST'])])
        self.assertEqual(app.errors, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
