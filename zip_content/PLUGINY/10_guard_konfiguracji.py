# -*- coding: utf-8 -*-
"""Read-only configuration guard. Enabled by default."""
import os

from asaonly.jezyk import t


class Wtyczka:
    nazwa="guard_konfiguracji"
    API=1
    TR={}
    manager_visible=True
    version="1.1.0"
    required=True

    @property
    def manager_name(self):
        return t("Guard konfiguracji", "Configuration guard")

    @property
    def manager_description(self):
        return t("Kontroluje spójność aktywnych map: porty RCON, katalogi logów "
                 "i podstawowe błędy konfiguracji.",
                 "Checks that active maps are consistent: RCON ports, log folders "
                 "and basic configuration errors.")

    def __init__(self):
        self.core=None; self.last_signature=None; self.next_check=0

    def start(self, rdzen):
        self.core=rdzen

    def tik(self, teraz):
        if teraz < self.next_check: return
        self.next_check=teraz+30
        tabs=self.core.tabs(); problems=[]; ports={}; logs={}
        for tab in tabs.values():
            if not tab.enabled: continue
            port=tab.rcon_port.strip()
            if not port.isdecimal() or not 1 <= int(port) <= 65535:
                problems.append(t("%s: nieprawidłowy port RCON %r", "%s: invalid RCON port %r") % (tab.name,port))
            else: ports.setdefault(port,[]).append(tab.name)
            path=os.path.normcase(os.path.normpath(tab.log_path.strip())) if tab.log_path.strip() else ""
            if not path: problems.append(t("%s: brak folderu logu", "%s: log folder missing") % tab.name)
            else: logs.setdefault(path,[]).append(tab.name)
        for port,names in ports.items():
            if len(names)>1:
                problems.append(t("port RCON %s współdzielą: %s", "RCON port %s is shared by: %s")
                                % (port,", ".join(names)))
        for path,names in logs.items():
            if len(names)>1:
                problems.append(t("folder logu współdzielą: %s", "log folder is shared by: %s")
                                % ", ".join(names))
        signature=tuple(sorted(problems))
        if signature != self.last_signature:
            if problems:
                self.core.warn("[GUARD CONFIG]\n"+"\n".join("- "+x for x in problems))
            elif self.last_signature:
                self.core.log(t("[GUARD CONFIG] konfiguracja aktywnych map jest spójna",
                                "[GUARD CONFIG] active map configuration is consistent"))
            self.last_signature=signature

    def konfiguracja(self): return {}
    def stop(self): pass
