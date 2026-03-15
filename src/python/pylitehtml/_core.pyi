# src/python/pylitehtml/_core.pyi
"""Type stubs for the _core C extension module."""
from enum import IntEnum

class OutputFormat(IntEnum):
    """Output image format."""
    PNG = 0
    """PNG-encoded bytes. Lossless, best for screenshots."""
    JPEG = 1
    """JPEG-encoded bytes. Smaller files; use `quality` to control compression."""
    RAW = 2
    """Uncompressed BGRA pixels (Cairo native channel order). Returns RawResult."""

class RawResult:
    """Returned when rendering with ``fmt=OutputFormat.RAW``."""
    data: bytes
    """Raw BGRA pixel data, row-major. Channel order: B, G, R, A."""
    width: int
    """Image width in pixels."""
    height: int
    """Image height in pixels."""

class RenderError(Exception):
    """Raised when HTML rendering fails (e.g. bad structure, resource error)."""

class ImageFetchError(Exception):
    """Raised when an image cannot be fetched or decoded."""

class Renderer:
    """
    Reusable HTML+CSS to image renderer.

    Create once, call :meth:`render` many times. Thread-safe after construction —
    multiple threads may call :meth:`render` concurrently on the same instance.

    Example::

        from pylitehtml import Renderer, OutputFormat

        r = Renderer(width=800, dpi=144, lang="zh", culture="zh-CN")
        png: bytes = r.render("<h1>你好</h1>")
        jpg: bytes = r.render("<p>hello</p>", fmt=OutputFormat.JPEG, quality=90)
    """

    def __init__(
        self,
        width: int,
        default_font: str = "Noto Sans",
        default_font_size: int = 16,
        extra_fonts: list[str] = ...,
        image_cache_max_bytes: int = 67_108_864,
        image_timeout_ms: int = 5_000,
        image_max_bytes: int = 10_485_760,
        allow_http_images: bool = True,
        dpi: float = 96.0,
        lang: str = "en",
        culture: str = "en-US",
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
        image_cache_max_bytes:
            Maximum total size of the decoded image cache in bytes (default 64 MB).
            Oldest images are evicted FIFO when the limit is reached.
        image_timeout_ms:
            Timeout for HTTP image fetches in milliseconds (default 5 s).
        image_max_bytes:
            Maximum size of a single image in bytes (default 10 MB).
            Images larger than this are skipped.
        allow_http_images:
            Whether to fetch images over ``http://`` / ``https://``.
            Set to ``False`` to disable all network access.
        dpi:
            Screen DPI used for ``pt`` unit conversion and ``resolution`` media
            features (default 96). Use ``144`` or ``192`` for HiDPI / Retina output.
        lang:
            BCP 47 language tag reported to litehtml (e.g. ``"en"``, ``"zh"``).
            Affects ``:lang()`` CSS selectors.
        culture:
            Culture / locale string reported to litehtml (e.g. ``"en-US"``, ``"zh-CN"``).
        """

    def render(
        self,
        html: str,
        *,
        base_url: str = "",
        height: int = 0,
        fmt: OutputFormat = OutputFormat.PNG,
        quality: int = 85,
        allow_refit: bool = False,
    ) -> bytes | RawResult:
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
            Use ``"file:///path/to/"`` for local files or an ``http://`` URL.
        height:
            Fixed canvas height in pixels. ``0`` (default) = auto-size to content.
        fmt:
            Output format. Returns ``bytes`` for PNG / JPEG, :class:`RawResult`
            for RAW.
        quality:
            JPEG compression quality, 1–100. Ignored for PNG and RAW.
        allow_refit:
            If ``True`` and the rendered content bounding box is narrower than
            *width*, re-render at the content width so the output image is not
            padded with empty space on the right.

        Returns
        -------
        bytes
            PNG or JPEG-encoded image data.
        RawResult
            When *fmt* is :attr:`OutputFormat.RAW`: uncompressed BGRA pixels.
        """

def render(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: OutputFormat = OutputFormat.PNG,
    quality: int = 85,
) -> bytes | RawResult:
    """
    One-shot convenience function.

    Creates a temporary :class:`Renderer`, renders once, and returns image data.
    For repeated rendering, use :class:`Renderer` directly — it amortizes the
    font-loading cost across calls.

    Parameters
    ----------
    html:
        HTML source string to render.
    width:
        Viewport width in pixels.
    base_url:
        Base URL for resolving relative resources.
    height:
        Fixed canvas height in pixels (0 = auto).
    fmt:
        Output format (:attr:`OutputFormat.PNG` by default).
    quality:
        JPEG quality 1–100 (ignored for PNG / RAW).

    Returns
    -------
    bytes | RawResult
        PNG / JPEG bytes, or :class:`RawResult` for RAW format.
    """
