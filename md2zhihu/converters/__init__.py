import json
import os
from typing import Any
from typing import List
from typing import Optional

import k3down2
import k3proc

from ..asset import save_image_to_asset_dir
from ..asset import save_linked_file_to_asset_dir
from ..errors import MissingToolError
from ..errors import RenderError
from ..renderer import MDRender
from ..renderer import RenderNode
from ..renderer.md_render import inline_children
from ..utils import asset_fn
from ..utils import code_fence
from ..utils import escape
from ..utils import fwrite


def code_join(n: dict) -> str:
    lang = n["info"] or ""
    lines = n["text"][:-1].split("\n")
    fence = code_fence(n["text"])
    txt = "\n".join([fence + lang] + lines + [fence, ""])
    return txt


def to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape(n["text"])]


def typ_text_to_jpg(mdrender: "MDRender", typ: str, txt: str, opt: Optional[dict] = None) -> List[str]:
    d = k3down2_convert(mdrender, typ, txt, "jpg", opt=opt)
    # One text can make different images, such as x in $x$ and in $$x$$, so the name also has the converter.
    fn = asset_fn(txt, "jpg", conversion_key(typ, opt))
    fwrite(mdrender.conf.asset_output_dir, fn, d)

    return [r"![]({})".format(mdrender.conf.img_url(fn)), ""]


def k3down2_convert(mdrender: "MDRender", typ: str, txt: str, output_typ: str, opt: Optional[dict] = None) -> Any:
    """
    Return what k3down2 converts `txt` of type `typ` to.
    Raise MissingToolError if the program that k3down2 runs is not on PATH, such as dot for graphviz,
    and RenderError if the program fails on `txt`, such as MathJax on TeX with an undefined command.
    """
    try:
        return k3down2.convert(typ, txt, output_typ, opt=opt)
    except FileNotFoundError as e:
        reason = f"needs {e.filename!r}, which is not on PATH"
        raise MissingToolError(f"rendering {typ} in {mdrender.conf.src_path!r} {reason}") from e
    except k3proc.CalledProcessError as e:
        # The program writes why it failed to stderr, such as "Undefined control sequence \foo" from MathJax.
        reason = "\n".join(e.err)
        raise RenderError(f"rendering {typ} in {mdrender.conf.src_path!r} failed: {reason}") from e


def conversion_key(typ: str, opt: Optional[dict]) -> str:
    """
    Return the converter `typ` and its options `opt`, which make an image from a text.
    The html option asset_base is left out: it is the absolute path of the folder of the article,
    the same for each table of the article, and with it the name of an image would depend on where the article is.
    """
    key_opt = dict(opt or {})
    if "html" in key_opt:
        html = dict(key_opt["html"])
        html.pop("asset_base", None)
        key_opt["html"] = html
    return json.dumps([typ, key_opt], sort_keys=True)


def block_code_to_jpg(mdrender: "MDRender", rnode: "RenderNode", width: Optional[int] = None) -> List[str]:
    n = rnode.node

    txt = code_join(n)

    w = width
    if w is None:
        w = mdrender.conf.plain_code_width

    return typ_text_to_jpg(mdrender, "code", txt, opt={"html": {"width": w}})


