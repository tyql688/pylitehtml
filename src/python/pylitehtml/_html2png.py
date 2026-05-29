"""HTML → PNG/JPEG/RAW: the core high-level pipeline on top of :class:`Renderer`.

This is the heart of the high-level API. It does **not** depend on any markdown
library — it turns HTML (a full document, or a bare fragment wrapped in a clean
default stylesheet) into image bytes. ``markdown_to_png`` (see
:mod:`pylitehtml.markdown`) is a thin optional layer that produces HTML and hands
it here.

Why not just call ``Renderer.render`` directly? Three things this adds:

* a polished, litehtml-safe default stylesheet (GitHub-ish), so an arbitrary
  HTML fragment renders legibly without the caller writing CSS;
* fragment auto-wrapping (detects full documents vs. fragments);
* HiDPI ``scale`` that is honest for wrapped content — the default CSS is
  ``em``-based, so scaling the root font size (and the width) scales everything.
"""

from __future__ import annotations

import re
from typing import Literal

from . import FontConfig, ImageConfig, OutputFormat, RawResult, Renderer

__all__ = [
    "DEFAULT_CSS",
    "wrap_html",
    "html_to_png",
    "html_to_image",
]

# Base font size (px) at scale=1. The default stylesheet is em-relative, so the
# whole layout scales with this single number.
_BASE_FONT_PX = 16

# Sticks to the litehtml-supported subset (no var() / grid / box-shadow):
# block/inline boxes, margins/border/radius, background, font, lists, tables.
DEFAULT_CSS = """
html { font-size: 16px; }
body {
  margin: 0;
  padding: 1.25em 1.5em;
  font-family: "Noto Sans", "Noto Sans SC", sans-serif;
  font-size: 1em;
  line-height: 1.6;
  color: #1f2328;
  background: #ffffff;
  word-wrap: break-word;
}
h1, h2, h3, h4, h5, h6 {
  margin: 1.2em 0 0.5em;
  font-weight: 600;
  line-height: 1.25;
}
h1 { font-size: 1.9em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.25em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em; }
h3 { font-size: 1.25em; }
h4 { font-size: 1.05em; }
h5 { font-size: 0.95em; }
h6 { font-size: 0.9em; color: #59636e; }
p { margin: 0 0 0.9em; }
a { color: #0969da; text-decoration: none; }
strong { font-weight: 600; }
em { font-style: italic; }
del { text-decoration: line-through; color: #818b96; }
hr { height: 1px; border: 0; background: #d0d7de; margin: 1.5em 0; }
ul, ol { margin: 0 0 0.9em; padding-left: 1.8em; }
li { margin: 0.2em 0; }
li > ul, li > ol { margin: 0.2em 0; }
li.md-task-item { list-style: none; }
.md-task {
  display: inline-block; width: 1em; height: 1em;
  border: 1px solid #8b949e; border-radius: 3px;
  margin: 0 0.5em 0 -1.5em; vertical-align: -0.1em;
}
.md-task.checked { background: #2da44e; border-color: #2da44e; }
blockquote {
  margin: 0 0 0.9em;
  padding: 0.2em 1em;
  color: #59636e;
  border-left: 0.25em solid #d0d7de;
  background: #f6f8fa;
}
blockquote > :last-child { margin-bottom: 0; }
code {
  font-family: "DejaVu Sans Mono", "Noto Sans", monospace;
  font-size: 0.88em;
  background: #eff1f3;
  padding: 0.15em 0.35em;
  border-radius: 4px;
}
pre {
  margin: 0 0 0.9em;
  padding: 0.9em 1em;
  background: #f6f8fa;
  border-radius: 6px;
  overflow: hidden;
  line-height: 1.45;
}
pre code {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: 0.85em;
  white-space: pre-wrap;
}
table {
  border-collapse: collapse;
  margin: 0 0 0.9em;
  width: auto;
}
th, td {
  border: 1px solid #d0d7de;
  padding: 0.4em 0.8em;
}
th { background: #f6f8fa; font-weight: 600; white-space: nowrap; }
tr:nth-child(2n) td { background: #f6f8fa; }
img { max-width: 100%; }
figure { margin: 0 0 0.9em; }
figcaption { font-size: 0.85em; color: #59636e; padding: 0.2em 0; }
.math { font-family: "DejaVu Sans Mono", monospace; background: #f6f8fa; padding: 0 0.2em; }
div.math { display: block; padding: 0.6em 1em; margin: 0 0 0.9em; border-radius: 6px; }
.markdown-alert {
  margin: 0 0 0.9em;
  padding: 0.4em 1em;
  border-left: 0.25em solid #d0d7de;
  background: #f6f8fa;
}
.markdown-alert-note { border-left-color: #0969da; }
.markdown-alert-warning { border-left-color: #bf8700; }
.markdown-alert-important { border-left-color: #8250df; }
.markdown-alert-tip { border-left-color: #1a7f37; }
.markdown-alert-caution { border-left-color: #cf222e; }
""".strip()

