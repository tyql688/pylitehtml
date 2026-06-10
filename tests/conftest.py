import pytest

from pylitehtml import Renderer

SIMPLE_HTML = """<html><style>
  body { font-family: "Noto Sans", sans-serif; background: #fff; margin: 0; padding: 20px; }
  h1 { color: #e00; font-size: 32px; }
  p  { color: #333; font-size: 16px; }
</style><body><h1>Hello pylitehtml</h1><p>Test paragraph.</p></body></html>"""


@pytest.fixture(scope="session")
def renderer() -> Renderer:
    return Renderer(width=800)


@pytest.fixture
def simple_html() -> str:
    return SIMPLE_HTML
