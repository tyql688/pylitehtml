#!/usr/bin/env python3
"""Markdown → image via the built-in zero-dependency converter.

→ assets/showcase_markdown.png   Run: ``python examples/showcase_markdown.py``
"""

from __future__ import annotations

from pathlib import Path

from pylitehtml.markdown import markdown_to_png

ASSETS = Path(__file__).resolve().parent.parent / "assets"

MARKDOWN = """\
# Markdown → PNG

内置**零依赖**转换器：标题、*强调*、`行内代码`、~~删除线~~、[链接](https://example.com)、
裸链接 https://example.com、`***粗斜体***`、反斜杠转义 \\*literal\\*。

## 列表与任务

- 无序项
  - 嵌套项
- [x] 已完成任务
- [ ] 待办任务

3. 从 3 开始的有序
4. 下一项

## 表格（带对齐）

| 左对齐 | 居中 | 右对齐 |
|:------|:----:|------:|
| a     | b    | 100   |
| cc    | dd   | 2     |

## 代码块

```python
def hello(name):
    print(f"你好, {name}")
```

> 引用块同样支持 **加粗** 与 `代码`。

---

行内 HTML 透传：<span style="color:#cf222e">红色文字</span>。
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    png = markdown_to_png(MARKDOWN, width=760, scale=2)
    out = ASSETS / "showcase_markdown.png"
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
