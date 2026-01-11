import os
import re

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
    """
    if re.match(r"http[s]?://", src):
        return src

    if src.startswith("/"):
        return src

    p = os.path.join(frm, src)
    p = os.path.relpath(p, start=to)

    return p
