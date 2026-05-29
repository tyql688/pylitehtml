#!/usr/bin/env python3
"""Benchmark: pylitehtml vs Playwright (headless Chromium) for HTML → PNG.

Renders the same self-contained HTML document N times with each engine and
reports cold-start and warm per-render latency. pylitehtml reuses one Renderer
(the recommended pattern); Playwright reuses one launched browser + page.

    pip install playwright && playwright install chromium   # 或: uv pip install --group bench
    python bench/bench_vs_playwright.py [N]
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable

import pylitehtml

WIDTH = 720
HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body { margin:0; padding:20px; font-family:"Noto Sans","Noto Sans SC",sans-serif; color:#1f2328; font-size:15px; line-height:1.55; }
  h1 { font-size:24px; margin:0 0 12px; } h2 { font-size:18px; border-bottom:1px solid #d0d7de; padding-bottom:4px; }
  table { border-collapse:collapse; width:100%; } th,td { border:1px solid #d8dee6; padding:6px 10px; }
  th { background:#f6f8fa; } pre { background:#0d1117; color:#e6edf3; padding:12px; border-radius:8px; }
  blockquote { border-left:4px solid #4f46e5; margin:0; padding:6px 14px; background:#f6f8fa; }
  .badge { display:inline-block; background:#2da44e; color:#fff; padding:2px 10px; border-radius:999px; font-size:12px; }
</style></head><body>
  <h1>渲染性能基准 Render Benchmark <span class="badge">demo</span></h1>
  <p>混排中文与 English，<strong>加粗</strong>、<em>斜体</em>、<code>inline code</code>、<a href="#">链接</a>。</p>
  <h2>表格 Table</h2>
  <table><tr><th>引擎</th><th>说明</th><th>支持</th></tr>
    <tr><td>pylitehtml</td><td>litehtml + Cairo + Pango</td><td>✅</td></tr>
    <tr><td>Playwright</td><td>headless Chromium</td><td>✅</td></tr></table>
  <h2>代码 Code</h2>
  <pre>def render(html, width=720):
    return pylitehtml.html_to_png(html, width=width)</pre>
  <blockquote>引用块：无需无头浏览器，启动快、依赖小。</blockquote>
  <ul><li>列表项一</li><li>列表项二<ul><li>嵌套</li></ul></li><li>列表项三</li></ul>
</body></html>"""


def _stats(samples: list[float]) -> dict[str, float]:
    return {
        "min": min(samples) * 1000,
        "mean": statistics.mean(samples) * 1000,
        "median": statistics.median(samples) * 1000,
        "max": max(samples) * 1000,
    }


def _time_warm(fn: Callable[[], object], n: int) -> list[float]:
    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return times


def bench_pylitehtml(n: int) -> tuple[float, list[float]]:
    t0 = time.perf_counter()
    r = pylitehtml.Renderer(width=WIDTH)
    _ = r.render(HTML)  # first render: pays font setup
    cold = time.perf_counter() - t0
    warm = _time_warm(lambda: r.render(HTML), n)
    return cold, warm


def bench_playwright(n: int) -> tuple[float, list[float]] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        t0 = time.perf_counter()
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": WIDTH, "height": 600})
        page.set_content(HTML, wait_until="load")
        _ = page.screenshot(type="png", full_page=True)
        cold = time.perf_counter() - t0

        def one() -> None:
            page.set_content(HTML, wait_until="load")
            page.screenshot(type="png", full_page=True)

        warm = _time_warm(one, n)
        browser.close()
    return cold, warm


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"Rendering the same document {n}x per engine (width={WIDTH})\n")

    pl_cold, pl_warm = bench_pylitehtml(n)
    ps = _stats(pl_warm)
    print("pylitehtml")
    print(f"  cold start (import-warm + 1st render): {pl_cold * 1000:8.1f} ms")
    print(
        f"  warm/render: mean {ps['mean']:.2f} ms · median {ps['median']:.2f} ms · min {ps['min']:.2f} ms"
    )

    pw = bench_playwright(n)
    if pw is None:
        print(
            "\nPlaywright not installed — `pip install playwright && playwright install chromium`"
        )
        return
    pw_cold, pw_warm = pw
    ws = _stats(pw_warm)
    print("\nPlaywright (headless Chromium)")
    print(f"  cold start (launch + 1st render):      {pw_cold * 1000:8.1f} ms")
    print(
        f"  warm/render: mean {ws['mean']:.2f} ms · median {ws['median']:.2f} ms · min {ws['min']:.2f} ms"
    )

    print("\nSpeedup (Playwright / pylitehtml):")
    print(f"  cold start : {pw_cold / pl_cold:6.1f}x")
    print(f"  warm/render: {ws['mean'] / ps['mean']:6.1f}x")


if __name__ == "__main__":
    main()
