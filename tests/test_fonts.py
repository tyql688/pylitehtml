import pathlib
import shutil

import pytest
from _helpers import dark_pixels, to_image

import pylitehtml
from pylitehtml import FontConfig, OutputFormat, RawResult, Renderer

FONTS_DIR = pathlib.Path(pylitehtml.__file__ or "").parent / "fonts"


def test_bundled_noto_sans() -> None:
    r = Renderer(width=400, fonts=FontConfig(default="Noto Sans"))
    png = r.render("<p>Latin ABC 123</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_bundled_dejavusans() -> None:
    r = Renderer(width=400, fonts=FontConfig(default="DejaVu Sans"))
    png = r.render("<p>DejaVu text</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_cjk_text() -> None:
    r = Renderer(width=400)
    png = r.render("<p>中文测试 日本語</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_extra_fonts(tmp_path: pathlib.Path) -> None:
    dst = tmp_path / "Copy.ttf"
    _ = shutil.copy(FONTS_DIR / "DejaVuSans.ttf", dst)
    r = Renderer(width=400, fonts=FontConfig(extra=[str(dst)], default="DejaVu Sans"))
    png = r.render("<p>Extra font</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_font_size_affects_height() -> None:
    big = Renderer(width=400, fonts=FontConfig(size=32))
    small = Renderer(width=400, fonts=FontConfig(size=8))
    raw_big = big.render("<p>X</p>", fmt=OutputFormat.RAW)
    raw_small = small.render("<p>X</p>", fmt=OutputFormat.RAW)
    assert isinstance(raw_big, RawResult)
    assert isinstance(raw_small, RawResult)
    assert raw_big.height >= raw_small.height


def test_text_decoration() -> None:
    r = Renderer(width=400)
    html = "<p style='text-decoration:underline'>underline</p>"
    png = r.render(html)
    assert isinstance(png, bytes)
    assert len(png) > 0
    html2 = "<p style='text-decoration:line-through'>strike</p>"
    png2 = r.render(html2)
    assert isinstance(png2, bytes)
    assert len(png2) > 0


# ── Generic font-family aliases ───────────────────────────────────────────────


@pytest.mark.parametrize("family", ["sans-serif", "serif", "monospace"])
def test_generic_font_families_render(family: str) -> None:
    """Generic CSS families map to bundled fonts and draw real glyphs."""
    r = Renderer(width=300)
    html = f'<body style="margin:0;font-family:{family};font-size:40px;color:#000">Agq</body>'
    im = to_image(r.render(html, fmt="raw"))
    assert dark_pixels(im) > 0, f"{family}: no glyphs drawn"


# ── Real x-height drives the `ex` unit ────────────────────────────────────────


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


# ── text-decoration draws real ink ────────────────────────────────────────────


def test_underline_adds_ink() -> None:
    def dark(decoration: str) -> int:
        html = (
            '<body style="margin:0;font-size:30px;color:#000">'
            f'<span style="text-decoration:{decoration}">WWWW</span></body>'
        )
        im = to_image(Renderer(width=300).render(html, fmt="raw"))
        return dark_pixels(im)

    assert dark("underline") > dark("none")
