# tests/test_render_file.py
"""Tests for render_file: local HTML files and Jinja2 templates."""
import pathlib

import pylitehtml
from pylitehtml import Renderer, OutputFormat, RawResult

TEMPLATES = pathlib.Path(__file__).parent / "assets" / "templates"


def test_render_file_plain_html() -> None:
    """Plain HTML file with <link> to external CSS should render."""
    r = Renderer(width=400)
    png = r.render_file(TEMPLATES / "plain.html")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_file_resolves_css() -> None:
    """External CSS (green background) should be loaded from file directory."""
    r = Renderer(width=100)
    raw = r.render_file(TEMPLATES / "plain.html", fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200, f"G={raw.data[1]}, expected green from style.css"


def test_render_file_jinja2_template() -> None:
    """Jinja2 template with variables should render correctly."""
    r = Renderer(width=400)
    png = r.render_file(
        TEMPLATES / "template.html",
        title="订单",
        items=[{"name": "苹果", "price": 5}, {"name": "香蕉", "price": 3}],
    )
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_render_file_jinja2_resolves_css() -> None:
    """Jinja2 template should also resolve external CSS from its directory."""
    r = Renderer(width=100)
    raw = r.render_file(
        TEMPLATES / "template.html",
        fmt=OutputFormat.RAW,
        height=2,
        title="Test",
        items=[],
    )
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200, f"G={raw.data[1]}, expected green from style.css"


def test_render_file_jpeg() -> None:
    """render_file should support JPEG output."""
    r = Renderer(width=400)
    jpg = r.render_file(TEMPLATES / "plain.html", fmt="jpeg", quality=80)
    assert isinstance(jpg, bytes)
    assert jpg[:2] == b"\xff\xd8"


def test_module_render_file() -> None:
    """Module-level render_file convenience function."""
    png = pylitehtml.render_file(TEMPLATES / "plain.html", width=400)
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_module_render_file_with_template() -> None:
    """Module-level render_file with Jinja2 template data."""
    png = pylitehtml.render_file(
        TEMPLATES / "template.html",
        width=400,
        title="Hello",
        items=[{"name": "Test", "price": 1}],
    )
    assert isinstance(png, bytes)
    assert len(png) > 0
