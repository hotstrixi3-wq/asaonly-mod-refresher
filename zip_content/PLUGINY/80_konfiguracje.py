# -*- coding: utf-8 -*-
"""Konfiguracje — import ze starego Refreshera, backup ZIP i przywracanie (V3.83).

Jeden plugin w miejsce dwóch: „Importer starych konfiguracji” (80) i
„Backup / Przywracanie” (81). Logika obu została bez zmian; nowe są:
  * jeden panel z dwiema zakładkami i jeden przełącznik ON/OFF,
  * jednorazowe przejęcie zapisanych wyborów ON/OFF starych pluginów,
  * po przywróceniu backupu program zamyka się BEZ zapisu — wcześniej każde
    późniejsze zapisanie (także zwykłe zamknięcie) nadpisywało przywrócone
    pliki starym stanem z pamięci,
  * przywracanie jest zablokowane w trakcie procedury restartu.
Wszystko na żądanie: samo ON nie uruchamia niczego w tle.
"""
import json
import os
import shutil
import tempfile
import time
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from asaonly.jezyk import t


ALLOWED_ROOTS = ("CONFIG_PROGRAM", "CONFIG_MAPS_TABS", "CONFIG_SECRET_API")


def _tak_nie(wartosc):
    return t("TAK", "YES") if wartosc else t("NIE", "NO")


