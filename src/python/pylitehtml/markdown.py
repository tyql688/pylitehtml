"""Lightweight, **dependency-free** markdown → HTML → image.

The philosophy: pylitehtml is a lightweight HTML renderer, so "render markdown"
means *convert markdown to HTML in-house (stdlib only) and render that HTML*. No
third-party markdown engine, no Pygments — nothing beyond the standard library.

Covered syntax (a pragmatic GitHub-flavored subset):

* ATX headings ``#``..``######``; thematic breaks (``---`` / ``***`` / ``___``)
* fenced code blocks ``` ``` ``` with optional language class (escaped, not
  syntax-highlighted — that would need a dependency)
* blockquotes; unordered/ordered/nested lists; GFM task lists ``- [ ]``
* GFM tables with per-column alignment
* paragraphs and raw HTML block pass-through
* inline: code spans, ``**bold**``/``__bold__``, ``*em*``/``_em_``,
  ``~~strike~~``, ``[text](url)``, ``![alt](url)``, ``<autolinks>``

Anything fancier (real CommonMark edge cases, math typesetting, mermaid) is out
of scope by design. If you need a full engine, pass your own ``converter=``
(e.g. a configured ``markdown-it-py``) — pylitehtml stays dependency-free.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from html import escape
from typing import Literal

from . import FontConfig, ImageConfig, OutputFormat, RawResult
from ._html2png import DEFAULT_CSS, html_to_image

__all__ = [
    "Converter",
    "markdown_to_html",
    "markdown_to_png",
    "markdown_to_image",
]

Converter = Callable[[str], str]


# ── inline ───────────────────────────────────────────────────────────────────
_CODE_SPAN = re.compile(r"(`+)(.+?)\1")
_IMAGE = re.compile(r"!\[(.*?)\]\(\s*(\S+?)(?:\s+\"(.*?)\")?\s*\)")
_LINK = re.compile(r"\[(.*?)\]\(\s*(\S+?)(?:\s+\"(.*?)\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
_RAW_TAG = re.compile(r"</?[a-zA-Z][^<>]*>|<!--.*?-->")
# Bare URL autolinking. The `(?<!\]\()` guard skips URLs inside `](url)` link /
# image syntax. The character class stops at whitespace, brackets, the stash
# sentinel (\x00) and any non-ASCII char (e.g. the CJK comma 、) so a URL
# immediately followed by Chinese text or another inline token is not over-eaten.
_BARE_URL = re.compile(r"(?<![\w/@.])(?<!\]\()(https?://[^\s\x00<>()\[\]\x80-\U0010ffff]+)")
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+.!~>|-])")
_BOLD_ITALIC = re.compile(r"(\*\*\*|___)(?=\S)(.+?)(?<=\S)\1")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_EM = re.compile(r"(\*|_)(?=\S)(.+?)(?<=\S)\1")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_PLACEHOLDER = "\x00{}\x00"
_TRAILING_PUNCT = ".,;:!?"


def _render_inline(text: str) -> str:
    """Inline markdown → HTML.

    Anything that must not be touched by the emphasis pass — code spans, image
    tags, link/autolink URLs (a ``_`` in a URL is not emphasis!) — is stashed as
    an opaque placeholder first, then restored at the end. Only link *text*
    stays inline so it can still receive emphasis.
    """
    stash: list[str] = []

    def put(html: str) -> str:
        stash.append(html)
        return _PLACEHOLDER.format(len(stash) - 1)

    def put_link(url: str) -> str:
        return put(f'<a href="{escape(url, quote=True)}">{escape(url)}</a>')

    # 0. Backslash escapes (\\* \\` \\_ …): stash the literal char so nothing
    # else touches it. Runs first so an escaped backtick is not seen as code.
    text = _ESCAPE.sub(lambda m: put(escape(m.group(1), quote=False)), text)
    # 1. Code spans: shield raw content from every other transform.
    text = _CODE_SPAN.sub(
        lambda m: put(f"<code>{escape(m.group(2).strip(), quote=False)}</code>"), text
    )
    # 2. Autolinks — BEFORE escaping, while the literal ``<url>`` is intact.
    text = _AUTOLINK.sub(
        lambda m: put(f'<a href="{escape(m.group(1), quote=True)}">{escape(m.group(1))}</a>'),
        text,
    )
    # 2b. Inline raw HTML tags pass through verbatim (e.g. ``<span style=...>``).
    # Must run before escaping; ``a < b`` is safe because the pattern requires a
    # letter or ``/`` right after ``<``.
    text = _RAW_TAG.sub(lambda m: put(m.group(0)), text)

    # 2c. Bare URL autolinking (linkify). Trailing sentence punctuation stays as
    # text. Stashed so emphasis cannot mangle underscores in the URL.
    def _bare(m: re.Match[str]) -> str:
        url = m.group(1).rstrip(_TRAILING_PUNCT)
        return put_link(url) + m.group(1)[len(url) :]

    text = _BARE_URL.sub(_bare, text)
    # 3. Escape the remaining literal text.
    text = escape(text, quote=False)
    # 4. Images → fully stashed <img> tags.
    text = _IMAGE.sub(
        lambda m: put(
            f'<img src="{escape(m.group(2), quote=True)}" alt="{escape(m.group(1), quote=True)}">'
        ),
        text,
    )
    # 5. Links: stash only the href; keep the text inline for emphasis.
    text = _LINK.sub(
        lambda m: f'<a href="{put(escape(m.group(2), quote=True))}">{m.group(1)}</a>',
        text,
    )
    # 6. Emphasis. ``***x***`` first (so its tags nest correctly), then bold
    # before em so ``**`` is not split by ``*``.
    text = _BOLD_ITALIC.sub(r"<strong><em>\2</em></strong>", text)
    text = _BOLD.sub(r"<strong>\2</strong>", text)
    text = _STRIKE.sub(r"<del>\1</del>", text)
    text = _EM.sub(r"<em>\2</em>", text)

    # 7. Restore placeholders. Stash entries are final HTML and never contain
    # other placeholders, so a single pass is sufficient.
    for i, html in enumerate(stash):
        text = text.replace(_PLACEHOLDER.format(i), html)
    return text


# ── block-level patterns ──────────────────────────────────────────────────────
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^\s`]*)")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")
_BLOCKQUOTE = re.compile(r"^ {0,3}>\s?(.*)$")
_TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")
_HTML_BLOCK = re.compile(r"^\s*<(?:/?[a-zA-Z][\w-]*|!--)")


def _is_blank(line: str) -> bool:
    return not line.strip()


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _table_aligns(delim: str) -> list[str]:
    aligns: list[str] = []
    for cell in _split_table_row(delim):
        left, right = cell.startswith(":"), cell.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append("")
    return aligns


def _style(align: str) -> str:
    return f' style="text-align:{align}"' if align else ""


class _Parser:
    """A line-oriented block parser. Deliberately small; see module docstring."""

    def __init__(self, text: str) -> None:
        # Normalise newlines and expand tabs so indentation math is consistent.
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n")
        self.i = 0
        self.out: list[str] = []

    def parse(self) -> str:
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if _is_blank(line):
                self.i += 1
                continue
            if self._try_fence():
                continue
            if _HEADING.match(line):
                self._heading(line)
            elif _HR.match(line):
                self.out.append("<hr>")
                self.i += 1
            elif _BLOCKQUOTE.match(line):
                self._blockquote()
            elif self._is_table_start():
                self._table()
            elif _LIST_ITEM.match(line):
                self._list(self._indent(line))
            elif _HTML_BLOCK.match(line):
                self._html_block()
            else:
                self._paragraph()
        return "\n".join(self.out)

    # ── helpers ──
    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def _heading(self, line: str) -> None:
        m = _HEADING.match(line)
        assert m
        level = len(m.group(1))
        self.out.append(f"<h{level}>{_render_inline(m.group(2))}</h{level}>")
        self.i += 1

    def _try_fence(self) -> bool:
        m = _FENCE.match(self.lines[self.i])
        if not m:
            return False
        indent, fence, lang = m.group(1), m.group(2), m.group(3)
        body: list[str] = []
        self.i += 1
        close = re.compile(rf"^\s*{re.escape(fence[0])}{{{len(fence)},}}\s*$")
        while self.i < len(self.lines) and not close.match(self.lines[self.i]):
            cur = self.lines[self.i]
            body.append(cur[len(indent) :] if cur.startswith(indent) else cur)
            self.i += 1
        self.i += 1  # consume closing fence (if any)
        cls = f' class="language-{escape(lang, quote=True)}"' if lang else ""
        code = escape("\n".join(body), quote=False)
        self.out.append(f"<pre><code{cls}>{code}</code></pre>")
        return True

    def _blockquote(self) -> None:
        inner: list[str] = []
        while self.i < len(self.lines):
            m = _BLOCKQUOTE.match(self.lines[self.i])
            if m is None:
                if _is_blank(self.lines[self.i]):
                    break
                inner.append(self.lines[self.i])  # lazy continuation
            else:
                inner.append(m.group(1))
            self.i += 1
        body = _Parser("\n".join(inner)).parse()
        self.out.append(f"<blockquote>{body}</blockquote>")

    def _html_block(self) -> None:
        block: list[str] = []
        while self.i < len(self.lines) and not _is_blank(self.lines[self.i]):
            block.append(self.lines[self.i])
            self.i += 1
        self.out.append("\n".join(block))

    def _paragraph(self) -> None:
        buf: list[str] = []
        while self.i < len(self.lines) and not _is_blank(self.lines[self.i]):
            line = self.lines[self.i]
            if (
                _HEADING.match(line)
                or _HR.match(line)
                or _BLOCKQUOTE.match(line)
                or _FENCE.match(line)
                or _LIST_ITEM.match(line)
            ):
                break
            # Hard line break: a line ending in two+ spaces or a backslash.
            stripped = line.rstrip()
            hard_break = line.endswith("  ") or stripped.endswith("\\")
            buf.append(stripped.rstrip("\\") + ("<br>" if hard_break else ""))
            self.i += 1
        if buf:
            # Join soft-wrapped lines with a space; hard breaks already inserted.
            joined = " ".join(buf).replace("<br> ", "<br>")
            self.out.append(f"<p>{_render_inline(joined)}</p>")

    # ── tables ──
    def _is_table_start(self) -> bool:
        if "|" not in self.lines[self.i]:
            return False
        nxt = self.i + 1
        return nxt < len(self.lines) and bool(_TABLE_DELIM.match(self.lines[nxt]))

    def _table(self) -> None:
        header = _split_table_row(self.lines[self.i])
        aligns = _table_aligns(self.lines[self.i + 1])
        self.i += 2
        rows: list[list[str]] = []
        while (
            self.i < len(self.lines)
            and "|" in self.lines[self.i]
            and not _is_blank(self.lines[self.i])
        ):
            rows.append(_split_table_row(self.lines[self.i]))
            self.i += 1

        def cells(values: list[str], tag: str) -> str:
            out = []
            for idx in range(len(header)):
                val = values[idx] if idx < len(values) else ""
                align = aligns[idx] if idx < len(aligns) else ""
                out.append(f"<{tag}{_style(align)}>{_render_inline(val)}</{tag}>")
            return "".join(out)

        thead = f"<thead><tr>{cells(header, 'th')}</tr></thead>"
        body = "".join(f"<tr>{cells(r, 'td')}</tr>" for r in rows)
        self.out.append(f"<table>{thead}<tbody>{body}</tbody></table>")

    # ── lists (indentation-based, recursive) ──
    @staticmethod
    def _is_ordered(marker: str) -> bool:
        return marker[0].isdigit()

    def _same_kind(self, line: str, base_indent: int, ordered: bool) -> bool:
        """A list line at base_indent whose marker matches this list's kind
        (ordered vs unordered). A change of kind starts a new list."""
        m = _LIST_ITEM.match(line)
        return (
            m is not None
            and self._indent(line) == base_indent
            and self._is_ordered(m.group(2)) == ordered
        )

    def _list(self, base_indent: int) -> None:
        first = _LIST_ITEM.match(self.lines[self.i])
        assert first
        marker = first.group(2)
        ordered = self._is_ordered(marker)
        if ordered:
            start = int(marker[:-1])
            tag = "ol" if start == 1 else f'ol start="{start}"'
            close = "ol"
        else:
            tag = close = "ul"
        items: list[str] = []

        while self.i < len(self.lines):
            line = self.lines[self.i]
            if _is_blank(line):
                # A blank line continues the list only if the next line is an
                # item of the SAME kind; a different marker starts a new list.
                nxt = self.i + 1
                if nxt < len(self.lines) and self._same_kind(self.lines[nxt], base_indent, ordered):
                    self.i += 1
                    continue
                break
            if not self._same_kind(line, base_indent, ordered):
                break
            items.append(self._list_item(base_indent))
        self.out.append(f"<{tag}>{''.join(items)}</{close}>")

    def _list_item(self, base_indent: int) -> str:
        m = _LIST_ITEM.match(self.lines[self.i])
        assert m
        content = m.group(3)
        self.i += 1
        # Gather indented continuation lines / nested lists.
        nested: list[str] = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if _is_blank(line):
                nxt = self.i + 1
                if (
                    nxt < len(self.lines)
                    and _LIST_ITEM.match(self.lines[nxt])
                    and self._indent(self.lines[nxt]) > base_indent
                ):
                    self.i += 1
                    continue
                break
            indent = self._indent(line)
            if _LIST_ITEM.match(line) and indent > base_indent:
                sub = _Parser("")
                sub.lines = self.lines
                sub.i = self.i
                sub.out = []
                sub._list(indent)
                nested.append("\n".join(sub.out))
                self.i = sub.i
            elif indent > base_indent and not _LIST_ITEM.match(line):
                nested.append(_render_inline(line.strip()))
                self.i += 1
            else:
                break

        task = _TASK.match(content)
        if task:
            # litehtml does not draw <input> form controls, so use a CSS box.
            checked = " checked" if task.group(1).lower() == "x" else ""
            inner = f'<span class="md-task{checked}"></span>{_render_inline(task.group(2))}'
            return f'<li class="md-task-item">{inner}{"".join(nested)}</li>'
        return f"<li>{_render_inline(content)}{''.join(nested)}</li>"


def markdown_to_html(md: str, *, converter: Converter | None = None) -> str:
    """Convert markdown to an HTML *fragment* (no ``<html>`` wrapper).

    Pass ``converter`` to use your own engine instead of the built-in one.
    """
    if converter is not None:
        return converter(md)
    return _Parser(md).parse()


def markdown_to_png(
    md: str,
    *,
    width: int = 720,
    scale: int = 2,
    converter: Converter | None = None,
    extra_css: str = "",
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
    locale: str = "zh-CN",
    fmt: Literal["png", "jpeg"] = "png",
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
) -> bytes:
    """Render markdown to PNG/JPEG bytes — markdown → HTML → :func:`html_to_image`.

    ``scale`` defaults to 2 (HiDPI). Dependency-free unless you pass ``converter``.
    """
    body = markdown_to_html(md, converter=converter)
    css = f"{DEFAULT_CSS}\n{extra_css}"
    result = html_to_image(
        body,
        width=width,
        scale=scale,
        wrap=True,
        css=css,
        fmt=fmt,
        quality=quality,
        height=height,
        shrink_to_fit=shrink_to_fit,
        locale=locale,
        fonts=fonts,
        images=images,
    )
    assert isinstance(result, bytes)
    return result


def markdown_to_image(
    md: str,
    *,
    width: int = 720,
    scale: int = 2,
    converter: Converter | None = None,
    extra_css: str = "",
    fmt: str | OutputFormat = OutputFormat.RAW,
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
    locale: str = "zh-CN",
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
) -> bytes | RawResult:
    """Like :func:`markdown_to_png` but exposes ``fmt`` (e.g. ``"raw"``)."""
    body = markdown_to_html(md, converter=converter)
    css = f"{DEFAULT_CSS}\n{extra_css}"
    return html_to_image(
        body,
        width=width,
        scale=scale,
        wrap=True,
        css=css,
        fmt=fmt,
        quality=quality,
        height=height,
        shrink_to_fit=shrink_to_fit,
        locale=locale,
        fonts=fonts,
        images=images,
    )
