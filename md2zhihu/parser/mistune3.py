"""
Parse markdown with mistune 3 into the AST that md2zhihu renders.
This is the only module that knows mistune 3's token format.

The text fields of the AST hold:
- markdown as written, with its backslash escapes and character references: the text of a text node,
  the name of a reference in a ref_label node, the alt of an image, and the TeX of math;
- plain chars: the code of a code span, whose line endings are spaces, and the code and the info of a code block;
- chars without the backslash escapes, but with the character references as written: the title of a link, an image or
  a ref_label node;
- a percent-encoded URL: the URL of a link, an image or a ref_label node.
"""

import re
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import mistune
from mistune.block_parser import BlockParser
from mistune.core import BlockState
from mistune.core import InlineState
from mistune.helpers import parse_link_href
from mistune.helpers import parse_link_title
from mistune.helpers import unescape_char
from mistune.inline_parser import InlineParser
from mistune.plugins.table import table_in_list
from mistune.plugins.table import table_in_quote
from mistune.util import escape_url
from mistune.util import unikey

from ..renderer.md_render import escape_text
from ..types import ASTNode
from ..types import ASTNodes
from ..types import Ref
from ..types import RefDict

# A mistune 3 token.
Token = Dict[str, Any]

# For each token type: the mistune 3 attributes that md2zhihu reads, and md2zhihu's field name for each.
attr_fields = {
    "link": {"url": "link", "title": "title"},
    "ref_label": {"url": "link", "title": "title"},
    "heading": {"level": "level"},
    "list": {"ordered": "ordered", "start": "start"},
    "table_cell": {"align": "align"},
}

# The forms of an undefined reference that md2zhihu warns about: "[text][label]" and "[label][]".
# A lone "[label]" is usually plain text, so it gets no warning.
undefined_ref_forms = re.compile(r"\[[^\[\]]*\]\[[^\[\]]*\]")

# md2zhihu's math, "$$...$$" or "$...$", which may span lines and have spaces inside, such as "$ x $".
# A "$" followed by a digit does not close math, so "costs $5 and $6" has no math.
# A "$...$" holds a "$" only in a backslash escape, such as "\$", and a "$" after a space closes only math that starts
# with a space. So in "costs $5 and $6; calculate $x$." only "x" is math.
math_pattern = re.compile(
    r"\$\$([^$][\s\S]*?)\$\$"  # "$$...$$"
    r"|\$((?=\s)(?:[^$\\]|\\[\s\S])+"  # "$...$" that starts with a space
    r"|(?:[^$\\]|\\[\s\S])*(?:[^\s$\\]|\\[\s\S])"  # "$...$" that ends with a char other than a space, or with an escape
    r")\$(?!\d)"
)

# A code span, whose "$$", such as in `$$`, is not math.
code_span = re.compile(r"(`+)[\s\S]*?\1")

# A line of only "$$", which opens math on the lines after it.
math_opening_line = r"^ {0,3}\$\$[ \t]*$"


def new_markdown() -> mistune.Markdown:
    """
    Build a mistune 3 parser that returns tokens instead of HTML.
    """

    # mistune registers no name for table_in_list and table_in_quote, so the functions are passed.
    md = mistune.create_markdown(
        renderer="ast",
        plugins=["strikethrough", "table", table_in_list, table_in_quote],
    )
    md.inline.register("escape", None, parse_escape)
    md.inline.register("link_close", r"\]", parse_link_close)
    md.inline.register("auto_link", None, parse_auto_link)
    md.inline.register("auto_email", None, parse_auto_email)
    # mistune skips plain text fast only if it knows the chars that start each rule.
    md.inline.register("math", r"\$", parse_math, start_chars="$")
    md.block.register("math_lines", math_opening_line, parse_math_lines)
    md.block.insert_rule(md.block.block_quote_rules, "math_lines")
    md.block.insert_rule(md.block.list_rules, "math_lines")
    md.before_render_hooks.append(lambda md, state: join_math_paragraphs(state.tokens))
    return md


