#!/usr/bin/env python3
"""More CSS capabilities → assets/showcase_css.png

Beyond the basics: conic/radial gradients, border styles, text-shadow,
text-transform, white-space:pre, position:absolute, list-style-type,
``::before`` pseudo-elements, text-overflow:ellipsis and vertical-align.
Run: ``python examples/showcase_css.py``
"""

from __future__ import annotations

from pathlib import Path

import pylitehtml

ASSETS = Path(__file__).resolve().parent.parent / "assets"

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body { margin:0; padding:18px 20px; font-family:"Noto Sans","Noto Sans SC",sans-serif; font-size:14px; color:#1f2328; background:#fff; }
  h2 { margin:0 0 14px; font-size:19px; border-bottom:2px solid #eef1f5; padding-bottom:8px; }
  .row { display:flex; }
  .col { flex:1; padding:0 10px; }
  .lab { font-size:12px; color:#59636e; margin:10px 0 4px; }
  .sw { height:40px; border-radius:8px; }
  .radial { background:radial-gradient(circle at 30% 30%, #f59e0b, #ef4444); }
  .conic  { background:conic-gradient(from .25turn, #4f46e5, #06b6d4, #2da44e, #f59e0b, #4f46e5); border-radius:50%; width:40px; margin:0 auto; }
  .tshadow { font-size:22px; font-weight:700; text-shadow:2px 2px 3px rgba(0,0,0,.35); }
  .b { display:inline-block; width:48px; height:30px; margin-right:6px; border-radius:6px; }
  .dashed{border:3px dashed #4f46e5} .dotted{border:3px dotted #cf222e} .double{border:4px double #2da44e}
  .rel { position:relative; height:42px; background:#eef1f5; border-radius:6px; padding:6px 10px; }
  .abs { position:absolute; right:6px; top:6px; background:#2da44e; color:#fff; padding:1px 8px; border-radius:999px; font-size:12px; }
  ol.roman { list-style-type:upper-roman; margin:4px 0; } ul.sq { list-style-type:square; margin:4px 0; }
  .starred::before { content:"★ "; color:#f59e0b; }
  pre.pre { white-space:pre; background:#0d1117; color:#e6edf3; padding:8px 10px; border-radius:6px; font-family:"DejaVu Sans Mono",monospace; font-size:12px; margin:0; }
  .ell { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; width:200px; border:1px solid #d0d7de; border-radius:6px; padding:5px 8px; }
  .up { text-transform:uppercase; }
  table.va { border-collapse:collapse; } table.va td { height:42px; border:1px solid #d8dee6; padding:0 10px; }
  .va .t{vertical-align:top} .va .m{vertical-align:middle} .va .bt{vertical-align:bottom}
</style></head><body>
  <h2>More CSS 能力</h2>
  <div class="row">
    <div class="col">
      <div class="lab">radial / conic 渐变</div>
      <div class="sw radial"></div>
      <div class="conic sw" style="height:40px;margin-top:8px"></div>
      <div class="lab">边框样式 border</div>
      <span class="b dashed"></span><span class="b dotted"></span><span class="b double"></span>
      <div class="lab">text-shadow / text-transform</div>
      <div class="tshadow">Shadow 阴影</div>
      <div class="up">uppercase 自动大写</div>
    </div>
    <div class="col">
      <div class="lab">position: absolute</div>
      <div class="rel">relative 容器<span class="abs">absolute</span></div>
      <div class="lab">list-style-type / ::before 伪元素</div>
      <ol class="roman"><li>one</li><li>two</li></ol>
      <p class="starred" style="margin:2px 0">伪元素加的星标</p>
      <div class="lab">text-overflow: ellipsis</div>
      <div class="ell">这是一段很长的文本会被裁剪并显示省略号 ellipsis</div>
    </div>
  </div>
  <div class="lab">white-space: pre（保留空白与换行）</div>
  <pre class="pre">def render(html, width):
    # 缩进与换行原样保留
    return png</pre>
  <div class="lab" style="margin-top:10px">vertical-align（表格单元格）</div>
  <table class="va"><tr><td class="t">top 顶</td><td class="m">middle 中</td><td class="bt">bottom 底</td></tr></table>
</body></html>
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    png = pylitehtml.html_to_png(HTML, width=820, scale=2, wrap=False)
    out = ASSETS / "showcase_css.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
