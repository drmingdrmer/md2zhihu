import hashlib
import json
import os
import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from typing import Any
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from urllib.parse import unquote

import k3down2
import k3proc

from ..asset import save_image_to_asset_dir
from ..asset import save_linked_file_to_asset_dir
from ..asset import store_linked_file
from ..errors import MissingToolError
from ..errors import RenderError
from ..renderer import MDRender
from ..renderer import RenderNode
from ..renderer.md_render import escape_plain
from ..renderer.md_render import inline_children
from ..renderer.refs import render_ref_definitions
from ..types import Ref
from ..types import RefDict
from ..utils import asset_fn
from ..utils import code_block_lines
from ..utils import fwrite
from ..utils import is_path_url
from ..utils import split_url

if TYPE_CHECKING:
    from ..config import Config

# A part of TeX that tex_one_line() reads as a whole, tried in this order:
# a "\verb" span, which ends on its line as in LaTeX, and in which "%" starts no comment, such as "\verb|a%b|";
# "\href", "\url" or "\style" with its first argument on its line, which MathJax and KaTeX read as written,
# so that "%" starts no comment in it, such as "\href{https://a.com/%20}";
# a gap, which is a run of white space and comments, with the control word right before it if there is one;
# or a control sequence, such as "\alpha", "\%", or the control space "\ ", whose space belongs to it, not to a gap.
# A comment runs from "%" to the end of its line.
tex_parts = re.compile(
    r"\\verb\*?(?P<delimiter>[^a-zA-Z \t\n]).*?(?P=delimiter)"
    r"|\\(?:href|url|style)[ \t]*\{[^{}\n]*\}"
    r"|(?P<word>\\[a-zA-Z]+)?(?P<gap>(?:[ \t\n]|%.*)+)"
    r"|\\(?:[a-zA-Z]+|[\s\S])"
)

# A TeX comment, with the line break that ends it, which TeX also drops.
tex_comment = re.compile(r"%.*\n?")


def code_join(n: dict) -> str:
    lines = code_block_lines(n["text"], n["info"] or "")
    txt = "\n".join(lines + [""])
    return txt


def to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape_plain(n["text"])]


def typ_text_to_jpg(
    mdrender: "MDRender", typ: str, txt: str, opt: Optional[dict] = None, shown_files: Sequence[str] = ()
) -> List[str]:
    """`shown_files` are the local files that the image of `txt` shows, such as the images of a table."""
    d = k3down2_convert(mdrender, typ, txt, "jpg", opt=opt)
    # One text can make different images, such as x in $x$ and in $$x$$, so the name also has the converter.
    fn = asset_fn(txt, "jpg", conversion_key(typ, opt, shown_files))
    fwrite(mdrender.conf.asset_output_dir, fn, d)

    return [r"![]({})".format(mdrender.conf.img_url(fn)), ""]


