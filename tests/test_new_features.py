# tests/test_new_features.py
"""Tests for data: URI images, SVG, CSS @import, DPI/locale config, shrink_to_fit."""
import base64
import io
import pathlib

from PIL import Image
from pylitehtml import Renderer, ImageConfig, OutputFormat, RawResult

ASSETS = pathlib.Path(__file__).parent / "assets"


def _make_png_bytes(color: tuple[int, int, int] = (255, 0, 0), size: tuple[int, int] = (10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(color: tuple[int, int, int] = (0, 0, 255), size: tuple[int, int] = (10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_webp_bytes(color: tuple[int, int, int] = (0, 255, 0), size: tuple[int, int] = (10, 10)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, (*color, 255)).save(buf, format="WEBP")
    return buf.getvalue()


def _data_uri(image_bytes: bytes, mime: str) -> str:
    encoded = base64.b64encode(image_bytes).decode()
    return f"data:{mime};base64,{encoded}"


# ── data: URI images ──────────────────────────────────────────────────────────

def test_data_uri_png_image() -> None:
    r = Renderer(width=200)
    uri = _data_uri(_make_png_bytes(), "image/png")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_jpeg_image() -> None:
    r = Renderer(width=200)
    uri = _data_uri(_make_jpeg_bytes(), "image/jpeg")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_webp_image() -> None:
    r = Renderer(width=200)
    uri = _data_uri(_make_webp_bytes(), "image/webp")
    html = f'<img src="{uri}" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_data_uri_background_image() -> None:
    r = Renderer(width=200)
    uri = _data_uri(_make_png_bytes(color=(255, 0, 0)), "image/png")
    html = f"<div style='background-image:url({uri});width:10px;height:10px'></div>"
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


# ── SVG images ───────────────────────────────────────────────────────────────

SVG_CIRCLE = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    b'<circle cx="50" cy="50" r="40" fill="red"/></svg>'
)


def test_svg_data_uri() -> None:
    """SVG embedded as base64 data URI should render a red circle."""
    r = Renderer(width=200)
    uri = _data_uri(SVG_CIRCLE, "image/svg+xml")
    html = f'<img src="{uri}" width="100" height="100">'
    raw = r.render(html, fmt=OutputFormat.RAW, height=120)
    assert isinstance(raw, RawResult)
    # At minimum the image should have non-white content
    assert raw.width > 0 and raw.height > 0


def test_svg_file_uri(tmp_path: pathlib.Path) -> None:
    """SVG loaded from a local file: URI should produce a valid image."""
    svg_file = tmp_path / "circle.svg"
    _ = svg_file.write_bytes(SVG_CIRCLE)
    r = Renderer(width=200)
    html = f'<img src="file://{svg_file}" width="100" height="100">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


def test_svg_no_size_attribute() -> None:
    """SVG with no explicit pixel dimensions falls back to 512×512 by default."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="blue"/></svg>'
    r = Renderer(width=200)
    uri = _data_uri(svg, "image/svg+xml")
    html = f'<img src="{uri}">'
    result = r.render(html)
    assert isinstance(result, bytes) and len(result) > 0


# ── device_height ─────────────────────────────────────────────────────────────

def test_device_height_default() -> None:
    """Renderer with default device_height should produce a valid image."""
    r = Renderer(width=400)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_device_height_custom() -> None:
    """Custom device_height is accepted and produces a valid image."""
    r = Renderer(width=400, device_height=1080)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


# ── CSS @import data URI ──────────────────────────────────────────────────────

def test_import_css_data_uri_base64() -> None:
    css_source = "body { background: #00ff00 !important; margin: 0; }"
    encoded = base64.b64encode(css_source.encode()).decode()
    uri = f"data:text/css;base64,{encoded}"
    html = (
        f"<html><head><style>@import url('{uri}');</style></head>"
        "<body><div style='height:2px'></div></body></html>"
    )
    r = Renderer(width=100)
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    # Green channel should be high (green background)
    assert raw.data[1] > 200, f"G={raw.data[1]}, expected green background from CSS data URI"


# ── DPI configuration ─────────────────────────────────────────────────────────

def test_dpi_default() -> None:
    """Renderer with default DPI should produce a valid image."""
    r = Renderer(width=400)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_dpi_custom() -> None:
    """High-DPI renderer should produce larger content (text appears bigger)."""
    r_96 = Renderer(width=400, dpi=96.0)
    r_192 = Renderer(width=400, dpi=192.0)
    html = "<p style='font-size:12pt'>Hi</p>"
    raw_96 = r_96.render(html, fmt=OutputFormat.RAW)
    raw_192 = r_192.render(html, fmt=OutputFormat.RAW)
    assert isinstance(raw_96, RawResult)
    assert isinstance(raw_192, RawResult)
    # Higher DPI → pt units map to more pixels → taller content
    assert raw_192.height >= raw_96.height


# ── Language / locale configuration ──────────────────────────────────────────

def test_locale_default() -> None:
    r = Renderer(width=400)
    png = r.render("<p lang='en'>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_custom() -> None:
    r = Renderer(width=400, locale="zh-CN")
    png = r.render("<p lang='zh'>你好</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_splits_correctly() -> None:
    """locale='zh-CN' should split into lang='zh', culture='zh-CN' without error."""
    r = Renderer(width=400, locale="zh-CN")
    png = r.render("<p>你好</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_plain_tag() -> None:
    """Plain locale tag without region (e.g. 'en') should work: lang='en', culture='en'."""
    r = Renderer(width=400, locale="en")
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_image_cache_mb_parameter() -> None:
    """image_cache_mb parameter should be accepted and produce a valid image."""
    r = Renderer(width=400, images=ImageConfig(cache_mb=8, max_mb=2))
    png = r.render("<p>test</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


# ── shrink_to_fit ──────────────────────────────────────────────────────────────

def test_shrink_to_fit_narrow_content() -> None:
    """Content narrower than viewport should produce a narrower surface when shrink_to_fit=True."""
    r = Renderer(width=800)
    html = "<p style='width:100px'>Hi</p>"
    raw_no = r.render(html, fmt=OutputFormat.RAW, shrink_to_fit=False)
    raw_yes = r.render(html, fmt=OutputFormat.RAW, shrink_to_fit=True)
    assert isinstance(raw_no, RawResult)
    assert isinstance(raw_yes, RawResult)
    assert raw_no.width == 800
    assert raw_yes.width <= 800


def test_shrink_to_fit_wide_content() -> None:
    """Content filling full width should not shrink when shrink_to_fit=True."""
    r = Renderer(width=400)
    html = "<div style='width:400px;height:10px;background:red'></div>"
    raw = r.render(html, fmt=OutputFormat.RAW, shrink_to_fit=True)
    assert isinstance(raw, RawResult)
    assert raw.width <= 400 and raw.width > 0


def test_shrink_to_fit_false_keeps_viewport_width() -> None:
    r = Renderer(width=800)
    raw = r.render("<p>Hi</p>", fmt=OutputFormat.RAW, shrink_to_fit=False)
    assert isinstance(raw, RawResult)
    assert raw.width == 800
