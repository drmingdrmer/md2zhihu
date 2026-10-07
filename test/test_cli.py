"""
Tests of the md2zhihu command: its exit status and what it prints.

They run md2zhihu.main() in the test process.
"""

import importlib.metadata
import io
import logging
import os
import subprocess
import sys

import pytest

import md2zhihu
from md2zhihu.cli import MessageFormatter
from md2zhihu.cli import use_color
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

# --embed flags before an input, as (md2zhihu arguments, the parsed regexes).
# Each flag takes one regex, so "a.md" stays the input.
embed_args = [
    (["a.md"], None),
    (["--embed", "x", "a.md"], ["x"]),
    (["--embed", "x", "--embed", "y", "a.md"], ["x", "y"]),
]

# The lines that md2zhihu prints for the message "x", as (log level, color, line).
formatted_messages = [
    (logging.INFO, False, "x"),
    (logging.INFO, True, "x"),
    (logging.WARNING, False, "md2zhihu: warning: x"),
    (logging.WARNING, True, "\x1b[33mmd2zhihu: warning:\x1b[0m x"),
    (logging.ERROR, True, "\x1b[31mmd2zhihu: error:\x1b[0m x"),
]

# Whether md2zhihu colors its messages, as (stream is a terminal, value of NO_COLOR, color).
# An empty NO_COLOR counts as unset, as https://no-color.org says.
color_cases = [
    (True, None, True),
    (True, "", True),
    (True, "1", False),
    (False, None, False),
]


class Terminal(io.StringIO):
    def isatty(self):
        return True


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
def test_bad_argument(name, tmp_path, monkeypatch, capsys, restore_logger):
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


def test_repo_without_remote(tmp_path, monkeypatch, capsys, restore_logger):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    (tmp_path / "a.md").write_text("# a\n")

    code, err = run_failing(monkeypatch, capsys, ["a.md", "-r", "."])

    assert code == 2
    assert err == usage_error("--repo .: the git repo in the working directory has no remote")


def test_output(tmp_path, monkeypatch, capsys, restore_logger):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("see [x][y]\n")
    (tmp_path / "b.md").write_text("# b\n")
    monkeypatch.setattr(sys, "argv", ["md2zhihu", "a.md", "b.md"])

    md2zhihu.main()

    out, err = capsys.readouterr()
    assert out == ""
    assert err == (
        "md2zhihu: warning: undefined reference [x][y] in 'a.md'\n"
        "a.md -> _md2/a.md\n"
        "b.md -> _md2/b.md\n"
        "no --repo, so images are referenced by relative path\n"
    )


def test_verbose_output(tmp_path, monkeypatch, capsys, restore_logger):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# a\n")
    monkeypatch.setattr(sys, "argv", ["md2zhihu", "-v", "a.md", "-p", "github", "-o", "out/"])

    md2zhihu.main()

    err = capsys.readouterr().err
    assert err == (
        "--platform: github\n"
        "--output-dir: _md2\n"
        "--md-output: out/\n"
        "--asset-output-dir: _md2\n"
        "a.md -> out/a.md\n"
        "no --repo, so images are referenced by relative path\n"
    )


@pytest.mark.parametrize("level, color, want", formatted_messages)
def test_message_formatter(level, color, want):
    record = logging.makeLogRecord({"msg": "x", "levelno": level, "levelname": logging.getLevelName(level)})
    got = MessageFormatter(color).format(record)
    assert got == want


@pytest.mark.parametrize("tty, no_color, want", color_cases)
def test_use_color(tty, no_color, want, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    if no_color is not None:
        monkeypatch.setenv("NO_COLOR", no_color)
    stream = Terminal() if tty else io.StringIO()

    got = use_color(stream)
    assert got == want


def test_usage(monkeypatch):
    # A wide terminal keeps the usage in one line.
    monkeypatch.setenv("COLUMNS", "1000")

    got = create_parser().format_usage()
    assert got == (
        "usage: md2zhihu [-h] [-d DIR] [-o PATH] [--asset-output-dir DIR] [-r URL]"
        " [-p {zhihu,github,wechat,weibo,simple,minimal_mistake,transparent}] [--keep-meta] [--jekyll]"
        " [--refs YAML] [--rewrite REGEX REPLACEMENT] [--download] [--embed REGEX] [--code-width PIXELS]"
        " [-v] [--version] MARKDOWN [MARKDOWN ...]\n"
    )


def test_version(monkeypatch, capsys, restore_logger):
    monkeypatch.setattr(sys, "argv", ["md2zhihu", "--version"])

    with pytest.raises(SystemExit) as exit_info:
        md2zhihu.main()

    out = capsys.readouterr().out
    assert exit_info.value.code == 0
    assert out == "md2zhihu " + importlib.metadata.version("md2zhihu") + "\n"


@pytest.mark.parametrize("args, want", embed_args)
def test_embed_args(args, want):
    parsed = create_parser().parse_args(args)
    assert parsed.src_path == ["a.md"]
    assert parsed.embed == want
