"""Pixel-level visual regression tests.

These assert on the actual rendered pixels (via RAW output), not just that a
render succeeded. The headline guard is mixed CJK/Latin **baseline alignment**:
litehtml emits mixed text as separate runs whose Pango layouts have different
top-to-baseline offsets, so naive drawing made CJK glyphs drift vertically
("飞"). draw_text aligns every run to a common baseline; these tests fail if
that regresses.
"""

from __future__ import annotations

import numpy as np
from _helpers import dark_mask as _dark_mask
from _helpers import to_array as _array

from pylitehtml import RawResult, html_to_image


def _glyph_bottom(mask: np.ndarray, x0: int, x1: int) -> int:
    rows = np.where(mask[:, x0:x1].any(axis=1))[0]
    assert rows.size, f"no ink found in columns [{x0}, {x1})"
    return int(rows.max())


# ── baseline alignment (the "飞了" fix) ───────────────────────────────────────
def _render_line(text: str, font_px: int = 100) -> np.ndarray:
    html = (
        f"<span style=\"font-family:'Noto Sans','Noto Sans SC';"
        f'font-size:{font_px}px;line-height:1;color:#000">{text}</span>'
    )
    out = html_to_image(
        html,
        width=900,
        fmt="raw",
        wrap=True,
        extra_css="body{margin:0;padding:0}",
        shrink_to_fit=False,
    )
    return _array(out)


def test_latin_cjk_share_baseline() -> None:
    """'H' (Latin cap, bottom on the baseline) and '中' (CJK) in the same line
    must sit on a common baseline.

    The old bug drew CJK runs *above* the Latin baseline (CJK bottom far higher
    than Latin → "飞"). Correct rendering keeps CJK at — or, per normal CJK
    metrics, slightly below — the Latin baseline, never above it.
    """
    font = 100
    arr = _render_line("H中", font_px=font)
    mask = _dark_mask(arr)
    cols = np.where(mask.any(axis=0))[0]
    x0, x1 = int(cols.min()), int(cols.max())
    mid = (x0 + x1) // 2
    h_bottom = _glyph_bottom(mask, x0, mid)
    cjk_bottom = _glyph_bottom(mask, mid, x1 + 1)
    offset = cjk_bottom - h_bottom
    # Regression guard: CJK must not fly up (offset clearly negative), and the
    # natural CJK descent below the Latin baseline stays modest (~10%).
    assert -0.04 * font <= offset <= 0.18 * font, (
        f"baseline misaligned: H bottom={h_bottom}, 中 bottom={cjk_bottom}, offset={offset}"
    )


def test_cjk_baseline_offset_is_stable_across_sizes() -> None:
    """The CJK-vs-Latin baseline offset must scale with font size (a fixed
    ratio), not jump around — proof the alignment is metric-driven."""
    ratios = []
    for font in (60, 100, 160):
        arr = _render_line("H中", font_px=font)
        mask = _dark_mask(arr)
        cols = np.where(mask.any(axis=0))[0]
        x0, x1 = int(cols.min()), int(cols.max())
        mid = (x0 + x1) // 2
        offset = _glyph_bottom(mask, mid, x1 + 1) - _glyph_bottom(mask, x0, mid)
        ratios.append(offset / font)
    assert max(ratios) - min(ratios) <= 0.03, f"offset ratio unstable: {ratios}"


def test_descenders_extend_below_baseline() -> None:
    """A line with descenders ('g','y') must reach lower than a caps-only line
    at the same top — proving glyphs are baseline-anchored, not box-anchored."""
    caps = _dark_mask(_render_line("HX", font_px=100))
    desc = _dark_mask(_render_line("gy", font_px=100))
    cols_c = np.where(caps.any(axis=0))[0]
    cols_d = np.where(desc.any(axis=0))[0]
    caps_bottom = _glyph_bottom(caps, int(cols_c.min()), int(cols_c.max()) + 1)
    desc_bottom = _glyph_bottom(desc, int(cols_d.min()), int(cols_d.max()) + 1)
    assert desc_bottom > caps_bottom


# ── colors / backgrounds / gradients ─────────────────────────────────────────
def test_background_color_applied() -> None:
    arr = _array(
        html_to_image(
            "<p>x</p>",
            width=120,
            fmt="raw",
            shrink_to_fit=False,
            extra_css="body{background:#3366cc;padding:0}",
        )
    )
    r, g, b = arr[2, 2, 0], arr[2, 2, 1], arr[2, 2, 2]
    assert (r, g, b) == (0x33, 0x66, 0xCC)


def test_text_color_applied() -> None:
    # Red text on white: ink pixels should be red-dominant.
    arr = _array(
        html_to_image(
            "<p style='color:#ff0000'>HHHH</p>",
            width=200,
            fmt="raw",
            shrink_to_fit=False,
        )
    )
    red_ink = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)
    assert red_ink.sum() > 20


def test_linear_gradient_varies_across_width() -> None:
    arr = _array(
        html_to_image(
            "<div style='height:40px;background:linear-gradient(90deg,#ff0000,#0000ff)'></div>",
            width=400,
            fmt="raw",
            wrap=False,
            shrink_to_fit=False,
        )
    )
    # Sample interior columns (edges may fall in the UA body margin).
    left = arr[20, 100, :3].astype(int)
    right = arr[20, 300, :3].astype(int)
    # 90deg gradient runs red (left) → blue (right).
    assert left[0] > right[0] and right[2] > left[2]


def test_table_borders_drawn() -> None:
    arr = _array(
        html_to_image(
            "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>",
            width=300,
            fmt="raw",
        )
    )
    # Border lines produce many non-white pixels arranged in the grid.
    assert _dark_mask(arr, thresh=230).sum() > 100


# ── determinism ───────────────────────────────────────────────────────────────
def test_pixel_identical_across_renders() -> None:
    a = html_to_image("<h1>Hi 你好</h1>", width=300, fmt="raw")
    b = html_to_image("<h1>Hi 你好</h1>", width=300, fmt="raw")
    assert isinstance(a, RawResult) and isinstance(b, RawResult)
    assert a.data == b.data
