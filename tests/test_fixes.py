"""Regression tests for the round of fixes covering:

- file:// / root-relative URL resolution + local-file-access hardening
- ImageCache surface ownership (no double-free with list markers)
- ImageCache thread-safety under concurrent eviction
- HTTP timeout applied to <link> CSS fetches
- generic font-family aliases (sans-serif / serif / monospace) render
- real x-height drives the CSS `ex` unit
- text-decoration still draws after the baseline fix
"""

import concurrent.futures
import hashlib
import pathlib
import time

import pytest
from _helpers import dark_pixels, is_red, to_image
from PIL import Image

from pylitehtml import ImageConfig, Renderer

RED = (255, 0, 0, 255)


def _save_red(path: pathlib.Path, size: int = 60) -> None:
    Image.new("RGBA", (size, size), RED).save(path)


# ── URL resolution / local-file hardening ────────────────────────────────────
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


def test_concurrent_image_eviction_no_crash(tmp_path: pathlib.Path) -> None:
    """Shared cache + tiny budget forces eviction while other threads still
    hold surfaces. The reference-counted get() must keep them alive (no UAF)."""
    pages = []
    for i in range(8):
        Image.new("RGBA", (80, 80), (i * 30 % 256, 0, 0, 255)).save(tmp_path / f"img{i}.png")
        page = tmp_path / f"page{i}.html"
        page.write_text(
            f'<body style="margin:0"><img src="img{i}.png" width="80" height="80"></body>'
        )
        pages.append(page)

    # ~31 KB cache: a single 80x80 surface fits, two do not → eviction churns.
    r = Renderer(width=120, images=ImageConfig(cache_mb=0.03))
    work = pages * 20
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda p: r.render_file(p), work))
    assert len(results) == len(work)
    assert all(isinstance(b, bytes) and len(b) > 0 for b in results)


# ── HTTP timeout applied to CSS fetches ──────────────────────────────────────
def test_css_http_timeout_respected() -> None:
    """import_css must honour the configured timeout, not a hardcoded 5000ms.
    A short timeout against a black-hole IP should return well under the old
    default."""
    r = Renderer(width=200, images=ImageConfig(timeout_ms=200))
    html = (
        '<html><head><base href="http://10.255.255.1/">'
        '<link rel="stylesheet" href="x.css"></head>'
        "<body>hi</body></html>"
    )
    start = time.monotonic()
    _ = r.render(html)
    assert time.monotonic() - start < 3.0


# ── Font aliases ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("family", ["sans-serif", "serif", "monospace"])
def test_generic_font_families_render(family: str) -> None:
    """Generic CSS families map to bundled fonts and draw real glyphs."""
    r = Renderer(width=300)
    html = f'<body style="margin:0;font-family:{family};font-size:40px;color:#000">Agq</body>'
    im = to_image(r.render(html, fmt="raw"))
    assert dark_pixels(im) > 0, f"{family}: no glyphs drawn"


# ── Real x-height drives the `ex` unit ───────────────────────────────────────
def test_ex_unit_scales_with_font_size() -> None:
    """The `ex` unit is the font's x-height; a block sized in `ex` must grow
    with font-size now that x-height is measured rather than ascent/2."""

    def content_height(font_px: int) -> int:
        html = (
            f'<body style="margin:0"><div style="height:10ex;font-size:{font_px}px"></div></body>'
        )
        out = Renderer(width=100).render(html, fmt="raw")
        return out.height  # type: ignore[union-attr]

    assert content_height(40) > content_height(20)


# ── text-decoration still draws after the baseline fix ───────────────────────
def test_underline_adds_ink() -> None:
    def dark(decoration: str) -> int:
        html = (
            '<body style="margin:0;font-size:30px;color:#000">'
            f'<span style="text-decoration:{decoration}">WWWW</span></body>'
        )
        im = to_image(Renderer(width=300).render(html, fmt="raw"))
        return dark_pixels(im)

    assert dark("underline") > dark("none")
