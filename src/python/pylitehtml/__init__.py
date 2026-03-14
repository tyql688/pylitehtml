import os
import sys

# Windows: Python 3.8+ no longer searches PATH for DLLs when loading extension
# modules. Add vcpkg/system DLL directories before importing _core.
if sys.platform == "win32":
    # 1. Bundled DLLs (production wheels, placed by delvewheel)
    _dll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dlls")
    if os.path.isdir(_dll_dir):
        os.add_dll_directory(_dll_dir)
    # 2. Explicit override via env var (CI editable installs with vcpkg)
    for _p in os.environ.get("PYLITEHTML_DLL_PATH", "").split(os.pathsep):
        if _p and os.path.isdir(_p):
            os.add_dll_directory(_p)

from ._core import (
    OutputFormat, RawResult, RenderError, ImageFetchError, Renderer,
    render as _render_core,
)
__all__ = ["OutputFormat", "RawResult", "RenderError", "ImageFetchError",
           "Renderer", "render"]

def render(html: str, width: int, *, base_url: str = "", height: int = 0,
           fmt: OutputFormat = OutputFormat.PNG, quality: int = 85):
    """One-shot convenience function. Creates a temporary Renderer."""
    return _render_core(html, width, base_url=base_url, height=height,
                        fmt=fmt, quality=quality)
