"""Focused regressions from Claude's review. Synthetic maps/processes only."""
import json
import os
import pathlib
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

from asaonly import zamrazanie as Z, synchronizacja as SYNC, siec
from asaonly.procedura import ProcedureMixin
from asaonly.kolejka import Kolejka, Mapa, START
from tests import test_aktualizacja_serwera as U
from tests.test_recovery_local import Recovery


class RecoveryReview(Recovery):
    # Run only additional methods; base class setUp supplies a temporary lease.
    def test_failed_suspend_is_compensated_immediately(self):
        def partial(pid):
            self.api.count[pid] += 1
            raise OSError('partly suspended')
        self.api.zamroz = partial
        self.assertFalse(self.freezer.zamroz()[0])
        self.assertEqual(self.api.count[10], 0)
        self.assertFalse(self.freezer.aktywna())

    def test_ambiguous_freeze_cannot_bypass_corrupt_journal(self):
        self.interrupted(corrupt=True)
        data = Z.czytaj_dzierzawe(self.path)
        data['manager'][0]['stan'] = 'zamrozenie_niepewne'
        Z.zapisz_dzierzawe(self.path, data)
        self.assertTrue(self.freezer.odzyskaj_po_awarii().zablokowane)
        self.assertNotIn('resume', self.api.events)

    def test_guardian_retries_half_second_lock(self):
        self.interrupted()
        held = threading.Event()
        def hold():
            with Z.blokada_dzierzawy(self.path):
                held.set()
                time.sleep(.5)
        holder = threading.Thread(target=hold)
        holder.start(); self.assertTrue(held.wait(3))
        try:
            self.assertEqual(Z.straznik(self.path, api=self.api, spij=lambda _: None), 'odmrozono')
        finally:
            holder.join(timeout=3)
        self.assertEqual(self.api.count[10], 0)

    def test_guardian_retries_transient_read_error(self):
        self.interrupted()
        original = Z.czytaj_dzierzawe
        n = [0]
        def read(path):
            n[0] += 1
            if n[0] == 1:
                raise PermissionError(13, 'temporary scanner lock')
            return original(path)
        with patch.object(Z, 'czytaj_dzierzawe', side_effect=read):
            self.assertEqual(Z.straznik(self.path, api=self.api, spij=lambda _: None), 'odmrozono')
        self.assertEqual(self.api.count[10], 0)

    def test_checkpoint_retries_sharing_violation(self):
        original = os.replace
        n = [0]
        def replace(src, dst):
            n[0] += 1
            if n[0] < 3:
                raise PermissionError(13, 'temporary sharing violation')
            return original(src, dst)
        with patch.object(Z.os, 'replace', side_effect=replace):
            Z.zapisz_dzierzawe(self.path, {'manager': []})
        self.assertEqual(n[0], 3)
        self.assertEqual(Z.czytaj_dzierzawe(self.path)['manager'], [])

    def test_backup_without_journal_is_preserved_and_unsafe(self):
        dest, journal, backup = self.interrupted()
        journal.unlink()
        old = (backup / 'server.bin').read_bytes()
        result = SYNC.wykonaj({}, str(self.root / 'unused'), str(dest))
        self.assertFalse(result.safe_to_resume)
        self.assertEqual((backup / 'server.bin').read_bytes(), old)


