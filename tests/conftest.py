# tests/conftest.py
import pytest
from pylitehtml import Renderer, OutputFormat

SIMPLE_HTML = """<html><style>
  body { font-family: "Noto Sans", sans-serif; background: #fff; margin: 0; padding: 20px; }
  h1 { color: #e00; font-size: 32px; }
  p  { color: #333; font-size: 16px; }
</style><body><h1>Hello pylitehtml</h1><p>Test paragraph.</p></body></html>"""

FLEX_HTML = """<html><style>
  .row { display: flex; gap: 10px; padding: 10px; }
  .box { width: 100px; height: 100px; background: #4af; border-radius: 8px; }
</style><body><div class="row">
  <div class="box"></div>
  <div class="box" style="background:#f4a"></div>
  <div class="box" style="background:#af4"></div>
</div></body></html>"""

@pytest.fixture(scope="session")
def renderer():
    return Renderer(width=800)

@pytest.fixture
def simple_html():
    return SIMPLE_HTML
