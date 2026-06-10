"""Tests for the dependency-free markdown → HTML converter and the end-to-end
markdown → PNG path."""

import pytest
from _helpers import PNG_SIG, to_image

from pylitehtml import RawResult
from pylitehtml.markdown import markdown_to_html as M
from pylitehtml.markdown import markdown_to_image, markdown_to_png


# ── headings & thematic break ─────────────────────────────────────────────────
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_headings(level: int) -> None:
    assert M("#" * level + " Title") == f"<h{level}>Title</h{level}>"


def test_hr() -> None:
    assert "<hr>" in M("a\n\n---\n\nb")


# ── inline ────────────────────────────────────────────────────────────────────
def test_bold_em_strike() -> None:
    assert M("**b**") == "<p><strong>b</strong></p>"
    assert M("*i*") == "<p><em>i</em></p>"
    assert M("__b__") == "<p><strong>b</strong></p>"
    assert M("~~s~~") == "<p><del>s</del></p>"


def test_inline_code_shields_formatting() -> None:
    assert M("`**x**`") == "<p><code>**x**</code></p>"


def test_html_escaping() -> None:
    assert M("a < b & c > d") == "<p>a &lt; b &amp; c &gt; d</p>"


def test_code_span_escapes() -> None:
    assert M("`<tag>`") == "<p><code>&lt;tag&gt;</code></p>"


def test_link_and_image() -> None:
    assert M("[t](u)") == '<p><a href="u">t</a></p>'
    assert M("![a](p.png)") == '<p><img src="p.png" alt="a"></p>'


def test_url_underscores_preserved() -> None:
    # The emphasis pass must not touch underscores inside a URL.
    assert M("[x](http://a_b_c/d)") == '<p><a href="http://a_b_c/d">x</a></p>'


def test_autolink() -> None:
    assert M("see <https://x.io> end") == '<p>see <a href="https://x.io">https://x.io</a> end</p>'


def test_inline_raw_html_passthrough() -> None:
    out = M("red <span style='color:red'>X</span> here")
    assert "<span style='color:red'>X</span>" in out


def test_lt_not_a_tag() -> None:
    assert M("1 < 2 and 3 > 2") == "<p>1 &lt; 2 and 3 &gt; 2</p>"


# ── code fences ───────────────────────────────────────────────────────────────
def test_fenced_code_lang_class_and_escape() -> None:
    out = M('```python\nprint("a<b>")\n```')
    assert 'class="language-python"' in out
    assert "&lt;b&gt;" in out
    assert out.startswith("<pre><code")


def test_fenced_code_no_lang() -> None:
    assert M("```\nplain\n```") == "<pre><code>plain</code></pre>"


# ── blockquote ────────────────────────────────────────────────────────────────
def test_blockquote() -> None:
    assert M("> hi") == "<blockquote><p>hi</p></blockquote>"


def test_blockquote_inline() -> None:
    assert "<strong>b</strong>" in M("> a **b**")


# ── lists ─────────────────────────────────────────────────────────────────────
def test_unordered_list() -> None:
    assert M("- a\n- b") == "<ul><li>a</li><li>b</li></ul>"


def test_ordered_list() -> None:
    assert M("1. a\n2. b").startswith("<ol>")


def test_nested_list() -> None:
    out = M("- a\n  - b\n- c")
    assert out == "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"


def test_task_list() -> None:
    out = M("- [x] done\n- [ ] todo")
    assert '<span class="md-task checked"></span>' in out
    assert '<span class="md-task"></span>' in out
    assert 'class="md-task-item"' in out


# ── tables ────────────────────────────────────────────────────────────────────
def test_table_with_alignment() -> None:
    out = M("| A | B | C |\n|:--|:-:|--:|\n| 1 | 2 | 3 |")
    assert "<table>" in out and "<thead>" in out
    assert "text-align:left" in out
    assert "text-align:center" in out
    assert "text-align:right" in out
    assert out.count("<td") == 3


def test_not_a_table_without_delimiter() -> None:
    # A line with pipes but no delimiter row is a paragraph, not a table.
    assert M("a | b | c").startswith("<p>")


# ── block html passthrough ────────────────────────────────────────────────────
def test_html_block_passthrough() -> None:
    assert M('<div class="x">raw</div>') == '<div class="x">raw</div>'


# ── edge cases ────────────────────────────────────────────────────────────────
def test_empty() -> None:
    assert M("") == ""
    assert M("\n\n\n") == ""


def test_cjk() -> None:
    assert M("# 你好\n\n世界") == "<h1>你好</h1>\n<p>世界</p>"


# ── end to end ────────────────────────────────────────────────────────────────
KITCHEN_SINK = """\
# Title

Para with **bold**, *em*, `code`, ~~strike~~, [link](https://x.io).

- item
  - nested
- [x] done

| A | B |
|:-|-:|
| 1 | 2 |

```python
print("hi")
```

> quote

---

<span style="color:#cf222e">raw html</span>
"""


def test_markdown_to_png_valid() -> None:
    out = markdown_to_png(KITCHEN_SINK, width=600)
    assert isinstance(out, bytes) and out[:8] == PNG_SIG and len(out) > 1000


def test_markdown_to_png_jpeg() -> None:
    out = markdown_to_png("# hi", width=300, fmt="jpeg", quality=80)
    assert out[:2] == b"\xff\xd8"


def test_markdown_to_image_raw_has_content() -> None:
    out = markdown_to_image(KITCHEN_SINK, width=600, fmt="raw")
    assert isinstance(out, RawResult)
    im = to_image(out)
    data = im.tobytes()
    assert any(data[i] < 100 for i in range(0, len(data), 4))  # text drawn


