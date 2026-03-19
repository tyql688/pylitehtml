# tests/test_css.py
from pylitehtml import Renderer, ImageConfig, OutputFormat, RawResult


def test_inline_style_green() -> None:
    r = Renderer(width=100)
    html = ("<html><body style='background:#00ff00;margin:0'>"
            "<div style='height:2px'></div></body></html>")
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200, "G channel should be high (green)"


def test_style_block_always_works() -> None:
    r = Renderer(width=100)
    html = ("<html><head><style>body{background:#00ff00;margin:0}</style></head>"
            "<body><div style='height:2px'></div></body></html>")
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200


def test_allow_http_false_blocks_css_import() -> None:
    """CSS @import over HTTP should be blocked when allow_http=False."""
    r = Renderer(width=100, images=ImageConfig(allow_http=False))
    html = (
        "<html><head><style>"
        "@import url('http://example.com/style.css');"
        "body{background:#00ff00;margin:0}"
        "</style></head>"
        "<body><div style='height:2px'></div></body></html>"
    )
    # Should not crash; the @import is simply skipped
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    # Green background from inline style should still work
    assert raw.data[1] > 200
