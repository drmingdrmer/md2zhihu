"""
package-name is utility to create sub process.

"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("md2zhihu")
except PackageNotFoundError:
    __version__ = "0.16"

__name__ = "md2zhihu"

from . import md2zhihu
from . import mistune
from .md2zhihu import Article
from .md2zhihu import AssetRepo
from .md2zhihu import Config
from .md2zhihu import LocalRepo
from .md2zhihu import ParserConfig
from .md2zhihu import main
