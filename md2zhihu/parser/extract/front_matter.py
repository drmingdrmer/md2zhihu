import re

import yaml


class FrontMatter(object):
    """
    The font matter is the yaml enclosed between `---` at the top of a markdown.
    """

    def __init__(self, front_matter_text: str):
        self.text = front_matter_text
        self.data = yaml.safe_load(front_matter_text)

    def get_refs(self, platform: str) -> dict:
        """
        Get refs from front matter.
        """
        dic = {}

        meta = self.data

        # Collect universal refs
        if "refs" in meta:
            refs = meta["refs"]

            for r in refs:
                dic.update(r)

        # Collect platform specific refs
        if "platform_refs" in meta:
            refs = meta["platform_refs"]
            if platform in refs:
                refs = refs[platform]

                for r in refs:
                    dic.update(r)

        return dic


def extract_front_matter(cont):
    meta = None
    m = re.match(r"^ *--- *\n(.*?)\n---\n", cont, flags=re.DOTALL | re.UNICODE)
    if m:
        cont = cont[m.end() :]
        meta_text = m.groups()[0].strip()
        meta = FrontMatter(meta_text)

    return cont, meta
