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
