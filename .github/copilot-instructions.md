# cdxcore — Copilot instructions for code agents

Purpose: give an AI coding agent the immediate, actionable knowledge to be productive in this repository.

- **Project root**: repository is a Python package at the repo root. See `pyproject.toml` for metadata and required Python `>=3.12`.
- **Install / build**: package uses setuptools via `pyproject.toml`. Quick local install for development:

  - `pip install -e .` (run from repository root)

- **Run tests**:
  - Tests live in the `tests/` folder and use Python `unittest.TestCase` style (not pytest-only). Run with:

    - `python -m unittest discover -v` (from repo root)
    - `pytest -q` will also work but note tests include a test helper (`import_local`) that expects running from the repository root or the `tests` directory.

- **Docs**:
  - Sphinx docs are in `docs/`. Build from the `docs/` directory: `make html` (or use `docs/make.bat` on Windows).
  - `docs/source/conf.py::set_path()` intentionally requires running `make` from the `docs` directory so the local package becomes importable.

- **What the codebase contains (big picture)**:
  - `cdxcore/` — main package modules:
    - `config.py`: configuration object and validation patterns used throughout the project (see `tests/test_config.py` for many usage examples).
    - `subdir.py`: file/directory helpers and the `SubDir.cache` decorator for code-versioned caching.
    - `uniquehash.py` / `version.py`: code-versioning and deterministic hashing used by caching and I/O.
    - `npio.py`, `npshm.py`: binary numpy I/O and shared-memory numpy arrays — used where zero-copy or interprocess sharing is needed.
    - `jcpool.py`: simple process-pool.
    - `dynaplot.py`, `pretty.py`, `util.py`, `verbose.py`: plotting, pretty dicts, formatting, and logging helpers.

- **Repository conventions & gotchas for agents**:
  - Docstrings follow NumPy-style; Sphinx uses `numpydoc`. When editing APIs, keep NumPy-style docstrings to preserve autodoc pages.
  - Tests use an `import_local()` helper in tests to force imports from the local package when running from `tests/`. When running or editing tests, ensure Python's import path points to the repository root (or run the helper's expected workflow).
  - `docs/source/conf.py` manipulates `sys.path`; don't modify it lightly — its `set_path()` asserts being run from `docs/`.
  - Version: `cdxcore/__init__.py` contains `__version__` (currently authoritative for the package). If releasing or changing package version, update `pyproject.toml` and `cdxcore/__init__.py` consistently.
  - Caching: `SubDir.cache("x.y")` implements code-versioned caching. When changing function code that is cached, bump the cache version string.

- **Testing & CI suggestions (how to run and validate changes)**:
  - Run unit tests locally first: `python -m unittest discover -v`.
  - Run doc build for any public API change to ensure Sphinx autosummary and numpydoc pages still build: `cd docs && make html`.
  - Linting/formatting: there is no repo-wide formatter enforced; prefer preserving the current style.

- **Files to inspect for patterns/examples** (quick links):
  - `pyproject.toml` — dependencies and Python version
  - `cdxcore/__init__.py` — package `__version__`
  - `cdxcore/config.py` — canonical config usage patterns (see `tests/test_config.py`)
  - `cdxcore/subdir.py` — caching and file I/O patterns
  - `cdxcore/npshm.py` and `cdxcore/npio.py` — shared-memory and binary I/O examples
  - `docs/source/conf.py` — documentation build expectations

- **When altering public APIs**:
  - Update docstrings in NumPy style.
  - Run `cd docs && make html` to ensure docs build.
  - Run unit tests to ensure behavior preserved (see `tests/`). If a cached function's behavior changes, bump its cache version.

If any of the above items are unclear or you want more detail (for example, concrete examples pulled from `cdxcore/config.py` or `cdxcore/subdir.py`), tell me which area to expand and I'll update this file.
