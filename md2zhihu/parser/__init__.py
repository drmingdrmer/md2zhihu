"""Parser classes for md2zhihu"""

import os
import re
from typing import List
from typing import Optional

import yaml
from k3fs import fread

from .._vendor import mistune
from ..config import Config
from ..renderer import MDRender
from ..renderer import RenderNode
from ..utils import add_paragraph_end


class FrontMatter(object):
    """
    The font matter is the yaml enclosed between `---` at the top of a markdown.
    """

    def __init__(self, front_matter_text: str):
        self.text = front_matter_text
        self.data = yaml.safe_load(front_matter_text)

    def get_refs(self, platform: str) -> dict:
        """
        Get refs from front matter.
        """
        dic = {}

        meta = self.data

        # Collect universal refs
        if "refs" in meta:
            refs = meta["refs"]

            for r in refs:
                dic.update(r)

        # Collect platform specific refs
        if "platform_refs" in meta:
            refs = meta["platform_refs"]
            if platform in refs:
                refs = refs[platform]

                for r in refs:
                    dic.update(r)

        return dic


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
        # Import here to avoid circular dependency
        from . import MDRender
        from . import RenderNode

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


def load_external_refs(conf: Config) -> dict:
    refs = {}
    for ref_path in conf.ref_files:
        fcont = fread(ref_path)
        y = yaml.safe_load(fcont)
        for r in y.get("universal", []):
            refs.update(r)
        for r in y.get(conf.platform, []):
            refs.update(r)

    return refs


def parse_in_list_tables(nodes) -> List[dict]:
    """
    mistune does not parse table in list item.
    We need to recursively fix it.
    """

    rst = []
    for n in nodes:
        if "children" in n:
            n["children"] = parse_in_list_tables(n["children"])

        nodes = convert_paragraph_table(n)
        rst.extend(nodes)

    return rst


def convert_paragraph_table(node: dict) -> List[dict]:
    """
    Parse table text in a paragraph and returns the ast of parsed table.

    :return List[dict]: a list of ast nodes.
    """

    if node["type"] != "paragraph":
        return [node]

    children = node["children"]

    if len(children) == 0:
        return [node]

    c0 = children[0]
    if c0["type"] != "text":
        return [node]

    txt = c0["text"]

    table_reg = r" {0,3}\|(.+)\n *\|( *[-:]+[-| :]*)\n((?: *\|.*(?:\n|$))*)\n*"

    match = re.match(table_reg, txt)
    if match:
        mdr = MDRender(None, features={})
        partialmd_lines = mdr.render(RenderNode(node))
        partialmd = "".join(partialmd_lines)

        parser = new_parser()
        new_children = parser(partialmd)

        return new_children
    else:
        return [node]


def join_math_block(nodes):
    """
    A tex segment may spans several paragraph:

        $$        // paragraph 1
        x = 5     //

        y = 3     // paragraph 2
        $$        //

    This function finds out all such paragraph and merge them into a single one.
    """

    for n in nodes:
        if "children" in n:
            join_math_block(n["children"])

    join_math_text(nodes)


def parse_math(nodes):
    """
    Extract all math segment such as ``$$ ... $$`` from a text and build a
    math_block or math_inline node.
    """

    children = []

    for n in nodes:
        if "children" in n:
            n["children"] = parse_math(n["children"])

        if n["type"] == "text":
            new_children = extract_math(n)
            children.extend(new_children)
        else:
            children.append(n)

    return children


def rebase_url_in_ast(frm, to, nodes):
    for n in nodes:
        if "children" in n:
            rebase_url_in_ast(frm, to, n["children"])

        if n["type"] == "image":
            n["src"] = rebase_url(frm, to, n["src"])
            continue

        if n["type"] == "link":
            n["link"] = rebase_url(frm, to, n["link"])
            continue


