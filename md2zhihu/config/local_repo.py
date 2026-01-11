import os

from k3handy import pjoin


class LocalRepo(object):
    is_local: bool = True
    """
    Create relative path for url in ``md_path` pointing to ``asset_dir_path``.
    """

    def __init__(self, md_path: str, asset_dir_path: str) -> None:
        md_base = os.path.split(md_path)[0]
        rel = os.path.relpath(
            asset_dir_path,
            start=md_base,
        )
        if rel == ".":
            rel = ""
        self.path_pattern: str = pjoin(rel, "{path}")
