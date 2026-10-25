"""Push the output folder of a run to its asset repo."""

import os
import shutil
import subprocess
from typing import List

from k3handy import CMD_NONE_ONELINE
from k3handy import cmdf
from k3handy import cmdpass
from k3handy import pjoin

from .config import AssetRepo
from .config import Options
from .errors import PushError
from .utils import debug
from .utils import mask_url_credential

# The committer of the assets, for each part of it that git has no config for, as on a fresh CI runner.
fallback_identity = {"user.name": "md2zhihu", "user.email": "noreply@localhost"}

# The config of the commit that stops the auto maintenance, which git starts after a commit.
# Newer git runs it in the background, so it could write in the .git that push() removes, such as
# .git/objects/info/packs. Git before 2.29 starts "git gc --auto" instead, which gc.auto=0 stops.
no_maintenance = ["-c", "maintenance.auto=false", "-c", "gc.auto=0"]


def push(options: Options, src_dst_fns: List[List[str]]) -> None:
    """
    Commit `options.output_dir` and push it to `options.asset_repo`.
    `src_dst_fns` holds the source path and the output path of each markdown that the run converted.
    A `.git` that this creates in `output_dir` is removed afterwards, also when the push fails.
    """
    repo = options.asset_repo
    if repo is None:
        raise ValueError("options.asset_repo is None, so there is no repo to push to")

    git_path = pjoin(options.output_dir, ".git")
    has_git = os.path.exists(git_path)

    # -q: md2zhihu prints one line for the push, so git prints only its errors.
    cmdpass("git", "init", "-q", cwd=options.output_dir)
    try:
        _commit_and_push(options, repo, src_dst_fns)
    finally:
        if not has_git:
            debug("Removing tmp git dir: ", git_path)
            shutil.rmtree(git_path)


def _commit_and_push(options: Options, repo: AssetRepo, src_dst_fns: List[List[str]]) -> None:
    x = dict(cwd=options.output_dir)

    options_str = "\n".join([k + ": " + str(v) for (k, v) in options.__dict__.items()])
    options_str = mask_url_credential(options_str)
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
        *no_maintenance,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "\n".join(
            [
                "Built pages by md2zhihu",
                "",
                "Options:",
                options_str,
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
            repo.url,
            "HEAD:refs/heads/" + repo.branch,
            **x,
        )
    except subprocess.CalledProcessError:
        err = mask_url_credential(f"failed to push {options.output_dir} to {repo.url}, branch {repo.branch}")
        # The git error shows the push URL with the token, so it is not chained.
        raise PushError(err) from None