class Wtyczka:
    nazwa = "konfiguracje"
    API = 1
    TR = {}
    manager_visible = True
    version = "2.1.0"
    required = False
    main_action_text = "IMPORT / BACKUP"
    main_action_hook = "panel"
    main_action_requires_enabled = True
    default_enabled = True  # jak dawny importer: przydatny na starcie
    # Host pomija te pluginy, jeśli ich stare pliki zostały w PLUGINY.
    zastepuje = ("importer_starych_konfigow", "backup_restore")

    # Teksty dla człowieka są właściwościami: język liczy się w chwili odczytu.
    @property
    def manager_name(self):
        return t("Konfiguracje — import, backup, przywracanie",
                 "Configurations — import, backup, restore")

    @property
    def manager_description(self):
        return t(
            "IMPORT ze starego Refreshera lub backupu (mapy, sekrety RCON, klucz CurseForge API — "
            "wybierasz, co wejdzie; źródło jest tylko czytane), BACKUP ZIP konfiguracji (sekrety "
            "tylko po zaznaczeniu) i PRZYWRACANIE z walidacją i rollbackiem. Wszystko na żądanie — "
            "samo ON nie uruchamia niczego w tle. Gdy mapy są skonfigurowane, można go wyłączyć — "
            "nie jest potrzebny do monitorowania, modów, RCON ani CPU.",
            "IMPORT from the old Refresher or a backup (maps, RCON secrets, CurseForge API key — "
            "you choose what goes in; the source is only read), ZIP BACKUP of the configuration "
            "(secrets only when ticked) and RESTORE with validation and rollback. Everything on "
            "demand — ON alone runs nothing in the background. Once the maps are configured you "
            "can turn it off — it is not needed for monitoring, mods, RCON or CPU.")

    def __init__(self):
        self.core = None
        self.enabled = True
        self.window = None
        self.root_var = None
        self.summary_var = None
        self.results_frame = None
        self.candidates = []
        self.vars = []
        self.api_candidate = None
        self.api_var = None
        self.secrets_var = None

    # -- cykl życia --------------------------------------------------------------
    def prepare(self, core):
        self.core = core
        cfg = core.plugin_config(self.nazwa)
        if "enabled" in cfg:
            self.enabled = bool(cfg.get("enabled"))
        else:
            wybor = self._wybor_ze_starych_pluginow(core)
            if wybor is None:
                self.enabled = bool(self.default_enabled)
            else:
                self.enabled = wybor
                core.save_plugin_config(self.nazwa, {"enabled": self.enabled})
        self._publish()

    @staticmethod
    def _wybor_ze_starych_pluginow(core):
        """Jednorazowo: ON, jeśli którykolwiek z zastąpionych pluginów był ON.

        None = żaden z nich nie ma zapisanego wyboru (zostaje domyślne ON).
        Importer bez zapisanego „enabled” był ON, backup — OFF.
        """
        app_cfg = getattr(core.application(), "config_data", None)
        plugins = app_cfg.get("plugins", {}) if isinstance(app_cfg, dict) else {}
        if not isinstance(plugins, dict):
            return None
        importer = plugins.get("importer_starych_konfigow")
        backup = plugins.get("backup_restore")
        if not isinstance(importer, dict) and not isinstance(backup, dict):
            return None
        importer_on = bool(importer.get("enabled", True)) if isinstance(importer, dict) else True
        backup_on = bool(backup.get("enabled", False)) if isinstance(backup, dict) else False
        return importer_on or backup_on

    def _publish(self):
        self.core.set_indicator(self.nazwa, t("ON — gotowy", "ON — ready") if self.enabled else "OFF",
                                "#207020" if self.enabled else "#555555")

    def start(self, core):
        self.prepare(core)

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.core.save_plugin_config(self.nazwa, {"enabled": self.enabled})
        self._publish()
        self.core.set_plugin_toggle(self.nazwa, self.enabled)
        self.core.log(t("[KONFIGURACJE] %s", "[CONFIGURATIONS] %s") % ("ON" if self.enabled else "OFF"),
                      "cpu_ok" if self.enabled else "cpu_off")
        if self.window and not self.enabled:
            self._close()

    def self_test(self):
        app = self.core.application()
        required = ("_normalize_legacy_tab", "_import_one_tab")
        missing = [name for name in required if not callable(getattr(app, name, None))]
        if missing:
            return {"ok": False, "details": t("brak usług importu: ", "import services missing: ")
                    + ", ".join(missing)}
        base = self._base_dir()
        if not os.access(base, os.R_OK | os.W_OK):
            return {"ok": False, "details": t("katalog programu bez prawa zapisu (backup/przywracanie)",
                                              "program folder is not writable (backup/restore)")}
        return {"ok": True, "details": t("skaner JSON, usługi importu i katalog programu dostępne; "
                                         "bez zapisu i bez tworzenia archiwum",
                                         "JSON scanner, import services and program folder available; "
                                         "nothing written and no archive created")}

    def konfiguracja(self):
        return {"enabled": self.enabled}

    def stop(self):
        self._close()

    @staticmethod
    def _base_dir():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # -- panel ---------------------------------------------------------------------
    def panel(self, parent):
        if not self.enabled:
            messagebox.showwarning(t("Konfiguracje — plugin wyłączony",
                                     "Configurations — plugin disabled"),
                                   t("Włącz plugin „Konfiguracje — import, backup, przywracanie” "
                                     "w Managerze Pluginów.",
                                     "Turn on the 'Configurations — import, backup, restore' plugin "
                                     "in the Plugin Manager."), parent=parent)
            return None
        try:
            if self.window and self.window.winfo_exists():
                self.window.deiconify(); self.window.lift(); return self.window
        except Exception:
            pass
        win = tk.Toplevel(parent); self.window = win
        win.title(t("Konfiguracje — import, backup, przywracanie",
                    "Configurations — import, backup, restore"))
        win.geometry("1050x720"); win.minsize(800, 520)
        win.protocol("WM_DELETE_WINDOW", self._close)
        outer = ttk.Frame(win, padding=14); outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=t("KONFIGURACJE — IMPORT, BACKUP, PRZYWRACANIE",
                                "CONFIGURATIONS — IMPORT, BACKUP, RESTORE"),
                  font=("TkDefaultFont", 15, "bold")).pack(anchor="w")
        book = ttk.Notebook(outer)
        book.pack(fill="both", expand=True, pady=(10, 0))
        imp = ttk.Frame(book, padding=10)
        book.add(imp, text=t("IMPORT ZE STAREGO REFRESHERA", "IMPORT FROM THE OLD REFRESHER"))
        bak = ttk.Frame(book, padding=14)
        book.add(bak, text=t("BACKUP I PRZYWRACANIE", "BACKUP AND RESTORE"))
        self._build_import_tab(imp)
        self._build_backup_tab(bak)
        ttk.Button(outer, text=t("ZAMKNIJ", "CLOSE"), command=self._close).pack(anchor="e", pady=(10, 0))
        return win

    def _build_import_tab(self, outer):
        ttk.Label(outer, text=t("Wskaż główny katalog starego Refreshera lub backupu. Skan niczego "
                                "nie zmienia; import nastąpi dopiero po zaznaczeniu pozycji "
                                "i potwierdzeniu.",
                                "Point to the main folder of the old Refresher or of a backup. The scan "
                                "changes nothing; the import happens only after you tick items "
                                "and confirm."),
                  foreground="#555555", wraplength=940).pack(anchor="w", pady=(0, 10))
        pick = ttk.Frame(outer); pick.pack(fill="x")
        self.root_var = tk.StringVar()
        ttk.Entry(pick, textvariable=self.root_var).pack(side="left", fill="x", expand=True)
        ttk.Button(pick, text=t("WYBIERZ KATALOG", "CHOOSE FOLDER"),
                   command=self._pick).pack(side="left", padx=6)
        ttk.Button(pick, text=t("SKANUJ KATALOG", "SCAN FOLDER"),
                   command=self._scan_clicked).pack(side="left")
        self.summary_var = tk.StringVar(value=t("Nie wykonano skanu.", "No scan yet."))
        ttk.Label(outer, textvariable=self.summary_var,
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=10)
        box = ttk.Frame(outer); box.pack(fill="both", expand=True)
        canvas = tk.Canvas(box, highlightthickness=0)
        sb = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        self.results_frame = ttk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        self.results_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(wid, width=e.width))
        ttk.Button(outer, text=t("IMPORTUJ ZAZNACZONE", "IMPORT SELECTED"),
                   command=self._import_selected).pack(anchor="w", pady=(10, 0))

    def _build_backup_tab(self, frame):
        ttk.Label(frame, wraplength=940, justify="left", text=t(
            "BACKUP obejmuje ZAPISANĄ na dysku konfigurację programu i map "
            "(CONFIG_PROGRAM, CONFIG_MAPS_TABS). Sekrety — hasła RCON i klucz CurseForge API — "
            "tylko po zaznaczeniu.",
            "The BACKUP covers the program and map configuration SAVED on disk "
            "(CONFIG_PROGRAM, CONFIG_MAPS_TABS). Secrets — RCON passwords and the CurseForge "
            "API key — only when ticked.")).pack(anchor="w")
        self.secrets_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text=t("Dołącz sekrety RCON i klucz API (wrażliwe dane)",
                                      "Include RCON secrets and the API key (sensitive data)"),
                        variable=self.secrets_var).pack(anchor="w", pady=8)
        ttk.Button(frame, text=t("UTWÓRZ BACKUP ZIP", "CREATE ZIP BACKUP"),
                   command=lambda: self._backup(self.window, self.secrets_var.get())).pack(
                       anchor="w", pady=(0, 18))
        ttk.Label(frame, wraplength=940, justify="left", text=t(
            "PRZYWRACANIE najpierw sprawdza całe archiwum w katalogu tymczasowym, potem podmienia "
            "konfigurację z rollbackiem. Hasła RCON, których nie ma w archiwum, zostają obecne. "
            "Po przywróceniu program zamknie się BEZ zapisywania (inaczej nadpisałby przywrócone "
            "pliki swoim starym stanem) — uruchom go ponownie. Niedostępne w trakcie procedury "
            "restartu.",
            "RESTORE first checks the whole archive in a temporary folder, then swaps the "
            "configuration with rollback. RCON passwords that are not in the archive stay as they "
            "are now. After restoring, the program closes WITHOUT saving (otherwise it would "
            "overwrite the restored files with its old state) — start it again. Not available "
            "during a restart procedure.")).pack(anchor="w")
        ttk.Button(frame, text=t("PRZYWRÓĆ Z ZIP (z potwierdzeniem)",
                                 "RESTORE FROM ZIP (with confirmation)"),
                   command=lambda: self._restore(self.window)).pack(anchor="w", pady=8)

    def _close(self):
        try:
            if self.window: self.window.destroy()
        except Exception: pass
        self.window = None

    # -- import ze starego Refreshera --------------------------------------------------
    def _pick(self):
        path = filedialog.askdirectory(title=t("Wskaż stary katalog Refreshera",
                                               "Choose the old Refresher folder"), parent=self.window)
        if path: self.root_var.set(path)

    @staticmethod
    def scan_directory(root):
        """Read-only recursive scan. Returns newest valid candidate per map."""
        root = os.path.abspath(root)
        found = {}
        passwords = {}
        api_keys = []
        errors = []
        files_seen = 0
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d)) and d != "__pycache__"]
            for filename in files:
                if not filename.lower().endswith(".json"):
                    continue
                path = os.path.join(base, filename); files_seen += 1
                try:
                    if os.path.getsize(path) > 10 * 1024 * 1024:
                        continue
                    with open(path, "r", encoding="utf-8-sig") as fh:
                        data = json.load(fh)
                except Exception as exc:
                    errors.append((path, str(exc))); continue
                entries = []
                if isinstance(data, dict) and str(data.get("api_key") or "").strip():
                    api_keys.append({"value": str(data["api_key"]).strip(), "path": path,
                                     "mtime": os.path.getmtime(path)})
                if isinstance(data, dict) and isinstance(data.get("passwords"), dict):
                    passwords.update({str(k): str(v) for k, v in data["passwords"].items() if v})
                if isinstance(data, dict) and data.get("password"):
                    parent_name = os.path.basename(os.path.dirname(base)) if os.path.basename(base) == "CONFIG_SECRET_RCON" else os.path.basename(base)
                    if parent_name: passwords[parent_name.replace("_", " ")] = str(data["password"])
                if isinstance(data, dict) and isinstance(data.get("servers"), dict):
                    global_mods = data.get("mod_ids", "")
                    for name, cfg in data["servers"].items():
                        if isinstance(cfg, dict):
                            item = dict(cfg); item["name"] = str(name)
                            if not item.get("mod_ids") and global_mods:
                                item["mod_ids"] = global_mods
                            entries.append((str(name), item, t("stara konfiguracja globalna",
                                                               "old global configuration")))
                elif isinstance(data, dict) and isinstance(data.get("lines"), list):
                    name = str(data.get("name") or "").strip()
                    if not name:
                        stem = os.path.splitext(filename)[0]
                        if stem.startswith("asa_server_"): name = stem[len("asa_server_"):].replace("_", " ")
                        else: name = os.path.basename(base).replace("_", " ")
                    entries.append((name or "Import", dict(data),
                                    t("konfiguracja mapy", "map configuration")))
                for name, cfg, fmt in entries:
                    stamp = os.path.getmtime(path)
                    bucket = found.setdefault(name, [])
                    bucket.append({"name": name, "config": cfg, "path": path,
                                   "mtime": stamp, "format": fmt})
        candidates = []
        for name, versions in found.items():
            versions.sort(key=lambda x: x["mtime"], reverse=True)
            best = dict(versions[0]); best["versions"] = len(versions)
            best["config"] = dict(best["config"])
            if name in passwords and not best["config"].get("password"):
                best["config"]["password"] = passwords[name]
            best["secret_found"] = bool(best["config"].get("password"))
            candidates.append(best)
        candidates.sort(key=lambda x: x["name"].lower())
        api_keys.sort(key=lambda x: x["mtime"], reverse=True)
        return {"root": root, "files_seen": files_seen, "candidates": candidates,
                "api_candidate": api_keys[0] if api_keys else None,
                "api_versions": len(api_keys), "errors": errors}

    def _scan_clicked(self):
        root = self.root_var.get().strip()
        if not root or not os.path.isdir(root):
            messagebox.showerror("Import", t("Wskaż istniejący katalog.", "Choose an existing folder."),
                                 parent=self.window); return
        self.summary_var.set(t("Skanowanie…", "Scanning…"))
        try:
            report = self.scan_directory(root)
        except Exception as exc:
            messagebox.showerror("Import", str(exc), parent=self.window); return
        self.candidates = report["candidates"]
        self.api_candidate = report.get("api_candidate")
        self.summary_var.set(t("Przejrzano %d plików JSON; map: %d; klucz CF API: %s; błędnych JSON: %d",
                               "Checked %d JSON files; maps: %d; CF API key: %s; invalid JSON: %d") %
                             (report["files_seen"], len(self.candidates),
                              _tak_nie(self.api_candidate), len(report["errors"])))
        self._render_results()
        self.core.log(t("[IMPORT] skan %s — mapy=%d, JSON=%d, błędy=%d",
                        "[IMPORT] scan %s — maps=%d, JSON=%d, errors=%d") %
                      (root, len(self.candidates), report["files_seen"], len(report["errors"])), "plugin_test")

    def _render_results(self):
        for child in self.results_frame.winfo_children(): child.destroy()
        self.vars = []
        self.api_var = tk.BooleanVar(value=bool(self.api_candidate))
        api_card = ttk.LabelFrame(self.results_frame, text="CurseForge API", padding=10)
        api_card.pack(fill="x", pady=4, padx=2)
        if self.api_candidate:
            ttk.Checkbutton(api_card, variable=self.api_var,
                            text=t("Importuj znaleziony klucz CurseForge API",
                                   "Import the CurseForge API key that was found")).pack(anchor="w")
            ttk.Label(api_card, text=t("Znaleziono: TAK · %s · wartość pozostaje ukryta",
                                       "Found: YES · %s · the value stays hidden") %
                      time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(self.api_candidate["mtime"])),
                      foreground="#207020").pack(anchor="w", padx=(24, 0))
            ttk.Label(api_card, text=self.api_candidate["path"], wraplength=850).pack(anchor="w", padx=(24, 0))
        else:
            ttk.Label(api_card, text=t("Klucz CurseForge API znaleziony: NIE",
                                       "CurseForge API key found: NO"),
                      foreground="#555555").pack(anchor="w")
        if not self.candidates:
            ttk.Label(self.results_frame, text=t("Nie znaleziono konfiguracji map.",
                                                 "No map configurations found."),
                      padding=15).pack(anchor="w"); return
        for item in self.candidates:
            var = tk.BooleanVar(value=True); self.vars.append(var)
            card = ttk.LabelFrame(self.results_frame, padding=10); card.pack(fill="x", pady=4, padx=2)
            ttk.Checkbutton(card, variable=var, text=item["name"],
                            style="TCheckbutton").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=t("%s · %s · backupów: %d · sekret RCON: %s",
                                   "%s · %s · backups: %d · RCON secret: %s") %
                      (item["format"], time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(item["mtime"])), item["versions"],
                       _tak_nie(item.get("secret_found"))),
                      foreground="#555555").grid(row=1, column=0, sticky="w", padx=(24, 0))
            ttk.Label(card, text=item["path"], wraplength=850).grid(row=2, column=0, sticky="w", padx=(24, 0))

    def _import_selected(self):
        selected = [item for item, var in zip(self.candidates, self.vars) if var.get()]
        import_api = bool(self.api_candidate and self.api_var and self.api_var.get())
        if not selected and not import_api:
            messagebox.showwarning("Import", t("Nie zaznaczono żadnej mapy ani klucza API.",
                                               "No map or API key selected."), parent=self.window); return
        if not messagebox.askyesno(t("Potwierdzenie importu", "Confirm import"),
            t("Zaimportować mapy: %d\nKlucz CurseForge API: %s\n\nKatalog źródłowy pozostanie nietknięty.",
              "Import maps: %d\nCurseForge API key: %s\n\nThe source folder stays untouched.") %
            (len(selected), _tak_nie(import_api)), parent=self.window): return
        app = self.core.application(); ok = 0; failed = []
        for item in selected:
            try:
                cfg = app._normalize_legacy_tab(dict(item["config"]), item["path"])
                cfg["name"] = item["name"]
                if app._import_one_tab(cfg, item["path"]): ok += 1
            except Exception as exc:
                failed.append("%s: %s" % (item["name"], exc))
        api_ok = False
        if import_api:
            try:
                app.var_api_key.set(self.api_candidate["value"])
                app.save_secrets(silent=True)
                api_ok = True
            except Exception as exc:
                failed.append(t("Klucz CurseForge API: %s", "CurseForge API key: %s") % exc)
        msg = (t("Zaimportowano map: %d\nKlucz CurseForge API: %s",
                 "Maps imported: %d\nCurseForge API key: %s") %
               (ok, t("ZAIMPORTOWANO", "IMPORTED") if api_ok else
                (t("POMINIĘTO", "SKIPPED") if not import_api else t("BŁĄD", "ERROR"))))
        if failed: msg += t("\nBłędy:\n", "\nErrors:\n") + "\n".join(failed)
        self.core.log("[IMPORT] " + msg.replace("\n", " | "), "cpu_ok" if not failed else "warn")
        messagebox.showinfo(t("Import — wynik", "Import — result"), msg, parent=self.window)
        # Wyniki skanu nie mogą pozostać aktywne po imporcie: ponowne
        # kliknięcie tworzyło duplikaty tych samych map. Okno zostaje otwarte,
        # ale wraca do czystego stanu i wymaga świadomego ponownego skanu.
        self._clear_after_import()

    def _clear_after_import(self):
        self.candidates = []
        self.vars = []
        self.api_candidate = None
        self.api_var = None
        if self.root_var is not None:
            self.root_var.set("")
        if self.summary_var is not None:
            self.summary_var.set(t("Import zakończony. Wybierz katalog, aby wykonać nowy skan.",
                                   "Import finished. Choose a folder to run a new scan."))
        if self.results_frame is not None:
            for child in self.results_frame.winfo_children():
                child.destroy()

    # -- backup ----------------------------------------------------------------------------
    def _backup(self, parent, secrets):
        base = self._base_dir()
        dst = filedialog.asksaveasfilename(
            parent=parent, defaultextension=".zip",
            initialfile="ASAonly-backup-%s.zip" % time.strftime("%Y%m%d-%H%M%S"),
            filetypes=[("ZIP", "*.zip")])
        if not dst:
            return
        roots = ["CONFIG_PROGRAM", "CONFIG_MAPS_TABS"]
        if secrets:
            roots.append("CONFIG_SECRET_API")
        count = 0
        try:
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
                for root in roots:
                    full = os.path.join(base, root)
                    if not os.path.isdir(full):
                        continue
                    for directory, subdirectories, files in os.walk(full):
                        if not secrets:
                            subdirectories[:] = [name for name in subdirectories
                                                 if name.casefold() != "config_secret_rcon"]
                        if not secrets and os.path.basename(directory) == "CONFIG_SECRET_RCON":
                            continue
                        for filename in files:
                            path = os.path.join(directory, filename)
                            archive.write(path, os.path.relpath(path, base))
                            count += 1
            self.core.log(t("[BACKUP] utworzono %s; plików=%d; sekrety=%s",
                            "[BACKUP] created %s; files=%d; secrets=%s") %
                          (dst, count, _tak_nie(secrets)), "cpu_ok")
            messagebox.showinfo("Backup", t("Utworzono backup:\n%s\n\nPlików: %d",
                                            "Backup created:\n%s\n\nFiles: %d") %
                                (dst, count), parent=parent)
        except Exception as exc:
            messagebox.showerror("Backup", str(exc), parent=parent)

    # -- przywracanie ------------------------------------------------------------------------
    @staticmethod
    def _safe_member(name):
        normalized = name.replace("\\", "/")
        if not normalized or normalized.startswith("/"):
            return None
        parts = normalized.split("/")
        if any(part in ("", ".", "..") for part in parts):
            return None
        if parts[0] not in ALLOWED_ROOTS:
            return None
        return "/".join(parts)

    @staticmethod
    def _validate_staging(stage):
        count = 0
        for directory, _, files in os.walk(stage):
            for filename in files:
                path = os.path.join(directory, filename)
                count += 1
                if filename.lower().endswith(".json"):
                    with open(path, "r", encoding="utf-8") as handle:
                        json.load(handle)
        if not count:
            raise ValueError(t("archiwum nie zawiera obsługiwanej konfiguracji",
                               "the archive contains no supported configuration"))
        return count

    @staticmethod
    def _preserve_current_rcon_secrets(base, staged_maps):
        current = os.path.join(base, "CONFIG_MAPS_TABS")
        if not os.path.isdir(current):
            return
        for map_name in os.listdir(current):
            source = os.path.join(current, map_name, "CONFIG_SECRET_RCON")
            target = os.path.join(staged_maps, map_name, "CONFIG_SECRET_RCON")
            if os.path.isdir(source) and not os.path.exists(target):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copytree(source, target)

    @staticmethod
    def _apply_roots(base, stage, rollback, roots):
        moved, installed = [], []
        try:
            for root in roots:
                current = os.path.join(base, root)
                saved = os.path.join(rollback, root)
                if os.path.exists(current):
                    os.replace(current, saved); moved.append((saved, current))
                os.replace(os.path.join(stage, root), current); installed.append(current)
        except Exception:
            for current in reversed(installed):
                if os.path.isdir(current): shutil.rmtree(current, ignore_errors=True)
                elif os.path.exists(current):
                    try: os.remove(current)
                    except OSError: pass
            for saved, current in reversed(moved):
                if os.path.exists(saved): os.replace(saved, current)
            raise

    def _procedura_trwa(self):
        app = self.core.application()
        return bool(getattr(app, "restart_active", False) or getattr(app, "watch_active", False))

    def _restore(self, parent):
        if self._procedura_trwa():
            messagebox.showwarning(
                t("Przywracanie", "Restore"),
                t("Trwa procedura restartu albo czuwanie nad mapą. Przywróć konfigurację "
                  "po jej zakończeniu.",
                  "A restart procedure or a return watch is running. Restore the configuration "
                  "after it finishes."), parent=parent)
            return
        src = filedialog.askopenfilename(parent=parent, filetypes=[("ZIP", "*.zip")])
        if not src:
            return
        base = self._base_dir()
        transaction = tempfile.mkdtemp(prefix=".asaonly-restore-", dir=base)
        stage = os.path.join(transaction, "stage")
        rollback = os.path.join(transaction, "rollback")
        os.makedirs(stage)
        os.makedirs(rollback)
        przywrocono = 0
        try:
            with zipfile.ZipFile(src) as archive:
                bad = archive.testzip()
                if bad:
                    raise ValueError(t("uszkodzony element: ", "damaged entry: ") + bad)
                members = []
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    safe = self._safe_member(info.filename)
                    if safe is None:
                        raise ValueError(t("niedozwolona ścieżka w ZIP: ", "path not allowed in ZIP: ")
                                         + info.filename)
                    members.append((info, safe))
                for info, safe in members:
                    target = os.path.join(stage, *safe.split("/"))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with archive.open(info) as source, open(target, "wb") as output:
                        shutil.copyfileobj(source, output)

            count = self._validate_staging(stage)
            staged_maps = os.path.join(stage, "CONFIG_MAPS_TABS")
            if os.path.isdir(staged_maps):
                self._preserve_current_rcon_secrets(base, staged_maps)
            roots = [root for root in ALLOWED_ROOTS if os.path.isdir(os.path.join(stage, root))]
            if not messagebox.askyesno(
                    t("Przywracanie", "Restore"),
                    t("Archiwum sprawdzone. Plików: %d.\nZostanie wykonana podmiana z rollbackiem, "
                      "a potem program zamknie się BEZ zapisywania. Kontynuować?",
                      "Archive checked. Files: %d.\nThe configuration will be swapped with rollback, "
                      "then the program will close WITHOUT saving. Continue?") % count,
                    parent=parent):
                return

            # Podmiana całych rodzin konfiguracji z testowalnym rollbackiem.
            self._apply_roots(base, stage, rollback, roots)
            przywrocono = count
            self.core.log(t("[BACKUP] przywrócono %d plików z %s; program zamyka się bez zapisu",
                            "[BACKUP] restored %d files from %s; the program closes without saving") %
                          (count, src), "cpu_config")
        except Exception as exc:
            messagebox.showerror(t("Przywracanie", "Restore"),
                                 t("Nie przywrócono konfiguracji:\n", "Configuration not restored:\n")
                                 + str(exc), parent=parent)
        finally:
            shutil.rmtree(transaction, ignore_errors=True)
        if przywrocono:
            self._zamknij_program_po_przywroceniu(parent)

    def _zamknij_program_po_przywroceniu(self, parent):
        """Program w pamięci ma STARY stan; jego zapis nadpisałby przywrócone pliki."""
        messagebox.showinfo(
            t("Przywracanie", "Restore"),
            t("Przywrócono konfigurację.\n\nProgram zamknie się teraz BEZ zapisywania — inaczej "
              "nadpisałby przywrócone pliki swoim starym stanem. Uruchom go ponownie.",
              "Configuration restored.\n\nThe program will now close WITHOUT saving — otherwise "
              "it would overwrite the restored files with its old state. Start it again."),
            parent=parent)
        app = self.core.application()
        zamknij = getattr(type(app), "_zamknij_teraz", None)
        if callable(zamknij):
            zamknij(app)
        else:
            self.core.warn(t("[BACKUP] Zamknij program BEZ zapisywania i uruchom go ponownie — "
                             "inaczej przywrócona konfiguracja zostanie nadpisana.",
                             "[BACKUP] Close the program WITHOUT saving and start it again — "
                             "otherwise the restored configuration will be overwritten."))
