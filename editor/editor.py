"""The editor widget with tabbed documents.

Each tab is an EditorTab holding its own Text widget plus per-language
syntax highlighting and autocomplete. A shared Notebook shows the tabs.
"""

import os
import re
import tkinter as tk
from tkinter import ttk

from . import syntax
from .autocomplete import Completer
from .theme import Theme


LANGUAGES = syntax.language_names()

_HIGHLIGHT_DELAY_MS = 300
_COMPLETE_MIN_CHARS = 1
_COMPLETE_DELAY_MS = 250

# open char -> closing char (auto-close pairs)
_PAIR_OPEN = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'", "`": "`"}
_PAIR_CLOSE = set(_PAIR_OPEN.values())
# opens that trigger multi-line smart-Enter expansion
_SMART_ENTER_OPENS = {"{", "(", "["}


class EditorTab:
    """A single open document."""

    def __init__(self, notebook, path=None, content="", language=None):
        self.notebook = notebook
        self.path = path
        self.language = language or (
            syntax.language_for_path(path) if path else "Plain Text"
        )
        self.content = content

        self.create_widgets()
        self.highlighter = syntax.Highlighter(self.text, Theme.DARK)
        self.highlighter.apply_tags()
        self.completer = Completer(self.text)

        self.user_edit = False
        self._schedule_id = None
        self._complete_id = None
        self.font_size = 12
        self.scroll_pos = (0, 0)

    def create_widgets(self):
        frame = ttk.Frame(self.notebook)
        self.frame = frame

        # --- line numbers gutter ---
        self.gutter = tk.Text(
            frame, width=4, padx=5, pady=4, takefocus=0, border=0,
            state=tk.DISABLED, cursor="arrow", wrap="none",
            font=("Consolas", 12), background=Theme.DARK["bg_alt"],
            foreground=Theme.DARK["fg_muted"],
        )
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)

        # --- text area inside a sub-frame for auto-hiding scrollbars ---
        body = ttk.Frame(frame)
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.text = tk.Text(
            body, wrap=tk.WORD, undo=True, padx=8, pady=4,
            font=("Consolas", 12),
            insertbackground=Theme.DARK["caret"],
            selectbackground=Theme.DARK["selection"],
            selectforeground=Theme.DARK["fg"],
            background=Theme.DARK["bg"],
            foreground=Theme.DARK["fg"],
            border=0, highlightthickness=0, tabs=60,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.vsb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.text.yview)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 1), pady=1)
        self.text.configure(yscrollcommand=self._on_yview)

        self.hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.text.xview)
        self.hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.configure(xscrollcommand=self.hsb.set)

        if self.content:
            self.text.insert("1.0", self.content)
        else:
            self.content = ""
        self.text.edit_reset()

        self.bind_events()
        self.update_gutter()

    def _on_yview(self, first, last):
        self.vsb.set(first, last)
        self.update_gutter()

    def bind_events(self):
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_key_release)
        self.text.bind("<KeyPress>", self._on_key_press)
        self.text.bind("<ButtonRelease-1>", self._on_button_release)
        self.text.bind("<MouseWheel>", self._on_mousewheel)
        self.text.bind("<<Paste>>", self._on_paste)
        self.text.bind("<<Cut>>", self._on_cut)
        self.text.bind("<FocusOut>", self._cancel_completion, add="+")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_modified(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.user_edit = True
            self.update_gutter()
            self.notebook.event_generate("<<DocumentModified>>")
            self._schedule_highlight()

    def _on_key_release(self, event=None):
        if event and event.keysym in ("Shift_L", "Shift_R", "Control_L",
                                      "Control_R", "Alt_L", "Alt_R"):
            return
        self._update_cursor_status()
        self.notebook.event_generate("<<CursorMoved>>")
        if event and event.char and (event.char.isalnum() or event.keysym in ("period", "underscore")):
            self._schedule_completion()
        else:
            self._cancel_completion()

    def _on_key_press(self, event=None):
        if not event:
            return
        ks = event.keysym

        if ks == "Escape":
            self._cancel_completion()
            return

        # ---- Backspace: delete auto-closed pair ----
        if ks == "BackSpace":
            if self._handle_delete_pair(backward=True):
                return "break"
            self._schedule_highlight()
            return

        # ---- Delete (forward): skip over a pair and delete it ----
        if ks == "Delete":
            if self._handle_delete_pair(backward=False):
                return "break"
            self._schedule_highlight()
            return

        # ---- Tab / Shift+Tab: indent / outdent or insert tab ----
        if ks == "Tab" or ks == "ISO_Left_Tab":
            if self._handle_tab(event):
                return "break"
            return

        # ---- Return: smart auto-indent inside brackets ----
        if ks == "Return":
            self._auto_indent()
            return "break"

        # ---- Auto-close pairs / wrap selection ----
        if event.char and event.char in _PAIR_OPEN:
            if self.text.tag_ranges("sel"):
                self._wrap_selection(event.char)
                self._schedule_highlight()
                return "break"
            self._insert_open_pair(event.char)
            self._schedule_highlight()
            return "break"

        # ---- Jump over an already-closed pair ----
        if event.char and event.char in _PAIR_CLOSE:
            if self.text.tag_ranges("sel"):
                return
            if self._jump_over_closing(event.char):
                self._schedule_highlight()
                return "break"

        self._schedule_highlight()

    # ------------------------------------------------------------------
    # Pair helpers
    # ------------------------------------------------------------------
    def _insert_open_pair(self, char):
        """Type an opening bracket and its matching closer."""
        closer = _PAIR_OPEN[char]
        insert = self.text.index(tk.INSERT)
        self.text.insert(insert, char + closer)
        self.text.mark_set(tk.INSERT, f"{insert}+1c")
        self.text.see(tk.INSERT)

    def _wrap_selection(self, char):
        """Wrap the current selection with opening/closing pair."""
        closer = _PAIR_OPEN[char]
        sel_start = self.text.index(tk.SEL_FIRST)
        sel_end = self.text.index(tk.SEL_LAST)
        # place the pair around the selection and re-select inner text
        self.text.insert(sel_end, closer)
        self.text.insert(sel_start, char)
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", f"{sel_start}+1c", f"{sel_end}+1c")
        self.text.mark_set(tk.INSERT, f"{sel_end}+1c")

    def _jump_over_closing(self, char):
        """If the char just after the cursor matches 'char', jump past it."""
        insert = self.text.index(tk.INSERT)
        after = self.text.get(insert, f"{insert}+1c")
        if after == char:
            self.text.mark_set(tk.INSERT, f"{insert}+1c")
            return True
        return False

    def _handle_delete_pair(self, backward):
        """When deleting, remove an auto-closed pair as a unit.

        backward=True  -> Backspace, cursor sits between open and close.
        backward=False -> Delete, cursor sits right before an open pair.
        """
        # If there is a selection, let the default behavior delete it.
        if self.text.tag_ranges("sel"):
            return False
        insert = self.text.index(tk.INSERT)
        if backward:
            left = self.text.get(f"{insert}-1c", insert)
            right = self.text.get(insert, f"{insert}+1c")
            expected = _PAIR_OPEN.get(left)
            if expected and right == expected:
                self.text.delete(f"{insert}-1c", f"{insert}+1c")
                self._schedule_highlight()
                return True
            return False
        else:
            here = self.text.get(insert, f"{insert}+1c")
            nextc = self.text.get(f"{insert}+1c", f"{insert}+2c")
            expected = _PAIR_OPEN.get(here)
            if expected and nextc == expected:
                self.text.delete(insert, f"{insert}+2c")
                self._schedule_highlight()
                return True
            return False

    def _on_button_release(self, event=None):
        self._update_cursor_status()
        self.notebook.event_generate("<<CursorMoved>>")
        self._cancel_completion()

    def _on_mousewheel(self, event):
        self.update_gutter()

    def _on_paste(self, event=None):
        self.notebook.after(10, lambda: self._schedule_highlight())

    def _on_cut(self, event=None):
        self.notebook.after(10, lambda: self._schedule_highlight())

    # ------------------------------------------------------------------
    # Editor behaviors
    # ------------------------------------------------------------------
    def _handle_tab(self, event=None):
        c = self.text
        # Shift+Tab -> outdent
        if event and getattr(event, "keysym", "") == "ISO_Left_Tab":
            self._outdent_selection()
            self._schedule_highlight()
            return True

        if self.text.tag_ranges("sel"):
            self._indent_selection()
            self._schedule_highlight()
            return True

        indent = " " * 4
        self.text.insert(tk.INSERT, indent)
        self._schedule_highlight()
        return True

    def _indent_selection(self):
        start = self.text.index(tk.SEL_FIRST)
        end = self.text.index(tk.SEL_LAST)
        first_line = int(start.split(".")[0])
        last_line = int(end.split(".")[0])
        for ln in range(first_line, last_line + 1):
            self.text.insert(f"{ln}.0", "    ", "adj")

    def _outdent_selection(self):
        start = self.text.index(tk.SEL_FIRST)
        end = self.text.index(tk.SEL_LAST)
        first_line = int(start.split(".")[0])
        last_line = int(end.split(".")[0])
        for ln in range(first_line, last_line + 1):
            line = self.text.get(f"{ln}.0", f"{ln}.end")
            stripped = line[:4]
            if stripped.startswith("    "):
                self.text.delete(f"{ln}.0", f"{ln}.4")
            elif stripped.startswith("\t"):
                self.text.delete(f"{ln}.0", f"{ln}.1")

    def _auto_indent(self):
        index = self.text.index(tk.INSERT)
        line_start = index.split(".")[0]
        line = self.text.get(f"{line_start}.0", f"{line_start}.end")
        col = int(index.split(".")[1])

        # smart indent inside an auto-closed bracket pair: "{|}"
        left = self.text.get(f"{index}-1c", index)
        right = self.text.get(index, f"{index}+1c")
        closer = _PAIR_OPEN.get(left)
        if left in _SMART_ENTER_OPENS and closer and right == closer:
            base = re.match(r'^\s*', line).group(0)
            indent = base + "    "
            self.text.insert(index, f"\n{indent}\n{base}")
            new_pos = f"{line_start}.{col + len(indent) + 1}"
            self.text.mark_set(tk.INSERT, new_pos)
            self._schedule_highlight()
            self._update_cursor_status()
            return True

        leading = re.match(r'^\s*', line).group(0)
        text_before = line[:col].rstrip()

        if text_before.endswith(":"):
            # block language: indent one level after a colon
            indent = leading + "    "
        else:
            indent = leading

        self.text.insert(index, "\n" + indent)
        new_line = int(index.split(".")[0]) + 1
        self.text.mark_set(tk.INSERT, f"{new_line}.{len(indent)}")
        self._schedule_highlight()
        self._update_cursor_status()
        return True

    # ------------------------------------------------------------------
    # Highlighting
    # ------------------------------------------------------------------
    def _schedule_highlight(self):
        if self._schedule_id:
            self.text.after_cancel(self._schedule_id)
        self._schedule_id = self.text.after(_HIGHLIGHT_DELAY_MS, self._do_highlight)

    def _do_highlight(self):
        self._schedule_id = None
        compiled = syntax.compile_language(self.language)
        self.highlighter.highlight(compiled)

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------
    def _schedule_completion(self):
        if self._complete_id:
            self.text.after_cancel(self._complete_id)
        self._complete_id = self.text.after(_COMPLETE_DELAY_MS, self._maybe_show_completion)

    def _maybe_show_completion(self):
        self._complete_id = None
        prefix = self._current_prefix()
        if len(prefix) < _COMPLETE_MIN_CHARS:
            self._cancel_completion()
            return
        matches = self.completer.word_matches(prefix, self.language)
        if not matches:
            self._cancel_completion()
            return
        self._show_completion_popup(matches, prefix)

    def _current_prefix(self):
        idx = self.text.index(tk.INSERT)
        line = idx.split(".")[0]
        start = idx.split(".")[1]
        text = self.text.get(f"{line}.0", f"{line}.{start}")
        m = re.search(r'\b[A-Za-z_][A-Za-z0-9_]*$', text)
        return m.group(0) if m else ""

    def _show_completion_popup(self, matches, prefix):
        self._completion_prefix = prefix
        self.completer.matches = matches
        self.completer.current_idx = 0

        if not self.completer.listbox or not self.completer.listbox.winfo_exists():
            top = tk.Toplevel(self.text)
            top.withdraw()
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            lb = tk.Listbox(
                top, activestyle="none", height=min(10, len(matches)),
                font=("Consolas", 11),
                bg=Theme.DARK["bg_widget"], fg=Theme.DARK["fg"],
                selectbackground=Theme.DARK["accent"],
                selectforeground="#ffffff",
                highlightthickness=1, highlightbackground=Theme.DARK["border"],
                border=0,
            )
            lb.pack(fill=tk.BOTH, expand=True)
            self.completer.listbox = lb
            self.completer.top = top

            lb.bind("<Return>", self._apply_completion)
            lb.bind("<Tab>", self._apply_completion)
            lb.bind("<Up>", self._move_completion_up)
            lb.bind("<Down>", self._move_completion_down)
            lb.bind("<Escape>", lambda e: self._cancel_completion() or "break")
            lb.bind("<Double-Button-1>", self._apply_completion)
            lb.bind("<Button-1>", lambda e: self._move_to_click(e))
        else:
            lb = self.completer.listbox
            top = self.completer.top

        lb.delete(0, tk.END)
        for m in matches:
            lb.insert(tk.END, m)
        lb.selection_set(0)
        lb.activate(0)

        self._position_popup(top, lb)

    def _position_popup(self, top, lb):
        insert_idx = self.text.index(tk.INSERT)
        try:
            bbox = self.text.bbox(insert_idx)
            x = self.text.winfo_rootx() + bbox[0]
            y = self.text.winfo_rooty() + bbox[1] + bbox[3]
        except Exception:
            x = self.text.winfo_rootx() + 10
            y = self.text.winfo_rooty() + 10
        top.geometry(f"+{x}+{y}")
        top.deiconify()

    def _move_completion_up(self, event):
        idx = self.completer.current_idx
        if idx > 0:
            idx -= 1
            self.completer.current_idx = idx
            lb = self.completer.listbox
            lb.selection_clear(0, tk.END)
            lb.selection_set(idx)
            lb.see(idx)
        return "break"

    def _move_completion_down(self, event):
        idx = self.completer.current_idx
        lb = self.completer.listbox
        if idx < lb.size() - 1:
            idx += 1
            self.completer.current_idx = idx
            lb.selection_clear(0, tk.END)
            lb.selection_set(idx)
            lb.see(idx)
        return "break"

    def _move_to_click(self, event):
        lb = self.completer.listbox
        idx = lb.nearest(event.y)
        self.completer.current_idx = idx
        lb.selection_clear(0, tk.END)
        lb.selection_set(idx)

    def _apply_completion(self, event):
        lb = self.completer.listbox
        sel = lb.curselection()
        if not sel:
            self._cancel_completion()
            return "break"
        word = lb.get(sel[0])
        prefix = getattr(self, "_completion_prefix", "")
        self.text.delete(f"insert-{len(prefix)}c", tk.INSERT)
        self.text.insert(tk.INSERT, word)
        self._cancel_completion()
        self._schedule_highlight()
        return "break"

    def _cancel_completion(self, event=None):
        lb = getattr(self.completer, "listbox", None)
        top = getattr(self.completer, "top", None)
        if lb and lb.winfo_exists():
            lb.master.destroy()
        self.completer.listbox = None
        self.completer.top = None
        self.completer.active = False
        return True

    # ------------------------------------------------------------------
    # Gutter / status
    # ------------------------------------------------------------------
    def update_gutter(self):
        self.gutter.config(state=tk.NORMAL)
        self.gutter.delete("1.0", tk.END)
        i = self.text.index("@0,0")
        while True:
            dline = self.text.dlineinfo(i)
            if dline is None:
                break
            line_num = str(i).split(".")[0]
            self.gutter.insert(tk.END, f"{line_num}\n")
            i = self.text.index(f"{i}+1line")
        self.gutter.config(state=tk.DISABLED)

    def _update_cursor_status(self):
        pos = self.text.index(tk.INSERT)
        line, col = pos.split(".")
        self.cursor_status = (int(line), int(col))
        self.notebook.event_generate("<<CursorMoved>>")

    def count_words(self):
        content = self.text.get("1.0", "end").strip()
        return len(content.split()) if content else 0

    def set_theme(self, theme_colors):
        self.text.config(
            background=theme_colors["bg"],
            foreground=theme_colors["fg"],
            insertbackground=theme_colors["caret"],
            selectbackground=theme_colors["selection"],
            selectforeground=theme_colors["fg"],
            inactiveselectbackground=theme_colors["selection"],
        )
        self.gutter.config(
            background=theme_colors["bg_alt"],
            foreground=theme_colors["fg_muted"],
        )
        self.highlighter.set_theme(theme_colors)

    def get_content(self):
        return self.text.get("1.0", "end-1c")

    def set_focus(self):
        self.text.focus_set()

    def close(self):
        for cid in (self._schedule_id, self._complete_id):
            if cid:
                try:
                    self.text.after_cancel(cid)
                except Exception:
                    pass
        if self.completer.listbox:
            try:
                self.completer.listbox.master.destroy()
            except Exception:
                pass
        self.frame.destroy()


class EditorNotebook:
    """Wraps a ttk.Notebook with modern-styled tabs and tab management."""

    def __init__(self, *args, **kwargs):
        self.notebook = ttk.Notebook(*args, **kwargs)
        self.notebook.enable_traversal()

    @property
    def control(self):
        return self.notebook

    def add_tab(self, tab, title):
        self.notebook.add(tab.frame, text=title)
        self._update_tab_styling()

    def select(self, tab):
        self.notebook.select(tab.frame)

    def index_of(self, tab):
        return self.notebook.index(tab.frame)

    def current_tab(self):
        idx = self.notebook.select()
        if not idx:
            return None
        return self.notebook._nametowidget(idx).master

    def _update_tab_styling(self):
        self.notebook.event_generate("<<TabChanged>>")

    def bind(self, *args, **kwargs):
        self.notebook.bind(*args, **kwargs)


def make_tab(notebook, path=None, content="", language=None):
    tab = EditorTab(notebook, path=path, content=content, language=language)
    return tab
