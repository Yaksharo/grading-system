"""UNP Grading System - desktop app (prototype v0.1).

Same design framework as the Advisee Document Filler: themed Tkinter,
system light/dark with toggle, font scaling, About dialog, custom
titlebar on Windows, native decorations on Linux, thread-safe workers,
lazy imports for fast startup.

Developed by Kuzikushiro Solutions (Kuzikushiro a.k.a Ezer)
"""
import os
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "UNP Grading System"
APP_VERSION = "0.1"
DEVELOPER = "Kuzikushiro a.k.a Ezer"

# lazy-loaded heavy modules
classlist_parser = None
storage = None
engine = None
exporter = None


def _load_engine():
    global classlist_parser, storage, engine, exporter
    if engine is None:
        import classlist_parser as _c
        import storage as _s
        import engine as _e
        import exporter as _x
        classlist_parser, storage, engine, exporter = _c, _s, _e, _x


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


try:
    import darkdetect
except ImportError:
    darkdetect = None

THEMES = {
    "light": {
        "bg": "#f6f8f6", "card": "#ffffff", "fg": "#1f2937",
        "muted": "#6b7280", "line": "#d6dbd6",
        "accent": "#14532d", "accent_fg": "#ffffff",
        "accent_hover": "#1c6b3a", "field": "#ffffff",
        "header": "#14532d", "header_fg": "#ffffff",
        "warn": "#b91c1c",
    },
    "dark": {
        "bg": "#161b18", "card": "#1f2621", "fg": "#e5e9e6",
        "muted": "#9aa39c", "line": "#3a423c",
        "accent": "#2f9e5b", "accent_fg": "#0b0f0c",
        "accent_hover": "#3cb96e", "field": "#262e28",
        "header": "#0f1512", "header_fg": "#e5e9e6",
        "warn": "#f87171",
    },
}


