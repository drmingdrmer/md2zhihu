"""Parser classes for md2zhihu"""

import os
import re
from typing import List
from typing import Optional

from k3fs import fread

from ..config import Config
from ..renderer import MDRender
from ..renderer import RenderNode
from ..utils import add_paragraph_end
from .extract.front_matter import FrontMatter
from .extract.front_matter import extract_front_matter
from .extract.refs import extract_ref_definitions
from .extract.refs import load_external_refs
from .new_parser import new_parser
from .transform.math import join_math_block
from .transform.math import parse_math
from .transform.rebase import rebase_url
from .transform.rebase import rebase_url_in_ast
from .transform.refs import replace_ref_with_def
from .transform.table import parse_in_list_tables


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
    def __init__(self, parser_config: ParserConfig, conf: Config, md_text: str):
        self.parser_config = parser_config

        self.conf = conf

        # init

        # Input markdown in str
        self.md_text: str = md_text

        # References defined in this markdown
        self.refs = {}

        # References used in this markdown
        self.used_refs = None

        self.front_matter: Optional[FrontMatter] = None

        # Parsed AST of the markdown
        self.ast = None

        # extract article meta

        self.md_text, self.front_matter = extract_front_matter(self.md_text)
        self.md_text, article_refs = extract_ref_definitions(self.md_text)

        # build refs

        self.refs.update(load_external_refs(self.conf))
        if self.front_matter is not None:
            self.refs.update(self.front_matter.get_refs(conf.platform))
        self.refs.update(article_refs)

        # parse to ast and clean up

        parse_to_ast = new_parser()
        self.ast = parse_to_ast(self.md_text)

        self.ast = parse_in_list_tables(self.ast)

        self.used_refs = replace_ref_with_def(self.ast, self.refs, self.parser_config.populate_reference)

        # extract already inlined math
        self.ast = parse_math(self.ast)

        # join cross paragraph math
        join_math_block(self.ast)
        self.ast = parse_math(self.ast)

        self.parse_embed()

    def parse_embed(self):
        # Import here to avoid circular dependency

        used_refs = {}
        self.ast = self.embed(self.ast, used_refs)
        self.used_refs.update(used_refs)

    def embed(self, nodes, used_refs):
        """
        Embed the content of url in ![](url) if url matches specified regex
        """

        children = []

        for n in nodes:
            if "children" in n:
                n["children"] = self.embed(n["children"], used_refs)

            if n["type"] != "paragraph" or len(n.get("children", [])) != 1:
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

            if not regex_search_any(self.parser_config.embed_patterns, child["src"]):
                children.append(n)
                continue

            article_path = self.conf.relpath_from_cwd(child["src"])
            md_text = fread(article_path)

            # save and restore parent src_path

            old = self.conf.src_path
            self.conf.src_path = article_path

            article = Article(self.parser_config, self.conf, md_text)

            self.conf.src_path = old

            # rebase urls in embedded article

            child_base = os.path.split(article_path)[0]
            parent_base = os.path.split(self.conf.src_path)[0]

            new_children = article.ast
            rebase_url_in_ast(child_base, parent_base, new_children)

            children.extend(new_children)

            # update used_refs

            used = {}
            for k, v in article.used_refs.items():
                v = v.strip()
                used[k] = rebase_url(child_base, parent_base, v)

            used_refs.update(used)

        return children

    def chunks(self):
        """
        yield str chunks of the markdown file.
        """

        if self.front_matter is not None:
            yield "front_matter", "", "---\n" + self.front_matter.text + "\n---"

        mdr = MDRender(self.conf, features=self.conf.features)

        for node in self.ast:
            # render list items separately
            if node["type"] == "list":
                root_node = RenderNode(node)
                for n in node["children"]:
                    child = root_node.new_child(n)
                    output_lines = mdr.render_node(child)
                    output_lines = add_paragraph_end(output_lines)
                    yield "content", n["type"], "\n".join(output_lines)
                yield "content", "new_line", ""
            else:
                root_node = RenderNode(
                    {
                        "type": "ROOT",
                        "children": [node],
                    }
                )
                output_lines = mdr.render(root_node)
                yield "content", node["type"], "\n".join(output_lines)

        ref_lines = ["[{id}]: {d}".format(id=ref_id, d=self.used_refs[ref_id]) for ref_id in sorted(self.used_refs)]

        yield "ref_def", "", "\n".join(ref_lines)

    def render(self):
        mdr = MDRender(self.conf, features=self.conf.features)

        root_node = {
            "type": "ROOT",
            "children": self.ast,
        }
        output_lines = mdr.render(RenderNode(root_node))

        if self.conf.keep_meta and self.front_matter is not None:
            output_lines = ["---", self.front_matter.text, "---"] + output_lines

        output_lines.append("")

        ref_list = render_ref_list(self.used_refs, self.conf.platform)
        output_lines.extend(ref_list)

        output_lines.append("")

        ref_lines = ["[{id}]: {d}".format(id=ref_id, d=self.used_refs[ref_id]) for ref_id in sorted(self.used_refs)]
        output_lines.extend(ref_lines)

        return output_lines


def regex_search_any(regex_list: List[str], s):
    for regex in regex_list:
        m = re.search(regex, s)
        if m:
            return True

    return False


def render_ref_list(refs, platform):
    ref_lines = ["", "Reference:", ""]
    for ref_id in sorted(refs):
        #  url_and_alt is in form "<url> <alt>"
        url_alt = refs[ref_id].split()
        url = url_alt[0]

        if len(url_alt) == 1:
            txt = ref_id
        else:
            txt = " ".join(url_alt[1:])
            txt = txt.strip('"')
            txt = txt.strip("'")

        ref_lines.append("- {id} : [{url}]({url})".format(id=txt, url=url))

        #  disable paragraph list in weibo
        if platform != "weibo":
            ref_lines.append("")

    return ref_lines
