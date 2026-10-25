from typing import List
from urllib.parse import unquote

from ..types import RefDict
from .md_render import char_reference_start
from .md_render import escape_block_start
from .md_render import escape_line_start
from .md_render import escape_text
from .md_render import link_destination
from .md_render import link_title


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
        txt = escape_line_start(txt)

        item = "- {id} : [{url_text}]({url})".format(id=txt, url_text=url_text, url=url)
        # A title can span lines. Each line after the first is indented into the item, and starts no block, such as "# x".
        lines = item.split("\n")
        ref_lines.append(lines[0])
        ref_lines.extend("  " + escape_block_start(x) for x in lines[1:])

        #  disable paragraph list in weibo
        if platform != "weibo":
            ref_lines.append("")

    return ref_lines


def render_ref_definitions(refs: RefDict) -> List[str]:
    """
    Return the definition of each reference, sorted by name, such as `[grpc]: https://grpc.io "gRPC"`.
    An empty URL is written as "<>", because a definition without a URL is not a definition.
    """
    lines: List[str] = []
    for ref_id in sorted(refs):
        ref = refs[ref_id]
        url = link_destination(ref.url)
        if url == "":
            url = "<>"
        title = link_title(ref.title)
        lines.append("[{id}]: {url}{title}".format(id=ref_id, url=url, title=title))
    return lines
