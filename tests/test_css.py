# tests/test_css.py
import pathlib, pytest
from pylitehtml import Renderer, OutputFormat

ASSETS = pathlib.Path(__file__).parent / "assets"

@pytest.fixture(autouse=True, scope="session")
def create_css_assets():
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "style.css").write_text("body { background: #0000ff !important; }")

def test_inline_style_green():
    r = Renderer(width=100)
    raw = r.render("<html><body style='background:#00ff00;margin:0'>"
                   "<div style='height:2px'></div></body></html>",
                   fmt=OutputFormat.RAW, height=2)
    assert raw.data[1] > 200, "G channel should be high (green)"

def test_link_with_base_url():
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>CSS</p></body></html>'
    png = r.render(html, base_url=f"file://{ASSETS}/index.html")
    assert len(png) > 0

def test_no_base_url_link_ignored():
    r = Renderer(width=400)
    html = '<html><head><link rel="stylesheet" href="style.css"></head><body><p>no css</p></body></html>'
    assert len(r.render(html)) > 0  # no raise

def test_style_block_always_works():
    r = Renderer(width=100)
    raw = r.render("<html><head><style>body{background:#00ff00;margin:0}</style></head>"
                   "<body><div style='height:2px'></div></body></html>",
                   fmt=OutputFormat.RAW, height=2)
    assert raw.data[1] > 200
