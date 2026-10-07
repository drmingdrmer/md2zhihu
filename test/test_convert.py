"""
Fast golden tests of md2zhihu's markdown output.

They run md2zhihu in the test process, and need no browser, LaTeX tool, network or git remote.
Run them with MD2ZHIHU_UPDATE_GOLDEN=1 to rewrite the golden files from the current output.
"""

import logging
import os
import shutil
import sys

import k3down2
import pytest

import md2zhihu

this_base = os.path.dirname(os.path.abspath(__file__))
test_data = os.path.join(this_base, "data")
golden_base = os.path.join(test_data, "cases", "want")

update_golden = os.environ.get("MD2ZHIHU_UPDATE_GOLDEN") == "1"

# The conversions that the end-to-end tests in test_md2zhihu.py run, as
# name: (working directory under test/data, md2zhihu arguments, path of the result markdown).
# --repo and --download are left out, so nothing is pushed or downloaded.
e2e_conversions = {
    "zhihu-meta": ("zhihu-meta", ["src/simple.md", "--output-dir", "dst", "--keep-meta"], "dst/simple.md"),
    "zhihu-download": ("zhihu-download", ["src/simple.md", "--output-dir", "dst"], "dst/simple.md"),
    "zhihu-embed": ("zhihu-embed", ["src/simple.md", "--output-dir", "dst", "--embed", "[.]md$"], "dst/simple.md"),
    "zhihu-extrefs": ("zhihu-extrefs", ["src/simple.md", "--output-dir", "dst", "--refs", "src/refs.yaml"], "dst/simple.md"),
    "zhihu-img-url": ("zhihu-img-url", ["src/simple.md", "--output-dir", "dst"], "dst/simple.md"),
    "zhihu": ("zhihu", ["src/simple.md", "--output-dir", "dst"], "dst/simple.md"),
    "github": ("github", ["src/simple.md", "--output-dir", "dst", "-p", "github"], "dst/simple.md"),
    "wechat": ("wechat", ["src/simple.md", "--output-dir", "dst", "-p", "wechat"], "dst/simple.md"),
    "weibo": ("weibo", ["src/simple.md", "--output-dir", "dst", "-p", "weibo"], "dst/simple.md"),
    "simple": ("simple", ["src/simple.md", "--output-dir", "dst", "-p", "simple"], "dst/simple.md"),
    "zhihu-rewrite": (
        "zhihu-rewrite",
        ["src/simple.md", "--output-dir", "dst", "--platform", "zhihu", "--rewrite", "^s", "/foo/"],
        "dst/simple.md",
    ),
    "zhihu-math-inline": (
        "zhihu-math-inline",
        ["src/simple.md", "--output-dir", "dst", "--platform", "zhihu"],
        "dst/simple.md",
    ),
    "zhihu-jekyll": (
        "zhihu-jekyll",
        ["src/2021-06-11-simple.md", "--output-dir", "dst", "--platform", "zhihu", "--jekyll"],
        "dst/2021-06-11-simple.md",
    ),
    "minimal_mistake": (
        "minimal_mistake",
        ["src/simple.md", "--output-dir", "dst", "--platform", "minimal_mistake"],
        "dst/simple.md",
    ),
    "transparent": (
        "transparent",
        ["src/transparent.md", "--output-dir", "dst", "--platform", "transparent"],
        "dst/transparent.md",
    ),
    "zhihu-localrepo": ("zhihu-localrepo/src", ["simple.md", "--md-output", "out.md", "--output-dir", "."], "out.md"),
    "zhihu-pushall": ("zhihu-pushall/src", ["simple.md", "--md-output", "out.md", "--output-dir", "."], "out.md"),
    "zhihu-deep-asset-dir": (
        "zhihu-deep-asset-dir/src",
        ["simple.md", "--md-output", "out.md", "--output-dir", ".", "--asset-output-dir", "foo/bar"],
        "out.md",
    ),
}


def fake_convert(input_typ, content, output_typ, opt=None):
    """
    Replace ``k3down2.convert``, which needs a browser or LaTeX tools.

    An image holds the converter's input, and its file name has an md5 of that input.
    Any other output shows the input in a marker.
    So a golden file changes when the text that md2zhihu passes to a converter changes.
    """
    if output_typ == "jpg":
        return content.encode("utf-8")
    return "{%s:%s}%s{/%s}" % (input_typ, output_typ, content, input_typ)


def check_golden(golden_path, got):
    if update_golden:
        os.makedirs(os.path.dirname(golden_path), exist_ok=True)
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(got)
        return

    with open(golden_path, encoding="utf-8") as f:
        want = f.read()
    assert got == want


@pytest.fixture
def restore_root_logger():
    # md2zhihu.main() adds a stdout handler to the root logger on each call.
    handlers = list(logging.root.handlers)
    level = logging.root.level
    yield
    logging.root.handlers = handlers
    logging.root.setLevel(level)


@pytest.mark.parametrize("name", sorted(e2e_conversions))
def test_e2e_conversion(name, tmp_path, monkeypatch, restore_root_logger):
    work_dir, args, result_path = e2e_conversions[name]

    # Convert a copy, so that no output lands in the source tree.
    case = work_dir.split("/")[0]
    shutil.copytree(os.path.join(test_data, case, "src"), tmp_path / case / "src")

    monkeypatch.chdir(tmp_path / work_dir)
    monkeypatch.setattr(sys, "argv", ["md2zhihu"] + args)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    md2zhihu.main()

    with open(result_path, encoding="utf-8") as f:
        got = f.read()
    check_golden(os.path.join(golden_base, "e2e", name + ".md"), got)
