from typing import List
from typing import Optional

from .asset import save_image_to_asset_dir
from .converters import block_code_graphviz_to_jpg
from .converters import block_code_mermaid_to_jpg
from .converters import block_code_to_fixwidth_jpg
from .converters import block_code_to_jpg
from .converters import math_block_join_dolar_when_nested
from .converters import math_block_to_imgtag
from .converters import math_block_to_jpg
from .converters import math_inline_single_dolar  # ... 其他转换函数
from .converters import math_inline_to_imgtag
from .converters import math_inline_to_jpg
from .converters import math_inline_to_plaintext
from .converters import table_to_barehtml
from .converters import table_to_jpg
from .converters import to_plaintext
from .utils import escape
from .utils import strip_paragraph_end


def weibo_specific(mdrender, rnode) -> Optional[List[str]]:
    n = rnode.node

    typ = n["type"]

    if typ == "image":
        return save_image_to_asset_dir(mdrender, rnode)

    if typ == "math_block":
        return math_block_to_imgtag(mdrender, rnode)

    if typ == "math_inline":
        return math_inline_to_plaintext(mdrender, rnode)

    if typ == "table":
        return table_to_jpg(mdrender, rnode)

    if typ == "codespan":
        return [escape(n["text"])]

    #  weibo does not support pasting <p> in <li>

    if typ == "list":
        lines = []
        lines.extend(mdrender.render(rnode))
        lines.append("")
        return lines

    if typ == "list_item":
        lines = []
        lines.extend(mdrender.render(rnode))
        lines.append("")
        return lines

    if typ == "block_quote":
        lines = mdrender.render(rnode)
        lines = strip_paragraph_end(lines)
        return lines

    if typ == "block_code":
        lang = n["info"] or ""
        if lang == "mermaid":
            return block_code_mermaid_to_jpg(mdrender, rnode)
        if lang == "graphviz":
            return block_code_graphviz_to_jpg(mdrender, rnode)

        if lang == "":
            return block_code_to_jpg(mdrender, rnode)
        else:
            return block_code_to_jpg(mdrender, rnode, width=600)

    return None


transparent_features = dict(
    image=save_image_to_asset_dir,
)

simple_features = dict(
    image=save_image_to_asset_dir,
    math_block=math_block_to_jpg,
    math_inline=math_inline_to_jpg,
    table=table_to_jpg,
    codespan=to_plaintext,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
        **{
            "": block_code_to_jpg,
            "*": block_code_to_fixwidth_jpg,
        },
    ),
)

weibo_features = {"*": weibo_specific}


wechat_features = dict(
    image=save_image_to_asset_dir,
    math_block=math_block_to_imgtag,
    math_inline=math_inline_to_imgtag,
    table=table_to_barehtml,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
        **{
            "": block_code_to_jpg,
            "*": block_code_to_fixwidth_jpg,
        },
    ),
)

zhihu_features = dict(
    image=save_image_to_asset_dir,
    math_block=math_block_to_imgtag,
    math_inline=math_inline_to_imgtag,
    table=table_to_barehtml,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    ),
)

#  Display markdown in github.com
#  Github supports:
#  - latex math
#  - mermaid
github_features = dict(
    image=save_image_to_asset_dir,
    math_block=math_block_join_dolar_when_nested,
    # github use single dolar inline math.
    math_inline=math_inline_single_dolar,
    block_code=dict(
        graphviz=block_code_graphviz_to_jpg,
    ),
)

#  jekyll theme: minimal mistake
minimal_mistake_features = dict(
    image=save_image_to_asset_dir,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    ),
)

# type, subtype... action
#
all_features = dict(
    image=dict(
        local_to_remote=save_image_to_asset_dir,
    ),
    math_block=dict(
        to_imgtag=math_block_to_imgtag,
        to_jpg=math_block_to_jpg,
    ),
    math_inline=dict(
        to_imgtag=math_inline_to_imgtag,
        to_jpg=math_inline_to_jpg,
        to_plaintext=math_inline_to_plaintext,
    ),
    table=dict(
        to_barehtml=table_to_barehtml,
        to_jpg=table_to_jpg,
    ),
    codespan=dict(to_text=to_plaintext),
    block_code=dict(
        graphviz=dict(
            to_jpg=block_code_graphviz_to_jpg,
        ),
        mermaid=dict(
            to_jpg=block_code_mermaid_to_jpg,
        ),
        **{
            "": dict(to_jpg=block_code_to_jpg),
            "*": dict(to_jpg=block_code_to_fixwidth_jpg),
        },
    ),
)

platform_feature_dict = {
    "zhihu": zhihu_features,
    "github": github_features,
    "wechat": wechat_features,
    "weibo": weibo_features,
    "minimal_mistake": minimal_mistake_features,
    "simple": simple_features,
    "transparent": transparent_features,
}


def rules_to_features(rules):
    features = {}
    for r in rules:
        rs, act = r.split(":")
        rs = rs.split("/")

        f = all_features
        rst = features
        for typ in rs[:-1]:
            f = f[typ]
            if typ not in rst:
                rst[typ] = {}

            rst = rst[typ]

        typ = rs[-1]
        rst[typ] = f[typ][act]

    return features
