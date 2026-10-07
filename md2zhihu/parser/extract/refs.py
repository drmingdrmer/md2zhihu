import re
from typing import Tuple

import yaml
from k3fs import fread

from ...config import Config
from ...types import RefDict


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
    for line in lines:
        # As in CommonMark, a definition may be indented by up to 3 spaces.
        # A definition whose URL is on the next line stays in the text, for the parser to read.
        r = re.match(r" {0,3}\[(.*?)\]:(\s*\S.*?)$", line, flags=re.UNICODE)
        if r:
            gs = r.groups()
            refs[gs[0]] = gs[1]
        else:
            rst.append(line)
    return "\n".join(rst), refs
