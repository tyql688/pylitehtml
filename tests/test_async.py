"""Tests for async rendering interface."""
import asyncio
import pytest
import pylitehtml
from pylitehtml import Renderer, OutputFormat

SIMPLE = "<html><body><p>Hello</p></body></html>"


@pytest.mark.asyncio
async def test_renderer_render_async_png():
    r = Renderer(width=400)
    png = await r.render_async(SIMPLE)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.asyncio
async def test_renderer_render_async_fmt_string():
    r = Renderer(width=400)
    jpg = await r.render_async(SIMPLE, fmt="jpeg", quality=80)
    assert jpg[:2] == b'\xff\xd8'


@pytest.mark.asyncio
async def test_renderer_render_async_raw():
    r = Renderer(width=400)
    raw = await r.render_async(SIMPLE, fmt="raw")
    assert isinstance(raw, pylitehtml.RawResult)
    assert raw.width == 400


@pytest.mark.asyncio
async def test_module_render_async():
    png = await pylitehtml.render_async(SIMPLE, width=400)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.asyncio
async def test_concurrent_async_renders():
    r = Renderer(width=400)
    results = await asyncio.gather(*[r.render_async(SIMPLE) for _ in range(10)])
    assert all(b[:8] == b'\x89PNG\r\n\x1a\n' for b in results)
