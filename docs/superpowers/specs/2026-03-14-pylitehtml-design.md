# pylitehtml Design Spec

**Date:** 2026-03-14
**Status:** Approved

## Overview

A Python pip package that wraps litehtml (C++ HTML/CSS layout engine) with a Cairo/Pango rendering backend to convert static HTML+CSS into images. Designed for high concurrency, zero system dependencies after install, and multi-platform distribution.

## Goals

- HTML + CSS → PNG / JPEG / raw RGBA bytes
- High concurrency safe (thread pool friendly)
- `pip install pylitehtml` — no system dependencies
- Linux + macOS + Windows wheels
- Python 3.10+

## Non-Goals

- JavaScript execution
- Animations or dynamic effects
- Full browser compatibility
- GIF animation (first frame only supported)

---

## Architecture

### Component Diagram

```
Python layer (pybind11)
    └── Renderer / render()
            ↓
C++ binding layer
    ├── py_container.h/cpp     # litehtml document_container (Cairo+Pango, no GDK)
    │                          # instantiated per render() call — stack-local, never shared
    ├── image_cache.h/cpp      # thread-safe image loading (LRU, local + HTTP)
    └── font_manager.h/cpp     # font init: bundled fonts + @font-face support
            ↓
Third-party C++ libraries
    ├── litehtml               # HTML parsing + CSS layout (git submodule)
    │   └── containers/cairo/  # reused: container_cairo_pango (GDK removed)
    ├── Cairo                  # 2D drawing
    ├── Pango + PangoCairo     # text layout and font rendering
    ├── libjpeg-turbo          # JPEG encode/decode
    ├── libwebp                # WebP decode only
    └── cpp-httplib            # header-only HTTP client for image fetching
```

### Render Data Flow

```
renderer.render(html, base_url, width, height, fmt)
    → create stack-local PyContainer(renderer.font_manager, renderer.image_cache)
    → litehtml::document::createFromString(html, base_url, &py_container)
    → litehtml::document::render(width)                  # layout calculation
    → actual_height = (height==0) ? document::height() : height
    → cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, actual_height)
    → litehtml::document::draw(&py_container, cairo_ctx, 0, 0)
        ├── draw_text()       → PangoCairo
        ├── draw_solid_fill() → Cairo
        ├── draw_borders()    → Cairo
        ├── draw_image()      → ImageCache → Cairo
        └── draw_*_gradient() → Cairo
    → encode:
        PNG  → cairo_surface_write_to_png()
        JPEG → swizzle ARGB32→RGB + libjpeg-turbo compress
        RAW  → swizzle ARGB32→RGBA bytes + width + height
    → return Python bytes / RawResult
```

### Project Layout

```
pylitehtml/
├── pyproject.toml              # scikit-build-core + package metadata
├── CMakeLists.txt              # top-level build
├── src/
│   ├── cpp/
│   │   ├── binding.cpp         # pybind11 entry: Renderer class + render()
│   │   ├── py_container.h/cpp  # document_container impl (Cairo+Pango, no GDK)
│   │   │                       # NOTE: always instantiated per render() call
│   │   ├── image_cache.h/cpp   # LRU image cache with shared_mutex
│   │   └── font_manager.h/cpp  # fontconfig init: bundled + extra fonts
│   └── python/
│       └── pylitehtml/
│           ├── __init__.py     # exports: Renderer, render(), OutputFormat, errors
│           └── _core.pyi       # type stubs (see API section for signatures)
├── fonts/                      # Noto Sans (Latin+CJK subset) + DejaVu Sans (~4MB)
├── third_party/
│   └── litehtml/               # git submodule
└── .github/workflows/
    └── wheels.yml              # cibuildwheel: Linux / macOS / Windows
```

---

## Python API

### Type Stubs (`_core.pyi`)

