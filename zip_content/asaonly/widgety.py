# -*- coding: utf-8 -*-
"""Reusable Tk widgets. They own presentation only, not cluster state."""
import tkinter as tk
from tkinter import ttk

class Led(tk.Canvas):
    def __init__(self, master, size=14, color="#505050"):
        super().__init__(master, width=size, height=size,
                         highlightthickness=0, bd=0)
        self._size = size
        self._item = self.create_oval(1.5, 1.5, size - 1.5, size - 1.5,
                                      fill=color, outline="#404040")

    def set_color(self, color):
        try:
            self.itemconfigure(self._item, fill=color)
        except Exception:
            pass

class ToolTip:
    def __init__(self, widget, text, delay_ms=450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _e):
        if self._after_id is None:
            self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _e):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._hide()

    def _show(self):
        self._after_id = None
        try:
            if not self.widget.winfo_exists():
                return
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.attributes("-topmost", True)
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 18
            self._tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self._tip, text=self.text, justify="left",
                     bg="#232936", fg="#e8eaf0",
                     font=("TkDefaultFont", 8), padx=8, pady=4,
                     wraplength=360).pack()
        except Exception:
            pass

    def _hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

class ModTile(tk.Frame):
    """3.40 "To tylko okno": kafelek moda ze ZWYKŁYCH widżetów.

    Zero ręcznej geometrii (poprzednie podejścia 3.34-3.39 rysowały tekst
    w Canvasie i ręcznie liczyły piksele - to bylo zrodlo ucinania kafelkow).
    Szerokosc kafelka zawsze pochodzi od rodzica (pack fill="x"); nazwa i
    linia informacji zawijaja sie SAME (wraplength podaza za wlasnym
    <Configure>). Nic nie jest mierzone recznie, wiec nic nie moze wystawac
    poza kafelek - tryb awarii strukturalnie nie istnieje.
    """

    BORDER = "#80d0f8"

    def __init__(self, master, app, mid):
        super().__init__(master, bg="#ffffff",
                         highlightbackground=self.BORDER,
                         highlightthickness=2)
        self.app = app
        self.mid = mid

        row1 = tk.Frame(self, bg="#ffffff")
        row1.pack(fill="x", padx=8, pady=(6, 0))
        self.led = Led(row1, size=12)
        self.led.pack(side="left", padx=(0, 6))
        self.lbl_name = tk.Label(row1, text="", bg="#ffffff", anchor="w",
                                 justify="left",
                                 font=("TkDefaultFont", 9, "bold"))
        self.lbl_name.pack(side="left", fill="x", expand=True)
        self.lbl_state = tk.Label(row1, text="", bg="#ffffff",
                                  font=("TkDefaultFont", 8, "bold"))
        self.lbl_state.pack(side="left", padx=(6, 8))
        self.var_mon = tk.BooleanVar(value=mid not in app.monitor_off)
        self.chk_mon = tk.Checkbutton(row1, text=app.tr("mod_monitor"),
                                      variable=self.var_mon, bg="#ffffff",
                                      activebackground="#ffffff",
                                      font=("TkDefaultFont", 8),
                                      command=self._toggle_monitor,
                                      cursor="hand2")
        self.chk_mon.pack(side="left")
        self.btn_open = ttk.Button(row1, text=app.tr("mod_page_btn"),
                                   command=lambda: app.open_mod_page(mid))
        self.btn_open.pack(side="left", padx=(6, 0))

        self.lbl_info = tk.Label(self, text="", bg="#ffffff", anchor="w",
                                 justify="left", font=("TkDefaultFont", 8),
                                 foreground="#444444", wraplength=300)
        self.lbl_info.pack(fill="x", padx=8, pady=(2, 6))

        # JEDyny trik geometryczny w calym kafelku: wraplength = biezaca
        # szerokosc etykiety (geometria plynie z rodzica, nigdy odwrotnie).
        for lbl in (self.lbl_name, self.lbl_info):
            lbl.bind(
                "<Configure>",
                lambda e, l=lbl: l.configure(wraplength=max(50, e.width - 2)))

        self.refresh()

    def refresh(self):
        app = self.app
        mid = self.mid
        off = mid in app.monitor_off
        st = app.mod_states.get(mid, "wait")
        name = app.mod_names.get(mid) or f"Mod {mid}"
        known = app.known_versions.get(mid) or "—"
        latest = app.mod_latest.get(mid)
        latest_txt = latest["fid"] if latest else "—"
        if off:
            st_text, st_color = app.tr("mods_state_off"), "#999999"
        else:
            st_text, st_color = app._mod_state_ui(st, mid)
        maps = app._tabs_for_mod(mid)

        self.lbl_name.configure(text=name)
        self.lbl_state.configure(text=st_text, foreground=st_color)
        self.led.set_color(st_color)
        parts = [f"{app.tr('tile_id')}: {mid}",
                 f"{app.tr('tile_known')}: {known}",
                 f"{app.tr('tile_latest')}: {latest_txt}"]
        if maps:
            parts.append(f"{app.tr('tile_maps')}: {', '.join(maps)}")
        self.lbl_info.configure(text=" · ".join(parts))
        self.var_mon.set(mid not in app.monitor_off)

    def _toggle_monitor(self):
        try:
            app = self.app
            if self.var_mon.get():
                app.monitor_off.discard(self.mid)
            else:
                app.monitor_off.add(self.mid)
            app.mod_states.pop(self.mid, None)
            self.refresh()
            app.request_save()
        except Exception:
            pass

