"""Tests for the Jinja2 templating path of render_file (and the module-level
render_file). Templates live on disk; relative CSS/images resolve from the
template's directory."""

import pathlib

from _helpers import is_png as _is_png
from _helpers import to_image

import pylitehtml
from pylitehtml import RawResult, Renderer


def _write(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_plain_file_no_template(tmp_path: pathlib.Path) -> None:
    page = _write(tmp_path, "a.html", "<h1>Plain</h1>")
    assert _is_png(Renderer(width=300).render_file(page))


def test_variable_substitution(tmp_path: pathlib.Path) -> None:
    page = _write(tmp_path, "t.html", "<h1>{{ title }}</h1>")
    assert _is_png(Renderer(width=300).render_file(page, title="Hello"))


def test_loop_and_conditional(tmp_path: pathlib.Path) -> None:
    page = _write(
        tmp_path,
        "list.html",
        "<ul>{% for it in items %}<li>{{ it }}{% if loop.last %}!{% endif %}</li>{% endfor %}</ul>",
    )
    assert _is_png(Renderer(width=300).render_file(page, items=["a", "b", "c"]))


def test_autoescape_escapes_html_in_data(tmp_path: pathlib.Path) -> None:
    """The headline bug: without autoescape, ``{{ x }}`` with HTML breaks the
    document / injects. The .html template must escape it."""
    page = _write(tmp_path, "x.html", "<p>{{ value }}</p>")
    html = pylitehtml._render_template(page, {"value": "<script>alert(1)</script> & <b>"})
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html


def test_autoescape_render_succeeds(tmp_path: pathlib.Path) -> None:
    page = _write(tmp_path, "x.html", "<p>{{ value }}</p>")
    assert _is_png(Renderer(width=300).render_file(page, value="<b>&'\"unsafe"))


def test_include_and_inheritance(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, "base.html", "<body><h1>Base</h1>{% block body %}{% endblock %}</body>")
    _write(tmp_path, "partial.html", "<p>partial</p>")
    page = _write(
        tmp_path,
        "page.html",
        '{% extends "base.html" %}{% block body %}{% include "partial.html" %}'
        "<span>{{ name }}</span>{% endblock %}",
    )
    assert _is_png(Renderer(width=300).render_file(page, name="X"))


def test_jinja_filters(tmp_path: pathlib.Path) -> None:
    page = _write(tmp_path, "f.html", "<p>{{ price | round(2) }} / {{ name | upper }}</p>")
    assert _is_png(Renderer(width=300).render_file(page, price=3.14159, name="abc"))


def test_module_level_render_file_template(tmp_path: pathlib.Path) -> None:
    page = _write(tmp_path, "m.html", "<h1>{{ t }}</h1>")
    assert _is_png(pylitehtml.render_file(page, 300, t="hi"))


def test_relative_css_resolved_in_template(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, "s.css", "body{background:#00ff00;margin:0}")
    page = _write(
        tmp_path,
        "p.html",
        '<html><head><link rel="stylesheet" href="s.css"></head><body>{{ msg }}</body></html>',
    )
    out = Renderer(width=80).render_file(page, msg="x", fmt="raw", shrink_to_fit=False)
    assert isinstance(out, RawResult)
    im = to_image(out)
    px = im.getpixel((2, 2))
    assert isinstance(px, tuple) and px[:3] == (0, 255, 0)  # external CSS applied


def test_env_is_cached(tmp_path: pathlib.Path) -> None:
    from pylitehtml._jinja import jinja_env

    _write(tmp_path, "a.html", "<p>{{ a }}</p>")
    assert jinja_env(str(tmp_path)) is jinja_env(str(tmp_path))
