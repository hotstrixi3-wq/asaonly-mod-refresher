# -*- coding: utf-8 -*-
"""Admin-side stress simulation: running servers and frequent random CF updates."""
import random
import unittest
from unittest.mock import patch

from symulacja.test_cluster import FakeApp, FakeTab


class AdminStressSimulation(unittest.TestCase):
    SEEDS = range(20)
    CYCLES = 25

    @staticmethod
    def _pending(mid, fid, target):
        return {"mid": mid, "name": "Synthetic " + mid, "fid": str(fid),
                "targets": [target], "verified": []}

    def _start(self, app, now):
        with patch("asaonly.procedura.time.time", return_value=now), \
             patch("asaonly.procedura.messagebox.showerror"), \
             patch("asaonly.procedura.messagebox.showwarning"), \
             patch("asaonly.procedura.messagebox.askyesno", return_value=True):
            app._exec_pending()

    def _finish_queue(self, app, now, event_log):
        """V3.81: sterownik niezależny od wnętrza kolejki — czas płynie co 1 s,
        a mapa w czuwaniu jest „restartowana” (STARTING → nowy boot → READY)."""
        guard = 0
        sent_before = {name: len(tab.sent) for name, tab in app.tabs.items()}
        while app.restart_active or app.watch_active:
            guard += 1
            self.assertLess(guard, 5000, "kolejka administratora zakleszczyła się")
            now += 1
            with patch("asaonly.procedura.time.time", return_value=now):
                app._tick_restart_timeline()
            if app.watch_active:
                name = next(iter(app.watch_maps))
                tab = app.tabs[name]
                tab._tail_status = "starting"
                with patch("asaonly.procedura.time.time", return_value=now + 0.2):
                    app._tick_return_watch()
                self.assertTrue(app.watch_active, "sam STARTING nie może kończyć oczekiwania")
                tab._ready_proof = str(tab._boot_seq + 1); tab._ready_observed_at = now + 0.5; tab._boot_seq += 1
                tab._server_versions = {}
                for item in app.pending_updates:
                    if name in item.get("targets", []):
                        tab.installed[item["mid"]] = item["fid"]
                        tab._server_versions[item["mid"]] = item["fid"]
                tab._tail_status = "ready"
                with patch("asaonly.procedura.time.time", return_value=now + 0.5), \
                     patch("asaonly.procedura.os.path.isdir", return_value=True):
                    app._tick_restart_timeline()
                event_log.append(("ready", name, tab._boot_seq))
        for name, tab in app.tabs.items():
            if len(tab.sent) > sent_before[name]:
                event_log.append(("rcon", name, list(tab.sent[sent_before[name]:])))
        return now

    def test_admin_view_many_running_servers_with_frequent_random_cf_updates(self):
        """500 cycles: unique mod sets, random updates, updates during a queue."""
        for seed in self.SEEDS:
            rng = random.Random(seed)
            tabs = []
            ownership = {}
            for index in range(5):
                name = "Test Server %d" % (index + 1)
                mods = ["S%02dM%02d" % (index + 1, m) for m in range(1, 5)]
                for mid in mods:
                    ownership[mid] = name
                # Each administrator-defined timeline is intentionally different.
                lines = [(str(index + 1), "ServerChat test"),
                         (str(10 + index * 7), "DoExit")]
                tab = FakeTab(name, mods, lines, 31000 + index, status="ready")
                tab.installed = {mid: "100" for mid in mods}
                tabs.append(tab)

            app = FakeApp(tabs, [])
            versions = {mid: 100 for mid in ownership}
            now = 1000.0
            for cycle in range(self.CYCLES):
                # A burst can contain several independent CF releases.
                burst = rng.sample(list(ownership), rng.randint(1, 7))
                for mid in burst:
                    versions[mid] += rng.randint(1, 3)
                    app._add_or_update_pending(mid, "Synthetic " + mid,
                                               str(versions[mid]))
                expected_first = {ownership[mid] for mid in burst}
                sent_before = {t.name: len(t.sent) for t in tabs}
                self._start(app, now)
                self.assertTrue(app.restart_active)
                self.assertTrue(all(not t.editable for t in tabs))

                # While the first queue is active, CF publishes another update
                # for a server outside that queue whenever possible.
                outside = [mid for mid, owner in ownership.items()
                           if owner not in expected_first]
                injected_owner = None
                if outside:
                    mid = rng.choice(outside)
                    versions[mid] += 1
                    injected_owner = ownership[mid]
                    app._add_or_update_pending(mid, "Synthetic " + mid,
                                               str(versions[mid]))

                events = []
                now = self._finish_queue(app, now, events)
                first_rcon_servers = {name for kind, name, _ in events if kind == "rcon"}
                self.assertEqual(first_rcon_servers, expected_first)
                self.assertTrue(all(t.editable for t in tabs))

                if injected_owner:
                    self.assertTrue(app.pending_updates)
                    self.assertIsNotNone(app._auto_next_t)
                    now = app._auto_next_t
                    self._start(app, now)
                    events2 = []
                    now = self._finish_queue(app, now, events2)
                    self.assertEqual({name for kind, name, _ in events2 if kind == "rcon"},
                                     {injected_owner})

                self.assertEqual(app.pending_updates, [])
                self.assertFalse(app.restart_active)
                self.assertFalse(app.watch_active)
                self.assertTrue(all(t.editable for t in tabs))
                # Unaffected servers received no command in the first queue.
                for tab in tabs:
                    if tab.name not in expected_first:
                        self.assertEqual(sent_before[tab.name],
                                         len(tab.sent) - (2 if tab.name == injected_owner else 0))
                now += 5


if __name__ == "__main__":
    unittest.main(verbosity=2)
