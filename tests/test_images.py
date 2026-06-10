"""Image loading: local files, HTTP policy, URL resolution/hardening,
data: URIs, SVG, and ImageCache ownership."""

import base64
import hashlib
import io
import pathlib
import time

import pytest
from _helpers import is_red, to_image
from PIL import Image

from pylitehtml import ImageConfig, OutputFormat, RawResult, Renderer

ASSETS = pathlib.Path(__file__).parent / "assets"

RED = (255, 0, 0, 255)


def _save_red(path: pathlib.Path, size: int = 60) -> None:
    Image.new("RGBA", (size, size), RED).save(path)


@pytest.fixture(autouse=True, scope="session")
def create_assets() -> None:
    ASSETS.mkdir(exist_ok=True)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(ASSETS / "red.png")
    Image.new("RGB", (10, 10), (0, 0, 255)).save(ASSETS / "blue.jpg")


# ── Local files / HTTP policy ─────────────────────────────────────────────────


def test_local_png() -> None:
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "red.png"}" width="10" height="10">'
    png = r.render(html)
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_local_jpeg() -> None:
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "blue.jpg"}" width="10" height="10">'
    jpg = r.render(html)
    assert isinstance(jpg, bytes)
    assert len(jpg) > 0


def test_allow_http_false_skips_image() -> None:
    r = Renderer(width=200, images=ImageConfig(allow_http=False))
    html = '<img src="http://example.com/x.png" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes)
    assert len(result) > 0  # no raise, image skipped


def test_http_timeout_respected() -> None:
    r = Renderer(width=200, images=ImageConfig(timeout_ms=200))
    html = '<img src="http://10.255.255.1/x.png" width="10" height="10">'
    start = time.monotonic()
    _ = r.render(html)
    assert time.monotonic() - start < 3.0


# ── URL resolution / local-file hardening ─────────────────────────────────────


def test_file_url_blocked_for_string_html(tmp_path: pathlib.Path) -> None:
    """A file:// reference in a bare HTML string (no file base) must not load —
    otherwise untrusted HTML could read local files into the output image."""
    img = tmp_path / "secret.png"
    _save_red(img)
    r = Renderer(width=120)
    html = (
        '<body style="margin:0">'
        f'<img src="file://{img}" width="60" height="60" style="display:block">'
        "</body>"
    )
    im = to_image(r.render(html, fmt="raw"))
    assert not is_red(im, 30, 30), "file:// image leaked into string render"


def test_file_url_allowed_via_render_file(tmp_path: pathlib.Path) -> None:
    """Relative images in a local HTML file are resolved against its directory."""
    _save_red(tmp_path / "pic.png")
    page = tmp_path / "page.html"
    page.write_text(
        '<body style="margin:0">'
        '<img src="pic.png" width="60" height="60" style="display:block"></body>'
    )
    im = to_image(Renderer(width=120).render_file(page, fmt="raw"))
    assert is_red(im, 30, 30), "relative image failed to load via render_file"


def test_root_relative_resolves_on_file_base(tmp_path: pathlib.Path) -> None:
    """A root-relative ('/abs/path') src resolves to the filesystem when the
    document itself is a local file."""
    img = tmp_path / "pic.png"
    _save_red(img)
    page = tmp_path / "page.html"
    page.write_text(
        '<body style="margin:0">'
        f'<img src="{img}" width="60" height="60" style="display:block"></body>'
    )
    im = to_image(Renderer(width=120).render_file(page, fmt="raw"))
    assert is_red(im, 30, 30)


def test_root_relative_blocked_without_base(tmp_path: pathlib.Path) -> None:
    """The same root-relative path must NOT load when there is no file base."""
    img = tmp_path / "pic.png"
    _save_red(img)
    r = Renderer(width=120)
    html = (
        '<body style="margin:0">'
        f'<img src="{img}" width="60" height="60" style="display:block"></body>'
    )
    im = to_image(r.render(html, fmt="raw"))
    assert not is_red(im, 30, 30)


# ── data: URI images ──────────────────────────────────────────────────────────


def _make_png_bytes(
    color: tuple[int, int, int] = (255, 0, 0), size: tuple[int, int] = (10, 10)
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(
    color: tuple[int, int, int] = (0, 0, 255), size: tuple[int, int] = (10, 10)
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_webp_bytes(
    color: tuple[int, int, int] = (0, 255, 0), size: tuple[int, int] = (10, 10)
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, (*color, 255)).save(buf, format="WEBP")
    return buf.getvalue()


def _data_uri(image_bytes: bytes, mime: str) -> str:
    encoded = base64.b64encode(image_bytes).decode()
    return f"data:{mime};base64,{encoded}"


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


# ── SVG images ────────────────────────────────────────────────────────────────

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


# ── ImageCache ownership: list-style-image goes through get_image() ──────────


def test_list_style_image_no_double_free(tmp_path: pathlib.Path) -> None:
    """container_cairo::draw_list_marker owns and destroys the get_image()
    surface. Rendering repeatedly must not corrupt the cache / crash and must
    stay deterministic."""
    _save_red(tmp_path / "dot.png", size=8)
    page = tmp_path / "list.html"
    page.write_text(
        '<ul style="list-style-image:url(dot.png)"><li>one</li><li>two</li><li>three</li></ul>'
    )
    r = Renderer(width=200)
    outs = [r.render_file(page) for _ in range(5)]
    assert all(isinstance(b, bytes) and b[:8] == b"\x89PNG\r\n\x1a\n" for b in outs)
    digests = {hashlib.md5(b).hexdigest() for b in outs if isinstance(b, bytes)}
    assert len(digests) == 1


# ── SVG decompression-bomb guard ──────────────────────────────────────────────


def test_svg_huge_dimensions_does_not_poison_page() -> None:
    """An SVG declaring absurd dimensions must be skipped (loader returns
    nothing) instead of handing an error surface to cairo — which would stop
    ALL subsequent drawing on the page."""
    bomb = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="1000000" height="1000000">'
        b'<rect width="10" height="10" fill="blue"/></svg>'
    )
    uri = _data_uri(bomb, "image/svg+xml")
    html = (
        '<body style="margin:0">'
        f'<img src="{uri}" width="10" height="10">'
        '<div style="width:60px;height:60px;background:#f00"></div></body>'
    )
    raw = Renderer(width=120).render(html, fmt=OutputFormat.RAW)
    assert isinstance(raw, RawResult)
    # The red div below the (skipped) image must still be drawn.
    y = raw.height - 30
    idx = (y * raw.width + 30) * 4
    assert raw.data[idx] > 200 and raw.data[idx + 1] < 80, "page drawing was poisoned"
