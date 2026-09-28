# -*- coding: utf-8 -*-
"""Small, failure-isolating plugin host for ASAonly.

Plugins are loaded alphabetically from PLUGINY/*.py. A plugin cannot receive the
App object; it gets CoreAPI, which exposes snapshots and explicit services.
"""
from dataclasses import dataclass
import importlib.util
import os
import traceback
from types import MappingProxyType

from .jezyk import t

PLUGIN_API = 1


@dataclass(frozen=True)
class TabSnapshot:
    name: str
    enabled: bool
    ip: str
    rcon_port: str
    log_path: str
    mod_ids: tuple
    status: str
    restart: bool = False       # V3.86.2: po DoExit z kolejki, jeszcze nie GOTOWA


class CoreAPI:
    API = PLUGIN_API

    def __init__(self, app):
        self.__app = app

    def log(self, message, tag=None):
        """Log clean text; optional semantic tag colors only the live console."""
        self.__app.log(str(message), tag)

    def warn(self, message):
        self.__app.log_warn(str(message))

    def tr(self, key, **kwargs):
        return self.__app.tr(key, **kwargs)

    def is_admin(self):
        return getattr(self.__app, "is_admin", None)

    def application(self):
        """Trusted in-repository plugins may use application services."""
        return self.__app

    def post_ui(self, callback):
        self.__app.post_ui(callback)

    def run_async(self, fn, *args):
        self.__app.run_async(fn, *args)

    def tabs(self):
        """Immutable point-in-time view; no Tk variables escape to plugins."""
        result = {}
        for name, tab in list(self.__app.tabs.items()):
            result[name] = TabSnapshot(
                name=name, enabled=bool(tab.var_map_on.get()),
                ip=str(tab.var_ip.get()), rcon_port=str(tab.var_port.get()),
                log_path=str(tab.var_log.get()),
                mod_ids=tuple(tab.get_effective_mod_ids()),
                status=str(tab._tail_status),
                restart=self._w_restarcie(name))
        return MappingProxyType(result)

    def _w_restarcie(self, name):
        sprawdz = getattr(self.__app, "mapa_w_restarcie", None)
        try:
            return bool(sprawdz(name)) if sprawdz is not None else False
        except Exception:
            return False

    def mods(self):
        """Point-in-time version view without exposing mutable app dictionaries."""
        per_map = {}
        for name, tab in list(self.__app.tabs.items()):
            per_map[name] = dict(getattr(tab, "_server_versions", {}))
        return {
            "known": dict(self.__app.known_versions),
            "latest": {k: dict(v) for k, v in self.__app.mod_latest.items()},
            "names": dict(self.__app.mod_names),
            "pending": [dict(x) for x in self.__app.pending_updates],
            "server_observed": per_map,
        }

    def plugin_config(self, name):
        root = self.__app.config_data.get("plugins", {})
        value = root.get(name, {}) if isinstance(root, dict) else {}
        return dict(value) if isinstance(value, dict) else {}

    def save_plugin_config(self, name, value):
        if not isinstance(value, dict):
            raise TypeError("plugin configuration must be a dict")
        root = self.__app.config_data.setdefault("plugins", {})
        root[name] = dict(value)
        self.__app.request_save()
        # "Zapisz ustawienia" means durable now, not only on application exit.
        save = getattr(self.__app, "save_config", None)
        if save:
            save(silent=True)

    def set_indicator(self, plugin_name, text, color="#555555"):
        def update():
            host = getattr(self.__app, "plugin_host", None)
            if host:
                host.update_status(plugin_name, str(text), color)
        self.__app.post_ui(update)

    def set_plugin_toggle(self, plugin_name, enabled):
        def update():
            host = getattr(self.__app, "plugin_host", None)
            if host:
                host._refresh_manager_row(plugin_name)
        self.__app.post_ui(update)

    def emit(self, event, **payload):
        self.__app.plugin_host.emit(event, **payload)


