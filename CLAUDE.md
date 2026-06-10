# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

HTML+CSS → PNG/JPEG/RAW image renderer: a pybind11 C++ extension (`_core`) wrapping
[litehtml](third_party/litehtml) (submodule) + Cairo/Pango/FontConfig, with a thin Python layer
on top. No headless browser, no JavaScript execution. README is in Chinese and is the primary
user-facing doc.

## Commands

```bash
git clone --recursive …   # third_party/litehtml is a submodule; --recursive is required

# Build deps (macOS): brew install cairo pango fontconfig webp jpeg-turbo openssl@3 cmake ninja
# On macOS force Apple clang:
CC=/usr/bin/clang CXX=/usr/bin/clang++ uv pip install -e ".[dev]" --no-build-isolation --python .venv/bin/python
# (requires scikit-build-core + pybind11 installed first; --no-build-isolation is required)

.venv/bin/python -m pytest tests/ -q              # full suite
.venv/bin/python -m pytest tests/test_images.py -q -k svg   # single file / pattern

# Lint/format — CI pins ruff (see .github/workflows/test.yml, version: "X.Y.Z").
# Run the SAME version locally or local-pass/CI-fail mismatches occur:
uvx ruff@0.15.16 check . && uvx ruff@0.15.16 format --check .

# Examples need extra deps (PEP 735 group): uv pip install --group examples
```

Any change to `src/cpp/` requires re-running the editable install (it does not auto-rebuild).
Pyright runs in `basic` mode against `.venv` (`pyrightconfig.json`; `tests/` is on `extraPaths`).
Async tests need no decorators — `asyncio_mode = "auto"` in pyproject.

## Build-time feature gates (silent at runtime)

- **HTTPS** is compiled in only when OpenSSL ≥ 3.0 is found (`CPPHTTPLIB_OPENSSL_SUPPORT` in
  CMakeLists). Without it, `https://` resources are silently skipped — never an error. This is
  why Linux wheels use manylinux_2_34 (OpenSSL 3) instead of 2_28 (1.1.1).
- **SVG** decoding (`load_svg_mem`) is behind `#ifdef HAVE_LIBRSVG`, which **no build path
  currently defines** — SVG images are silently skipped everywhere, despite the README
  capability table claiming SVG support. The SVG tests only assert "renders without crash", so
  they pass either way. If you touch this area: either wire librsvg into CMake/CI/vcpkg and
  strengthen the tests to assert pixels, or remove the dead path and fix the README.

## Architecture

Render pipeline: `pylitehtml.Renderer.render()` (Python, `__init__.py`) → `_core.Renderer.render`
(`binding.cpp`, releases the GIL around C++ work) → `PyContainer::render` (`py_container.cpp`,
implements `litehtml::document_container`; litehtml calls its virtual overrides back during
layout/draw — they are NOT dead code even if nothing in `src/cpp` calls them) → `encode.cpp`
(PNG via cairo, JPEG via libjpeg with setjmp-safe error handler, RAW swizzled directly into a
preallocated `PyBytes`).

Invariants that span files:

- **The render surface is always opaque** — `PyContainer::create_surface` paints a white
  background first. `encode.cpp`'s JPEG flatten (`c_premult + (255 - a)`) and the RAW swizzle
  rely on cairo's premultiplied ARGB32; don't "fix" them for straight alpha.
- **Threading contract**: construct `Renderer` on one thread, then `render()` may be called from
  many threads concurrently (GIL released; litehtml document is per-render).
  `FontManager` holds process-wide fontconfig state behind `once_flag` + mutex —
  constructing a Renderer with `extra` fonts mutates process state.
- **ImageCache** (`image_cache.cpp`) is the security boundary for resources:
  `resolve()` blocks `file://` and root-relative paths unless the document base is `file://`
  (i.e. came from `render_file`). It is a thread-safe LRU (atomic `last_used` stamps bumped
  under a shared lock) with in-flight load dedup (`loading_` set + `condition_variable_any`).
  Every decoder (PNG/JPEG/WebP/SVG) must reject error surfaces — handing an error surface to
  cairo poisons the page's whole context.
- **`render_file`** injects `<base href="file://…">` (HTML-entity-escaped; litehtml's parser
  decodes it back) so the C++ side resolves relative CSS/images. Keyword args switch it into
  Jinja2 mode (`_jinja.py`: autoescape on, env `lru_cache`d per resolved directory).
- **markdown.py** is a deliberately small stdlib-only converter (stash-placeholder inline pass +
  line-oriented block parser). URL schemes go through `_safe_url` (cmark `--safe` semantics).
  Don't add third-party deps here — full GFM is the user's job via `converter=`.
- **`markdown_to_*` defaults differ from `html_to_*` on purpose** (`scale=2`,
  `locale="zh-CN"` for Han glyph selection) — documented in their docstrings; not a bug.
- **Type stubs**: `__init__.pyi` and `_core.pyi` are hand-written. Any public API change must
  update them in the same commit.

## CI / packaging gotchas

- Release flow: bump `version` in pyproject.toml, push tag `v*` → `wheels.yml` builds
  cp310–cp314 wheels (cibuildwheel) + sdist → publishes to PyPI via Trusted Publishing (OIDC,
  `environment: pypi` — no token) → creates the GitHub release.
- `wheels.yml` runs `CIBW_TEST_COMMAND` against specific test files (currently
  `tests/test_render.py tests/test_async.py`) — renaming test files breaks release builds.
- Those cibuildwheel smoke tests must not import numpy (only `[dev]`-extra deps installed in
  the test.yml jobs; cibw installs a smaller set).
- Windows builds via vcpkg use the shared composite action
  `.github/actions/setup-vcpkg-win` (used by both test.yml and wheels.yml — edit once).
- The wheel ships only the `pylitehtml/` package; litehtml's own install rules are excluded in
  `pyproject.toml` (`wheel.exclude`). `src/python/pylitehtml/fonts` is a symlink to repo-root
  `fonts/`; CMake installs the real files into the wheel.
- `assets/*.png` are README screenshots regenerated by `examples/*.py`. Pixel output is
  sensitive to Homebrew pango/harfbuzz versions, so byte-diffs vs committed images do not by
  themselves indicate a rendering regression — verify visually / against a same-environment
  HEAD build before concluding code changed rendering.

## Conventions

- Examples in `examples/` are intentionally self-contained (copy-paste runnable, public API
  only) — don't extract shared helpers from them.
- ruff: E501 ignored repo-wide (long inline CSS/HTML); `__init__.py` ignores E402 (imports must
  follow the Windows DLL-path setup).
- Commit style: conventional commits (`feat:`/`fix:`/`refactor:`/`ci:`/`docs:`), English.
