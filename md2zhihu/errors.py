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