class PluginHost:
    def __init__(self, app, directory):
        self.app = app
        self.directory = directory
        self.core = CoreAPI(app)
        self.plugins = []
        self.listeners = {}
        self._error_throttle = {}
        self.runtime_status = {}
        self.manager_window = None
        self.manager_rows = {}
        self.main_action_buttons = {}
        self.last_diagnostics = {}
        self._startup_diagnostics_done = False
        self._prepared = set()
        self._active = set()
        self._off_reconciled = set()

    def _report(self, plugin_name, phase, exc):
        key = (plugin_name, phase, type(exc).__name__, str(exc))
        # A broken 500 ms tick must not flood the console.
        import time
        now = time.time()
        if now - self._error_throttle.get(key, 0) < 60:
            return
        self._error_throttle[key] = now
        self.app.log_warn("[PLUGIN %s] %s: %s" % (plugin_name, phase, exc))
        try:
            from pathlib import Path
            Path(self.directory).mkdir(parents=True, exist_ok=True)
            with open(os.path.join(self.directory, "plugin-errors.log"), "a", encoding="utf-8") as fh:
                fh.write(traceback.format_exc() + "\n")
        except Exception:
            pass

    def load_all(self):
        os.makedirs(self.directory, exist_ok=True)
        for filename in sorted(os.listdir(self.directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            path = os.path.join(self.directory, filename)
            module_name = "asaonly_user_plugin_" + filename[:-3].replace("-", "_")
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                cls = getattr(module, "Wtyczka")
                plugin = cls()
                if getattr(plugin, "API", None) != PLUGIN_API:
                    raise RuntimeError(t("niezgodne API: %r (wymagane %r)",
                                         "incompatible API: %r (required %r)") %
                                       (getattr(plugin, "API", None), PLUGIN_API))
                if not getattr(plugin, "nazwa", ""):
                    raise RuntimeError(t("brak nazwy pluginu", "plugin has no name"))
                self.plugins.append(plugin)
            except Exception as exc:
                self._report(filename, "load", exc)
        self._pomin_zastapione()
        return tuple(self.plugins)

    def _pomin_zastapione(self):
        """V3.83: plugin może zastąpić wcześniejsze (atrybut `zastepuje`).

        Stare pliki zostają w PLUGINY, gdy nową wersję rozpakuje się na starą.
        Wtedy nie ładujemy ich obok następcy (dwa importery, dwa backupy).
        """
        zastapione = {}
        for plugin in self.plugins:
            for stara in getattr(plugin, "zastepuje", ()) or ():
                if str(stara) != plugin.nazwa:
                    zastapione[str(stara)] = plugin.nazwa
        if not zastapione:
            return
        zostaja = []
        for plugin in self.plugins:
            if plugin.nazwa in zastapione:
                self.app.log(t("[PLUGIN %s] pominięty — zastąpiony przez %s; jego stary plik "
                               "można usunąć z PLUGINY.",
                               "[PLUGIN %s] skipped — replaced by %s; its old file can be "
                               "deleted from PLUGINY.") % (plugin.nazwa, zastapione[plugin.nazwa]))
            else:
                zostaja.append(plugin)
        self.plugins = zostaja

    def _saved_enabled(self, plugin):
        if bool(getattr(plugin, "required", False)):
            return True
        cfg = self.core.plugin_config(plugin.nazwa)
        if "enabled" in cfg:
            return cfg.get("enabled") is True
        # Absence is not implicit ON. Only plugins that explicitly declare a
        # first-run default may activate without a persisted user choice.
        return bool(getattr(plugin, "default_enabled", False))

    def _prepare_plugin(self, plugin):
        """Bind configuration/UI only; preparation must not start operational work."""
        if plugin.nazwa in self._prepared:
            return True
        prepare = getattr(plugin, "prepare", None)
        if not callable(prepare):
            return False
        prepare(self.core)
        self._prepared.add(plugin.nazwa)
        return True

    def _activate_plugin(self, plugin):
        """Start operational lifecycle only after the authoritative ON decision."""
        if plugin.nazwa in self._active:
            return
        if not self._prepare_plugin(plugin):
            plugin.start(self.core)
            self._prepared.add(plugin.nazwa)
        activate = getattr(plugin, "activate", None)
        if callable(activate):
            activate()
        self._active.add(plugin.nazwa)

    def _effective_enabled(self, plugin):
        """One authoritative state: persisted OFF means not operationally active."""
        if bool(getattr(plugin, "required", False)):
            return plugin.nazwa in self._active
        if not self._saved_enabled(plugin):
            if (plugin.nazwa in self._prepared and
                    plugin.nazwa not in self._off_reconciled and
                    bool(getattr(plugin, "is_enabled", lambda: False)())):
                setter = getattr(plugin, "set_enabled", None)
                if callable(setter):
                    try:
                        setter(False)
                    except Exception as exc:
                        self._report(plugin.nazwa, "reconcile_off", exc)
                self._off_reconciled.add(plugin.nazwa)
            return False
        self._off_reconciled.discard(plugin.nazwa)
        if plugin.nazwa not in self._active:
            return False
        return bool(getattr(plugin, "is_enabled", lambda: True)())

    def start_all(self):
        for plugin in self.plugins:
            try:
                required = bool(getattr(plugin, "required", False))
                if required or self._saved_enabled(plugin):
                    self._activate_plugin(plugin)
                else:
                    # OFF plugins may load configuration for an explicitly safe
                    # configuration panel, but their operational start is forbidden.
                    self._prepare_plugin(plugin)
            except Exception as exc:
                self._report(plugin.nazwa, "start", exc)
        frame = getattr(self.app, "frm_plugin_actions", None)
        if frame is not None:
            self.build_main_actions(frame, self.app)

    def tick(self, now):
        for plugin in self.plugins:
            if not self._effective_enabled(plugin):
                continue
            fn = getattr(plugin, "tik", None)
            if fn:
                try:
                    fn(now)
                except Exception as exc:
                    self._report(plugin.nazwa, "tik", exc)

    def get(self, name):
        return next((p for p in self.plugins if p.nazwa == name), None)

    def call_one(self, name, hook, *args, **kwargs):
        plugin = self.get(name)
        if plugin is None:
            self.app.log_warn(t("[PLUGIN %s] nie został załadowany", "[PLUGIN %s] was not loaded") % name)
            return None
        fn = getattr(plugin, hook, None)
        if fn is None:
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            self._report(plugin.nazwa, hook, exc)
            return None

    def open_panel(self, name, parent):
        return self.call_one(name, "panel", parent)

    def call_hook(self, hook, *args, **kwargs):
        for plugin in self.plugins:
            if not self._effective_enabled(plugin):
                continue
            fn = getattr(plugin, hook, None)
            if fn:
                try:
                    fn(*args, **kwargs)
                except Exception as exc:
                    self._report(plugin.nazwa, hook, exc)

    def subscribe(self, event, callback, owner="anonymous"):
        self.listeners.setdefault(event, []).append((owner, callback))

    def emit(self, event, **payload):
        for owner, callback in list(self.listeners.get(event, ())):
            owner_plugin = self.get(owner)
            if owner_plugin is not None and not self._effective_enabled(owner_plugin):
                continue
            try:
                callback(dict(payload))
            except Exception as exc:
                self._report(owner, "event:" + event, exc)

    def visible_plugins(self):
        return tuple(p for p in self.plugins
                     if bool(getattr(p, "manager_visible", False)))

    def build_main_actions(self, frame, parent):
        """Build plugin-declared toolbar actions; core never names a plugin."""
        from tkinter import ttk
        try:
            for child in frame.winfo_children():
                child.destroy()
        except Exception:
            return
        self.main_action_buttons = {}
        # V3.85.3: pasek pluginów zawija przyciski do kolejnej linii (BadgeFlow),
        # zamiast wypychać je poza okno.
        zawijany = callable(getattr(frame, "set_badges", None))
        przyciski = []
        for plugin in self.visible_plugins():
            text = str(getattr(plugin, "main_action_text", "") or "").strip()
            hook = str(getattr(plugin, "main_action_hook", "panel") or "panel")
            if not text:
                continue
            button = ttk.Button(frame, text=text,
                command=lambda n=plugin.nazwa, h=hook:
                    self.call_one(n, h, parent))
            if not zawijany:
                button.pack(side="left", padx=(0, 6))
            przyciski.append(button)
            self.main_action_buttons[plugin.nazwa] = button
            self._refresh_main_action(plugin.nazwa)
        if zawijany:
            frame.set_badges(przyciski)

    def _refresh_main_action(self, name):
        plugin = self.get(name); button = self.main_action_buttons.get(name)
        if plugin is None or button is None:
            return
        requires = bool(getattr(plugin, "main_action_requires_enabled", False))
        enabled = self._effective_enabled(plugin)
        try:
            button.configure(state="normal" if (enabled or not requires) else "disabled")
        except Exception:
            pass

    def plugin_info(self, plugin):
        return {
            "name": str(getattr(plugin, "manager_name", plugin.nazwa)),
            "version": str(getattr(plugin, "version", "—")),
            "description": str(getattr(plugin, "manager_description", "")),
            "required": bool(getattr(plugin, "required", False)),
            "panel": callable(getattr(plugin, "panel", None)),
            "panel_available_when_off": bool(
                getattr(plugin, "panel_available_when_off", False)),
            "enabled": self._effective_enabled(plugin),
        }

    def update_status(self, name, text, color="#555555"):
        self.runtime_status[name] = (str(text), color)
        self._refresh_manager_row(name)

    def _refresh_manager_row(self, name):
        row = self.manager_rows.get(name)
        plugin = self.get(name)
        self._refresh_main_action(name)
        if not row or plugin is None:
            return
        try:
            info = self.plugin_info(plugin)
            text, color = self.runtime_status.get(name, (t("URUCHOMIONY", "RUNNING"), "#207020"))
            row["status"].configure(text=text, foreground=color)
            if row.get("on_button") is not None:
                # Dwa prawdziwe przyciski, nie miniaturowy Checkbutton udający
                # sterowanie ON/OFF. Nieaktywny przycisk pokazuje bieżący stan.
                row["on_button"].configure(
                    state="disabled" if info["enabled"] else "normal")
                row["off_button"].configure(
                    state="normal" if info["enabled"] else "disabled")
            panel_button = row.get("panel_button")
            if panel_button is not None:
                available = (info["required"] or info["enabled"] or
                             info["panel_available_when_off"])
                panel_button.configure(state="normal" if available else "disabled")
            diagnostic_button = row.get("diagnostic_button")
            if diagnostic_button is not None:
                # Wyłączony plugin nie pracuje, więc automatyczne/ręczne
                # diagnozowanie jego funkcji nie ma sensu i daje mylący wynik.
                eligible = self._diagnostic_eligible(plugin)
                diagnostic_button.configure(
                    state="normal" if eligible else "disabled")
                if not eligible:
                    self.last_diagnostics.pop(name, None)
                    row["test"].configure(text="—", foreground="#777777")
        except Exception:
            pass
        self._refresh_main_action(name)

    def set_enabled_from_manager(self, name, enabled):
        plugin = self.get(name)
        if plugin is None or bool(getattr(plugin, "required", False)):
            return
        try:
            if enabled:
                # For legacy plugins start() runs while durable state is still OFF;
                # they must therefore load dormant, then set_enabled(True) activates.
                self._activate_plugin(plugin)
                self.call_one(name, "set_enabled", True)
            else:
                self.call_one(name, "set_enabled", False)
                deactivate = getattr(plugin, "deactivate", None)
                if callable(deactivate):
                    deactivate()
                self._active.discard(name)
        except Exception as exc:
            self._report(name, "set_enabled", exc)
        self._refresh_manager_row(name)
        self.run_tests(name)

    def test_one(self, name):
        plugin = self.get(name)
        if plugin is None:
            return {"level": "error", "text": t("NIE ZAŁADOWANO", "NOT LOADED")}
        try:
            if getattr(plugin, "API", None) != PLUGIN_API:
                raise RuntimeError(t("niezgodne API", "incompatible API"))
            if not getattr(plugin, "nazwa", ""):
                raise RuntimeError(t("brak nazwy", "no name"))
            fn = getattr(plugin, "self_test", None)
            result = fn() if callable(fn) else {"ok": True, "details": t("struktura i start OK",
                                                                         "structure and start OK")}
            if result is False:
                raise RuntimeError(t("self-test zwrócił wynik negatywny", "self-test returned a negative result"))
            if isinstance(result, dict) and not result.get("ok", True):
                return {"level": "warning",
                        "text": t("OSTRZEŻENIE: ", "WARNING: ") + str(result.get("details", ""))}
            details = result.get("details", "") if isinstance(result, dict) else str(result or "")
            # To jest wyłącznie bezpieczna diagnostyka techniczna. Nie wolno
            # przedstawiać jej jako testu funkcjonalnego: większość pluginów
            # celowo nie wykonuje tu importu, zapisu, RCON ani zmiany CPU.
            text = t("DOSTĘPNY", "AVAILABLE")
            if details:
                text += " — " + details
            text += t(" — NIE POTWIERDZA PEŁNEGO DZIAŁANIA", " — DOES NOT CONFIRM FULL OPERATION")
            return {"level": "info", "text": text}
        except Exception as exc:
            self._report(name, "self_test", exc)
            return {"level": "error", "text": t("BŁĄD — ", "ERROR — ") + str(exc)}

    def run_startup_diagnostics(self):
        """Run the safe technical diagnostics once after process startup."""
        if self._startup_diagnostics_done:
            return dict(self.last_diagnostics)
        self._startup_diagnostics_done = True
        self.app.log(t("[DIAGNOSTYKA PLUGINÓW] Automatyczna kontrola po starcie.",
                       "[PLUGIN DIAGNOSTICS] Automatic check after startup."),
                     "plugin_test")
        return self.run_tests()

    def run_language_change_diagnostics(self):
        """A rebuilt UI/plugin start is a new lifecycle and must be checked again."""
        # Jeżeli język zmieniono w pierwszych 3 sekundach, pierwotny timer
        # startowy nadal istnieje. Oznaczenie kontroli jako wykonanej zapobiega
        # drugiemu, spóźnionemu przebiegowi chwilę po kontroli językowej.
        self._startup_diagnostics_done = True
        self.app.log(t("[DIAGNOSTYKA PLUGINÓW] Ponowna kontrola po zmianie języka.",
                       "[PLUGIN DIAGNOSTICS] Re-check after the language change."),
                     "plugin_test")
        return self.run_tests()

    def _diagnostic_eligible(self, plugin):
        """Only required or effectively ON plugins may be diagnosed."""
        return self._effective_enabled(plugin)

    def run_tests(self, only=None):
        requested = [self.get(only)] if only else list(self.visible_plugins())
        targets = []
        results = {}
        for plugin in requested:
            if plugin is None:
                continue
            if not self._diagnostic_eligible(plugin):
                # OFF oznacza brak działania i brak diagnostyki. Nie dokładamy
                # zbędnego komunikatu o pominięciu; pole pozostaje puste.
                self.last_diagnostics.pop(plugin.nazwa, None)
                row = self.manager_rows.get(plugin.nazwa)
                if row:
                    try:
                        row["test"].configure(text="—", foreground="#777777")
                    except Exception:
                        # The language rebuild destroys Tk children before a delayed
                        # diagnostic callback can observe them. Stale presentation
                        # objects must never abort the diagnostic lifecycle.
                        self.manager_rows.pop(plugin.nazwa, None)
                continue
            targets.append(plugin)
        for plugin in targets:
            result = self.test_one(plugin.nazwa)
            results[plugin.nazwa] = result
            self.last_diagnostics[plugin.nazwa] = dict(result)
            color = {"info": "#005a9c", "warning": "#b07000"}.get(result["level"], "#b00020")
            row = self.manager_rows.get(plugin.nazwa)
            if row:
                try:
                    row["test"].configure(text=result["text"], foreground=color)
                except Exception:
                    pass
            log_tag = "plugin_test" if result["level"] == "info" else (
                "cpu_wait" if result["level"] == "warning" else "warn")
            self.app.log(t("[DIAGNOSTYKA PLUGINU] %s: %s", "[PLUGIN DIAGNOSTICS] %s: %s") %
                         (plugin.nazwa, result["text"]), log_tag)
        return results

    def open_manager(self, parent):
        import tkinter as tk
        from tkinter import ttk
        try:
            if self.manager_window and self.manager_window.winfo_exists():
                self.manager_window.deiconify(); self.manager_window.lift(); return
        except Exception:
            pass
        win = tk.Toplevel(parent)
        self.manager_window = win
        win.title(t("Manager Pluginów", "Plugin Manager"))
        win.geometry("860x540")
        win.minsize(720, 400)
        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)

        title = ttk.Frame(outer)
        title.pack(fill="x", pady=(0, 12))
        ttk.Label(title, text=t("MANAGER PLUGINÓW", "PLUGIN MANAGER"),
                  font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(title,
                  text=t("Sterowanie i panele pluginów. Diagnostyka sprawdza tylko załadowanie/API/"
                         "bezpieczny odczyt — nie potwierdza pełnego działania.",
                         "Plugin control and panels. Diagnostics only check loading/API/safe "
                         "reading — they do not confirm full operation."),
                  foreground="#666666", wraplength=820).pack(anchor="w", pady=(3, 0))
        ttk.Label(title,
                  text=t("ON = plugin aktywny. OFF = brak pracy w tle; ustawienia pozostają zapisane. "
                         "PANEL może służyć do konfiguracji lub ręcznej operacji.",
                         "ON = plugin active. OFF = no background work; settings stay saved. "
                         "PANEL is for configuration or a manual operation."),
                  foreground="#555555", font=("TkDefaultFont", 8)).pack(anchor="w", pady=(1, 0))

        # Canvas keeps the manager useful when more plugins are added later.
        canvas_box = ttk.Frame(outer)
        canvas_box.pack(fill="both", expand=True)
        canvas = tk.Canvas(canvas_box, highlightthickness=0, background="#f4f5f7")
        scrollbar = ttk.Scrollbar(canvas_box, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(canvas, padding=3)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(body_id, width=e.width))

        self.manager_rows = {}
        plugins = self.visible_plugins()
        if not plugins:
            ttk.Label(body, text=t("Brak pluginów użytkowych.", "No user plugins."), padding=24).pack(fill="x")
        for plugin in plugins:
            info = self.plugin_info(plugin)
            # Truly compact card: one header/action row, description, one status/test row.
            card = ttk.Frame(body, padding=(5, 3), relief="solid", borderwidth=1)
            card.pack(fill="x", pady=1)
            card.columnconfigure(0, weight=1)

            header = ttk.Frame(card)
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(0, weight=1)
            identity = ttk.Frame(header)
            identity.grid(row=0, column=0, sticky="w")
            ttk.Label(identity, text=info["name"],
                      font=("TkDefaultFont", 9, "bold")).pack(side="left")
            ttk.Label(identity, text="v" + info["version"], foreground="#666666",
                      font=("TkDefaultFont", 7)).pack(side="left", padx=(5, 0))
            type_text = t("KONIECZNY", "REQUIRED") if info["required"] else t("OPCJONALNY", "OPTIONAL")
            type_color = "#7a4d00" if info["required"] else "#365f91"
            ttk.Label(identity, text=type_text, foreground=type_color,
                      font=("TkDefaultFont", 7, "bold")).pack(side="left", padx=(7, 0))

            actions = ttk.Frame(header)
            actions.grid(row=0, column=1, sticky="e", padx=(8, 0))
            on_button = off_button = None
            if not info["required"]:
                on_button = ttk.Button(
                    actions, text="ON", width=4,
                    command=lambda n=plugin.nazwa:
                        self.set_enabled_from_manager(n, True))
                off_button = ttk.Button(
                    actions, text="OFF", width=4,
                    command=lambda n=plugin.nazwa:
                        self.set_enabled_from_manager(n, False))
                on_button.pack(side="left", padx=(0, 2))
                off_button.pack(side="left", padx=(0, 4))
            else:
                ttk.Label(actions, text=t("ZAWSZE ON", "ALWAYS ON"), foreground="#555555",
                          font=("TkDefaultFont", 7)).pack(side="left", padx=(0, 4))
            panel_button = None
            if info["panel"]:
                panel_button = ttk.Button(
                    actions, text="PANEL",
                    command=lambda n=plugin.nazwa: self.open_panel(n, win))
                panel_button.pack(side="left", padx=(0, 3))
            diagnostic_button = ttk.Button(
                actions, text=t("DIAGNOSTYKA", "DIAGNOSTICS"),
                command=lambda n=plugin.nazwa: self.run_tests(n))
            diagnostic_button.pack(side="left")

            if info["description"]:
                ttk.Label(card, text=info["description"], foreground="#555555",
                          wraplength=760, justify="left", font=("TkDefaultFont", 8)).grid(
                              row=1, column=0, sticky="ew", pady=(1, 0))

            meta = ttk.Frame(card)
            meta.grid(row=2, column=0, sticky="ew", pady=(1, 0))
            ttk.Label(meta, text="STATUS", font=("TkDefaultFont", 7, "bold")).pack(side="left")
            status = ttk.Label(meta, text="—", font=("TkDefaultFont", 8))
            status.pack(side="left", padx=(4, 14))
            ttk.Label(meta, text=t("DIAGNOSTYKA TECHNICZNA", "TECHNICAL DIAGNOSTICS"),
                      font=("TkDefaultFont", 7, "bold")).pack(side="left")
            test = ttk.Label(meta, text=t("Nie wykonano — to nie jest test funkcjonalny",
                                          "Not run — this is not a functional test"), foreground="#666666",
                             wraplength=500, justify="left", font=("TkDefaultFont", 8))
            test.pack(side="left", padx=(4, 0), fill="x", expand=True)

            self.manager_rows[plugin.nazwa] = {
                "status": status, "test": test,
                "on_button": on_button, "off_button": off_button,
                "panel_button": panel_button,
                "diagnostic_button": diagnostic_button}
            self._refresh_manager_row(plugin.nazwa)
            previous = self.last_diagnostics.get(plugin.nazwa)
            if previous:
                color = {"info": "#005a9c", "warning": "#b07000"}.get(
                    previous.get("level"), "#b00020")
                test.configure(text=previous.get("text", "—"), foreground=color)

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text=t("DIAGNOSTYKA TECHNICZNA AKTYWNYCH", "TECHNICAL DIAGNOSTICS OF ACTIVE PLUGINS"),
                   command=self.run_tests).pack(side="left")
        ttk.Button(bottom, text=t("ZAMKNIJ", "CLOSE"), command=win.destroy).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def stop_all(self):
        for plugin in reversed(self.plugins):
            if plugin.nazwa not in self._prepared:
                continue
            fn = getattr(plugin, "stop", None)
            if fn:
                try:
                    fn()
                except Exception as exc:
                    self._report(plugin.nazwa, "stop", exc)
        self._active.clear()
        self._prepared.clear()
        self._off_reconciled.clear()
        # Every language rebuild destroys all Tk widgets owned by the old tree.
        # Do not retain labels/buttons/windows that Tcl has already deleted.
        self.manager_window = None
        self.manager_rows.clear()
        self.main_action_buttons.clear()
