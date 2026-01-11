"""Type definitions for md2zhihu"""

from __future__ import annotations

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

# Reference dictionary: {ref_id: url}
RefDict: TypeAlias = Dict[str, str]

# Feature handler type for MDRender
# Returns list of rendered lines, or None if not handled
FeatureHandler: TypeAlias = Callable[..., Optional[List[str]]]

# Features dictionary: {node_type: handler} or {node_type: {subtype: handler}}
Features: TypeAlias = Dict[str, Union[FeatureHandler, Dict[str, FeatureHandler]]]