def parse(
    text: str, refs: RefDict, populate_reference: bool, ref_name: Optional[Callable[[str, Ref], str]] = None
) -> Tuple[ASTNodes, RefDict, List[str]]:
    """
    Parse markdown with mistune 3 into the AST that md2zhihu renders.

    `refs` maps md2zhihu's name of each reference from outside the text to its definition.
    A definition in the text wins over the reference of the same name.
    With `populate_reference` False, a link to a reference is written as a full reference to its name, such as `[text][name]`.
    `ref_name` returns the name in the output of a used reference, from its name and its definition,
    such as "r-2" for an "r" that the output already has for another reference. Without it, each name stays.

    Return the AST, the references that it uses by their names in the output, and the undefined references in it.
    """

    state = BlockState()
    state.env["populate_reference"] = populate_reference
    state.env["ref_name"] = ref_name
    state.env["used_refs"] = {}
    state.env["undefined_refs"] = []

    md = new_markdown()
    # mistune reads the definitions in the text with the blocks, before it reads any link, and then refs fill in the rest.
    md.before_render_hooks.append(lambda md, state: add_refs(state.env["ref_links"], refs))
    tokens, _ = md.parse(text, state)
    assert isinstance(tokens, list)
    return adapt(tokens), state.env["used_refs"], state.env["undefined_refs"]


def add_refs(ref_links: Dict[str, Dict[str, Any]], refs: RefDict) -> None:
    """
    Add md2zhihu's references to mistune 3's `ref_links`, so that mistune resolves them.
    A name that the text defines keeps the definition in the text.
    """

    for name, ref in refs.items():
        key = unikey(name)
        if key not in ref_links:
            # mistune upper-cases its key, so its entry keeps the name as written in "label", as for a definition in the text.
            ref_links[key] = {"url": ref.url, "title": ref.title, "label": name}


def parse_ref(value: str) -> Optional[Ref]:
    """
    Parse `value` as the text after "]:" of a link reference definition: a URL and an optional title,
    such as `https://a.com "A"` or `<a b.pdf>`. Return None if `value` is not one, such as an empty text.
    The result is what mistune keeps of such a definition in the text.
    """

    url, url_end = parse_link_href(value, 0, block=True)
    if url is None:
        return None
    assert url_end is not None

    title, title_end = parse_link_title(value, url_end, len(value))
    end = url_end
    if title_end is not None:
        end = title_end
    if value[end:].strip() != "":
        return None

    if title == "":
        title = None
    url = unescape_char(url)
    url = escape_url(url)
    return Ref(url, title)


def parse_escape(inline: InlineParser, m: re.Match[str], state: InlineState) -> int:
    r"""
    Keep a backslash escape such as "\*" as written, because md2zhihu writes text as it is.
    As with mistune's rule, the escaped character starts no emphasis.
    """

    inline.process_text(m.group(0), state, parse_emphasis=False)
    return m.end()


def parse_link_close(inline: InlineParser, m: re.Match[str], state: InlineState) -> int:
    """
    Run mistune's rule of a "]", which closes the last "[" or "![" into a link or an image, if it can.
    md2zhihu registers the rule for one "]" instead of mistune's run of "]",
    so each call closes at most one bracket: the last one in `state.brackets`.
    On an image it builds, keep the alt text as written.
    Record the references that md2zhihu defines and the links use, and the undefined references.
    """

    if len(state.brackets) == 0:
        # No "[" is open, so mistune keeps the "]" as text.
        return inline.parse_link_close(m, state)

    opener = state.brackets[-1]
    end = inline.parse_link_close(m, state)
    # The token of the "[" becomes the link or the image, or stays text if the bracket closes nothing.
    tok = state.tokens[opener.token_index]

    # In an HTML link, such as `<a href="u">[x][r]</a>`, mistune makes no link, even of a defined reference.
    if tok["type"] == "text" and not state.in_link:
        # `opener.start` is the position after the "[", also for "![".
        form = undefined_ref_forms.match(state.src, opener.start - 1)
        if form is not None:
            state.env["undefined_refs"].append(form.group(0))

    if tok["type"] == "image":
        # mistune keeps the alt text only as parsed tokens, but md2zhihu writes it as written, such as "a *b*".
        tok["alt"] = state.src[opener.start : m.start()]

    if tok["type"] == "link" and "ref" in tok:
        use_ref(state, opener.token_index)

    return end


