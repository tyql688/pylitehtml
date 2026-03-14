# tests/test_thread_safety.py
import concurrent.futures, hashlib
from pylitehtml import Renderer, OutputFormat

HTMLS = [
    f"<html><body style='background:#{i*7%256:02x}{i*13%256:02x}{i*17%256:02x}'>"
    f"<h1>Item {i}</h1><p>Para {i}</p></body></html>"
    for i in range(50)
]

def test_concurrent_no_crash():
    r = Renderer(width=400)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(r.render, HTMLS))
    assert len(results) == 50
    assert all(b[:8] == b'\x89PNG\r\n\x1a\n' for b in results)

def test_concurrent_deterministic():
    r = Renderer(width=400)
    html = HTMLS[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: r.render(html), range(16)))
    digests = {hashlib.md5(x).hexdigest() for x in results}
    assert len(digests) == 1, f"Non-deterministic: {len(digests)} unique outputs"
