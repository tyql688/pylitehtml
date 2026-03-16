"""Tests for async rendering interface."""
import asyncio

import pytest
import pylitehtml
from pylitehtml import Renderer, RawResult

SIMPLE = "<html><body><p>Hello</p></body></html>"


@pytest.mark.asyncio
async def test_renderer_render_async_png() -> None:
    r = Renderer(width=400)
    png = await r.render_async(SIMPLE)
    assert isinstance(png, bytes)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.asyncio
async def test_renderer_render_async_fmt_string() -> None:
    r = Renderer(width=400)
    jpg = await r.render_async(SIMPLE, fmt="jpeg", quality=80)
    assert isinstance(jpg, bytes)
    assert jpg[:2] == b'\xff\xd8'


@pytest.mark.asyncio
async def test_renderer_render_async_raw() -> None:
    r = Renderer(width=400)
    raw = await r.render_async(SIMPLE, fmt="raw")
    assert isinstance(raw, RawResult)
    assert raw.width == 400


@pytest.mark.asyncio
async def test_module_render_async() -> None:
    png = await pylitehtml.render_async(SIMPLE, width=400)
    assert isinstance(png, bytes)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.asyncio
async def test_concurrent_async_renders() -> None:
    r = Renderer(width=400)
    results = await asyncio.gather(*[r.render_async(SIMPLE) for _ in range(10)])
    assert all(isinstance(b, bytes) and b[:8] == b'\x89PNG\r\n\x1a\n' for b in results)
