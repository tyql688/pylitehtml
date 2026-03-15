"""
pylitehtml — HTML+CSS to image renderer.

Lightweight, no headless browser, thread-safe.

Quick start::

    import pylitehtml

    # One-shot
    png = pylitehtml.render("<h1>Hello</h1>", width=800)

    # Reusable (amortises font-loading cost)
    r = pylitehtml.Renderer(width=800, dpi=144, lang="zh", culture="zh-CN")
    png = r.render(html)

    # Async (runs in a thread-pool executor, does not block the event loop)
    png = await pylitehtml.render_async(html, width=800)
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
    Renderer,
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


def render(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: OutputFormat = OutputFormat.PNG,
    quality: int = 85,
) -> Union[bytes, RawResult]:
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
        Output format. Default :attr:`OutputFormat.PNG`.
    quality:
        JPEG quality 1–100. Ignored for PNG and RAW.

    Returns
    -------
    bytes
        PNG or JPEG image data.
    RawResult
        When *fmt* is :attr:`OutputFormat.RAW`.
    """
    return _render_core(html, width, base_url=base_url, height=height,
                        fmt=fmt, quality=quality)


async def render_async(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: OutputFormat = OutputFormat.PNG,
    quality: int = 85,
    renderer: Renderer | None = None,
) -> Union[bytes, RawResult]:
    """
    Async convenience wrapper — runs rendering in the default thread-pool executor.

    Does **not** block the event loop. Safe to call from FastAPI, NoneBot2, or any
    other asyncio-based framework.

    Parameters
    ----------
    html:
        HTML source string to render.
    width:
        Viewport width in pixels. Ignored when *renderer* is provided.
    base_url:
        Base URL for resolving relative resources.
    height:
        Fixed canvas height in pixels (``0`` = auto).
    fmt:
        Output format. Default :attr:`OutputFormat.PNG`.
    quality:
        JPEG quality 1–100. Ignored for PNG and RAW.
    renderer:
        Optional pre-built :class:`Renderer` instance to reuse. When provided,
        *width* is ignored (the renderer was configured at construction time).

    Returns
    -------
    bytes | RawResult
        Same as :func:`render`.

    Example::

        r = Renderer(width=800, dpi=144)
        png = await render_async("<h1>Hello</h1>", width=800, renderer=r)
    """
    loop = asyncio.get_running_loop()
    if renderer is not None:
        return await loop.run_in_executor(
            None,
            lambda: renderer.render(html, base_url=base_url, height=height,
                                    fmt=fmt, quality=quality),
        )
    return await loop.run_in_executor(
        None,
        lambda: _render_core(html, width, base_url=base_url, height=height,
                              fmt=fmt, quality=quality),
    )
