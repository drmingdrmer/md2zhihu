import hashlib
import os
import re

import k3git
from k3handy import CMD_RAISE_STDOUT
from k3handy import CmdFlag
from k3str import to_bytes

from ..utils import msg


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
