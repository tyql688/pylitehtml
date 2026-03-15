# tests/test_new_features.py
"""Tests for data: URI images, CSS @import data URIs, DPI/lang config, allow_refit."""
import base64
import io
import pathlib
import pytest
from PIL import Image
from pylitehtml import Renderer, OutputFormat

ASSETS = pathlib.Path(__file__).parent / "assets"


def _make_png_bytes(color=(255, 0, 0), size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(color=(0, 0, 255), size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_webp_bytes(color=(0, 255, 0), size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, (*color, 255)).save(buf, format="WEBP")
    return buf.getvalue()


def _data_uri(image_bytes: bytes, mime: str) -> str:
    encoded = base64.b64encode(image_bytes).decode()
    return f"data:{mime};base64,{encoded}"


# ── data: URI images ──────────────────────────────────────────────────────────

def test_data_uri_png_image():
    r = Renderer(width=200)
    uri = _data_uri(_make_png_bytes(), "image/png")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_jpeg_image():
    r = Renderer(width=200)
    uri = _data_uri(_make_jpeg_bytes(), "image/jpeg")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_webp_image():
    r = Renderer(width=200)
    uri = _data_uri(_make_webp_bytes(), "image/webp")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_background_image():
    r = Renderer(width=200)
    uri = _data_uri(_make_png_bytes(color=(255, 0, 0)), "image/png")
    html = f"<div style='background-image:url({uri});width:10px;height:10px'></div>"
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


# ── CSS @import data URI ──────────────────────────────────────────────────────

def test_import_css_data_uri_base64():
    css_source = "body { background: #00ff00 !important; margin: 0; }"
    encoded = base64.b64encode(css_source.encode()).decode()
    uri = f"data:text/css;base64,{encoded}"
    html = (f"<html><head><style>@import url('{uri}');</style></head>"
            "<body><div style='height:2px'></div></body></html>")
    r = Renderer(width=100)
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    # Green channel should be high (green background)
    assert raw.data[1] > 200, f"G={raw.data[1]}, expected green background from CSS data URI"


# ── DPI configuration ─────────────────────────────────────────────────────────

def test_dpi_default():
    """Renderer with default DPI should produce a valid image."""
    r = Renderer(width=400)
    assert len(r.render("<p>Hello</p>")) > 0


def test_dpi_custom():
    """High-DPI renderer should produce larger content (text appears bigger)."""
    r_96 = Renderer(width=400, dpi=96.0)
    r_192 = Renderer(width=400, dpi=192.0)
    html = "<p style='font-size:12pt'>Hi</p>"
    raw_96 = r_96.render(html, fmt=OutputFormat.RAW)
    raw_192 = r_192.render(html, fmt=OutputFormat.RAW)
    # Higher DPI → pt units map to more pixels → taller content
    assert raw_192.height >= raw_96.height


# ── Language / culture configuration ─────────────────────────────────────────

def test_lang_default():
    r = Renderer(width=400)
    assert len(r.render("<p lang='en'>Hello</p>")) > 0


def test_lang_custom():
    r = Renderer(width=400, lang="zh", culture="zh-CN")
    assert len(r.render("<p lang='zh'>你好</p>")) > 0


# ── allow_refit ───────────────────────────────────────────────────────────────

def test_allow_refit_narrow_content():
    """Content narrower than viewport should produce a narrower surface when allow_refit=True."""
    r = Renderer(width=800)
    html = "<p style='width:100px'>Hi</p>"
    raw_no  = r.render(html, fmt=OutputFormat.RAW, allow_refit=False)
    raw_yes = r.render(html, fmt=OutputFormat.RAW, allow_refit=True)
    assert raw_no.width == 800
    assert raw_yes.width <= 800


def test_allow_refit_wide_content():
    """Content filling full width should not shrink when allow_refit=True."""
    r = Renderer(width=400)
    html = "<div style='width:400px;height:10px;background:red'></div>"
    raw = r.render(html, fmt=OutputFormat.RAW, allow_refit=True)
    assert raw.width <= 400 and raw.width > 0


def test_allow_refit_false_keeps_viewport_width():
    r = Renderer(width=800)
    raw = r.render("<p>Hi</p>", fmt=OutputFormat.RAW, allow_refit=False)
    assert raw.width == 800
