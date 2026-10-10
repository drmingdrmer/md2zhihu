from typing import Any
from typing import Dict

import yaml
from k3fs import fread

from ...config import Config
from ...errors import FormatError
from ...types import RefDict
from ..mistune3 import parse_ref


def load_external_refs(conf: Config) -> RefDict:
    refs: RefDict = {}
    for ref_path in conf.ref_files:
        fcont = fread(ref_path)
        loaded = yaml.safe_load(fcont)
        y = mapping_in(loaded, ref_path)
        refs.update(refs_in(y.get("universal"), "universal in " + ref_path))
        refs.update(refs_in(y.get(conf.platform), conf.platform + " in " + ref_path))

    return refs


def mapping_in(value: Any, where: str) -> Dict[str, Any]:
    """
    Return the mapping that YAML loaded as `value`, or an empty one if `value` is empty.
    Raise FormatError, which names `where`, for any other value.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise FormatError(where + ": must be a mapping")
    return value


def refs_in(value: Any, where: str) -> RefDict:
    """
    Return the references that YAML loaded as `value`: a mapping of names to URLs, or a list of such mappings.
    A URL may have a title, as in a link reference definition, such as `https://grpc.io "gRPC"`.
    Raise FormatError, which names `where`, for any other value.
    """
    if value is None:
        return {}

    mappings = value
    if isinstance(value, dict):
        mappings = [value]

    valid = isinstance(mappings, list) and all(is_text_mapping(m) for m in mappings)
    if not valid:
        raise FormatError(where + ": must be a mapping of names to URLs, or a list of such mappings")

    refs: RefDict = {}
    for m in mappings:
        for name, definition in m.items():
            ref = parse_ref(definition)
            if ref is None:
                raise FormatError(f'{where}: {name}: must be a URL and an optional title, such as https://grpc.io "gRPC"')
            refs[name] = ref
    return refs


def is_text_mapping(value: Any) -> bool:
    """Tell whether `value` is a mapping of text to text."""
    if not isinstance(value, dict):
        return False
    return all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
