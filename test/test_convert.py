"""
Fast golden tests of md2zhihu's markdown output.

They run md2zhihu in the test process, and need no browser, LaTeX tool, network or git remote.
Run them with MD2ZHIHU_UPDATE_GOLDEN=1 to rewrite the golden files from the current output.
"""

import json
import logging
import os
import re
import shutil
import sys

import k3down2
import pytest

import md2zhihu

this_base = os.path.dirname(os.path.abspath(__file__))
test_data = os.path.join(this_base, "data")
cases_dir = os.path.join(test_data, "cases")
golden_base = os.path.join(cases_dir, "want")

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

# The small cases in test/data/cases/src/, by file name without ".md".
case_files = os.listdir(os.path.join(cases_dir, "src"))
case_names = sorted(fn[: -len(".md")] for fn in case_files if fn.endswith(".md"))

# Config arguments of the small cases that need them.
case_config = {
    "refs-external": {"ref_files": ["src/refs-external.yaml"]},
    "blocks-front-matter-keep-meta": {"keep_meta": True},
}

# The small cases that keep references as written, as Article.chunks() does.
no_populate_cases = {"refs-no-populate"}

# Inputs with references, as name: (markdown, the undefined references that Article warns about).
# A lone `[x]` is usually plain text, so it gets no warning.
warn_cases = {
    "warn-full": ("[foo][bar]", ["[foo][bar]"]),
    "warn-collapsed": ("[baz][]", ["[baz][]"]),
    "warn-in-text": ("see [foo][bar] now", ["[foo][bar]"]),
    "warn-two-on-one-line": ("[a][b] and [c][]", ["[a][b]", "[c][]"]),
    "warn-shortcut": ("[x]", []),
    "warn-defined": ("[ok][]\n\n[ok]: http://ok", []),
    "warn-emphasis-text": ("[*foo*][bar]", ["[*foo*][bar]"]),
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


@pytest.mark.parametrize("name", case_names)
def test_case(name, tmp_path, monkeypatch):
    # The zhihu converters wrap tables and math in fake_convert's markers,
    # so the output shows which nodes the parser built and the text they hold.
    monkeypatch.chdir(cases_dir)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    src_path = "src/" + name + ".md"
    out_dir = str(tmp_path)
    options = case_config.get(name, {})
    conf = md2zhihu.Config(src_path, "zhihu", out_dir, out_dir, md_output_path=out_dir + "/", **options)
    os.makedirs(conf.asset_output_dir)

    populate_reference = name not in no_populate_cases
    parser_config = md2zhihu.ParserConfig(populate_reference, [])

    with open(src_path, encoding="utf-8") as f:
        md_text = f.read()
    article = md2zhihu.Article(parser_config, conf, md_text)

    got = "\n".join(article.render())
    check_golden(os.path.join(golden_base, name + ".md"), got)


@pytest.mark.parametrize("name", sorted(warn_cases))
def test_undefined_reference_warning(name, tmp_path, caplog):
    md_text, want = warn_cases[name]
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("warn.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [])

    caplog.set_level(logging.INFO)
    md2zhihu.Article(parser_config, conf, md_text)

    got = []
    for record in caplog.records:
        warning = re.search(r"Warn: undefined reference (.*) in 'warn\.md'", record.getMessage())
        if warning:
            got.append(warning.group(1))
    assert got == want


def test_examples_convert(tmp_path):
    # Platform "null" has no features, so only the parser and MDRender run.
    with open(os.path.join(test_data, "robust", "examples.json"), encoding="utf-8") as f:
        examples = json.load(f)
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("example.md", "null", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [])

    got = {}
    for example_id, md_text in examples.items():
        try:
            article = md2zhihu.Article(parser_config, conf, md_text)
            output = "\n".join(article.render())
        except Exception as e:
            got[example_id] = type(e).__name__
            continue
        # MDRender writes "***:" and the type of a node that it does not know.
        if "***:" in output:
            got[example_id] = "***:"

    assert got == {}
