# -*- coding: utf-8 -*-
"""Warns about version-state contradictions without changing any state."""

from asaonly.jezyk import t


class Wtyczka:
    nazwa="audyt_wersji"
    API=1
    TR={}
    manager_visible=True
    version="1.1.0"
    required=True

    @property
    def manager_name(self):
        return t("Audyt wersji modów", "Mod version audit")

    @property
    def manager_description(self):
        return t("Wykrywa sprzeczności w zapamiętanych, oczekujących i odczytanych "
                 "z serwerów wersjach modów; nie zmienia wersji.",
                 "Detects contradictions between stored, pending and server-reported "
                 "mod versions; does not change versions.")

    def __init__(self): self.core=None; self.next_check=0; self.last=None
    def start(self,rdzen): self.core=rdzen

    def tik(self,teraz):
        if teraz < self.next_check: return
        self.next_check=teraz+30
        data=self.core.mods(); problems=[]
        for pending in data["pending"]:
            mid=pending.get("mid",""); targets=set(pending.get("targets",[])); verified=set(pending.get("verified",[]))
            if not mid: problems.append(t("pending bez mod_id", "pending without mod_id"))
            if verified-targets:
                problems.append(t("mod %s: verified poza targets: %s",
                                  "mod %s: verified outside targets: %s")%(mid,sorted(verified-targets)))
            if not targets:
                problems.append(t("mod %s: pending bez map docelowych", "mod %s: pending without target maps")%mid)
        for map_name, versions in data["server_observed"].items():
            for mid,fid in versions.items():
                if not str(mid).isdigit() or not str(fid).isdigit():
                    problems.append(t("%s: nieprawidłowa para wersji %r/%r",
                                      "%s: invalid version pair %r/%r")%(map_name,mid,fid))
        signature=tuple(sorted(problems))
        if signature != self.last:
            if problems: self.core.warn(t("[AUDYT WERSJI]\n", "[VERSION AUDIT]\n")+"\n".join("- "+x for x in problems))
            elif self.last: self.core.log(t("[AUDYT WERSJI] brak sprzeczności", "[VERSION AUDIT] no contradictions"))
            self.last=signature

    def konfiguracja(self): return {}
    def stop(self): pass
