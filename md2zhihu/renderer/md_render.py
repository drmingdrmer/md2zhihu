import re
from typing import List
from typing import Optional

from ..utils import add_paragraph_end
from ..utils import code_fence
from ..utils import indent
from ..utils import longest_backtick_run
from ..utils import msg
from ..utils import strip_paragraph_end
from .dispatch import render_with_features

# The characters that end the URL of a link or an image in markdown: the ASCII control characters and the space.
url_breakers = re.compile(r"[\x00-\x20\x7f]")


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
            src = link_destination(n["src"])
            return ["![{alt}]({src}{title})".format(alt=n["alt"], src=src, title=title)]

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
                head = (str(start) + ".").ljust(3) + " "

            lines[0] = head + lines[0]
            # The later lines of the item start at the column of its text, such as column 5 after "100. ".
            lines = lines[0:1] + [indent(x, len(head)) for x in lines[1:]]
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
            lines[-1] = lines[-1] + "](" + link_destination(n["link"]) + link_title(n["title"]) + ")"

            return lines

        if typ == "heading":
            lines = self.render(rnode)
            # The heading is written on one line, so its parts, such as text and code, are joined.
            # The lines of a setext heading are joined with a space.
            text = "".join(lines).replace("\n", " ")
            return ["#" * n["level"] + " " + text, ""]

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

        raise TypeError(f"MDRender can not render a node of type {typ!r}, at {rnode.to_str()}")

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


def link_destination(url: str) -> str:
    """
    Return `url` as written as the destination of a link or an image, which a markdown parser reads to its end.
    Each space or control character is percent-encoded, and so is each parenthesis, if they do not pair up, such as in "x).png".
    """
    url = url_breakers.sub(percent_encode, url)

    depth = 0
    for c in url:
        if c == "(":
            depth += 1
        if c == ")":
            depth -= 1
        if depth < 0:
            break

    if depth == 0:
        return url
    return url.replace("(", "%28").replace(")", "%29")


def percent_encode(m: re.Match[str]) -> str:
    """Return the character that `m` matches as a percent-encoded byte, such as "%20" for a space."""
    code = ord(m.group(0))
    return "%{:02X}".format(code)
