"""Tests for async rendering via asyncio.to_thread."""
import asyncio

import pytest
from pylitehtml import Renderer, RawResult

SIMPLE = "<html><body><p>Hello</p></body></html>"


@pytest.mark.asyncio
async def test_async_render_png() -> None:
    r = Renderer(width=400)
    png = await asyncio.to_thread(r.render, SIMPLE)
    assert isinstance(png, bytes)
    assert png[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.asyncio
async def test_async_render_fmt_string() -> None:
    r = Renderer(width=400)
    jpg = await asyncio.to_thread(r.render, SIMPLE, fmt="jpeg", quality=80)
    assert isinstance(jpg, bytes)
    assert jpg[:2] == b'\xff\xd8'


@pytest.mark.asyncio
async def test_async_render_raw() -> None:
    r = Renderer(width=400)
    raw = await asyncio.to_thread(r.render, SIMPLE, fmt="raw")
    assert isinstance(raw, RawResult)
    assert raw.width == 400


@pytest.mark.asyncio
async def test_concurrent_async_renders() -> None:
    r = Renderer(width=400)
    results = await asyncio.gather(
        *[asyncio.to_thread(r.render, SIMPLE) for _ in range(10)]
    )
    assert all(isinstance(b, bytes) and b[:8] == b'\x89PNG\r\n\x1a\n' for b in results)
