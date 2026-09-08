"""Multi-language syntax highlighting.

Provides a lightweight, dependency-free tokenizer that tags ranges
in a Tkinter Text widget. Each language defines patterns (regexes)
mapped to token categories (keyword, string, comment, ...) that the
view layer turns into colors from the active theme.

Supported languages: Python, JavaScript/TypeScript, HTML, CSS,
JSON, C, C++, Java, Go, Rust, C#, Ruby, PHP, Shell, SQL, Markdown,
XML, YAML, Lua, and plain text (no highlighting).
"""

import re


# ---------------------------------------------------------------------------
# Per-language configurations.
# Each entry is (label, is_bracketed, patterns)
# patterns: list of (regex, token_category, flags)
# ---------------------------------------------------------------------------

_KEYWORDS = (
    (r'\b(?:def|class|return|if|elif|else|for|while|break|continue|pass|'
     r'import|from|as|with|try|except|finally|raise|global|nonlocal|lambda|'
     r'and|or|not|in|is|None|True|False|yield|del|assert|async|await)\b',
     'keyword'),

    (r'\b(?:print|len|range|type|isinstance|str|int|float|list|dict|set|'
     r'tuple|open|enumerate|zip|map|filter|super|self|abs|min|max|sum|'
     r'repr|input|id|vars|help)\b',
     'builtin'),

    (r'@\w+[\w_.]*', 'decorator'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),
    (r'"""(?:.|\n)*?"""', 'string'),
    (r"'''(?:.|\n)*?'''", 'string'),

    (r'\b\d+(?:\.\d+)?[jJ]?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'#[^\n]*', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_JAVASCRIPT = (
    (r'\b(?:var|let|const|function|return|if|else|for|while|do|switch|case|'
     r'break|continue|new|delete|typeof|instanceof|in|of|class|extends|super|'
     r'this|import|export|from|default|try|catch|finally|throw|async|await|'
     r'yield|void|null|undefined|true|false|static|get|set|debugger)\b',
     'keyword'),

    (r'\b(?:console|document|window|Math|JSON|Object|Array|String|Number|'
     r'Boolean|Promise|Set|Map|RegExp|Date|parseInt|parseFloat|setTimeout|'
     r'alert|require|module|process|globalThis)\b',
     'builtin'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),
    (r'`(?:[^`\\]|\\.)*`', 'string'),

    (r'\b\d+(?:\.\d+)?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'\b[A-Za-z_$]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_JAVA = (
    (r'\b(?:public|private|protected|static|final|void|class|interface|'
     r'extends|implements|return|if|else|for|while|do|switch|case|break|'
     r'continue|new|this|super|import|package|try|catch|finally|throw|'
     r'throws|abstract|synchronized|volatile|transient|native|boolean|byte|'
     r'char|short|int|long|float|double|true|false|null|enum|default)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),

    (r'\b\d+(?:\.\d+)?[fFdDlL]?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_CPP = (
    (r'\b(?:int|float|double|char|bool|void|class|struct|public|private|'
     r'protected|virtual|const|static|return|if|else|for|while|do|switch|'
     r'case|break|continue|new|delete|this|using|namespace|template|'
     r'typename|typedef|auto|extern|inline|friend|operator|enum|union|'
     r'unsigned|signed|size_t|true|false|nullptr|and|or|not|override|'
     r'default|throw|catch|try|finally|goto|register|volatile|mutable|'
     r'explicit|export)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),

    (r'\b\d+(?:\.\d+)?[fFuUlL]?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'#[^\n]*', 'preproc'),
    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_GO = (
    (r'\b(?:package|import|func|return|if|else|for|range|switch|case|'
     r'default|break|continue|go|defer|select|type|struct|interface|var|'
     r'const|map|chan|len|cap|make|new|panic|recover|true|false|nil|'
     r'fallthrough|goto)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"`(?:.|\n)*?`", 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),

    (r'\b\d+(?:\.\d+)?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_RUST = (
    (r'\b(?:fn|let|mut|const|static|if|else|match|for|while|loop|break|'
     r'continue|return|impl|trait|struct|enum|mod|use|pub|where|move|ref|'
     r'as|async|await|type|unsafe|extern|crate|self|super|true|false|None|'
     r'Some|Ok|Err|in|of)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),
    (r'r#"(?:.|\n)*?"#', 'string'),

    (r'\b\d+(?:\.\d+)?[fFiIuU]?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
    (r'\b[A-Z]\w*\b', 'class'),
)

_HTML = (
    (r'<!--.*?-->', 'comment'),

    (r'</?[a-zA-Z][a-zA-Z0-9-]*(?=\s|/?>)', 'class'),
    (r'</?[a-zA-Z][a-zA-Z0-9-]*/?>', 'class'),

    (r'"[^"]*"', 'string'),
    (r"'[^']*'", 'string'),

    (r'\b[a-zA-Z-]+(?==)', 'constant'),

    (r'<(?:script|style)[^>]*>.*?</(?:script|style)>', 'function'),
)

_CSS = (
    (r'/\*.*?\*/', 'comment'),

    (r'(@media|@import|@keyframes|@font-face|@supports)',
     'preproc'),

    (r'\{[^}]*\}', 'keyword'),

    (r'#[0-9a-fA-F]{3,8}\b', 'number'),
    (r'\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|deg|s|ms|pt|fr)\b', 'number'),

    (r'"[^"]*"', 'string'),

    (r'\.[A-Za-z_-][A-Za-z0-9_-]*', 'class'),
    (r'#[A-Za-z_-][A-Za-z0-9_-]*', 'function'),

    (r'[a-zA-Z-]+(?=\s*:)', 'constant'),
)

_JSON = (
    (r'"(?:[^"\\]|\\.)*"(?=\s*:)', 'string'),
    (r'"(?:[^"\\]|\\.)*"', 'string'),

    (r'\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b', 'number'),

    (r'\b(?:true|false|null)\b', 'keyword'),
)

_MARKDOWN = (
    (r'(^#{1,6}\s.*$)', 'class'),
    (r'(^\s*[-*+]\s.*$)', 'function'),
    (r'(^\s*\d+\.\s.*$)', 'function'),
    (r'\[[^\]]*\]\([^)]*\)', 'keyword'),
    (r'(\*\*[^*]+\*\*|__[^_]+__)', 'string'),
    (r'(\*[^*]+\*|_[^_]+_)', 'comment'),
    (r'`[^`]+`', 'number'),
    (r'(^>.*$)', 'comment'),
    (r'(^---+$)', 'operator'),
)

_PHP = (
    (r'\b(?:echo|print|return|if|else|elseif|for|foreach|while|do|switch|'
     r'case|break|continue|function|class|interface|extends|implements|'
     r'public|private|protected|static|new|this|require|include|use|'
     r'namespace|try|catch|finally|throw|true|false|null|global|const|'
     r'abstract|final|as|instanceof|isset|empty|unset|array)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),

    (r'\$\w+', 'variable'),
    (r'\b\d+(?:\.\d+)?\b', 'number'),

    (r'//[^\n]*', 'comment'),
    (r'#[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),

    (r'@\w+', 'decorator'),
    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
)

_RUBY = (
    (r'\b(?:def|class|module|end|if|elsif|else|unless|for|while|do|return|'
     r'break|next|redo|retry|raise|rescue|ensure|begin|then|yield|self|nil|'
     r'true|false|and|or|not|require|require_relative|attr_accessor|'
     r'attr_reader|attr_writer|initialize|new|super|case|when|lambda|proc)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),
    (r'%q\[[^\]]*\]|%Q\[[^\]]*\]', 'string'),

    (r'@\w+|@@\w+', 'variable'),
    (r'\b\d+(?:\.\d+)?\b', 'number'),
    (r'#\{[^}]*\}', 'string'),

    (r'#[^\n]*', 'comment'),

    (r'\?[a-zA-Z_]\w*', 'constant'),
)

_SQL = (
    (r'\b(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN|INNER|LEFT|RIGHT|'
     r'OUTER|ON|AS|GROUP|BY|ORDER|HAVING|LIMIT|OFFSET|INTO|VALUES|SET|'
     r'CREATE|TABLE|DROP|ALTER|INDEX|VIEW|AND|OR|NOT|NULL|IS|LIKE|'
     r'BETWEEN|IN|EXISTS|CASE|WHEN|THEN|ELSE|END|PRIMARY|KEY|FOREIGN|'
     r'REFERENCES|UNIQUE|DEFAULT|AUTO_INCREMENT|CONSTRAINT|PRIMARY|'
     r'DISTINCT|COUNT|SUM|AVG|MIN|MAX|UNION|ALL)\b',
     'keyword'),

    (r"'(?:[^'\\]|\\.)*'", 'string'),

    (r'\b\d+(?:\.\d+)?\b', 'number'),

    (r'(--|#)[^\n]*', 'comment'),
    (r'/\*.*?\*/', 'comment'),
)

_SHELL = (
    (r'\b(?:if|then|else|elif|fi|for|while|until|do|done|case|esac|function|'
     r'in|return|exit|local|export|declare|select|break|continue)\b',
     'keyword'),

    (r'"([^"\\]|\\.)*"', 'string'),
    (r"'[^']*'", 'string'),

    (r'\$\w+|\$\{[^}]*\}|\$\w+\[[^\]]*\]|\$@|\$\$|\$!|\$\?|\$#|\$\*',
     'variable'),

    (r'\b\d+\b', 'number'),

    (r'#[^\n]*', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
)

_XML = (
    (r'<!--.*?-->', 'comment'),
    (r'<\?[^>]*\?>', 'preproc'),
    (r'</?[a-zA-Z][a-zA-Z0-9-]*(?=\s|/?>)', 'class'),
    (r'</?[a-zA-Z][a-zA-Z0-9-]*/?>', 'class'),
    (r'"[^"]*"', 'string'),
    (r"'[^']*'", 'string'),
    (r'\b[a-zA-Z-]+(?==)', 'constant'),
)

_YAML = (
    (r'[#][^\n]*', 'comment'),
    (r'^\s*[a-zA-Z0-9_-]+(?=\s*:)', 'constant'),
    (r'"([^"\\]|\\.)*"', 'string'),
    (r"'[^']*'", 'string'),
    (r'\b(?:true|false|null|yes|no|on|off)\b', 'keyword'),
    (r'\b\d+(?:\.\d+)?\b', 'number'),
)

_LUA = (
    (r'\b(?:function|end|if|then|else|elseif|for|while|do|repeat|until|'
     r'return|local|break|and|or|not|nil|true|false|in|goto|call)\b',
     'keyword'),

    (r'"(?:[^"\\]|\\.)*"', 'string'),
    (r"'(?:[^'\\]|\\.)*'", 'string'),
    (r'\[\[.*?\]\]', 'string'),

    (r'\b\d+(?:\.\d+)?\b|\b0[xX][0-9a-fA-F]+\b', 'number'),

    (r'--\[\[.*?\]\]', 'comment'),
    (r'--[^\n]*', 'comment'),

    (r'\b[A-Za-z_]\w*(?=\s*\()', 'function'),
)

_LANGUAGES = {
    "Python": _KEYWORDS,
    "JavaScript": _JAVASCRIPT,
    "TypeScript": _JAVASCRIPT,
    "Java": _JAVA,
    "C": _CPP,
    "C++": _CPP,
    "C#": _CPP,
    "Go": _GO,
    "Rust": _RUST,
    "HTML": _HTML,
    "CSS": _CSS,
    "JSON": _JSON,
    "Markdown": _MARKDOWN,
    "PHP": _PHP,
    "Ruby": _RUBY,
    "SQL": _SQL,
    "Shell": _SHELL,
    "XML": _XML,
    "YAML": _YAML,
    "Lua": _LUA,
    "Plain Text": [],
}

# extension -> language name. Longer/more specific extensions come first.
_EXT_MAP = [
    (".py", "Python"), (".pyw", "Python"),
    (".js", "JavaScript"), (".jsx", "JavaScript"),
    (".ts", "TypeScript"), (".tsx", "TypeScript"),
    (".mjs", "JavaScript"), (".cjs", "JavaScript"),
    (".java", "Java"),
    (".c", "C"), (".h", "C"),
    (".cpp", "C++"), (".cc", "C++"), (".cxx", "C++"), (".hpp", "C++"), (".hh", "C++"),
    (".cs", "C#"),
    (".go", "Go"),
    (".rs", "Rust"),
    (".html", "HTML"), (".htm", "HTML"),
    (".css", "CSS"),
    (".json", "JSON"),
    (".md", "Markdown"), (".markdown", "Markdown"),
    (".php", "PHP"),
    (".rb", "Ruby"),
    (".sql", "SQL"),
    (".sh", "Shell"), (".bash", "Shell"), (".zsh", "Shell"),
    (".xml", "XML"), (".svg", "XML"),
    (".yaml", "YAML"), (".yml", "YAML"),
    (".lua", "Lua"),
]

# token category -> canonical tag name used in the Text widget
TOKEN_TAGS = {
    "keyword": "tk_keyword",
    "string": "tk_string",
    "comment": "tk_comment",
    "number": "tk_number",
    "function": "tk_function",
    "class": "tk_class",
    "variable": "tk_variable",
    "builtin": "tk_builtin",
    "decorator": "tk_decorator",
    "constant": "tk_constant",
    "preproc": "tk_preproc",
    "operator": "tk_operator",
    "type": "tk_type",
}


def language_for_path(path):
    """Return the language name for a file path, or 'Plain Text'."""
    name = (path or "").lower()
    for ext, lang in _EXT_MAP:
        if name.endswith(ext):
            return lang
    return "Plain Text"


def extension_for_language(language):
    """Return the canonical file extension for a language, e.g. 'Python' -> '.py'."""
    for ext, lang in _EXT_MAP:
        if lang == language:
            return ext
    return ".txt"


def language_names():
    """Return sorted list of all supported language names."""
    return sorted(_LANGUAGES.keys())


def _compile(patterns):
    compiled = []
    for regex, category in patterns:
        try:
            compiled.append((re.compile(regex), category))
        except re.error:
            continue
    return compiled


def compile_language(name):
    """Pre-compile patterns for a language. Returns list of (compiled, category)."""
    patterns = _LANGUAGES.get(name, [])
    return _compile(patterns)


class Highlighter:
    """Statically highlights an entire widget's content (debounced by caller).

    The caller is responsible for scheduling, so this class stays simple.
    """

    def __init__(self, text_widget, theme, on_view_changed=None):
        self.text = text_widget
        self.theme = theme

    def set_theme(self, theme):
        self.theme = theme
        self.apply_tags()

    def apply_tags(self):
        for name, key in [
            ("tk_keyword", "keyword"),
            ("tk_string", "string"),
            ("tk_comment", "comment"),
            ("tk_number", "number"),
            ("tk_function", "function"),
            ("tk_class", "class"),
            ("tk_variable", "variable"),
            ("tk_builtin", "builtin"),
            ("tk_decorator", "decorator"),
            ("tk_constant", "constant"),
            ("tk_preproc", "preproc"),
            ("tk_operator", "operator"),
            ("tk_type", "type"),
        ]:
            self.text.tag_config(name, foreground=self.theme[key])

    def clear(self):
        for tag in TOKEN_TAGS.values():
            self.text.tag_remove(tag, "1.0", "end")

    def highlight(self, compiled, start="1.0", end="end"):
        """Highlight the region between start and end using compiled patterns."""
        if not compiled:
            self.clear()
            return
        self._process(compiled, start, end)

    def _process(self, compiled, start, end):
        # remove existing token tags in range
        for tag in TOKEN_TAGS.values():
            self.text.tag_remove(tag, start, end)

        # Build a char-indexed mask over the content so overlapping
        # patterns do not clobber each other.
        content = self.text.get(start, end) or ""
        spans = {cat: [] for cat in TOKEN_TAGS.values()}
        # reserve the whole thing; we'll fill per category
        base_count = {"keyword": 0, "default": 0}

        for regex, category in compiled:
            tag = TOKEN_TAGS[category]
            for m in regex.finditer(content):
                s, e = m.span()
                spans[tag].append((s, e))

        # Add tags. Because we process by category, a token later in the
        # list can overwrite an earlier same-category one, but our
        # per-language ordering avoids most conflicts.
        self._add_spans(spans, order=list(TOKEN_TAGS.values()))

    def _add_spans(self, spans, order):
        # Prefer "more specific" tokens: add them in order, each category
        # overwriting lower-priority on overlaps using tag priority config.
        for tag in order:
            for s, e in spans[tag]:
                start = f"1.0+{s}c"
                end = f"1.0+{e}c"
                self.text.tag_add(tag, start, end)