def block_code_to_fixwidth_jpg(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    return block_code_to_jpg(mdrender, rnode, width=mdrender.conf.code_width)


def block_code_mermaid_to_jpg(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    n = rnode.node
    return typ_text_to_jpg(mdrender, "mermaid", n["text"])


def block_code_graphviz_to_jpg(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    n = rnode.node
    return typ_text_to_jpg(mdrender, "graphviz", n["text"])


def math_block_to_imgtag(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    n = rnode.node
    return [k3down2.convert("tex_block", n["text"], "imgtag")]


def math_inline_to_imgtag(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    n = rnode.node
    return [k3down2.convert("tex_inline", n["text"], "imgtag")]


def math_block_join_dolar_when_nested(mdrender, rnode):
    n = rnode.node

    # If it is not a top level paragraph, convert block math to one-line math.
    # e.g., github does not support multi line block math that is nested in a list item

    # ROOT -> paragraph -> math_block
    # 0       1            2
    if rnode.level > 2:
        return ["$$" + n["text"].strip() + "$$"]

    return ["$$", n["text"], "$$"]


def math_inline_single_dolar(mdrender, rnode):
    n = rnode.node
    return ["$" + n["text"].strip() + "$"]


def math_block_to_hugo(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    r"""
    Write a math block on one line, between "\[" and "\]" if it is alone in its paragraph, else between "$$" and "$$".
    md2zhihu reads math as a block if it starts its paragraph and ends a line, such as in "$$x$$\nis a number.",
    but kramdown, which reads the "$$" math of minimal_mistake, takes such math as inline math.
    """
    n = rnode.node
    tex = tex_one_line(n["text"])
    if alone_in_paragraph(rnode):
        return ["\\[" + tex + "\\]"]
    return ["$$" + tex + "$$"]


def math_inline_to_hugo(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    """
    Write inline math on one line, between "$$" and "$$".
    """
    n = rnode.node
    tex = tex_one_line(n["text"])
    return ["$$" + tex + "$$"]


def alone_in_paragraph(rnode: "RenderNode") -> bool:
    """
    Return whether the node `rnode` is the only node of its paragraph, or of the text of an item of a tight list.
    """
    parent = rnode.parent
    if parent is None:
        return False
    if parent.node["type"] not in ("paragraph", "block_text"):
        return False
    siblings = inline_children(parent.node)
    return len(siblings) == 1


def tex_one_line(tex: str) -> str:
    """
    Return the TeX `tex` on one line: each line without its comment and its spaces at both ends, joined with a space.
    TeX reads a line break as a space, and a comment ends at the end of its line,
    so the line breaks can become spaces once the comments are gone.
    """
    parts = []
    for line in tex.split("\n"):
        code = strip_tex_comment(line).strip()
        if code != "":
            parts.append(code)
    return " ".join(parts)


def strip_tex_comment(line: str) -> str:
    r"""
    Return `line` up to its first "%" that is not escaped as "\%", which starts a TeX comment.
    """
    escaped = False
    for i, c in enumerate(line):
        if c == "%" and not escaped:
            return line[:i]
        escaped = c == "\\" and not escaped
    return line


def math_block_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, "tex_block", n["text"])


def math_inline_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, "tex_inline", n["text"])


def math_inline_to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape(k3down2.convert("tex_inline", n["text"], "plain"))]


def table_to_barehtml(mdrender, rnode) -> List[str]:
    # create a markdown render to recursively deal with images etc.
    mdr = MDRender(mdrender.conf, features=importer_features)
    # The links in the table and the links outside it are copied in one conversion, which finds two files of one name.
    mdr.linked_files = mdrender.linked_files

    md = mdr.render_node(rnode)
    md = "\n".join(md)

    table_html = k3down2_convert(mdrender, "table", md, "html")
    table_html = table_html.split("\n") + [""]
    return table_html


def table_to_jpg(mdrender, rnode):
    mdr = MDRender(mdrender.conf, features={})

    md = mdr.render_node(rnode)
    md = "\n".join(md)

    md_base_path = os.path.split(mdrender.conf.src_path)[0]

    return typ_text_to_jpg(
        mdrender,
        "md",
        md,
        opt={
            "html": {
                "asset_base": os.path.abspath(md_base_path),
            }
        },
    )


# Importer is only used to copy local images and linked files to output dir and update their urls.
# This is used to deal with partial renderers, e.g., table_to_barehtml,
# which is not handled by universal image importer, but need to import the image when rendering a table with images.
importer_features = dict(
    image=save_image_to_asset_dir,
    link=save_linked_file_to_asset_dir,
)
