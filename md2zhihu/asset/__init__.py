import hashlib
import os
import re
import shutil
from typing import TYPE_CHECKING
from typing import List
from typing import Optional
from urllib.parse import unquote
from urllib.parse import urlsplit

import urllib3
from k3handy import pjoin
from k3handy import to_bytes

from ..errors import DownloadError
from ..errors import MissingFileError

if TYPE_CHECKING:
    from ..config import Config
    from ..renderer.md_render import MDRender
    from ..renderer.render_node import RenderNode

# The characters of a file name that break the image URL that it is stored under:
# a space ends the URL in markdown, a server reads "%", "#" and "?" as URL syntax, and "/" as a folder.
unsafe_name_chars = re.compile(r"[\s%#?/]")

# How long to wait for an image server to connect and to send data, in seconds, so that a stalled server ends the run.
download_timeout = urllib3.Timeout(connect=10.0, read=30.0)

# The connections of --download, which the downloads from one server share.
pool = urllib3.PoolManager()

# The file name suffixes of markdown. A link to a markdown file names another article, so it stays as written.
markdown_suffixes = (".md", ".markdown")


def save_image_to_asset_dir(mdrender: "MDRender", rnode: "RenderNode") -> Optional[List[str]]:
    #  {'alt': 'openacid',
    #   'src': 'https://...',
    #   'title': None,
    #   'type': 'image'},

    n = rnode.node

    src: str = n["src"]
    if re.match(r"https?://", src):
        if not mdrender.conf.download:
            return None

        fn = src.split("/")[-1].split("#")[0].split("?")[0]
        # mistune percent-encodes the URL, such as "图片.png" to "%E5%9B%BE%E7%89%87.png".
        fn = unquote(fn)
        fn = unsafe_name_chars.sub("-", fn)

        content_md5 = hashlib.md5(to_bytes(src)).hexdigest()
        content_md5 = content_md5[:16]
        fn = content_md5 + "-" + fn

        target = pjoin(mdrender.conf.asset_output_dir, fn)

        if not os.path.exists(target):
            try:
                r = pool.request("GET", src, timeout=download_timeout)
            except urllib3.exceptions.HTTPError as e:
                raise DownloadError(f"failed to download {src}: {e}") from e
            if r.status != 200:
                raise DownloadError(f"failed to download {src}: HTTP status {r.status}")

            with open(target, "wb") as f:
                f.write(r.data)

        n["src"] = mdrender.conf.img_url(fn)

        return None

    src = mdrender.conf.relpath_from_cwd(src)
    if not os.path.exists(src):
        raise MissingFileError(f"image not found: {src!r}, used in {mdrender.conf.src_path!r}")

    fn = copy_to_asset_dir(mdrender.conf, src)

    n["src"] = mdrender.conf.img_url(fn)

    # Transform ast node but does not render, leave the task to default image
    # renderer.
    return None


def save_linked_file_to_asset_dir(mdrender: "MDRender", rnode: "RenderNode") -> Optional[List[str]]:
    """Point a link to a local file at a copy of the file in the asset dir, and leave the rendering to the default renderer."""
    n = rnode.node
    n["link"] = store_linked_file(mdrender.conf, n["link"])
    return None


def store_linked_file(conf: "Config", url: str) -> str:
    """
    Copy the local file that the link URL `url` refers to into the asset dir, and return the URL of the copy.
    Return `url` as it is if it refers to no local file, such as a web page, a heading, a folder or a missing file,
    or if it refers to a markdown file.
    """
    parts = urlsplit(url)
    is_path = parts.scheme == "" and parts.netloc == "" and parts.query == ""
    if not is_path:
        return url

    # mistune 3 percent-encodes a URL, but md2zhihu opens a local file by its path, such as "文件/a.pdf".
    path = unquote(parts.path)
    if path == "" or path.lower().endswith(markdown_suffixes):
        return url

    path = conf.relpath_from_cwd(path)
    if not os.path.isfile(path):
        return url

    fn = copy_to_asset_dir(conf, path)
    stored_url = conf.img_url(fn)
    if parts.fragment != "":
        # Such as "#page=2" of a PDF.
        stored_url += "#" + parts.fragment
    return stored_url


def copy_to_asset_dir(conf: "Config", path: str) -> str:
    """Copy the file at `path` into the asset dir, under a name made of an md5 of its content and its file name. Return the name."""
    fn = os.path.split(path)[1]
    fn = unsafe_name_chars.sub("-", fn)

    with open(path, "rb") as f:
        content = f.read()

    content_md5 = hashlib.md5(content).hexdigest()
    content_md5 = content_md5[:16]
    fn = content_md5 + "-" + fn

    target = pjoin(conf.asset_output_dir, fn)
    shutil.copyfile(path, target)

    return fn
