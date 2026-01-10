import hashlib
import os
import re
import shutil
import urllib3
from k3handy import pjoin, to_bytes


def save_image_to_asset_dir(mdrender, rnode):
    #  {'alt': 'openacid',
    #   'src': 'https://...',
    #   'title': None,
    #   'type': 'image'},

    n = rnode.node

    src = n["src"]
    if re.match(r"https?://", src):
        if not mdrender.conf.download:
            return None

        fn = src.split("/")[-1].split("#")[0].split("?")[0]

        content_md5 = hashlib.md5(to_bytes(src)).hexdigest()
        content_md5 = content_md5[:16]
        fn = content_md5 + "-" + fn

        target = pjoin(mdrender.conf.asset_output_dir, fn)

        if not os.path.exists(target):
            http = urllib3.PoolManager()
            r = http.request("GET", src)
            if r.status != 200:
                raise Exception("Failure to download:", src)

            with open(target, "wb") as f:
                f.write(r.data)

        n["src"] = mdrender.conf.img_url(fn)

        return None

    src = mdrender.conf.relpath_from_cwd(src)

    fn = os.path.split(src)[1]

    with open(src, "rb") as f:
        content = f.read()

    content_md5 = hashlib.md5(content).hexdigest()
    content_md5 = content_md5[:16]
    fn = content_md5 + "-" + fn

    target = pjoin(mdrender.conf.asset_output_dir, fn)
    shutil.copyfile(src, target)

    n["src"] = mdrender.conf.img_url(fn)

    # Transform ast node but does not render, leave the task to default image
    # renderer.
    return None
