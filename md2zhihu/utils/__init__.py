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


def indent(line: str, width: int = 4) -> str:
    """Indent `line` by `width` spaces, or return it as it is if it is empty."""
    if line == "":
        return ""
    return " " * width + line


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


def code_block_lines(code: str, info: str) -> List[str]:
    r"""
    Return the lines of a fenced code block that holds `code`, which ends with "\n", and has the info string `info`.
    The fence is a run of "~" if `info` has a "`", which a markdown parser does not allow after a fence of "`",
    else a run of "`". No run in `code` closes it: it is 1 longer than the longest run of its char in `code`,
    and at least 3 long.
    A space keeps an `info` that starts with the fence char, such as "~a`b", apart from the fence.
    """
    char = "`"
    if "`" in info:
        char = "~"
    longest = longest_run(code, char)
    fence = char * max(3, longest + 1)

    opening = fence + info
    if info.startswith(char):
        opening = fence + " " + info

    # remove the last \n
    lines = code[:-1].split("\n")
    return [opening] + lines + [fence]


def longest_run(text: str, char: str) -> int:
    """Return the length of the longest run of `char` in `text`, or 0."""
    pattern = re.escape(char) + "+"
    runs = re.findall(pattern, text)
    return max([len(r) for r in runs], default=0)


def asset_fn(text: str, suffix: str, key: str = "") -> str:
    """
    Return the file name of an asset made from `text`: the letters and digits of `text`, then an md5 of `text` and `key`.
    `key` tells apart the assets made from one text, such as the images of different converters.
    """
    textmd5 = hashlib.md5(to_bytes(text + key)).hexdigest()
    escaped = re.sub(r"[^a-zA-Z0-9_\-=]+", "", text)
    fn = escaped[:32] + "-" + textmd5[:16] + "." + suffix
    return fn


def fwrite(*p) -> None:
    cont = p[-1]
    p = p[:-1]
    with open(os.path.join(*p), "wb") as f:
        f.write(cont)
