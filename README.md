# pylitehtml

HTML+CSS → PNG/JPEG image renderer. Lightweight, no headless browser, thread-safe.

## Install

```bash
pip install pylitehtml
```

## Usage

```python
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
```

## Built on

- [litehtml](https://github.com/litehtml/litehtml) — HTML/CSS layout
- Cairo + Pango — rendering + text
