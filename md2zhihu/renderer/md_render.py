import pprint
from typing import List
from typing import Optional

from ..utils import add_paragraph_end
from ..utils import code_fence
from ..utils import indent
from ..utils import longest_backtick_run
from ..utils import msg
from ..utils import strip_paragraph_end
from .dispatch import render_with_features


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
            return ["$$" + n["text"].strip() + "$$"]

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
            fence = code_fence(n["text"])
            # remove the last \n
            return [fence + (n["info"] or "")] + n["text"][:-1].split("\n") + [fence, ""]

        if typ == "codespan":
            code = n["text"]
            ticks = "`" * (longest_backtick_run(code) + 1)
            # A markdown parser removes one space from each side of the code, if it has one on both sides and is not all spaces.
            # So a space keeps a "`" at either end apart from `ticks`, and keeps the spaces of the code.
            touches_ticks = code.startswith("`") or code.endswith("`")
            loses_spaces = code.startswith(" ") and code.endswith(" ") and code.strip() != ""
            if touches_ticks or loses_spaces:
                code = " " + code + " "
            return [ticks + code + ticks]

        if typ == "image":
            title = link_title(n["title"])
            return ["![{alt}]({src}{title})".format(alt=n["alt"], src=n["src"], title=title)]

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
                # mistune gives the number of the first item only when it is not 1.
                start = parent.node["start"]
                if start is None:
                    start = 1
                # A markdown parser numbers the items from the first number and ignores the others.
                # Up to 99, the marker is 4 characters wide, as indent() indents the later lines of the item.
                head = (str(start) + ".").ljust(3) + " "

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

        if typ == "block_html":
            return add_paragraph_end([n["text"]])

        if typ == "link":
            lines = self.render(rnode)
            lines[0] = "[" + lines[0]
            lines[-1] = lines[-1] + "](" + n["link"] + link_title(n["title"]) + ")"

            return lines

        if typ == "heading":
            lines = self.render(rnode)
            if not lines:
                # A heading with no text, such as "##", has no children.
                lines = [""]
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


def link_title(title: Optional[str]) -> str:
    """
    Return the title of a link or an image as written after its URL, such as ` "Figure 1"`, or "" without a title.
    mistune removes the backslash escapes from a title, so a backslash and a double quote in it are escaped again.
    """
    if title is None:
        return ""
    escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    return ' "' + escaped + '"'
