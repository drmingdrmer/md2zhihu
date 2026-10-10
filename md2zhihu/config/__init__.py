"""Configuration classes for md2zhihu"""

import argparse
import os
import re
import shutil
import subprocess
from typing import List

from k3handy import CMD_NONE_ONELINE
from k3handy import cmdf
from k3handy import cmdpass
from k3handy import pjoin

from ..errors import PushError
from ..platform import platform_feature_dict
from ..utils import debug
from ..utils import mask_url_credential
from .asset_repo import AssetRepo
from .local_repo import LocalRepo

# The committer of the assets, for each part of it that git has no config for, as on a fresh CI runner.
fallback_identity = {"user.name": "md2zhihu", "user.email": "noreply@localhost"}

# The width of the image of a code block with a language, such as ```python, and of one without, such as an ASCII diagram.
default_code_width = 600
default_plain_code_width = 1000


class Config(object):
    #  TODO refactor var names
    def __init__(
        self,
        src_path,
        platform,
        output_dir,
        asset_output_dir,
        asset_repo=None,
        md_output_path=None,
        code_width=None,
        keep_meta=None,
        ref_files=None,
        jekyll=False,
        rewrite=None,
        download=False,
        plain_code_width=None,
    ):
        """
        Config of markdown rendering

        Args:
            src_path(str): path to markdown to convert.

            platform(str): target platform the converted markdown compatible with.

            output_dir(str): the output dir path to which converted/generated file saves.

            asset_repo(AssetRepo): git repo to upload output files, i.e.
                    result markdown, moved image or generated images.

            md_output_path(str): when present, specifies the path of the result markdown or result dir.
                    ``{title}`` in it is replaced with the article name.

            code_width(int): the width of the image of each code block.
                    Default: 600 for a block with a language, and 1000 for a block without one.

            plain_code_width(int): the width of the image of a code block without a language,
                    such as an ASCII diagram. Default: code_width if given, else 1000.

            keep_meta(bool): whether to keep the jekyll meta file header.

        """

        self.output_dir = output_dir
        self.md_output_path = md_output_path
        self.platform: str = platform
        self.features: dict = platform_feature_dict.get(platform, dict())
        self.src_path = src_path
        self.root_src_path = self.src_path

        # A width given for every code block also applies to a block without a language.
        if plain_code_width is None:
            plain_code_width = code_width
        if plain_code_width is None:
            plain_code_width = default_plain_code_width
        self.plain_code_width = plain_code_width

        if code_width is None:
            code_width = default_code_width
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

        assert self.md_output_path is not None

        self.md_output_path = self.md_output_path.format(title=self.article_name)

        if self.md_output_path.endswith("/"):
            self.md_output_base = self.md_output_path
            self.md_output_path = pjoin(self.md_output_path, fn)
        else:
            self.md_output_base = os.path.split(os.path.abspath(self.md_output_path))[0]

        if asset_repo is None:
            # The URL of an asset is its path from the markdown, so that it does not depend on output_dir.
            self.asset_repo = LocalRepo(self.md_output_path, self.asset_output_dir)
            self.rel_dir = ""
        else:
            # The repo holds output_dir, so the URL of an asset has the path of the asset in output_dir.
            self.asset_repo = asset_repo
            self.rel_dir = os.path.relpath(self.asset_output_dir, self.output_dir)

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
        """
        Commit `output_dir` and push it to the asset repo.
        A `.git` that this creates in `output_dir` is removed afterwards, also when the push fails.
        """
        git_path = pjoin(self.output_dir, ".git")
        has_git = os.path.exists(git_path)

        # -q: md2zhihu prints one line for the push, so git prints only its errors.
        cmdpass("git", "init", "-q", cwd=self.output_dir)
        try:
            self._commit_and_push(args, src_dst_fns)
        finally:
            if not has_git:
                debug("Removing tmp git dir: ", git_path)
                shutil.rmtree(git_path)

    def _commit_and_push(self, args: argparse.Namespace, src_dst_fns: List[List[str]]) -> None:
        x = dict(cwd=self.output_dir)

        args_str = "\n".join([k + ": " + str(v) for (k, v) in args.__dict__.items()])
        args_str = mask_url_credential(args_str)
        conf_str = "\n".join([k + ": " + str(v) for (k, v) in self.__dict__.items()])
        fns_str = "\n".join([src for (src, dst) in src_dst_fns])

        cmdpass("git", "add", ".", **x)

        # Commit as the user that git knows.
        identity = []
        for key, fallback in fallback_identity.items():
            value = cmdf("git", "config", key, flag=CMD_NONE_ONELINE, **x)
            if not value:
                identity += ["-c", key + "=" + fallback]

        cmdpass(
            "git",
            *identity,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "\n".join(
                [
                    "Built pages by md2zhihu",
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
        # Push with error handling
        try:
            cmdpass(
                "git",
                "push",
                "-q",
                "-f",
                self.asset_repo.url,
                "HEAD:refs/heads/" + self.asset_repo.branch,
                **x,
            )
        except subprocess.CalledProcessError:
            repo = self.asset_repo
            err = mask_url_credential(f"failed to push {self.output_dir} to {repo.url}, branch {repo.branch}")
            # The git error shows the push URL with the token, so it is not chained.
            raise PushError(err) from None
