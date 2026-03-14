# pylitehtml Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pip-installable Python package that wraps litehtml to render static HTML+CSS into PNG/JPEG/raw RGBA images, with full thread safety and multi-platform wheel distribution.

**Architecture:** litehtml handles HTML parsing and CSS layout; Cairo+Pango render the layout to a pixel buffer via `PyContainer` (inherits from `container_cairo`, adds Pango text layer) that is instantiated stack-locally per `render()` call for thread safety. pybind11 exposes a `Renderer` class and a `render()` convenience function to Python. Wheels are built for Linux/macOS/Windows via cibuildwheel.

**Tech Stack:** C++17, litehtml (git submodule), Cairo, PangoCairo, fontconfig, libjpeg-turbo, libwebp, cpp-httplib (header-only), pybind11, scikit-build-core, cibuildwheel.

**Spec:** `docs/superpowers/specs/2026-03-14-pylitehtml-design.md`

---

## Dev Environment Setup (read before starting)

**macOS:**
```bash
brew install cairo pango fontconfig webp jpeg-turbo cmake ninja python@3.11
pip install scikit-build-core pybind11 pytest pillow
```

**Ubuntu/Debian:**
```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev libfontconfig1-dev \
  libwebp-dev libjpeg-turbo8-dev cmake ninja-build python3-dev
pip install scikit-build-core pybind11 pytest pillow
```

**Windows:** install vcpkg, then:
```powershell
vcpkg install cairo pango fontconfig libwebp libjpeg-turbo --triplet x64-windows-static
pip install scikit-build-core pybind11 pytest pillow
```

**Build in editable mode (after scaffold is done):**
```bash
pip install -e . --no-build-isolation
```

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package metadata, scikit-build-core build backend |
| `CMakeLists.txt` | Top-level CMake: find deps, compile `_core` extension |
| `src/cpp/binding.cpp` | pybind11 module: exposes `Renderer`, `OutputFormat`, `RawResult`, exceptions |
| `src/cpp/image_cache.h/cpp` | FIFO-eviction image cache (thread-safe with shared_mutex); holds decoded `cairo_surface_t*` |
| `src/cpp/font_manager.h/cpp` | fontconfig init with bundled + extra fonts; Pango font map setup |
| `src/cpp/py_container.h/cpp` | Inherits `container_cairo`; adds Pango text + image loading via ImageCache |
| `src/cpp/encode.h/cpp` | PNG/JPEG/RAW encoding; ARGB32→RGBA swizzle; safe libjpeg error handling |
| `src/cpp/vendor/httplib.h` | cpp-httplib single header (vendored, Task 7 — must be done before Task 6) |
| `src/python/pylitehtml/__init__.py` | Re-exports `Renderer`, `render()`, `OutputFormat`, `RawResult`, errors |
| `src/python/pylitehtml/_core.pyi` | Full type stubs |
| `fonts/NotoSans-Regular.ttf` | Bundled Latin font |
| `fonts/DejaVuSans.ttf` | Bundled fallback font |
| `fonts/NotoSansSC-Regular.otf` | Bundled CJK font |
| `fonts/fonts.conf` | fontconfig config for Windows |
| `tests/conftest.py` | Shared fixtures |
| `tests/test_basic.py` | Smoke tests (written first — TDD) |
| `tests/test_fonts.py` | Font tests (written before FontManager impl) |
| `tests/test_images.py` | Image loading tests (written before ImageCache impl) |
| `tests/test_css.py` | CSS loading tests |
| `tests/test_thread_safety.py` | Concurrent render tests |
| `.github/workflows/` | CI + cibuildwheel |

---

## Chunk 1: Project Scaffold & Build System

### Task 1: Git submodule + directory skeleton

**Files:**
- Create: `.gitmodules`, `.gitignore`
- Create: `src/cpp/vendor/`, `src/python/pylitehtml/`, `fonts/`, `tests/`

- [ ] **Step 1: Add litehtml as git submodule**

```bash
git submodule add https://github.com/litehtml/litehtml.git third_party/litehtml
git submodule update --init --recursive
```

Expected: `third_party/litehtml/` populated.

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p src/cpp/vendor src/python/pylitehtml fonts tests/assets tests/golden scripts
```

- [ ] **Step 3: Create `.gitignore`**

```
build/
dist/
*.egg-info/
__pycache__/
*.so
*.pyd
*.dylib
_skbuild/
.cmake/
tests/assets/
```

- [ ] **Step 4: Commit**

```bash
git add .gitmodules .gitignore third_party/ src/ fonts/ tests/ scripts/
git commit -m "chore: project scaffold and litehtml submodule"
```

---

### Task 2: pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["scikit-build-core>=0.9", "pybind11>=2.12"]
build-backend = "scikit_build_core.build"

[project]
name = "pylitehtml"
version = "0.1.0"
description = "HTML+CSS to image renderer based on litehtml"
readme = "README.md"
license = { text = "BSD-3-Clause" }
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "pillow", "numpy"]

[tool.scikit-build]
cmake.build-type = "Release"
wheel.packages = ["src/python/pylitehtml"]
cmake.verbose = true

[tool.scikit-build.cmake.define]
LITEHTML_BUILD_TESTING = "OFF"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml with scikit-build-core"
```

---

### Task 3: CMakeLists.txt

**Files:**
- Create: `CMakeLists.txt`
- Create: `src/cpp/binding.cpp` (minimal stub)
- Create stub .h/.cpp for all C++ components

- [ ] **Step 1: Write `CMakeLists.txt`**

```cmake
cmake_minimum_required(VERSION 3.21)
project(pylitehtml CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Dependencies via pkg-config ───────────────────────────────────────────────
find_package(PkgConfig REQUIRED)
pkg_check_modules(CAIRO     REQUIRED IMPORTED_TARGET cairo)
pkg_check_modules(PANGOCAIRO REQUIRED IMPORTED_TARGET pangocairo)
pkg_check_modules(FONTCONFIG REQUIRED IMPORTED_TARGET fontconfig)

# JPEG: prefer CMake config (libjpeg-turbo), fall back to pkg-config
find_package(JPEG QUIET)
if(NOT JPEG_FOUND)
  pkg_check_modules(JPEG REQUIRED IMPORTED_TARGET libjpeg)
endif()

# WebP: prefer CMake config, fall back to pkg-config
find_package(WebP CONFIG QUIET)
if(NOT WebP_FOUND)
  pkg_check_modules(WEBP REQUIRED IMPORTED_TARGET libwebp)
endif()

# ── litehtml ──────────────────────────────────────────────────────────────────
set(LITEHTML_BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/litehtml)

# ── pybind11 ─────────────────────────────────────────────────────────────────
find_package(pybind11 CONFIG REQUIRED)

# ── Extension module ─────────────────────────────────────────────────────────
pybind11_add_module(_core
  src/cpp/binding.cpp
  src/cpp/image_cache.cpp
  src/cpp/font_manager.cpp
  src/cpp/py_container.cpp
  src/cpp/encode.cpp
  # Reuse Cairo drawing helpers from litehtml (no GDK dependency)
  third_party/litehtml/containers/cairo/container_cairo.cpp
  third_party/litehtml/containers/cairo/cairo_borders.cpp
)

target_include_directories(_core PRIVATE
  src/cpp
  src/cpp/vendor
  third_party/litehtml/include
  third_party/litehtml/containers/cairo
)

# Use IMPORTED_TARGET from pkg_check_modules — carries both include dirs AND cflags
target_link_libraries(_core PRIVATE
  litehtml
  PkgConfig::CAIRO
  PkgConfig::PANGOCAIRO
  PkgConfig::FONTCONFIG
)

if(JPEG_FOUND AND TARGET JPEG::JPEG)
  target_link_libraries(_core PRIVATE JPEG::JPEG)
elseif(TARGET PkgConfig::JPEG)
  target_link_libraries(_core PRIVATE PkgConfig::JPEG)
endif()

if(TARGET WebP::webp)
  target_link_libraries(_core PRIVATE WebP::webp)
elseif(TARGET PkgConfig::WEBP)
  target_link_libraries(_core PRIVATE PkgConfig::WEBP)
endif()

# stdc++fs on older Linux toolchains
if(UNIX AND NOT APPLE)
  target_link_libraries(_core PRIVATE stdc++fs)
endif()

# ── Install ───────────────────────────────────────────────────────────────────
install(TARGETS _core DESTINATION pylitehtml)
install(DIRECTORY fonts/ DESTINATION pylitehtml/fonts)
```

