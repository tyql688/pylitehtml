# pylitehtml

![CI](https://github.com/tyql688/pylitehtml/actions/workflows/test.yml/badge.svg)

HTML+CSS → PNG/JPEG 图像渲染器。轻量级，无需无头浏览器，线程安全。

[English](README.md) | 中文

## 安装

```bash
pip install pylitehtml
```

## 快速开始

```python
import pylitehtml

# 一次性便捷函数
png_bytes = pylitehtml.render("<h1>你好，世界</h1>", width=800)
with open("output.png", "wb") as f:
    f.write(png_bytes)
```

## API 参考

### `pylitehtml.render(html, width, *, base_url="", height=0, fmt=OutputFormat.PNG, quality=85)`

一次性便捷函数，内部创建临时 `Renderer`，渲染完成后返回图像字节。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `html` | `str` | — | 要渲染的 HTML 源码 |
| `width` | `int` | — | 视口宽度（像素） |
| `base_url` | `str` | `""` | 解析相对资源的基础 URL |
| `height` | `int` | `0` | 固定高度（0 表示自动） |
| `fmt` | `OutputFormat` | `PNG` | 输出格式 |
| `quality` | `int` | `85` | JPEG 质量（1–100，PNG/RAW 忽略） |

返回 `bytes`（PNG 或 JPEG）或 `RawResult`（RAW）。

---

### `class Renderer(width=800, default_font="Noto Sans", default_font_size=16, extra_fonts=[], image_cache_max_bytes=67108864, image_timeout_ms=5000, image_max_bytes=10485760, allow_http_images=True)`

可复用渲染器。创建一次，多次调用 `.render()`，线程安全。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `width` | `int` | `800` | 视口宽度（像素） |
| `default_font` | `str` | `"Noto Sans"` | 备用字体族名称 |
| `default_font_size` | `int` | `16` | 默认字体大小（像素） |
| `extra_fonts` | `list[str]` | `[]` | 额外注册的字体文件路径 |
| `image_cache_max_bytes` | `int` | `67108864` | 图片缓存最大字节数（64 MB） |
| `image_timeout_ms` | `int` | `5000` | HTTP 图片获取超时（毫秒） |
| `image_max_bytes` | `int` | `10485760` | 单张图片最大字节数（10 MB） |
| `allow_http_images` | `bool` | `True` | 是否允许通过 HTTP/HTTPS 获取图片 |

#### `Renderer.render(html, *, base_url="", height=0, fmt=OutputFormat.PNG, quality=85)`

渲染 HTML 并返回图像数据。

返回 PNG/JPEG 时为 `bytes`，RAW 时为 `RawResult`。

---

### `class OutputFormat`

```python
OutputFormat.PNG   # PNG 编码字节
OutputFormat.JPEG  # JPEG 编码字节
OutputFormat.RAW   # 未压缩 RGBA 字节（见 RawResult）
```

---

### `class RawResult`

当 `fmt=OutputFormat.RAW` 时返回。

```python
result.data    # bytes — RGBA 像素数据，行优先排列
result.width   # int — 图像宽度（像素）
result.height  # int — 图像高度（像素）
```

---

### `class RenderError(Exception)`

渲染失败时抛出（如 HTML 结构错误、资源加载失败）。

---

### `class ImageFetchError(Exception)`

图片无法获取或解码时抛出。

---

## 使用示例

### 可复用渲染器

```python
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=1200)

# PNG（默认）
png = renderer.render("<p>你好</p>")

# JPEG
jpg = renderer.render("<p>你好</p>", fmt=OutputFormat.JPEG, quality=90)

# 原始 RGBA
raw = renderer.render("<p>你好</p>", fmt=OutputFormat.RAW)
print(raw.width, raw.height, len(raw.data))  # 例：1200 600 2880000
```

### 高并发渲染

```python
import concurrent.futures
from pylitehtml import Renderer

renderer = Renderer(width=800)  # 多线程共享同一实例

html_list = ["<h1>第 {} 页</h1>".format(i) for i in range(1000)]

with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    images = list(pool.map(renderer.render, html_list))
```

### 自定义字体

```python
from pylitehtml import Renderer

renderer = Renderer(
    width=800,
    default_font="我的自定义字体",
    extra_fonts=["/path/to/extra.ttf"],
)
```

### 转换为 PIL 图像

```python
from PIL import Image
import io
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=800)
raw = renderer.render("<h1>你好</h1>", fmt=OutputFormat.RAW)
img = Image.frombytes("RGBA", (raw.width, raw.height), raw.data)
img.save("output.png")
```

### 转换为 NumPy 数组

```python
import numpy as np
from pylitehtml import Renderer, OutputFormat

renderer = Renderer(width=800)
raw = renderer.render("<h1>你好</h1>", fmt=OutputFormat.RAW)
arr = np.frombuffer(raw.data, dtype=np.uint8).reshape(raw.height, raw.width, 4)
# arr shape: (height, width, 4) — 通道顺序为 BGRA（Cairo 原生格式）
```

## 输出格式

| 格式 | 返回类型 | 说明 |
|------|----------|------|
| `PNG` | `bytes` | 无损压缩，适合截图 |
| `JPEG` | `bytes` | 文件更小，`quality` 1–100 |
| `RAW` | `RawResult` | 未压缩 BGRA 像素（Cairo 原生通道顺序） |

## 支持版本

| Python | Linux | macOS | Windows |
|--------|-------|-------|---------|
| 3.10 | ✅ | ✅ | ✅ |
| 3.11 | ✅ | ✅ | ✅ |
| 3.12 | ✅ | ✅ | ✅ |
| 3.13 | ✅ | ✅ | ✅ |
| 3.14 | ✅ | ✅ | ✅ |

## 已知限制

- **不支持 JavaScript** — 仅静态 HTML+CSS
- **不发起网络请求** — 外部图片/样式表须内联或通过本地服务提供
- **不支持 SVG** — SVG 图像不会被渲染
- **CSS 子集** — 基于 [litehtml](https://github.com/litehtml/litehtml)；部分高级 CSS 特性（如 Grid、Flexbox）支持不完整

## 线程安全

`Renderer` 构造完成后线程安全，多线程可并发调用同一实例的 `.render()`。请勿并发构造多个 `Renderer` 实例。

## 从源码构建

**依赖项：** Cairo、Pango、FontConfig、libwebp、libjpeg-turbo、CMake、Ninja、pybind11

```bash
# Linux
sudo apt-get install libcairo2-dev libpango1.0-dev libfontconfig1-dev \
  libwebp-dev libjpeg-turbo8-dev cmake ninja-build

# macOS
brew install cairo pango fontconfig webp jpeg-turbo cmake ninja

# 构建
pip install scikit-build-core pybind11
pip install -e . --no-build-isolation
pytest tests/
```

## 基于

- [litehtml](https://github.com/litehtml/litehtml) — HTML/CSS 布局引擎
- [Cairo](https://www.cairographics.org/) — 2D 图形渲染
- [Pango](https://pango.gnome.org/) — 文本布局与渲染
- [FontConfig](https://www.freedesktop.org/wiki/Software/fontconfig/) — 字体发现
- [pybind11](https://github.com/pybind/pybind11) — Python/C++ 绑定

## 许可证

MIT
