"""Main application window: toolbar, tabbed editor, status bar, menus,
keyboard shortcuts and modern styling.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys

from . import syntax
from .editor import make_tab, LANGUAGES
from .theme import Theme
from .runner import Runner, resolve_command, detect_missing_interpreter
from .output import OutputConsole
from .tabcontrol import CustomNotebook


RECENT_FILES_KEY = "recent_files"


class AboutDialog(tk.Toplevel):
    def __init__(self, parent, version):
        super().__init__(parent)
        self.title("About")
        self.resizable(False, False)
        self.transient(parent)
        self.configure(bg=Theme.DARK["bg_alt"])
        self.grab_set()

        title = tk.Label(self, text="CodePad", font=("Segoe UI", 16, "bold"),
                         bg=Theme.DARK["bg_alt"], fg=Theme.DARK["fg_strong"])
        title.pack(padx=40, pady=(20, 4))

        ver = tk.Label(self, text=f"Version {version}", font=("Segoe UI", 10),
                       bg=Theme.DARK["bg_alt"], fg=Theme.DARK["fg_muted"])
        ver.pack(pady=(0, 4))

        desc = tk.Label(self, text="A modern text & code editor\nbuilt with Python and Tkinter.",
                        font=("Segoe UI", 10), justify="center",
                        bg=Theme.DARK["bg_alt"], fg=Theme.DARK["fg"])
        desc.pack(pady=(0, 20))


class MainWindow:
    def __init__(self, root):
        self.root = root
        root.title("CodePad")
        root.geometry("1040x700")
        root.minsize(640, 400)

        self.version = "1.0.0"
        self.dark = True
        self.tabs = []           # list of EditorTab
        self.current_tab = None
        self.recent_files = []
        self._status_job = None
        self.module_dirs = []    # directories added to the import path
        self.console_visible = False
        self.runner = Runner(root=self.root)
        self.running_tab = None

        self._load_recent()
        self._build_style()
        self._build_menu()
        self._build_toolbar()
        self._build_editor()
        self._build_statusbar()
        self._setup_shortcuts()

        # open with args if given
        self.new_file(show=True)
        self._apply_theme()
        self.root.update_idletasks()

    # ------------------------------------------------------------------
    # Theme / styling
    # ------------------------------------------------------------------
    def _theme(self):
        return Theme.DARK if self.dark else Theme.LIGHT

    def _build_style(self):
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.style.element_create("Toolbar.button", "from", "clam")

    def _configure_ttk(self, c):
        s = self.style
        font_ui = ("Segoe UI", 9)
        font_ui_md = ("Segoe UI", 9, "semibold")

        s.configure("TFrame", background=c["bg_alt"])
        s.configure("TLabel", background=c["bg_alt"], foreground=c["fg"],
                    font=font_ui)
        s.configure("Status.TLabel", background=c["bg_alt"],
                    foreground=c["fg_muted"], font=font_ui)

        # ---- Toolbar ----
        s.configure("Toolbar.TFrame", background=c["bg_alt"])
        s.configure("Toolbar.TButton",
                    background=c["bg_alt"], foreground=c["fg"],
                    borderwidth=0, focusthickness=0, padding=(10, 6),
                    font=font_ui)
        s.map("Toolbar.TButton",
              background=[("active", c["bg_highlight"]),
                          ("pressed", c["accent"])],
              foreground=[("active", c["fg_strong"]),
                          ("pressed", "#ffffff")])

        # primary (accent) button style
        s.configure("Accent.TButton",
                    background=c["accent"], foreground="#ffffff",
                    borderwidth=0, focusthickness=0, padding=(12, 6),
                    font=font_ui_md)
        s.map("Accent.TButton",
              background=[("active", c["accent_alt"]),
                          ("pressed", c["accent_alt"])])

        # ---- Tab bar ----
        s.configure("TNotebook", background=c["bg_alt"],
                    borderwidth=0, tabmargins=(0, 3, 0, 0))
        s.configure("TNotebook.Tab",
                    background=c["tab_inactive_bg"],
                    foreground=c["fg_muted"],
                    padding=(14, 7), font=font_ui,
                    borderwidth=0, focuscolor=c["bg_alt"])
        s.map("TNotebook.Tab",
              background=[("selected", c["bg"]),
                          ("active", c["bg_highlight"])],
              foreground=[("selected", c["fg_strong"])])

        # ---- Scrollbars: slim, flat, modern ----
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar",
                        troughcolor=c["bg_alt"],
                        background=c["bg_widget"],
                        borderwidth=0,
                        lightcolor=c["bg_widget"],
                        darkcolor=c["bg_widget"],
                        arrowcolor=c["fg_muted"],
                        width=12,
                        relief="flat")
            s.map(f"{orient}.TScrollbar",
                  background=[("active", c["fg_muted"])])

        # ---- Entry ----
        s.configure("TEntry", fieldbackground=c["bg"],
                    foreground=c["fg"], bordercolor=c["border"],
                    lightcolor=c["border"], darkcolor=c["border"],
                    insertcolor=c["fg"], padding=(6, 4))

        # ---- Combobox ----
        s.configure("TCombobox", fieldbackground=c["bg"],
                    background=c["bg_widget"], foreground=c["fg"],
                    arrowcolor=c["fg_muted"], bordercolor=c["border"],
                    lightcolor=c["border"], darkcolor=c["border"],
                    padding=(6, 4))
        s.map("TCombobox",
              fieldbackground=[("readonly", c["bg"])],
              foreground=[("readonly", c["fg"])])

        # ---- Checkbutton ----
        s.configure("TCheckbutton", background=c["bg_alt"],
                    foreground=c["fg"], font=font_ui, padding=(2, 2))
        s.map("TCheckbutton",
              background=[("active", c["bg_alt"])])

    def _apply_theme(self):
        c = self._theme()
        self._configure_ttk(c)
        self.root.configure(bg=c["bg_alt"])
        self.paned.configure(bg=c["bg_alt"])
        self.notebook_widget.set_theme(c)
        for tab in self.tabs:
            tab.set_theme(c)
        self.console.set_theme(c)

    # ------------------------------------------------------------------
    # Widgets
    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root, tearoff=0)
        self.root.config(menu=menubar)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New File", accelerator="Ctrl+N",
                              command=lambda: self.new_file())
        file_menu.add_command(label="Open File...", accelerator="Ctrl+O",
                              command=self.open_files)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S",
                              command=self.save_as)
        file_menu.add_command(label="Save All", accelerator="Ctrl+Alt+S",
                              command=self.save_all)
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab", accelerator="Ctrl+W",
                              command=self.close_tab)
        file_menu.add_command(label="Close All", accelerator="Ctrl+Shift+W",
                              command=self.close_all)
        file_menu.add_separator()
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z",
                              command=lambda: self._call_tab("undo"))
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y",
                              command=lambda: self._call_tab("redo"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X",
                              command=lambda: self._call_tab("cut"))
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C",
                              command=lambda: self._call_tab("copy"))
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V",
                              command=lambda: self._call_tab("paste"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Find", accelerator="Ctrl+F",
                              command=self.find)
        edit_menu.add_command(label="Replace", accelerator="Ctrl+H",
                              command=self.replace)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A",
                              command=lambda: self._call_tab("select_all"))
        edit_menu.add_command(label="Go to Line...", accelerator="Ctrl+G",
                              command=self.go_to_line)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0)
        self.wrap_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(label="Word Wrap", variable=self.wrap_var,
                                  command=self._toggle_wrap)
        view_menu.add_checkbutton(label="Dark Theme", variable=tk.BooleanVar(value=True),
                                  command=self._toggle_theme)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", accelerator="Ctrl+=", command=self.zoom_in)
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+-", command=self.zoom_out)
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.zoom_reset)
        view_menu.add_separator()
        view_menu.add_command(label="Fullscreen", accelerator="F11",
                              command=self._toggle_fullscreen)
        menubar.add_cascade(label="View", menu=view_menu)

        # Language
        lang_menu = tk.Menu(menubar, tearoff=0)
        self.lang_menu = lang_menu
        self._lang_items = {}
        self.lang_var = tk.StringVar(value="Plain Text")
        menubar.add_cascade(label="Language", menu=lang_menu)
        self._rebuild_language_menu()

        # Run
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="Run", accelerator="F5", command=self.run_current)
        run_menu.add_command(label="Run in Console", accelerator="Ctrl+Enter",
                             command=self.run_detached)
        run_menu.add_separator()
        run_menu.add_command(label="Stop", command=self.stop_run)
        run_menu.add_separator()
        self.console_menu_var = tk.BooleanVar(value=False)
        run_menu.add_checkbutton(label="Show Output Panel", variable=self.console_menu_var,
                                 command=self.toggle_console)
        menubar.add_cascade(label="Run", menu=run_menu)

        # Project (module importing)
        project_menu = tk.Menu(menubar, tearoff=0)
        project_menu.add_command(label="Import Module / File...", command=self.import_module)
        project_menu.add_command(label="Add Folder to Path...", command=self.add_module_folder)
        project_menu.add_separator()
        project_menu.add_command(label="Clear Imported Modules", command=self.clear_modules)
        menubar.add_cascade(label="Modules", menu=project_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="About CodePad", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        # Rebind fix so Ctrl+Ctrl combos don't conflict:
        self.menubar = menubar

    def _rebuild_language_menu(self):
        self.lang_menu.delete(0, tk.END)
        for lang in LANGUAGES:
            self.lang_menu.add_radiobutton(
                label=lang, value=lang, variable=self.lang_var,
                command=self._apply_language_menu_change)

    def _apply_language_menu_change(self):
        if self.current_tab:
            self.current_tab.language = self.lang_var.get()
            self.current_tab._schedule_highlight()
            self._update_title()

    # ------------------------------------------------------------------
    def _build_toolbar(self):
        self.toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(4, 3))
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Run button (accent, primary) at far left
        ttk.Button(self.toolbar, text="Run", style="Accent.TButton",
                   width=6, command=self.run_current).pack(side=tk.LEFT, padx=(4, 1), pady=1)
        ttk.Button(self.toolbar, text="Stop", style="Toolbar.TButton",
                   width=6, command=self.stop_run).pack(side=tk.LEFT, padx=1, pady=1)
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        buttons = [
            ("New", self.new_file),
            ("Open", self.open_files),
            ("Save", self.save),
            ("|", None),
            ("Undo", lambda: self._call_tab("undo")),
            ("Redo", lambda: self._call_tab("redo")),
            ("|", None),
            ("Cut", lambda: self._call_tab("cut")),
            ("Copy", lambda: self._call_tab("copy")),
            ("Paste", lambda: self._call_tab("paste")),
            ("|", None),
            ("Find", self.find),
            ("Replace", self.replace),
        ]
        for label, cmd in buttons:
            if label == "|":
                ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(
                    side=tk.LEFT, fill=tk.Y, padx=6)
            else:
                ttk.Button(self.toolbar, text=label, style="Toolbar.TButton",
                           width=max(5, len(label) + 2), command=cmd).pack(
                    side=tk.LEFT, padx=1)

    def _build_editor(self):
        self.editor_area = ttk.Frame(self.root, style="TFrame")
        self.editor_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Paned pane so a console can be shown below the tabs
        self.paned = tk.PanedWindow(self.editor_area, orient=tk.VERTICAL,
                                    sashwidth=3, bg=self._theme()["bg_alt"],
                                    borderwidth=0, relief=tk.FLAT)
        self.paned.pack(fill=tk.BOTH, expand=True)

        tab_host = ttk.Frame(self.paned, style="TFrame")
        self.paned.add(tab_host, stretch="always")

        self.notebook_widget = CustomNotebook(tab_host)
        self.notebook_widget.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.notebook_widget.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.notebook_widget.bind("<<TabContextMenu>>", self._on_tab_right_click)
        self.notebook_widget.on_close = self._tab_close_requested

        # Console (hidden by default)
        self.console = OutputConsole(self.paned, style_name="TFrame")
        self.console.pack_forget()

    def _build_statusbar(self):
        self.statusbar = ttk.Frame(self.root, style="TFrame", padding=(8, 3))
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.pos_label = ttk.Label(self.statusbar, text="Ln 1, Col 1", style="Status.TLabel")
        self.pos_label.pack(side=tk.LEFT, padx=4)
        self.lang_label = ttk.Label(self.statusbar, text="Plain Text", style="Status.TLabel")
        self.lang_label.pack(side=tk.LEFT, padx=16)
        self.word_label = ttk.Label(self.statusbar, text="0 words", style="Status.TLabel")
        self.word_label.pack(side=tk.LEFT, padx=4)

        self.enc_label = ttk.Label(self.statusbar, text="UTF-8", style="Status.TLabel")
        self.enc_label.pack(side=tk.RIGHT, padx=4)
        self.eol_label = ttk.Label(self.statusbar, text="LF", style="Status.TLabel")
        self.eol_label.pack(side=tk.RIGHT, padx=8)
        self.pos2_label = ttk.Label(self.statusbar, text="Ln 1, Col 1", style="Status.TLabel")
        self.pos2_label.pack(side=tk.RIGHT, padx=8)
        self.tab_label = ttk.Label(self.statusbar, text="Spaces: 4", style="Status.TLabel")
        self.tab_label.pack(side=tk.RIGHT, padx=8)

    def _setup_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_files())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_as())
        self.root.bind("<Control-Alt-s>", lambda e: self.save_all())
        self.root.bind("<Control-w>", lambda e: self.close_tab())
        self.root.bind("<Control-Shift-W>", lambda e: self.close_all() if False else self.close_all())
        self.root.bind("<Control-g>", lambda e: self.go_to_line())
        self.root.bind("<Control-f>", lambda e: self.find())
        self.root.bind("<Control-h>", lambda e: self.replace())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-plus>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())
        self.root.bind("<F5>", lambda e: self.run_current())
        self.root.bind("<Control-Return>", lambda e: self.run_detached())
        self.root.bind("<F6>", lambda e: self.stop_run())
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.root.bind("<Control-Tab>", lambda e: self.next_tab())
        self.root.bind("<Control-Shift-Tab>", lambda e: self.prev_tab())
        self.root.bind("<Control-Shift-T>", lambda e: self._toggle_theme())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------
    def new_file(self, show=True):
        tab = make_tab(self.notebook_widget)
        self.tabs.append(tab)
        title = self._title_for(tab, "Untitled")
        self.notebook_widget.add(tab.frame, text=title)
        self.notebook_widget.select(tab.frame)
        self.current_tab = tab
        if show:
            self._on_tab_changed()
        self._update_status()
        return tab

    def open_files(self):
        paths = filedialog.askopenfilenames(
            title="Open Files",
            filetypes=[
                ("All Files", "*.*"),
                ("Source Code", "*.py *.js *.ts *.jsx *.tsx *.html *.css *.json "
                                "*.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.php "
                                "*.rb *.sql *.sh *.xml *.yaml *.yml *.lua *.md"),
                ("Text Files", "*.txt *.md"),
                ("Python", "*.py *.pyw"),
                ("JavaScript", "*.js *.mjs *.cjs *.ts"),
                ("C / C++", "*.c *.h *.cpp *.hpp"),
                ("Markdown", "*.md"),
            ],
        )
        if not paths:
            return
        for path in paths:
            self._open_path(path)
        if self.tabs:
            self.current_tab = self.tabs[-1]
            self.notebook_widget.select(self.tabs[-1].frame)
            self._on_tab_changed()

    def _open_path(self, path, show=True):
        for tab in self.tabs:
            if tab.path and os.path.abspath(tab.path) == os.path.abspath(path):
                self.notebook_widget.select(tab.frame)
                self.current_tab = tab
                self._on_tab_changed()
                return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            enc = "UTF-8"
        except (UnicodeDecodeError, OSError):
            try:
                with open(path, "r", encoding="latin-1") as f:
                    content = f.read()
                enc = "Latin-1"
            except OSError as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")
                return

        tab = make_tab(self.notebook_widget, path=path, content=content,
                       language=syntax.language_for_path(path))
        tab.enc = enc
        self.tabs.append(tab)
        title = self._title_for(tab, os.path.basename(path))
        self.notebook_widget.add(tab.frame, text=title)
        self._add_recent(path)
        if show:
            self.notebook_widget.select(tab.frame)
            self.current_tab = tab
            self._on_tab_changed()

    def _title_for(self, tab, base):
        title = base
        marker = ""
        return title + marker

    def _update_title(self):
        if self.current_tab:
            idx = self.notebook_widget.index(self.current_tab.frame)
            base = os.path.basename(self.current_tab.path) if self.current_tab.path else "Untitled"
            self.notebook_widget.tab(idx, text=base)
            lang = self.current_tab.language
            self.lang_label.config(text=lang)

    def save(self):
        if not self.current_tab:
            return
        tab = self.current_tab
        if tab.path:
            self._write(tab, tab.path)
        else:
            self.save_as()

    def save_as(self):
        if not self.current_tab:
            return
        tab = self.current_tab

        ext = syntax.extension_for_language(tab.language)
        if tab.path:
            base = os.path.splitext(tab.path)[0]
            current_ext = os.path.splitext(tab.path)[1].lower()
            initial = (base + ext) if current_ext != ext else tab.path
            initial_dir = os.path.dirname(tab.path)
        else:
            initial = "Untitled" + ext
            initial_dir = None

        types = [("All Files", "*.*")]
        seen = set()
        for lang in LANGUAGES:
            e = syntax.extension_for_language(lang)
            if e in seen:
                continue
            seen.add(e)
            types.insert(0, (lang, f"*{e}"))

        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=os.path.basename(initial) if initial else None,
            initialdir=initial_dir,
            filetypes=types,
        )
        if path:
            self._write(tab, path)
            tab.path = path
            tab.language = syntax.language_for_path(path)
            tab._schedule_highlight()
            self._update_title()
            self._add_recent(path)

    def save_all(self):
        for tab in self.tabs:
            if tab.path:
                self._write(tab, tab.path)
            else:
                self.current_tab = tab
                self.notebook_widget.select(tab.frame)
                self.save_as()

    def _write(self, tab, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(tab.get_content())
            tab.enc = "UTF-8"
            self._add_recent(path)
            self._update_title()
        except OSError as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")

    # ------------------------------------------------------------------
    # Run / Output console / Modules
    # ------------------------------------------------------------------
    def run_current(self):
        """Save the active file if needed, then run it with the console."""
        tab = self.current_tab
        if not tab:
            return
        # Save first so we run the latest version.
        if tab.path:
            self._write(tab, tab.path)
        else:
            if messagebox.askyesno("Save First",
                                   "Run requires a saved file. Save it now?"):
                self.save_as()
            if not tab.path:
                return

        missing = detect_missing_interpreter(tab.language)
        if missing:
            messagebox.showerror("Cannot Run", missing)
            return

        self.show_console()
        self.console.clear()
        self.console.write(f"\n{'-' * 46}\n", "cmd")
        self.console.write(f"Running: {os.path.basename(tab.path)} "
                           f"[{tab.language}]\n", "cmd")

        cwd = os.path.dirname(tab.path) or None
        # make the file's directory importable
        if tab.language == "Python":
            if cwd and cwd not in self.module_dirs:
                self.module_dirs.append(cwd)

        cmd, env = resolve_command(tab.language, tab.path, self.module_dirs)
        if not cmd:
            self.console.write_error("Could not build a run command.\n")
            return

        self.running_tab = tab
        self.runner.on_output = self.console.write
        self.runner.on_error = self.console.write_error
        self.runner.on_done = self._on_run_done
        self.console.set_input_handler(self.runner.write_input)
        self.console.set_interrupt_handler(self.runner.stop)
        self.runner.run(cmd, cwd=cwd, env=env)
        if self.runner.is_running:
            self.console.set_running(True)
            self.console.start_input_mode()
        else:
            self.console.set_running(False)
        self._update_status()

    def run_detached(self):
        """Run the file in an external console window."""
        tab = self.current_tab
        if not tab:
            return
        if tab.path:
            self._write(tab, tab.path)
        else:
            messagebox.showinfo("Save First", "Please save the file before running.")
            return
        missing = detect_missing_interpreter(tab.language)
        if missing:
            messagebox.showerror("Cannot Run", missing)
            return
        cmd, env = resolve_command(tab.language, tab.path, self.module_dirs)
        if not cmd:
            return
        cwd = os.path.dirname(tab.path) or None
        try:
            subprocess.Popen(
                f'cmd /k "{cmd}"' if os.name == "nt" else f'{cmd}',
                cwd=cwd, env=env or os.environ.copy(),
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            )
        except OSError as e:
            messagebox.showerror("Run Error", str(e))

    def _on_run_done(self, code):
        self.console.end_input_mode()
        self.console.set_running(False)
        tag = "err" if code != 0 else "cmd"
        self.console.write(f"\n[Process finished with exit code {code}]\n", tag)
        self.running_tab = None
        self._update_status()

    def stop_run(self):
        if self.runner.is_running:
            self.runner.stop()
        self.console.end_input_mode()
        self.console.set_running(False)
        self.running_tab = None
        self._update_status()

    def show_console(self):
        if self.console_visible:
            return
        self.console_visible = True
        self.console_menu_var.set(True)
        self.paned.add(self.console, stretch="never")
        try:
            self.paned.paneconfigure(self.console, height=180)
        except Exception:
            pass

    def hide_console(self):
        if not self.console_visible:
            return
        self.console_visible = False
        self.console_menu_var.set(False)
        try:
            self.paned.forget(self.console)
        except Exception:
            pass

    def toggle_console(self):
        if self.console_visible:
            self.hide_console()
        else:
            self.show_console()

    def import_module(self):
        """Open one or more module files as editable tabs."""
        paths = filedialog.askopenfilenames(
            title="Import Module(s)",
            filetypes=[
                ("Python module", "*.py *.pyw"),
                ("JavaScript", "*.js *.mjs *.cjs"),
                ("C / C++", "*.c *.h *.cpp *.hpp"),
                ("All Files", "*.*"),
            ],
        )
        if not paths:
            return
        for p in paths:
            self._open_path(p)
        self._refresh_recent_menu()
        # add their folders to the import path
        for p in paths:
            d = os.path.dirname(os.path.abspath(p))
            if d not in self.module_dirs:
                self.module_dirs.append(d)
        if self.module_dirs:
            self.console.write(f"[Modules] import paths: "
                               f"{self.module_dirs}\n", "cmd")
            if not self.console_visible:
                self.show_console()

    def add_module_folder(self):
        path = filedialog.askdirectory(title="Add Folder to Import Path")
        if path:
            abspath = os.path.abspath(path)
            if abspath not in self.module_dirs:
                self.module_dirs.append(abspath)
                self.console.write(f"[Modules] added path: {abspath}\n", "cmd")
                if not self.console_visible:
                    self.show_console()

    def clear_modules(self):
        self.module_dirs = []
        if self.console_visible:
            self.console.write("[Modules] import paths cleared.\n", "cmd")

    def close_tab(self, tab=None):
        tab = tab or self.current_tab
        if not tab:
            return
        # make sure the tab being closed is the active one
        if tab is not self.current_tab:
            self.notebook_widget.select(tab.frame)
            self.current_tab = tab
            self._on_tab_changed()
        if tab.user_edit and not self._confirm_discard(tab):
            return
        self.tabs.remove(tab)
        self.notebook_widget.forget(tab.frame)
        tab.close()
        if not self.tabs:
            self.new_file(show=True)
        else:
            idx = self.notebook_widget.select()
            self.current_tab = self._tab_from_widget(idx)
            self._on_tab_changed()

    def _keep_untitled(self, tab):
        return True

    def _confirm_discard(self, tab):
        result = messagebox.askyesnocancel(
            "Unsaved Changes", f"Save changes to '{os.path.basename(tab.path) if tab.path else 'Untitled'}'?")
        if result is None:
            return False  # user chose Cancel -> abort close
        if result:
            self.current_tab = tab
            self.notebook_widget.select(tab.frame)
            self.save()
        return True

    def close_all(self):
        while self.tabs:
            self.close_tab()

    def next_tab(self):
        if len(self.tabs) > 1:
            idx = self.notebook_widget.index("current")
            self.notebook_widget.select((idx + 1) % len(self.tabs))

    def prev_tab(self):
        if len(self.tabs) > 1:
            idx = self.notebook_widget.index("current")
            self.notebook_widget.select((idx - 1) % len(self.tabs))

    def _tab_from_widget(self, widget):
        for tab in self.tabs:
            if tab.frame == widget or str(tab.frame) == str(widget):
                return tab
        return self.tabs[0] if self.tabs else None

    def _tab_close_requested(self, pane_widget):
        """Called by the custom tab bar when the user clicks a tab's X."""
        tab = self._tab_from_widget(pane_widget)
        if tab:
            self.close_tab(tab)

    def _tab_context_menu(self, tab):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Close " + (os.path.basename(tab.path)
                                           if tab.path else "Tab"),
                         command=lambda: self.close_tab(tab))
        menu.add_command(label="Close Other Tabs", command=self._close_others)
        menu.add_separator()
        menu.add_command(label="Save", command=lambda: self._save_tab(tab))
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def _save_tab(self, tab):
        if tab.path:
            self._write(tab, tab.path)
        else:
            self.current_tab = tab
            self.save_as()

    def _on_tab_changed(self, event=None):
        idx = self.notebook_widget.select()
        if not idx:
            self.current_tab = None
            return
        self.current_tab = self._tab_from_widget(idx)
        if self.current_tab:
            self.lang_var.set(self.current_tab.language)
            self._update_status()
            try:
                self.current_tab.text.focus_set()
            except Exception:
                pass
        self._update_title()

    def _on_tab_right_click(self, event=None):
        # context menu fired by the custom tab bar (already on the right tab)
        tab = self.current_tab
        if tab:
            self._tab_context_menu(tab)

    def _close_others(self):
        current = self.current_tab
        for tab in list(self.tabs):
            if tab is not current:
                self.tabs.remove(tab)
                self.notebook_widget.forget(tab.frame)
                tab.close()
        self.current_tab = current
        self._on_tab_changed()

    # ------------------------------------------------------------------
    # Actions on current tab
    # ------------------------------------------------------------------
    def _call_tab(self, action):
        tab = self.current_tab
        if not tab:
            return
        text = tab.text
        if action == "undo":
            text.edit_undo()
        elif action == "redo":
            text.edit_redo()
        elif action == "cut":
            text.event_generate("<<Cut>>")
        elif action == "copy":
            text.event_generate("<<Copy>>")
        elif action == "paste":
            text.event_generate("<<Paste>>")
        elif action == "select_all":
            text.tag_add("sel", "1.0", "end")
        text.focus_set()

    def find(self):
        tab = self.current_tab
        if tab:
            self._show_find_dialog(show_replace=False)

    def replace(self):
        self._show_find_dialog(show_replace=True)

    def _find_dialog(self):
        return self._find_win

    def go_to_line(self):
        if not self.current_tab:
            return
        win = tk.Toplevel(self.root)
        win.title("Go to Line")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=self._theme()["bg_alt"])
        ttk.Label(win, text="Line number:").pack(padx=10, pady=(10, 2))
        entry = ttk.Entry(win)
        entry.pack(padx=10, pady=2)
        entry.focus_set()

        def do_go():
            try:
                line = int(entry.get())
                text = self.current_tab.text
                last = int(text.index("end-1c").split(".")[0])
                line = max(1, min(line, last))
                text.mark_set("insert", f"{line}.0")
                text.see(f"{line}.0")
                win.destroy()
            except ValueError:
                pass
        btn = ttk.Button(win, text="Go", command=do_go)
        btn.pack(pady=(2, 10))
        entry.bind("<Return>", lambda e: do_go())
        win.grab_set()

    def _show_find_dialog(self, show_replace=False):
        if not self.current_tab:
            return
        if getattr(self, "_find_win", None) and self._find_win.winfo_exists():
            self._find_win.lift()
            return
        c = self._theme()
        win = tk.Toplevel(self.root)
        win.title("Find" if not show_replace else "Find and Replace")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=c["bg_alt"])
        self._find_win = win

        ttk.Label(win, text="Find:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        find_entry = ttk.Entry(win, width=32)
        find_entry.grid(row=0, column=1, padx=6, pady=6)
        find_entry.focus_set()

        replace_entry = None
        if show_replace:
            ttk.Label(win, text="Replace:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
            replace_entry = ttk.Entry(win, width=32)
            replace_entry.grid(row=1, column=1, padx=6, pady=6)

        self.find_match_case = tk.BooleanVar(value=False)
        ttk.Checkbutton(win, text="Match case", variable=self.find_match_case).grid(
            row=2 if show_replace else 1, column=0, columnspan=2, padx=6, sticky="w")

        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=3 if show_replace else 2, column=0, columnspan=2, pady=6)

        def on_find():
            self._find_text(find_entry.get())

        def on_find_next():
            self._find_next(find_entry.get())

        def on_replace():
            if replace_entry:
                self._replace_one(find_entry.get(), replace_entry.get())

        def on_replace_all():
            if replace_entry:
                self._replace_all_found(find_entry.get(), replace_entry.get())

        ttk.Button(btn_frame, text="Find", command=on_find).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Next", command=on_find_next).pack(side=tk.LEFT, padx=3)
        if show_replace:
            ttk.Button(btn_frame, text="Replace", command=on_replace).pack(side=tk.LEFT, padx=3)
            ttk.Button(btn_frame, text="All", command=on_replace_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=3)

        find_entry.bind("<Return>", lambda e: on_find_next())
        win.grab_set()

    def _find_text(self, query):
        tab = self.current_tab
        if not tab or not query:
            return
        text = tab.text
        text.tag_remove("found", "1.0", "end")
        flags = 0 if self.find_match_case.get() else re.IGNORECASE
        content = text.get("1.0", "end")
        for m in re.finditer(re.escape(query), content, flags):
            s = f"1.0+{m.start()}c"
            e = f"1.0+{m.end()}c"
            text.tag_add("found", s, e)
        text.tag_config("found", background="#f4bf42", foreground="#000000")
        if text.tag_ranges("found"):
            text.see(text.tag_ranges("found")[0])

    def _find_next(self, query):
        tab = self.current_tab
        if not tab or not query:
            return
        text = tab.text
        text.tag_remove("found", "1.0", "end")
        flags = 0 if self.find_match_case.get() else re.IGNORECASE
        start = text.index(tk.INSERT)
        content_from = text.get(start, "end")
        m = re.search(re.escape(query), content_from, flags)
        if not m:
            content = text.get("1.0", "end")
            m = re.search(re.escape(query), content, flags)
            if not m:
                return
            s = f"1.0+{m.start()}c"
            e = f"1.0+{m.end()}c"
        else:
            s = f"{start}+{m.start()}c"
            e = f"{start}+{m.end()}c"
        text.tag_add("found", s, e)
        text.tag_config("found", background="#f4bf42", foreground="#000000")
        text.see(s)

    def _replace_one(self, find_text, replace_text):
        tab = self.current_tab
        if not tab or not find_text:
            return
        text = tab.text
        sel = text.tag_ranges("sel")
        flags = 0 if self.find_match_case.get() else re.IGNORECASE
        if sel:
            current = text.get(sel[0], sel[1])
            if re.fullmatch(re.escape(find_text), current, flags):
                text.delete(sel[0], sel[1])
                text.insert(sel[0], replace_text)
        self._find_next(find_text)

    def _replace_all_found(self, find_text, replace_text):
        tab = self.current_tab
        if not tab or not find_text:
            return
        text = tab.text
        flags = 0 if self.find_match_case.get() else re.IGNORECASE
        content = text.get("1.0", "end")
        new = re.sub(re.escape(find_text), replace_text, content, flags=flags)
        text.delete("1.0", "end")
        text.insert("1.0", new)
        tab._schedule_highlight()

    # ------------------------------------------------------------------
    # View actions
    # ------------------------------------------------------------------
    def _toggle_wrap(self):
        for tab in self.tabs:
            tab.text.configure(wrap=tk.WORD if self.wrap_var.get() else tk.NONE)

    def _toggle_theme(self):
        self.dark = not self.dark
        self._apply_theme()

    def _toggle_fullscreen(self):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def zoom_in(self):
        tab = self.current_tab
        if tab:
            if tab.font_size < 72:
                self._set_font_size(tab.font_size + 2)

    def zoom_out(self):
        tab = self.current_tab
        if tab:
            if tab.font_size > 6:
                self._set_font_size(tab.font_size - 2)

    def zoom_reset(self):
        self._set_font_size(12)

    def _set_font_size(self, size):
        for tab in self.tabs:
            tab.font_size = size
            tab.text.configure(font=("Consolas", size))
            tab.gutter.configure(font=("Consolas", size))
        if self.current_tab:
            self.current_tab.update_gutter()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _update_status(self):
        tab = self.current_tab
        if not tab:
            return
        try:
            pos = tab.text.index(tk.INSERT)
            line, col = pos.split(".")
            self.pos_label.config(text=f"Ln {line}, Col {int(col) + 1}")
            self.pos2_label.config(text=f"Ln {line}, Col {int(col) + 1}")
        except Exception:
            pass
        words = tab.count_words()
        self.word_label.config(text=f"{words} words")
        lang = tab.language
        if self.runner.is_running and self.running_tab is tab:
            lang = f"{tab.language} ● running"
        self.lang_label.config(text=lang)
        self.lang_var.set(tab.language)
        self.enc_label.config(text=getattr(tab, "enc", "UTF-8"))

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------
    def _load_recent(self):
        self.recent_files = []

    def _add_recent(self, path):
        path = os.path.abspath(path)
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:8]
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
        for p in self.recent_files:
            self.recent_menu.add_command(
                label=os.path.basename(p), command=lambda pp=p: self._open_path(pp))

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def show_about(self):
        AboutDialog(self.root, self.version)

    def show_shortcuts(self):
        c = self._theme()
        win = tk.Toplevel(self.root)
        win.title("Keyboard Shortcuts")
        win.geometry("520x520")
        win.transient(self.root)
        win.configure(bg=c["bg_alt"])
        win.grab_set()

        shortcuts = [
            ("Ctrl+N", "New File"),
            ("Ctrl+O", "Open File"),
            ("Ctrl+S", "Save"),
            ("Ctrl+Shift+S", "Save As"),
            ("Ctrl+Alt+S", "Save All"),
            ("Ctrl+W", "Close Tab"),
            ("Ctrl+Shift+W", "Close All"),
            ("Ctrl+Z / Ctrl+Y", "Undo / Redo"),
            ("Ctrl+X / C / V", "Cut / Copy / Paste"),
            ("Ctrl+A", "Select All"),
            ("Ctrl+F", "Find"),
            ("Ctrl+H", "Replace"),
            ("Ctrl+G", "Go to Line"),
            ("Ctrl+Tab / Ctrl+Shift+Tab", "Next / Previous Tab"),
            ("Ctrl+= / Ctrl+- / Ctrl+0", "Zoom In / Out / Reset"),
            ("Ctrl+Shift+T", "Toggle Theme"),
            ("F11", "Fullscreen"),
        ]
        title = tk.Label(win, text="Keyboard Shortcuts", font=("Segoe UI", 13, "bold"),
                         bg=c["bg_alt"], fg=c["fg_strong"])
        title.pack(pady=(14, 8))

        frame = tk.Frame(win, bg=c["bg_alt"])
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
        scroll = tk.Scrollbar(frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(frame, font=("Consolas", 10), bg=c["bg"], fg=c["fg"],
                       yscrollcommand=scroll.set, border=0, padx=10, pady=6)
        scroll.config(command=text.yview)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for key, desc in shortcuts:
            text.insert(tk.END, f"{key:<24}{desc}\n")
        text.config(state=tk.DISABLED)

        close = ttk.Button(win, text="Close", command=win.destroy)
        close.pack(pady=10)

    def _quit(self):
        try:
            self.runner.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    window = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
