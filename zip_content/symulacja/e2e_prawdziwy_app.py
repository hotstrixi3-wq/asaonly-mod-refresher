# -*- coding: utf-8 -*-
"""V3.81 — próba end-to-end PRAWDZIWEJ aplikacji (App + Tk + LogTail + PluginHost).

Uruchamiana ręcznie (trwa ok. 1–2 min, bo LogTail trzyma 15 s łaski na rotację
logu — blizna): xvfb-run -a python3 symulacja/e2e_prawdziwy_app.py

Co robi:
  * kopiuje program do katalogu tymczasowego (program zakłada tam CONFIG_*),
  * wkłada konfigurację trzech map w formacie V3.74 (z zaznaczonymi pustymi
    wierszami RCON na Extinction — ten sam układ, który blokował V3.74),
  * zostawia „przerwaną procedurę” w PROCEDURE_RUN_STATE.json (ma być porzucona,
    a nie blokować automat),
  * stawia atrapy serwerów RCON na portach map i atrapy logów ASA,
  * po DoExit „restartuje” serwer: kasuje log, pisze nowy start z liniami CFCore
    i LoadGameMods w prawdziwym formacie ASA, zakłada katalog nowej wersji moda,
  * na końcu wypisuje raport i kod wyjścia 0/1.
"""
import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from symulacja.test_sciezka_produkcyjna import AtrapaRcon  # noqa: E402

MOD, STARY, NOWY = "928548", "7005633", "7005700"
MAPY = {
    # nazwa: (port, odpowiedź ListPlayers, linie RCON w formacie V3.74)
    "Genesis 1": (27020, "No Players Connected",
                  [{"time": "5", "cmd": "doExit", "on": True},
                   {"time": "", "cmd": "", "on": False}]),
    "Ragnarok": (27022, "0. Magus, 0002a1b2c3d4e5f6",
                 [{"time": "0", "cmd": "ServerChat Restart za 20 s", "on": True},
                  {"time": "20", "cmd": "doExit", "on": True}]),
    "Extinction": (27021, "No Players Connected",
                   [{"time": "405", "cmd": "DoExit", "on": True},
                    {"time": "", "cmd": "", "on": True},
                    {"time": "", "cmd": "", "on": True},
                    {"time": "", "cmd": "", "on": True},
                    {"time": "", "cmd": "", "on": True}]),
}


def log_startu(fid, z_aktualizacja):
    t = time.strftime("%Y.%m.%d-%H.%M.%S")
    linie = ["[%s:000][  0]Log file open, %s" % (t, time.strftime("%m/%d/%y %H:%M:%S"))]
    if z_aktualizacja:
        linie += [
            "[%s:100][ 18]LogCFCore: Mod: Shiny! Dinos Ascended (%s) requires upgrade/downgrade (%s -> %s)"
            % (t, MOD, STARY, fid),
            "[%s:200][ 18]LogCFCore: Request to Install mod 'Shiny! Dinos Ascended' (modId=%s, fileId=%s)"
            % (t, MOD, fid),
            "[%s:300][ 18]LogCFCore: Starting download - 1 parts for https://mediafilez.forgecdn.net/x ..." % t,
            "[%s:400][ 66]LogCFCore: Successfully installed mod 'Shiny! Dinos Ascended' (modId=%s, fileId=%s)"
            % (t, MOD, fid)]
    else:
        linie.append("[%s:100][ 17]LogCFCore: No need to update existing mod: Shiny! Dinos Ascended (%s)"
                     % (t, MOD))
    linie += ["[%s:500][ 18]UShooterEngine::LoadGameMods with 1 mods" % t,
              "[%s:600][ 18]UShooterEngine::LoadGameMods Loading Mod ShooterGame/Mods/83374/%s_%s/"
              "ShinyAscended/Content/PrimalGameData_Shiny.uasset : %s" % (t, MOD, fid, MOD)]
    return linie


def gotowosc():
    t = time.strftime("%Y.%m.%d-%H.%M.%S")
    return ["[%s:700][100]Server has successfully started!" % t,
            "[%s:800][248]Server has completed startup and is now advertising for join. (7.53GB Mem)" % t]


