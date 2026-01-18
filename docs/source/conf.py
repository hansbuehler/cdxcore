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
    "sphinx_autodoc_typehints",
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
    "navigation_depth": 2,
    "show_prev_next": False,
    "github_url": "https://quantitative-research.de/docs/cdxcore",  # optional
    "show_toc_level": 3,
    "secondary_sidebar_items": ["page-toc", "sourcelink"],
}

html_static_path = ['_static']
html_css_files = ["custom.css"]

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
typehints_document_rtype = False

# numpydoc tweaks
#
# IMPORTANT:
# numpydoc can inject ``.. autosummary::`` blocks for class members into the rendered
# docstring. Sphinx's autosummary stub generation does not generate pages for those
# docstring-injected directives, which results in a flood of warnings like
# "autosummary: stub file not found 'pkg.Class.method'".
#
# We therefore do not ask numpydoc to generate autosummary/toctree pages for members.
# Class members are still shown inline via autodoc_default_options['members'].
numpydoc_show_class_members = False
numpydoc_class_members_toctree = False
# Optional validation during build:
# numpydoc_validation_checks = {"all"}  # or a subset like {"GL06","PR01",...}

# Cross-link to external projects (like NumPy, SciPy, pandas)
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy":  ("https://numpy.org/doc/stable/", None),
    "scipy":  ("https://docs.scipy.org/doc/scipy/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "ipython": ("https://ipython.readthedocs.io/en/stable/", None),
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

from docutils import nodes
from sphinx.roles import XRefRole

def decorator_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    """Custom role to display decorators with @ prefix."""
    # Create a pending_xref node like other Sphinx cross-references
    node = nodes.literal(text, f"@{text}", classes=["xref", "dec"])
    node["reftype"] = "func"     # decorators are functions
    node["reftarget"] = text
    node["refdomain"] = "py"     # Python domain
    return [node], []

from sphinx.domains.python import PyXRefRole

def setup(app):
    # Make :dec: behave exactly like :py:func:
    app.add_role_to_domain("py", "dec", PyXRefRole("func"))
    return {"parallel_read_safe": True}


