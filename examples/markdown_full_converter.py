#!/usr/bin/env python3
"""Full CommonMark / GFM via a custom ``converter=`` — markdown-it-py.

pylitehtml's built-in markdown converter is a lightweight, zero-dependency
subset. When you need the *full* CommonMark/GFM grammar (footnotes, definition
lists, real syntax highlighting, …), pass your own ``converter`` — a
``Callable[[str], str]`` that turns markdown into HTML. pylitehtml itself stays
dependency-free; only this example needs the extra packages:

    pip install markdown-it-py mdit-py-plugins linkify-it-py pygments

→ assets/showcase_markdown_full.png   Run: ``python examples/markdown_full_converter.py``
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pyg_highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from pylitehtml.markdown import markdown_to_png

ASSETS = Path(__file__).resolve().parent.parent / "assets"

_FORMATTER = HtmlFormatter(style="friendly", nowrap=True)


def _highlight(code: str, lang: str, _attrs: str) -> str:
    """Pygments fence highlighter. Returning "" lets markdown-it fall back to
    its own (escaped, unhighlighted) rendering."""
    try:
        lexer = get_lexer_by_name(lang) if lang else None
    except ClassNotFound:
        lexer = None
    if lexer is None:
        return ""
    return f'<pre class="highlight"><code>{pyg_highlight(code, lexer, _FORMATTER)}</code></pre>'


def build_converter() -> MarkdownIt:
    """A fully configured GFM engine: tables/strikethrough/autolink (gfm-like
    preset) + task lists + footnotes + definition lists + Pygments highlighting."""
    md = MarkdownIt("gfm-like", {"highlight": _highlight, "linkify": True})
    md.use(tasklists_plugin).use(footnote_plugin).use(deflist_plugin)
    return md


SAMPLE = """\
# 完整 GFM（markdown-it-py converter）

支持内置转换器没有的语法：脚注[^note]、定义列表、带 Pygments 高亮的代码块。

## 任务列表与表格

- [x] gfm-like 预设：表格、删除线、~~strikethrough~~、autolink
- [ ] 待办项

| 功能 | 内置转换器 | markdown-it-py |
|:-----|:---------:|:--------------:|
| 表格 | ✅ | ✅ |
| 脚注 | ❌ | ✅ |
| 定义列表 | ❌ | ✅ |
| 语法高亮 | ❌ | ✅（Pygments） |

## 定义列表

术语
: 这是定义列表，由 deflist_plugin 提供。

## 语法高亮

```python
def render(html: str, width: int = 800) -> bytes:
    return pylitehtml.html_to_png(html, width=width)
```

[^note]: 这是一个脚注，由 footnote_plugin 渲染到文末。
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    md = build_converter()
    # Inject the Pygments stylesheet so the highlighted tokens are coloured.
    pygments_css = HtmlFormatter(style="friendly").get_style_defs(".highlight")
    png = markdown_to_png(SAMPLE, width=760, converter=md.render, extra_css=pygments_css)
    out = ASSETS / "showcase_markdown_full.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
