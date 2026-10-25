import re
from functools import partial
from typing import Dict
from typing import List
from typing import Optional

from mistune.helpers import BLOCK_TAGS
from mistune.helpers import PRE_TAGS

from ..utils import add_paragraph_end
from ..utils import code_block_lines
from ..utils import indent
from ..utils import longest_run
from ..utils import msg
from ..utils import strip_paragraph_end
from .dispatch import render_with_features

# The characters that end the URL of a link or an image in markdown: the ASCII control characters and the space.
url_breakers = re.compile(r"[\x00-\x20\x7f]")

# An "&" that starts a character reference, such as "&copy;" or "&#169;", which a markdown parser reads as one char.
char_reference_start = re.compile(r"&(?=#[0-9]{1,7};|#[xX][0-9a-fA-F]{1,6};|[A-Za-z][A-Za-z0-9]*;)")

# A line that closes its block, so that the next line starts a block without a blank line between them:
# a code fence, an ATX heading or a thematic break.
block_closing_line = re.compile(r" *(?:`{3,}|#{1,6}(?: .*)?|(?:- *){3,}|(?:\* *){3,}|(?:_ *){3,})")

# The quote markers, with their indent, at the start of a line in a quote, such as "    > >" in "    > > a".
quote_markers = re.compile(r" *>(?: *>)*")

# The start of a line that, after a line of a paragraph, starts a block or underlines the paragraph as a heading.
# It also matches a few lines that start no block, such as "+ " of an empty item, which only get an indent they do not need.
paragraph_breaker = re.compile(
    r" {0,3}(?:"
    r"[=-]+ *$"  # a setext heading underline
    r"|(?:[-*_] *){3,}$"  # a thematic break
    r"|#{1,6}(?: |$)"  # an ATX heading
    r"|`{3,}|~{3,}"  # a code fence
    r"|>"  # a quote
    r"|[-+*] "  # an item of an unordered list
    r"|0*1[.)] "  # an item of an ordered list, which only 1 starts after a paragraph line
    r"|\|?[ :]*-[-| :]*$"  # the delimiter row of a table
    r"|<(?:!|\?|/?(?:" + "|".join(BLOCK_TAGS + PRE_TAGS) + r")(?:[ \t/>]|$))"  # an HTML block
    r")",
    re.IGNORECASE,
)

# The spaces and the number at the start of a line, before the char that starts its block, such as "1" of "1. a".
block_start_prefix = re.compile(r"^ *[0-9]*")

# A block marker at the start of a line that starts a block, such as the first line of a paragraph:
# an ATX heading, a quote, an item of a bullet list or of an ordered list, or a thematic break up to its last char,
# such as "# x", "> q", "- x", "1. x" or "---".
line_block_marker = re.compile(
    r"#{1,6}(?=[ \t]|$)|>|[-+*](?=[ \t]|$)|\d{1,9}[.)](?=[ \t]|$)"
    r"|(?:-[ \t]*){2,}-(?=[ \t]*$)|(?:_[ \t]*){2,}_(?=[ \t]*$)|(?:\*[ \t]*){2,}\*(?=[ \t]*$)"
)

# The closing sequence of an ATX heading at the end of its text, such as the last "#" of "# a #", which a markdown parser
# removes.
heading_closing = re.compile(r"(?:^|(?<=[ \t]))#+[ \t]*$")

# The two markers of the items of an unordered list, and of an ordered list after its number.
# The other bullet char is "+", because with "*" an item that holds a thematic break, "*   ***", is a thematic break.
bullets = ["-", "+"]
delimiters = [".", ")"]

# A backslash escape in text, which is written as it is, or a "*" or "`" without one, which md2zhihu escapes.
# Such a "*" or "`" is a char of the text, but where md2zhihu writes it, it could pair with md2zhihu's emphasis markers,
# or with the backticks of a code span that md2zhihu writes with fewer backticks than the source.
literal_markers = re.compile(r"\\.|[*`]")

