from typing import List
from urllib.parse import unquote

from ..renderer.md_render import link_destination
from ..renderer.md_render import link_title
from ..types import RefDict


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

        if ref.title is None:
            txt = ref_id
        else:
            txt = ref.title

        ref_lines.append("- {id} : [{url_text}]({url})".format(id=txt, url_text=url_text, url=url))

        #  disable paragraph list in weibo
        if platform != "weibo":
            ref_lines.append("")

    return ref_lines


def render_ref_definitions(refs: RefDict) -> List[str]:
    """Return the definition of each reference, sorted by name, such as `[grpc]: https://grpc.io "gRPC"`."""
    lines: List[str] = []
    for ref_id in sorted(refs):
        ref = refs[ref_id]
        url = link_destination(ref.url)
        title = link_title(ref.title)
        lines.append("[{id}]: {url}{title}".format(id=ref_id, url=url, title=title))
    return lines