```python
from enum import IntEnum
from dataclasses import dataclass

class OutputFormat(IntEnum):
    PNG = 0
    JPEG = 1
    RAW = 2

@dataclass
class RawResult:
    data: bytes    # true RGBA, row-major (C++ swizzles from Cairo ARGB32)
    width: int
    height: int

class RenderError(Exception): ...
class ImageFetchError(Exception): ...

class Renderer:
    def __init__(
        self,
        width: int,
        dpi: int = 96,
        default_font: str = "Noto Sans",
        default_font_size: int = 16,
        extra_fonts: list[str] = [],
        image_cache_max_bytes: int = 64 * 1024 * 1024,  # 64MB
        image_timeout_ms: int = 5000,
        image_max_bytes: int = 10 * 1024 * 1024,        # 10MB
        allow_http_images: bool = True,
    ) -> None: ...

    def render(
        self,
        html: str,
        *,
        base_url: str = "",
        height: int = 0,            # 0 = auto (content height)
        fmt: OutputFormat = OutputFormat.PNG,
        quality: int = 85,          # JPEG only
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
```

### Usage Examples

```python
import pylitehtml
from pylitehtml import Renderer, OutputFormat

# Main API — create once, render many times (thread-safe)
renderer = Renderer(
    width=800,
    default_font="Noto Sans",
    image_timeout_ms=3000,
    allow_http_images=True,
)

# PNG
png: bytes = renderer.render("<h1>Hello</h1>")

# JPEG
jpg: bytes = renderer.render(html, fmt=OutputFormat.JPEG, quality=85)

# Raw RGBA (true RGBA byte order, safe for Pillow / numpy)
raw = renderer.render(html, fmt=OutputFormat.RAW)
# raw.data layout: [R0,G0,B0,A0, R1,G1,B1,A1, ...]

# With base URL (enables <link> CSS and relative image paths)
png = renderer.render(html, base_url="file:///path/to/assets/")

# Per-call height override
png = renderer.render(html, height=600)   # fixed 600px tall

# Convenience function (one-shot, no caching)
png = pylitehtml.render("<h1>Hello</h1>", width=800)

# High-concurrency pattern
import concurrent.futures
renderer = Renderer(width=1200)   # one per process
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    results = list(pool.map(renderer.render, html_list))
```

### Error Handling

```python
from pylitehtml import RenderError, ImageFetchError

try:
    png = renderer.render(html)
except RenderError as e:
    ...           # layout or rendering failure
except ImageFetchError as e:
    ...           # image download timeout, size exceeded, or network error
                  # (non-fatal: renderer can be configured to skip failed images)
```

---

## Thread Safety

- `Renderer` stores: `FontManager` (read-only after init) + `ImageCache` (shared_mutex)
- `render()` creates a **stack-local** `PyContainer` on every call — it is NEVER stored as a `Renderer` member
- `PyContainer` holds a `cairo_t*` and `cairo_surface_t*` that are local to that call stack
- `ImageCache` uses `std::shared_mutex`: concurrent reads, exclusive writes
- Result: multiple threads can call `renderer.render()` simultaneously with no locking on the hot path

---

## Image Support

| Format | Decode library | Notes |
|--------|---------------|-------|
| PNG | Cairo built-in (libpng) | Full support |
| JPEG | libjpeg-turbo | Full support |
| WebP | libwebp | Decode only |
| GIF | Cairo built-in | First frame only |

- **Local paths:** `<img src="/absolute/path/image.png">` or relative to `base_url`
- **HTTP/HTTPS:** fetched via cpp-httplib, subject to `image_timeout_ms` and `image_max_bytes`
- **Cache:** per-`Renderer` LRU cache, bounded by `image_cache_max_bytes` (default 64MB)
- **Security:** `allow_http_images=False` disables all network fetching

---

## CSS Loading (`import_css`)

The `document_container::import_css()` callback is called for `<link rel="stylesheet">` and `@import`:

- If `base_url` is a `file://` URL: CSS loaded from local filesystem relative to that path
- If `base_url` is an `http(s)://` URL: CSS fetched via cpp-httplib (same timeout/size limits as images)
- If `base_url` is empty: `<link>` and `@import` silently produce no CSS (only inline styles apply)
- Inline `<style>` blocks always work regardless of `base_url`

---

## Font Strategy

- **Bundled fonts:** Noto Sans (Latin + CJK subset) + DejaVu Sans, ~4MB, at `pylitehtml/fonts/`
- **Registration:** fontconfig `FcConfigAppFontAddFile()` called in `FontManager` constructor
- **System fonts:** fontconfig also scans system font directories as fallback
- **Custom fonts:** `extra_fonts` list in `Renderer` constructor adds additional TTF/OTF paths
- **`@font-face`:** local `src: url("...")` paths resolved relative to `base_url`

