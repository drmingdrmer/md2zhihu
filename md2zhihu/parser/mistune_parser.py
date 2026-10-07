from typing import Callable

from .._vendor import mistune
from ..types import ASTNodes


def new_parser() -> Callable[[str], ASTNodes]:
    rdr = mistune.create_markdown(
        escape=False,
        renderer="ast",
        plugins=["strikethrough", "footnotes", "table"],
    )

    def parse(text: str) -> ASTNodes:
        nodes = rdr(text)
        return drop_newline(nodes)

    return parse


def drop_newline(nodes: ASTNodes) -> ASTNodes:
    """
    Remove the ``newline`` nodes that mistune 2 emits for blank lines that no block consumes.
    """

    rst: ASTNodes = []
    for n in nodes:
        if n["type"] == "newline":
            continue

        # An autolink's children is a str.
        if isinstance(n.get("children"), list):
            n["children"] = drop_newline(n["children"])

        rst.append(n)

    return rst