class ModBadge(tk.Label):
    """3.42 "Dioda = numer moda": chip (Label) z kolorem stanu i numerem moda.

    Poprzedni patent (Canvas 36x36 z kolkiem i tekstem) mial dwa grzechy:
    kolor stanu czytany RAZ przy tworzeniu (diody wygladaly na martwe)
    i canvas tam, gdzie wystarczy Label. Teraz: numer moda NA kolorze stanu,
    odswiezany metoda refresh() przy kazdej zmianie stanu.
    """
    def __init__(self, master, app, mid, map_name=None):
        self.app = app
        self.mid = mid
        self.map_name = map_name
        super().__init__(master, text=mid, font=("TkDefaultFont", 9, "bold"),
                         fg="#ffffff", padx=7, pady=2, cursor="hand2",
                         highlightthickness=0, bd=0)
        self.bind("<Button-1>", lambda e: app.open_mod_page(mid))
        self._tt = None
        self.refresh()

    def refresh(self):
        try:
            app = self.app
            state = app._badge_state(self.mid, self.map_name)
            st_text, color = app._mod_state_ui(state, self.mid)
            self.configure(bg=color)
            name = app.mod_names.get(self.mid, "?")
            latest = app.mod_latest.get(self.mid)
            tip = "%s - %s\n%s" % (self.mid, name, st_text)
            if latest:
                tip += "\n%s: %s" % (app.tr("tile_latest"), latest.get("fid", "—"))
            tip += "\n%s" % app.tr("badge_click")
            if self._tt is None:
                self._tt = ToolTip(self, tip)
            else:
                self._tt.text = tip
        except Exception:
            pass

class BadgeFlow(tk.Frame):
    """3.44: kontener diod modow, ktory SAM zawija do kolejnych linii.
    Diody (chipy z numerami modow) ukladaja sie od lewej; gdy w biezacej
    szerokosci nie miesci sie kolejna - przechodza do nastepnej linii.
    Rozciaganie/kurczenie okna przelicza uklad na nowo (<Configure>).
    """
    def __init__(self, master):
        super().__init__(master)
        self._order = []
        self._after = None
        self.bind("<Configure>", self._on_cfg)

    def set_badges(self, badges):
        for w in self.winfo_children():
            try:
                w.grid_forget()
            except Exception:
                pass
        self._order = list(badges)
        self._relayout()

    def _on_cfg(self, _e):
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.after(60, self._relayout)

    def _relayout(self):
        self._after = None
        try:
            w = self.winfo_width()
            if w <= 1:
                w = self.winfo_reqwidth() or 300
            row, col, x = 0, 0, 0
            for b in self._order:
                bw = (b.winfo_reqwidth() or 60) + 5  # 5 = padx pomiedzy
                if col > 0 and x + bw > w:
                    row += 1
                    col = 0
                    x = 0
                b.grid(row=row, column=col, sticky="w",
                       padx=(0, 5), pady=(0, 3))
                x += bw
                col += 1
        except Exception:
            pass