# A char of plain text that starts inline markdown where md2zhihu writes the text, such as the text of an autolink
# or the title of a reference: a backslash escape, a code span, an emphasis, a link, md2zhihu's math, a strikethrough,
# or inline HTML. A run of "_" is matched as a whole, because escape_text_char() decides by the chars around the run.
text_specials = re.compile(r"[\\`*\[\]$~<]|_+")

# A run of "_" in plain text.
underscore_runs = re.compile(r"_+")

# A char of plain chars that starts inline markdown where md2zhihu writes them, such as the code of a code span on simple:
# a char of `text_specials`, or an "&" that starts a character reference.
plain_specials = re.compile(text_specials.pattern + "|" + char_reference_start.pattern)


class MDRender(object):
    # platform specific renderer

    def __init__(self, conf, features: dict):
        self.conf = conf
        self.features = features
        # The name of each copy that store_linked_file makes in this conversion, mapped to the path of the file that it copies.
        self.linked_files: Dict[str, str] = {}

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
            # In a list item, "---" after a paragraph line underlines a heading, and "-   ---" is a thematic break of its own.
            in_item = rnode.parent is not None and rnode.parent.node["type"] == "list_item"
            if in_item:
                return ["***", ""]
            return ["---", ""]

        if typ == "paragraph":
            lines = self.render(rnode)
            return paragraph_lines(lines) + [""]

        if typ == "text":
            text = literal_markers.sub(escape_marker, n["text"])
            return [text]

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
            align_line = "| " + " | ".join(aligns) + " |"
            return ["| " + " | ".join(lines) + " |", align_line]

        if typ == "table_cell":
            lines = self.render(rnode)
            return ["".join(lines)]

        if typ == "table_body":
            return self.render(rnode)

        if typ == "table_row":
            lines = self.render(rnode)
            return ["| " + " | ".join(lines) + " |"]

        if typ == "block_code":
            lines = code_block_lines(n["text"], n["info"] or "")
            return lines + [""]

        if typ == "codespan":
            code = n["text"]
            ticks = "`" * (longest_run(code, "`") + 1)
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
            # parent is a `list` node
            parent = rnode.parent
            assert parent.node["type"] == "list"

            if parent.node["tight"]:
                lines = self.render_tight_item(rnode)
            else:
                lines = self.render(rnode)

            # A list right after a list of the same kind takes the other marker, or a markdown parser joins the two lists.
            marker = lists_before(parent) % 2

            head = bullets[marker] + "   "
            if parent.node["ordered"]:
                # mistune gives the number of the first item only when it is not 1.
                start = parent.node["start"]
                if start is None:
                    start = 1
                # A markdown parser numbers the items from the first number and ignores the others.
                head = (str(start) + delimiters[marker]).ljust(3) + " "

            lines[0] = head + lines[0]
            # The later lines of the item start at the column of its text, such as column 5 after "100. ".
            lines = lines[0:1] + [indent(x, len(head)) for x in lines[1:]]
            return lines

        if typ == "block_text":
            lines = self.render(rnode)
            return paragraph_lines(lines)

        if typ == "block_quote":
            lines = self.render(rnode)
            lines = strip_paragraph_end(lines)
            # A quote without a block, such as one that holds only a reference definition, still needs its ">".
            if len(lines) == 0:
                return [">", ""]
            lines = ["> " + x for x in lines]
            return lines + [""]

        if typ == "block_html":
            # A quote or a list item puts its marker or indent before each of its lines, so each line of the HTML is one.
            return add_paragraph_end(n["text"].split("\n"))

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
            # A "#" after a space at the end would close the heading, such as in the text of the setext heading "a #\n===",
            # or in "a #" of the code span `a #`, which simple writes as text.
            text = heading_closing.sub(r"\\\g<0>", text)
            return ["#" * n["level"] + " " + text, ""]

        if typ == "strikethrough":
            lines = self.render(rnode)
            lines[0] = "~~" + lines[0]
            lines[-1] = lines[-1] + "~~"
            return lines

        if typ == "emphasis":
            lines = self.render(rnode)
            char = emphasis_marker(self, rnode)
            lines[0] = char + lines[0]
            lines[-1] = lines[-1] + char
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
            lines = self.render_child(child)
            rst.extend(lines)

        return rst

    def render_child(self, rnode) -> List[str]:
        """
        Return the lines of `rnode`, and keep them in its parent, so that render() renders it once,
        because rendering can write a file, such as the image of math.
        touches_letter() renders the node next to an emphasis this way before render() reaches it.
        """
        cache = rnode.parent.child_lines
        key = id(rnode.node)
        if key not in cache:
            cache[key] = self.render_node(rnode)
        return cache[key]

    def render_tight_item(self, rnode) -> List[str]:
        """
        Render the blocks of an item of a tight list, in which a blank line between two blocks makes the list loose.
        The last block needs no blank line after it, because the next item closes it.
        """
        children = rnode.node["children"]
        rst = []
        for n in children[:-1]:
            lines = self.render_node(rnode.new_child(n))
            rst.extend(end_block_in_tight_item(lines))

        lines = self.render_node(rnode.new_child(children[-1]))
        rst.extend(strip_paragraph_end(lines))

        # An empty item still needs a line for its bullet.
        if len(rst) == 0:
            return [""]
        return rst

    def msg(self, *args):
        msg(*args)


