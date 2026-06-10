# Examples

每个脚本独立可跑，输出图片到仓库根的 `assets/`（README 引用的截图即来源于此）。

| 脚本 | 演示内容 | 输出 |
|------|---------|------|
| `showcase_html.py` | HTML/CSS 能力总览："kitchen sink"——排版（CJK/Latin 基线对齐）、颜色与渐变、表格、代码、列表、进度条、HTTPS 真实图片 + `data:` URI 图标 | `assets/showcase_html.png` |
| `showcase_css.py` | 进阶 CSS：conic/radial 渐变、border 样式、text-shadow、text-transform、`white-space:pre`、绝对定位、`::before` 伪元素、ellipsis、vertical-align | `assets/showcase_css.png` |
| `showcase_markdown.py` | 内置零依赖 Markdown 转换器 → 图片 | `assets/showcase_markdown.png` |
| `showcase_jinja2.py` | Jinja2 数据驱动模板（循环/条件/过滤器/autoescape）经 `render_file` 渲染发票 | `assets/showcase_jinja2.png` |
| `markdown_full_converter.py` | 自定义 `converter=` 接入 markdown-it-py，获得完整 CommonMark/GFM（脚注、定义列表、语法高亮等） | `assets/showcase_markdown_full.png` |
| `render_markdown_doc.py` | 渲染一份特性密集的真实文档 `markdown.md`（多表格、嵌套列表、代码高亮、行号区间 fence 等） | `assets/markdown_doc.png` |

## 运行

```bash
# 基础示例只需要 pylitehtml 本体
python examples/showcase_html.py

# markdown-it-py 系列示例需要额外依赖（PEP 735 dependency group）
uv pip install --group examples
python examples/render_markdown_doc.py
```

`markdown.md` 是 `render_markdown_doc.py` 的输入文档，不是可执行脚本。