def main():
    work = pathlib.Path(tempfile.mkdtemp(prefix="asaonly-e2e-"))
    app_dir = work / "program"
    shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns(
        "tests", "symulacja", "__pycache__", ".git", ".pytest_cache"))
    serwery_dir = work / "ARKservers"
    raport = {"komendy": {}, "zdarzenia": []}

    # --- serwery: logi i katalogi modów -----------------------------------------
    logi = {}
    mods = {}
    for nazwa in MAPY:
        base = serwery_dir / (nazwa.replace(" ", "") + "_WP") / "ShooterGame"
        (base / "Saved" / "Logs").mkdir(parents=True)
        md = base / "Binaries" / "Win64" / "ShooterGame" / "Mods" / "83374"
        (md / ("%s_%s" % (MOD, STARY))).mkdir(parents=True)
        logi[nazwa] = base / "Saved" / "Logs" / "ShooterGame.log"
        mods[nazwa] = md
        logi[nazwa].write_text("\n".join(log_startu(STARY, False) + gotowosc()) + "\n", encoding="utf-8")

    # --- konfiguracja w formacie V3.74 -------------------------------------------
    stamp = time.strftime("%d.%m.%Y %H-%M-%S")
    for nazwa, (port, _, linie) in MAPY.items():
        tab_dir = app_dir / "CONFIG_MAPS_TABS" / nazwa
        (tab_dir / "CONFIG_SECRET_RCON").mkdir(parents=True)
        cfg = {"ip": "127.0.0.1", "port": str(port), "log_path": str(logi[nazwa].parent),
               "tail_log": True, "mods_unverified": False, "mod_ids": MOD, "map_on": True,
               "lines": linie, "admin_cmd": "", "stash": [], "name": nazwa}
        (tab_dir / ("CONFIG_MAP %s - zapis %s.json" % (nazwa, stamp))).write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        (tab_dir / "CONFIG_SECRET_RCON" / ("CONFIG_SECRET_RCON %s - zapis %s.json" % (nazwa, stamp))
         ).write_text(json.dumps({"password": "pw"}), encoding="utf-8")
    (app_dir / "CONFIG_PROGRAM").mkdir(exist_ok=True)
    (app_dir / "CONFIG_PROGRAM" / ("CONFIG_PROGRAM - zapis %s.json" % stamp)).write_text(json.dumps({
        "lang": "pl", "interval": 300, "cf_delay": 1.0, "watch_timeout_min": 3, "auto_rcon": True,
        "pending_updates": [], "known_versions": {MOD: STARY},
        "mod_names": {MOD: "Shiny! Dinos Ascended"}, "mod_pages": {}, "mods_disabled": []}),
        encoding="utf-8")
    (app_dir / "CONFIG_PROGRAM" / "PROCEDURE_RUN_STATE.json").write_text(json.dumps({
        "schema": 1, "procedure_run": {"run_id": "przerwany-test", "stage": "doexit_sent",
                                       "map": "Ragnarok"}}), encoding="utf-8")

    # --- atrapy RCON ------------------------------------------------------------------
    atrapy = {nazwa: AtrapaRcon(nazwa, "pw", odp, port=port)
              for nazwa, (port, odp, _) in MAPY.items()}

    # --- „restart serwera” po DoExit -------------------------------------------------
    def restartuj(nazwa):
        raport["zdarzenia"].append((round(time.time() - t0, 1), "DoExit odebrany", nazwa))
        time.sleep(1.0)
        logi[nazwa].unlink()                           # manager kasuje log przed startem
        time.sleep(2.0)
        (mods[nazwa] / ("%s_%s" % (MOD, STARY))).rename(mods[nazwa] / ("%s_%s" % (MOD, NOWY)))
        logi[nazwa].write_text("\n".join(log_startu(NOWY, True)) + "\n", encoding="utf-8")
        time.sleep(2.0)
        with open(logi[nazwa], "a", encoding="utf-8") as fh:
            fh.write("\n".join(gotowosc()) + "\n")
        raport["zdarzenia"].append((round(time.time() - t0, 1), "serwer GOTOWY w logu", nazwa))

    obserwowane = set()

    def straznik():
        while True:
            for nazwa, srv in atrapy.items():
                if nazwa not in obserwowane and any(c.lower().startswith("doexit") for c in srv.komendy()):
                    obserwowane.add(nazwa)
                    threading.Thread(target=restartuj, args=(nazwa,), daemon=True).start()
            time.sleep(0.1)
    threading.Thread(target=straznik, daemon=True).start()

    # --- prawdziwa aplikacja -----------------------------------------------------------
    main_file = app_dir / "ASAonly - (AUTO)Manual - ModRefresher (RCON).py"
    sys.path.insert(0, str(app_dir))
    spec = importlib.util.spec_from_file_location("asaonly_program_e2e", str(main_file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    app = mod.App()
    t0 = time.time()
    wynik = {"ok": False}

    def wstrzyknij():
        raport["stan_po_starcie"] = json.loads(
            (app_dir / "CONFIG_PROGRAM" / "PROCEDURE_RUN_STATE.json").read_text(encoding="utf-8"))
        raport["taby"] = {n: [(r["time"], r["cmd"], r["on"]) for r in t.rows] for n, t in app.tabs.items()}
        raport["checkbox_pusty"] = bool(app.var_pusty.get())
        app.pending_updates = [{"mid": MOD, "name": "Shiny! Dinos Ascended", "fid": NOWY,
                                "targets": list(MAPY), "verified": [], "qualified": True}]
        app._exec_pending()

    def pilnuj():
        if time.time() - t0 > 170 or (not app.restart_active and not app.watch_active
                                       and time.time() - t0 > 8):
            for nazwa, srv in atrapy.items():
                raport["komendy"][nazwa] = srv.komendy()
            raport["pending_na_koniec"] = app.pending_updates
            raport["known"] = dict(app.known_versions)
            raport["czasy_startu"] = app.config_data.get("czasy_startu")
            raport["dziennik"] = [x.rstrip() for x in app._log_buffer]
            wynik["ok"] = (not app.restart_active and app.pending_updates == [] and
                           app.known_versions.get(MOD) == NOWY)
            app._destroying = True
            try:
                app.plugin_host.stop_all()
            except Exception:
                pass
            app.destroy()
            return
        app.after(500, pilnuj)

    app.after(4000, wstrzyknij)
    app.after(6000, pilnuj)
    app.mainloop()

    out = work / "raport-e2e.json"
    out.write_text(json.dumps(raport, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RAPORT:", out)
    print("WYNIK:", "OK" if wynik["ok"] else "BLAD")
    return 0 if wynik["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