def k3down2_convert(mdrender: "MDRender", typ: str, txt: str, output_typ: str, opt: Optional[dict] = None) -> Any:
    """
    Return what k3down2 converts `txt` of type `typ` to.
    Raise MissingToolError if the program that k3down2 runs is not on PATH, such as dot for graphviz,
    or if node can not find the package mathjax-full,
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
        # node writes a stack of many lines when it can not load MathJax, with "Cannot find module 'mathjax-full/...".
        if "Cannot find module 'mathjax-full" in reason:
            missing = "needs the node package mathjax-full; install it with npm install -g mathjax-full@3.2.2"
            raise MissingToolError(f"rendering {typ} in {mdrender.conf.src_path!r} {missing}") from e
        raise RenderError(f"rendering {typ} in {mdrender.conf.src_path!r} failed: {reason}") from e


def conversion_key(typ: str, opt: Optional[dict], shown_files: Sequence[str] = ()) -> str:
    """
    Return the converter `typ` and its options `opt`, which make an image from a text, and the md5 of each of
    `shown_files`, the local files that the image shows.
    The html option asset_base is left out: it is the absolute path of the folder of the article,
    the same for each table of the article, and with it the name of an image would depend on where the article is.
    The files that the image shows from that folder take its place, such as x.png of "| ![](x.png) |",
    because two folders can each have their own x.png.
    """
    key_opt = dict(opt or {})
    if "html" in key_opt:
        html = dict(key_opt["html"])
        html.pop("asset_base", None)
        key_opt["html"] = html
    key = json.dumps([typ, key_opt], sort_keys=True)
    for path in shown_files:
        with open(path, "rb") as f:
            content = f.read()
        key += hashlib.md5(content).hexdigest()
    return key


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


def math_in_table(mdrender, rnode) -> List[str]:
    r"""
    Write the math of a table cell for pandoc's markdown reader, which makes the HTML or the image of a table:
    between "$", such as "$x$", because pandoc reads math between "$$" as display math.
    A cell holds a "|" of its math as "\|", which pandoc reads as the TeX of "∥", so the "|" is written as "\vert".
    """
    n = rnode.node
    tex = n["text"].replace("\\|", "\\vert ")
    # pandoc reads no math between "$" with a space next to either "$", such as "$ x $".
    return ["$" + tex.strip() + "$"]


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
    r"""
    Return the TeX `tex` on one line, which MathJax and KaTeX draw as they draw `tex`, except for some white space in
    text: TeX reads one space in both "\text{a % one\n b}" and its one-line form "\text{a b}", but they draw two in
    the first.
    """
    return tex_parts.sub(tex_part_on_one_line, tex)


def tex_part_on_one_line(m: re.Match[str]) -> str:
    r"""
    Return the match of `tex_parts` as it goes on one line.
    MathJax and KaTeX read a comment and the line break after it as nothing, and any other line break as a space.
    So a gap that holds a line break or a comment becomes one space, or nothing if it holds only comments,
    as "ab% one\ncd" becomes "abcd".
    After a control word, such a gap still becomes a space, as "\alpha% one\nbeta" becomes "\alpha beta".
    A gap at either end of the TeX is dropped.
    """
    gap = m.group("gap")
    if gap is None:
        # TeX reads "\" at the end of a line as the control space "\ ".
        if m.group(0) == "\\\n":
            return "\\ "
        return m.group(0)

    word = m.group("word") or ""
    at_end = m.start("gap") == 0 or m.end() == len(m.string)
    if at_end:
        return word
    within_line = "\n" not in gap and "%" not in gap
    if within_line:
        return m.group(0)
    spaces = tex_comment.sub("", gap)
    if spaces == "" and word == "":
        return ""
    return word + " "


def math_block_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, "tex_block", n["text"])


def math_inline_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, "tex_inline", n["text"])


def math_inline_to_plaintext(mdrender, rnode):
    n = rnode.node
    text = k3down2.convert("tex_inline", n["text"], "plain")
    return [escape_plain(text)]


def table_to_barehtml(mdrender, rnode) -> List[str]:
    # create a markdown render to recursively deal with images etc.
    # The table shares the copies of the run, so that store_linked_file finds two files that would be copied to one path.
    features = {**importer_features, **table_math_features}
    mdr = MDRender(mdrender.conf, features=features, linked_files=mdrender.linked_files)

    md = mdr.render_node(rnode)
    # The definition of a reference in the table points at the copy of a local file, as a link in the table does.
    refs: RefDict = {}
    for name, ref in kept_refs([rnode.node]).items():
        url = store_linked_file(mdrender.conf, ref.url, mdrender.linked_files)
        refs[name] = Ref(url, ref.title)
    md += render_ref_definitions(refs)
    md = "\n".join(md)

    table_html = k3down2_convert(mdrender, "table", md, "html")
    table_html = table_html.split("\n") + [""]
    return table_html


def table_to_jpg(mdrender, rnode):
    mdr = MDRender(mdrender.conf, features=table_math_features)

    md = mdr.render_node(rnode)
    refs = kept_refs([rnode.node])
    md += render_ref_definitions(refs)
    md = "\n".join(md)

    md_base_path = os.path.split(mdrender.conf.src_path)[0]
    # The browser shows the local images of the table from the folder of the markdown.
    shown_files = local_images(mdrender.conf, [rnode.node])

    return typ_text_to_jpg(
        mdrender,
        "md",
        md,
        opt={
            "html": {
                "asset_base": os.path.abspath(md_base_path),
            }
        },
        shown_files=shown_files,
    )


def kept_refs(nodes: List[dict]) -> RefDict:
    """
    Return the definition of each reference that the AST `nodes` keep, by name, from their ref_label nodes,
    such as of "slim" for the text "[slim][slim]" that `ParserConfig(False, ...)` keeps.
    A converter gets a table without the definitions at the end of the output, so they follow the table,
    or the reference shows as its text.
    """
    refs: RefDict = {}
    for n in nodes:
        if "children" in n:
            refs.update(kept_refs(n["children"]))
        if n["type"] == "ref_label":
            refs[n["text"]] = Ref(n["link"], n["title"])
    return refs


def local_images(conf: "Config", nodes: List[dict]) -> List[str]:
    """
    Return the path from the working dir of each image in the AST `nodes` that is a local file,
    such as "a/x.png" for "![](x.png)" or '<img src="x.png">' in "a/b.md".
    """
    paths = []
    for n in nodes:
        if "children" in n:
            paths.extend(local_images(conf, n["children"]))
        for url in image_urls(n):
            if not is_path_url(url):
                continue
            parts = split_url(url)
            # mistune percent-encodes the URL, such as "图片/a.png" to "%E5%9B%BE%E7%89%87/a.png",
            # and a browser decodes the src of an <img> in the same way.
            path = unquote(parts.head)
            path = conf.relpath_from_cwd(path)
            if os.path.isfile(path):
                paths.append(path)
    return paths


def image_urls(n: dict) -> List[str]:
    """
    Return the URL of each image that the AST node `n` shows, without its children:
    the URL of an image node, or the src of each <img> tag of an HTML node.
    """
    if n["type"] == "image":
        return [n["src"]]
    if n["type"] in ("inline_html", "block_html"):
        sources = ImageSources()
        sources.feed(n["text"])
        sources.close()
        return sources.urls
    return []


class ImageSources(HTMLParser):
    """The src of each <img> tag in the HTML fed to it, in `urls`, with its character references decoded."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag != "img":
            return
        # A browser uses the first src of a tag.
        for name, value in attrs:
            if name == "src" and value is not None:
                self.urls.append(value)
                return


# Importer is only used to copy local images and linked files to output dir and update their urls.
# This is used to deal with partial renderers, e.g., table_to_barehtml,
# which is not handled by universal image importer, but need to import the image when rendering a table with images.
importer_features = dict(
    image=save_image_to_asset_dir,
    link=save_linked_file_to_asset_dir,
)

# The renderers of the math of a table, for pandoc's markdown reader. Math alone in a cell is a math block,
# such as "$x$" in "| $x$ |".
table_math_features = dict(
    math_block=math_in_table,
    math_inline=math_in_table,
)
