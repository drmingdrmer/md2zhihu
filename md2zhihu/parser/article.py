import copy
import os
import re
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from urllib.parse import unquote
from urllib.parse import urlsplit

from k3fs import fread
from mistune.util import unikey

from ..asset import store_linked_file
from ..config import Config
from ..errors import EmbedCycleError
from ..errors import MissingFileError
from ..renderer import MDRender
from ..renderer import RenderNode
from ..renderer.refs import render_ref_definitions
from ..renderer.refs import render_ref_list
from ..types import Ref
from ..types import RefDict
from ..utils import add_paragraph_end
from ..utils import warn
from . import mistune3
from .extract.front_matter import FrontMatter
from .extract.front_matter import extract_front_matter
from .extract.refs import load_external_refs
from .extract.refs import update_refs
from .transform.rebase import rebase_url
from .transform.rebase import rebase_url_in_ast


class ParserConfig(object):
    """
    Config for parsing markdown file.

    `populate_reference`: whether to replace reference with definition.

    `embed_patterns`: the url regex patterns to replace the content of url in ![](url).
    """

    def __init__(self, populate_reference: bool, embed_patterns: List[str]):
        self.populate_reference = populate_reference
        self.embed_patterns = embed_patterns


class Article(object):
    def __init__(
        self,
        parser_config: ParserConfig,
        conf: Config,
        md_text: str,
        embedders: Tuple[str, ...] = (),
        ref_names: Optional[Dict[str, Ref]] = None,
    ):
        """
        `embedders` holds the paths of the markdown files that embed this one, outermost first.
        `ref_names` maps the key of each reference name in the output, such as "R" for "r", as markdown matches names,
        to its reference, whose path URL is from the working dir.
        The articles that embed one another share it, so that each name stays one reference.
        """
        self.parser_config = parser_config

        self.conf = conf

        self.embedders = embedders

        if ref_names is None:
            ref_names = {}
        self.ref_names = ref_names

        # init

        # Input markdown in str, with the "\n" line ends that the extractors below expect.
        # A caller may pass "\r\n", which the md2zhihu command does not, because it reads files in text mode.
        self.md_text: str = md_text.replace("\r\n", "\n")

        # References from outside the text: the --refs files and the front matter.
        # A definition in the text wins over one of them, as mistune3.parse reads the text.
        self.refs: RefDict = {}

        self.front_matter: Optional[FrontMatter] = None

        # extract article meta

        self.md_text, self.front_matter = extract_front_matter(self.md_text, conf.src_path)

        # build refs

        update_refs(self.refs, load_external_refs(self.conf))
        if self.front_matter is not None:
            update_refs(self.refs, self.front_matter.get_refs(conf.options.platform, conf.src_path))

        # parse to ast and clean up

        # The AST of the markdown, and the references used in it.
        self.ast, self.used_refs, undefined_refs = mistune3.parse(
            self.md_text, self.refs, self.parser_config.populate_reference, self.ref_name
        )

        for ref in undefined_refs:
            warn("undefined reference ", ref, " in ", repr(self.conf.src_path))

        self.parse_embed()

    def ref_name(self, name: str, ref: Ref) -> str:
        """
        Return the name in the output of the reference `name` to `ref`: `name`, or a new one such as "r-2",
        if another article of the output, such as the one that embeds this one, uses `name` for another reference.
        """
        # A path URL is compared from the working dir, because each article writes it from its own dir.
        base = os.path.split(self.conf.src_path)[0]
        url = rebase_url(base, os.curdir, ref.url)
        key_ref = Ref(url, ref.title)

        new_name = name
        n = 1
        while True:
            registered = self.ref_names.setdefault(unikey(new_name), key_ref)
            if registered == key_ref:
                return new_name
            n += 1
            new_name = name + "-" + str(n)

    def parse_embed(self):
        # Import here to avoid circular dependency

        used_refs: RefDict = {}
        self.ast = self.embed(self.ast, used_refs)
        self.used_refs.update(used_refs)

    def embed(self, nodes, used_refs):
        """
        Embed the content of url in ![](url) if url matches specified regex
        The blocks of the markdown replace the block that holds only the image: a paragraph, or the text of an item of
        a tight list, which mistune makes a block_text. An image among other text stays an image, because a line of
        text can not hold blocks.
        """

        children = []

        for n in nodes:
            if "children" in n:
                n["children"] = self.embed(n["children"], used_refs)

            is_text_block = n["type"] in ("paragraph", "block_text")
            if not is_text_block or len(n.get("children", [])) != 1:
                children.append(n)
                continue

            child = n["children"][0]

            if child["type"] != "image":
                children.append(n)
                continue

            #  {'alt': 'openacid',
            #   'src': 'https://...',
            #   'title': None,
            #   'type': 'image'},

            # mistune percent-encodes the URL, such as "子文档.md", but md2zhihu matches and opens the path.
            src = unquote(child["src"])
            if not regex_search_any(self.parser_config.embed_patterns, src):
                children.append(n)
                continue

            # md2zhihu embeds local markdown only, so a URL with a scheme or a host, such as "https://a.com/x.md", stays an image.
            parts = urlsplit(child["src"])
            is_path = parts.scheme == "" and parts.netloc == ""
            if not is_path:
                children.append(n)
                continue

            article_path = self.conf.relpath_from_cwd(src)
            if not os.path.exists(article_path):
                raise MissingFileError(f"embedded markdown not found: {article_path!r}, used in {self.conf.src_path!r}")

            chain = self.embedders + (self.conf.src_path,)
            # realpath() gives one path for a file that other paths also name, such as a symlink to it.
            embedding = {os.path.realpath(p) for p in chain}
            if os.path.realpath(article_path) in embedding:
                names = [repr(p) for p in chain + (article_path,)]
                raise EmbedCycleError("markdown embeds itself: " + " -> ".join(names))

            md_text = fread(article_path)

            # The embedded article reads its own path, such as for the images in it, and the parent keeps its config.
            child_conf = Config.from_options(article_path, self.conf.options)

            article = Article(self.parser_config, child_conf, md_text, embedders=chain, ref_names=self.ref_names)

            # rebase urls in embedded article

            child_base = os.path.split(article_path)[0]
            parent_base = os.path.split(self.conf.src_path)[0]

            new_children = article.ast
            rebase_url_in_ast(child_base, parent_base, new_children)

            children.extend(new_children)

            # update used_refs

            used = {}
            for k, ref in article.used_refs.items():
                url = rebase_url(child_base, parent_base, ref.url)
                used[k] = Ref(url, ref.title)

            used_refs.update(used)

        return children

    def chunks(self):
        """
        yield str chunks of the markdown file.
        """

        if self.front_matter is not None:
            yield "front_matter", "", "---\n" + self.front_matter.text + "\n---"

        mdr, root_node = self.render_root()
        for node in root_node.node["children"]:
            block = root_node.new_child(node)
            # render list items separately
            if node["type"] == "list":
                for n in node["children"]:
                    child = block.new_child(n)
                    output_lines = mdr.render_node(child)
                    output_lines = add_paragraph_end(output_lines)
                    yield "content", n["type"], "\n".join(output_lines)
                yield "content", "new_line", ""
            else:
                output_lines = mdr.render_node(block)
                yield "content", node["type"], "\n".join(output_lines)

        used_refs = self.stored_refs(mdr.linked_files)
        ref_lines = render_ref_definitions(used_refs)

        yield "ref_def", "", "\n".join(ref_lines)

    def render(self):
        mdr, root_node = self.render_root()
        output_lines = mdr.render(root_node)

        if self.conf.options.keep_meta and self.front_matter is not None:
            output_lines = ["---", self.front_matter.text, "---"] + output_lines

        output_lines.append("")

        used_refs = self.stored_refs(mdr.linked_files)
        ref_list = render_ref_list(used_refs, self.conf.options.platform)
        output_lines.extend(ref_list)

        output_lines.append("")

        ref_lines = render_ref_definitions(used_refs)
        output_lines.extend(ref_lines)

        return output_lines

    def render_root(self) -> Tuple[MDRender, RenderNode]:
        """
        Return a renderer for the platform, and the root that render() and chunks() render: one root holds every block,
        so that each block is rendered among its siblings, such as a list right after a list of its kind,
        which takes the other marker.
        The renderer changes nodes, such as the URL of a local image to the URL of its copy,
        so the root holds a copy of the AST, and the next render reads the AST as parsed.
        """
        mdr = MDRender(self.conf, features=self.conf.features)
        ast = copy.deepcopy(self.ast)
        root_node = RenderNode({"type": "ROOT", "children": ast})
        return mdr, root_node

    def stored_refs(self, linked_files: Dict[str, str]) -> RefDict:
        """
        Return the used references, with the URL of a local file replaced by the URL of its copy in the asset dir,
        as every platform does for a link.
        `linked_files` is the `MDRender.linked_files` of the conversion that renders the references.
        """
        refs: RefDict = {}
        for ref_id, ref in self.used_refs.items():
            stored_url = store_linked_file(self.conf, ref.url, linked_files)
            refs[ref_id] = Ref(stored_url, ref.title)
        return refs


def regex_search_any(regex_list: List[str], s):
    for regex in regex_list:
        m = re.search(regex, s)
        if m:
            return True

    return False
