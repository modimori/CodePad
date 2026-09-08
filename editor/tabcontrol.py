"""Custom tabbed container.

A drop-in replacement for ttk.Notebook that draws its own tab bar. Each tab
is a small frame with a title label and a close (X) button that appears on
hover. Works on every Tk build (the ttk.Notebook ``-window`` tab option is
not available everywhere).

The API mirrors the subset of ttk.Notebook used by the editor:
  add(widget, text=...)
  select(widget_or_index)
  index(widget_or_index_or_"current")
  tab(widget_or_index, text=...)          # getter returns {'text': ...}
  forget(widget)
  bind(event, handler)
  after/event_generate (inherited from tk.Frame)

Extra:
  set_theme(c)          -- restyle for a theme dict
  on_close(widget)      -- callback(widget) fired when the user closes a tab
"""

import tkinter as tk

from .theme import Theme

_FONT = ("Segoe UI", 9)
_CLOSE_GLYPH = "\u2715"


def _is_hovering(widget):
    try:
        x, y = widget.winfo_pointerx(), widget.winfo_pointery()
        return widget.winfo_containing(x, y) is widget
    except Exception:
        return False


class CustomNotebook(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.theme = Theme.DARK
        self.on_close = None

        self.bar = tk.Frame(self, bg=self.theme["bg_alt"])
        self.bar.pack(side=tk.TOP, fill=tk.X)

        self.stack = tk.Frame(self, bg=self.theme["bg"])
        self.stack.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self._children = []      # list of pane widgets (EditorTab.frames)
        self._nodes = {}         # widget str -> tab node frame
        self._active = None      # currently shown pane widget

        self.bar.bind("<Button-3>", self._bar_right_click)

    # ------------------------------------------------------------------
    # public API (ttk.Notebook compatible subset)
    # ------------------------------------------------------------------
    def add(self, child, text="", **kw):
        node = self._build_node(child, text)
        self._children.append(child)
        self._nodes[str(child)] = node
        if self._active is None:
            self.select(child)

    def select(self, tabid="current"):
        child = self._resolve(tabid)
        if child is None:
            return None
        if self._active is child:
            # already active: avoid redundant repack + re-entrant event
            self._restyle()
            return child
        if self._active is not None:
            self._active.pack_forget()
        self._active = child
        child.pack(in_=self.stack, fill=tk.BOTH, expand=True)
        child.lift()
        self._restyle()
        self.event_generate("<<NotebookTabChanged>>")
        return child

    def index(self, tabid="current"):
        if tabid == "current":
            if self._active is None:
                return 0
            for i, c in enumerate(self._children):
                if c is self._active:
                    return i
            return 0
        if isinstance(tabid, int):
            n = len(self._children)
            return tabid % n if n else 0
        if isinstance(tabid, str) and tabid.startswith("."):
            for i, c in enumerate(self._children):
                if str(c) == tabid:
                    return i
            return 0
        if isinstance(tabid, str) and tabid.startswith("@"):
            # coords -> index (approximation via identify)
            return self._identify_tab(tabid)
        for i, c in enumerate(self._children):
            if c is tabid:
                return i
        return 0

    def tab(self, tabid, **kw):
        child = self._resolve(tabid)
        if child is None:
            return {}
        node = self._nodes.get(str(child))
        if not kw:
            return {"text": node.lbl.cget("text") if node else ""}
        if "text" in kw:
            if node:
                node.lbl.config(text=kw["text"])
        return {}

    def forget(self, tabid):
        child = self._resolve(tabid)
        if child is None:
            return
        node = self._nodes.pop(str(child), None)
        if node:
            try:
                node.destroy()
            except Exception:
                pass
        if child in self._children:
            self._children.remove(child)
        if self._active is child:
            self._active = None
            if self._children:
                self.select(self._children[-1])
            else:
                self.event_generate("<<NotebookTabChanged>>")

    def set_theme(self, c):
        self.theme = c
        self.bar.config(bg=c["bg_alt"])
        self.stack.config(bg=c["bg"])
        self._restyle()

    # ------------------------------------------------------------------
    # node construction / theming
    # ------------------------------------------------------------------
    def _build_node(self, child, text):
        c = self.theme
        active = (self._active is child)
        bg = c["bg"] if active else c["tab_inactive_bg"]
        fg = c["fg_strong"] if active else c["fg_muted"]

        node = tk.Frame(self.bar, bg=bg, padx=0, pady=0)
        lbl = tk.Label(node, text=text, bg=bg, fg=fg, font=_FONT, padx=8)
        x = tk.Label(node, text=_CLOSE_GLYPH, bg=bg, fg=fg,
                     font=_FONT, cursor="hand2", padx=5)
        lbl.pack(side=tk.LEFT)
        x.pack_forget()

        node.lbl = lbl
        node.x = x
        node.tab_id = child

        node.pack(side=tk.LEFT, pady=(3, 0))

        # left-click selects the tab
        for w in (node, lbl):
            w.bind("<Button-1>", lambda e: self.select(child), add="+")
        # middle-click closes
        for w in (node, lbl):
            w.bind("<Button-2>", lambda e: self._fire_close(child), add="+")
        # right-click context menu
        for w in (node, lbl, x):
            w.bind("<Button-3>", lambda e: self._node_right_click(child), add="+")
        # hover shows/hides the X (tracking covers the whole node, including X)
        for w in (node, lbl, x):
            w.bind("<Enter>", self._hover_enter, add="+")
            w.bind("<Leave>", self._hover_leave, add="+")
        # X button styling
        x.bind("<Enter>", self._x_hover, add="+")
        x.bind("<Leave>", self._x_unhover, add="+")
        x.bind("<Button-1>", lambda e: self._fire_close(child), add="+")

        return node

    def _fire_close(self, child):
        self.select(child)
        if self.on_close:
            self.on_close(child)

    def _node_right_click(self, child):
        self.select(child)
        self.event_generate("<<TabContextMenu>>")

    def _bar_right_click(self, event):
        if self._active is not None:
            self.event_generate("<<TabContextMenu>>")

    def _hover_enter(self, event):
        node = self._node_of(event.widget)
        if node is None:
            return
        self._cancel_hide(node)
        if node.x.winfo_manager() != "pack":
            node.x.pack(side=tk.LEFT)

    def _hover_leave(self, event):
        # Ignore moves into a child of the widget itself (frame -> label).
        if getattr(event, "detail", "") == "NotifyInferior":
            return
        node = self._node_of(event.widget)
        if node is None:
            return
        self._cancel_hide(node)
        node._hide_job = self.after(140, lambda n=node: self._hide_unless_hovered(n))

    def _hide_unless_hovered(self, node):
        node._hide_job = None
        try:
            containing = node.winfo_containing(self.winfo_pointerx(),
                                               self.winfo_pointery())
        except Exception:
            containing = None
        # pointer still over the tab (label or X)? keep the X visible
        if self._node_of(containing) is node:
            return
        try:
            node.x.pack_forget()
        except Exception:
            pass

    def _cancel_hide(self, node):
        job = getattr(node, "_hide_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
            node._hide_job = None

    def _x_hover(self, event):
        node = self._node_of(event.widget)
        if node:
            node.x.config(fg="#f14c4c", bg=self.theme["bg_highlight"])
            self._cancel_hide(node)

    def _x_unhover(self, event):
        node = self._node_of(event.widget)
        if node:
            active = (node.tab_id is self._active)
            node.x.config(
                fg=self.theme["fg_strong"] if active else self.theme["fg_muted"],
                bg=self.theme["bg"] if active else self.theme["tab_inactive_bg"],
            )

    def _restyle(self):
        c = self.theme
        for child in self._children:
            node = self._nodes.get(str(child))
            if not node:
                continue
            active = (child is self._active)
            bg = c["bg"] if active else c["tab_inactive_bg"]
            fg = c["fg_strong"] if active else c["fg_muted"]
            node.config(bg=bg)
            node.lbl.config(bg=bg, fg=fg)
            if not _is_hovering(node.x):
                node.x.config(bg=bg, fg=fg)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _resolve(self, tabid):
        if isinstance(tabid, int):
            n = len(self._children)
            if n == 0:
                return None
            return self._children[tabid % n]
        if isinstance(tabid, str):
            if tabid == "current":
                return self._active
            if tabid.startswith("."):
                for c in self._children:
                    if str(c) == tabid:
                        return c
            if tabid.startswith("@"):
                return self._identify_tab(tabid)
            return None
        if tabid in self._children:
            return tabid
        return None

    def _identify_tab(self, coords):
        """coords of form '@x,y' -> index of tab under that pointer pos."""
        try:
            _, x, y = coords.replace("@", "").split(",")
            x, y = int(x), int(y)
        except Exception:
            return 0
        w = self.bar.winfo_containing(self.winfo_rootx() + x,
                                      self.winfo_rooty() + y)
        if w is None:
            return self.index("current")
        node = self._node_of(w)
        if node is None:
            return self.index("current")
        for i, c in enumerate(self._children):
            if str(c) == str(node.tab_id):
                return i
        return self.index("current")

    def _node_of(self, widget):
        w = widget
        while w is not None:
            if getattr(w, "tab_id", None) is not None:
                return w
            w = w.master
        return None