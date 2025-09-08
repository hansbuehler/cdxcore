# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# conf.py
def set_path(source = "cdxcore"):
    import os, sys
    root_path = os.path.split(
                os.path.split(  
                  os.path.split( __file__ )[0] # 'source
                  )[0] # 'docs'
                )[0] # 'packag
    assert root_path[-len(source):] == source, f"Conf.py '{__file__}': invalid source path '{root_path}'. Call 'make html' from the docs directory"
    sys.path.insert(0, root_path)  # so your package is importable
    
project = 'cdxcore'
copyright = '2025, Hans Buehler'
author = 'Hans Buehler'

set_path(project)

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    #"sphinx_autodoc_typehints",
    "numpydoc",
    "sphinx_automodapi.automodapi",
    "sphinx_copybutton",
    "sphinx_design",
    "myst_parser",       # pip install myst-parser
]
templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "navigation_depth": 4,
    "show_prev_next": False,
    "github_url": "https://github.com/hansbuehler/cdxcore",  # optional
    "show_toc_level": 2,
    "secondary_sidebar_items": ["page-toc", "sourcelink"],
}
html_theme_options = {
}

html_static_path = ['_static']

# Autodoc / autosummary: NumPy-like API pages
autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "inherited-members": False,
    "undoc-members": False,
    "show-inheritance": False, 
    "special-members": "__call__"
}
autodoc_typehints = 'signature'  # types shown in the doc body, like NumPy
#numpydoc_show_class_members = True

# numpydoc tweaks (keeps class doc at top, avoids member spam)
numpydoc_show_class_members = True
numpydoc_class_members_toctree = True
# Optional validation during build:
# numpydoc_validation_checks = {"all"}  # or a subset like {"GL06","PR01",...}

# Cross-link to external projects (like NumPy, SciPy, pandas)
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy":  ("https://numpy.org/doc/stable/", None),
    "scipy":  ("https://docs.scipy.org/doc/scipy/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

myst_enable_extensions = [
    "colon_fence",   # allow ::: fenced blocks
    "deflist",       # definition lists
    "dollarmath",    # $math$ and $$math$$
    "amsmath",       # AMS math environments
    "linkify",       # auto-detect bare URLs
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

