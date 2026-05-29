#!/usr/bin/env python3
"""Jinja2 data-driven template → image.

Renders a data-driven invoice (loop / conditional / filter / autoescape) via
``render_file``. → assets/showcase_jinja2.png
Run: ``python examples/showcase_jinja2.py``
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pylitehtml

ASSETS = Path(__file__).resolve().parent.parent / "assets"

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body { margin: 0; padding: 22px 24px; font-family: "Noto Sans","Noto Sans SC",sans-serif; color: #1f2328; }
  h2 { margin: 0 0 4px; font-size: 20px; }
  .sub { color: #59636e; margin: 0 0 16px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border-bottom: 1px solid #e1e5ea; padding: 8px 10px; text-align: left; }
  th { background: #f6f8fa; }
  td.amt { text-align: right; font-variant-numeric: tabular-nums; }
  .badge { display:inline-block; padding:1px 9px; border-radius:999px; font-size:12px; color:#fff; }
  .paid { background:#2da44e; } .due { background:#cf222e; }
  tr.total td { font-weight:700; border-top:2px solid #d0d7de; border-bottom:none; }
  .note { margin-top:14px; color:#59636e; font-size:13px; }
</style></head><body>
  <h2>{{ title }} <span class="badge {{ 'paid' if paid else 'due' }}">{{ '已支付' if paid else '待支付' }}</span></h2>
  <p class="sub">客户：{{ customer }} · 单号 #{{ number }}</p>
  <table>
    <thead><tr><th>商品</th><th>单价</th><th>数量</th><th>小计</th></tr></thead>
    <tbody>
    {% for it in items %}
      <tr>
        <td>{{ it.name }}</td>
        <td class="amt">¥{{ "%.2f"|format(it.price) }}</td>
        <td class="amt">{{ it.qty }}</td>
        <td class="amt">¥{{ "%.2f"|format(it.price * it.qty) }}</td>
      </tr>
    {% endfor %}
      <tr class="total"><td colspan="3">合计</td>
        <td class="amt">¥{{ "%.2f"|format(total) }}</td></tr>
    </tbody>
  </table>
  <p class="note">备注（autoescape 演示）：{{ note }}</p>
</body></html>
"""

DATA: dict[str, Any] = {
    "title": "订单 Order",
    "paid": True,
    "customer": "张三 <Acme & Co.>",  # < & " are auto-escaped, never injected
    "number": 20260529,
    "items": [
        {"name": "苹果 Apple", "price": 5.0, "qty": 3},
        {"name": "香蕉 Banana", "price": 3.5, "qty": 2},
        {"name": "咖啡 Coffee", "price": 28.0, "qty": 1},
    ],
    "total": 5.0 * 3 + 3.5 * 2 + 28.0,
    "note": '<b>谢谢惠顾</b> & 欢迎下次 "光临"',
}


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        tpl = Path(d) / "invoice.html"
        tpl.write_text(TEMPLATE, encoding="utf-8")
        png = pylitehtml.Renderer(width=760, locale="zh-CN").render_file(tpl, **DATA)
    assert isinstance(png, bytes)
    out = ASSETS / "showcase_jinja2.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
