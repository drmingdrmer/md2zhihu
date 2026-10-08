import re
from typing import Optional
from typing import Tuple

import yaml
from k3fs import fread

from ...config import Config
from ...types import RefDict

# A link reference definition: "[label]: destination", with an optional title in "...", '...' or (...), and nothing after it.
# As in CommonMark, a definition may be indented by up to 3 spaces.
ref_definition = re.compile(r""" {0,3}\[(.*?)\]:(\s*(?:<[^<>]*>|\S+)(?:\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?\s*)$""")

# A fence of a fenced code block: 3 or more "`" or "~", indented by up to 3 spaces, and the text after it.
code_fence = re.compile(r" {0,3}(`{3,}|~{3,})(.*)$")


def load_external_refs(conf: Config) -> RefDict:
    refs: RefDict = {}
    for ref_path in conf.ref_files:
        fcont = fread(ref_path)
        y = yaml.safe_load(fcont)
        for r in y.get("universal", []):
            refs.update(r)
        for r in y.get(conf.platform, []):
            refs.update(r)

    return refs


def extract_ref_definitions(cont: str) -> Tuple[str, RefDict]:
    lines = cont.split("\n")
    rst = []
    refs: RefDict = {}
    # The fence of the code block that the line is in, or None.
    fence: Optional[str] = None
    for line in lines:
        in_code = fence is not None
        fence = next_fence(fence, line)

        # A definition whose URL is on the next line stays in the text, for the parser to read.
        r = ref_definition.match(line)
        if r and not in_code:
            gs = r.groups()
            refs[gs[0]] = gs[1]
        else:
            rst.append(line)
    return "\n".join(rst), refs


def next_fence(fence: Optional[str], line: str) -> Optional[str]:
    """
    Return the fence of the code block that the line after `line` is in, or None.
    `fence` is the fence of the code block that `line` is in, or None.
    """
    m = code_fence.match(line)
    if m is None:
        return fence

    marks, after = m.groups()
    if fence is None:
        # A "`" fence has no "`" after it, so "``` `a` ```" is a code span in a paragraph.
        if marks[0] == "`" and "`" in after:
            return None
        return marks

    # A closing fence has the same character, is at least as long, and has nothing after it.
    same_fence = marks[0] == fence[0] and len(marks) >= len(fence)
    if same_fence and after.strip() == "":
        return None
    return fence