def paragraph_lines(parts: List[str]) -> List[str]:
    """
    Join the rendered parts of a paragraph and split them into lines.
    The first line starts no block, as escape_line_start() writes it, because a platform can write a part as text,
    such as "# a" of the code span `# a` on simple.
    A line after the first that would start a block, such as "# a" or "---", is indented by 4 spaces,
    because no block starts after 4 spaces in a paragraph.
    """
    lines = "".join(parts).split("\n")
    rst = [escape_line_start(lines[0])]
    for line in lines[1:]:
        if paragraph_breaker.match(line):
            line = indent(line)
        rst.append(line)
    return rst


def escape_block_start(line: str) -> str:
    r"""
    Return `line`, a line after the first of a paragraph, with a backslash before the char that would start a block,
    such as "\# a" for "# a", "\> a" for "> a" or "1\. a" for "1. a", so that the line stays in the paragraph.
    Return it as it is if it starts no block.
    """
    if not paragraph_breaker.match(line):
        return line
    return block_start_prefix.sub(r"\g<0>\\", line, count=1)


def escape_line_start(text: str) -> str:
    r"""
    Return the text at the start of a line that starts a block, such as the first line of a paragraph or the text of
    a list item, without the spaces at its start, and with a backslash before the last char of a block marker at its
    start, such as "\# x" for "# x", "1\. Intro" for "1. Intro" or "--\-" for "---".
    4 spaces would start a code block, and a block marker would start its block.
    """
    text = text.lstrip(" \t")
    m = line_block_marker.match(text)
    if m is None:
        return text
    end = m.end()
    return text[: end - 1] + "\\" + text[end - 1 :]


def lists_before(rnode) -> int:
    """
    Return how many lists of the kind of the list `rnode`, ordered or not, come right before it among its siblings.
    """
    if rnode.parent is None:
        return 0

    siblings = rnode.parent.node["children"]
    i = next(k for k, n in enumerate(siblings) if n is rnode.node)
    count = 0
    for n in reversed(siblings[:i]):
        same_kind = n["type"] == "list" and n["ordered"] == rnode.node["ordered"]
        if not same_kind:
            break
        count += 1
    return count


