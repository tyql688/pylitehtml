# tests/test_fonts.py
import shutil, pathlib
import pylitehtml
from pylitehtml import Renderer, OutputFormat

FONTS_DIR = pathlib.Path(pylitehtml.__file__ or "").parent / "fonts"

def test_bundled_noto_sans():
    r = Renderer(width=400, default_font="Noto Sans")
    assert len(r.render("<p>Latin ABC 123</p>")) > 0

def test_bundled_dejavusans():
    r = Renderer(width=400, default_font="DejaVu Sans")
    assert len(r.render("<p>DejaVu text</p>")) > 0

def test_cjk_text():
    r = Renderer(width=400)
    assert len(r.render("<p>中文测试 日本語</p>")) > 0

def test_extra_fonts(tmp_path):
    dst = tmp_path / "Copy.ttf"
    shutil.copy(FONTS_DIR / "DejaVuSans.ttf", dst)
    r = Renderer(width=400, extra_fonts=[str(dst)], default_font="DejaVu Sans")
    assert len(r.render("<p>Extra font</p>")) > 0

def test_font_size_affects_height():
    big = Renderer(width=400, default_font_size=32)
    small = Renderer(width=400, default_font_size=8)
    raw_big   = big.render("<p>X</p>", fmt=OutputFormat.RAW)
    raw_small = small.render("<p>X</p>", fmt=OutputFormat.RAW)
    assert raw_big.height >= raw_small.height

def test_text_decoration():
    """Underline/strikethrough must not crash the renderer."""
    r = Renderer(width=400)
    html = "<p style='text-decoration:underline'>underline</p>"
    assert len(r.render(html)) > 0
    html2 = "<p style='text-decoration:line-through'>strike</p>"
    assert len(r.render(html2)) > 0
