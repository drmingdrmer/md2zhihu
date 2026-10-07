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

# Inputs with undefined references, as name: (markdown, the references that Article warns about).
# A lone `[x]` is usually plain text, so it gets no warning.
warn_cases = {
    "warn-full": ("[foo][bar]", ["[foo][bar]"]),
    "warn-collapsed": ("[baz][]", ["[baz][]"]),
    "warn-in-text": ("see [foo][bar] now", ["[foo][bar]"]),
    "warn-two-on-one-line": ("[a][b] and [c][]", ["[a][b]", "[c][]"]),
    "warn-shortcut": ("[x]", []),
    "warn-emphasis-text": ("[*foo*][bar]", ["[*foo*][bar]"]),
}

# The parsers under test: "v2" is the vendored mistune 2.0.0a6, and "v3" is mistune 3.
# MD2ZHIHU_UPDATE_GOLDEN=1 writes the golden files from the output of the first one.
engines = ["v2", "v3"]

# The v3 difference that comes from md2zhihu's math post-processing, which the v3 pipeline still runs
# on mistune 3's text, in which an escape such as `\{` has lost its backslash.
v3_math = "an escape in math loses its backslash"

# Known bugs and differences, as case name: {parser: reason}. An end-to-end conversion is named "e2e/<name>".
# A case with a v2 entry expects the correct result, written by hand.
# A v3 entry that is not a bug above is an intended change of the output.
# The case must fail on each listed parser, and MD2ZHIHU_UPDATE_GOLDEN=1 skips it.
expected_fail = {
    "code-blocks": {"v3": "an indented code block loses the empty line that mistune 2 keeps at its end"},
    "e2e/github": {"v3": v3_math},
    "e2e/minimal_mistake": {"v3": v3_math},
    "e2e/simple": {"v3": v3_math},
    "e2e/wechat": {"v3": v3_math},
    "e2e/weibo": {"v3": v3_math},
    "e2e/zhihu": {"v3": v3_math},
    "e2e/zhihu-deep-asset-dir": {"v3": v3_math},
    "e2e/zhihu-localrepo": {"v3": v3_math},
    "e2e/zhihu-pushall": {"v3": v3_math},
    "escapes-backslash": {"v2": "a backslash escape loses its backslash", "v3": "a backslash escape loses its backslash"},
    "inline-autolink": {"v2": "an autolink crashes parse_in_list_tables"},
    "inline-cjk-underscore": {"v2": "`_` between Chinese characters becomes emphasis"},
    "inline-hard-break-backslash": {"v3": "a backslash hard break is written as two trailing spaces"},
    "inline-image-cjk-url": {"v3": "a remote image URL is percent-encoded"},
    "inline-link-ampersand": {"v2": "`&` in a link URL becomes `&amp;`"},
    "math-dollar-amounts": {"v2": "`$5 and $` becomes inline math", "v3": "`$5 and $` becomes inline math"},
    "math-emphasis": {
        "v2": "emphasis inside `$...$` splits the text, so the math is not found",
        "v3": "emphasis inside `$...$` splits the text, so the math is not found",
    },
    "math-escape": {
        "v2": "an escape inside `$...$` splits the text, so the math is not found",
        "v3": "an escape inside `$...$` loses its backslash",
    },
    "math-latex": {"v3": r"an escape such as `\{` in math loses its backslash"},
    "math-table-cell": {
        "v2": r"`\|` in math in a table cell loses its backslash, which splits the cell",
        "v3": r"`\|` in math in a table cell loses its backslash, which splits the cell",
    },
    "refs-emphasis-text": {"v2": "a reference whose text has emphasis is not resolved"},
    "refs-image": {"v2": "an image reference is not resolved, and its definition is removed"},
    "refs-label-case": {"v2": "a reference label in another case is not resolved"},
    "tables-escaped-pipe": {
        "v2": r"`\|` in a table cell loses its backslash, which splits the cell",
        "v3": r"`\|` in a table cell loses its backslash, which splits the cell",
    },
    "tables-syntax": {"v3": "a table row with fewer cells than the header gets empty cells, as GFM requires"},
    "warn-emphasis-text": {"v2": "an undefined reference whose text has emphasis gets no warning"},
}

