#!/usr/bin/env python3
"""Render a real, feature-dense markdown document (examples/markdown.md) as
completely as pylitehtml can — via a full markdown-it-py converter.

    pip install markdown-it-py mdit-py-plugins linkify-it-py pygments  # 或: uv pip install --group examples
    python examples/render_markdown_doc.py     # → assets/markdown_doc.png

What renders fully: headings, bold/italic/strikethrough, inline code, multiple
tables, nested ordered/unordered lists, blockquotes, links + bare URLs, Windows
paths with backslashes, and syntax-highlighted code (bash / TS / Python, plus a
``start:end:path`` line-range fence shown with a caption).

Honest limits (pylitehtml runs no JavaScript):
* **Mermaid** diagrams cannot be drawn — they are shown as labelled source.
* **Math** (``$…$`` / ``$$…$$``) is shown as the raw TeX in a styled box, not
  typeset by KaTeX.
"""

from __future__ import annotations

import re
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pyg_highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.util import ClassNotFound

from pylitehtml.markdown import markdown_to_png

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DOC = Path(__file__).resolve().parent / "markdown.md"

_FORMATTER = HtmlFormatter(style="friendly", nowrap=True)
_LINE_REF = re.compile(r"^(\d+):(\d+):(.+)$")  # `start:end:path` line-range fences

# Extra styling on top of pylitehtml's DEFAULT_CSS (+ Pygments tokens).
EXTRA_CSS = """
.mermaid-src { border: 1px solid #d0d7de; border-radius: 8px; margin: 0 0 0.9em; }
.mermaid-src .head { background: #fff8c5; padding: 4px 12px; font-size: 0.8em; color: #7a6500; border-bottom: 1px solid #eaddae; }
.mermaid-src pre { background: #f6f8fa; color: #1f2328; border-radius: 0 0 8px 8px; margin: 0; }
figure.code-ref { margin: 0 0 0.9em; }
figure.code-ref figcaption { font-size: 0.78em; color: #59636e; background: #eef1f5; padding: 4px 12px; border-radius: 8px 8px 0 0; font-family: "DejaVu Sans Mono", monospace; }
figure.code-ref pre { border-radius: 0 0 8px 8px; margin: 0; }
"""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pygments_block(code: str, lexer) -> str:
    return f'<pre class="highlight"><code>{pyg_highlight(code, lexer, _FORMATTER)}</code></pre>'


def _highlight(code: str, lang: str, _attrs: str) -> str:
    """Fence renderer covering mermaid, line-range fences, and normal languages."""
    name = (lang or "").strip()
    if name.lower() == "mermaid":
        kind = code.strip().split(None, 1)[0] if code.strip() else "diagram"
        return (
            '<div class="mermaid-src">'
            f'<div class="head">Mermaid · {kind}（无 JS，展示源码）</div>'
            f"<pre><code>{_escape(code)}</code></pre></div>"
        )
    ref = _LINE_REF.match(name)
    if ref:
        start, end, path = ref.groups()
        try:
            lexer = get_lexer_for_filename(path)
            body = _pygments_block(code, lexer)
        except ClassNotFound:
            body = f"<pre><code>{_escape(code)}</code></pre>"
        return f'<figure class="code-ref"><figcaption>{_escape(path)} :{start}-{end}</figcaption>{body}</figure>'
    try:
        lexer = get_lexer_by_name(name) if name else None
    except ClassNotFound:
        lexer = None
    if lexer is None:
        return ""  # let markdown-it do its default escaped rendering
    return _pygments_block(code, lexer)


def build_converter() -> MarkdownIt:
    md = MarkdownIt("gfm-like", {"highlight": _highlight, "html": True, "linkify": True})
    md.use(tasklists_plugin).use(footnote_plugin).use(deflist_plugin)
    # double_inline=True so a single-line `$$…$$` (here inside a blockquote) is
    # recognised as display math instead of leaking literal `$` signs.
    md.use(dollarmath_plugin, double_inline=True)
    return md


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    text = DOC.read_text(encoding="utf-8")
    md = build_converter()
    pygments_css = HtmlFormatter(style="friendly").get_style_defs(".highlight")
    png = markdown_to_png(
        text,
        width=860,
        converter=md.render,
        extra_css=pygments_css + EXTRA_CSS,
        locale="zh-CN",
    )
    out = ASSETS / "markdown_doc.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
