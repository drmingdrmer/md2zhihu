"""Configuration classes for md2zhihu"""

import argparse
import os
import re
import shutil
from typing import List

from k3color import darkred
from k3color import darkyellow
from k3handy import cmdpass
from k3handy import pjoin

from ..platform import platform_feature_dict
from ..utils import msg
from .asset_reop import AssetRepo
from .local_repo import LocalRepo


class Config(object):
    #  TODO refactor var names
    def __init__(
        self,
        src_path,
        platform,
        output_dir,
        asset_output_dir,
        asset_repo_url=None,
        md_output_path=None,
        code_width=1000,
        keep_meta=None,
        ref_files=None,
        jekyll=False,
        rewrite=None,
        download=False,
    ):
        """
        Config of markdown rendering

        Args:
            src_path(str): path to markdown to convert.

            platform(str): target platform the converted markdown compatible with.

            output_dir(str): the output dir path to which converted/generated file saves.

            asset_repo_url(str): url of a git repo to upload output files, i.e.
                    result markdown, moved image or generated images.

            md_output_path(str): when present, specifies the path of the result markdown or result dir.

            code_width(int): the result image width of code block.

            keep_meta(bool): whether to keep the jekyll meta file header.

        """

        self.output_dir = output_dir
        self.md_output_path = md_output_path
        self.platform: str = platform
        self.features: dict = platform_feature_dict.get(platform, dict())
        self.src_path = src_path
        self.root_src_path = self.src_path

        self.code_width = code_width
        if keep_meta is None:
            keep_meta = False
        self.keep_meta = keep_meta

        if ref_files is None:
            ref_files = []
        self.ref_files = ref_files

        self.jekyll = jekyll

        if rewrite is None:
            rewrite = []
        self.rewrite = rewrite

        self.download = download

        fn = os.path.split(self.src_path)[-1]

        trim_fn = re.match(r"\d\d\d\d-\d\d-\d\d-(.*)", fn)
        if trim_fn:
            trim_fn = trim_fn.groups()[0]
        else:
            trim_fn = fn

        if not self.jekyll:
            fn = trim_fn

        self.article_name = trim_fn.rsplit(".", 1)[0]

        self.asset_output_dir = pjoin(asset_output_dir, self.article_name)
        self.rel_dir = os.path.relpath(self.asset_output_dir, self.output_dir)

        assert self.md_output_path is not None

        if self.md_output_path.endswith("/"):
            self.md_output_base = self.md_output_path
            self.md_output_path = pjoin(self.md_output_path, fn)
        else:
            self.md_output_base = os.path.split(os.path.abspath(self.md_output_path))[0]

        if asset_repo_url is None:
            self.asset_repo = LocalRepo(self.md_output_path, self.output_dir)
        else:
            self.asset_repo = AssetRepo(asset_repo_url)

        for k in (
            "src_path",
            "platform",
            "output_dir",
            "asset_output_dir",
            "md_output_base",
            "md_output_path",
        ):
            msg(darkyellow(k), ": ", getattr(self, k))

    def img_url(self, fn):
        url = self.asset_repo.path_pattern.format(path=pjoin(self.rel_dir, fn))

        for pattern, repl in self.rewrite:
            url = re.sub(pattern, repl, url)

        return url

    def relpath_from_cwd(self, p):
        """
        If ``p`` starts with "/", it is path starts from CWD.
        Otherwise, it is relative to the md src path.

        :return the path that can be used to read or write.
        """

        if p.startswith("/"):
            # absolute path from CWD.
            p = p[1:]
        else:
            # relative path from markdown containing dir.
            p = os.path.join(os.path.split(self.src_path)[0], p)
            abs_path = os.path.abspath(p)
            p = os.path.relpath(abs_path, start=os.getcwd())

        return p

    def push(self, args: argparse.Namespace, src_dst_fns: List[List[str]]) -> None:
        x = dict(cwd=self.output_dir)

        git_path = pjoin(self.output_dir, ".git")
        has_git = os.path.exists(git_path)

        args_str = "\n".join([k + ": " + str(v) for (k, v) in args.__dict__.items()])
        conf_str = "\n".join([k + ": " + str(v) for (k, v) in self.__dict__.items()])
        fns_str = "\n".join([src for (src, dst) in src_dst_fns])

        cmdpass("git", "init", **x)
        cmdpass("git", "add", ".", **x)
        cmdpass(
            "git",
            "-c",
            "user.name='drmingdrmer'",
            "-c",
            "user.email='drdr.xp@gmail.com'",
            "commit",
            "--allow-empty",
            "-m",
            "\n".join(
                [
                    "Built pages by md2zhihu by drdr.xp@gmail.com",
                    "",
                    "CLI args:",
                    args_str,
                    "",
                    "Config:",
                    conf_str,
                    "",
                    "Converted:",
                    fns_str,
                ]
            ),
            **x,
        )
        # Validate branch before force push
        branch = self.asset_repo.branch
        protected_branches = ["main", "master"]
        if branch in protected_branches:
            raise ValueError(f"Cannot force push to protected branch: {branch}. Use a different branch name.")

        # Push with error handling
        try:
            cmdpass(
                "git",
                "push",
                "-f",
                self.asset_repo.url,
                "HEAD:refs/heads/" + self.asset_repo.branch,
                **x,
            )
        except Exception as e:
            msg(darkred(f"Failed to push to {self.asset_repo.url}: {e}"))
            raise

        if not has_git:
            msg("Removing tmp git dir: ", self.output_dir + "/.git")
            shutil.rmtree(self.output_dir + "/.git")
