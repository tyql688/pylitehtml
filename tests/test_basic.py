# tests/test_basic.py
import pytest
import pylitehtml
from pylitehtml import Renderer, OutputFormat, RawResult

def test_render_png(renderer, simple_html):
    png = renderer.render(simple_html)
    assert isinstance(png, bytes)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'

def test_render_jpeg(renderer, simple_html):
    jpg = renderer.render(simple_html, fmt=OutputFormat.JPEG, quality=80)
    assert isinstance(jpg, bytes)
    assert jpg[:2] == b'\xff\xd8'

def test_render_raw_rgba(renderer, simple_html):
    raw = renderer.render(simple_html, fmt=OutputFormat.RAW)
    assert isinstance(raw, RawResult)
    assert raw.width == 800
    assert raw.height > 0
    assert len(raw.data) == raw.width * raw.height * 4

def test_raw_rgba_byte_order(renderer):
    """ARGB32 -> RGBA swizzle: red background must produce R=255, G=0, B=0."""
    html = "<html><body style='background:#ff0000;margin:0'><div style='height:2px'></div></body></html>"
    raw = renderer.render(html, fmt=OutputFormat.RAW, height=2)
    r, g, b, _ = raw.data[0], raw.data[1], raw.data[2], raw.data[3]
    assert r == 255, f"R={r}"
    assert g == 0,   f"G={g}"
    assert b == 0,   f"B={b}"

def test_auto_height(renderer):
    raw = renderer.render("<p>Hello</p>", fmt=OutputFormat.RAW)
    assert raw.height > 0

def test_fixed_height(renderer, simple_html):
    raw = renderer.render(simple_html, fmt=OutputFormat.RAW, height=600)
    assert raw.height == 600

def test_convenience_function(simple_html):
    png = pylitehtml.render(simple_html, width=400)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'

def test_render_fmt_string_png(renderer, simple_html):
    assert renderer.render(simple_html, fmt="png")[:8] == b'\x89PNG\r\n\x1a\n'


def test_render_fmt_string_jpeg(renderer, simple_html):
    assert renderer.render(simple_html, fmt="jpeg")[:2] == b'\xff\xd8'


def test_render_fmt_string_raw(renderer, simple_html):
    assert isinstance(renderer.render(simple_html, fmt="raw"), RawResult)


def test_render_fmt_invalid_raises(renderer, simple_html):
    with pytest.raises(ValueError, match="Unknown fmt"):
        renderer.render(simple_html, fmt="bmp")


def test_flexbox():
    r = Renderer(width=400)
    html = """<html><style>.row{display:flex}.box{width:50px;height:50px;background:red}</style>
    <body><div class="row"><div class="box"></div></div></body></html>"""
    png = r.render(html)
    assert len(png) > 0
