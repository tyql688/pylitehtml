# pylitehtml

![CI](https://github.com/tyql688/pylitehtml/actions/workflows/test.yml/badge.svg)

HTML+CSS → PNG/JPEG image renderer. Lightweight, no headless browser, thread-safe.

English | [中文](README_zh.md)

## Install

```bash
pip install pylitehtml
```

## Quick Start

```python
import pylitehtml

# One-shot convenience function
png_bytes = pylitehtml.render("<h1>Hello</h1>", width=800)
with open("output.png", "wb") as f:
    f.write(png_bytes)
```

## API Reference

### `pylitehtml.render(html, width, *, base_url="", height=0, fmt=OutputFormat.PNG, quality=85)`

Convenience wrapper — creates a temporary `Renderer`, renders once, returns bytes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `html` | `str` | — | HTML source to render |
| `width` | `int` | — | Viewport width in pixels |
| `base_url` | `str` | `""` | Base URL for resolving relative resources |
| `height` | `int` | `0` | Fixed height (0 = auto) |
| `fmt` | `OutputFormat` | `PNG` | Output format |
| `quality` | `int` | `85` | JPEG quality (1–100, ignored for PNG/RAW) |

Returns `bytes` (PNG or JPEG) or `RawResult` (RAW).

---

### `class Renderer(width=800, default_font="Noto Sans", default_font_size=16, extra_fonts=[], image_cache_max_bytes=67108864, image_timeout_ms=5000, image_max_bytes=10485760, allow_http_images=True)`

Reusable renderer. Create once, call `.render()` many times. Thread-safe.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | `800` | Viewport width in pixels |
| `default_font` | `str` | `"Noto Sans"` | Fallback font family name |
| `default_font_size` | `int` | `16` | Default font size in pixels |
| `extra_fonts` | `list[str]` | `[]` | Additional font file paths to register |
| `image_cache_max_bytes` | `int` | `67108864` | Max image cache size in bytes (64 MB) |
| `image_timeout_ms` | `int` | `5000` | HTTP image fetch timeout in milliseconds |
| `image_max_bytes` | `int` | `10485760` | Max size per image in bytes (10 MB) |
| `allow_http_images` | `bool` | `True` | Whether to fetch images over HTTP/HTTPS |

#### `Renderer.render(html, *, base_url="", height=0, fmt=OutputFormat.PNG, quality=85)`

Render HTML and return image data.

Returns `bytes` for PNG/JPEG, or `RawResult` for RAW.

---

### `class OutputFormat`

```python
OutputFormat.PNG   # PNG-encoded bytes
OutputFormat.JPEG  # JPEG-encoded bytes
OutputFormat.RAW   # Uncompressed RGBA bytes (see RawResult)
```

---

### `class RawResult`

Returned when `fmt=OutputFormat.RAW`.

```python
result.data    # bytes — RGBA pixel data, row-major
result.width   # int — image width in pixels
result.height  # int — image height in pixels
```

---

### `class RenderError(Exception)`

Raised when rendering fails (e.g., bad HTML structure, resource load error).

---

### `class ImageFetchError(Exception)`

Raised when an image cannot be fetched or decoded.

---

## Examples

### Reusable Renderer

```python
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=1200)

# PNG (default)
png = renderer.render("<p>Hello</p>")

# JPEG
jpg = renderer.render("<p>Hello</p>", fmt=OutputFormat.JPEG, quality=90)

# Raw RGBA
raw = renderer.render("<p>Hello</p>", fmt=OutputFormat.RAW)
print(raw.width, raw.height, len(raw.data))  # e.g. 1200 600 2880000
```

### High Concurrency

```python
import concurrent.futures
from pylitehtml import Renderer

renderer = Renderer(width=800)  # shared across threads

html_list = ["<h1>Page {}</h1>".format(i) for i in range(1000)]

with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    images = list(pool.map(renderer.render, html_list))
```

### Custom Fonts

```python
from pylitehtml import Renderer

renderer = Renderer(
    width=800,
    fonts_dir="/path/to/my/fonts",   # directory with .ttf/.otf files
    default_font="My Custom Font",
    extra_fonts=["/path/to/extra.ttf"],
)
```

### Convert to PIL Image

```python
from PIL import Image
import io
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=800)
raw = renderer.render("<h1>Hello</h1>", fmt=OutputFormat.RAW)
img = Image.frombytes("RGBA", (raw.width, raw.height), raw.data)
img.save("output.png")
```

### NumPy Array

```python
import numpy as np
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=800)
raw = renderer.render("<h1>Hello</h1>", fmt=OutputFormat.RAW)
arr = np.frombuffer(raw.data, dtype=np.uint8).reshape(raw.height, raw.width, 4)
# arr shape: (height, width, 4) — channels are BGRA (Cairo native)
```

## Output Formats

| Format | Return type | Description |
|--------|-------------|-------------|
| `PNG` | `bytes` | Lossless, best for screenshots |
| `JPEG` | `bytes` | Smaller files, `quality` 1–100 |
| `RAW` | `RawResult` | Uncompressed BGRA pixels (Cairo native channel order) |

## Supported Versions

| Python | Linux | macOS | Windows |
|--------|-------|-------|---------|
| 3.10 | ✅ | ✅ | ✅ |
| 3.11 | ✅ | ✅ | ✅ |
| 3.12 | ✅ | ✅ | ✅ |
| 3.13 | ✅ | ✅ | ✅ |
| 3.14 | ✅ | ✅ | ✅ |

## Known Limitations

- **No JavaScript** — static HTML+CSS only
- **No network requests** — external images/stylesheets must be inlined or served locally
- **No SVG** — SVG images are not rendered
- **CSS subset** — powered by [litehtml](https://github.com/litehtml/litehtml); some advanced CSS features (e.g., CSS Grid, Flexbox) may have incomplete support

## Thread Safety

`Renderer` is thread-safe after construction. Multiple threads may call `.render()` concurrently on a single instance. Do not construct multiple `Renderer` instances concurrently.

## Building from Source

### System Dependencies

**Ubuntu / Debian**
```bash
sudo apt-get update
sudo apt-get install -y libcairo2-dev libpango1.0-dev libfontconfig1-dev \
  libwebp-dev libjpeg-turbo8-dev cmake ninja-build pkg-config
```

**Fedora / RHEL / CentOS**
```bash
sudo dnf install -y cairo-devel pango-devel fontconfig-devel \
  libwebp-devel libjpeg-turbo-devel cmake ninja-build pkgconf
```

**macOS (Homebrew)**
```bash
brew install cairo pango fontconfig webp jpeg-turbo cmake ninja
```
> Note: On macOS, use Apple's clang (not Homebrew LLVM) to avoid C++ ABI issues:
> `CC=/usr/bin/clang CXX=/usr/bin/clang++ pip install -e . --no-build-isolation`

**Windows**

Windows builds require [vcpkg](https://github.com/microsoft/vcpkg) and Visual Studio 2019+.
See [`.github/workflows/test.yml`](.github/workflows/test.yml) for the full CI build recipe.

### Build

```bash
# Recommended: use a virtual environment
uv venv .venv && uv pip install scikit-build-core pybind11 pytest pillow

# Build and install in editable mode
# macOS: prefix with CC=/usr/bin/clang CXX=/usr/bin/clang++ if using Homebrew LLVM
pip install -e . --no-build-isolation

# Run tests
pytest tests/ -v
```

## Built On

- [litehtml](https://github.com/litehtml/litehtml) — HTML/CSS layout engine
- [Cairo](https://www.cairographics.org/) — 2D graphics rendering
- [Pango](https://pango.gnome.org/) — text layout and rendering
- [FontConfig](https://www.freedesktop.org/wiki/Software/fontconfig/) — font discovery
- [pybind11](https://github.com/pybind/pybind11) — Python/C++ bindings

## License

MIT
