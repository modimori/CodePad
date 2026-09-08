"""Run source files with the appropriate interpreter per language.

Maps editor languages to the interpreter/compiler command and provides a
background process runner with streaming output.

Threading: the reader uses a thread + queue, and output is drained on the
main Tk thread via a periodic poll, which is the thread-safe Tkinter pattern.
"""

import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk


# language -> (command template, is_compiled)
# command template uses {file} for the script path.
_RUNNERS = {
    "Python":            ("{python} -u {file}", False),
    "JavaScript":        ("node {file}", False),
    "TypeScript":        ("node {file}", False),
    "HTML":              ("{browser} {file}", False),
    "Go":                ("go run {file}", False),
    "Rust":              ("cargo run 2>&1", False),
    "PHP":               ("php {file}", False),
    "Ruby":              ("ruby {file}", False),
    "Shell":             ("bash {file}", False),
    "SQL":               ("sqlite3 {file}", False),
    "C":                 ("cc {file} -o {base} && {base}", True),
    "C++":               ("c++ {file} -o {base} && {base}", True),
    "C#":                ("dotnet {file}", False),
    "Java":              ("java {file}", False),
    "Lua":               ("lua {file}", False),
    "Haxe":              ("haxe --interp {file}", False),
    "Perl":              ("perl {file}", False),
    "Swift":             ("swift {file}", False),
    "Kotlin":            ("kotlin {file}", False),
    "Scala":             ("scala {file}", False),
    "Dart":              ("dart run {file}", False),
    "R":                 ("Rscript {file}", False),
    "Julia":             ("julia {file}", False),
    "Elixir":            ("elixir {file}", False),
    "Haskell":           ("runghc {file}", False),
    "Clojure":           ("clojure {file}", False),
    "Erlang":            ("escript {file}", False),
    "Pascal":            ("fpc {file} -o{base} && {base}", True),
    "Bash":              ("bash {file}", False),
    "Batch":             ("cmd /c {file}", False),
}


def _find(prog):
    """Return the full path to an executable, or None if not found."""
    return shutil.which(prog)


def _python_bin():
    """The Python executable to launch scripts with.

    When frozen (PyInstaller), sys.executable is the app itself; use the
    host interpreter that built the bundle instead.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_base_executable", None)
        return base or "python"
    return sys.executable


def resolve_command(language, filepath, module_dirs):
    """Return (shell_command, env) to run a file for a language.

    Returns (None, None) if the language can't be run.
    """
    if not filepath:
        return None, None
    base = os.path.splitext(os.path.basename(filepath))[0]

    runner = _RUNNERS.get(language)
    if not runner:
        return None, None

    template, _is_compiled = runner

    cmd = template.format(
        python=_python_bin(),
        file=f'"{filepath}"',
        base=base,
        browser=_find("start") or "start",
    )

    extra_env = None
    if language == "Python" and module_dirs:
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        joined = os.pathsep.join(module_dirs)
        env["PYTHONPATH"] = (joined + os.pathsep + existing) if existing else joined
        extra_env = env

    return cmd, extra_env


def detect_missing_interpreter(language):
    """Return an error message if the required interpreter isn't installed."""
    needs = {
        "JavaScript": "node",
        "TypeScript": "node",
        "Go": "go",
        "Rust": "cargo",
        "PHP": "php",
        "Ruby": "ruby",
        "Shell": "bash",
        "SQL": "sqlite3",
        "C": "cc",
        "C++": "c++",
        "C#": "dotnet",
        "Java": "java",
        "Lua": "lua",
        "Haxe": "haxe",
        "Perl": "perl",
        "Swift": "swift",
        "Kotlin": "kotlin",
        "Scala": "scala",
        "Dart": "dart",
        "R": "Rscript",
        "Julia": "julia",
        "Elixir": "elixir",
        "Haskell": "runghc",
        "Clojure": "clojure",
        "Erlang": "escript",
        "Pascal": "fpc",
        "Bash": "bash",
        "Batch": "cmd",
    }
    prog = needs.get(language)
    if prog and not _find(prog):
        return f"'{prog}' was not found on your system. Install it to run {language} files."
    return None


