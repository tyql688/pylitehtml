"""Exhaustive tests for the core lightweight HTML → image pipeline."""

import pytest
from _helpers import PNG_SIG, has_dark, pixel, to_array, to_image

import pylitehtml
from pylitehtml import (
    ImageConfig,
    OutputFormat,
    RawResult,
    html_to_image,
    html_to_png,
    wrap_html,
)


# ── output formats ───────────────────────────────────────────────────────────
def test_png_output() -> None:
    out = html_to_png("<h1>Hello</h1>", width=400)
    assert isinstance(out, bytes) and out[:8] == PNG_SIG


def test_jpeg_output() -> None:
    out = html_to_png("<h1>Hello</h1>", width=400, fmt="jpeg", quality=80)
    assert isinstance(out, bytes) and out[:2] == b"\xff\xd8"


def test_raw_output() -> None:
    out = html_to_image("<p>x</p>", width=200, fmt="raw")
    assert isinstance(out, RawResult)
    assert out.width > 0 and out.height > 0
    assert len(out.data) == out.width * out.height * 4


# ── wrapping ─────────────────────────────────────────────────────────────────
def test_fragment_is_wrapped_with_default_css() -> None:
    # h1 in the default stylesheet is large/bold → produces dark glyph pixels.
    im = to_image(html_to_image("<h1>Title</h1>", width=400, fmt="raw"))
    assert has_dark(im)


def test_full_document_rendered_verbatim() -> None:
    doc = "<html><body style='margin:0;background:#00ff00'>x</body></html>"
    im = to_image(html_to_image(doc, width=120, fmt="raw", shrink_to_fit=False))
    assert pixel(im, 2, 2)[:3] == (0, 255, 0)  # our default body bg NOT applied


def test_wrap_true_forces_wrapping() -> None:
    out = html_to_png("<html><body>x</body></html>", width=200, wrap=True)
    assert out[:8] == PNG_SIG


def test_wrap_false_renders_fragment_unstyled() -> None:
    # Without wrapping, the default white bg/padding is gone; a bare fragment
    # still renders (litehtml supplies a default UA style).
    out = html_to_png("<p>x</p>", width=200, wrap=False)
    assert out[:8] == PNG_SIG


def test_extra_css_overrides_default() -> None:
    im = to_image(
        html_to_image(
            "<p>x</p>",
            width=120,
            fmt="raw",
            shrink_to_fit=False,
            extra_css="body{background:#ff0000;padding:0}",
        )
    )
    assert pixel(im, 2, 2)[:3] == (255, 0, 0)


# ── scale / dimensions ───────────────────────────────────────────────────────
def test_scale_multiplies_width() -> None:
    a = html_to_image("<p>hi</p>", width=200, scale=1, fmt="raw", shrink_to_fit=False)
    b = html_to_image("<p>hi</p>", width=200, scale=2, fmt="raw", shrink_to_fit=False)
    assert isinstance(a, RawResult) and isinstance(b, RawResult)
    assert a.width == 200 and b.width == 400


def test_scale_multiplies_fixed_height() -> None:
    out = html_to_image("<p>x</p>", width=200, scale=2, height=100, fmt="raw", shrink_to_fit=False)
    assert isinstance(out, RawResult) and out.height == 200


def test_scale_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        html_to_png("<p>x</p>", width=200, scale=0)


def test_shrink_to_fit_never_widens() -> None:
    # shrink_to_fit can only reduce the canvas to the content's right edge, so a
    # shrunk render is never wider than the fixed-width one.
    fixed = html_to_image("<p>hi</p>", width=2000, fmt="raw", shrink_to_fit=False)
    shrunk = html_to_image("<p>hi</p>", width=2000, fmt="raw", shrink_to_fit=True)
    assert isinstance(fixed, RawResult) and isinstance(shrunk, RawResult)
    assert fixed.width == 2000
    assert shrunk.width <= fixed.width


# ── content coverage (smoke: must render, must not crash) ────────────────────
@pytest.mark.parametrize(
    "html",
    [
        "<table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>",
        "<div style='display:flex'><div style='flex:1'>L</div><div style='flex:1'>R</div></div>",
        "<div style='background:linear-gradient(90deg,#f00,#00f);height:40px'></div>",
        "<ul><li>a<ul><li>b</li></ul></li></ul>",
        "<blockquote>q</blockquote>",
        "<pre><code>code &lt;x&gt;</code></pre>",
        "<div style='float:left;width:50%'>L</div><div style='float:right;width:50%'>R</div>",
        "<p style='border:2px solid #000;border-radius:8px;padding:8px'>boxed</p>",
        "<dl><dt>term</dt><dd>definition</dd></dl>",
        "<p>x<sup>2</sup> and H<sub>2</sub>O and <mark>hi</mark> <kbd>Esc</kbd></p>",
        "<span style='display:inline-block;width:40px;height:40px;background:#000'></span>",
        "<ol start='5'><li>five</li><li>six</li></ol>",
        "<p style='text-align:center'>centered</p>",
        "<div style='background:#eee;padding:10px;margin:10px'>box model</div>",
    ],
)
def test_css_features_render(html: str) -> None:
    out = html_to_png(html, width=400)
    assert out[:8] == PNG_SIG and len(out) > 100


