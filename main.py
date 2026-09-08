#!/usr/bin/env python3
"""CodePad -- a modern text & code editor.

Run with:  python main.py [file1 file2 ...]
"""

import sys
import tkinter as tk

from editor.main_window import MainWindow
from editor import __version__


def main():
    files = sys.argv[1:]
    root = tk.Tk()
    window = MainWindow(root)
    for path in files:
        window._open_path(path)
    root.mainloop()


if __name__ == "__main__":
    main()
