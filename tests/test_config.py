"""Renderer configuration: device_height, DPI, locale, image cache sizing."""

from pylitehtml import ImageConfig, OutputFormat, RawResult, Renderer

# ── device_height ─────────────────────────────────────────────────────────────


def test_device_height_default() -> None:
    """Renderer with default device_height should produce a valid image."""
    r = Renderer(width=400)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_device_height_custom() -> None:
    """Custom device_height is accepted and produces a valid image."""
    r = Renderer(width=400, device_height=1080)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


# ── DPI configuration ─────────────────────────────────────────────────────────


def test_dpi_default() -> None:
    """Renderer with default DPI should produce a valid image."""
    r = Renderer(width=400)
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_dpi_custom() -> None:
    """High-DPI renderer should produce larger content (text appears bigger)."""
    r_96 = Renderer(width=400, dpi=96.0)
    r_192 = Renderer(width=400, dpi=192.0)
    html = "<p style='font-size:12pt'>Hi</p>"
    raw_96 = r_96.render(html, fmt=OutputFormat.RAW)
    raw_192 = r_192.render(html, fmt=OutputFormat.RAW)
    assert isinstance(raw_96, RawResult)
    assert isinstance(raw_192, RawResult)
    # Higher DPI → pt units map to more pixels → taller content
    assert raw_192.height >= raw_96.height


# ── Language / locale configuration ──────────────────────────────────────────


def test_locale_default() -> None:
    r = Renderer(width=400)
    png = r.render("<p lang='en'>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_custom() -> None:
    r = Renderer(width=400, locale="zh-CN")
    png = r.render("<p lang='zh'>你好</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_splits_correctly() -> None:
    """locale='zh-CN' should split into lang='zh', culture='zh-CN' without error."""
    r = Renderer(width=400, locale="zh-CN")
    png = r.render("<p>你好</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_locale_plain_tag() -> None:
    """Plain locale tag without region (e.g. 'en') should work: lang='en', culture='en'."""
    r = Renderer(width=400, locale="en")
    png = r.render("<p>Hello</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0


# ── Image cache sizing ────────────────────────────────────────────────────────


def test_image_cache_mb_parameter() -> None:
    """image_cache_mb parameter should be accepted and produce a valid image."""
    r = Renderer(width=400, images=ImageConfig(cache_mb=8, max_mb=2))
    png = r.render("<p>test</p>")
    assert isinstance(png, bytes)
    assert len(png) > 0
