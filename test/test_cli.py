"""
Tests of the md2zhihu command: its exit status and what it prints.

They run md2zhihu.main() in the test process.
"""

import os
import subprocess
import sys

import pytest

import md2zhihu
from md2zhihu.cli.args import create_parser

# Bad arguments, as name: (md2zhihu arguments, the error message).
# The working directory holds a.md, b.md and the folder docs.
bad_args = {
    "missing-input": (["a.md", "nope.md"], "nope.md: no such file"),
    "folder-input": (["docs"], "docs: is a directory, pass the markdown files in it, such as docs/*.md"),
    "same-output": (["a.md", "b.md", "-o", "out.md"], "a.md and b.md both convert to out.md"),
    "protected-branch": (
        ["a.md", "-r", "git@github.com:x/y.git@main"],
        "--repo git@github.com:x/y.git@main: Cannot force push to protected branch: main. Use a different branch name.",
    ),
    "token-in-url": (
        ["a.md", "-r", "https://someone:TOKEN@github.com/x/y.git@master"],
        "--repo https://***@github.com/x/y.git@master: Cannot force push to protected branch: master. Use a different branch name.",
    ),
    "bad-url": (["a.md", "-r", "not a url"], "--repo not a url: unknown url: not a url;"),
    "unsupported-host": (
        ["a.md", "-r", "git@example.com:x/y.git"],
        "--repo git@example.com:x/y.git: unsupported git host: example.com, supported: github.com, gitee.com",
    ),
    "not-in-git": (
        ["a.md", "-r", "."],
        "--repo .: fatal: not a git repository (or any of the parent directories): .git",
    ),
}


def run_failing(monkeypatch, capsys, args):
    """Run md2zhihu with `args`, which must make it exit. Return the exit status and stderr."""
    monkeypatch.setattr(sys, "argv", ["md2zhihu"] + args)
    with pytest.raises(SystemExit) as exit_info:
        md2zhihu.main()
    return exit_info.value.code, capsys.readouterr().err


def usage_error(message):
    """Return what argparse writes to stderr for a usage error: the usage line, then the message."""
    return create_parser().format_usage() + "md2zhihu: error: " + message + "\n"


@pytest.mark.parametrize("name", sorted(bad_args))
def test_bad_argument(name, tmp_path, monkeypatch, capsys, restore_root_logger):
    args, want = bad_args[name]
    monkeypatch.chdir(tmp_path)
    # "--repo ." must not find a git repo in a parent folder of tmp_path.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    (tmp_path / "a.md").write_text("# a\n")
    (tmp_path / "b.md").write_text("# b\n")
    (tmp_path / "docs").mkdir()

    code, err = run_failing(monkeypatch, capsys, args)

    assert code == 2
    assert err == usage_error(want)
    # md2zhihu found the bad argument before it wrote anything.
    assert sorted(os.listdir(tmp_path)) == ["a.md", "b.md", "docs"]


def test_repo_without_remote(tmp_path, monkeypatch, capsys, restore_root_logger):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    (tmp_path / "a.md").write_text("# a\n")

    code, err = run_failing(monkeypatch, capsys, ["a.md", "-r", "."])

    assert code == 2
    assert err == usage_error("--repo .: the git repo in the working directory has no remote")