def escape_marker(m: re.Match[str]) -> str:
    r"""
    Return the match of `literal_markers`: a backslash escape as it is, a "*" with a backslash before it,
    or a "`" as "&#96;", because in the text of a link mistune starts a code span at "\`" too.
    """
    s = m.group(0)
    if s.startswith("\\"):
        return s
    if s == "`":
        return "&#96;"
    return "\\" + s


def escape_text(text: str) -> str:
    r"""
    Return the plain text `text` as markdown that shows it, with each char of `text_specials` escaped,
    such as "\*a\*" for "*a*".
    An "&" is kept, because mistune keeps a character reference in the title of a link as written, such as "&amp;".
    """
    emphasis_pair = has_emphasis_pair(text)
    escape = partial(escape_text_char, emphasis_pair=emphasis_pair)
    return text_specials.sub(escape, text)


def escape_plain(text: str) -> str:
    r"""
    Return the plain chars `text`, such as the code of a code span that simple writes as text, as markdown that shows
    them in a line, with each char of `text_specials` escaped, and with a backslash before an "&" that would start
    a character reference, such as "\*a\*" for "*a*" or "\&amp;" for "&amp;".
    A run of "_" is kept only with a letter or digit on both sides, because a run beyond `text` in the line can pair with it.
    """
    escape = partial(escape_text_char, emphasis_pair=True)
    return plain_specials.sub(escape, text)


def escape_text_char(m: re.Match[str], emphasis_pair: bool) -> str:
    r"""
    Return the match of `text_specials` or of `plain_specials` escaped, such as "\_" for "_" or "\&" for "&".
    A "`" is written as "&#96;", because in the text of a link mistune starts a code span at "\`" too.
    A run of "_" with a letter or digit on both sides, such as in "a_b", is kept, because it opens or closes no emphasis.
    Every run of "_" is kept if `emphasis_pair` is False, because then no run of "_" in the text starts an emphasis.
    """
    c = m.group(0)
    if c == "`":
        return "&#96;"
    if c[0] == "_":
        before = m.string[m.start() - 1 : m.start()]
        after = m.string[m.end() : m.end() + 1]
        inside_word = before.isalnum() and after.isalnum()
        if inside_word or not emphasis_pair:
            return c
        return "\\_" * len(c)
    return "\\" + c


def has_emphasis_pair(text: str) -> bool:
    """
    Return whether a run of "_" in the plain text `text` can open an emphasis, and a later run can close one.
    As mistune reads a run of "_", it can open an emphasis if no letter or digit is before it and no space is after it,
    and close one if no letter or digit is after it and no space is before it.
    The char beyond either end of `text` counts as punctuation, such as the "[" that md2zhihu writes before the text of a link.
    """
    opened = False
    for m in underscore_runs.finditer(text):
        before = text[m.start() - 1 : m.start()]
        after = text[m.end() : m.end() + 1]
        can_open = not before.isalnum() and not after.isspace()
        can_close = not after.isalnum() and not before.isspace()
        if opened and can_close:
            return True
        if can_open:
            opened = True
    return False


def emphasis_marker(mdrender, rnode) -> str:
    """
    Return the char that marks the emphasis `rnode`: "_" if it starts or ends a strong emphasis or an emphasis marked
    with "*", else "*".
    With "*" for both, their markers would join into one run, which a parser reads another way:
    "**foo**" for "*_foo_*" is a strong emphasis, and "***x***" for "**_x_**" is an emphasis that holds a strong emphasis.
    But "_" opens or closes nothing next to a letter or digit, such as the "_" after "b" in "*_b_c*" for "_*b*c_".
    So an emphasis whose other marker touches one takes "*", and its parent emphasis takes "_".
    """
    if touches_letter(mdrender, rnode):
        return "*"

    if touches_parent_marker(rnode):
        parent = rnode.parent
        if parent.node["type"] == "emphasis" and emphasis_marker(mdrender, parent) == "_":
            return "*"
        return "_"

    for n in inline_children(rnode.node):
        if n["type"] == "emphasis" and touches_letter(mdrender, rnode.new_child(n)):
            return "_"
    return "*"


