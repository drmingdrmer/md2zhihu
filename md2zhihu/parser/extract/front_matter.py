import re
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple

from ...types import RefDict
from .refs import load_yaml
from .refs import mapping_in
from .refs import refs_in


class FrontMatter(object):
    """
    The font matter is the yaml enclosed between `---` at the top of a markdown.
    """

    def __init__(self, front_matter_text: str, src_path: str = "the markdown") -> None:
        """Raise FormatError, which names `src_path`, if the front matter is not valid YAML."""
        self.text: str = front_matter_text
        self.data: Dict[str, Any] = load_yaml(front_matter_text, "the front matter of " + src_path)

    def get_refs(self, platform: str, src_path: str = "the markdown") -> RefDict:
        """
        Get refs from front matter.
        Raise FormatError, which names `src_path`, if "refs" or "platform_refs" has a shape that md2zhihu can not use.
        """
        dic: RefDict = {}

        meta = self.data
        # Front matter that is empty, or that is not a mapping, such as "Foo" in "---\nFoo\n---", has no refs.
        if not isinstance(meta, dict):
            return dic

        where = " in the front matter of " + src_path

        # Collect universal refs
        dic.update(refs_in(meta.get("refs"), "refs" + where))

        # Collect platform specific refs
        platform_refs = mapping_in(meta.get("platform_refs"), "platform_refs" + where)
        dic.update(refs_in(platform_refs.get(platform), "platform_refs." + platform + where))

        return dic


def extract_front_matter(cont: str, src_path: str = "the markdown") -> Tuple[str, Optional[FrontMatter]]:
    meta: Optional[FrontMatter] = None
    m = re.match(r"^ *--- *\n(.*?)\n---\n", cont, flags=re.DOTALL | re.UNICODE)
    if m:
        cont = cont[m.end() :]
        meta_text = m.groups()[0].strip()
        meta = FrontMatter(meta_text, src_path)

    return cont, meta