def test_cjk_renders() -> None:
    im = to_image(html_to_image("<p>你好，世界 ★ ✓</p>", width=300, fmt="raw", locale="zh-CN"))
    assert has_dark(im)


def test_data_uri_image() -> None:
    # 1x1 red PNG.
    uri = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    out = html_to_png(f'<img src="{uri}" width="20" height="20">', width=100)
    assert out[:8] == PNG_SIG


# ── extremes / adversarial (must not crash) ──────────────────────────────────
def test_empty_html() -> None:
    out = html_to_png("", width=200)
    assert out[:8] == PNG_SIG


def test_width_one() -> None:
    out = html_to_png("<p>narrow</p>", width=1, shrink_to_fit=False)
    assert out[:8] == PNG_SIG


def test_very_wide() -> None:
    out = html_to_png("<p>wide</p>", width=4000, shrink_to_fit=False)
    assert out[:8] == PNG_SIG


def test_huge_document() -> None:
    body = "".join(f"<p>paragraph number {i}</p>" for i in range(800))
    out = html_to_png(body, width=600)
    assert out[:8] == PNG_SIG


def test_deeply_nested() -> None:
    html = "<div>" * 200 + "deep" + "</div>" * 200
    out = html_to_png(html, width=400)
    assert out[:8] == PNG_SIG


@pytest.mark.parametrize(
    "html",
    [
        "<p>unclosed <b>bold",
        "<div><span></div></span>",
        "<<>><p>weird</p>",
        "<script>alert(1)</script><p>after</p>",  # inert: no JS engine
        "<p>& < > \" '</p>",
        "<img src='nonexistent.png'><p>still ok</p>",
        "</p></div></body>",
    ],
)
def test_malformed_html_does_not_crash(html: str) -> None:
    out = html_to_png(html, width=300)
    assert out[:8] == PNG_SIG


def test_deterministic() -> None:
    h = "<h1>Same</h1><p>input <strong>bold</strong></p><ul><li>a</li></ul>"
    assert html_to_png(h, width=400) == html_to_png(h, width=400)


# ── HTTP/HTTPS images (network failures must never crash a render) ───────────
def test_unreachable_https_image_skipped_gracefully() -> None:
    # Black-hole IP + short timeout: the image is skipped, the render succeeds.
    html = '<img src="https://10.255.255.1/x.png" width="40" height="40"><p>after</p>'
    out = html_to_png(html, width=200, images=ImageConfig(timeout_ms=300))
    assert out[:8] == PNG_SIG


def test_allow_http_false_skips_remote_image() -> None:
    html = '<img src="https://example.com/x.png" width="40" height="40"><p>ok</p>'
    out = html_to_png(html, width=200, images=ImageConfig(allow_http=False))
    assert out[:8] == PNG_SIG


@pytest.mark.parametrize(
    "uri",
    [
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ==",  # truncated JPEG
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA",  # truncated PNG
        "data:image/webp;base64,UklGRgggg",  # garbage WebP
        "data:image/jpeg;base64,!!!notbase64!!!",  # invalid base64
    ],
)
def test_malformed_image_skipped_gracefully(uri: str) -> None:
    """A corrupt/truncated image must be skipped, never crash the render
    (C++ decoders guard the cairo surface status before writing pixels)."""
    out = html_to_png(f'<img src="{uri}" width="20" height="20"><p>after</p>', width=120)
    assert out[:8] == PNG_SIG


@pytest.mark.parametrize(
    "url",
    [
        "https://httpbin.org/image/png",
        "http://httpbin.org/image/jpeg",
    ],
)
def test_remote_image_loads_if_network_available(url: str) -> None:
    """Real HTTP(S) fetch. Skips (does not fail) when the network is
    unavailable so the suite stays green offline."""
    html = f'<img src="{url}" width="120" height="120">'
    out = html_to_image(html, width=180, fmt="raw", images=ImageConfig(timeout_ms=4000))
    assert isinstance(out, RawResult)
    arr = to_array(out)
    colored = int(((arr[:, :, 0] < 250) | (arr[:, :, 1] < 250) | (arr[:, :, 2] < 250)).sum())
    if colored < 50:
        pytest.skip(f"network unavailable or {url} unreachable")
    assert colored >= 50


# ── helpers / API surface ────────────────────────────────────────────────────
def test_wrap_html_structure() -> None:
    doc = wrap_html("<p>body</p>", title="T")
    assert doc.startswith("<!DOCTYPE html>")
    assert "<title>T</title>" in doc
    assert "<p>body</p>" in doc
    assert "font-size" in doc  # default css present


def test_public_exports() -> None:
    for name in ("DEFAULT_CSS", "wrap_html", "html_to_png", "html_to_image"):
        assert hasattr(pylitehtml, name)
    # markdown is intentionally NOT a core export.
    assert "markdown_to_png" not in pylitehtml.__all__


def test_fmt_outputformat_enum_accepted() -> None:
    out = html_to_image("<p>x</p>", width=100, fmt=OutputFormat.PNG)
    assert isinstance(out, bytes) and out[:8] == PNG_SIG


def test_wrap_html_escapes_title() -> None:
    doc = wrap_html("<p>x</p>", title="</title><script>x</script>")
    assert "<script>" not in doc
    assert "&lt;/title&gt;" in doc
