"""Modern dark & light themes for the editor.

Centralizes all colors so the UI is consistent and easy to re-theme.
Each theme is a dict of named colors used across widgets.
"""


class Theme:
    DARK = {
        "bg": "#1e1e1e",            # main window / editor background
        "bg_alt": "#252526",        # panels, status bar
        "bg_highlight": "#333333",  # hover, selection in menus/lists
        "bg_widget": "#2d2d30",     # inputs, toolbars
        "fg": "#d4d4d4",            # main text
        "fg_muted": "#858585",      # line numbers, secondary
        "fg_strong": "#ffffff",     # titles, active tab
        "accent": "#0e639c",        # primary accent (panels, focus)
        "accent_alt": "#1177bb",    # brighter accent
        "selection": "#264f78",     # text selection
        "caret": "#ffffff",
        "tab_active_bg": "#1e1e1e",
        "tab_inactive_bg": "#2d2d30",
        "border": "#3c3c3c",
        "error": "#f14c4c",
        # syntax colors
        "keyword": "#569cd6",
        "string": "#ce9178",
        "comment": "#6a9955",
        "number": "#b5cea8",
        "function": "#dcdcaa",
        "class": "#4ec9b0",
        "variable": "#9cdcfe",
        "operator": "#d4d4d4",
        "builtin": "#4fc1ff",
        "decorator": "#c586c0",
        "constant": "#569cd6",
        "type": "#4ec9b0",
        "preproc": "#c586c0",
    }

    LIGHT = {
        "bg": "#ffffff",
        "bg_alt": "#f3f3f3",
        "bg_highlight": "#e0e0e0",
        "bg_widget": "#ffffff",
        "fg": "#000000",
        "fg_muted": "#808080",
        "fg_strong": "#000000",
        "accent": "#0078d7",
        "accent_alt": "#005fb8",
        "selection": "#add6ff",
        "caret": "#000000",
        "tab_active_bg": "#ffffff",
        "tab_inactive_bg": "#ececec",
        "border": "#d4d4d4",
        "error": "#e51400",
        # syntax colors
        "keyword": "#0000ff",
        "string": "#a31515",
        "comment": "#008000",
        "number": "#098658",
        "function": "#795e26",
        "class": "#267f99",
        "variable": "#001080",
        "operator": "#000000",
        "builtin": "#267f99",
        "decorator": "#af00db",
        "constant": "#0000ff",
        "type": "#267f99",
        "preproc": "#af00db",
    }