def system_theme():
    if darkdetect is not None:
        try:
            return "dark" if darkdetect.isDark() else "light"
        except Exception:
            pass
    return "light"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self._center_window(1180, 720)
        self.minsize(980, 620)

        self.cls = None          # current class dict
        self.cls_path = None
        self._save_job = None
        self._msgq = queue.Queue()
        self._poll_queue()
        self._custom_titlebar = sys.platform.startswith("win")
        self._is_zoomed = False
        self._normal_geometry = None
        self._drag_origin = None
        self.font_size = 11
        self.theme_name = system_theme()
        self._themed_plain = []

        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        try:
            self._mdl2 = "Segoe MDL2 Assets" in tkfont.families()
        except tk.TclError:
            self._mdl2 = False
        self._glyphs = ({"min": "\uE921", "max": "\uE922",
                         "restore": "\uE923", "close": "\uE8BB"}
                        if self._mdl2 else
                        {"min": "\u2500", "max": "\u25a1",
                         "restore": "\u25a1", "close": "\u2715"})
        self._set_app_icon()
        self._init_fonts()
        self._build_chrome()
        self.apply_theme()
        if self._custom_titlebar:
            self._enable_custom_titlebar()
        self.show_home()

    # ------------------------------------------------------------ chrome
    def _build_chrome(self):
        if self._custom_titlebar:
            tb = ttk.Frame(self, style="Header.TFrame")
            tb.pack(fill="x")
            ttk.Label(tb, text=f"  {APP_TITLE}",
                      style="HeaderSub.TLabel").pack(side="left", pady=4)
            ttk.Button(tb, text=self._glyphs["close"], width=5,
                       style="TitleClose.TButton",
                       command=self.destroy).pack(side="right", fill="y")
            self._btn_zoom = ttk.Button(tb, text=self._glyphs["max"],
                                        width=5, style="Title.TButton",
                                        command=self._toggle_zoom)
            self._btn_zoom.pack(side="right", fill="y")
            ttk.Button(tb, text=self._glyphs["min"], width=5,
                       style="Title.TButton",
                       command=self._minimize).pack(side="right", fill="y")
            for w in (tb, tb.winfo_children()[0]):
                w.bind("<ButtonPress-1>", self._start_move)
                w.bind("<B1-Motion>", self._do_move)
                w.bind("<Double-Button-1>", lambda e: self._toggle_zoom())

        header = ttk.Frame(self, style="Header.TFrame", padding=(16, 10))
        header.pack(fill="x")
        left = ttk.Frame(header, style="Header.TFrame")
        left.pack(side="left")
        ttk.Label(left, text=APP_TITLE,
                  style="Header.TLabel").pack(anchor="w")
        self.subtitle = ttk.Label(left, text="E-Class Record made easy",
                                  style="HeaderSub.TLabel")
        self.subtitle.pack(anchor="w")
        right = ttk.Frame(header, style="Header.TFrame")
        right.pack(side="right")
        ttk.Button(right, text="A-", width=3,
                   command=lambda: self.change_font(-1)).pack(side="left",
                                                              padx=2)
        ttk.Button(right, text="A+", width=3,
                   command=lambda: self.change_font(1)).pack(side="left",
                                                             padx=2)
        self.btn_theme = ttk.Button(right, command=self.toggle_theme)
        self.btn_theme.pack(side="left", padx=8)
        ttk.Button(right, text="About",
                   command=self.show_about).pack(side="left")

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=14, pady=10)

        self.statusbar = ttk.Label(self, text="", style="Muted.TLabel",
                                   padding=(16, 4))
        self.statusbar.pack(fill="x", side="bottom")
        if self._custom_titlebar:
            grip = ttk.Sizegrip(self.statusbar)
            grip.pack(side="right")

    def _clear_body(self):
        self._themed_plain = [w for w in self._themed_plain
                              if str(w[0]) .startswith(str(self))
                              and w[0].winfo_exists()]
        for w in self.body.winfo_children():
            w.destroy()
        self._themed_plain = []

    def status(self, text):
        self.statusbar.config(text=text)

    # ------------------------------------------------------- home screen
    def show_home(self):
        self._clear_body()
        self.subtitle.config(text="E-Class Record made easy")
        f = self.body
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="My Classes",
                  style="Step.TLabel").pack(side="left")
        ttk.Button(top, text="New Class from Class List PDF...",
                   style="Accent.TButton",
                   command=self._new_class).pack(side="right")

        cols = ("cls", "students")
        tree = ttk.Treeview(f, columns=cols, show="headings", height=14)
        tree.heading("cls", text="Class")
        tree.heading("students", text="Students")
        tree.column("cls", width=520)
        tree.column("students", width=90, anchor="center")
        tree.pack(fill="both", expand=True)
        self._home_tree = tree

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Open", style="Accent.TButton",
                   command=self._open_selected).pack(side="left")
        ttk.Button(btns, text="Delete",
                   command=self._delete_selected).pack(side="left", padx=8)
        tree.bind("<Double-Button-1>", lambda e: self._open_selected())

        def load():
            _load_engine()
            items = storage.list_classes()
            self._ui(lambda: self._fill_home(items))
        threading.Thread(target=load, daemon=True).start()
        self.status("Loading classes...")

    def _fill_home(self, items):
        self._home_items = items
        for it in self._home_tree.get_children():
            self._home_tree.delete(it)
        for i, it in enumerate(items):
            self._home_tree.insert("", "end", iid=str(i),
                                   values=(it["label"], it["students"]))
        self.status(f"{len(items)} class(es). Everything is saved "
                    f"automatically to {storage.data_dir()}")

    def _selected_item(self):
        sel = self._home_tree.selection()
        if not sel:
            messagebox.showinfo(APP_TITLE, "Select a class first.")
            return None
        return self._home_items[int(sel[0])]

    def _open_selected(self):
        it = self._selected_item()
        if it:
            self.cls = storage.load_class(it["path"])
            self.cls_path = it["path"]
            self.show_workspace()

    def _delete_selected(self):
        it = self._selected_item()
        if it and messagebox.askyesno(
                APP_TITLE, f"Delete {it['label']}?\nThis cannot be undone."):
            os.remove(it["path"])
            self.show_home()

    # ---------------------------------------------------------- new class
    def _new_class(self):
        path = filedialog.askopenfilename(
            title="Select a Class List PDF",
            filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        self.status("Reading class list...")

        def work():
            try:
                _load_engine()
                parsed = classlist_parser.parse_class_list(path)
                self._ui(lambda: self._show_import_preview(parsed))
            except Exception as e:
                msg = str(e)
                self._ui(lambda: messagebox.showerror(
                    APP_TITLE, f"Could not parse the PDF:\n{msg}"))
        threading.Thread(target=work, daemon=True).start()

    def _show_import_preview(self, parsed):
        self.status("")
        if not parsed["students"]:
            messagebox.showwarning(
                APP_TITLE, "No students found. Is this a Class List PDF "
                           "from the portal?")
            return
        self._clear_body()
        m = parsed["meta"]
        self.subtitle.config(text="New class - confirm the import")
        f = self.body
        ttk.Label(f, text=f"{m['subject_code']} - {m['subject_title']}  |  "
                          f"{m['section']}  |  {m['term']} "
                          f"{m['school_year']}",
                  style="Step.TLabel").pack(anchor="w")
        ttk.Label(f, text=f"Instructor: {m['instructor']}    "
                          f"Schedule: {m['schedule']}",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        cols = ("no", "id", "name", "sex", "course", "year")
        tree = ttk.Treeview(f, columns=cols, show="headings", height=15)
        for c, t, w in [("no", "No", 40), ("id", "ID", 90),
                        ("name", "Name", 320), ("sex", "Sex", 50),
                        ("course", "Course", 70), ("year", "Year", 50)]:
            tree.heading(c, text=t)
            tree.column(c, width=w,
                        anchor="center" if c != "name" else "w")
        for s in parsed["students"]:
            tree.insert("", "end", values=(s["no"], s["id"], s["name"],
                                           s["sex"], s["course"],
                                           s["year"]))
        tree.pack(fill="both", expand=True)
        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="< Cancel",
                   command=self.show_home).pack(side="left")
        ttk.Button(btns, text=f"Confirm {len(parsed['students'])} "
                              f"students >",
                   style="Accent.TButton",
                   command=lambda: self._create_class(parsed)
                   ).pack(side="right")

    def _create_class(self, parsed):
        self.cls = storage.new_class(parsed["meta"], parsed["students"])
        self.cls_path = None
        self.show_setup(first_time=True)

    # ------------------------------------------------------------- setup
    def show_setup(self, first_time=False):
        self._clear_body()
        cfg = self.cls["config"]
        m = self.cls["meta"]
        self.subtitle.config(text="Class setup")
        f = self.body

        form = ttk.LabelFrame(f, text="Class information", padding=10)
        form.pack(fill="x")
        self._setup_vars = {}
        fields = [("subject_code", "Subject code"),
                  ("subject_title", "Subject description"),
                  ("section", "Section"), ("term", "Term / Semester"),
                  ("school_year", "School Year"),
                  ("instructor", "Instructor"), ("schedule", "Schedule")]
        for i, (key, label) in enumerate(fields):
            r, c = divmod(i, 2)
            ttk.Label(form, text=label + ":",
                      style="Card.TLabel").grid(row=r, column=c * 2,
                                                sticky="w", padx=4, pady=3)
            var = tk.StringVar(value=m.get(key, ""))
            self._setup_vars[key] = var
            ttk.Entry(form, textvariable=var, width=38).grid(
                row=r, column=c * 2 + 1, sticky="we", padx=4, pady=3)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        gr = ttk.LabelFrame(f, text="Grading configuration", padding=10)
        gr.pack(fill="x", pady=8)
        ttk.Label(gr, text="Subject type preset:",
                  style="Card.TLabel").grid(row=0, column=0, sticky="w",
                                            padx=4)
        self._preset_var = tk.StringVar(value=cfg.get("preset", "Lecture"))
        presets = list(engine.PRESETS) + ["Custom"]
        cb = ttk.Combobox(gr, textvariable=self._preset_var,
                          values=presets, state="readonly", width=26)
        cb.grid(row=0, column=1, sticky="w", padx=4)
        cb.bind("<<ComboboxSelected>>", self._apply_preset)

        ttk.Label(gr, text="Component", style="Card.TLabel",
                  font=("", self.font_size, "bold")).grid(row=1, column=0,
                                                          sticky="w",
                                                          padx=4, pady=(8, 2))
        ttk.Label(gr, text="Weight %", style="Card.TLabel",
                  font=("", self.font_size, "bold")).grid(row=1, column=1,
                                                          sticky="w", padx=4)
        ttk.Label(gr, text="Score columns", style="Card.TLabel",
                  font=("", self.font_size, "bold")).grid(row=1, column=2,
                                                          sticky="w", padx=4)
        self._weight_vars, self._count_vars = {}, {}
        for i, comp in enumerate(engine.COMPONENTS):
            ttk.Label(gr, text=cfg["labels"][comp],
                      style="Card.TLabel").grid(row=2 + i, column=0,
                                                sticky="w", padx=4, pady=2)
            wv = tk.StringVar(value=str(cfg["weights"][comp]))
            self._weight_vars[comp] = wv
            ttk.Entry(gr, textvariable=wv, width=7).grid(row=2 + i,
                                                         column=1, padx=4)
            cv = tk.StringVar(value=str(cfg["columns"][comp]))
            self._count_vars[comp] = cv
            ttk.Spinbox(gr, from_=1, to=10, textvariable=cv,
                        width=5).grid(row=2 + i, column=2, padx=4)
        self._weight_msg = ttk.Label(gr, text="", style="Card.TLabel")
        self._weight_msg.grid(row=6, column=0, columnspan=3, sticky="w",
                              padx=4, pady=(6, 0))

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="< Back",
                   command=(self.show_home if first_time
                            else self.show_workspace)).pack(side="left")
        ttk.Button(btns, text="Save and open gradesheet >",
                   style="Accent.TButton",
                   command=self._save_setup).pack(side="right")
        ttk.Label(f, text="Set the Highest Possible Score for each column "
                          "in the yellow HPS row of the gradesheet itself.",
                  style="Muted.TLabel").pack(anchor="w")

    def _apply_preset(self, _e=None):
        name = self._preset_var.get()
        if name in engine.PRESETS:
            for comp, w in zip(engine.COMPONENTS, engine.PRESETS[name]):
                self._weight_vars[comp].set(str(w))

    def _save_setup(self):
        cfg = self.cls["config"]
        try:
            weights = {c: float(self._weight_vars[c].get())
                       for c in engine.COMPONENTS}
            counts = {c: max(1, min(10, int(self._count_vars[c].get())))
                      for c in engine.COMPONENTS}
        except ValueError:
            self._weight_msg.config(text="Weights and column counts must "
                                         "be numbers.")
            return
        if not engine.validate_weights(weights):
            self._weight_msg.config(
                text=f"Weights must add up to 100 "
                     f"(currently {sum(weights.values()):g}).")
            return
        for key, var in self._setup_vars.items():
            self.cls["meta"][key] = var.get().strip()
        cfg["preset"] = self._preset_var.get()
        cfg["weights"] = weights
        old_counts = cfg["columns"]
        cfg["columns"] = counts
        # resize HPS lists to the new counts
        for term in ("midterm", "finals"):
            for comp in engine.COMPONENTS:
                vals = cfg["hps"][term].get(comp, [])
                vals = (vals + [None] * counts[comp])[:counts[comp]]
                cfg["hps"][term][comp] = vals
        self._autosave(now=True)
        self.show_workspace()

    # --------------------------------------------------------- workspace
    def show_workspace(self):
        self._clear_body()
        m = self.cls["meta"]
        self.subtitle.config(
            text=f"{m.get('subject_code','')} - {m.get('section','')} - "
                 f"{m.get('term','')} {m.get('school_year','')}")
        f = self.body
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        ttk.Button(top, text="< My Classes",
                   command=self._back_home).pack(side="left")
        ttk.Button(top, text="Class setup",
                   command=self.show_setup).pack(side="left", padx=6)
        ttk.Button(top, text="Export gradesheet...",
                   style="Accent.TButton",
                   command=self._export_dialog).pack(side="right")

        nb = ttk.Notebook(f)
        nb.pack(fill="both", expand=True)
        self._grids = {}
        for term, title in (("midterm", "Midterm"), ("finals", "Finals")):
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            self._grids[term] = ScoreGrid(frame, self, term)
        sem = ttk.Frame(nb)
        nb.add(sem, text="Semestral")
        self._sem_frame = sem
        nb.bind("<<NotebookTabChanged>>",
                lambda e: self._refresh_semestral()
                if nb.index("current") == 2 else None)
        self._nb = nb

    def _back_home(self):
        self._autosave(now=True)
        self.cls = None
        self.show_home()

    def _refresh_semestral(self):
        for w in self._sem_frame.winfo_children():
            w.destroy()
        cols = ("no", "name", "mi", "mg", "fi", "fg", "si", "sg", "rem")
        tree = ttk.Treeview(self._sem_frame, columns=cols, show="headings")
        heads = [("no", "No", 40), ("name", "Learner's Name", 300),
                 ("mi", "Midterm Initial", 100), ("mg", "Midterm Grade", 100),
                 ("fi", "Finals Initial", 100), ("fg", "Finals Grade", 100),
                 ("si", "Semestral Initial", 110),
                 ("sg", "Semestral Grade", 110), ("rem", "Remark", 90)]
        for c, t, w in heads:
            tree.heading(c, text=t)
            tree.column(c, width=w,
                        anchor="center" if c != "name" else "w")
        cfg = self.cls["config"]
        table = [tuple(r) for r in cfg["transmutation"]]
        for i, s in enumerate(self.cls["students"]):
            results = {}
            for term in ("midterm", "finals"):
                scores = {c: storage.get_scores(self.cls, term, s["id"], c)
                          for c in engine.COMPONENTS}
                results[term] = engine.term_result(
                    scores, cfg["hps"][term], cfg["weights"], table)
            sem = engine.semestral_result(
                results["midterm"]["initial"], results["finals"]["initial"],
                cfg["semestral_weights"]["midterm"],
                cfg["semestral_weights"]["finals"], table)
            def fmt(v):
                return "" if v is None else f"{v:.2f}"
            tree.insert("", "end", values=(
                i + 1, s["name"],
                fmt(results["midterm"]["initial"]),
                fmt(results["midterm"]["grade"]),
                fmt(results["finals"]["initial"]),
                fmt(results["finals"]["grade"]),
                fmt(sem["initial"]), fmt(sem["grade"]), sem["remark"]))
        tree.pack(fill="both", expand=True)

    # ------------------------------------------------------------ export
    def _export_dialog(self):
        self._autosave(now=True)
        top = tk.Toplevel(self)
        top.title("Export gradesheet")
        top.transient(self)
        frame = ttk.Frame(top, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="What should the gradesheet include?",
                  font=("", self.font_size, "bold")).pack(anchor="w")
        var = tk.StringVar(value="complete")
        for val, label in [("midterm", "Midterm only"),
                           ("finals", "Finals only"),
                           ("complete", "Complete (Midterm + Finals + "
                                        "Semestral)")]:
            ttk.Radiobutton(frame, text=label, value=val,
                            variable=var).pack(anchor="w", pady=2)

        def go():
            m = self.cls["meta"]
            default = (f"GS-{m.get('subject_code','').replace(' ','')}-"
                       f"{m.get('section','').replace(' ','_')}.xlsx")
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", initialfile=default,
                filetypes=[("Excel workbook", "*.xlsx")])
            if not path:
                return
            include = {"midterm": ("midterm",),
                       "finals": ("finals",),
                       "complete": ("midterm", "finals", "semestral")
                       }[var.get()]
            top.destroy()
            self.status("Exporting gradesheet...")

            def work():
                try:
                    exporter.export_gradesheet(self.cls, path, include)
                    self._ui(lambda: (self.status(f"Exported to {path}"),
                                      messagebox.showinfo(
                                          APP_TITLE,
                                          f"Gradesheet saved:\n{path}")))
                except Exception as e:
                    msg = str(e)
                    self._ui(lambda: messagebox.showerror(
                        APP_TITLE, f"Export failed:\n{msg}"))
            threading.Thread(target=work, daemon=True).start()

        ttk.Button(frame, text="Export", style="Accent.TButton",
                   command=go).pack(anchor="e", pady=(12, 0))
        top.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()
                               - top.winfo_reqwidth()) // 2
        py = self.winfo_y() + (self.winfo_height()
                               - top.winfo_reqheight()) // 2
        top.geometry(f"+{max(0, px)}+{max(0, py)}")
        top.grab_set()

    # ---------------------------------------------------------- autosave
    def _autosave(self, now=False):
        if self.cls is None:
            return
        if self._save_job:
            self.after_cancel(self._save_job)
            self._save_job = None
        if now:
            self.cls_path = storage.save_class(self.cls, self.cls_path)
            self.status("Saved.")
        else:
            self._save_job = self.after(800, lambda: self._autosave(True))

    # ----------------------------------------------------- shared chrome
    def _init_fonts(self):
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont",
                     "TkMenuFont", "TkFixedFont"):
            try:
                tkfont.nametofont(name).configure(size=self.font_size)
            except tk.TclError:
                pass

    def change_font(self, delta):
        self.font_size = max(9, min(16, self.font_size + delta))
        self._init_fonts()
        self.apply_theme()

    def toggle_theme(self):
        self.theme_name = ("dark" if self.theme_name == "light"
                           else "light")
        self.apply_theme()

    def apply_theme(self):
        t = THEMES[self.theme_name]
        s = self.style
        base = ("", self.font_size)
        s.configure(".", background=t["bg"], foreground=t["fg"],
                    fieldbackground=t["field"], font=base,
                    bordercolor=t["line"], troughcolor=t["card"])
        s.configure("TFrame", background=t["bg"])
        s.configure("Card.TFrame", background=t["card"])
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("Card.TLabel", background=t["card"],
                    foreground=t["fg"])
        s.configure("Muted.TLabel", background=t["bg"],
                    foreground=t["muted"])
        s.configure("Header.TFrame", background=t["header"])
        s.configure("Header.TLabel", background=t["header"],
                    foreground=t["header_fg"],
                    font=("", self.font_size + 3, "bold"))
        s.configure("HeaderSub.TLabel", background=t["header"],
                    foreground=t["header_fg"])
        s.configure("Step.TLabel", background=t["bg"], foreground=t["fg"],
                    font=("", self.font_size + 2, "bold"))
        s.configure("TLabelframe", background=t["card"],
                    bordercolor=t["line"])
        s.configure("TLabelframe.Label", background=t["card"],
                    foreground=t["accent"],
                    font=("", self.font_size, "bold"))
        for w in ("TCheckbutton", "TRadiobutton"):
            s.configure(w, background=t["card"], foreground=t["fg"])
            s.map(w, background=[("active", t["card"])])
        s.configure("TButton", background=t["card"], foreground=t["fg"],
                    bordercolor=t["line"], focusthickness=1, padding=6)
        s.map("TButton", background=[("active", t["line"])])
        s.configure("Accent.TButton", background=t["accent"],
                    foreground=t["accent_fg"], padding=8,
                    font=("", self.font_size, "bold"))
        s.map("Accent.TButton",
              background=[("active", t["accent_hover"]),
                          ("disabled", t["line"])])
        s.configure("TEntry", fieldbackground=t["field"],
                    foreground=t["fg"], insertcolor=t["fg"])
        s.configure("TSpinbox", fieldbackground=t["field"],
                    foreground=t["fg"], insertcolor=t["fg"],
                    arrowcolor=t["fg"])
        s.configure("TCombobox", fieldbackground=t["field"],
                    foreground=t["fg"])
        s.configure("TNotebook", background=t["bg"],
                    bordercolor=t["line"])
        s.configure("TNotebook.Tab", background=t["card"],
                    foreground=t["fg"], padding=(14, 6))
        s.map("TNotebook.Tab",
              background=[("selected", t["accent"])],
              foreground=[("selected", t["accent_fg"])])
        s.configure("Treeview", background=t["field"],
                    fieldbackground=t["field"], foreground=t["fg"],
                    rowheight=int(self.font_size * 2.2))
        s.configure("Treeview.Heading", background=t["card"],
                    foreground=t["fg"],
                    font=("", self.font_size, "bold"))
        tbfont = (("Segoe MDL2 Assets", max(8, self.font_size - 3))
                  if self._mdl2 else ("", max(8, self.font_size - 2)))
        s.configure("Title.TButton", background=t["header"],
                    foreground=t["header_fg"], borderwidth=0,
                    padding=(10, 8), font=tbfont)
        s.map("Title.TButton", background=[("active", t["line"])])
        s.configure("TitleClose.TButton", background=t["header"],
                    foreground=t["header_fg"], borderwidth=0,
                    padding=(10, 8), font=tbfont)
        s.map("TitleClose.TButton",
              background=[("active", "#e81123")],
              foreground=[("active", "#ffffff")])
        s.configure("Vertical.TScrollbar", background=t["card"],
                    troughcolor=t["bg"], bordercolor=t["line"],
                    arrowcolor=t["fg"])
        s.configure("Horizontal.TScrollbar", background=t["card"],
                    troughcolor=t["bg"], bordercolor=t["line"],
                    arrowcolor=t["fg"])
        self.configure(background=t["bg"])
        if getattr(self, "_custom_titlebar", False):
            try:
                self.configure(highlightthickness=1,
                               highlightbackground=t["line"],
                               highlightcolor=t["line"])
            except tk.TclError:
                pass
        for w, kind in list(self._themed_plain):
            try:
                if kind == "canvas":
                    w.configure(bg=t["card"], highlightthickness=0)
                elif kind == "entry":
                    w.configure(bg=t["field"], fg=t["fg"],
                                insertbackground=t["fg"],
                                highlightbackground=t["line"],
                                disabledbackground=t["card"])
            except tk.TclError:
                pass
        if hasattr(self, "btn_theme"):
            nxt = "Dark" if self.theme_name == "light" else "Light"
            self.btn_theme.config(text=f"{nxt} mode")

    def show_about(self):
        top = tk.Toplevel(self)
        top.title(f"About {APP_TITLE}")
        top.resizable(False, False)
        top.transient(self)
        frame = ttk.Frame(top, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=APP_TITLE,
                  font=("", self.font_size + 4, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Version {APP_VERSION} (prototype)",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, justify="left", text=(
            "Imports UNP class list PDFs, records scores per grading\n"
            "component, computes Midterm, Finals, and Semestral grades\n"
            "using the official E-Class Record formulation, and exports\n"
            "a gradesheet with live formulas.\n\n"
            "Everything runs locally. No data is sent anywhere.")
            ).pack(anchor="w")
        ttk.Label(frame, text=f"\nDeveloped by {DEVELOPER}",
                  font=("", self.font_size, "bold")).pack(anchor="w")
        ttk.Button(frame, text="Close", style="Accent.TButton",
                   command=top.destroy).pack(anchor="e", pady=(16, 0))
        top.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()
                               - top.winfo_reqwidth()) // 2
        py = self.winfo_y() + (self.winfo_height()
                               - top.winfo_reqheight()) // 2
        top.geometry(f"+{max(0, px)}+{max(0, py)}")
        top.grab_set()

    # window helpers (same behavior as the Appraisal Filler)
    def _center_window(self, w, h):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//3)}")

    def _work_area(self):
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0)
            return (rect.left, rect.top, rect.right - rect.left,
                    rect.bottom - rect.top)
        except Exception:
            return (0, 0, self.winfo_screenwidth(),
                    self.winfo_screenheight())

    def _enable_custom_titlebar(self):
        self.overrideredirect(True)
        self.update_idletasks()
        self._set_appwindow_style()
        self.wm_withdraw()
        self.after(30, self._reshow_on_top)
        self.bind("<Map>", self._on_map)

    def _set_appwindow_style(self):
        try:
            import ctypes
            GWL_EXSTYLE = -20
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~0x00000080) | 0x00040000
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def _reshow_on_top(self):
        self.wm_deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(700, lambda: self.attributes("-topmost", False))
        except tk.TclError:
            pass
        self.focus_force()

    def _on_map(self, _e=None):
        if self._custom_titlebar and not self.overrideredirect():
            self.overrideredirect(True)
            self.update_idletasks()
            self._set_appwindow_style()
            self.lift()

    def _minimize(self):
        self.overrideredirect(False)
        self.iconify()

    def _toggle_zoom(self):
        if self._is_zoomed:
            self.state("normal")
            if self._normal_geometry:
                self.geometry(self._normal_geometry)
            self._is_zoomed = False
            self._btn_zoom.config(text=self._glyphs["max"])
        else:
            self._normal_geometry = self.geometry()
            x, y, w, h = self._work_area()
            self.geometry(f"{w}x{h}+{x}+{y}")
            self._is_zoomed = True
            self._btn_zoom.config(text=self._glyphs["restore"])

    def _start_move(self, event):
        if self._is_zoomed:
            self._drag_origin = None
            return
        self._drag_origin = (event.x_root, event.y_root,
                             self.winfo_x(), self.winfo_y())

    def _do_move(self, event):
        if not self._drag_origin:
            return
        ox, oy, wx, wy = self._drag_origin
        self.geometry(f"+{wx + event.x_root - ox}+{wy + event.y_root - oy}")

    def _set_app_icon(self):
        try:
            png = resource_path(os.path.join("assets", "logo.png"))
            if os.path.exists(png):
                self._icon_img = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon_img)
        except tk.TclError:
            pass
        if sys.platform.startswith("win"):
            try:
                ico = resource_path(os.path.join("assets", "logo.ico"))
                if os.path.exists(ico):
                    self.iconbitmap(default=ico)
            except tk.TclError:
                pass

    def _ui(self, fn):
        self._msgq.put(fn)

    def _poll_queue(self):
        try:
            while True:
                fn = self._msgq.get_nowait()
                try:
                    fn()
                except tk.TclError:
                    pass
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)


