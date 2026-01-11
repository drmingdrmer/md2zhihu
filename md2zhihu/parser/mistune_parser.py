from typing import Callable

from .._vendor import mistune
from ..types import ASTNodes


def new_parser() -> Callable[[str], ASTNodes]:
    rdr = mistune.create_markdown(
        escape=False,
        renderer="ast",
        plugins=["strikethrough", "footnotes", "table"],
    )

    return rdr
