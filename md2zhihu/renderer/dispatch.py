from typing import List
from typing import Optional

from .render_node import RenderNode


#  features: {typ:action(), typ2:{subtyp:action()}}
def render_with_features(mdrender, rnode: RenderNode, features=None) -> Optional[List[str]]:
    if features is None:
        features = {}

    n = rnode.node

    node_type = n["type"]

    if node_type not in features:
        if "*" in features:
            return features["*"](mdrender, rnode)
        else:
            return None

    type_handler = features[node_type]
    if callable(type_handler):
        return type_handler(mdrender, rnode)

    #  subtype is info, the type after "```"
    lang = n["info"] or ""

    if lang in type_handler:
        return type_handler[lang](mdrender, rnode)

    if "*" in type_handler:
        return type_handler["*"](mdrender, rnode)

    return None
