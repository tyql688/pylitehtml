# tests/test_images.py
import pathlib
import time

import pytest
from PIL import Image
from pylitehtml import Renderer, ImageConfig

ASSETS = pathlib.Path(__file__).parent / "assets"


@pytest.fixture(autouse=True, scope="session")
def create_assets() -> None:
    ASSETS.mkdir(exist_ok=True)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(ASSETS / "red.png")
    Image.new("RGB",  (10, 10), (0, 0, 255)).save(ASSETS / "blue.jpg")


def test_local_png() -> None:
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "red.png"}" width="10" height="10">'
    png = r.render(html)
    assert isinstance(png, bytes)
    assert len(png) > 0


def test_local_jpeg() -> None:
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "blue.jpg"}" width="10" height="10">'
    jpg = r.render(html)
    assert isinstance(jpg, bytes)
    assert len(jpg) > 0


def test_allow_http_false_skips_image() -> None:
    r = Renderer(width=200, images=ImageConfig(allow_http=False))
    html = '<img src="http://example.com/x.png" width="10" height="10">'
    result = r.render(html)
    assert isinstance(result, bytes)
    assert len(result) > 0  # no raise, image skipped


def test_http_timeout_respected() -> None:
    r = Renderer(width=200, images=ImageConfig(timeout_ms=200))
    html = '<img src="http://10.255.255.1/x.png" width="10" height="10">'
    start = time.monotonic()
    _ = r.render(html)
    assert time.monotonic() - start < 3.0
