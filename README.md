# pylitehtml

![CI](https://github.com/tyql688/pylitehtml/actions/workflows/test.yml/badge.svg)

HTML+CSS → PNG/JPEG 图像渲染器。轻量级，无需无头浏览器，线程安全。需要 Python ≥ 3.10。

## 安装

```bash
pip install pylitehtml
```

## 快速上手

```python
import pylitehtml

# 一次性渲染
png = pylitehtml.render("<h1>Hello</h1>", width=800)

# 复用渲染器（推荐，字体只加载一次）
r = pylitehtml.Renderer(width=800)
png = r.render("<h1>Hello</h1>")
jpg = r.render("<h1>Hello</h1>", fmt="jpeg", quality=90)

# 渲染本地 HTML 文件（自动解析相对路径的 CSS 和图片）
png = r.render_file("project/index.html")

# Jinja2 模板渲染（传入数据自动填充）
png = r.render_file("project/order.html", title="订单", items=[...])

# 异步渲染（不阻塞事件循环）
import asyncio
png = await asyncio.to_thread(r.render, "<h1>Hello</h1>")
```

---

## Renderer 参数

```python
Renderer(
    width,                    # 必填：画布宽度（像素）
    *,
    locale = "en-US",            # 语言区域，影响 CSS :lang() 选择器，如 "zh-CN"
    dpi = 96.0,                  # DPI，影响 pt 单位换算；HiDPI 用 144 或 192
    device_height = 600,         # 媒体查询用的逻辑屏幕高度（不影响实际输出高度）
    fonts = FontConfig(),        # 字体配置（见下方）
    images = ImageConfig(),      # 图片配置（见下方）
)
```

```python
FontConfig(
    default = "Noto Sans",       # 默认字体（系统需已安装）
    size = 16,                   # 默认字号（像素）
    extra = [],                  # 额外字体文件路径列表，如 ["/path/to/font.ttf"]
)

ImageConfig(
    cache_mb = 64.0,             # 图片缓存上限（MB）
    timeout_ms = 5000,           # HTTP 图片请求超时（毫秒）
    max_mb = 10.0,               # 单张图片最大体积（MB），超出则跳过
    allow_http = True,           # 是否允许通过 HTTP/HTTPS 加载图片和 CSS
)
```

### 哪些参数通常需要改？

| 场景                   | 改哪个参数                                      |
| ---------------------- | ----------------------------------------------- |
| 渲染中文 / 多语言内容  | `locale="zh-CN"`                                |
| 输出 HiDPI / Retina 图 | `dpi=192.0`                                     |
| 加载本地字体文件       | `fonts=FontConfig(extra=["/path/to/font.ttf"])` |
| 禁用网络图片和 CSS     | `images=ImageConfig(allow_http=False)`          |
| 渲染很多大图           | `images=ImageConfig(cache_mb=128)`              |

---

## render() 参数

```python
r.render(
    html,                        # 必填：HTML 字符串
    *,
    fmt = "png",                 # 输出格式："png" / "jpeg" / "raw"
    quality = 85,                # JPEG 质量 1-100（png/raw 忽略此参数）
    height = 0,                  # 固定输出高度（像素）；0 = 自动按内容高度
    shrink_to_fit = True,        # True = 内容比 width 窄时，自动收窄画布宽度；False = 固定 width 宽度
)
```

返回值：

- `fmt="png"` / `fmt="jpeg"` → `bytes`
- `fmt="raw"` → `RawResult`（含 `.data` `.width` `.height`，像素格式为 BGRA）

---

## render_file() — 渲染本地 HTML 文件

像写标准网页一样组织文件，pylitehtml 自动解析相对路径的 CSS 和图片：

```
project/
├── index.html          # <link rel="stylesheet" href="style.css">
├── style.css
└── images/
    └── logo.png        # <img src="images/logo.png">
```

```python
r = pylitehtml.Renderer(width=800)

# 渲染 HTML 文件，CSS 和图片从文件所在目录自动加载
png = r.render_file("project/index.html")

# 一次性渲染
png = pylitehtml.render_file("project/index.html", width=800)
```

### Jinja2 模板

传入关键字参数时，文件会作为 [Jinja2](https://jinja.palletsprojects.com/) 模板渲染：

```html
<!-- project/order.html -->
<link rel="stylesheet" href="style.css">
<h1>{{ title }}</h1>
<ul>
{% for item in items %}
    <li>{{ item.name }} - ¥{{ item.price }}</li>
{% endfor %}
</ul>
```

```python
png = r.render_file(
    "project/order.html",
    title="订单",
    items=[{"name": "苹果", "price": 5}, {"name": "香蕉", "price": 3}],
)
```

---

## 支持与不支持

| 功能                                         | 是否支持                  |
| -------------------------------------------- | ------------------------- |
| PNG / JPEG / RAW 输出                        | ✅                        |
| HTTP/HTTPS 图片（`<img src="https://...">`） | ✅ 默认开启               |
| `data:` URI 内嵌图片（PNG/JPEG/WebP/SVG）    | ✅                        |
| CSS `@import`（本地文件 / HTTP）             | ✅                        |
| 本地 HTML 文件渲染（自动解析相对路径）       | ✅ `render_file()`        |
| Jinja2 模板渲染                              | ✅ `render_file(k=v)`     |
| 多线程并发渲染                               | ✅                        |
| 异步渲染（asyncio.to_thread）                | ✅                        |
| JavaScript                                   | ❌ 静态渲染，不执行 JS    |
| CSS `@font-face`（HTTP 字体）                | ❌ 不支持，字体须预先安装 |
| CSS Grid                                     | ❌ litehtml 暂不支持      |
| Flexbox                                      | ⚠️ 部分支持               |

---

## 常用示例

### 渲染中文

```python
r = pylitehtml.Renderer(width=800, locale="zh-CN")
png = r.render("<p>你好，世界</p>")
```

### 异步（FastAPI / asyncio）

```python
import asyncio

r = pylitehtml.Renderer(width=800)
png = await asyncio.to_thread(r.render, "<h1>Hello</h1>")
```

### HiDPI 输出

```python
r = pylitehtml.Renderer(width=800, dpi=192.0)
png = r.render("<p style='font-size:12pt'>Hello</p>")
```

### 内嵌图片（离线渲染）

```python
import base64

with open("logo.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

png = pylitehtml.Renderer(width=400).render(
    f'<img src="data:image/png;base64,{b64}">'
)
```

### 加载本地字体

```python
r = pylitehtml.Renderer(
    width=800,
    fonts=pylitehtml.FontConfig(
        default="My Font",
        extra=["/path/to/myfont.ttf"],
    ),
)
```

### 获取原始像素（接入 PIL / NumPy）

```python
from PIL import Image
import numpy as np

r = pylitehtml.Renderer(width=800)
raw = r.render("<h1>Hello</h1>", fmt="raw")

# PIL
img = Image.frombytes("RGBA", (raw.width, raw.height), raw.data)

# NumPy，shape=(height, width, 4)，通道顺序 BGRA
arr = np.frombuffer(raw.data, dtype=np.uint8).reshape(raw.height, raw.width, 4)
```

### 高并发

```python
import concurrent.futures

r = pylitehtml.Renderer(width=800)  # 线程安全，多线程共享
pages = ["<h1>Page {}</h1>".format(i) for i in range(1000)]

with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    images = list(pool.map(r.render, pages))
```

---

## 从源码构建

**Ubuntu / Debian**

```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev libfontconfig1-dev \
  libwebp-dev libjpeg-turbo8-dev cmake ninja-build pkg-config
pip install -e ".[dev]" --no-build-isolation
```

**macOS**

```bash
brew install cairo pango fontconfig webp jpeg-turbo cmake ninja
CC=/usr/bin/clang CXX=/usr/bin/clang++ pip install -e ".[dev]" --no-build-isolation
```

**运行测试**

```bash
pytest tests/ -v
```

---

## 基于

[litehtml](https://github.com/litehtml/litehtml) · [Cairo](https://www.cairographics.org/) · [Pango](https://pango.gnome.org/) · [FontConfig](https://www.freedesktop.org/wiki/Software/fontconfig/) · [pybind11](https://github.com/pybind/pybind11)

MIT License
