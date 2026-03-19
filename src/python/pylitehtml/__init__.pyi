# src/python/pylitehtml/__init__.pyi
"""Type stubs for pylitehtml public API."""
from dataclasses import dataclass
from typing import Literal, overload

from ._core import ImageFetchError as ImageFetchError
from ._core import OutputFormat as OutputFormat
from ._core import RawResult as RawResult
from ._core import RenderError as RenderError

__all__: list[str]

@dataclass(frozen=True)
class FontConfig:
    default: str = "Noto Sans"
    size: int = 16
    extra: list[str] = ...

@dataclass(frozen=True)
class ImageConfig:
    cache_mb: float = 64.0
    timeout_ms: int = 5_000
    max_mb: float = 10.0
    allow_http: bool = True

class Renderer:
    def __init__(
        self,
        width: int,
        *,
        locale: str = "en-US",
        dpi: float = 96.0,
        device_height: int = 600,
        fonts: FontConfig | None = None,
        images: ImageConfig | None = None,
    ) -> None: ...

    @overload
    def render(
        self, html: str, *, fmt: Literal["raw"],
        quality: int = 85, height: int = 0, shrink_to_fit: bool = True,
    ) -> RawResult: ...
    @overload
    def render(
        self, html: str, *, fmt: Literal["png", "jpeg"],
        quality: int = 85, height: int = 0, shrink_to_fit: bool = True,
    ) -> bytes: ...
    @overload
    def render(
        self, html: str, *, fmt: str | OutputFormat = ...,
        quality: int = 85, height: int = 0, shrink_to_fit: bool = True,
    ) -> bytes | RawResult: ...

@overload
def render(
    html: str, width: int, *, locale: str = ..., dpi: float = ...,
    device_height: int = ..., fonts: FontConfig | None = ...,
    images: ImageConfig | None = ..., fmt: Literal["raw"],
    quality: int = ..., height: int = ..., shrink_to_fit: bool = ...,
) -> RawResult: ...
@overload
def render(
    html: str, width: int, *, locale: str = ..., dpi: float = ...,
    device_height: int = ..., fonts: FontConfig | None = ...,
    images: ImageConfig | None = ..., fmt: Literal["png", "jpeg"],
    quality: int = ..., height: int = ..., shrink_to_fit: bool = ...,
) -> bytes: ...
@overload
def render(
    html: str, width: int, *, locale: str = ..., dpi: float = ...,
    device_height: int = ..., fonts: FontConfig | None = ...,
    images: ImageConfig | None = ..., fmt: str | OutputFormat = ...,
    quality: int = ..., height: int = ..., shrink_to_fit: bool = ...,
) -> bytes | RawResult: ...
