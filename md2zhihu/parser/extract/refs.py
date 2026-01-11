import re

import yaml
from k3fs import fread

from ...config import Config


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
