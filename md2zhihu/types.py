"""Type definitions for md2zhihu"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from typing_extensions import TypeAlias

# AST node types
ASTNode: TypeAlias = Dict[str, Any]
ASTNodes: TypeAlias = List[ASTNode]


@dataclass
class Ref:
    """
    A link reference definition, such as `[grpc]: https://grpc.io "gRPC"`.
    `url` is percent-encoded, as mistune writes the URL of a link, and `title` is None without a title.
    """

    url: str
    title: Optional[str] = None


# Reference dictionary: {ref_id: Ref}
RefDict: TypeAlias = Dict[str, Ref]

# Feature handler type for MDRender
# Returns list of rendered lines, or None if not handled
FeatureHandler: TypeAlias = Callable[..., Optional[List[str]]]

# Features dictionary: {node_type: handler} or {node_type: {subtype: handler}}
Features: TypeAlias = Dict[str, Union[FeatureHandler, Dict[str, FeatureHandler]]]