class DoExitReview(U.Baza):
    def setUp(self):
        super().setUp()
        self.sprawdzenie()
        self.assertEqual(self.p.przed_doexit('Ragnarok'), ('ok', ''))

    def test_process_exit_confirms_uncertain_doexit_without_resend(self):
        result = []
        with patch.object(self.p, '_serwer_dziala', return_value=(False, True)):
            self.assertTrue(self.p.rozstrzygnij_doexit('Ragnarok', result.append))
        self.assertEqual(result, [None])
        self.assertEqual(self.api.licznik[10], 1)  # manager waits for normal copy path
        with patch.object(SYNC, 'wykonaj', return_value=SYNC.WynikSynchronizacji(False, 'test', {}, True)) as sync, \
             patch.object(U.modul.time, 'sleep'):
            self.p.po_doexit('Ragnarok')
        self.assertEqual(sync.call_count, 1)
        self.assertEqual(self.api.licznik[10], 0)

    def test_process_still_alive_counts_failed_attempt_and_does_not_copy(self):
        with patch.object(U.modul, 'CZEKAJ_NA_WYJSCIE_S', 0), \
             patch.object(self.p, '_serwer_dziala', return_value=(True, True)), \
             patch.object(SYNC, 'wykonaj') as sync:
            self.assertTrue(self.p.rozstrzygnij_doexit(
                'Ragnarok', lambda err: self.p.doexit_nieudany('Ragnarok') if err else self.fail('false success')))
        sync.assert_not_called()
        self.assertEqual(len(self.p.cfg['proby']['Ragnarok|%s' % U.NOWY]), 1)
        self.assertEqual(self.api.licznik[10], 0)

    def test_missing_permissions_do_not_confirm_process_exit(self):
        result = []
        with patch.object(U.modul, 'CZEKAJ_NA_WYJSCIE_S', 0), \
             patch.object(self.p, '_serwer_dziala', return_value=(False, False)):
            self.p.rozstrzygnij_doexit('Ragnarok', result.append)
        self.assertTrue(result[0])
        self.assertEqual(self.api.licznik[10], 1)

    def test_timer_cannot_resume_during_exit_observation(self):
        with patch.object(self.core, 'run_async'):
            self.assertTrue(self.p.rozstrzygnij_doexit('Ragnarok', lambda err: None))
        self.p._bez_instalacji(self.p._zadanie)
        self.assertEqual(self.api.licznik[10], 1)
        self.assertEqual(self.p._zadanie['faza'], 'oczekiwanie_doexit')

    def test_retry_button_does_not_touch_active_worker(self):
        with patch.object(self.p.zamrazarka, 'ponow_po_zakonczeniu_pracy') as recover:
            self.assertFalse(self.p.ponow_odzyskiwanie())
        recover.assert_not_called()

    def test_retry_button_recovers_failed_resume_with_live_idle_owner(self):
        with patch.object(self.api, 'odmroz', side_effect=PermissionError('temporary')):
            self.p.doexit_nieudany('Ragnarok')
        self.assertTrue(self.p.zamrazarka.aktywna())
        self.assertTrue(self.p.ponow_odzyskiwanie())
        self.assertEqual(self.api.licznik[10], 0)
        self.assertFalse(self.p.blokada_kolejki())

    def test_alarm_is_visible_once_and_in_panel_text(self):
        Z._alarm(self.p.zamrazarka.sciezka, ['synthetic alarm'])
        self.p._pokaz_alarm(); self.p._pokaz_alarm()
        self.assertEqual(len(self.logi('Strażnik: synthetic alarm')), 1)
        self.assertIn('synthetic alarm', self.p._opis_stanu())


class QueueReview(unittest.TestCase):
    def test_uncertain_doexit_keeps_queue_waiting_until_process_observed(self):
        class App(ProcedureMixin):
            def log(self, *a): pass
            def tr(self, key, **kw): return key
            def _checkpoint_procedure(self, *a, **kw): pass
            def _start_return_watch(self, maps): self.watched = maps
        app = App()
        q = Kolejka([Mapa('A', [(0, 'DoExit')])], sondy=False)
        app._kolejka = q
        q.tick(1000)
        before = q.mapa('A').stan
        app._proc_map_results = {}
        app._zlecenia_w_kolejce = {'A': {'aktywne': True, 'wlasciciel': 'aktualizacja_serwera'}}
        callbacks, hooks = [], []
        def call(owner, hook, name, *args):
            hooks.append(hook)
            if hook == 'rozstrzygnij_doexit':
                callbacks.append(args[0]); return True
        app.plugin_host = types.SimpleNamespace(call_one=call)
        app._wynik_doexit('A', 'DoExit', siec.RCONUncertainError('closed'))
        self.assertEqual(q.mapa('A').stan, before)
        self.assertNotIn('doexit_nieudany', hooks)
        callbacks[0](None)
        self.assertEqual(q.mapa('A').stan, START)
        self.assertIn('po_doexit', hooks)
        self.assertEqual(app.watched, ['A'])


# Avoid rerunning imported/inherited regression cases during discovery.
def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    for cls in (RecoveryReview, DoExitReview, QueueReview):
        suite.addTests(cls(name) for name in cls.__dict__ if name.startswith('test_'))
    return suite
