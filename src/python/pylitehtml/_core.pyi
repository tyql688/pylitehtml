# src/python/pylitehtml/_core.pyi
from enum import IntEnum

class OutputFormat(IntEnum):
    PNG = 0
    JPEG = 1
    RAW = 2

class RawResult:
    data: bytes    # true RGBA row-major
    width: int
    height: int

class RenderError(Exception): ...
class ImageFetchError(Exception): ...

class Renderer:
    def __init__(
        self,
        width: int,
        default_font: str = "Noto Sans",
        default_font_size: int = 16,
        extra_fonts: list[str] = ...,
        image_cache_max_bytes: int = 67108864,
        image_timeout_ms: int = 5000,
        image_max_bytes: int = 10485760,
        allow_http_images: bool = True,
    ) -> None: ...

    def render(
        self,
        html: str,
        *,
        base_url: str = "",
        height: int = 0,
        fmt: OutputFormat = OutputFormat.PNG,
        quality: int = 85,
    ) -> bytes | RawResult: ...

def render(
    html: str,
    width: int,
    *,
    base_url: str = "",
    height: int = 0,
    fmt: OutputFormat = OutputFormat.PNG,
    quality: int = 85,
) -> bytes | RawResult: ...
