import base64
import time

from pylitehtml import ImageConfig, OutputFormat, RawResult, Renderer


def test_inline_style_green() -> None:
    r = Renderer(width=100)
    html = (
        "<html><body style='background:#00ff00;margin:0'>"
        "<div style='height:2px'></div></body></html>"
    )
    raw = r.render(html, fmt=OutputFormat.RAW, height=2)
    assert isinstance(raw, RawResult)
    assert raw.data[1] > 200, "G channel should be high (green)"


def test_style_block_always_works() -> None:
    r = Renderer(width=100)
    html = (
        "<html><head><style>body{background:#00ff00;margin:0}</style></head>"
        "<body><div style='height:2px'></div></body></html>"
    )
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
