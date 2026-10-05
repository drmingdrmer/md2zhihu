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
    line = "".join([str(x) for x in args])
    line = mask_url_credential(line)
    logger.info(line)


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
    if lines[-1] == "":
        return strip_paragraph_end(lines[:-1])

    return lines


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
