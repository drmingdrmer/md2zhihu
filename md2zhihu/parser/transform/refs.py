import re
from typing import List
from typing import Optional
from typing import Tuple

from ...types import ASTNodes
from ...types import RefDict


def replace_ref_with_def(nodes: ASTNodes, refs: RefDict, do_replace: bool) -> Tuple[RefDict, List[str]]:
    """
    Convert ``[text][link-def]`` to ``[text](link-url)``
    Convert ``[link-def][]``     to ``[link-def](link-url)``
    Convert ``[link-def]``       to ``[link-def](link-url)``

    If `do_replace` is True, replace the ref with def.
    Otherwise, just extract the used refs.

    Return the used refs, and the ``[text][link-def]`` and ``[link-def][]``
    texts whose definition is not found.
    """

    used_defs: RefDict = {}
    undefined: List[str] = []

    for n in nodes:
        if "children" in n:
            used, undef = replace_ref_with_def(n["children"], refs, do_replace)
            used_defs.update(used)
            undefined.extend(undef)

        if n["type"] != "text":
            continue

        t: str = n["text"]
        link = re.match(r"^\[(.*?)\](\[([^\]]*?)\])?$", t)
        if not link:
            continue

        gs = link.groups()
        txt: str = gs[0]
        definition: Optional[str] = None
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
        elif gs[1] is not None:
            # A lone ``[text]`` is usually plain text, so only the two-bracket forms are reported.
            undefined.append(t)

    return used_defs, undefined