def test_custom_converter_override() -> None:
    out = markdown_to_png("ignored", width=200, converter=lambda _md: "<h1>From converter</h1>")
    assert out[:8] == PNG_SIG


def test_scale_doubles_markdown_width() -> None:
    a = markdown_to_image("# t", width=300, scale=1, fmt="raw")
    b = markdown_to_image("# t", width=300, scale=2, fmt="raw")
    assert isinstance(a, RawResult) and isinstance(b, RawResult)
    assert b.width == 2 * a.width


def test_deterministic() -> None:
    assert markdown_to_png(KITCHEN_SINK, width=500) == markdown_to_png(KITCHEN_SINK, width=500)


# ── extra coverage ────────────────────────────────────────────────────────────
def test_ordered_list_paren_marker() -> None:
    assert M("1) a\n2) b").startswith("<ol>")


def test_heading_trailing_hashes_stripped() -> None:
    assert M("## Title ##") == "<h2>Title</h2>"


def test_nested_blockquote() -> None:
    out = M("> outer\n> > inner")
    assert out.count("<blockquote>") == 2


def test_multiple_paragraphs() -> None:
    assert M("para one\n\npara two") == "<p>para one</p>\n<p>para two</p>"


def test_mixed_emphasis_in_one_line() -> None:
    out = M("a **b** c *d* e `f` g")
    assert "<strong>b</strong>" in out
    assert "<em>d</em>" in out
    assert "<code>f</code>" in out


def test_image_inside_link() -> None:
    out = M("[![alt](img.png)](https://x.io)")
    assert '<img src="img.png"' in out and '<a href="https://x.io">' in out


def test_table_ragged_rows_padded() -> None:
    # A row with fewer cells than the header is padded, not dropped.
    out = M("| A | B | C |\n|---|---|---|\n| 1 |")
    assert out.count("<td") == 3


def test_fenced_code_preserves_indentation() -> None:
    out = M("```\n    indented\n        more\n```")
    assert "    indented\n        more" in out


def test_consecutive_lists_separated_by_blank() -> None:
    out = M("- a\n- b\n\n1. c\n2. d")
    assert out.count("<ul>") == 1 and out.count("<ol>") == 1


def test_bold_italic_nesting() -> None:
    assert M("***bi***") == "<p><strong><em>bi</em></strong></p>"
    assert M("___bi___") == "<p><strong><em>bi</em></strong></p>"


def test_backslash_escapes() -> None:
    assert M(r"\*not italic\*") == "<p>*not italic*</p>"
    assert M(r"\`not code\`") == "<p>`not code`</p>"
    assert M(r"a \_ b") == "<p>a _ b</p>"


def test_bare_url_autolinked() -> None:
    out = M("see https://example.com/a_b_c here")
    assert '<a href="https://example.com/a_b_c">https://example.com/a_b_c</a>' in out


def test_bare_url_trailing_punctuation_kept_as_text() -> None:
    out = M("go to https://x.io.")
    assert '<a href="https://x.io">https://x.io</a>.' in out


def test_bare_url_not_triggered_in_link_syntax() -> None:
    assert M("[t](https://x.io)") == '<p><a href="https://x.io">t</a></p>'


def test_bare_url_stops_at_cjk_and_tokens() -> None:
    # The URL must stop at the CJK comma and not swallow following inline tokens.
    out = M("裸链接 https://example.com、`code`、转义 \\*x\\*。")
    assert '<a href="https://example.com">https://example.com</a>' in out
    assert "<code>code</code>" in out
    assert "*x*" in out and "<em>" not in out  # backslash-escaped, not italic


def test_bare_url_query_ampersand_escaped() -> None:
    out = M("see https://a.io/p?q=1&x=2 ok")
    assert '<a href="https://a.io/p?q=1&amp;x=2">' in out


def test_hard_line_break() -> None:
    assert M("line1  \nline2") == "<p>line1<br>line2</p>"
    assert M("line1\\\nline2") == "<p>line1<br>line2</p>"


def test_ordered_list_start_attribute() -> None:
    assert M("3. c\n4. d").startswith('<ol start="3">')
    assert M("1. a\n2. b").startswith("<ol>")  # start=1 omits the attribute


def test_render_file_style_full_doc_via_converter() -> None:
    # A converter may emit a full document; html_to_image renders it verbatim.
    out = markdown_to_png(
        "x",
        width=200,
        converter=lambda _m: "<html><body style='background:#000'>x</body></html>",
    )
    assert out[:8] == PNG_SIG


# ── escaped pipes in tables (GFM: \| is a literal pipe inside a cell) ─────────


def test_table_escaped_pipe_is_literal() -> None:
    out = M("| a \\| b | c |\n|---|---|\n| 1 | 2 |")
    assert "<th>a | b</th>" in out
    assert "<th>c</th>" in out
    assert "<td>1</td>" in out and "<td>2</td>" in out


# ── URL scheme allowlist (cmark --safe semantics) ─────────────────────────────


def test_link_javascript_url_dropped() -> None:
    out = M("[click](javascript:alert(1))")
    assert "javascript:" not in out
    assert '<a href="">' in out


def test_image_unsafe_scheme_dropped() -> None:
    out = M("![x](vbscript:foo)")
    assert "vbscript:" not in out


def test_image_data_uri_still_allowed() -> None:
    out = M("![x](data:image/png;base64,iVBORw0KGgo=)")
    assert 'src="data:image/png;base64,iVBORw0KGgo="' in out


def test_link_relative_and_anchor_still_allowed() -> None:
    assert '<a href="docs/page.html">' in M("[d](docs/page.html)")
    assert '<a href="#sec">' in M("[s](#sec)")
