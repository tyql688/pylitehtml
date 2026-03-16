# tests/test_css.py
import pathlib

import pytest
from pylitehtml import Renderer, OutputFormat, RawResult

ASSETS = pathlib.Path(__file__).parent / "assets"


@pytest.fixture(autouse=True, scope="session")
def create_css_assets() -> None:
    ASSETS.mkdir(exist_ok=True)
    _ = (ASSETS / "style.css").write_text("body { background: #0000ff !important; }")


def test_inline_style_green() -> None:
    r = Renderer(width=100)
    html = ("<html><body style='background:#00ff00;margin:0'>"
            "<div style='height:2px'></div></body></html>")
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200, "G channel should be high (green)"


def test_link_with_base_url() -> None:
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>CSS</p></body></html>'
    png = r.render(html, base_url=f"file://{ASSETS}/index.html")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_no_base_url_link_ignored() -> None:
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>no css</p></body></html>'
    result = r.render(html)
    assert isinstance(result, bytes)
    assert len(result) > 0  # no raise


def test_style_block_always_works() -> None:
    r = Renderer(width=100)
    html = ("<html><head><style>body{background:#00ff00;margin:0}</style></head>"
            "<body><div style='height:2px'></div></body></html>")
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200
