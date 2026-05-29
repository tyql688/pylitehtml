"""Jinja2 templating helpers for render_file (kept out of __init__ for clarity)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2


@lru_cache(maxsize=8)
def jinja_env(template_dir: str) -> jinja2.Environment:
    """Cached per-directory Jinja2 environment.

    autoescape is ON for HTML/XML templates (so ``{{ user_value }}`` containing
    ``<`` / ``&`` is escaped, not injected). FileSystemLoader supports
    ``{% include %}`` / ``{% extends %}`` relative to the template's directory.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(["html", "htm", "xml", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(path: Path, data: dict[str, Any]) -> str:
    """Render the Jinja2 template at *path* with *data* → HTML string."""
    return jinja_env(str(path.parent)).get_template(path.name).render(**data)
