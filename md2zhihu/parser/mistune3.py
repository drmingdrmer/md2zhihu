"""
Parse markdown with mistune 3 into the AST that md2zhihu renders.
This is the only module that knows mistune 3's token format.
"""

import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from urllib.parse import unquote

import mistune
from mistune.block_parser import BlockParser
from mistune.core import BlockState
from mistune.core import InlineState
from mistune.inline_parser import InlineParser
from mistune.plugins.table import table_in_list
from mistune.plugins.table import table_in_quote
from mistune.util import unikey

from ..types import ASTNode
from ..types import ASTNodes
from ..types import RefDict

# A mistune 3 token.
Token = Dict[str, Any]

# For each token type: the mistune 3 attributes that md2zhihu reads, and md2zhihu's field name for each.
attr_fields = {
    "link": {"url": "link", "title": "title"},
    "heading": {"level": "level"},
    "list": {"ordered": "ordered", "start": "start"},
    "table_cell": {"align": "align"},
}

# The forms of an undefined reference that md2zhihu warns about: "[text][label]" and "[label][]".
# A lone "[label]" is usually plain text, so it gets no warning.
undefined_ref_forms = re.compile(r"\[[^\[\]]*\]\[[^\[\]]*\]")

# md2zhihu's math, "$$...$$" or "$...$", which may span lines and have spaces inside, such as "$ x $".
# A "$" followed by a digit does not close math, so "costs $5 and $6" has no math.
math_pattern = re.compile(r"\$\$([^$][\s\S]*?)\$\$|\$([^$][\s\S]*?)\$(?!\d)")

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
    md.block.register("ref_link", None, parse_ref_link)
    md.inline.register("escape", None, parse_escape)
    md.inline.register("link", None, parse_link)
    md.inline.register("math", r"\$", parse_math)
    md.block.register("math_lines", math_opening_line, parse_math_lines)
    md.block.insert_rule(md.block.block_quote_rules, "math_lines")
    md.block.insert_rule(md.block.list_rules, "math_lines")
    md.before_render_hooks.append(lambda md, state: join_math_paragraphs(state.tokens))
    return md


def parse(text: str, refs: RefDict, populate_reference: bool) -> Tuple[ASTNodes, RefDict, List[str]]:
    """
    Parse markdown with mistune 3 into the AST that md2zhihu renders.

    `refs` maps md2zhihu's name of each reference from outside the text to its value, such as `https://a.com "title"`.
    A definition in the text wins over the reference of the same name.
    With `populate_reference` False, a link to a reference keeps its form, such as `[text][name]`.

    Return the AST, the references in `refs` that it uses, and the undefined references in it.
    """

    state = BlockState()
    state.env["populate_reference"] = populate_reference
    state.env["used_refs"] = {}
    state.env["undefined_refs"] = []

    md = new_markdown()
    # mistune reads the definitions in the text with the blocks, before it reads any link, and then refs fill in the rest.
    md.before_render_hooks.append(lambda md, state: add_refs(state.env["ref_links"], refs))
    tokens, _ = md.parse(text, state)
    assert isinstance(tokens, list)
    return adapt(tokens), state.env["used_refs"], state.env["undefined_refs"]


def add_refs(ref_links: Dict[str, Dict[str, str]], refs: RefDict) -> None:
    """
    Add md2zhihu's references to mistune 3's `ref_links`, so that mistune resolves them.
    A name that the text defines keeps the definition in the text.
    """

    for name, value in refs.items():
        key = unikey(name)
        if key not in ref_links:
            ref_links[key] = new_ref_link(name, value)


def new_ref_link(name: str, value: str) -> Dict[str, str]:
    """
    Build mistune 3's entry of the reference `name`, whose value is a URL and an optional title.
    mistune upper-cases its key, so the entry also keeps md2zhihu's name and value, which the output lists.
    """

    return {"url": value.split()[0], "name": name, "value": value}


