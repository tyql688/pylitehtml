# pylitehtml

![CI](https://github.com/tyql688/pylitehtml/actions/workflows/test.yml/badge.svg)

HTML + CSS → PNG/JPEG 图像渲染器：**轻量、无需无头浏览器、线程安全**。

- **快** — 稳态单次渲染约 15 ms（比无头 Chromium 快约 1.4×），冷启动约 0.2 s
- **轻** — 不需要下载 ~190 MB 的 Chromium，官方 wheel 开箱即用（Linux / macOS / Windows）
- **中文友好** — 内置 Noto Sans + SC 字体，中英文混排共享基线（不会出现中文"飞起来"）
- **线程安全** — 渲染期间释放 GIL，可多线程并发，`asyncio` 友好
- **内置电池** — 零依赖 Markdown 转换器、Jinja2 模板、HTTPS 图片加载

需要 Python ≥ 3.10。不执行 JavaScript（KaTeX 数学公式 / Mermaid 图需预渲染，或改用浏览器方案）。

## 安装

```bash
pip install pylitehtml
```

## 30 秒上手

三个最常用入口，按需取用：

**① HTML → 图片**（推荐入口，自动套用一套干净的 GitHub 风默认样式）

```python
from pylitehtml import html_to_png

png = html_to_png("<h1>Hello</h1><p>世界</p>", width=720)
open("out.png", "wb").write(png)
```

**② Markdown → 图片**（内置转换器，零第三方依赖）

```python
from pylitehtml.markdown import markdown_to_png

png = markdown_to_png("# 标题\n\n- 列表\n- [x] 任务\n\n> 引用")
```

**③ 模板文件 → 图片**（本地 HTML 自动解析相对路径的 CSS/图片；带关键字参数即按 Jinja2 模板渲染）

```python
from pylitehtml import render_file

png = render_file("project/index.html", width=800)                          # 纯文件
png = render_file("order.html", width=800,
                  title="订单", items=[{"name": "苹果", "price": 5}])        # Jinja2 模板
```

异步场景：`png = await asyncio.to_thread(html_to_png, html)`。

## 效果展示

[`examples/`](https://github.com/tyql688/pylitehtml/blob/main/examples/) 下的示例均**独立可运行**，各渲染一张图（详见 [examples/README](https://github.com/tyql688/pylitehtml/blob/main/examples/README.md)）：

| 示例 | 说明 | 渲染结果 |
| --- | --- | --- |
| [`showcase_html.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/showcase_html.py) | HTML/CSS 能力参考：排版、颜色/渐变、表格、代码、列表、进度条 + **真实 HTTPS 图片** + `data:` URI 图标 | ![html](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/showcase_html.png) |
| [`showcase_css.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/showcase_css.py) | More CSS：conic/radial 渐变、边框样式、`position`、`::before`、`text-overflow:ellipsis`、`white-space:pre`、`vertical-align` | ![css](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/showcase_css.png) |
| [`showcase_markdown.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/showcase_markdown.py) | 内置**零依赖** Markdown 转换器的端到端输出 | ![markdown](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/showcase_markdown.png) |
| [`showcase_jinja2.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/showcase_jinja2.py) | Jinja2 数据驱动模板（循环 / 条件 / 过滤器 / **autoescape**，一张订单发票） | ![jinja2](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/showcase_jinja2.png) |
| [`markdown_full_converter.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/markdown_full_converter.py) | 用 markdown-it-py 接入**完整 GFM**（脚注 / 定义列表 / Pygments 语法高亮） | ![gfm](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/showcase_markdown_full.png) |
| [`render_markdown_doc.py`](https://github.com/tyql688/pylitehtml/blob/main/examples/render_markdown_doc.py) | 渲染一篇**真实复杂文档**（[`markdown.md`](https://github.com/tyql688/pylitehtml/blob/main/examples/markdown.md)：多表格 / 嵌套列表 / 多语言代码 / 行号引用代码块） | ![doc](https://raw.githubusercontent.com/tyql688/pylitehtml/main/assets/markdown_doc.png) |

> 文本测量为子像素精度；模板变量经 autoescape 安全转义；抓取失败的远程图片自动跳过，不影响整图渲染。

## 使用指南

### `html_to_png` — 带默认样式的 HTML 渲染

```python
from pylitehtml import html_to_png, html_to_image, wrap_html, DEFAULT_CSS

# 传入"片段"时，自动套用默认样式；传入完整文档（含 <html>/<body>）时按原样渲染
png = html_to_png("<h1>标题</h1><p>正文 <code>code</code></p>", width=720)
png = html_to_png("<html><body style='background:#000'>…</body></html>")

# HiDPI：scale 同时放大画布宽度与根字号，em 布局等比放大
png = html_to_png(fragment, width=720, scale=2)

# 追加/覆盖样式；或拿原始 RGBA 像素
png = html_to_png(fragment, extra_css="body{background:#0d1117;color:#e6edf3}")
raw = html_to_image(fragment, fmt="raw")           # → RawResult(.data/.width/.height)
doc = wrap_html("<p>x</p>", css=DEFAULT_CSS)       # 仅生成完整 HTML 文档字符串
```

主要参数：`width`、`scale`（HiDPI 倍数，默认 1）、`wrap`（`None` 自动判断片段/整文档；`True/False` 强制）、`css` / `extra_css`、`fmt`（`"png"`/`"jpeg"`）、`quality`、`height`、`shrink_to_fit`、`locale`、`fonts`、`images`。

### `markdown_to_png` — Markdown → 图片

内置一个**纯标准库**的轻量 Markdown→HTML 转换器，再交给 `html_to_png`，不引入 `markdown-it-py`、`pygments` 等任何第三方依赖：

```python
from pylitehtml.markdown import markdown_to_png, markdown_to_html

png = markdown_to_png("# 标题\n\n- 列表\n- [x] 任务", width=720)   # scale 默认 2
html = markdown_to_html("**bold**")    # → '<p><strong>bold</strong></p>'
```

内置转换器**覆盖**：标题、粗/斜/`***粗斜***`/删除线/行内代码、反斜杠转义、链接/图片/裸 URL、行内 raw HTML、硬换行、围栏代码块（不高亮）、引用、有序（含 `start`）/无序/嵌套/任务列表、带对齐的 GFM 表格、分隔线。**不支持**：setext 标题、引用式链接、脚注、定义列表、缩进代码块。

需要完整 CommonMark/GFM 时，传入 `converter=`（任意 `Callable[[str], str]`）接入 markdown-it-py：

```python
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.deflist import deflist_plugin
from pylitehtml.markdown import markdown_to_png

md = MarkdownIt("gfm-like").use(footnote_plugin).use(deflist_plugin)
png = markdown_to_png(text, converter=md.render)
```

### `Renderer` / `render` — 底层接口（不注入默认样式）

需要复用实例（字体只加载一次）或精细控制输出时使用：

```python
import pylitehtml

png = pylitehtml.render("<h1>Hello</h1>", width=800)      # 一次性便捷函数

r = pylitehtml.Renderer(width=800)                        # 可复用、可并发
jpg = r.render("<h1>Hello</h1>", fmt="jpeg", quality=90)
raw = r.render("<h1>Hello</h1>", fmt="raw")               # RGBA 原始像素
```

`fmt="raw"` 返回的 `RawResult` 可直接转 PIL / NumPy：`Image.frombytes("RGBA", (raw.width, raw.height), raw.data)` 或 `np.frombuffer(raw.data, np.uint8).reshape(raw.height, raw.width, 4)`。

### `render_file` 与 Jinja2 模板

按标准网页组织目录，自动解析相对路径的 CSS/图片；传入关键字参数即作为 [Jinja2](https://jinja.palletsprojects.com/) 模板渲染（变量 / 循环 / 条件 / 过滤器 / `include` / `extends`）：

```python
r = pylitehtml.Renderer(width=800)
png = r.render_file("project/index.html")                                              # 纯文件
png = r.render_file("order.html", title="订单", items=[{"name": "苹果", "price": 5}])   # 模板
```

> **autoescape 默认开启**：`.html` 模板里的 `{{ 变量 }}` 会转义 `<`/`&`/`"`，不可信数据也不会注入。
> **本地文件安全**：`file://` 与根路径资源仅在 `render_file()` 下加载；直接 `render()` 字符串时忽略。

### 多线程与异步

先在单线程构造 `Renderer`，之后可多线程并发 `render()`（渲染期间释放 GIL）；异步用 `await asyncio.to_thread(r.render, html)`。带 `extra` 字体的构造会改写进程级字体配置，勿在渲染进行中于其它线程构造新 `Renderer`。

## 能力边界

litehtml = CSS 2.1 + 部分 CSS3。下表为**实测**结论：

| 能力 | 状态 |
| --- | --- |
| PNG / JPEG / RAW 输出 | ✅ |
| 盒模型、边框（solid/dashed/dotted/double）、`border-radius`、背景色 | ✅ |
| `linear-gradient` / `conic-gradient`（`radial-gradient` ⚠️ 仅颜色对） | ✅ |
| 字体、`color`、`text-align`、`line-height`、`text-shadow`、`text-transform` | ✅ |
| `text-decoration`、`<mark>`/`<sub>`/`<sup>`/`<kbd>`、`white-space:pre/nowrap` | ✅ |
| 列表（嵌套 / `list-style-type` / 任务列表）、定义列表、表格（对齐 / `:nth-child`） | ✅ |
| `float`、`inline-block`、`position:relative/absolute`、`text-overflow:ellipsis`、`::before/::after` | ✅ |
| 图片 `<img>`：`data:`(PNG/JPEG/WebP) / 本地 / HTTP·HTTPS、`@import` CSS | ✅ |
| SVG 图片（内置 nanosvg：path/形状/描边/`userSpaceOnUse` 渐变；不含 `<text>`/滤镜/内联 `<svg>` 标记） | ⚠️ 图形子集 |
| 中文 / 多语言（内置 Noto Sans + SC，中英共享基线、子像素测量） | ✅ |
| 多线程并发、`asyncio.to_thread` | ✅ |
| Flexbox（简单行 / 列） | ⚠️ 部分 |
| `background-image:url()`、`box-shadow`、`transform`、`opacity`、`letter-spacing` | ❌ |
| CSS Grid、`var()`、`@font-face`、动画 / 过渡、`filter`、JavaScript | ❌ |

> 图片抓取失败会自动跳过（不报错）；官方 wheel（Linux manylinux_2_34 / macOS / Windows）均含 OpenSSL ≥ 3.0，支持 https。

## 性能：对比 Playwright

同一篇文档各渲染 30 次（macOS arm64，width=720；基准脚本 [`bench/bench_vs_playwright.py`](https://github.com/tyql688/pylitehtml/blob/main/bench/bench_vs_playwright.py)）：

| 指标 | pylitehtml | Playwright（无头 Chromium） |
| --- | --- | --- |
| 单次渲染（warm，均值） | **≈ 15.5 ms** | ≈ 21 ms |
| 首屏 / 冷启动 | ≈ 0.2 s | ≈ 0.25 s（OS 已缓存）/ **首次可达 ~3.4 s** |
| 额外依赖 | 无（仅系统 Cairo/Pango 等） | **需下载 Chromium ~190 MB+**，每次渲染有浏览器进程内存开销 |
| JavaScript | ❌ 不执行 | ✅ 可执行（KaTeX/Mermaid 等） |

要点：稳态吞吐约快 1.4×；真正的差距在**部署体积与冷启动**——无 Chromium、无浏览器进程，适合容器 / Serverless / 弹性扩缩容场景。需要执行 JS（数学排版、Mermaid 绘图）时仍应选 Playwright。

```bash
pip install playwright && playwright install chromium   # 或: uv pip install --group bench
python bench/bench_vs_playwright.py 30
```

## API 速查

```python
# 高层（推荐）：自动默认样式、片段/整文档自动判别、HiDPI scale
html_to_png(html, *, width=720, scale=1, wrap=None, css=DEFAULT_CSS, extra_css="",
            fmt="png", quality=85, height=0, shrink_to_fit=True,
            locale="en-US", fonts=None, images=None) -> bytes
html_to_image(...)   # 同参数，fmt 可取 "raw" → RawResult(.data/.width/.height，RGBA 行主序)

markdown_to_png(md, *, converter=None, ...)   # converter: Callable[[str], str]，默认内置转换器
markdown_to_html(md) -> str

# 底层：不注入默认样式
Renderer(width, *, locale="en-US", dpi=96.0, device_height=600, fonts=None, images=None)
Renderer.render(html, *, fmt="png", quality=85, height=0, shrink_to_fit=True)
Renderer.render_file(path, *, fmt="png", quality=85, height=0, shrink_to_fit=True, **template_data)
render(html, width, ...) / render_file(path, width, ...)   # 一次性便捷函数

FontConfig(default="Noto Sans", size=16, extra=[])          # 已内置 Noto Sans/SC + DejaVu Sans
ImageConfig(cache_mb=64.0, timeout_ms=5000, max_mb=10.0, allow_http=True)
```

- `scale` 等比放大画布与（默认样式的）根字号；`shrink_to_fit` 把画布收窄到内容宽度。
- 内置字体使 `sans-serif`/`serif`/`monospace` 与中文在无系统字体时也能渲染；`dpi` 影响 `pt` 换算。

## 从源码构建

**Ubuntu / Debian**

```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev libfontconfig1-dev \
  libwebp-dev libjpeg-turbo8-dev libssl-dev cmake ninja-build pkg-config
pip install -e ".[dev]" --no-build-isolation
```

**macOS**

```bash
brew install cairo pango fontconfig webp jpeg-turbo openssl@3 cmake ninja
CC=/usr/bin/clang CXX=/usr/bin/clang++ pip install -e ".[dev]" --no-build-isolation
```

**运行测试 / 代码检查**

```bash
pytest tests/ -v
ruff check .        # lint
ruff format .       # 格式化（CI 用 `ruff format --check` 校验）
```

## 基于

[litehtml](https://github.com/litehtml/litehtml) · [Cairo](https://www.cairographics.org/) · [Pango](https://pango.gnome.org/) · [FontConfig](https://www.freedesktop.org/wiki/Software/fontconfig/) · [pybind11](https://github.com/pybind/pybind11)

MIT License
