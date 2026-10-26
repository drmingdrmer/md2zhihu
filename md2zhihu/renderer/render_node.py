from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from ..types import ASTNode


class RenderNode(object):
    """
    RenderNode is a container of current ast-node and parent
    """

    def __init__(self, n: ASTNode, parent: Optional[RenderNode] = None) -> None:
        """
        :param n: ast node: a normal dictionary such as {'type': 'text' ... }
        :param parent: parent RenderNode
        """
        self.node: ASTNode = n

        self.level: int = 0

        # parent RenderNode
        self.parent: Optional[RenderNode] = parent

        # The lines of each child that MDRender.render_child() renders, by the id of its node.
        self.child_lines: Dict[int, List[str]] = {}

        # The RenderNode of each child that new_child() returns, by the id of its node.
        self.children: Dict[int, RenderNode] = {}

    def new_child(self, n: ASTNode) -> RenderNode:
        """
        Return the RenderNode of the child `n`, the same one each time, so that the lines of the children of `n`
        that it keeps are read through it before and after `n` is rendered.
        """
        c = self.children.get(id(n))
        if c is None:
            c = RenderNode(n, parent=self)
            c.level = self.level + 1
            self.children[id(n)] = c
        return c

    def to_str(self) -> str:
        t = "{}".format(self.node.get("type"))
        if self.parent is None:
            return t

        return self.parent.to_str() + " -> " + t
