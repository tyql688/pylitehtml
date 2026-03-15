"""
pylitehtml — HTML+CSS to image renderer.

Lightweight, no headless browser, thread-safe.

Quick start::

    import pylitehtml

    # One-shot
    png = pylitehtml.render("<h1>Hello</h1>", width=800)

    # Reusable (amortises font-loading cost)
    r = pylitehtml.Renderer(width=800, locale="zh-CN", image_cache_mb=64)
    png = r.render(html)

    # Async method on Renderer
    png = await r.render_async("<h1>你好</h1>")

    # One-shot async (no renderer reuse)
    png = await pylitehtml.render_async("<h1>Hello</h1>", width=800)
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Union

# Windows: Python 3.8+ no longer searches PATH for DLLs when loading extension
# modules. Add vcpkg/system DLL directories before importing _core.
if sys.platform == "win32":
    # 1. Bundled DLLs (production wheels, placed by delvewheel)
    _dll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dlls")
    if os.path.isdir(_dll_dir):
        os.add_dll_directory(_dll_dir)
    # 2. Explicit override via env var (CI editable installs with vcpkg)
    for _p in os.environ.get("PYLITEHTML_DLL_PATH", "").split(os.pathsep):
        _p = _p.strip()
        if _p:
            try:
                os.add_dll_directory(os.path.normpath(_p))
            except OSError:
                pass

from ._core import (  # noqa: E402
    ImageFetchError,
    OutputFormat,
    RawResult,
    RenderError,
    Renderer as _CoreRenderer,
    render as _render_core,
)

__all__ = [
    "OutputFormat",
    "RawResult",
    "RenderError",
    "ImageFetchError",
    "Renderer",
    "render",
    "render_async",
]


def _resolve_fmt(fmt: "str | OutputFormat") -> OutputFormat:
    if isinstance(fmt, OutputFormat):
        return fmt
    _map = {"png": OutputFormat.PNG, "jpeg": OutputFormat.JPEG, "raw": OutputFormat.RAW}
    try:
        return _map[fmt.lower()]
    except KeyError:
        raise ValueError(f"Unknown fmt {fmt!r}. Use 'png', 'jpeg', 'raw', or OutputFormat.")


def _split_locale(locale: str) -> "tuple[str, str]":
    """'zh-CN' -> ('zh', 'zh-CN');  'en' -> ('en', 'en')"""
    lang = locale.split("-", 1)[0]
    return lang, locale


class Renderer:
    """
    Reusable HTML+CSS to image renderer.

    Create once, call :meth:`render` or :meth:`render_async` many times.
    Thread-safe after construction.

    Example::

        from pylitehtml import Renderer, OutputFormat

        r = Renderer(width=800, locale="zh-CN", image_cache_mb=64)
        png: bytes = r.render("<h1>你好</h1>")
        jpg: bytes = r.render("<p>hello</p>", fmt="jpeg", quality=90)
        png2 = await r.render_async("<h1>async</h1>")
    """

    def __init__(
        self,
        width: int,
        *,
        default_font: str = "Noto Sans",
        default_font_size: int = 16,
        extra_fonts: "list[str] | None" = None,
        image_cache_mb: float = 64.0,
        image_timeout_ms: int = 5_000,
        image_max_mb: float = 10.0,
        allow_http_images: bool = True,
        dpi: float = 96.0,
        device_height: int = 600,
        locale: str = "en-US",
    ) -> None:
        """
        Create a new renderer.

        Parameters
        ----------
        width:
            Viewport width in pixels.
        default_font:
            Fallback font family name (must be installed or in *extra_fonts*).
        default_font_size:
            Default font size in pixels (used when CSS does not specify one).
        extra_fonts:
            Additional font file paths (``.ttf`` / ``.otf``) to register.
        image_cache_mb:
            Maximum total size of the decoded image cache in megabytes (default 64).
            Oldest images are evicted FIFO when the limit is reached.
        image_timeout_ms:
            Timeout for HTTP image fetches in milliseconds (default 5000).
        image_max_mb:
            Maximum size of a single image in megabytes (default 10).
            Images larger than this are skipped.
        allow_http_images:
            Whether to fetch images over ``http://`` / ``https://``.
            Set to ``False`` to disable all network access.
        dpi:
            Screen DPI used for ``pt`` unit conversion and ``resolution`` media
            features (default 96). Use ``144`` or ``192`` for HiDPI / Retina output.
        device_height:
            Logical screen height in pixels reported to CSS media queries (default 600).
            Does not affect the rendered canvas height — use *height* in :meth:`render`.
        locale:
            BCP 47 locale string (e.g. ``"en-US"``, ``"zh-CN"``). Affects
            ``:lang()`` CSS selectors. Split into lang/culture internally.
        """
        lang, culture = _split_locale(locale)
        self._r = _CoreRenderer(
            width=width,
            default_font=default_font,
            default_font_size=default_font_size,
            extra_fonts=extra_fonts or [],
            image_cache_max_bytes=int(image_cache_mb * 1024 * 1024),
            image_timeout_ms=image_timeout_ms,
            image_max_bytes=int(image_max_mb * 1024 * 1024),
            allow_http_images=allow_http_images,
            dpi=dpi,
            device_height=device_height,
            lang=lang,
            culture=culture,
        )

    def render(
        self,
        html: str,
        *,
        base_url: str = "",
        height: int = 0,
        fmt: "str | OutputFormat" = OutputFormat.PNG,
        quality: int = 85,
        shrink_to_fit: bool = False,
    ) -> "bytes | RawResult":
        """
        Render HTML and return image data.

        The GIL is released during the C++ render pass, so concurrent calls
        from multiple threads proceed without blocking each other.

        Parameters
        ----------
        html:
            HTML source string to render.
        base_url:
            Base URL for resolving relative resources (images, stylesheets).
        height:
            Fixed canvas height in pixels. ``0`` (default) = auto-size to content.
        fmt:
            Output format. Accepts :class:`OutputFormat` or string
            ``'png'``, ``'jpeg'``, ``'raw'``. Default ``'png'``.
        quality:
            JPEG compression quality, 1–100. Ignored for PNG and RAW.
        shrink_to_fit:
            If ``True`` and the rendered content bounding box is narrower than
            *width*, re-render at the content width so the output image is not
            padded with empty space on the right.

        Returns
        -------
        bytes
            PNG or JPEG-encoded image data.
        RawResult
            When *fmt* is ``'raw'`` or :attr:`OutputFormat.RAW`.
        """
        return self._r.render(
            html,
            base_url=base_url,
            height=height,
            fmt=_resolve_fmt(fmt),
            quality=quality,
            shrink_to_fit=shrink_to_fit,
        )

    async def render_async(
        self,
        html: str,
        *,
        base_url: str = "",
        height: int = 0,
        fmt: "str | OutputFormat" = OutputFormat.PNG,
        quality: int = 85,
        shrink_to_fit: bool = False,
    ) -> "bytes | RawResult":
        """
        Async render — runs in the default thread-pool via ``asyncio.to_thread``.

        Does **not** block the event loop. Safe to call from FastAPI, NoneBot2,
        or any asyncio-based framework.

        Parameters
        ----------
        html:
            HTML source string to render.
        base_url:
            Base URL for resolving relative resources.
        height:
            Fixed canvas height in pixels (``0`` = auto).
        fmt:
            Output format. Accepts :class:`OutputFormat` or string
            ``'png'``, ``'jpeg'``, ``'raw'``. Default ``'png'``.
        quality:
            JPEG quality 1–100. Ignored for PNG and RAW.
        shrink_to_fit:
            Re-render at content width if content is narrower than viewport.

        Returns
        -------
        bytes | RawResult
            Same as :meth:`render`.
        """
        resolved_fmt = _resolve_fmt(fmt)
        return await asyncio.to_thread(
            self._r.render,
            html,
            base_url=base_url,
            height=height,
            fmt=resolved_fmt,
            quality=quality,
            shrink_to_fit=shrink_to_fit,
        )


def render(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: "str | OutputFormat" = OutputFormat.PNG,
    quality: int = 85,
    shrink_to_fit: bool = False,
) -> "bytes | RawResult":
    """
    One-shot convenience function — creates a temporary :class:`Renderer`.

    For repeated rendering use :class:`Renderer` directly so font loading
    is paid only once.

    Parameters
    ----------
    html:
        HTML source string to render.
    width:
        Viewport width in pixels.
    base_url:
        Base URL for resolving relative resources (images, stylesheets).
    height:
        Fixed canvas height in pixels (``0`` = auto-size to content).
    fmt:
        Output format. Accepts :class:`OutputFormat` or string
        ``'png'``, ``'jpeg'``, ``'raw'``. Default ``'png'``.
    quality:
        JPEG quality 1–100. Ignored for PNG and RAW.
    shrink_to_fit:
        Re-render at content width if content is narrower than viewport.

    Returns
    -------
    bytes
        PNG or JPEG image data.
    RawResult
        When *fmt* is ``'raw'`` or :attr:`OutputFormat.RAW`.
    """
    return _render_core(
        html, width,
        base_url=base_url,
        height=height,
        fmt=_resolve_fmt(fmt),
        quality=quality,
        shrink_to_fit=shrink_to_fit,
    )


async def render_async(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: "str | OutputFormat" = OutputFormat.PNG,
    quality: int = 85,
    shrink_to_fit: bool = False,
) -> "bytes | RawResult":
    """
    Async one-shot convenience function.

    Runs rendering in the default thread-pool executor via ``asyncio.to_thread``.
    Does **not** block the event loop.

    For reusable async rendering use :meth:`Renderer.render_async` instead.

    Parameters
    ----------
    html:
        HTML source string to render.
    width:
        Viewport width in pixels.
    base_url:
        Base URL for resolving relative resources.
    height:
        Fixed canvas height in pixels (``0`` = auto).
    fmt:
        Output format. Accepts :class:`OutputFormat` or string
        ``'png'``, ``'jpeg'``, ``'raw'``. Default ``'png'``.
    quality:
        JPEG quality 1–100. Ignored for PNG and RAW.
    shrink_to_fit:
        Re-render at content width if content is narrower than viewport.

    Returns
    -------
    bytes | RawResult
        Same as :func:`render`.
    """
    resolved_fmt = _resolve_fmt(fmt)
    return await asyncio.to_thread(
        _render_core,
        html, width,
        base_url=base_url,
        height=height,
        fmt=resolved_fmt,
        quality=quality,
        shrink_to_fit=shrink_to_fit,
    )
