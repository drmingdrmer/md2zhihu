"""Configuration classes for md2zhihu"""

import argparse
import hashlib
import os
import re
import shutil
from typing import List

import k3git
from k3color import darkred
from k3color import darkyellow
from k3handy import CMD_RAISE_STDOUT
from k3handy import CmdFlag
from k3handy import cmdpass
from k3handy import pjoin
from k3handy import to_bytes

from ..platform import platform_feature_dict
from ..utils import msg


class LocalRepo(object):
    is_local = True
    """
    Create relative path for url in ``md_path` pointing to ``asset_dir_path``.
    """

    def __init__(self, md_path, asset_dir_path):
        md_base = os.path.split(md_path)[0]
        rel = os.path.relpath(
            asset_dir_path,
            start=md_base,
        )
        if rel == ".":
            rel = ""
        self.path_pattern = pjoin(rel, "{path}")


class AssetRepo(object):
    is_local = False

    def __init__(self, repo_url, cdn=True):
        #  TODO: test rendering md rendering with pushed assets

        self.cdn = cdn

        repo_url = self.parse_shortcut_repo_url(repo_url)

        gu = k3git.GitUrl.parse(repo_url)
        f = gu.fields

        if f["scheme"] == "https" and "committer" in f and "token" in f:
            url = gu.fmt(scheme="https")
        else:
            url = gu.fmt(scheme="ssh")

        host, user, repo, branch = (
            f.get("host"),
            f.get("user"),
            f.get("repo"),
            f.get("branch"),
        )

        self.url = url

        url_patterns = {
            "github.com": "https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}",
            "gitee.com": "https://gitee.com/{user}/{repo}/raw/{branch}/{path}",
        }

        cdn_patterns = {
            "github.com": "https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}",
        }

        if branch is None:
            branch = self.make_default_branch()
        else:
            #  strip '@'
            branch = branch[1:]

        self.host = host
        self.user = user
        self.repo = repo
        self.branch = branch

        ptn = url_patterns[host]
        if self.cdn and host == "github.com":
            ptn = cdn_patterns[host]

        self.path_pattern = ptn.format(user=user, repo=repo, branch=branch, path="{path}")

    def parse_shortcut_repo_url(self, repo_url):
        """
        If repo_url is a shortcut specifying to use local git repo remote url,
        convert repo shortcut to url.

            md2zhihu --repo .                   # default remote, default branch
            md2zhihu --repo .@brach             # default remote
            md2zhihu --repo remote@brach

        """

        elts = repo_url.split("@", 1)
        first = elts.pop(0)
        g = k3git.Git(k3git.GitOpt(), cwd=".")

        is_shortcut = False

        # ".": use cwd git
        # ".@foo_branch": use cwd git and specified branch
        if first == ".":
            msg("Using current git to store assets...")

            u = self.get_remote_url()
            is_shortcut = True

        elif g.remote_get(first) is not None:
            msg("Using current git remote: {} to store assets...".format(first))
            u = self.get_remote_url(first)
            is_shortcut = True

        if is_shortcut:
            if len(elts) > 0:
                u += "@" + elts[0]
            msg("Parsed shortcut {} to {}".format(repo_url, u))
            repo_url = u

        return repo_url

    def get_remote_url(self, remote=None):
        g = k3git.Git(k3git.GitOpt(), cwd=".")

        if remote is None:
            branch = g.head_branch(flag=[CmdFlag.RAISE])
            remote = g.branch_default_remote(branch, flag=[CmdFlag.NONE])
            if remote is None:
                # `branch` has no remote configured.
                remote = g.cmdf("remote", flag=CMD_RAISE_STDOUT)[0]

        remote_url = g.remote_get(remote, flag=[CmdFlag.RAISE])
        return remote_url

    def make_default_branch(self):
        cwd = os.getcwd().split(os.path.sep)
        cwdmd5 = hashlib.md5(to_bytes(os.getcwd())).hexdigest()
        branch = "_md2zhihu_{tail}_{md5}".format(
            tail=cwd[-1],
            md5=cwdmd5[:8],
        )
        # escape special chars
        branch = re.sub(r"[^a-zA-Z0-9_\-=]+", "", branch)

        return branch


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
