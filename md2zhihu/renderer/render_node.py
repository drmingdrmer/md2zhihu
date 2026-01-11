from __future__ import annotations

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

    def new_child(self, n: ASTNode) -> RenderNode:
        c = RenderNode(n, parent=self)
        c.level = self.level + 1
        return c

    def to_str(self) -> str:
        t = "{}".format(self.node.get("type"))
        if self.parent is None:
            return t

        return self.parent.to_str() + " -> " + t