def use_ref(state: InlineState, index: int) -> None:
    """
    Record the reference that the link `state.tokens[index]` uses, by its name in the output.
    With populate_reference False, write the link as a full reference to that name, such as "[text][name]",
    also for a shortcut "[name]" or a collapsed "[name][]".
    """

    ref = state.env["ref_links"][state.tokens[index]["ref"]]
    used = Ref(ref["url"], ref.get("title"))
    name = ref["label"]
    if state.env["ref_name"] is not None:
        name = state.env["ref_name"](name, used)
    state.env["used_refs"][name] = used
    if not state.env["populate_reference"]:
        # The text keeps its tokens, so that md2zhihu converts the math in it, such as in "[$x$][name]".
        # The renderer escapes the text, such as "foo\*" for "foo*", but a definition matches a name without decoding its
        # escapes, so the name follows the text, in a token that the renderer writes as it is, such as in "[foo\*][foo*]".
        # The token also holds the definition, for a converter that gets a part of the output without the definitions at
        # its end, such as a table.
        opening = {"type": "text", "raw": "["}
        middle = {"type": "text", "raw": "]["}
        label = {"type": "ref_label", "raw": name, "attrs": {"url": used.url, "title": used.title}}
        closing = {"type": "text", "raw": "]"}
        source = [opening] + state.tokens[index]["children"] + [middle, label, closing]
        for tok in source:
            if tok["type"] == "text":
                # With "_emphasis" False, no emphasis crosses the brackets, as with a link.
                tok["_emphasis"] = False
        state.tokens[index : index + 1] = source


def parse_auto_link(inline: InlineParser, m: re.Match[str], state: InlineState) -> int:
    """
    Run mistune's rule of an autolink, such as "<http://a.com/x_y>", and keep the text of the link as markdown.
    """

    count = len(state.tokens)
    end = inline.parse_auto_link(m, state)
    escape_autolink_text(state.tokens[count:])
    return end


def parse_auto_email(inline: InlineParser, m: re.Match[str], state: InlineState) -> int:
    """
    Run mistune's rule of an email autolink, such as "<a_b@c.com>", and keep the text of the link as markdown.
    """

    count = len(state.tokens)
    end = inline.parse_auto_email(m, state)
    escape_autolink_text(state.tokens[count:])
    return end


def escape_autolink_text(tokens: List[Token]) -> None:
    r"""
    Escape each char that starts inline markdown in the text of each link in `tokens`, such as "_" in "http://a.com/x_y".
    mistune keeps the text of an autolink as plain chars, but md2zhihu keeps every other text as written,
    and writes an autolink as a link, such as "[http://a.com/x\_y](http://a.com/x_y)".
    """

    for tok in tokens:
        if tok["type"] != "link":
            continue
        text = tok["children"][0]
        text["raw"] = escape_text(text["raw"])


def parse_math(inline: InlineParser, m: re.Match[str], state: InlineState) -> Optional[int]:
    """
    Read md2zhihu's math at a "$". It is a block if it starts its paragraph and ends a line.
    The math text stays as written, because the escape and emphasis rules never see it.
    """

    math = math_pattern.match(state.src, m.start())
    if math is None:
        return None

    text = math.group(1)
    if text is None:
        text = math.group(2)

    # mistune parses the text of a strikethrough on its own, with a depth of 1,
    # so the start of that text is not the start of the paragraph.
    starts_paragraph = math.start() == 0 and state.depth == 0
    ends_line = math.end() == len(state.src) or state.src.startswith("\n", math.end())
    if starts_paragraph and ends_line:
        state.append_token({"type": "math_block", "raw": text})
    else:
        state.append_token({"type": "math_inline", "raw": text})
    return math.end()


def parse_math_lines(block: BlockParser, m: re.Match[str], state: BlockState) -> Optional[int]:
    """
    Read the math that a line of only "$$" opens, up to the end of the line that closes it, as paragraph text.
    So mistune's block parser reads no line in the math as a block, such as "=" as the underline of a heading.
    parse_math then reads the math in the paragraph.
    """

    if math_is_open(state.tokens):
        # The line closes the math that the paragraphs before it open, and join_math_paragraphs joins them.
        return None

    start = state.src.index("$$", m.start())
    math = math_pattern.match(state.src, start)
    if math is None:
        return None

    end = state.find_line_end_at(math.end())
    state.add_paragraph(state.get_text(end))
    return end


def join_math_paragraphs(tokens: List[Token]) -> None:
    """
    Join each paragraph that opens "$$" math with the paragraphs after it, up to the one that closes the math.
    mistune's block parser splits such math at a blank line, and this runs before mistune parses the inline text.
    If no paragraph closes the math, nothing is joined, and the "$$" is text.
    """

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "children" in tok:
            join_math_paragraphs(tok["children"])

        end = closing_math_paragraph(tokens, i)
        if end is None:
            i += 1
            continue

        for following in tokens[i + 1 : end + 1]:
            if following["type"] == "paragraph":
                tok["text"] = tok["text"].rstrip("\n") + "\n\n" + following["text"]
        del tokens[i + 1 : end + 1]


