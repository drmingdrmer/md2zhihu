import re
from typing import List
from urllib.parse import unquote

from ..renderer.md_render import escape_text
from ..renderer.md_render import link_destination
from ..renderer.md_render import link_title
from ..types import RefDict

# A block marker at the start of the text of a list item, which would start a block in the item:
# an ATX heading, a quote, a bullet list or an ordered list, such as "# x", "> q", "- x" or "1. x".
item_block_marker = re.compile(r"#{1,6}(?=[ \t]|$)|>|[-+*](?=[ \t]|$)|\d{1,9}[.)](?=[ \t]|$)")

# An "&" that starts a character reference, such as "&copy;" or "&#169;", which a markdown parser reads as one char.
char_reference_start = re.compile(r"&(?=#[0-9]{1,7};|#[xX][0-9a-fA-F]{1,6};|[A-Za-z][A-Za-z0-9]*;)")


# TODO: move to renderer module?
def render_ref_list(refs: RefDict, platform: str) -> List[str]:
    if len(refs) == 0:
        return []

    ref_lines: List[str] = ["", "Reference:", ""]
    for ref_id in sorted(refs):
        ref = refs[ref_id]
        url = link_destination(ref.url)
        # mistune percent-encodes a URL, such as "图片" to "%E5%9B%BE%E7%89%87", but the text shows it as written.
        url_text = unquote(ref.url)
        url_text = escape_text(url_text)
        # The URL holds plain chars, so an "&", such as one from "%26", shows as itself, not as a reference.
        url_text = char_reference_start.sub(r"\\&", url_text)

        if ref.title is None:
            # A name is a label as written, such as "foo\!", but mistune removes the backslash escapes from a title.
            txt = ref_id
        else:
            txt = escape_text(ref.title)
        txt = escape_item_start(txt)

        ref_lines.append("- {id} : [{url_text}]({url})".format(id=txt, url_text=url_text, url=url))

        #  disable paragraph list in weibo
        if platform != "weibo":
            ref_lines.append("")

    return ref_lines


def escape_item_start(text: str) -> str:
    r"""
    Return the text of a list item without the spaces at its start, and with a backslash before the last char
    of a block marker at its start, such as "\# x" for "# x" or "1\. Intro" for "1. Intro".
    Right after "- ", 4 spaces would start a code block, and a block marker would start its block in the item.
    """
    text = text.lstrip(" \t")
    m = item_block_marker.match(text)
    if m is None:
        return text
    end = m.end()
    return text[: end - 1] + "\\" + text[end - 1 :]


def render_ref_definitions(refs: RefDict) -> List[str]:
    """Return the definition of each reference, sorted by name, such as `[grpc]: https://grpc.io "gRPC"`."""
    lines: List[str] = []
    for ref_id in sorted(refs):
        ref = refs[ref_id]
        url = link_destination(ref.url)
        title = link_title(ref.title)
        lines.append("[{id}]: {url}{title}".format(id=ref_id, url=url, title=title))
    return lines
