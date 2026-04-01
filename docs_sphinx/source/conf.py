import os
import sys

project = "Read_For_Me"
author = "Read_For_Me Team"
release = "1.0"

sys.path.insert(0, os.path.abspath("../.."))

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = []

language = "fr"

html_theme = "alabaster"
html_static_path = ["_static"]

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

autodoc_member_order = "bysource"
autodoc_inherit_docstrings = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

autodoc_mock_imports = [
    "gpiozero",
    "bleak",
    "pyrf24",
    "pytesseract",
    "piper",
    "PIL",
    "requests",
]