def closing_math_paragraph(tokens: List[Token], i: int) -> Optional[int]:
    """
    Return the index of the paragraph that closes the "$$" math that the paragraph `tokens[i]` opens, or None.
    Only paragraphs and blank lines may come between them.
    """

    if tokens[i]["type"] != "paragraph":
        return None

    text = tokens[i]["text"]
    if not opens_math(text):
        return None

    for j in range(i + 1, len(tokens)):
        typ = tokens[j]["type"]
        if typ == "blank_line":
            continue
        if typ != "paragraph":
            return None

        text += "\n\n" + tokens[j]["text"]
        if not opens_math(text):
            return j

    return None


def math_is_open(tokens: List[Token]) -> bool:
    """
    Tell whether the last paragraphs of `tokens`, with only blank lines between them, have a "$$" that is not closed.
    """

    texts: List[str] = []
    for tok in reversed(tokens):
        if tok["type"] == "blank_line":
            continue
        if tok["type"] != "paragraph":
            break
        texts.insert(0, tok["text"])

    return opens_math("\n\n".join(texts))


def opens_math(text: str) -> bool:
    """
    Tell whether the text has a "$$" that no math in the text closes.
    """

    plain = code_span.sub("", text)
    rest = math_pattern.sub("", plain)
    return "$$" in rest


def adapt(tokens: List[Token]) -> ASTNodes:
    """
    Convert mistune 3 tokens to the nodes that mistune 2 builds.
    """

    nodes: ASTNodes = []
    for tok in tokens:
        if tok["type"] == "blank_line":
            continue

        node = adapt_token(tok)

        # mistune 3 splits text at line ends and at unmatched emphasis markers, which mistune 2 keeps in one text node.
        follows_text = len(nodes) > 0 and nodes[-1]["type"] == "text"
        if node["type"] == "text" and follows_text:
            nodes[-1]["text"] += node["text"]
            continue

        nodes.append(node)

    return nodes


def adapt_token(tok: Token) -> ASTNode:
    typ = tok["type"]

    if typ == "softbreak":
        return {"type": "text", "text": "\n"}
    if typ == "image":
        return adapt_image(tok)
    if typ == "block_code":
        return adapt_block_code(tok)
    if typ == "block_html":
        return adapt_block_html(tok)
    if typ == "list_item":
        return adapt_list_item(tok)

    node: ASTNode = {"type": typ}

    attrs = tok.get("attrs", {})
    for attr, field in attr_fields.get(typ, {}).items():
        node[field] = attrs.get(attr)

    # Only a list has "tight": no blank line separates its items or the blocks in an item.
    if "tight" in tok:
        node["tight"] = tok["tight"]

    if "raw" in tok:
        node["text"] = tok["raw"]

    if "children" in tok:
        node["children"] = adapt(tok["children"])

    if typ == "link" and len(node["children"]) == 0:
        # MDRender needs a child in a link. mistune 2 gives an empty link text, such as in "[](u)", an empty text.
        node["children"] = [{"type": "text", "text": ""}]

    return node


def adapt_image(tok: Token) -> ASTNode:
    attrs = tok["attrs"]
    # As for a link, "src" is the URL that mistune 3 percent-encodes, such as "%E5%9B%BE%E7%89%87/a.png" for "图片/a.png".
    return {"type": "image", "src": attrs["url"], "alt": tok["alt"], "title": attrs.get("title")}


def adapt_block_code(tok: Token) -> ASTNode:
    text = tok["raw"]
    if not text.endswith("\n"):
        # MDRender drops the last character of a code block, which mistune 2 always makes a newline.
        text += "\n"

    info = tok.get("attrs", {}).get("info")
    return {"type": "block_code", "text": text, "info": info}


def adapt_block_html(tok: Token) -> ASTNode:
    # mistune 2 does not end an HTML block with a newline.
    text = tok["raw"].removesuffix("\n")
    return {"type": "block_html", "text": text}


def adapt_list_item(tok: Token) -> ASTNode:
    children = adapt(tok["children"])
    if len(children) == 0:
        # MDRender needs a child in a list item. mistune 2 gives an empty item an empty block_text.
        children = [{"type": "block_text", "children": [{"type": "text", "text": ""}]}]

    return {"type": "list_item", "children": children}