### Windows Font Pipeline

On Windows, fontconfig is provided via vcpkg and configured explicitly:
- A bundled `fonts.conf` is written to a temp dir at `Renderer` init time
- `FcConfigSetCurrent()` called with this config so bundled fonts are always found
- `extra_fonts` uses `FcConfigAppFontAddFile()` (same API as Linux/macOS)
- Pango on Windows uses fontconfig via the `pangofc-fontmap` backend (linked via vcpkg)

---

## Output Pixel Format

Cairo's `CAIRO_FORMAT_ARGB32` stores pixels as native-endian 32-bit integers (`0xAARRGGBB` on little-endian = `[B,G,R,A]` in memory).

Before returning to Python, the C++ layer **always swizzles** to true RGBA byte order `[R,G,B,A]`:
- `OutputFormat.RAW` → `RawResult.data` is guaranteed RGBA, safe for `PIL.Image.frombuffer("RGBA", ...)`
- `OutputFormat.PNG` → Cairo's built-in PNG encoder handles byte order internally
- `OutputFormat.JPEG` → swizzle to RGB (drop alpha) before libjpeg-turbo compression

---

## Build & Distribution

### Build System

```toml
# pyproject.toml
[build-system]
requires = ["scikit-build-core", "pybind11"]
build-backend = "scikit_build_core.build"

[tool.scikit-build]
cmake.build-type = "Release"
wheel.packages = ["src/python/pylitehtml"]
```

### CMake Dependencies

```cmake
find_package(Cairo REQUIRED)
find_package(PangoCairo REQUIRED)
find_package(Fontconfig REQUIRED)
find_package(JPEG REQUIRED)        # libjpeg-turbo
find_package(WebP REQUIRED)        # libwebp
# cpp-httplib: header-only, vendored in src/cpp/
```

### Platform Strategy

| Platform | Dependencies source | Bundle tool | Wheel size est. |
|----------|--------------------|-------------|-----------------|
| Linux | manylinux2014 (Cairo, Pango, libjpeg-turbo, libwebp, fontconfig) | `auditwheel repair` | ~14MB |
| macOS | vcpkg | `delocate` | ~18MB |
| Windows | vcpkg (static link all) | `delvewheel` | ~20MB |

### cibuildwheel Matrix

```yaml
CIBW_BUILD: "cp310-* cp311-* cp312-* cp313-*"
CIBW_ARCHS_MACOS: "x86_64 arm64"
CIBW_ARCHS_LINUX: "x86_64 aarch64"
CIBW_ARCHS_WINDOWS: "AMD64"
```

Triggers on `git tag v*`, uploads to PyPI automatically.

---

## Testing Strategy

| Test type | Tool | What it covers |
|-----------|------|----------------|
| Golden image tests | pytest + pixelmatch | pixel-diff vs reference PNGs for known HTML |
| Thread safety | pytest + threading | 50 concurrent renders, check for crashes/corruption |
| Font rendering | pytest | bundled font loads, @font-face, CJK characters |
| Image loading | pytest + responses mock | local PNG/JPEG/WebP, HTTP fetch, timeout, size limit |
| CSS loading | pytest | inline style, `<link>` with base_url, @import |
| Cross-platform | cibuildwheel test step | smoke test on each platform/arch |

---

## Key Implementation Notes

1. **Remove GDK:** `render2png.cpp` uses `GdkPixbuf` — replace with `cairo_surface_write_to_png()` and libjpeg-turbo; drop all `#include <gdk/gdk.h>`
2. **cpp-httplib:** header-only, vendored in `src/cpp/vendor/`; configure `CPPHTTPLIB_OPENSSL_SUPPORT=OFF` to avoid OpenSSL dependency
3. **PyContainer lifetime:** constructor takes `FontManager&` and `ImageCache&` by reference; destroyed at end of `render()` scope
4. **Auto height:** call `document::render(width)` first, then read `document::height()`, then create surface; if `height != 0`, clip/pad to requested height
5. **JPEG alpha:** flatten ARGB onto white background before JPEG encode (JPEG has no alpha channel)
6. **fontconfig on Windows:** ship `fonts/fonts.conf` in the wheel; set `FONTCONFIG_FILE` env var in `FontManager` constructor if not already set
