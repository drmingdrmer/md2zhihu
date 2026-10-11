"""
Tests of md2zhihu.publish, which pushes the output folder of a run to its asset repo.
"""

import os
import subprocess

import md2zhihu
from md2zhihu.publish import push

push_url = "https://someone:TOKEN@github.com/x/y.git"


def test_push(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out" / "a").mkdir(parents=True)
    (tmp_path / "out" / "a.md").write_text("# a\n")
    (tmp_path / "out" / "a" / "x.jpg").write_bytes(b"jpg")
    (tmp_path / "out" / "b.md").write_text("# b\n")
    bare = str(tmp_path / "assets.git")
    subprocess.run(["git", "init", "-q", "--bare", bare], check=True)

    # git pushes to the local bare repo instead of github.com.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url." + bare + ".insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", push_url)
    repo = md2zhihu.AssetRepo(push_url, branch="b")
    options = md2zhihu.Options("zhihu", "out", "out", "out/", asset_repo=repo)

    push(options, [["src/a.md", "out/a.md"], ["src/b.md", "out/b.md"]])

    files = subprocess.run(
        ["git", "--git-dir", bare, "ls-tree", "-r", "--name-only", "b"], capture_output=True, text=True, check=True
    )
    assert files.stdout == "a.md\na/x.jpg\nb.md\n"

    # The message names the options of the run and every converted markdown, with the token masked.
    log = subprocess.run(
        ["git", "--git-dir", bare, "log", "-1", "--format=%B", "b"], capture_output=True, text=True, check=True
    )
    want_message = [
        "Built pages by md2zhihu",
        "",
        "Options:",
        "platform: zhihu",
        "output_dir: out",
        "asset_output_dir: out",
        "md_output: out/",
        "asset_repo: https://***@github.com/x/y.git, branch b",
        "code_width: None",
        "plain_code_width: None",
        "keep_meta: False",
        "ref_files: []",
        "jekyll: False",
        "rewrite: []",
        "download: False",
        "",
        "Converted:",
        "src/a.md",
        "src/b.md",
    ]
    assert log.stdout == "\n".join(want_message) + "\n\n"

    # push() removes the .git that it created.
    assert sorted(os.listdir(tmp_path / "out")) == ["a", "a.md", "b.md"]
