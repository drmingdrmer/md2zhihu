"""Utility functions for md2zhihu"""

import hashlib
import logging
import os
import re
from typing import List

from k3handy import to_bytes

logger = logging.getLogger(__name__)


def sj(*args) -> str:
    return "".join([str(x) for x in args])


def msg(*args) -> None:
    """Log a message with backward-compatible output format.

    The token in a git push URL such as ``https://user:token@github.com/...`` is masked.
    """
    log(logging.INFO, args)


def debug(*args) -> None:
    """Log a message as msg() does, at the debug level, which ``md2zhihu --verbose`` shows."""
    log(logging.DEBUG, args)


def warn(*args) -> None:
    """Log a warning as msg() does."""
    log(logging.WARNING, args)


def log(level: int, args: tuple) -> None:
    line = "".join([str(x) for x in args])
    line = mask_url_credential(line)
    logger.log(level, line)


def mask_url_credential(s: str) -> str:
    """Replace the ``user:token@`` part of each http(s) URL in ``s`` with ``***@``."""
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", s)


def indent(line: str) -> str:
    if line == "":
        return ""
    return "    " + line


def escape(s: str, quote: bool = True) -> str:
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace('"', "&quot;")
    return s


def add_paragraph_end(lines: List[str]) -> List[str]:
    #  add blank line to a paragraph block
    if lines[-1] == "":
        return lines

    lines.append("")
    return lines


def strip_paragraph_end(lines: List[str]) -> List[str]:
    #  remove last blank lines
    if lines and lines[-1] == "":
        return strip_paragraph_end(lines[:-1])

    return lines


def code_fence(code: str) -> str:
    """
    Return the fence for a code block that holds `code`: a run of "`" that no run of "`" in `code` closes.
    It is 1 longer than the longest run in `code`, and at least 3 long.
    """
    longest = longest_backtick_run(code)
    return "`" * max(3, longest + 1)


def longest_backtick_run(text: str) -> int:
    """Return the length of the longest run of "`" in `text`, or 0."""
    runs = re.findall("`+", text)
    return max([len(r) for r in runs], default=0)


def asset_fn(text: str, suffix: str) -> str:
    textmd5 = hashlib.md5(to_bytes(text)).hexdigest()
    escaped = re.sub(r"[^a-zA-Z0-9_\-=]+", "", text)
    fn = escaped[:32] + "-" + textmd5[:16] + "." + suffix
    return fn


def fwrite(*p) -> None:
    cont = p[-1]
    p = p[:-1]
    with open(os.path.join(*p), "wb") as f:
        f.write(cont)
