# CodePad
# CodePad

A modern text and code editor built with **Python and Tkinter** — no extra
dependencies, runs on Windows / macOS / Linux wherever Python has Tkinter.

## Run it

```
python main.py            # or double-click CodePad.bat (Windows)
python main.py file.py    # open files directly
```

## Features

- **Tabbed editing** — open multiple files, switch with `Ctrl+Tab`
- **Syntax highlighting (21 languages)** — Python, JavaScript, TypeScript,
  Java, C, C++, C#, Go, Rust, HTML, CSS, JSON, Markdown, PHP, Ruby, SQL,
  Shell, XML, YAML, Lua + plain text
- **Autocomplete** — keyword- and document-based suggestions pop up as you type
- **Modern UI** — clean dark/light theme, styled tabs, toolbar and status bar
- **Full editing** — find/replace, go to line, undo/redo, word wrap,
  line numbers, word count
- **Shortcuts** — see Help → Keyboard Shortcuts

## Layout

```
main.py                 entry point
editor/
  __init__.py           package metadata
  theme.py              dark & light color themes
  syntax.py             multi-language tokenizer / highlighter
  autocomplete.py       completion engine
  editor.py             editable tab widget + highlighting + autocomplete
  main_window.py        main window: menus, toolbar, tabs, status bar, actions
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N / Ctrl+O | New / Open file |
| Ctrl+S / Ctrl+Shift+S | Save / Save As |
| Ctrl+Alt+S | Save All |
| Ctrl+W / Ctrl+Shift+W | Close Tab / Close All |
| Ctrl+Z, Ctrl+Y | Undo / Redo |
| Ctrl+X / C / V | Cut / Copy / Paste |
| Ctrl+A | Select All |
| Ctrl+F / Ctrl+H | Find / Replace |
| Ctrl+G | Go to Line |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / Previous tab |
| Ctrl+= / Ctrl+- / Ctrl+0 | Zoom In / Out / Reset |
| Ctrl+Shift+T | Toggle theme |
| F11 | Fullscreen |
