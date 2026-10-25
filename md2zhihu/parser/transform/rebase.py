import os
import re
from urllib.parse import urlsplit

from ...types import ASTNodes


def rebase_url_in_ast(frm: str, to: str, nodes: ASTNodes) -> None:
    for n in nodes:
        if "children" in n:
            rebase_url_in_ast(frm, to, n["children"])

        if n["type"] == "image":
            n["src"] = rebase_url(frm, to, n["src"])
            continue

        if n["type"] == "link":
            n["link"] = rebase_url(frm, to, n["link"])
            continue


def rebase_url(frm: str, to: str, src: str) -> str:
    """
    Change relative path based from ``frm`` to from ``to``.
    Only the path of ``src`` changes. Its query and its fragment stay as written, such as "?next=a/../b",
    which is not a path.
    """
    # A URL with a scheme, such as "https:" or "mailto:", is not a path.
    if urlsplit(src).scheme != "":
        return src

    if src.startswith("/"):
        return src

    # The path ends where the query or the fragment starts, such as "doc.html" in "doc.html?next=a/../b".
    path = re.split(r"[?#]", src, maxsplit=1)[0]
    # A URL without a path refers to the article where it is: "#intro" to a heading in it, and "" or "?q=1" to itself.
    if path == "":
        return src
    rest = src[len(path) :]

    p = os.path.join(frm, path)
    p = os.path.relpath(p, start=to)

    return p + rest