def touches_parent_marker(rnode) -> bool:
    """
    Return whether the node `rnode` starts or ends its parent, a strong emphasis or an emphasis.
    """
    parent = rnode.parent
    if parent is None or parent.node["type"] not in ("strong", "emphasis"):
        return False

    siblings = inline_children(parent.node)
    return siblings[0] is rnode.node or siblings[-1] is rnode.node


def touches_letter(mdrender, rnode) -> bool:
    """
    Return whether the node `rnode` starts or ends its parent, a strong emphasis or an emphasis, but not both,
    and its other end touches a letter or digit, such as the end of "*b*" in "_*b*c_".
    The node next to it is rendered to find the char, because a platform can write a node as plain text,
    such as a code span on weibo.
    """
    if not touches_parent_marker(rnode):
        return False

    siblings = inline_children(rnode.parent.node)
    if len(siblings) == 1:
        return False

    if siblings[0] is rnode.node:
        neighbor = siblings[1]
        side = 0
    else:
        neighbor = siblings[-2]
        side = -1

    # A strong emphasis or an emphasis starts and ends with its marker, and rendering it early could render `rnode` again.
    if neighbor["type"] in ("strong", "emphasis"):
        return False

    lines = mdrender.render_child(rnode.parent.new_child(neighbor))
    text = "".join(lines)
    if text == "":
        return False
    return text[side].isalnum()


def inline_children(node) -> List[dict]:
    """
    Return the children of `node` without the empty texts,
    which mistune leaves where it uses up a run of markers, such as on both sides of "_foo_" in "*_foo_*".
    """
    children = []
    for n in node["children"]:
        is_empty_text = n["type"] == "text" and n["text"] == ""
        if not is_empty_text:
            children.append(n)
    return children


def end_block_in_tight_item(lines: List[str]) -> List[str]:
    """
    Return the lines of a block in an item of a tight list, which another block of the item follows.
    A block that its last line closes, such as a fenced code block, needs no blank line after it.
    A quote ends with an empty quote line instead, such as ">", so that the next block does not continue its paragraph.
    Any other block keeps the blank line after it, because the next block would continue it,
    such as the paragraph of the image that a code block converts to.
    """
    stripped = strip_paragraph_end(lines)
    if len(stripped) == 0:
        return lines
    last = stripped[-1]

    if block_closing_line.fullmatch(last):
        return stripped

    quote = quote_markers.match(last)
    if quote is not None:
        return stripped + [quote.group(0)]

    return lines


def link_title(title: Optional[str]) -> str:
    r"""
    Return the title of a link or an image as written after its URL, such as ` "Figure 1"`, or "" without a title.
    mistune removes the backslash escapes from a title, so a backslash and a double quote in it are escaped again.
    A title can span lines, and each line after the first is escaped as a line of a paragraph, such as "\# x" for "# x".
    """
    if title is None:
        return ""
    escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    lines = escaped.split("\n")
    lines = lines[:1] + [escape_block_start(x) for x in lines[1:]]
    return ' "' + "\n".join(lines) + '"'


def link_destination(url: str) -> str:
    r"""
    Return `url` as written as the destination of a link or an image, which a markdown parser reads to its end.
    Each space or control character is percent-encoded, and so is each parenthesis, if they do not pair up, such as in "x).png".
    Each backslash is percent-encoded too, because a markdown parser reads a backslash before a punctuation as an escape,
    such as "x\_.png" as "x_.png". md2zhihu builds such a URL from a file name, which keeps the backslash.
    An "&" that starts a character reference is written as "&amp;", such as "&amp;copy;" for "&copy;".
    mistune reads "&amp;" back as "&", but it reads "\&copy;" in a URL as "©".
    """
    url = url_breakers.sub(percent_encode, url)
    url = url.replace("\\", "%5C")
    url = char_reference_start.sub("&amp;", url)

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