**Note:** Using `IMPORTED_TARGET` with `pkg_check_modules` automatically propagates compile flags (including `-pthread`, feature macros) to the target — no manual `target_compile_options` needed.

- [ ] **Step 2: Write minimal stub `src/cpp/binding.cpp`**

```cpp
#include <pybind11/pybind11.h>
namespace py = pybind11;
PYBIND11_MODULE(_core, m) { m.doc() = "pylitehtml stub"; }
```

- [ ] **Step 3: Create empty stub implementation files**

```bash
for f in image_cache font_manager py_container encode; do
  touch src/cpp/${f}.h src/cpp/${f}.cpp
done
```

- [ ] **Step 4: Verify stub build succeeds**

```bash
pip install -e . --no-build-isolation -v 2>&1 | tail -10
python -c "import pylitehtml._core; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add CMakeLists.txt src/cpp/
git commit -m "chore: CMakeLists.txt with pkg-config IMPORTED_TARGET and stub binding"
```

---

### Task 4: Python package skeleton

**Files:**
- Create: `src/python/pylitehtml/__init__.py`
- Create: `src/python/pylitehtml/_core.pyi`

- [ ] **Step 1: Write `_core.pyi`**

```python
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
        dpi: int = 96,
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
```

- [ ] **Step 2: Write `__init__.py`**

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add src/python/
git commit -m "feat: Python package skeleton with type stubs"
```

---

### Task 5: Bundle fonts

**Files:**
- Create: `scripts/download_fonts.sh`
- Create: `fonts/fonts.conf`
- Populate: `fonts/*.ttf`, `fonts/*.otf`

- [ ] **Step 1: Write download script**

```bash
#!/usr/bin/env bash
# scripts/download_fonts.sh
set -e
mkdir -p fonts

curl -L "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2" \
  -o /tmp/dejavu.tar.bz2
tar -xjf /tmp/dejavu.tar.bz2 -C /tmp
cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf fonts/

curl -L "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf" \
  -o fonts/NotoSans-Regular.ttf

curl -L "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC-Regular.otf" \
  -o fonts/NotoSansSC-Regular.otf

echo "Done: $(ls -lh fonts/)"
```

- [ ] **Step 2: Run download script**

```bash
chmod +x scripts/download_fonts.sh && ./scripts/download_fonts.sh
ls -lh fonts/
```

Expected: three font files totalling ~4MB.

- [ ] **Step 3: Write `fonts/fonts.conf`**

```xml
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir prefix="relative">.</dir>
  <cachedir prefix="relative">cache</cachedir>
</fontconfig>
```

- [ ] **Step 4: Commit**

```bash
git add fonts/ scripts/
git commit -m "chore: bundle NotoSans, NotoSansSC, DejaVuSans fonts"
```

---

## Chunk 2: TDD — Write Tests Before C++ Implementation

**TDD rule:** write failing tests first, then implement. The tests below will fail (import error) until the C++ is done. That is expected and correct.

### Task 6: Write all test files (RED phase)

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_basic.py`
- Create: `tests/test_fonts.py`
- Create: `tests/test_images.py`
- Create: `tests/test_css.py`
- Create: `tests/test_thread_safety.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from pylitehtml import Renderer, OutputFormat

SIMPLE_HTML = """<html><style>
  body { font-family: "Noto Sans", sans-serif; background: #fff; margin: 0; padding: 20px; }
  h1 { color: #e00; font-size: 32px; }
  p  { color: #333; font-size: 16px; }
</style><body><h1>Hello pylitehtml</h1><p>Test paragraph.</p></body></html>"""

FLEX_HTML = """<html><style>
  .row { display: flex; gap: 10px; padding: 10px; }
  .box { width: 100px; height: 100px; background: #4af; border-radius: 8px; }
</style><body><div class="row">
  <div class="box"></div>
  <div class="box" style="background:#f4a"></div>
  <div class="box" style="background:#af4"></div>
</div></body></html>"""

@pytest.fixture(scope="session")
def renderer():
    return Renderer(width=800)

@pytest.fixture
def simple_html():
    return SIMPLE_HTML
```

- [ ] **Step 2: Write `tests/test_basic.py`**

```python
# tests/test_basic.py
import pylitehtml
from pylitehtml import Renderer, OutputFormat, RawResult

def test_render_png(renderer, simple_html):
    png = renderer.render(simple_html)
    assert isinstance(png, bytes)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'

def test_render_jpeg(renderer, simple_html):
    jpg = renderer.render(simple_html, fmt=OutputFormat.JPEG, quality=80)
    assert isinstance(jpg, bytes)
    assert jpg[:2] == b'\xff\xd8'

def test_render_raw_rgba(renderer, simple_html):
    raw = renderer.render(simple_html, fmt=OutputFormat.RAW)
    assert isinstance(raw, RawResult)
    assert raw.width == 800
    assert raw.height > 0
    assert len(raw.data) == raw.width * raw.height * 4

def test_raw_rgba_byte_order(renderer):
    """ARGB32 → RGBA swizzle: red background must produce R=255, G=0, B=0."""
    html = "<html><body style='background:#ff0000;margin:0'><div style='height:2px'></div></body></html>"
    raw = renderer.render(html, fmt=OutputFormat.RAW, height=2)
    r, g, b, a = raw.data[0], raw.data[1], raw.data[2], raw.data[3]
    assert r == 255, f"R={r}"
    assert g == 0,   f"G={g}"
    assert b == 0,   f"B={b}"

def test_auto_height(renderer):
    raw = renderer.render("<p>Hello</p>", fmt=OutputFormat.RAW)
    assert raw.height > 0

def test_fixed_height(renderer, simple_html):
    raw = renderer.render(simple_html, fmt=OutputFormat.RAW, height=600)
    assert raw.height == 600

def test_convenience_function(simple_html):
    png = pylitehtml.render(simple_html, width=400)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'

def test_flexbox():
    r = Renderer(width=400)
    html = """<html><style>.row{display:flex}.box{width:50px;height:50px;background:red}</style>
    <body><div class="row"><div class="box"></div></div></body></html>"""
    png = r.render(html)
    assert len(png) > 0
```

- [ ] **Step 3: Write `tests/test_fonts.py`**

```python
# tests/test_fonts.py
import shutil, pathlib
import pylitehtml
from pylitehtml import Renderer, OutputFormat

FONTS_DIR = pathlib.Path(pylitehtml.__file__).parent / "fonts"

def test_bundled_noto_sans():
    r = Renderer(width=400, default_font="Noto Sans")
    assert len(r.render("<p>Latin ABC 123</p>")) > 0

def test_bundled_dejavusans():
    r = Renderer(width=400, default_font="DejaVu Sans")
    assert len(r.render("<p>DejaVu text</p>")) > 0

def test_cjk_text():
    r = Renderer(width=400)
    assert len(r.render("<p>中文测试 日本語</p>")) > 0

def test_extra_fonts(tmp_path):
    dst = tmp_path / "Copy.ttf"
    shutil.copy(FONTS_DIR / "DejaVuSans.ttf", dst)
    r = Renderer(width=400, extra_fonts=[str(dst)], default_font="DejaVu Sans")
    assert len(r.render("<p>Extra font</p>")) > 0

def test_font_size_affects_height():
    big = Renderer(width=400, default_font_size=32)
    small = Renderer(width=400, default_font_size=8)
    raw_big   = big.render("<p>X</p>", fmt=OutputFormat.RAW)
    raw_small = small.render("<p>X</p>", fmt=OutputFormat.RAW)
    assert raw_big.height >= raw_small.height

def test_text_decoration():
    """Underline/strikethrough must not crash the renderer."""
    r = Renderer(width=400)
    html = "<p style='text-decoration:underline'>underline</p>"
    assert len(r.render(html)) > 0
    html2 = "<p style='text-decoration:line-through'>strike</p>"
    assert len(r.render(html2)) > 0
```

- [ ] **Step 4: Write `tests/test_images.py`**

```python
# tests/test_images.py
import time, pathlib, pytest
from PIL import Image
from pylitehtml import Renderer, OutputFormat

ASSETS = pathlib.Path(__file__).parent / "assets"

@pytest.fixture(autouse=True, scope="session")
def create_assets():
    ASSETS.mkdir(exist_ok=True)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(ASSETS / "red.png")
    Image.new("RGB",  (10, 10), (0, 0, 255)).save(ASSETS / "blue.jpg")

def test_local_png():
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "red.png"}" width="10" height="10">'
    assert len(r.render(html)) > 0

def test_local_jpeg():
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "blue.jpg"}" width="10" height="10">'
    assert len(r.render(html)) > 0

def test_allow_http_false_skips_image():
    r = Renderer(width=200, allow_http_images=False)
    html = '<img src="http://example.com/x.png" width="10" height="10">'
    assert len(r.render(html)) > 0  # no raise, image skipped

def test_http_timeout_respected():
    r = Renderer(width=200, image_timeout_ms=200)
    html = '<img src="http://10.255.255.1/x.png" width="10" height="10">'
    start = time.monotonic()
    r.render(html)
    assert time.monotonic() - start < 3.0
```

- [ ] **Step 5: Write `tests/test_css.py`**

```python
# tests/test_css.py
import pathlib, pytest
from pylitehtml import Renderer, OutputFormat

ASSETS = pathlib.Path(__file__).parent / "assets"

@pytest.fixture(autouse=True, scope="session")
def create_css_assets():
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "style.css").write_text("body { background: #0000ff !important; }")

def test_inline_style_green():
    r = Renderer(width=100)
    raw = r.render("<html><body style='background:#00ff00;margin:0'>"
                   "<div style='height:2px'></div></body></html>",
                   fmt=OutputFormat.RAW, height=2)
    assert raw.data[1] > 200, "G channel should be high (green)"

def test_link_with_base_url():
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>CSS</p></body></html>'
    png = r.render(html, base_url=f"file://{ASSETS}/index.html")
    assert len(png) > 0

def test_no_base_url_link_ignored():
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>no css</p></body></html>'
    assert len(r.render(html)) > 0  # no raise

def test_style_block_always_works():
    r = Renderer(width=100)
    raw = r.render("<html><head><style>body{background:#00ff00;margin:0}</style></head>"
                   "<body><div style='height:2px'></div></body></html>",
                   fmt=OutputFormat.RAW, height=2)
    assert raw.data[1] > 200
```

- [ ] **Step 6: Write `tests/test_thread_safety.py`**

```python
# tests/test_thread_safety.py
import concurrent.futures, hashlib
from pylitehtml import Renderer, OutputFormat

HTMLS = [
    f"<html><body style='background:#{i*7%256:02x}{i*13%256:02x}{i*17%256:02x}'>"
    f"<h1>Item {i}</h1><p>Para {i}</p></body></html>"
    for i in range(50)
]

def test_concurrent_no_crash():
    r = Renderer(width=400)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(r.render, HTMLS))
    assert len(results) == 50
    assert all(b[:8] == b'\x89PNG\r\n\x1a\n' for b in results)

def test_concurrent_deterministic():
    r = Renderer(width=400)
    html = HTMLS[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: r.render(html), range(16)))
    digests = {hashlib.md5(x).hexdigest() for x in results}
    assert len(digests) == 1, f"Non-deterministic: {len(digests)} unique outputs"
```

- [ ] **Step 7: Confirm tests FAIL before implementation (expected)**

```bash
pytest tests/ -v 2>&1 | head -20
```

Expected: `ImportError` or `AttributeError` — C++ not yet implemented. This is RED. ✓

- [ ] **Step 8: Commit**

```bash
git add tests/
git commit -m "test: add all test files (RED — implementation not yet done)"
```

---

## Chunk 3: C++ Core Components

### Task 7: Vendor cpp-httplib (required before ImageCache)

**Files:**
- Create: `src/cpp/vendor/httplib.h`

- [ ] **Step 1: Download cpp-httplib**

```bash
curl -L "https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.18.3/httplib.h" \
  -o src/cpp/vendor/httplib.h
head -3 src/cpp/vendor/httplib.h
```

Expected: `// httplib.h` header comment.

- [ ] **Step 2: Commit**

```bash
git add src/cpp/vendor/httplib.h
git commit -m "chore: vendor cpp-httplib v0.18.3"
```

---

### Task 8: Encode helpers

**Files:**
- Modify: `src/cpp/encode.h`
- Modify: `src/cpp/encode.cpp`

- [ ] **Step 1: Write `encode.h`**

```cpp
// src/cpp/encode.h
#pragma once
#include <cairo.h>
#include <vector>
#include <cstdint>

namespace encode {
std::vector<uint8_t> to_png (cairo_surface_t* surface);
std::vector<uint8_t> to_jpeg(cairo_surface_t* surface, int quality);
std::vector<uint8_t> to_rgba(cairo_surface_t* surface);
} // namespace encode
```

- [ ] **Step 2: Write `encode.cpp`**

```cpp
// src/cpp/encode.cpp
#include "encode.h"
#include <jpeglib.h>
#include <csetjmp>
#include <stdexcept>
#include <string>

namespace encode {

// ── PNG ───────────────────────────────────────────────────────────────────────
static cairo_status_t png_write_cb(void* closure, const unsigned char* data, unsigned int len) {
    auto* buf = static_cast<std::vector<uint8_t>*>(closure);
    buf->insert(buf->end(), data, data + len);
    return CAIRO_STATUS_SUCCESS;
}

std::vector<uint8_t> to_png(cairo_surface_t* surface) {
    std::vector<uint8_t> buf;
    auto st = cairo_surface_write_to_png_stream(surface, png_write_cb, &buf);
    if (st != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error(std::string("PNG encode: ") + cairo_status_to_string(st));
    return buf;
}

// ── JPEG (with safe setjmp error handler to avoid calling exit()) ─────────────
struct SafeJpegError {
    jpeg_error_mgr pub;   // must be first
    jmp_buf        jmpbuf;
};

static void jpeg_error_exit(j_common_ptr cinfo) {
    auto* err = reinterpret_cast<SafeJpegError*>(cinfo->err);
    char msg[JMSG_LENGTH_MAX];
    (*cinfo->err->format_message)(cinfo, msg);
    longjmp(err->jmpbuf, 1);  // jump back to setjmp site with error message
}

std::vector<uint8_t> to_jpeg(cairo_surface_t* surface, int quality) {
    int w = cairo_image_surface_get_width(surface);
    int h = cairo_image_surface_get_height(surface);
    int stride = cairo_image_surface_get_stride(surface);
    const uint8_t* src = cairo_image_surface_get_data(surface);

    // Build RGB buffer (flatten alpha on white background)
    std::vector<uint8_t> rgb(w * h * 3);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + y * stride;
        uint8_t* out = rgb.data() + y * w * 3;
        for (int x = 0; x < w; ++x) {
            // Cairo ARGB32 LE: [B, G, R, A]
            float a = row[x*4+3] / 255.0f;
            out[x*3+0] = static_cast<uint8_t>(row[x*4+2] * a + 255.0f * (1.0f - a)); // R
            out[x*3+1] = static_cast<uint8_t>(row[x*4+1] * a + 255.0f * (1.0f - a)); // G
            out[x*3+2] = static_cast<uint8_t>(row[x*4+0] * a + 255.0f * (1.0f - a)); // B
        }
    }

    jpeg_compress_struct cinfo{};
    SafeJpegError jerr{};
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = jpeg_error_exit;  // override to avoid exit()

    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_compress(&cinfo);
        throw std::runtime_error("JPEG encode error");
    }

    jpeg_create_compress(&cinfo);
    uint8_t* mem = nullptr;
    unsigned long mem_size = 0;
    jpeg_mem_dest(&cinfo, &mem, &mem_size);

    cinfo.image_width = w;
    cinfo.image_height = h;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    while (cinfo.next_scanline < cinfo.image_height) {
        JSAMPROW row = rgb.data() + cinfo.next_scanline * w * 3;
        jpeg_write_scanlines(&cinfo, &row, 1);
    }
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);

    std::vector<uint8_t> result(mem, mem + mem_size);
    free(mem);
    return result;
}

// ── RAW RGBA ─────────────────────────────────────────────────────────────────
// Cairo ARGB32 LE: [B,G,R,A] per pixel → swizzle to true [R,G,B,A]
std::vector<uint8_t> to_rgba(cairo_surface_t* surface) {
    int w = cairo_image_surface_get_width(surface);
    int h = cairo_image_surface_get_height(surface);
    int stride = cairo_image_surface_get_stride(surface);
    const uint8_t* src = cairo_image_surface_get_data(surface);

    std::vector<uint8_t> rgba(w * h * 4);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + y * stride;
        uint8_t* out = rgba.data() + y * w * 4;
        for (int x = 0; x < w; ++x) {
            out[x*4+0] = row[x*4+2]; // R
            out[x*4+1] = row[x*4+1]; // G
            out[x*4+2] = row[x*4+0]; // B
            out[x*4+3] = row[x*4+3]; // A
        }
    }
    return rgba;
}

} // namespace encode
```

- [ ] **Step 3: Commit**

```bash
git add src/cpp/encode.h src/cpp/encode.cpp
git commit -m "feat: PNG/JPEG/RGBA encode helpers with safe libjpeg error handling"
```

---

### Task 9: ImageCache

**Files:**
- Modify: `src/cpp/image_cache.h`
- Modify: `src/cpp/image_cache.cpp`

- [ ] **Step 1: Write `image_cache.h`**

```cpp
// src/cpp/image_cache.h
#pragma once
#include <cairo.h>
#include <list>
#include <memory>
#include <shared_mutex>
#include <string>
#include <unordered_map>
#include <cstdint>

// Thread-safe image cache with FIFO eviction (bounded by byte count).
// Holds decoded cairo_surface_t* ready to draw.
// On cache hit: returns existing surface (shared lock, no promotion needed).
// On cache miss: loads image, then writes under exclusive lock.
class ImageCache {
public:
    struct Config {
        size_t max_bytes       = 64 * 1024 * 1024;
        int    timeout_ms      = 5000;
        size_t max_image_bytes = 10 * 1024 * 1024;
        bool   allow_http      = true;
    };

    explicit ImageCache(Config cfg);
    ~ImageCache();

    // Returns non-owning pointer valid for lifetime of this cache, or nullptr.
    cairo_surface_t* get(const std::string& url, const std::string& base_url);

private:
    struct Entry {
        cairo_surface_t* surface;
        size_t bytes;
    };

    std::string resolve(const std::string& url, const std::string& base_url) const;
    cairo_surface_t* load(const std::string& resolved);
    cairo_surface_t* load_file(const std::string& path);
    cairo_surface_t* load_jpeg_file(const std::string& path);
    cairo_surface_t* load_webp_file(const std::string& path);
    cairo_surface_t* load_http(const std::string& url);
    void evict_to_fit(size_t needed);  // call under exclusive lock

    Config cfg_;
    mutable std::shared_mutex mu_;
    // Insertion-order eviction (FIFO): front=oldest, back=newest
    std::list<std::string> insertion_order_;
    std::unordered_map<std::string, Entry> map_;
    size_t used_bytes_ = 0;
};
```

- [ ] **Step 2: Write `image_cache.cpp`**

```cpp
// src/cpp/image_cache.cpp
#include "image_cache.h"
#include <cairo.h>
#include <webp/decode.h>
#include <jpeglib.h>
#include <csetjmp>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <random>
#include <chrono>

#define CPPHTTPLIB_OPENSSL_SUPPORT 0
#include "vendor/httplib.h"

namespace fs = std::filesystem;

ImageCache::ImageCache(Config cfg) : cfg_(std::move(cfg)) {}

ImageCache::~ImageCache() {
    for (auto& [key, entry] : map_) {
        if (entry.surface) cairo_surface_destroy(entry.surface);
    }
}

cairo_surface_t* ImageCache::get(const std::string& url, const std::string& base_url) {
    std::string key = resolve(url, base_url);
    if (key.empty()) return nullptr;

    // Fast path: shared lock (read-only check)
    {
        std::shared_lock lk(mu_);
        auto it = map_.find(key);
        if (it != map_.end()) return it->second.surface;
    }

    // Slow path: load then exclusive lock
    cairo_surface_t* surface = load(key);
    if (!surface) return nullptr;

    size_t img_bytes = static_cast<size_t>(
        cairo_image_surface_get_stride(surface)) *
        cairo_image_surface_get_height(surface);

    std::unique_lock lk(mu_);
    // Double-check (another thread may have inserted while we loaded)
    auto it = map_.find(key);
    if (it != map_.end()) {
        cairo_surface_destroy(surface);
        return it->second.surface;
    }

    evict_to_fit(img_bytes);
    insertion_order_.push_back(key);
    map_[key] = {surface, img_bytes};
    used_bytes_ += img_bytes;
    return surface;
}

void ImageCache::evict_to_fit(size_t needed) {
    while (!insertion_order_.empty() && used_bytes_ + needed > cfg_.max_bytes) {
        const std::string& victim = insertion_order_.front();
        auto it = map_.find(victim);
        if (it != map_.end()) {
            if (it->second.surface) cairo_surface_destroy(it->second.surface);
            used_bytes_ -= it->second.bytes;
            map_.erase(it);
        }
        insertion_order_.pop_front();
    }
}

std::string ImageCache::resolve(const std::string& url, const std::string& base_url) const {
    if (url.empty()) return {};
    if (url.find("://") != std::string::npos) return url;
    if (url.starts_with('/')) return "file://" + url;
    if (base_url.starts_with("file://")) {
        fs::path base = fs::path(base_url.substr(7)).parent_path();
        return "file://" + (base / url).string();
    }
    if (base_url.starts_with("http://") || base_url.starts_with("https://")) {
        auto slash = base_url.rfind('/');
        return base_url.substr(0, slash + 1) + url;
    }
    return {};
}

cairo_surface_t* ImageCache::load(const std::string& resolved) {
    if (resolved.starts_with("file://")) return load_file(resolved.substr(7));
    if (cfg_.allow_http &&
        (resolved.starts_with("http://") || resolved.starts_with("https://")))
        return load_http(resolved);
    return nullptr;
}

cairo_surface_t* ImageCache::load_file(const std::string& path) {
    // Try PNG (Cairo built-in)
    cairo_surface_t* s = cairo_image_surface_create_from_png(path.c_str());
    if (cairo_surface_status(s) == CAIRO_STATUS_SUCCESS) return s;
    cairo_surface_destroy(s);

    // Try JPEG
    s = load_jpeg_file(path);
    if (s) return s;

    // Try WebP
    return load_webp_file(path);
}

cairo_surface_t* ImageCache::load_jpeg_file(const std::string& path) {
    struct SafeErr { jpeg_error_mgr pub; jmp_buf jmpbuf; };
    static auto err_exit = [](j_common_ptr c) {
        longjmp(reinterpret_cast<SafeErr*>(c->err)->jmpbuf, 1);
    };

    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return nullptr;

    jpeg_decompress_struct cinfo{};
    SafeErr jerr{};
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = err_exit;

    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_decompress(&cinfo);
        fclose(f);
        return nullptr;
    }

    jpeg_create_decompress(&cinfo);
    jpeg_stdio_src(&cinfo, f);
    jpeg_read_header(&cinfo, TRUE);
    cinfo.out_color_space = JCS_RGB;
    jpeg_start_decompress(&cinfo);

    int w = cinfo.output_width, h = cinfo.output_height;
    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_surface_flush(surf);
    uint8_t* dst = cairo_image_surface_get_data(surf);
    int stride = cairo_image_surface_get_stride(surf);

    std::vector<uint8_t> row_buf(w * 3);
    while (cinfo.output_scanline < (JDIMENSION)h) {
        JSAMPROW p = row_buf.data();
        jpeg_read_scanlines(&cinfo, &p, 1);
        int y = cinfo.output_scanline - 1;
        uint8_t* out = dst + y * stride;
        for (int x = 0; x < w; ++x) {
            out[x*4+0] = row_buf[x*3+2]; // B
            out[x*4+1] = row_buf[x*3+1]; // G
            out[x*4+2] = row_buf[x*3+0]; // R
            out[x*4+3] = 255;             // A (JPEG has no alpha)
        }
    }
    cairo_surface_mark_dirty(surf);
    jpeg_finish_decompress(&cinfo);
    jpeg_destroy_decompress(&cinfo);
    fclose(f);
    return surf;
}

cairo_surface_t* ImageCache::load_webp_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return nullptr;
    std::string data((std::istreambuf_iterator<char>(f)), {});
    if (data.size() > cfg_.max_image_bytes) return nullptr;

    int w = 0, h = 0;
    uint8_t* rgba = WebPDecodeRGBA(
        reinterpret_cast<const uint8_t*>(data.data()), data.size(), &w, &h);
    if (!rgba) return nullptr;

    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_surface_flush(surf);
    uint8_t* dst = cairo_image_surface_get_data(surf);
    int stride = cairo_image_surface_get_stride(surf);

    for (int y = 0; y < h; ++y) {
        const uint8_t* src = rgba + y * w * 4;
        uint8_t* out = dst + y * stride;
        for (int x = 0; x < w; ++x) {
            uint8_t r = src[x*4+0], g = src[x*4+1],
                    b = src[x*4+2], a = src[x*4+3];
            // Premultiply alpha for CAIRO_FORMAT_ARGB32
            out[x*4+0] = static_cast<uint8_t>((b * a + 127) / 255); // B_pm
            out[x*4+1] = static_cast<uint8_t>((g * a + 127) / 255); // G_pm
            out[x*4+2] = static_cast<uint8_t>((r * a + 127) / 255); // R_pm
            out[x*4+3] = a;
        }
    }
    cairo_surface_mark_dirty(surf);
    WebPFree(rgba);
    return surf;
}

cairo_surface_t* ImageCache::load_http(const std::string& url) {
    bool https = url.starts_with("https://");
    std::string rest = url.substr(https ? 8 : 7);
    auto slash = rest.find('/');
    std::string host = rest.substr(0, slash);
    std::string path = slash != std::string::npos ? rest.substr(slash) : "/";

    httplib::Client cli((https ? "https://" : "http://") + host);
    int sec = cfg_.timeout_ms / 1000;
    int us  = (cfg_.timeout_ms % 1000) * 1000;
    cli.set_connection_timeout(sec, us);
    cli.set_read_timeout(sec, us);

    auto res = cli.Get(path);
    if (!res || res->status != 200) return nullptr;
    if (res->body.size() > cfg_.max_image_bytes) return nullptr;

    // Write to a unique temp file (per-call UUID to avoid concurrent races)
    auto uid = std::chrono::steady_clock::now().time_since_epoch().count();
    std::mt19937_64 rng(uid ^ reinterpret_cast<uintptr_t>(&url));
    std::string tmp = (fs::temp_directory_path() /
        ("pylitehtml_" + std::to_string(rng()) + ".tmp")).string();
    {
        std::ofstream out(tmp, std::ios::binary);
        out.write(res->body.data(), res->body.size());
    }
    cairo_surface_t* surf = load_file(tmp);
    fs::remove(tmp);
    return surf;
}
```

- [ ] **Step 3: Build check**

```bash
pip install -e . --no-build-isolation -v 2>&1 | grep -E "^.*error:"
```

Expected: no `error:` lines.

- [ ] **Step 4: Commit**

```bash
git add src/cpp/image_cache.h src/cpp/image_cache.cpp
git commit -m "feat: thread-safe ImageCache (FIFO eviction, PNG/JPEG/WebP/HTTP)"
```

---

### Task 10: FontManager

**Files:**
- Modify: `src/cpp/font_manager.h`
- Modify: `src/cpp/font_manager.cpp`

- [ ] **Step 1: Write `font_manager.h`**

```cpp
// src/cpp/font_manager.h
#pragma once
#include <fontconfig/fontconfig.h>
#include <pango/pango.h>
#include <string>
#include <vector>

class FontManager {
public:
    struct Config {
        std::string fonts_dir;
        std::string default_font      = "Noto Sans";
        int         default_font_size = 16;
        std::vector<std::string> extra_fonts;
    };

    explicit FontManager(Config cfg);
    ~FontManager();

    const std::string& default_font() const { return cfg_.default_font; }
    int default_font_size_px() const { return cfg_.default_font_size; }
    PangoFontMap* font_map() const { return font_map_; }

private:
    Config cfg_;
    FcConfig* fc_config_ = nullptr;
    PangoFontMap* font_map_ = nullptr;
};
```

- [ ] **Step 2: Write `font_manager.cpp`**

```cpp
// src/cpp/font_manager.cpp
#include "font_manager.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <stdexcept>

namespace fs = std::filesystem;

FontManager::FontManager(Config cfg) : cfg_(std::move(cfg)) {
    // ── Step 1: create a fresh fontconfig config ──────────────────────────────
    fc_config_ = FcConfigCreate();
    if (!fc_config_) throw std::runtime_error("FcConfigCreate failed");

    // ── Step 2: load system fonts into this config ────────────────────────────
    // FcConfigSetSysRoot + FcInitLoadConfigAndFonts operate on the default config.
    // Instead, use FcConfigBuildFonts after adding system dirs manually is complex.
    // Simplest cross-platform approach: parse the system default config file too.
    {
        const FcChar8* sys_conf = FcConfigFilename(nullptr);  // system fonts.conf path
        if (sys_conf) FcConfigParseAndLoad(fc_config_, sys_conf, FcFalse);
    }

    // ── Step 3: load bundled fonts.conf (Windows runtime path setup) ──────────
    fs::path conf = fs::path(cfg_.fonts_dir) / "fonts.conf";
    if (fs::exists(conf)) {
        FcConfigParseAndLoad(fc_config_,
            reinterpret_cast<const FcChar8*>(conf.string().c_str()), FcFalse);
    }

    // ── Step 4: add bundled fonts directory ───────────────────────────────────
    FcConfigAppFontAddDir(fc_config_,
        reinterpret_cast<const FcChar8*>(cfg_.fonts_dir.c_str()));

    // ── Step 5: add user-supplied extra fonts ─────────────────────────────────
    for (const auto& path : cfg_.extra_fonts) {
        FcConfigAppFontAddFile(fc_config_,
            reinterpret_cast<const FcChar8*>(path.c_str()));
    }

    // ── Step 6: build font index ──────────────────────────────────────────────
    FcConfigBuildFonts(fc_config_);

    // ── Step 7: activate config (LAST — after all fonts are registered) ───────
    FcConfigSetCurrent(fc_config_);

    // ── Step 8: init Pango using the now-active fontconfig ────────────────────
    font_map_ = pango_cairo_font_map_new();
    if (!font_map_) throw std::runtime_error("pango_cairo_font_map_new failed");
}

FontManager::~FontManager() {
    if (font_map_) g_object_unref(font_map_);
    // Note: do NOT call FcConfigDestroy on the current config while Pango is alive.
    // Pango holds a reference; let it be destroyed when Pango is cleaned up.
}
```

- [ ] **Step 3: Build check**

```bash
pip install -e . --no-build-isolation -v 2>&1 | grep -E "^.*error:"
```

- [ ] **Step 4: Commit**

```bash
git add src/cpp/font_manager.h src/cpp/font_manager.cpp
git commit -m "feat: FontManager with correct fontconfig init order (system + bundled fonts)"
```

---

### Task 11: PyContainer

**Files:**
- Modify: `src/cpp/py_container.h`
- Modify: `src/cpp/py_container.cpp`

`PyContainer` inherits from `container_cairo` (from litehtml's reference containers). This gives us `draw_borders`, `draw_solid_fill`, `draw_*_gradient`, `draw_list_marker` for free — implemented with Cairo and no GDK dependency. We override only what's missing: font management (Pango), images (ImageCache), CSS loading, and metadata.

- [ ] **Step 1: Write `py_container.h`**

```cpp
// src/cpp/py_container.h
#pragma once
#include "container_cairo.h"       // from third_party/litehtml/containers/cairo/
#include "font_manager.h"
#include "image_cache.h"
#include <pango/pangocairo.h>
#include <string>
#include <unordered_map>

// FontHandle stores PangoFontDescription plus text decoration info.
// This mirrors the approach of container_cairo_pango from the reference.
struct FontHandle {
    PangoFontDescription* desc       = nullptr;
    bool underline                   = false;
    bool strikethrough               = false;
    bool overline                    = false;
    litehtml::web_color decoration_color{0, 0, 0, 255};
    bool has_decoration_color        = false;

    ~FontHandle() { if (desc) pango_font_description_free(desc); }
    FontHandle(const FontHandle&) = delete;
    FontHandle& operator=(const FontHandle&) = delete;
    FontHandle(FontHandle&&) = default;
};

// PyContainer inherits container_cairo for all Cairo drawing primitives.
// It adds Pango-based text rendering and ImageCache-based image loading.
// MUST be stack-allocated inside render() — never stored in Renderer.
class PyContainer : public container_cairo {
public:
    PyContainer(FontManager& fm, ImageCache& ic, int width);
    ~PyContainer();

    // Render html into an internal cairo_surface_t; returns actual height.
    int render(const std::string& html, const std::string& base_url, int fixed_height);

    cairo_surface_t* surface() const { return surface_; }
    int rendered_height() const { return rendered_height_; }

    // ── Overrides for font management ────────────────────────────────────────
    litehtml::uint_ptr create_font(const litehtml::font_description& descr,
                                   const litehtml::document* doc,
                                   litehtml::font_metrics* fm) override;
    void delete_font(litehtml::uint_ptr hFont) override;
    litehtml::pixel_t text_width(const char* text, litehtml::uint_ptr hFont) override;
    void draw_text(litehtml::uint_ptr hdc, const char* text, litehtml::uint_ptr hFont,
                   litehtml::web_color color, const litehtml::position& pos) override;
    litehtml::pixel_t pt_to_px(float pt) const override;
    litehtml::pixel_t get_default_font_size() const override;
    const char* get_default_font_name() const override;

    // ── Overrides for image loading ──────────────────────────────────────────
    void load_image(const char* src, const char* baseurl, bool) override;
    void get_image_size(const char* src, const char* baseurl, litehtml::size& sz) override;
    void draw_image(litehtml::uint_ptr hdc, const litehtml::background_layer& layer,
                    const std::string& url, const std::string& base_url) override;

    // ── Overrides for metadata and CSS loading ───────────────────────────────
    void set_caption(const char*) override {}
    void set_base_url(const char* base_url) override;
    void link(const std::shared_ptr<litehtml::document>&,
              const litehtml::element::ptr&) override {}
    void on_anchor_click(const char*, const litehtml::element::ptr&) override {}
    void on_mouse_event(const litehtml::element::ptr&, litehtml::mouse_event) override {}
    void set_cursor(const char*) override {}
    void transform_text(litehtml::string& text, litehtml::text_transform tt) override;
    void import_css(litehtml::string& text, const litehtml::string& url,
                    litehtml::string& baseurl) override;
    void get_viewport(litehtml::position& vp) const override;
    litehtml::element::ptr create_element(const char*, const litehtml::string_map&,
                                          const std::shared_ptr<litehtml::document>&) override;
    void get_media_features(litehtml::media_features& mf) const override;
    void get_language(litehtml::string& lang, litehtml::string& culture) const override;

private:
    FontManager& fm_;
    ImageCache&  ic_;
    int          width_;
    int          rendered_height_ = 0;
    std::string  base_url_;

    cairo_surface_t* surface_ = nullptr;
    cairo_t*         cr_      = nullptr;

    // Font ID → FontHandle (owned)
    std::unordered_map<litehtml::uint_ptr, std::unique_ptr<FontHandle>> fonts_;
    litehtml::uint_ptr next_font_id_ = 1;

    void create_surface(int w, int h);
};
```

- [ ] **Step 2: Write `py_container.cpp`**

```cpp
// src/cpp/py_container.cpp
#include "py_container.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>

#define CPPHTTPLIB_OPENSSL_SUPPORT 0
#include "vendor/httplib.h"

namespace fs = std::filesystem;

PyContainer::PyContainer(FontManager& fm, ImageCache& ic, int width)
    : fm_(fm), ic_(ic), width_(width) {}

PyContainer::~PyContainer() {
    fonts_.clear();
    if (cr_)      cairo_destroy(cr_);
    if (surface_) cairo_surface_destroy(surface_);
}

void PyContainer::create_surface(int w, int h) {
    if (cr_)      { cairo_destroy(cr_); cr_ = nullptr; }
    if (surface_) { cairo_surface_destroy(surface_); surface_ = nullptr; }
    surface_ = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cr_ = cairo_create(surface_);
    // White background
    cairo_set_source_rgb(cr_, 1, 1, 1);
    cairo_paint(cr_);
}

int PyContainer::render(const std::string& html, const std::string& base_url, int fixed_height) {
    base_url_ = base_url;
    create_surface(width_, 1);  // temporary 1px surface for layout pass

    litehtml::context ctx;
    auto doc = litehtml::document::createFromString(html, this, &ctx);
    if (!doc) throw std::runtime_error("litehtml: failed to parse HTML");

    doc->render(width_);

    int h = (fixed_height > 0) ? fixed_height : doc->height();
    rendered_height_ = h;

    create_surface(width_, h);  // final surface with correct dimensions
    litehtml::position clip{0, 0, width_, h};
    doc->draw(reinterpret_cast<litehtml::uint_ptr>(cr_), 0, 0, &clip);
    cairo_surface_flush(surface_);
    return h;
}

// ── Fonts ─────────────────────────────────────────────────────────────────────
litehtml::uint_ptr PyContainer::create_font(const litehtml::font_description& descr,
                                             const litehtml::document*,
                                             litehtml::font_metrics* fm_out) {
    auto handle = std::make_unique<FontHandle>();
    handle->desc = pango_font_description_new();
    pango_font_description_set_family(handle->desc, descr.family.c_str());
    pango_font_description_set_absolute_size(handle->desc,
        static_cast<double>(descr.size) * PANGO_SCALE);
    pango_font_description_set_style(handle->desc,
        descr.italic ? PANGO_STYLE_ITALIC : PANGO_STYLE_NORMAL);
    pango_font_description_set_weight(handle->desc,
        static_cast<PangoWeight>(descr.weight));

    // Store text decoration info
    handle->underline       = descr.decoration.decoration & litehtml::font_decoration_underline;
    handle->strikethrough   = descr.decoration.decoration & litehtml::font_decoration_linethrough;
    handle->overline        = descr.decoration.decoration & litehtml::font_decoration_overline;

    // Measure font metrics
    if (fm_out) {
        PangoLayout* layout = pango_cairo_create_layout(cr_);
        pango_layout_set_font_description(layout, handle->desc);
        PangoFontMetrics* metrics = pango_context_get_metrics(
            pango_layout_get_context(layout), handle->desc, nullptr);
        fm_out->ascent  = PANGO_PIXELS(pango_font_metrics_get_ascent(metrics));
        fm_out->descent = PANGO_PIXELS(pango_font_metrics_get_descent(metrics));
        fm_out->height  = fm_out->ascent + fm_out->descent;
        fm_out->x_height = fm_out->ascent / 2;
        pango_font_metrics_unref(metrics);
        g_object_unref(layout);
    }

    litehtml::uint_ptr id = next_font_id_++;
    fonts_[id] = std::move(handle);
    return id;
}

void PyContainer::delete_font(litehtml::uint_ptr hFont) {
    fonts_.erase(hFont);
}

litehtml::pixel_t PyContainer::text_width(const char* text, litehtml::uint_ptr hFont) {
    auto it = fonts_.find(hFont);
    if (it == fonts_.end()) return 0;
    PangoLayout* layout = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(layout, it->second->desc);
    pango_layout_set_text(layout, text, -1);
    int w = 0, h = 0;
    pango_layout_get_pixel_size(layout, &w, &h);
    g_object_unref(layout);
    return static_cast<litehtml::pixel_t>(w);
}

void PyContainer::draw_text(litehtml::uint_ptr, const char* text, litehtml::uint_ptr hFont,
                             litehtml::web_color color, const litehtml::position& pos) {
    auto it = fonts_.find(hFont);
    if (it == fonts_.end()) return;
    const FontHandle& fh = *it->second;

    cairo_save(cr_);
    cairo_set_source_rgba(cr_, color.red/255.0, color.green/255.0,
                          color.blue/255.0, color.alpha/255.0);
    cairo_move_to(cr_, pos.x, pos.y);

    PangoLayout* layout = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(layout, fh.desc);
    pango_layout_set_text(layout, text, -1);
    pango_cairo_show_layout(cr_, layout);

    // Draw text decorations
    if (fh.underline || fh.strikethrough || fh.overline) {
        int w = 0, h = 0;
        pango_layout_get_pixel_size(layout, &w, &h);
        cairo_set_line_width(cr_, 1.0);
        if (fh.underline) {
            cairo_move_to(cr_, pos.x, pos.y + h);
            cairo_line_to(cr_, pos.x + w, pos.y + h);
            cairo_stroke(cr_);
        }
        if (fh.strikethrough) {
            cairo_move_to(cr_, pos.x, pos.y + h / 2.0);
            cairo_line_to(cr_, pos.x + w, pos.y + h / 2.0);
            cairo_stroke(cr_);
        }
        if (fh.overline) {
            cairo_move_to(cr_, pos.x, pos.y);
            cairo_line_to(cr_, pos.x + w, pos.y);
            cairo_stroke(cr_);
        }
    }

    g_object_unref(layout);
    cairo_restore(cr_);
}

litehtml::pixel_t PyContainer::pt_to_px(float pt) const {
    return static_cast<litehtml::pixel_t>(pt * 96.0f / 72.0f);
}
litehtml::pixel_t PyContainer::get_default_font_size() const {
    return fm_.default_font_size_px();
}
const char* PyContainer::get_default_font_name() const {
    return fm_.default_font().c_str();
}

// ── Images ────────────────────────────────────────────────────────────────────
void PyContainer::load_image(const char* src, const char* baseurl, bool) {
    ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
}
void PyContainer::get_image_size(const char* src, const char* baseurl, litehtml::size& sz) {
    cairo_surface_t* s = ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
    if (s) {
        sz.width  = cairo_image_surface_get_width(s);
        sz.height = cairo_image_surface_get_height(s);
    }
}
void PyContainer::draw_image(litehtml::uint_ptr, const litehtml::background_layer& layer,
                              const std::string& url, const std::string& base_url) {
    cairo_surface_t* img = ic_.get(url, base_url.empty() ? base_url_ : base_url);
    if (!img) return;
    cairo_save(cr_);
    cairo_set_source_surface(cr_, img, layer.origin_box.x, layer.origin_box.y);
    cairo_rectangle(cr_, layer.border_box.x, layer.border_box.y,
                    layer.border_box.width, layer.border_box.height);
    cairo_fill(cr_);
    cairo_restore(cr_);
}

// ── CSS / Base URL ────────────────────────────────────────────────────────────
void PyContainer::set_base_url(const char* u) { if (u) base_url_ = u; }

void PyContainer::import_css(litehtml::string& text, const litehtml::string& url,
                               litehtml::string& baseurl) {
    if (baseurl.empty() && base_url_.empty()) return;
    const std::string& effective_base = baseurl.empty() ? base_url_ : std::string(baseurl);

    if (effective_base.starts_with("file://")) {
        fs::path base_path = fs::path(effective_base.substr(7)).parent_path();
        fs::path css_path = base_path / url;
        std::ifstream f(css_path);
        if (f) { std::ostringstream ss; ss << f.rdbuf(); text = ss.str(); }
        return;
    }
    // HTTP CSS: for v1, skip (CSS from HTTP base URLs not yet supported)
    text = "";
}

// ── Viewport / Media ──────────────────────────────────────────────────────────
void PyContainer::get_viewport(litehtml::position& vp) const {
    vp = {0, 0, width_, rendered_height_ > 0 ? rendered_height_ : 600};
}
void PyContainer::get_media_features(litehtml::media_features& mf) const {
    mf.type       = litehtml::media_type_screen;
    mf.width      = width_;
    mf.height     = rendered_height_ > 0 ? rendered_height_ : 600;
    mf.color      = 8;
    mf.resolution = 96;
}
void PyContainer::get_language(litehtml::string& lang, litehtml::string& culture) const {
    lang = "en"; culture = "en-US";
}

// ── Text transform ────────────────────────────────────────────────────────────
void PyContainer::transform_text(litehtml::string& text, litehtml::text_transform tt) {
    if (tt == litehtml::text_transform_uppercase)
        std::transform(text.begin(), text.end(), text.begin(), ::toupper);
    else if (tt == litehtml::text_transform_lowercase)
        std::transform(text.begin(), text.end(), text.begin(), ::tolower);
}

litehtml::element::ptr PyContainer::create_element(const char*, const litehtml::string_map&,
                                                    const std::shared_ptr<litehtml::document>&) {
    return nullptr;
}
```

- [ ] **Step 3: Build check**

```bash
pip install -e . --no-build-isolation -v 2>&1 | grep -E "^.*error:"
```

- [ ] **Step 4: Commit**

```bash
git add src/cpp/py_container.h src/cpp/py_container.cpp
git commit -m "feat: PyContainer inheriting container_cairo, Pango text, FontHandle with decorations"
```

---

## Chunk 4: Python Binding + GREEN Phase

### Task 12: Full pybind11 binding

**Files:**
- Modify: `src/cpp/binding.cpp`

- [ ] **Step 1: Write full `binding.cpp`**

```cpp
// src/cpp/binding.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <filesystem>
#include "font_manager.h"
#include "image_cache.h"
#include "py_container.h"
#include "encode.h"

namespace py = pybind11;
namespace fs = std::filesystem;

static fs::path fonts_dir_from_module() {
    // _core.so lives at pylitehtml/_core.so; fonts/ is at pylitehtml/fonts/
    py::object this_mod = py::module_::import("pylitehtml._core");
    std::string so_path = py::cast<std::string>(
        py::getattr(this_mod, "__file__", py::str("")));
    return fs::path(so_path).parent_path() / "fonts";
}

enum class OutputFormat { PNG = 0, JPEG = 1, RAW = 2 };

struct RawResult {
    py::bytes data;
    int width;
    int height;
};

struct RenderError    : std::runtime_error { using runtime_error::runtime_error; };
struct ImageFetchError: std::runtime_error { using runtime_error::runtime_error; };

class Renderer {
public:
    Renderer(int width, int dpi, std::string default_font, int default_font_size,
             std::vector<std::string> extra_fonts,
             size_t image_cache_max_bytes, int image_timeout_ms,
             size_t image_max_bytes, bool allow_http_images)
        : width_(width)
        , fm_(FontManager::Config{
              fonts_dir_from_module().string(),
              std::move(default_font),
              default_font_size,
              std::move(extra_fonts)})
        , ic_(ImageCache::Config{
              image_cache_max_bytes,
              image_timeout_ms,
              image_max_bytes,
              allow_http_images})
    {}

    py::object render(const std::string& html, const std::string& base_url,
                      int height, OutputFormat fmt, int quality) {
        // Stack-local — thread safe. Each call is fully independent.
        PyContainer container(fm_, ic_, width_);
        try {
            container.render(html, base_url, height);
        } catch (const std::exception& e) {
            throw RenderError(e.what());
        }
        cairo_surface_t* surf = container.surface();
        switch (fmt) {
            case OutputFormat::PNG: {
                auto buf = encode::to_png(surf);
                return py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
            }
            case OutputFormat::JPEG: {
                auto buf = encode::to_jpeg(surf, quality);
                return py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
            }
            case OutputFormat::RAW: {
                auto buf = encode::to_rgba(surf);
                RawResult r;
                r.data   = py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
                r.width  = cairo_image_surface_get_width(surf);
                r.height = cairo_image_surface_get_height(surf);
                return py::cast(std::move(r));
            }
        }
        throw RenderError("Unknown output format");
    }

private:
    int         width_;
    FontManager fm_;
    ImageCache  ic_;
};

PYBIND11_MODULE(_core, m) {
    m.doc() = "pylitehtml: HTML+CSS to image renderer";

    py::register_exception<RenderError>(m, "RenderError");
    py::register_exception<ImageFetchError>(m, "ImageFetchError");

    py::enum_<OutputFormat>(m, "OutputFormat")
        .value("PNG",  OutputFormat::PNG)
        .value("JPEG", OutputFormat::JPEG)
        .value("RAW",  OutputFormat::RAW)
        .export_values();

    py::class_<RawResult>(m, "RawResult")
        .def_readonly("data",   &RawResult::data)
        .def_readonly("width",  &RawResult::width)
        .def_readonly("height", &RawResult::height);

    py::class_<Renderer>(m, "Renderer")
        .def(py::init<int,int,std::string,int,std::vector<std::string>,
                      size_t,int,size_t,bool>(),
             py::arg("width"),
             py::arg("dpi")                   = 96,
             py::arg("default_font")          = "Noto Sans",
             py::arg("default_font_size")     = 16,
             py::arg("extra_fonts")           = std::vector<std::string>{},
             py::arg("image_cache_max_bytes") = 64*1024*1024,
             py::arg("image_timeout_ms")      = 5000,
             py::arg("image_max_bytes")       = 10*1024*1024,
             py::arg("allow_http_images")     = true)
        .def("render", &Renderer::render,
             py::arg("html"),
             py::arg("base_url") = "",
             py::arg("height")   = 0,
             py::arg("fmt")      = OutputFormat::PNG,
             py::arg("quality")  = 85,
             py::call_guard<py::gil_scoped_release>());

    m.def("render",
        [](const std::string& html, int width, const std::string& base_url,
           int height, OutputFormat fmt, int quality) -> py::object {
            Renderer r(width,96,"Noto Sans",16,{},64*1024*1024,5000,10*1024*1024,true);
            return r.render(html, base_url, height, fmt, quality);
        },
        py::arg("html"), py::arg("width"),
        py::arg("base_url") = "", py::arg("height") = 0,
        py::arg("fmt")      = OutputFormat::PNG,
        py::arg("quality")  = 85);
}
```

- [ ] **Step 2: Build**

```bash
pip install -e . --no-build-isolation -v 2>&1 | grep -E "^.*error:"
```

- [ ] **Step 3: Smoke test**

```bash
python - <<'EOF'
import pylitehtml
png = pylitehtml.render("<h1 style='color:red'>Hello</h1>", width=400)
assert png[:8] == b'\x89PNG\r\n\x1a\n'
print(f"OK — {len(png)} bytes")
EOF
```

Expected: `OK — XXXXX bytes`

- [ ] **Step 4: Run the full test suite (GREEN phase)**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass. Fix any failures before proceeding.

- [ ] **Step 5: Commit**

```bash
git add src/cpp/binding.cpp
git commit -m "feat: full pybind11 binding — Renderer + render() — GREEN"
```

---

## Chunk 5: CI/CD

### Task 13: GitHub Actions — test + wheel build

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/wheels.yml`

- [ ] **Step 1: Write `.github/workflows/test.yml`**

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive }
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }

      - name: System deps (Linux)
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y libcairo2-dev libpango1.0-dev libfontconfig1-dev \
            libwebp-dev libjpeg-turbo8-dev cmake ninja-build

      - name: System deps (macOS)
        if: runner.os == 'macOS'
        run: brew install cairo pango fontconfig webp jpeg-turbo cmake ninja

      - name: Build and test
        run: |
          pip install scikit-build-core pybind11 pytest pillow
          pip install -e . --no-build-isolation
          pytest tests/ -v
```

- [ ] **Step 2: Write `.github/workflows/wheels.yml`**

```yaml
name: Build Wheels
on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build_wheels:
    name: Wheels ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]

    steps:
      - uses: actions/checkout@v4
        with: { submodules: recursive }

      - uses: lukka/run-vcpkg@v11
        if: runner.os != 'Linux'
        with: { vcpkgGitCommitId: "2024.11.16" }

      - name: vcpkg deps (Windows)
        if: runner.os == 'Windows'
        run: vcpkg install cairo pango fontconfig libwebp libjpeg-turbo --triplet x64-windows-static

      - name: vcpkg deps (macOS)
        if: runner.os == 'macOS'
        run: vcpkg install cairo pango fontconfig libwebp libjpeg-turbo --triplet arm64-osx

      - uses: pypa/cibuildwheel@v2.22
        env:
          CIBW_BUILD: "cp310-* cp311-* cp312-* cp313-*"
          CIBW_ARCHS_LINUX: "x86_64 aarch64"
          CIBW_ARCHS_MACOS: "x86_64 arm64"
          CIBW_ARCHS_WINDOWS: "AMD64"
          CIBW_MANYLINUX_X86_64_IMAGE: manylinux2014
          CIBW_BEFORE_ALL_LINUX: |
            yum install -y cairo-devel pango-devel fontconfig-devel \
              libwebp-devel libjpeg-turbo-devel
          CIBW_REPAIR_WHEEL_COMMAND_LINUX:   "auditwheel repair -w {dest_dir} {wheel}"
          CIBW_REPAIR_WHEEL_COMMAND_MACOS:   "delocate-wheel -w {dest_dir} {wheel}"
          CIBW_REPAIR_WHEEL_COMMAND_WINDOWS: "delvewheel repair -w {dest_dir} {wheel}"
          CIBW_TEST_REQUIRES: "pytest pillow"
          CIBW_TEST_COMMAND: "pytest {project}/tests/test_basic.py -v"

      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: ./wheelhouse/*.whl

  publish:
    needs: build_wheels
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    environment: pypi
    permissions: { id-token: write }
    steps:
      - uses: actions/download-artifact@v4
        with: { pattern: wheels-*, merge-multiple: true, path: dist/ }
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 3: Push and verify CI**

```bash
git add .github/
git commit -m "ci: test workflow + cibuildwheel wheel builder"
git push origin main
```

Check: `https://github.com/tyql688/pylitehtml/actions` — test workflow should go green.

---

### Task 14: README + first tag

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# pylitehtml

HTML+CSS → PNG/JPEG image renderer. Lightweight, no headless browser, thread-safe.

## Install

\```bash
pip install pylitehtml
\```

## Usage

\```python
import pylitehtml
from pylitehtml import Renderer, OutputFormat

# One-shot
png = pylitehtml.render("<h1>Hello</h1>", width=800)

# Reusable renderer (thread-safe, create once per process)
renderer = Renderer(width=1200)
png = renderer.render(html)
jpg = renderer.render(html, fmt=OutputFormat.JPEG, quality=85)
raw = renderer.render(html, fmt=OutputFormat.RAW)
# raw.data: RGBA bytes | raw.width, raw.height: int

# High concurrency
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    images = list(pool.map(renderer.render, html_list))
\```

## Built on

- [litehtml](https://github.com/litehtml/litehtml) — HTML/CSS layout
- Cairo + Pango — rendering + text
```

- [ ] **Step 2: Tag v0.1.0**

```bash
git add README.md
git commit -m "docs: README"
git tag v0.1.0
git push origin main --tags
```

Expected: `wheels.yml` triggers, builds 12 wheels across 3 OS × 4 Python versions.

---

## Done

Deliverables after this plan:
- `pip install pylitehtml` on Linux / macOS / Windows
- Thread-safe `Renderer` class + `render()` convenience function
- PNG / JPEG / raw RGBA output
- Bundled Noto Sans, Noto Sans SC, DejaVu Sans fonts
- Full test suite: basic, fonts, images, CSS, thread safety
- GitHub Actions CI on every push, wheel release on tag
