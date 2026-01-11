class RenderNode(object):
    """
    RenderNode is a container of current ast-node and parent
    """

    def __init__(self, n, parent=None):
        """
        :param n: ast node: a normal dictionary such as {'type': 'text' ... }
        :param parent: parent RenderNode
        """
        self.node = n

        self.level = 0

        # parent RenderNode
        self.parent = parent

    def new_child(self, n):
        c = RenderNode(n, parent=self)
        c.level = self.level + 1
        return c

    def to_str(self):
        t = "{}".format(self.node.get("type"))
        if self.parent is None:
            return t

        return self.parent.to_str() + " -> " + t
