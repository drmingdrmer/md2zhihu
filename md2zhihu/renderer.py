"""Renderer classes for md2zhihu"""

import pprint
from typing import List
from typing import Optional

from .utils import add_paragraph_end
from .utils import indent
from .utils import msg
from .utils import strip_paragraph_end


class MDRender(object):
    # platform specific renderer

    def __init__(self, conf, features: dict):
        self.conf = conf
        self.features = features

    def render_node(self, rnode):
        """
        Render a AST node into lines of text

        Args:
            rnode is a RenderNode instance
        """

        n = rnode.node
        typ = n["type"]

        #  customized renderers:

        lines = render_with_features(self, rnode, self.features)
        if lines is not None:
            return lines
        else:
            # can not render, continue with default handler
            pass

        # default renderers:

        if typ == "thematic_break":
            return ["---", ""]

        if typ == "paragraph":
            lines = self.render(rnode)
            return "".join(lines).split("\n") + [""]

        if typ == "text":
            return [n["text"]]

        if typ == "strong":
            lines = self.render(rnode)
            lines[0] = "**" + lines[0]
            lines[-1] = lines[-1] + "**"
            return lines

        if typ == "math_block":
            return ["$$", n["text"], "$$"]

        if typ == "math_inline":
            return ["$$ " + n["text"].strip() + " $$"]

        if typ == "table":
            return self.render(rnode) + [""]

        if typ == "table_head":
            alignmap = {
                "left": ":--",
                "right": "--:",
                "center": ":-:",
                None: "---",
            }
            lines = self.render(rnode)
            aligns = [alignmap[x["align"]] for x in n["children"]]
            aligns = "| " + " | ".join(aligns) + " |"
            return ["| " + " | ".join(lines) + " |", aligns]

        if typ == "table_cell":
            lines = self.render(rnode)
            return ["".join(lines)]

        if typ == "table_body":
            return self.render(rnode)

        if typ == "table_row":
            lines = self.render(rnode)
            return ["| " + " | ".join(lines) + " |"]

        if typ == "block_code":
            # remove the last \n
            return ["```" + (n["info"] or "")] + n["text"][:-1].split("\n") + ["```", ""]

        if typ == "codespan":
            return [("`" + n["text"] + "`")]

        if typ == "image":
            if n["title"] is None:
                return ["![{alt}]({src})".format(**n)]
            else:
                return ["![{alt}]({src} {title})".format(**n)]

        if typ == "list":
            lines = self.render(rnode)
            return add_paragraph_end(lines)

        if typ == "list_item":
            lines = self.render(rnode)

            # parent is a `list` node
            parent = rnode.parent
            assert parent.node["type"] == "list"

            head = "-   "
            if parent.node["ordered"]:
                head = "1.  "

            lines[0] = head + lines[0]
            lines = lines[0:1] + [indent(x) for x in lines[1:]]
            return lines

        if typ == "block_text":
            lines = self.render(rnode)
            return "".join(lines).split("\n")

        if typ == "block_quote":
            lines = self.render(rnode)
            lines = strip_paragraph_end(lines)
            lines = ["> " + x for x in lines]
            return lines + [""]

        if typ == "newline":
            return [""]

        if typ == "block_html":
            return add_paragraph_end([n["text"]])

        if typ == "link":
            #  TODO title
            lines = self.render(rnode)
            lines[0] = "[" + lines[0]
            lines[-1] = lines[-1] + "](" + n["link"] + ")"

            return lines

        if typ == "heading":
            lines = self.render(rnode)
            lines[0] = "#" * n["level"] + " " + lines[0]
            return lines + [""]

        if typ == "strikethrough":
            lines = self.render(rnode)
            lines[0] = "~~" + lines[0]
            lines[-1] = lines[-1] + "~~"
            return lines

        if typ == "emphasis":
            lines = self.render(rnode)
            lines[0] = "*" + lines[0]
            lines[-1] = lines[-1] + "*"
            return lines

        if typ == "inline_html":
            return [n["text"]]

        if typ == "linebreak":
            return ["  \n"]

        print(typ, n.keys())
        pprint.pprint(n)
        return ["***:" + typ]

    def render(self, rnode) -> List[str]:
        rst = []
        for n in rnode.node["children"]:
            child = rnode.new_child(n)
            lines = self.render_node(child)
            rst.extend(lines)

        return rst

    def msg(self, *args):
        msg(*args)


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


#  features: {typ:action(), typ2:{subtyp:action()}}
def render_with_features(mdrender, rnode: RenderNode, features=None) -> Optional[List[str]]:
    if features is None:
        features = {}

    n = rnode.node

    node_type = n["type"]

    if node_type not in features:
        if "*" in features:
            return features["*"](mdrender, rnode)
        else:
            return None

    type_handler = features[node_type]
    if callable(type_handler):
        return type_handler(mdrender, rnode)

    #  subtype is info, the type after "```"
    lang = n["info"] or ""

    if lang in type_handler:
        return type_handler[lang](mdrender, rnode)

    if "*" in type_handler:
        return type_handler["*"](mdrender, rnode)

    return None