class Runner:
    """Runs a command in the background and streams output to the UI.

    Usage:
        runner = Runner(root, on_output=cb, on_done=cb)
        runner.run(command, cwd=..., env=...)

    On Windows a temporary .bat wrapper is used so compound commands
    (e.g. C/C++ compile-then-run) work cleanly.
    """

    def __init__(self, root=None, on_output=None, on_done=None, on_error=None):
        self.root = root or tk._default_root
        self.on_output = on_output or (lambda line: None)
        self.on_done = on_done or (lambda code: None)
        self.on_error = on_error or (lambda msg: None)
        self._queue = queue.Queue()
        self.is_running = False
        self.process = None
        self._poll_job = None
        self._temp_files = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def run(self, command, cwd=None, env=None):
        self.stop()
        self._queue = queue.Queue()
        self.is_running = True
        # emitted synchronously (run() always happens on the main thread) so
        # the echo appears before the console starts its input prompt
        self.on_output(f"\n$ {command}\n")

        try:
            bat = None
            if os.name == "nt":
                fd, bat = tempfile.mkstemp(suffix=".bat", prefix="codepad_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("@echo off\r\n")
                    f.write("chcp 65001 >nul\r\n")
                    if cwd:
                        f.write(f'cd /d "{cwd}"\r\n')
                    f.write(command + "\r\n")
                self._temp_files.append(bat)
                cmd_line = f'cmd.exe /c "{bat}"'
                self.process = subprocess.Popen(
                    cmd_line,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    shell=True, env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                self.process = subprocess.Popen(
                    command, shell=True, env=env, cwd=cwd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                )
        except Exception as e:
            self.is_running = False
            self._emit_line(f"Failed to start process: {e}\n")
            return

        threading.Thread(target=self._read_output, daemon=True).start()
        if self.root:
            self._poll_job = self.root.after(40, self._drain)

    def write_input(self, text):
        """Send a line of text to the child process's stdin.

        Returns True on success, False if there is no process or its stdin
        is closed (e.g. the process already exited).
        """
        proc = self.process
        if proc is None or proc.stdin is None:
            return False
        try:
            data = text.encode("utf-8", errors="replace")
            proc.stdin.write(data)
            proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def stop(self):
        with self._lock:
            self.is_running = False
            proc = self.process
            self.process = None
        if self.root and self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
            self._emit_line("\n[Process terminated]\n")
        for f in self._temp_files:
            try:
                os.remove(f)
            except Exception:
                pass
        self._temp_files = []

    # ------------------------------------------------------------------
    # background reading
    # ------------------------------------------------------------------
    def _read_output(self):
        proc = self.process
        if proc is None:
            return
        try:
            fd = proc.stdout.fileno()
        except (AttributeError, OSError):
            try:
                for part in proc.stdout.read().decode("utf-8", errors="replace").splitlines(True):
                    if part:
                        self._queue.put(("out", part))
            except Exception:
                pass
            try:
                code = proc.wait()
            except Exception:
                code = -1
            self._queue.put(("done", code))
            return
        try:
            while True:
                try:
                    chunk = os.read(fd, 8192)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                for part in chunk.decode("utf-8", errors="replace").splitlines(True):
                    if part:
                        self._queue.put(("out", part))
        except Exception:
            pass
        try:
            code = proc.wait()
        except Exception:
            code = -1
        self._queue.put(("done", code))

    # ------------------------------------------------------------------
    # main-thread drain
    # ------------------------------------------------------------------
    def _drain(self):
        drained = False
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            drained = True
            if kind == "out":
                self.on_output(payload)
            elif kind == "done":
                self.is_running = False
                self.on_done(payload)
                return
        if self._poll_job:
            self._poll_job = None
        if self.root and self.is_running:
            self._poll_job = self.root.after(40, self._drain)

    def _emit_line(self, text):
        if self.root:
            try:
                self.root.after(0, lambda: self.on_output(text))
            except Exception:
                pass
        else:
            self.on_output(text)