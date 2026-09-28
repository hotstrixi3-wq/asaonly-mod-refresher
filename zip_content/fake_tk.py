"""Fake tkinter for headless testing - improved"""
import sys
import types
tk_module = types.ModuleType('tkinter')
class FakeBase:
    def __init__(self, *a, **kw): 
        self._children = []
        self._config = {}
        self._text = ""
        self._items = []
    def withdraw(self): pass
    def destroy(self): pass
    def after(self, *a, **kw): return 1
    def after_cancel(self, *a, **kw): pass
    def winfo_exists(self): return True
    def pack(self, *a, **kw): pass
    def grid(self, *a, **kw): pass
    def place(self, *a, **kw): pass
    def config(self, *a, **kw): self._config.update(kw)
    def configure(self, *a, **kw): self._config.update(kw)
    def cget(self, key): return self._config.get(key, "")
    def bind(self, *a, **kw): pass
    def winfo_children(self): return self._children
    def get_children(self, *a, **kw):
        cnt = self.__dict__.get('_gc_cnt', 0)
        self.__dict__['_gc_cnt'] = cnt + 1
        if cnt < 2:
            return ()
        return ("id1","id2")
    def item(self, *a, **kw):
        if len(a)>=2 and a[1]=="values":
            if a[0]=="id1":
                return ("Ragnarok","pusta","—","0:00","120")
            return ("Extinction","pusta","—","2:00","120")
        return {"values": ("Ragnarok","pusta","—","0:00","120")}
    def yview(self, *a, **kw): pass
    def title(self, *a, **kw): pass
    def geometry(self, *a, **kw): pass
    def resizable(self, *a, **kw): pass
    def protocol(self, *a, **kw): pass
    def deiconify(self): pass
    def lift(self): pass
    def focus_set(self): pass
    def update(self): pass
    def update_idletasks(self): pass
    def mainloop(self, *a, **kw): pass
    def quit(self): pass
    def minsize(self, *a, **kw): pass
    def maxsize(self, *a, **kw): pass
    def add(self, *a, **kw): 
        if a:
            self._children.append(a[0])
    def insert(self, *a, **kw):
        if len(a) >= 2:
            self._text += str(a[1])
            self._items.append(a[1])
        elif a:
            self._text += str(a[0])
            self._items.append(a[0])
    def delete(self, *a, **kw): 
        self._text = ""
        self._items = []
    def get(self, *a, **kw): 
        return self._text if self._text else ""
    def set(self, *a, **kw): pass
    def selection_set(self, *a, **kw): pass
    def heading(self, *a, **kw): pass
    def column(self, *a, **kw): pass
    def tag_configure(self, *a, **kw): pass
    def __getitem__(self, key): return self._config.get(key)
    def __setitem__(self, key, value): self._config[key] = value
    def __getattr__(self, name):
        def _noop(*a, **kw):
            if name == 'get':
                return self._text
            if name == 'get_children':
                return ()
            return None
        return _noop
class FakeTk(FakeBase): pass
class FakeWidget(FakeBase): pass
class FakeVar:
    def __init__(self, *a, **kw): 
        self._val = kw.get('value', '' if 'String' in str(type(self)) else 0)
    def get(self): return self._val
    def set(self, v): self._val = v
    def trace_add(self, *a, **kw): return "trace_id"
    def trace_remove(self, *a, **kw): pass
    def trace(self, *a, **kw): pass
def make_var(default):
    class V(FakeVar):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            if 'value' not in kw:
                self._val = default
    return V
tk_module.Tk = FakeTk
tk_module.Frame = FakeWidget
tk_module.Label = FakeWidget
tk_module.Button = FakeWidget
tk_module.Entry = FakeWidget
tk_module.Text = FakeWidget
tk_module.Scrollbar = FakeWidget
tk_module.Canvas = FakeWidget
tk_module.Listbox = FakeWidget
tk_module.Menu = FakeWidget
tk_module.Toplevel = FakeTk
tk_module.Checkbutton = FakeWidget
tk_module.Radiobutton = FakeWidget
tk_module.Scale = FakeWidget
tk_module.Spinbox = FakeWidget
tk_module.PanedWindow = FakeWidget
tk_module.LabelFrame = FakeWidget
tk_module.StringVar = make_var("")
tk_module.IntVar = make_var(0)
tk_module.BooleanVar = make_var(False)
tk_module.DoubleVar = make_var(0.0)
ttk_module = types.ModuleType('tkinter.ttk')
for name in ["Frame", "Label", "Button", "Entry", "Combobox", "Notebook", "Treeview", "Scrollbar", "Progressbar", "Style", "Separator", "Checkbutton", "Radiobutton", "LabelFrame", "PanedWindow", "Scale"]:
    setattr(ttk_module, name, FakeWidget)
messagebox_module = types.ModuleType('tkinter.messagebox')
messagebox_module.showinfo = lambda *a, **kw: None
messagebox_module.showwarning = lambda *a, **kw: None
messagebox_module.showerror = lambda *a, **kw: None
messagebox_module.askyesno = lambda *a, **kw: False
messagebox_module.askokcancel = lambda *a, **kw: False
messagebox_module.askquestion = lambda *a, **kw: "no"
messagebox_module.askretrycancel = lambda *a, **kw: False
filedialog_module = types.ModuleType('tkinter.filedialog')
filedialog_module.askopenfilename = lambda *a, **kw: ""
filedialog_module.asksaveasfilename = lambda *a, **kw: ""
filedialog_module.askdirectory = lambda *a, **kw: ""
simpledialog_module = types.ModuleType('tkinter.simpledialog')
simpledialog_module.askstring = lambda *a, **kw: None
simpledialog_module.askinteger = lambda *a, **kw: None
simpledialog_module.askfloat = lambda *a, **kw: None
tk_module.END = "end"
tk_module.BOTH = "both"
tk_module.LEFT = "left"
tk_module.RIGHT = "right"
tk_module.TOP = "top"
tk_module.BOTTOM = "bottom"
tk_module.X = "x"
tk_module.Y = "y"
tk_module.W = "w"
tk_module.E = "e"
tk_module.N = "n"
tk_module.S = "s"
tk_module.CENTER = "center"
tk_module.HORIZONTAL = "horizontal"
tk_module.VERTICAL = "vertical"
tk_module.DISABLED = "disabled"
tk_module.NORMAL = "normal"
tk_module.WORD = "word"
tk_module.CHAR = "char"
import sys
sys.modules['tkinter'] = tk_module
sys.modules['tkinter.ttk'] = ttk_module
sys.modules['tkinter.messagebox'] = messagebox_module
sys.modules['tkinter.filedialog'] = filedialog_module
sys.modules['tkinter.simpledialog'] = simpledialog_module
tk_module.ttk = ttk_module
tk_module.messagebox = messagebox_module
tk_module.filedialog = filedialog_module
tk_module.simpledialog = simpledialog_module