def parse_ref_link(block: BlockParser, m: re.Match[str], state: BlockState) -> Optional[int]:
    """
    Run mistune's rule for a link reference definition, which reads one only where CommonMark allows it:
    not in code, and not in a paragraph. As in CommonMark, the first definition of a name wins.
    Keep a definition as md2zhihu's reference: its name, and the text after "]:" as its value.
    """

    name = m.group("reflink_1")
    key = unikey(name)
    defined = key in state.env["ref_links"]
    end = block.parse_ref_link(m, state)
    if defined or key not in state.env["ref_links"]:
        # The line is not a definition, such as a line of a paragraph, or an earlier definition has the name.
        return end

    assert end is not None
    # A definition may span lines, such as one with its URL on the next line, but its value is one line.
    value = state.src[m.end() : end].rstrip("\n").replace("\n", " ")
    state.env["ref_links"][key] = new_ref_link(name, value)
    return end


def parse_escape(inline: InlineParser, m: re.Match[str], state: InlineState) -> int:
    r"""
    Keep a backslash escape such as "\*" as written, because md2zhihu writes text as it is.
    As with mistune's rule, the escaped character starts no emphasis.
    """

    inline.process_text(m.group(0), state, parse_emphasis=False)
    return m.end()


def parse_link(inline: InlineParser, m: re.Match[str], state: InlineState) -> Optional[int]:
    """
    Run mistune's link rule. On an image it builds, keep the alt text as written.
    Record the references that md2zhihu defines and the links use, and the undefined references.
    """

    count = len(state.tokens)
    end = inline.parse_link(m, state)
    if end is None:
        form = undefined_ref_forms.match(state.src, m.start())
        if form is not None:
            state.env["undefined_refs"].append(form.group(0))
        return None

    new_tokens = state.tokens[count:]
    if len(new_tokens) == 1 and new_tokens[0]["type"] == "image":
        # mistune keeps the alt text only as parsed tokens, but md2zhihu writes it as written, such as "a *b*".
        alt_end = closing_bracket(state.src, m.end())
        new_tokens[0]["alt"] = state.src[m.end() : alt_end]

    if len(new_tokens) == 1 and new_tokens[0]["type"] == "link" and "ref" in new_tokens[0]:
        text_end = closing_bracket(state.src, m.end())
        use_ref(state, count, state.src[text_end:end])

    return end


def use_ref(state: InlineState, index: int, tail: str) -> None:
    """
    Record the reference that the link `state.tokens[index]` uses.
    With populate_reference False, write the link as its source: "[", its text, and `tail`, such as "][name]".
    """

    ref = state.env["ref_links"][state.tokens[index]["ref"]]
    state.env["used_refs"][ref["name"]] = ref["value"]
    if not state.env["populate_reference"]:
        # The text keeps its tokens, so that md2zhihu converts the math in it, such as in "[$x$][name]".
        opening = {"type": "text", "raw": "["}
        closing = {"type": "text", "raw": tail}
        source = [opening] + state.tokens[index]["children"] + [closing]
        for tok in source:
            if tok["type"] == "text":
                # With "_emphasis" False, no emphasis crosses the brackets, as with a link.
                tok["_emphasis"] = False
        state.tokens[index : index + 1] = source


def closing_bracket(src: str, pos: int) -> int:
    """
    Return the position of the "]" that closes the "[" before ``pos``.
    Nested brackets and backslash escapes are skipped, as mistune does.
    """

    depth = 0
    while True:
        c = src[pos]
        if c == "\\":
            pos += 2
            continue

        if c == "]" and depth == 0:
            return pos

        if c == "[":
            depth += 1
        if c == "]":
            depth -= 1
        pos += 1


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

    # mistune parses a link's text on its own, so the start of that text is not the start of the paragraph.
    starts_paragraph = math.start() == 0 and not state.in_link
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

    if "raw" in tok:
        node["text"] = tok["raw"]

    if "children" in tok:
        node["children"] = adapt(tok["children"])

    return node


def adapt_image(tok: Token) -> ASTNode:
    attrs = tok["attrs"]

    src = attrs["url"]
    is_remote = re.match(r"https?://", src) is not None
    if not is_remote:
        # mistune 3 percent-encodes a URL, but md2zhihu opens a local image by its path, such as "图片/a.png".
        src = unquote(src)

    return {"type": "image", "src": src, "alt": tok["alt"], "title": attrs.get("title")}


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
