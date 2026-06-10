import concurrent.futures
import hashlib
import pathlib

from PIL import Image

from pylitehtml import ImageConfig, RawResult, Renderer

HTMLS = [
    (
        f"<html><body style='background:#{i * 7 % 256:02x}{i * 13 % 256:02x}{i * 17 % 256:02x}'>"
        f"<h1>Item {i}</h1><p>Para {i}</p></body></html>"
    )
    for i in range(50)
]


def test_concurrent_no_crash() -> None:
    r = Renderer(width=400)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(r.render, HTMLS))
    assert len(results) == 50
    assert all(isinstance(b, bytes) and b[:8] == b"\x89PNG\r\n\x1a\n" for b in results)


def test_concurrent_deterministic() -> None:
    r = Renderer(width=400)
    html = HTMLS[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:

        def render_one(_x: int) -> bytes | RawResult:
            return r.render(html)

        results = list(pool.map(render_one, range(16)))
    digests = {hashlib.md5(x).hexdigest() for x in results if isinstance(x, bytes)}
    assert len(digests) == 1, f"Non-deterministic: {len(digests)} unique outputs"


def test_concurrent_image_eviction_no_crash(tmp_path: pathlib.Path) -> None:
    """Shared cache + tiny budget forces eviction while other threads still
    hold surfaces. The reference-counted get() must keep them alive (no UAF)."""
    pages = []
    for i in range(8):
        Image.new("RGBA", (80, 80), (i * 30 % 256, 0, 0, 255)).save(tmp_path / f"img{i}.png")
        page = tmp_path / f"page{i}.html"
        page.write_text(
            f'<body style="margin:0"><img src="img{i}.png" width="80" height="80"></body>'
        )
        pages.append(page)

    # ~31 KB cache: a single 80x80 surface fits, two do not → eviction churns.
    r = Renderer(width=120, images=ImageConfig(cache_mb=0.03))
    work = pages * 20
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda p: r.render_file(p), work))
    assert len(results) == len(work)
    assert all(isinstance(b, bytes) and len(b) > 0 for b in results)
