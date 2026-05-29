#!/usr/bin/env python3
"""HTML/CSS capability reference → assets/showcase_html.png

A "kitchen sink" exercising the slice of HTML/CSS that litehtml (and therefore
pylitehtml) supports well: typography (baseline-correct CJK/Latin), colours &
gradients, tables, code, lists, progress bars, and a **real HTTPS image** plus a
``data:`` URI icon. Run: ``python examples/showcase_html.py``
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

import pylitehtml

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _icon_data_uri() -> str:
    """A small rounded icon PNG embedded as a data URI (offline, no network)."""
    s = 36
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = img.load()
    assert px is not None
    for x in range(s):
        for y in range(s):
            px[x, y] = (int(60 + 150 * x / s), int(90 + 120 * y / s), 230, 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: "Noto Sans", "Noto Sans SC", sans-serif;
    color: #1f2328; background: #eef1f5; font-size: 15px; line-height: 1.55;
  }
  .page { padding: 24px; }
  .hero {
    background: linear-gradient(120deg, #4f46e5, #06b6d4);
    color: #fff; padding: 28px 32px; border-radius: 14px; margin-bottom: 22px;
  }
  .hero h1 { margin: 0 0 6px; font-size: 30px; font-weight: 700; }
  .hero p  { margin: 0; opacity: 0.92; }
  .card {
    background: #fff; border: 1px solid #d8dee6; border-radius: 12px;
    padding: 18px 20px; margin-bottom: 18px;
  }
  .card h2 { margin: 0 0 12px; font-size: 19px; border-bottom: 2px solid #eef1f5; padding-bottom: 8px; }
  .row { display: flex; }
  .col { flex: 1; padding: 0 8px; }
  .swatch { height: 46px; border-radius: 8px; margin-bottom: 6px; }
  .label { font-size: 12px; color: #59636e; text-align: center; }
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; color: #fff; background: #2da44e; margin-right: 6px;
  }
  .badge.warn { background: #bf8700; } .badge.err { background: #cf222e; } .badge.info { background: #0969da; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #d8dee6; padding: 7px 12px; text-align: left; }
  th { background: #f6f8fa; } tr:nth-child(2n) td { background: #fafbfc; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  pre { background: #0d1117; color: #e6edf3; padding: 14px 16px; border-radius: 10px; margin: 0; line-height: 1.5; }
  pre .k { color: #ff7b72; } pre .s { color: #a5d6ff; } pre .c { color: #8b949e; } pre .f { color: #d2a8ff; }
  code { font-family: "DejaVu Sans Mono", monospace; background: #eff1f3; padding: 2px 6px; border-radius: 5px; font-size: 0.88em; }
  blockquote { margin: 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f6f8fa; color: #444; }
  ul.feat { margin: 0; padding-left: 22px; } ul.feat li { margin: 4px 0; }
  .bar { background: #eef1f5; border-radius: 6px; height: 12px; overflow: hidden; margin: 6px 0; }
  .bar > span { display: block; height: 12px; background: linear-gradient(90deg, #4f46e5, #06b6d4); }
  mark { background: #fff3a3; padding: 0 3px; }
  kbd { background: #fff; border: 1px solid #ccc; border-radius: 4px; padding: 1px 6px; font-family: monospace; font-size: 0.85em; }
  .muted { color: #8b949e; }
  dl { margin: 0; } dt { font-weight: 600; margin-top: 8px; } dd { margin: 0 0 0 16px; color: #444; }
  .right { float: right; color: #8b949e; font-size: 12px; }
  .media { display: flex; }
  .photo { width: 240px; height: 160px; border-radius: 10px; border: 1px solid #d8dee6; }
  .media-body { padding-left: 16px; flex: 1; }
  .media-body p { margin: 0 0 8px; }
  .icon { width: 18px; height: 18px; border-radius: 4px; vertical-align: -4px; }
</style></head>
<body><div class="page">

  <div class="hero">
    <h1>pylitehtml</h1>
    <p>HTML + CSS &rarr; PNG · 轻量级 · 无需无头浏览器 · 线程安全</p>
  </div>

  <div class="card">
    <h2>排版 Typography <span class="right">inline styles</span></h2>
    <p><strong>加粗</strong>、<em>斜体</em>、<u>下划线</u>、<del>删除线</del>、
       <code>inline code</code>、<mark>高亮</mark>、上标 x<sup>2</sup>、下标 H<sub>2</sub>O、
       快捷键 <kbd>Ctrl</kbd>+<kbd>C</kbd>、<a href="#">链接</a>。</p>
    <p class="muted">混排中文与 English、絵文字 ★ ✓ → 与多字号文本，行高与基线对齐正常。</p>
    <blockquote>引用块 blockquote：litehtml 支持 border-left、背景与内边距。</blockquote>
  </div>

  <div class="card">
    <h2>颜色与渐变 Colors &amp; Gradients</h2>
    <div class="row">
      <div class="col"><div class="swatch" style="background:#4f46e5"></div><div class="label">indigo</div></div>
      <div class="col"><div class="swatch" style="background:#06b6d4"></div><div class="label">cyan</div></div>
      <div class="col"><div class="swatch" style="background:#2da44e"></div><div class="label">green</div></div>
      <div class="col"><div class="swatch" style="background:#cf222e"></div><div class="label">red</div></div>
      <div class="col"><div class="swatch" style="background:linear-gradient(90deg,#f59e0b,#ef4444)"></div><div class="label">gradient</div></div>
    </div>
    <p style="margin-bottom:0"><span class="badge">success</span><span class="badge info">info</span><span class="badge warn">warning</span><span class="badge err">error</span></p>
  </div>

  <div class="card">
    <h2>表格 Table</h2>
    <table>
      <thead><tr><th>引擎</th><th>说明</th><th class="num">支持度</th></tr></thead>
      <tbody>
        <tr><td>block / inline</td><td>盒模型、边距、边框、圆角</td><td class="num">100%</td></tr>
        <tr><td>flexbox</td><td>简单行/列布局</td><td class="num">部分</td></tr>
        <tr><td>table</td><td>border-collapse、对齐、斑马纹</td><td class="num">100%</td></tr>
        <tr><td>float</td><td>左右浮动与清除</td><td class="num">100%</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>代码高亮 Code</h2>
    <pre><span class="k">def</span> <span class="f">render</span>(html, width=<span class="s">800</span>):
    <span class="c"># HTML + CSS -&gt; PNG</span>
    <span class="k">return</span> pylitehtml.render(html, width)</pre>
  </div>

  <div class="row">
    <div class="col">
      <div class="card" style="margin:0">
        <h2>列表 Lists</h2>
        <ul class="feat">
          <li>无序列表项</li>
          <li>嵌套：
            <ul><li>子项 A</li><li>子项 B</li></ul>
          </li>
          <li>第三项</li>
        </ul>
      </div>
    </div>
    <div class="col">
      <div class="card" style="margin:0">
        <h2>进度条 Bars</h2>
        <div class="bar"><span style="width:90%"></span></div>
        <div class="bar"><span style="width:65%"></span></div>
        <div class="bar"><span style="width:40%"></span></div>
        <dl>
          <dt>定义列表</dt><dd>dt / dd 正常渲染</dd>
        </dl>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:18px">
    <h2>图片 Images <span class="right">真实图片 · HTTPS</span></h2>
    <div class="media">
      <img class="photo" src="https://picsum.photos/seed/pylitehtml/240/160" alt="photo">
      <div class="media-body">
        <p><strong>真实远程图片</strong>：通过 HTTPS 加载（Lorem Picsum），自动按 <code>width</code>/<code>height</code>
        缩放，圆角与边框生效。支持 PNG / JPEG / WebP / SVG。</p>
        <p class="muted">内联 <code>data:</code> URI 图标 <img class="icon" src="__ICON__" alt=""> 离线可用，无需网络。</p>
        <p class="muted">抓取失败的图片会被自动跳过，不会让整张图渲染失败。</p>
      </div>
    </div>
  </div>

</div></body></html>
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    png = pylitehtml.html_to_png(
        HTML.replace("__ICON__", _icon_data_uri()),
        width=820,
        scale=2,
        wrap=False,
        images=pylitehtml.ImageConfig(timeout_ms=8000),
    )
    out = ASSETS / "showcase_html.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
