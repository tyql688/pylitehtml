# tests/test_images.py
import time, pathlib, pytest
from PIL import Image
from pylitehtml import Renderer, OutputFormat

ASSETS = pathlib.Path(__file__).parent / "assets"

@pytest.fixture(autouse=True, scope="session")
def create_assets():
    ASSETS.mkdir(exist_ok=True)
    Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(ASSETS / "red.png")
    Image.new("RGB",  (10, 10), (0, 0, 255)).save(ASSETS / "blue.jpg")

def test_local_png():
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "red.png"}" width="10" height="10">'
    assert len(r.render(html)) > 0

def test_local_jpeg():
    r = Renderer(width=200)
    html = f'<img src="{ASSETS / "blue.jpg"}" width="10" height="10">'
    assert len(r.render(html)) > 0

def test_allow_http_false_skips_image():
    r = Renderer(width=200, allow_http_images=False)
    html = '<img src="http://example.com/x.png" width="10" height="10">'
    assert len(r.render(html)) > 0  # no raise, image skipped

def test_http_timeout_respected():
    r = Renderer(width=200, image_timeout_ms=200)
    html = '<img src="http://10.255.255.1/x.png" width="10" height="10">'
    start = time.monotonic()
    r.render(html)
    assert time.monotonic() - start < 3.0
