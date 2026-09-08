"""Output console / terminal panel shown at the bottom of the editor.

Displays program output and errors, and acts as a stdin terminal while a
process is running: type a line, press Enter, and it is sent to the child
process (e.g. Python's ``input()``).

VS Code-ish terminal features:
  * type-ahead input while the program runs (Enter submits the current line)
  * Ctrl+C interrupts/stops the running program
  * auto-scroll on new output (toggleable)
  * word-wrap on/off
  * font zoom (Ctrl+= / Ctrl+- / Ctrl+0)
  * right-click context menu (Copy / Select All / Clear / toggles)
  * running status indicator
"""

import tkinter as tk
from tkinter import ttk

from .theme import Theme

_BASE_FONT = ("Consolas", 10)
_STATUS_RUNNING = "#4ec9b0"
_STATUS_IDLE = "#76a3b8"


class OutputConsole(ttk.Frame):
    def __init__(self, master, style_name="TFrame", **kwargs):
        super().__init__(master, style=style_name, **kwargs)
        self._input_mode = False
        self._typed = ""
        self._input_handler = None
        self._interrupt_handler = None
        self._autoscroll = True
        self._wrap_var = tk.BooleanVar(value=True)
        self._scroll_var = tk.BooleanVar(value=True)
        self._font_size = 10
        self._idle_fg = Theme.DARK["fg_muted"]
        self._bar_bg = Theme.DARK["bg_alt"]

        # toolbar
        bar = ttk.Frame(self, style=style_name)
        bar.pack(side=tk.TOP, fill=tk.X)

        self.mode_label = tk.Label(bar, text="● OUTPUT",
                                   bg=self._bar_bg, fg=self._idle_fg,
                                   font=("Segoe UI", 9, "bold"))
        self.mode_label.pack(side=tk.LEFT, padx=(8, 2), pady=2)

        ttk.Button(bar, text="Clear", style="Toolbar.TButton",
                   width=6, command=self.clear).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar, text="Copy", style="Toolbar.TButton",
                   width=6, command=self.copy_all).pack(side=tk.RIGHT, padx=2)
        ttk.Checkbutton(bar, text="Wrap", variable=self._wrap_var,
                        style="Toolbar.TButton",
                        command=self._toggle_wrap).pack(side=tk.RIGHT, padx=2)
        ttk.Checkbutton(bar, text="Auto-scroll", variable=self._scroll_var,
                        style="Toolbar.TButton",
                        command=self._toggle_autoscroll).pack(side=tk.RIGHT, padx=2)

        # text area
        body = ttk.Frame(self, style=style_name)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.text = tk.Text(
            body, wrap=tk.WORD, state=tk.DISABLED,
            font=_BASE_FONT,
            bg=Theme.DARK["bg"], fg=Theme.DARK["fg"],
            insertbackground=Theme.DARK["caret"],
            selectbackground=Theme.DARK["selection"],
            selectforeground=Theme.DARK["fg"],
            border=0, highlightthickness=1, highlightbackground=Theme.DARK["border"],
            padx=8, pady=6,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.text.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=vsb.set)

        self.text.tag_config("err", foreground="#f14c4c")
        self.text.tag_config("cmd", foreground="#858585")

        # keyboard / mouse bindings (all guarded by input mode)
        self.text.bind("<Return>", self._on_return, add="+")
        self.text.bind("<KeyPress>", self._on_key, add="+")
        self.text.bind("<KeyRelease>", self._on_keyrelease, add="+")
        self.text.bind("<Button-1>", self._on_click, add="+")
        self.text.bind("<Control-c>", self._on_ctrl_c, add="+")
        self.text.bind("<Control-Key-equal>", self._zoom_in, add="+")
        self.text.bind("<Control-Key-plus>", self._zoom_in, add="+")
        self.text.bind("<Control-Key-KP_Add>", self._zoom_in, add="+")
        self.text.bind("<Control-Key-minus>", self._zoom_out, add="+")
        self.text.bind("<Control-Key-KP_Subtract>", self._zoom_out, add="+")
        self.text.bind("<Control-Key-0>", self._zoom_reset, add="+")
        self.text.bind("<Control-Key-KP_0>", self._zoom_reset, add="+")
        self.text.bind("<Button-3>", self._context_menu, add="+")
        self._build_context_menu()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def set_input_handler(self, fn):
        """Set callable(line) that submits one input line to the process."""
        self._input_handler = fn

    def set_interrupt_handler(self, fn):
        """Set callable() invoked by Ctrl+C in the terminal."""
        self._interrupt_handler = fn

    def set_running(self, running):
        """Update the status indicator shown in the toolbar."""
        self.mode_label.config(
            text=("● RUNNING" if running else "● OUTPUT"),
            fg=(_STATUS_RUNNING if running else self._idle_fg))

    def start_input_mode(self):
        """Enter terminal mode so the user can type input for the program."""
        if self._input_mode:
            return
        self._input_mode = True
        self._typed = ""
        self._insert("\n> ", "cmd")
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.see(tk.END)
        try:
            self.text.focus_set()
        except Exception:
            pass

    def end_input_mode(self):
        """Leave terminal mode and make the console read-only again."""
        if self._input_mode:
            self._typed = ""
            self._insert("\n", "cmd")
        self._input_mode = False
        self.text.configure(state=tk.DISABLED)

    def write(self, text, tag=None):
        self._insert(text, tag)

    def write_error(self, text):
        self.write(text, "err")

    def clear(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if self._input_mode:
            self._typed = ""
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.configure(state=tk.NORMAL if self._input_mode else tk.DISABLED)

    def copy_all(self):
        self.root().clipboard_clear()
        self.root().clipboard_append(self.text.get("1.0", "end-1c"))

    def copy_selection(self):
        try:
            sel = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            sel = None
        if sel:
            self.root().clipboard_clear()
            self.root().clipboard_append(sel)
        else:
            self.copy_all()

    def select_all(self):
        self.text.tag_add("sel", "1.0", "end")
        self.text.mark_set(tk.INSERT, "end")

    # ------------------------------------------------------------------
    # theming
    # ------------------------------------------------------------------
    def set_theme(self, c):
        self._idle_fg = c["fg_muted"]
        self._bar_bg = c["bg_alt"]
        self.mode_label.config(bg=self._bar_bg)
        if self._input_mode or self._running():
            self.mode_label.config(fg=_STATUS_RUNNING)
        else:
            self.mode_label.config(fg=self._idle_fg)
        self.text.configure(bg=c["bg"], fg=c["fg"],
                            insertbackground=c["caret"],
                            selectbackground=c["selection"],
                            selectforeground=c["fg"],
                            highlightbackground=c["border"])
        self.text.tag_config("err", foreground=c["error"])
        self.text.tag_config("cmd", foreground=c["fg_muted"])

    def _running(self):
        return self.mode_label.cget("text").startswith("● RUNNING")

    # ------------------------------------------------------------------
    # input handling
    # ------------------------------------------------------------------
    def _submit_input(self):
        if not self._input_mode:
            return
        line = self._typed
        self._typed = ""
        self._insert("\n", "cmd")
        if line and self._input_handler:
            try:
                self._input_handler(line + "\n")
            except Exception:
                pass
        if self._input_mode:
            self._insert("> ", "cmd")
            self.text.mark_set(tk.INSERT, tk.END)
            self.text.see(tk.END)

    def _handle_type(self, ch):
        """Append one typed character to the trailing input line."""
        if not self._input_mode:
            return
        self._typed += ch
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, ch)
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.see(tk.END)
        if not self._input_mode:
            self.text.configure(state=tk.DISABLED)

    def _handle_backspace(self):
        if not self._input_mode or not self._typed:
            return
        self._typed = self._typed[:-1]
        self.text.configure(state=tk.NORMAL)
        try:
            # Text keeps an implicit trailing newline, so the last typed
            # char sits between end-2c and end-1c.
            self.text.delete("end-2c", "end-1c")
        except tk.TclError:
            pass
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.see(tk.END)

    def _typed_end_index(self):
        """Index just before the user's typed input (kept glued to the end)."""
        if not self._typed:
            return tk.END
        # Text keeps an implicit trailing newline, so the typed chars occupy
        # (end-(N+1)c, end-1c); insert before them lands at end-(N+1)c.
        return self.text.index("end-%dc" % (len(self._typed) + 1))

    def _on_return(self, event):
        if self._input_mode:
            self._submit_input()
        return "break"

    def _on_key(self, event):
        if not self._input_mode:
            return None
        if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R",
                            "Alt_L", "Alt_R", "Caps_Lock"):
            return None
        if event.keysym == "BackSpace":
            self._handle_backspace()
            return "break"
        if event.char and len(event.char) == 1 and ord(event.char) >= 32:
            self._handle_type(event.char)
            return "break"
        return None

    def _on_keyrelease(self, event):
        if not self._input_mode:
            return
        self.text.mark_set(tk.INSERT, tk.END)

    def _on_click(self, event):
        if self._input_mode:
            self.text.mark_set(tk.INSERT, tk.END)
            return "break"
        return None

    def _on_ctrl_c(self, event):
        if self._input_mode and self._interrupt_handler:
            try:
                self._interrupt_handler()
            except Exception:
                pass
            return "break"
        return None

    # ------------------------------------------------------------------
    # view options / zoom / context menu
    # ------------------------------------------------------------------
    def _toggle_wrap(self):
        self.text.configure(wrap=tk.WORD if self._wrap_var.get() else "none")

    def _toggle_autoscroll(self):
        self._autoscroll = self._scroll_var.get()

    def _set_font_size(self, size):
        self._font_size = max(6, min(28, size))
        self.text.configure(font=(_BASE_FONT[0], self._font_size))

    def _zoom_in(self, event=None):
        self._set_font_size(self._font_size + 1)
        return "break"

    def _zoom_out(self, event=None):
        self._set_font_size(self._font_size - 1)
        return "break"

    def _zoom_reset(self, event=None):
        self._set_font_size(10)
        return "break"

    def _build_context_menu(self):
        self._ctx = tk.Menu(self.text, tearoff=0)
        self._ctx.add_command(label="Copy", command=self.copy_selection)
        self._ctx.add_command(label="Select All", command=self.select_all)
        self._ctx.add_separator()
        self._ctx.add_checkbutton(label="Word Wrap", variable=self._wrap_var,
                                  command=self._toggle_wrap)
        self._ctx.add_checkbutton(label="Auto-scroll", variable=self._scroll_var,
                                  command=self._toggle_autoscroll)
        self._ctx.add_separator()
        self._ctx.add_command(label="Clear", command=self.clear)

    def _context_menu(self, event):
        try:
            self._ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx.grab_release()

    def _insert(self, text, tag=None):
        self.text.configure(state=tk.NORMAL)
        # while typing, stream output in *above* the input line so the
        # user's typed text (and backspace) stays intact at the end
        if self._input_mode and self._typed:
            where = self._typed_end_index()
        else:
            where = tk.END
        self.text.insert(where, text, tag)
        if self._input_mode or self._autoscroll:
            self.text.see(tk.END)
        if not self._input_mode:
            self.text.configure(state=tk.DISABLED)

    def root(self):
        return self.winfo_toplevel()