# tests/test_fonts.py
import pathlib
import shutil

import pylitehtml
from pylitehtml import Renderer, OutputFormat, RawResult

FONTS_DIR = pathlib.Path(pylitehtml.__file__ or "").parent / "fonts"


def test_bundled_noto_sans() -> None:
    r = Renderer(width=400, default_font="Noto Sans")
    png = r.render("<p>Latin ABC 123</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_bundled_dejavusans() -> None:
    r = Renderer(width=400, default_font="DejaVu Sans")
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
    r = Renderer(width=400, extra_fonts=[str(dst)], default_font="DejaVu Sans")
    png = r.render("<p>Extra font</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_font_size_affects_height() -> None:
    big = Renderer(width=400, default_font_size=32)
    small = Renderer(width=400, default_font_size=8)
    raw_big = big.render("<p>X</p>", fmt=OutputFormat.RAW)
    raw_small = small.render("<p>X</p>", fmt=OutputFormat.RAW)
    assert isinstance(raw_big, RawResult)
    assert isinstance(raw_small, RawResult)
    assert raw_big.height >= raw_small.height


def test_text_decoration() -> None:
    """Underline/strikethrough must not crash the renderer."""
    r = Renderer(width=400)
    html = "<p style='text-decoration:underline'>underline</p>"
    png = r.render(html)
    assert isinstance(png, bytes)
    assert len(png) > 0
    html2 = "<p style='text-decoration:line-through'>strike</p>"
    png2 = r.render(html2)
    assert isinstance(png2, bytes)
    assert len(png2) > 0