# The inputs in test/data/robust/examples.json that md2zhihu fails to convert, as example id: {parser: error}.
# The error is the exception type, or "***:" when MDRender meets a node type it does not know.
robust_failures = {
    # An autolink crashes parse_in_list_tables.
    "commonmark-297": {"v2": "TypeError"},
    "commonmark-327": {"v2": "TypeError"},
    "commonmark-565": {"v2": "TypeError"},
    "commonmark-566": {"v2": "TypeError"},
    "commonmark-567": {"v2": "TypeError"},
    "commonmark-568": {"v2": "TypeError"},
    "commonmark-569": {"v2": "TypeError"},
    "commonmark-570": {"v2": "TypeError"},
    "commonmark-571": {"v2": "TypeError"},
    "commonmark-572": {"v2": "TypeError"},
    "commonmark-574": {"v2": "TypeError"},
    "commonmark-575": {"v2": "TypeError"},
    "commonmark-576": {"v2": "TypeError"},
    "non-commonmark-18": {"v2": "TypeError"},
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


def case_params(names, prefix=""):
    """
    Pair each case with each engine. The name of a case in expected_fail is prefix + name.
    """
    params = []
    for engine in engines:
        for name in names:
            params.append(case_param(engine, name, prefix))
    return params


def case_param(engine, name, prefix):
    if update_golden and engine != engines[0]:
        return pytest.param(engine, name, marks=pytest.mark.skip(reason="the golden files are written from " + engines[0]))
    reason = expected_fail.get(prefix + name, {}).get(engine)
    if reason is None:
        return pytest.param(engine, name)
    if update_golden:
        return pytest.param(engine, name, marks=pytest.mark.skip(reason=reason))
    return pytest.param(engine, name, marks=pytest.mark.xfail(strict=True, reason=reason))


@pytest.mark.parametrize("engine,name", case_params(sorted(e2e_conversions), "e2e/"))
def test_e2e_conversion(engine, name, tmp_path, monkeypatch, restore_root_logger):
    work_dir, args, result_path = e2e_conversions[name]

    # Convert a copy, so that no output lands in the source tree.
    case = work_dir.split("/")[0]
    shutil.copytree(os.path.join(test_data, case, "src"), tmp_path / case / "src")

    monkeypatch.chdir(tmp_path / work_dir)
    monkeypatch.setattr(sys, "argv", ["md2zhihu"] + args)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    monkeypatch.setenv("MD2ZHIHU_PARSER", engine)
    md2zhihu.main()

    with open(result_path, encoding="utf-8") as f:
        got = f.read()
    check_golden(os.path.join(golden_base, "e2e", name + ".md"), got)


@pytest.mark.parametrize("engine,name", case_params(case_names))
def test_case(engine, name, tmp_path, monkeypatch):
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
    parser_config = md2zhihu.ParserConfig(populate_reference, [], engine)

    with open(src_path, encoding="utf-8") as f:
        md_text = f.read()
    article = md2zhihu.Article(parser_config, conf, md_text)

    got = "\n".join(article.render())
    check_golden(os.path.join(golden_base, name + ".md"), got)


@pytest.mark.parametrize("engine,name", case_params(warn_cases))
def test_undefined_reference_warning(engine, name, tmp_path, caplog):
    md_text, want = warn_cases[name]
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("warn.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [], engine)

    caplog.set_level(logging.INFO)
    md2zhihu.Article(parser_config, conf, md_text)

    got = []
    for record in caplog.records:
        warning = re.search(r"Warn: undefined reference (.*) in 'warn\.md'", record.getMessage())
        if warning:
            got.append(warning.group(1))
    assert got == want


@pytest.mark.parametrize("engine", engines)
def test_examples_convert(engine, tmp_path):
    # Platform "null" has no features, so only the parser and MDRender run.
    with open(os.path.join(test_data, "robust", "examples.json"), encoding="utf-8") as f:
        examples = json.load(f)
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("example.md", "null", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [], engine)

    got = {}
    for example_id, md_text in examples.items():
        try:
            article = md2zhihu.Article(parser_config, conf, md_text)
            output = "\n".join(article.render())
        except Exception as e:
            got[example_id] = type(e).__name__
            continue
        if "***:" in output:
            got[example_id] = "***:"

    want = {}
    for example_id, errors in robust_failures.items():
        if engine in errors:
            want[example_id] = errors[engine]
    assert got == want