class ScoreGrid:
    """Spreadsheet-like score entry grid for one term."""

    def __init__(self, parent, app, term):
        self.app = app
        self.term = term
        self.cls = app.cls
        cfg = self.cls["config"]

        outer = ttk.Frame(parent)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical",
                            command=canvas.yview)
        hsb = ttk.Scrollbar(outer, orient="horizontal",
                            command=canvas.xview)
        self.inner = ttk.Frame(canvas, style="Card.TFrame")
        self.inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        app._themed_plain.append((canvas, "canvas"))

        self.hps_entries = {}      # (comp, i) -> entry
        self.entries = {}          # (sid, comp, i) -> entry
        self.result_labels = {}    # sid -> (initial, grade, remark labels)
        self._build()
        self.recompute_all()

    def _mk_entry(self, parent, width=5):
        e = tk.Entry(parent, width=width, justify="center",
                     relief="solid", borderwidth=1)
        self.app._themed_plain.append((e, "entry"))
        return e

    def _build(self):
        cfg = self.cls["config"]
        f = self.inner
        exam_label = ("MIDTERM EXAM" if self.term == "midterm"
                      else "FINAL EXAM")

        # header rows
        col = 0
        ttk.Label(f, text="No", style="Card.TLabel", width=4,
                  font=("", self.app.font_size, "bold")
                  ).grid(row=0, column=col, rowspan=2, sticky="nsew")
        col += 1
        ttk.Label(f, text="LEARNERS' NAMES", style="Card.TLabel",
                  width=32, font=("", self.app.font_size, "bold")
                  ).grid(row=0, column=col, rowspan=2, sticky="nsew")
        col += 1
        self.comp_cols = {}
        for comp in engine.COMPONENTS:
            n = cfg["columns"][comp]
            label = (exam_label if comp == "exam"
                     else cfg["labels"][comp])
            ttk.Label(f, text=f"{label} ({cfg['weights'][comp]:g}%)",
                      style="Card.TLabel", anchor="center",
                      font=("", self.app.font_size, "bold")
                      ).grid(row=0, column=col, columnspan=n,
                             sticky="nsew", padx=1)
            start = col
            for i in range(n):
                ttk.Label(f, text=str(i + 1), style="Card.TLabel",
                          anchor="center").grid(row=1, column=col,
                                                sticky="nsew")
                col += 1
            self.comp_cols[comp] = start
        for text in ("INITIAL", "GRADE", "REMARK"):
            ttk.Label(f, text=text, style="Card.TLabel", width=8,
                      anchor="center",
                      font=("", self.app.font_size, "bold")
                      ).grid(row=0, column=col, rowspan=2, sticky="nsew")
            col += 1

        # HPS row
        ttk.Label(f, text="", style="Card.TLabel").grid(row=2, column=0)
        ttk.Label(f, text="HIGHEST POSSIBLE SCORE", style="Card.TLabel",
                  font=("", self.app.font_size, "bold")
                  ).grid(row=2, column=1, sticky="w")
        for comp in engine.COMPONENTS:
            hps = cfg["hps"][self.term][comp]
            for i in range(cfg["columns"][comp]):
                e = self._mk_entry(f)
                if i < len(hps) and hps[i] is not None:
                    e.insert(0, f"{hps[i]:g}")
                e.grid(row=2, column=self.comp_cols[comp] + i, padx=1,
                       pady=1)
                e.bind("<KeyRelease>",
                       lambda ev, c=comp, idx=i: self._hps_changed(c, idx))
                self.hps_entries[(comp, i)] = e

        # student rows
        for r, s in enumerate(self.cls["students"], start=3):
            ttk.Label(f, text=str(r - 2), style="Card.TLabel",
                      anchor="center").grid(row=r, column=0, sticky="nsew")
            ttk.Label(f, text=s["name"], style="Card.TLabel"
                      ).grid(row=r, column=1, sticky="w")
            for comp in engine.COMPONENTS:
                vals = storage.get_scores(self.cls, self.term, s["id"],
                                          comp)
                for i in range(cfg["columns"][comp]):
                    e = self._mk_entry(f)
                    if i < len(vals) and vals[i] is not None:
                        e.insert(0, f"{vals[i]:g}")
                    e.grid(row=r, column=self.comp_cols[comp] + i,
                           padx=1, pady=1)
                    e.bind("<KeyRelease>",
                           lambda ev, sid=s["id"], c=comp, idx=i:
                           self._score_changed(sid, c, idx))
                    self.entries[(s["id"], comp, i)] = e
            labels = []
            base_col = max(self.comp_cols[c] + cfg["columns"][c]
                           for c in engine.COMPONENTS)
            for j in range(3):
                lb = ttk.Label(f, text="", style="Card.TLabel",
                               anchor="center", width=8)
                lb.grid(row=r, column=base_col + j, sticky="nsew")
                labels.append(lb)
            self.result_labels[s["id"]] = labels

    @staticmethod
    def _num(text):
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return "bad"

    def _hps_changed(self, comp, idx):
        v = self._num(self.hps_entries[(comp, idx)].get())
        if v == "bad":
            return
        hps = self.cls["config"]["hps"][self.term][comp]
        while len(hps) <= idx:
            hps.append(None)
        hps[idx] = v
        self.recompute_all()
        self.app._autosave()

    def _score_changed(self, sid, comp, idx):
        e = self.entries[(sid, comp, idx)]
        v = self._num(e.get())
        warn = THEMES[self.app.theme_name]["warn"]
        normal = THEMES[self.app.theme_name]["fg"]
        if v == "bad":
            e.configure(fg=warn)
            return
        hps = self.cls["config"]["hps"][self.term][comp]
        hv = hps[idx] if idx < len(hps) else None
        e.configure(fg=warn if (v is not None and hv is not None
                                and v > hv) else normal)
        storage.set_score(self.cls, self.term, sid, comp, idx, v)
        self.recompute_row(sid)
        self.app._autosave()

    def recompute_row(self, sid):
        cfg = self.cls["config"]
        scores = {c: storage.get_scores(self.cls, self.term, sid, c)
                  for c in engine.COMPONENTS}
        table = [tuple(r) for r in cfg["transmutation"]]
        res = engine.term_result(scores, cfg["hps"][self.term],
                                 cfg["weights"], table)
        init, grade, remark = self.result_labels[sid]
        init.config(text="" if res["initial"] is None
                    else f"{res['initial']:.2f}")
        grade.config(text="" if res["grade"] is None
                     else f"{res['grade']:.2f}")
        remark.config(text=res["remark"])

    def recompute_all(self):
        for s in self.cls["students"]:
            self.recompute_row(s["id"])


def main():
    _load_engine()
    App().mainloop()


if __name__ == "__main__":
    main()
