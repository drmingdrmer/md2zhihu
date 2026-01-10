import os
from typing import List
from typing import Optional

import k3down2

from .asset import save_image_to_asset_dir
from .renderer import MDRender
from .renderer import RenderNode
from .utils import asset_fn
from .utils import escape
from .utils import fwrite


def code_join(n: dict) -> str:
    lang = n["info"] or ""
    lines = n["text"][:-1].split("\n")
    txt = "\n".join(["```" + lang] + lines + ["```", ""])
    return txt


def to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape(n["text"])]


def typ_text_to_jpg(mdrender: "MDRender", typ: str, txt: str, opt: Optional[dict] = None) -> List[str]:
    d = k3down2.convert(typ, txt, "jpg", opt=opt)
    fn = asset_fn(txt, "jpg")
    fwrite(mdrender.conf.asset_output_dir, fn, d)

    return [r"![]({})".format(mdrender.conf.img_url(fn)), ""]


def block_code_to_jpg(mdrender: "MDRender", rnode: "RenderNode", width: Optional[int] = None) -> List[str]:
    n = rnode.node

    txt = code_join(n)

    w = width
    if w is None:
        w = mdrender.conf.code_width

    return typ_text_to_jpg(mdrender, "code", txt, opt={"html": {"width": w}})


def block_code_to_fixwidth_jpg(mdrender: "MDRender", rnode: "RenderNode") -> List[str]:
    return block_code_to_jpg(mdrender, rnode, width=600)


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

    md = mdr.render_node(rnode)
    md = "\n".join(md)

    table_html = k3down2.convert("table", md, "html")
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


# Importer is only used to copy local image to output dir and update image urls.
# This is used to deal with partial renderers, e.g., table_to_barehtml,
# which is not handled by universal image importer, but need to import the image when rendering a table with images.
importer_features = dict(
    image=save_image_to_asset_dir,
)
