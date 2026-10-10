"""Exceptions for the failures that the user can fix."""


class UserError(Exception):
    """
    A failure that the user can fix, such as a missing image.
    The md2zhihu command prints its message as one line, without a traceback, and exits 1.
    """


class MissingFileError(UserError, FileNotFoundError):
    """A file that the markdown uses does not exist, such as an image."""


class PushError(UserError, RuntimeError):
    """git failed to push the output folder to the asset repo."""


class DownloadError(UserError, RuntimeError):
    """--download can not download an image, such as for a 404 status or a stalled server."""


class FormatError(UserError, ValueError):
    """A file that md2zhihu reads has a shape that it can not use, such as front matter whose "refs" is a number."""


class EmbedCycleError(UserError, ValueError):
    """A markdown embeds itself, directly or through other markdown files."""
