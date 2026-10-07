"""
Parse markdown with mistune 3 into the AST that md2zhihu renders.
This is the only module that knows mistune 3's token format.
"""

import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from urllib.parse import unquote

import mistune
from mistune.core import InlineState
from mistune.inline_parser import InlineParser
from mistune.plugins.table import table_in_list
from mistune.plugins.table import table_in_quote

from ..types import ASTNode
from ..types import ASTNodes

# A mistune 3 token.
Token = Dict[str, Any]

# For each token type: the mistune 3 attributes that md2zhihu reads, and md2zhihu's field name for each.
attr_fields = {
    "link": {"url": "link"},
    "heading": {"level": "level"},
    "list": {"ordered": "ordered"},
    "table_cell": {"align": "align"},
}


def new_markdown() -> mistune.Markdown:
    """
    Build a mistune 3 parser that returns tokens instead of HTML.
    """

    # mistune registers no name for table_in_list and table_in_quote, so the functions are passed.
    md = mistune.create_markdown(
        renderer="ast",
        plugins=["strikethrough", "table", table_in_list, table_in_quote],
    )
    md.inline.register("link", None, parse_link)
    return md


def parse(text: str) -> ASTNodes:
    """
    Parse markdown with mistune 3 into the AST that md2zhihu renders.
    """

    md = new_markdown()
    tokens, _ = md.parse(text)
    assert isinstance(tokens, list)
    return adapt(tokens)


def parse_link(inline: InlineParser, m: re.Match[str], state: InlineState) -> Optional[int]:
    """
    Run mistune's link rule. On an image it builds, keep the alt text as written.
    """

    count = len(state.tokens)
    end = inline.parse_link(m, state)
    if end is None:
        return None

    new_tokens = state.tokens[count:]
    if len(new_tokens) == 1 and new_tokens[0]["type"] == "image":
        # mistune keeps the alt text only as parsed tokens, but md2zhihu writes it as written, such as "a *b*".
        alt_end = closing_bracket(state.src, m.end())
        new_tokens[0]["alt"] = state.src[m.end() : alt_end]

    return end


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
