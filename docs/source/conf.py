# Configuration file for the Sphinx documentation builder.

import tomllib
from pathlib import Path
from os.path import dirname

# -- Project information

project = "cubething_psync"
copyright = "2025, ada mandala"
author = "ada mandala"

toml = tomllib.load(open(Path(dirname(__file__)) / "../../pyproject.toml", 'rb'))
release = toml["project"]["version"]
version = release

# -- General configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

autosummary_generate = True

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "private-members": False,
}

# -- Options for HTML output

html_theme = "furo"
html_logo = "../static/logo.png"

# -- Options for EPUB output
epub_show_urls = "footnote"
