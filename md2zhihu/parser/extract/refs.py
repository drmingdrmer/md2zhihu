import os
from typing import Any
from typing import Dict

import yaml
from k3fs import fread

from ...config import Config
from ...errors import FormatError
from ...errors import MissingFileError
from ...types import RefDict
from ..mistune3 import parse_ref


def load_external_refs(conf: Config) -> RefDict:
    refs: RefDict = {}
    for ref_path in conf.ref_files:
        if not os.path.isfile(ref_path):
            raise MissingFileError(f"refs file not found: {ref_path!r}")
        fcont = fread(ref_path)
        loaded = load_yaml(fcont, ref_path)
        y = mapping_in(loaded, ref_path)
        refs.update(refs_in(y.get("universal"), "universal in " + ref_path))
        refs.update(refs_in(y.get(conf.platform), conf.platform + " in " + ref_path))

    return refs


def load_yaml(text: str, where: str) -> Any:
    """
    Return the data in the YAML `text`.
    Raise FormatError, which names `where` and the place of the problem in `text`, if `text` is not valid YAML.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise FormatError(where + ": " + yaml_problem(e)) from e


def yaml_problem(e: yaml.YAMLError) -> str:
    """Return the problem that `e` reports, on one line, such as "line 1, column 8: expected the node content"."""
    if isinstance(e, yaml.MarkedYAMLError) and e.problem is not None and e.problem_mark is not None:
        mark = e.problem_mark
        return f"line {mark.line + 1}, column {mark.column + 1}: {e.problem}"
    # Such as a ReaderError for a character that YAML does not allow, which its first line names.
    return str(e).splitlines()[0]


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