# Detect a full HTML document (vs. a bare fragment to be wrapped).
_DOC_RE = re.compile(r"<\s*(?:!doctype|html|head|body)\b", re.IGNORECASE)


def _looks_like_document(html: str) -> bool:
    return bool(_DOC_RE.search(html))


def wrap_html(
    body: str,
    *,
    css: str = DEFAULT_CSS,
    extra_css: str = "",
    title: str = "",
    base_font_px: int = _BASE_FONT_PX,
) -> str:
    """Wrap an HTML *fragment* into a full document with a stylesheet.

    ``base_font_px`` sets the root ``font-size``; because the default CSS is
    ``em``-based, raising it scales the entire layout (used for HiDPI ``scale``).
    """
    root = f"html {{ font-size: {base_font_px}px; }}"
    head_title = f"<title>{title}</title>" if title else ""
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"{head_title}<style>{root}\n{css}\n{extra_css}</style>"
        f"</head><body>{body}</body></html>"
    )


def html_to_image(
    html: str,
    *,
    width: int = 720,
    scale: int = 1,
    wrap: bool | None = None,
    css: str = DEFAULT_CSS,
    extra_css: str = "",
    fmt: str | OutputFormat = OutputFormat.PNG,
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
    locale: str = "en-US",
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
) -> bytes | RawResult:
    """Render HTML to image bytes (or :class:`RawResult` for ``fmt="raw"``).

    Parameters
    ----------
    html:
        A full HTML document or a bare fragment.
    width:
        Logical canvas width in px (before ``scale``).
    scale:
        HiDPI multiplier (e.g. ``2`` for retina). Multiplies both the canvas
        width and the wrapped content's root font size, so ``em``-based layouts
        scale faithfully. For non-wrapped full documents using ``px`` units,
        only the canvas widens — pre-scale such CSS yourself.
    wrap:
        ``True`` to force fragment-wrapping with ``css``; ``False`` to render
        ``html`` verbatim; ``None`` (default) auto-detects.
    """
    if scale < 1:
        raise ValueError(f"scale must be >= 1, got {scale}")

    do_wrap = (not _looks_like_document(html)) if wrap is None else wrap
    if do_wrap:
        document = wrap_html(html, css=css, extra_css=extra_css, base_font_px=_BASE_FONT_PX * scale)
    else:
        document = html

    render_width = width * scale
    return Renderer(render_width, locale=locale, fonts=fonts, images=images).render(
        document, fmt=fmt, quality=quality, height=height * scale, shrink_to_fit=shrink_to_fit
    )


def html_to_png(
    html: str,
    *,
    width: int = 720,
    scale: int = 1,
    wrap: bool | None = None,
    css: str = DEFAULT_CSS,
    extra_css: str = "",
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
    locale: str = "en-US",
    fmt: Literal["png", "jpeg"] = "png",
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
) -> bytes:
    """Render HTML to PNG (or JPEG) bytes. See :func:`html_to_image`."""
    result = html_to_image(
        html,
        width=width,
        scale=scale,
        wrap=wrap,
        css=css,
        extra_css=extra_css,
        fmt=fmt,
        quality=quality,
        height=height,
        shrink_to_fit=shrink_to_fit,
        locale=locale,
        fonts=fonts,
        images=images,
    )
    assert isinstance(result, bytes)  # png/jpeg always return bytes
    return result