def rebase_url(frm, to, src):
    """
    Change relative path based from ``frm`` to from ``to``.
    """
    if re.match(r"http[s]?://", src):
        return src

    if src.startswith("/"):
        return src

    p = os.path.join(frm, src)
    p = os.path.relpath(p, start=to)

    return p


def regex_search_any(regex_list: List[str], s):
    for regex in regex_list:
        m = re.search(regex, s)
        if m:
            return True

    return False


def join_math_text(nodes):
    i = 0
    while i < len(nodes) - 1:
        n1 = nodes[i]
        n2 = nodes[i + 1]
        if (
            "children" in n1
            and "children" in n2
            and len(n1["children"]) > 0
            and len(n2["children"]) > 0
            and n1["children"][-1]["type"] == "text"
            and n2["children"][0]["type"] == "text"
            and "$$" in n1["children"][-1]["text"]
        ):
            has_dd = "$$" in n2["children"][0]["text"]
            n1["children"][-1]["text"] += "\n\n" + n2["children"][0]["text"]
            n1["children"].extend(n2["children"][1:])

            nodes.pop(i + 1)

            if has_dd:
                i += 1
        else:
            i += 1


def extract_math(n):
    """
    Extract ``$$ ... $$`` or ``$ .. $` from a text node and build a new node.
    The original text node is split into multiple segments.

    The math is a block if it is a paragraph.
    Otherwise, it is an inline math.
    """
    children = []

    math_regex = r"([$]|[$][$])([^$].*?)\1"

    t = n["text"]
    while True:
        match = re.search(math_regex, t, flags=re.DOTALL)
        if match:
            children.append({"type": "text", "text": t[: match.start()]})
            children.append({"type": "math_inline", "text": match.groups()[1]})
            t = t[match.end() :]

            left = children[-2]["text"]
            right = t
            if (left == "" or left.endswith("\n\n")) and (right == "" or right.startswith("\n")):
                children[-1]["type"] = "math_block"
            continue

        break
    children.append({"type": "text", "text": t})
    return children


def replace_ref_with_def(nodes, refs, do_replace: bool):
    """
    Convert ``[text][link-def]`` to ``[text](link-url)``
    Convert ``[link-def][]``     to ``[link-def](link-url)``
    Convert ``[link-def]``       to ``[link-def](link-url)``

    If `do_replace` is True, replace the ref with def.
    Otherwise, just extract the used refs.
    """

    used_defs = {}

    for n in nodes:
        if "children" in n:
            used = replace_ref_with_def(n["children"], refs, do_replace)
            used_defs.update(used)

        if n["type"] != "text":
            continue

        t = n["text"]
        link = re.match(r"^\[(.*?)\](\[([^\]]*?)\])?$", t)
        if not link:
            continue

        gs = link.groups()
        txt = gs[0]
        if len(gs) >= 3:
            definition = gs[2]

        if definition is None or definition == "":
            definition = txt

        if definition in refs:
            r = refs[definition]
            used_defs[definition] = r

            if do_replace:
                n["type"] = "link"
                #  TODO title
                n["link"] = r.split()[0]
                n["children"] = [{"type": "text", "text": txt}]

    return used_defs


def new_parser():
    rdr = mistune.create_markdown(
        escape=False,
        renderer="ast",
        plugins=["strikethrough", "footnotes", "table"],
    )

    return rdr


def extract_ref_definitions(cont):
    lines = cont.split("\n")
    rst = []
    refs = {}
    for line in lines:
        r = re.match(r"\[(.*?)\]:(.*?)$", line, flags=re.UNICODE)
        if r:
            gs = r.groups()
            refs[gs[0]] = gs[1]
        else:
            rst.append(line)
    return "\n".join(rst), refs


def extract_front_matter(cont):
    meta = None
    m = re.match(r"^ *--- *\n(.*?)\n---\n", cont, flags=re.DOTALL | re.UNICODE)
    if m:
        cont = cont[m.end() :]
        meta_text = m.groups()[0].strip()
        meta = FrontMatter(meta_text)

    return cont, meta


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
