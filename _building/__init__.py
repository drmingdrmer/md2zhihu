#!/usr/bin/env python
# coding: utf-8

import imp
import sys

# sys.path.insert(0, os.path.abspath('..'))
# sys.path.insert(0, os.path.abspath('../..'))
# sys.path.insert(0, os.path.abspath('../../..'))

# __title__ = 'requests'
# __description__ = 'Python HTTP for Humans.'
# __url__ = 'https://requests.readthedocs.io'
# __version__ = '2.23.0'

__author__ = 'Zhang Yanpo'
__author_email__ = 'drdr.xp@gmail.com'
__license__ = 'MIT'
__copyright__ = 'Copyright 2020 Zhang Yanpo'


# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html


# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    'sphinx.ext.napoleon',
    # "sphinx.ext.intersphinx",
    # "sphinx.ext.todo",
    # "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


master_doc = "index"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']
html_static_path = []


def sphinx_confs():
    """
        Load repo dir as a package

        `readthedocs` use branch name as dir!
        Thus the following does not work::

            import pk3proc
    """

    print("sys.path:", sys.path)

    pkg = imp.load_source("foo", '../../__init__.py')
    return (
        pkg.__name__,
        pkg,
        pkg.__version__,
        __author__,
        __copyright__,
        extensions,
        templates_path,
        exclude_patterns,
        master_doc,
        html_theme,
        html_static_path,
    )
