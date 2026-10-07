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
    "link": {"url": "link"},
    "heading": {"level": "level"},
    "list": {"ordered": "ordered"},
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
    md.inline.register("link", None, parse_link)
    md.inline.register("math", r"\$", parse_math)
    md.before_render_hooks.append(lambda md, state: join_math_paragraphs(state.tokens))
    return md


def parse(text: str, refs: RefDict, populate_reference: bool) -> Tuple[ASTNodes, RefDict, List[str]]:
    """
    Parse markdown with mistune 3 into the AST that md2zhihu renders.

    `refs` maps md2zhihu's name of each reference to its value, such as `https://a.com "title"`.
    With `populate_reference` False, a link to one of them stays as written, such as `[text][name]`.

    Return the AST, the references in `refs` that it uses, and the undefined references in it.
    """

    state = BlockState()
    state.env["ref_links"] = new_ref_links(refs)
    state.env["populate_reference"] = populate_reference
    state.env["used_refs"] = {}
    state.env["undefined_refs"] = []

    md = new_markdown()
    tokens, _ = md.parse(text, state)
    assert isinstance(tokens, list)
    return adapt(tokens), state.env["used_refs"], state.env["undefined_refs"]


def new_ref_links(refs: RefDict) -> Dict[str, Dict[str, str]]:
    """
    Build mistune 3's `ref_links` from md2zhihu's references, so that mistune resolves them.
    """

    ref_links = {}
    for name, value in refs.items():
        # mistune upper-cases its key, so the entry also keeps md2zhihu's name and value, which the output lists.
        ref_links[unikey(name)] = {"url": value.split()[0], "name": name, "value": value}
    return ref_links


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
        use_ref(state, count, state.src[m.start() : end])

    return end


def use_ref(state: InlineState, index: int, source: str) -> None:
    """
    Record the reference that the link `state.tokens[index]` uses, if md2zhihu defines it.
    With populate_reference False, replace the link with its source text.
    """

    ref = state.env["ref_links"][state.tokens[index]["ref"]]
    if "name" not in ref:
        # md2zhihu did not extract this definition, such as one whose URL is on the next line, so mistune read it from the text.
        return

    state.env["used_refs"][ref["name"]] = ref["value"]
    if not state.env["populate_reference"]:
        # With "_emphasis" False, mistune finds no emphasis in the text, such as in "[*foo*][bar]".
        state.tokens[index] = {"type": "text", "raw": source, "_emphasis": False}


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

    starts_paragraph = math.start() == 0
    ends_line = math.end() == len(state.src) or state.src.startswith("\n", math.end())
    if starts_paragraph and ends_line:
        state.append_token({"type": "math_block", "raw": text})
    else:
        state.append_token({"type": "math_inline", "raw": text})
    return math.end()


def join_math_paragraphs(tokens: List[Token]) -> None:
    """
    Join each paragraph that opens "$$" math with the paragraphs after it, up to the one that closes the math.
    mistune's block parser splits such math at a blank line, and this runs before mistune parses the inline text.
    """

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if "children" in tok:
            join_math_paragraphs(tok["children"])

        following = i + 1
        while following < len(tokens) and tokens[following]["type"] == "blank_line":
            following += 1

        joinable = tok["type"] == "paragraph" and following < len(tokens) and tokens[following]["type"] == "paragraph"
        if not joinable or not opens_math(tok["text"]):
            i += 1
            continue

        tok["text"] = tok["text"].rstrip("\n") + "\n\n" + tokens[following]["text"]
        del tokens[i + 1 : following + 1]


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
