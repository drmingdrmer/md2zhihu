import re
from typing import List

from ...renderer import MDRender
from ...renderer import RenderNode
from ..mistune_parser import new_parser


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
