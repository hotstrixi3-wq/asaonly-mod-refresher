# -*- coding: utf-8 -*-
import json
import os
import platform
import re
import time
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from asaonly.jezyk import t


SENSITIVE_KEYS = ("password", "passwd", "token", "secret", "api_key", "apikey",
                  "authorization", "credential", "rcon_pass")


class Wtyczka:
    nazwa="diagnostyka_zip"; API=1; TR={}; manager_visible=True
    version="1.2.0"; required=False
    @property
    def manager_name(self): return t("Pakiet diagnostyczny","Diagnostic package")
    @property
    def manager_description(self):
        return t("Tworzy na żądanie ZIP diagnostyczny. Rekursywnie redaguje wrażliwe "
                 "klucze JSON i typowe sekrety w logach; dołącza manifest zawartości.",
                 "Creates a diagnostic ZIP on demand. Recursively redacts sensitive "
                 "JSON keys and common secrets in logs; includes a content manifest.")
    def __init__(self): self.core=None; self.enabled=False
    def prepare(self,core):
        self.core=core; self.enabled=bool(core.plugin_config(self.nazwa).get("enabled",False)); self._publish()
    def _publish(self):
        self.core.set_indicator(self.nazwa,t("ON — gotowy","ON — ready") if self.enabled else "OFF",
                                "#207020" if self.enabled else "#555555")
    def start(self, core):
        self.prepare(core)

    def is_enabled(self): return self.enabled
    def set_enabled(self,value):
        self.enabled=bool(value); self.core.save_plugin_config(self.nazwa,{"enabled":self.enabled})
        self._publish(); self.core.set_plugin_toggle(self.nazwa,self.enabled)
    def self_test(self):
        return {"ok":True,"details":t("redaktor i generator ZIP dostępne; bez odczytu plików",
                                      "redactor and ZIP generator available; no files read")}

    @staticmethod
    def _redact_json(value):
        if isinstance(value,dict):
            result={}
            for key,item in value.items():
                low=str(key).lower().replace("-","_")
                result[key]="[REDACTED]" if any(mark in low for mark in SENSITIVE_KEYS) else Wtyczka._redact_json(item)
            return result
        if isinstance(value,list): return [Wtyczka._redact_json(x) for x in value]
        return value

    @staticmethod
    def _redact_text(text):
        patterns=(
            r"(?i)(password|passwd|token|secret|api[_ -]?key|authorization|rcon[_ -]?pass)(\s*[:=]\s*)([^\s,;]+)",
            r"(?i)(Bearer\s+)([A-Za-z0-9._~+/=-]+)",
        )
        for pattern in patterns:
            text=re.sub(pattern,lambda m:m.group(1)+m.group(2)+"[REDACTED]" if len(m.groups())>=3 else m.group(1)+"[REDACTED]",text)
        return text

    def panel(self,parent):
        if not self.enabled:
            messagebox.showwarning(t("Diagnostyka","Diagnostics"),
                                   t("Włącz plugin w Managerze.","Turn the plugin on in the Manager."),
                                   parent=parent); return
        win=tk.Toplevel(parent); win.title(self.manager_name); win.geometry("650x280")
        frame=ttk.Frame(win,padding=16); frame.pack(fill="both",expand=True)
        ttk.Label(frame,text=t("PAKIET DIAGNOSTYCZNY","DIAGNOSTIC PACKAGE"),
                  font=("TkDefaultFont",14,"bold")).pack(anchor="w")
        ttk.Label(frame,text=t("JSON i logi przechodzą redakcję. ZIP zawiera manifest dokładnie wskazujący "
                               "dołączone pliki.",
                               "JSON and logs are redacted. The ZIP contains a manifest listing exactly "
                               "which files are included."),wraplength=600).pack(anchor="w",pady=12)
        ttk.Button(frame,text=t("UTWÓRZ ZREDAGOWANY PAKIET ZIP","CREATE REDACTED ZIP PACKAGE"),
                   command=lambda:self._make(win)).pack(fill="x",pady=6)
        ttk.Button(frame,text=t("ZAMKNIJ","CLOSE"),command=win.destroy).pack(pady=10)

    def _make(self,parent):
        dst=filedialog.asksaveasfilename(parent=parent,defaultextension=".zip",
            initialfile="ASAonly-diagnostyka-%s.zip"%time.strftime("%Y%m%d-%H%M%S"),filetypes=[("ZIP","*.zip")])
        if not dst: return
        app=self.core.application(); tabs=self.core.tabs(); mods=self.core.mods(); host=app.plugin_host
        summary={"generated":time.strftime("%Y-%m-%d %H:%M:%S"),"system":platform.platform(),
                 "admin":self.core.is_admin(),
                 "maps":{name:{"enabled":tab.enabled,"port":tab.rcon_port,"log_path":tab.log_path,
                                      "status":tab.status,"mods":list(tab.mod_ids)} for name,tab in tabs.items()},
                 "mods":mods,"plugins":[{"name":p.nazwa,"version":getattr(p,"version","—"),
                    "enabled":bool(getattr(p,"is_enabled",lambda:True)())} for p in host.plugins]}
        base=os.path.dirname(os.path.dirname(__file__)); entries=[]
        with zipfile.ZipFile(dst,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostyka.json",json.dumps(self._redact_json(summary),ensure_ascii=False,indent=2,default=str)); entries.append("diagnostyka.json")
            for rel in ("WIEDZA_O_PROGRAMIE/asa_debug.log","WIEDZA_O_PROGRAMIE/dziennik-zdarzen.txt","PLUGINY/plugin-errors.log"):
                path=os.path.join(base,rel)
                if os.path.isfile(path):
                    with open(path,"r",encoding="utf-8",errors="replace") as handle: text=self._redact_text(handle.read())
                    archive.writestr(rel,text); entries.append(rel)
            cfg=os.path.join(base,"CONFIG_PROGRAM")
            if os.path.isdir(cfg):
                for filename in sorted(os.listdir(cfg)):
                    if not filename.endswith(".json"): continue
                    path=os.path.join(cfg,filename)
                    try:
                        with open(path,"r",encoding="utf-8-sig") as handle: data=json.load(handle)
                    except Exception: continue
                    rel="CONFIG_PROGRAM_BEZ_SEKRETOW/"+filename
                    archive.writestr(rel,json.dumps(self._redact_json(data),ensure_ascii=False,indent=2)); entries.append(rel)
            manifest={"generated":summary["generated"],"redaction":"recursive JSON keys + common log assignments",
                      "entries":entries,"excluded":["CONFIG_SECRET_API","CONFIG_SECRET_RCON"]}
            archive.writestr("MANIFEST.json",json.dumps(manifest,ensure_ascii=False,indent=2))
        self.core.log(t("[DIAGNOSTYKA] utworzono zredagowany pakiet %s",
                        "[DIAGNOSTICS] created redacted package %s")%dst,"plugin_ok")
        messagebox.showinfo(t("Diagnostyka","Diagnostics"),t("Utworzono:\n","Created:\n")+dst,parent=parent)
    def konfiguracja(self): return {"enabled":self.enabled}
    def stop(self): pass
