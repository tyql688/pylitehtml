"""
pylitehtml — HTML+CSS to image renderer.

Lightweight, no headless browser, thread-safe.

Quick start::

    import pylitehtml

    # One-shot
    png = pylitehtml.render("<h1>Hello</h1>", width=800)

    # Reusable (amortises font-loading cost)
    r = pylitehtml.Renderer(width=800, locale="zh-CN")
    png = r.render(html)

    # Async (standard library pattern)
    import asyncio
    png = await asyncio.to_thread(r.render, html)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from html import escape as _html_escape
from pathlib import Path
from typing import Any

# Windows: Python 3.8+ no longer searches PATH for DLLs when loading extension
# modules. Add vcpkg/system DLL directories before importing _core.
if sys.platform == "win32":
    # 1. Bundled DLLs (production wheels, placed by delvewheel)
    _dll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dlls")
    if os.path.isdir(_dll_dir):
        _ = os.add_dll_directory(_dll_dir)
    # 2. Explicit override via env var (CI editable installs with vcpkg)
    for _p in os.environ.get("PYLITEHTML_DLL_PATH", "").split(os.pathsep):
        _p = _p.strip()
        if _p:
            try:
                _ = os.add_dll_directory(os.path.normpath(_p))
            except OSError:
                pass

from ._core import OutputFormat, RawResult, RenderError
from ._core import Renderer as _CoreRenderer
from ._jinja import render_template as _render_template

__all__ = [
    "FontConfig",
    "ImageConfig",
    "OutputFormat",
    "RawResult",
    "RenderError",
    "Renderer",
    "render",
    "render_file",
    # Lightweight HTML → image helpers (core; no third-party deps).
    "DEFAULT_CSS",
    "wrap_html",
    "html_to_png",
    "html_to_image",
]
# Note: markdown is intentionally NOT part of the core API. The optional
# markdown_to_png() helper lives in the `pylitehtml.markdown` submodule and only
# imports a markdown engine when actually called (or you pass your own).


@dataclass(frozen=True)
class FontConfig:
    """Font configuration for the renderer."""

    default: str = "Noto Sans"
    """Fallback font family name (bundled, or installed, or listed in *extra*)."""

    size: int = 16
    """Default font size in pixels (used when CSS does not specify one)."""

    extra: list[str] = field(default_factory=list)
    """Additional font file paths (``.ttf`` / ``.otf``) to register."""

    def __post_init__(self) -> None:
        if not self.default or not self.default.strip():
            raise ValueError("FontConfig.default must be a non-empty family name")
        if self.size <= 0:
            raise ValueError(f"FontConfig.size must be > 0, got {self.size}")


@dataclass(frozen=True)
class ImageConfig:
    """Image loading and caching configuration."""

    cache_mb: float = 64.0
    """Maximum total size of the decoded image cache in megabytes."""

    timeout_ms: int = 5_000
    """Timeout for HTTP image fetches in milliseconds."""

    max_mb: float = 10.0
    """Maximum size of a single image in megabytes. Larger images are skipped."""

    allow_http: bool = True
    """Whether to fetch resources (images and CSS) over ``http://`` / ``https://``.
    Set to ``False`` to disable all network access."""

    def __post_init__(self) -> None:
        if self.cache_mb < 0:
            raise ValueError(f"ImageConfig.cache_mb must be >= 0, got {self.cache_mb}")
        if self.timeout_ms <= 0:
            raise ValueError(f"ImageConfig.timeout_ms must be > 0, got {self.timeout_ms}")
        if self.max_mb <= 0:
            raise ValueError(f"ImageConfig.max_mb must be > 0, got {self.max_mb}")


def _resolve_fmt(fmt: str | OutputFormat) -> OutputFormat:
    if isinstance(fmt, OutputFormat):
        return fmt
    _map = {"png": OutputFormat.PNG, "jpeg": OutputFormat.JPEG, "raw": OutputFormat.RAW}
    try:
        return _map[fmt.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown fmt {fmt!r}. Use 'png', 'jpeg', 'raw', or OutputFormat."
        ) from None


def _split_locale(locale: str) -> tuple[str, str]:
    """'zh-CN' -> ('zh', 'zh-CN');  'en' -> ('en', 'en')"""
    lang = locale.split("-", 1)[0]
    return lang, locale


class Renderer:
    """
    Reusable HTML+CSS to image renderer.

    Create once, call :meth:`render` many times.
    Thread-safe after construction.

    Example::

        from pylitehtml import Renderer, FontConfig

        r = Renderer(width=800, locale="zh-CN", fonts=FontConfig(extra=["custom.ttf"]))
        png: bytes = r.render("<h1>你好</h1>")
        jpg: bytes = r.render("<p>hello</p>", fmt="jpeg", quality=90)
    """

    def __init__(
        self,
        width: int,
        *,
        locale: str = "en-US",
        dpi: float = 96.0,
        device_height: int = 600,
        fonts: FontConfig | None = None,
        images: ImageConfig | None = None,
    ) -> None:
        if width <= 0:
            raise ValueError(f"width must be > 0, got {width}")
        if dpi <= 0:
            raise ValueError(f"dpi must be > 0, got {dpi}")
        if device_height <= 0:
            raise ValueError(f"device_height must be > 0, got {device_height}")
        _fonts = fonts or FontConfig()
        _images = images or ImageConfig()
        lang, culture = _split_locale(locale)
        self._r: _CoreRenderer = _CoreRenderer(
            width=width,
            default_font=_fonts.default,
            default_font_size=_fonts.size,
            extra_fonts=_fonts.extra,
            image_cache_max_bytes=int(_images.cache_mb * 1024 * 1024),
            image_timeout_ms=_images.timeout_ms,
            image_max_bytes=int(_images.max_mb * 1024 * 1024),
            allow_http_images=_images.allow_http,
            dpi=dpi,
            device_height=device_height,
            lang=lang,
            culture=culture,
        )

    def render(
        self,
        html: str,
        *,
        fmt: str | OutputFormat = OutputFormat.PNG,
        quality: int = 85,
        height: int = 0,
        shrink_to_fit: bool = True,
    ) -> bytes | RawResult:
        """
        Render HTML and return image data.

        The GIL is released during the C++ render pass, so concurrent calls
        from multiple threads proceed without blocking each other.

        For async usage: ``await asyncio.to_thread(r.render, html)``
        """
        if not 1 <= quality <= 100:
            raise ValueError(f"quality must be in 1..100, got {quality}")
        if height < 0:
            raise ValueError(f"height must be >= 0, got {height}")
        return self._r.render(
            html,
            height=height,
            fmt=_resolve_fmt(fmt),
            quality=quality,
            shrink_to_fit=shrink_to_fit,
        )

    def render_file(
        self,
        path: str | Path,
        *,
        fmt: str | OutputFormat = OutputFormat.PNG,
        quality: int = 85,
        height: int = 0,
        shrink_to_fit: bool = True,
        **template_data: Any,
    ) -> bytes | RawResult:
        """
        Render a local HTML file to image data.

        Relative resources (CSS via ``<link>``, images via ``<img>``) are
        resolved from the file's directory automatically.

        If *template_data* is provided, the file is treated as a
        `Jinja2 <https://jinja.palletsprojects.com/>`_ template and rendered
        with the given keyword arguments before the HTML-to-image pass.
        Requires ``jinja2`` (install with ``pip install pylitehtml[templates]``).

        Example::

            r = Renderer(width=800)

            # Plain HTML file with external CSS
            png = r.render_file("project/index.html")

            # Jinja2 template
            png = r.render_file("project/order.html", title="订单", items=[...])
        """
        resolved = Path(path).resolve()
        if template_data:
            html = _render_template(resolved, template_data)
        else:
            html = resolved.read_text(encoding="utf-8")

        # Inject <base> so litehtml resolves relative CSS/image paths. Entity-
        # escape the path: a quote in a directory name must not break out of
        # the attribute (the HTML parser decodes entities, so the C++ side
        # still receives the original path).
        html = f'<base href="file://{_html_escape(resolved.as_posix(), quote=True)}">\n{html}'

        return self.render(
            html,
            fmt=fmt,
            quality=quality,
            height=height,
            shrink_to_fit=shrink_to_fit,
        )


def render(
    html: str,
    width: int,
    *,
    locale: str = "en-US",
    dpi: float = 96.0,
    device_height: int = 600,
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
    fmt: str | OutputFormat = OutputFormat.PNG,
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
) -> bytes | RawResult:
    """
    One-shot convenience function — creates a temporary :class:`Renderer`.

    For repeated rendering use :class:`Renderer` directly so font loading
    is paid only once.
    """
    return Renderer(
        width,
        locale=locale,
        dpi=dpi,
        device_height=device_height,
        fonts=fonts,
        images=images,
    ).render(html, fmt=fmt, quality=quality, height=height, shrink_to_fit=shrink_to_fit)


def render_file(
    path: str | Path,
    width: int,
    *,
    locale: str = "en-US",
    dpi: float = 96.0,
    device_height: int = 600,
    fonts: FontConfig | None = None,
    images: ImageConfig | None = None,
    fmt: str | OutputFormat = OutputFormat.PNG,
    quality: int = 85,
    height: int = 0,
    shrink_to_fit: bool = True,
    **template_data: Any,
) -> bytes | RawResult:
    """
    One-shot file rendering — creates a temporary :class:`Renderer`.

    Equivalent to ``Renderer(width, ...).render_file(path, ...)``.
    """
    r = Renderer(
        width,
        locale=locale,
        dpi=dpi,
        device_height=device_height,
        fonts=fonts,
        images=images,
    )
    return r.render_file(
        path,
        fmt=fmt,
        quality=quality,
        height=height,
        shrink_to_fit=shrink_to_fit,
        **template_data,
    )


# Lightweight HTML → image helpers. Imported last to avoid a circular import
# (these modules import names defined above). No third-party dependencies.
from ._html2png import (
    DEFAULT_CSS,
    html_to_image,
    html_to_png,
    wrap_html,
)
