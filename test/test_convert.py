"""
Fast golden tests of md2zhihu's markdown output.

They run md2zhihu in the test process, and need no browser, LaTeX tool, network or git remote.
Run them with MD2ZHIHU_UPDATE_GOLDEN=1 to rewrite the golden files from the current output.
"""

import copy
import functools
import hashlib
import html
import http.server
import json
import logging
import os
import re
import shutil
import socket
import sys
import threading

import k3down2
import pytest
import urllib3

import md2zhihu
from md2zhihu.errors import DownloadError
from md2zhihu.errors import EmbedCycleError
from md2zhihu.errors import MissingFileError
from md2zhihu.errors import NameClashError

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

# URLs in a markdown that is embedded from "src/sub" into "src", and the URLs after embedding.
rebase_cases = [
    ("x.png", "sub/x.png"),
    ("../x.png", "x.png"),
    ("/x.png", "/x.png"),
    ("https://a.com/x.png", "https://a.com/x.png"),
    ("mailto:a@b.com", "mailto:a@b.com"),
    ("#intro", "#intro"),
]

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

# Local images, as name: (file name, its URL in the markdown, the name of its copy after the md5, the URL of the copy after the md5).
# The copy's name has "-" for a character that breaks a URL, and the copy's URL keeps the query or the fragment.
local_images = {
    "svg-fragment": ("icons.svg", "icons.svg#home", "icons.svg", "icons.svg#home"),
    "query": ("x.png", "x.png?v=2", "x.png", "x.png?v=2"),
    "space": ("my logo.png", "<my logo.png>", "my-logo.png", "my-logo.png"),
    "percent": ("100%.png", "100%25.png", "100-.png", "100-.png"),
    "encoded-hash": ("C#.png", "C%23.png", "C-.png", "C-.png"),
    "unmatched-parenthesis": ("x).png", "<x).png>", "x).png", "x%29.png"),
}

# URLs, as (URL, the URL as md2zhihu writes it in a link or an image).
link_destinations = [
    ("a/x.png", "a/x.png"),
    ("https://en.wikipedia.org/wiki/Foo_(bar)", "https://en.wikipedia.org/wiki/Foo_(bar)"),
    ("a/x).png", "a/x%29.png"),
    ("a/(x.png", "a/%28x.png"),
    (")(", "%29%28"),
    ("my dir/x.png", "my%20dir/x.png"),
]

# Markdown files that embed themselves, as name: ({path: content}, the error message).
# md2zhihu reads src/a.md, and a content of None makes the path a symlink to src/a.md.
embed_cycles = {
    "direct": ({"src/a.md": "![](a.md)\n"}, "markdown embeds itself: 'src/a.md' -> 'src/a.md'"),
    "indirect": (
        {"src/a.md": "![](sub/b.md)\n", "src/sub/b.md": "![](../a.md)\n"},
        "markdown embeds itself: 'src/a.md' -> 'src/sub/b.md' -> 'src/a.md'",
    ),
    "symlink": (
        {"src/a.md": "![](link.md)\n", "src/link.md": None},
        "markdown embeds itself: 'src/a.md' -> 'src/link.md'",
    ),
}

# The links of src/a.md and of src/sub/b.md that it embeds, as written with and without populating references.
# Both define "r", for two URLs, so the "r" of b.md gets the name "r-2". Both "s" are ../s.pdf from src, so "s" keeps its name.
embed_ref_links = {
    True: ["[x](http://parent.example/) and [s](../s.pdf)", "", "[y](http://child.example/) and [s](../s.pdf)"],
    False: ["[x][r] and [s][]", "", "[y][r-2] and [s][]"],
}

# References whose URL has angle brackets or whose title has escapes, as name: (markdown, the lines that zhihu renders).
# A link gets the URL as mistune writes it, percent-encoded, and the title; the reference list shows the URL as written.
# The reference list escapes each char of the URL and the title that would start inline markdown, such as "\*",
# and a block marker that starts the title, such as "\#".
ref_definitions = {
    "image-angle-brackets": (
        '![logo][img]\n\n[img]: <https://example.com/logo.png> "Logo"\n',
        ['![logo](https://example.com/logo.png "Logo")', "", "", ""],
    ),
    "space-in-url": (
        "[x][r]\n\n[r]: <no such.pdf>\n",
        [
            "[x](no%20such.pdf)",
            "",
            "",
            "",
            "Reference:",
            "",
            "- r : [no such.pdf](no%20such.pdf)",
            "",
            "",
            "[r]: no%20such.pdf",
        ],
    ),
    "title-escapes": (
        "[a][t]\n\n" + r'[t]: https://a.com "say \"hi\" \\ now"',
        [
            r'[a](https://a.com "say \"hi\" \\ now")',
            "",
            "",
            "",
            "Reference:",
            "",
            r'- say "hi" \\ now : [https://a.com](https://a.com)',
            "",
            "",
            r'[t]: https://a.com "say \"hi\" \\ now"',
        ],
    ),
    "markdown-chars": (
        '[x][r]\n\n[r]: <https://a.com/_x_/[b]> "a *b* `c` <T>"\n',
        [
            '[x](https://a.com/_x_/%5Bb%5D "a *b* `c` <T>")',
            "",
            "",
            "",
            "Reference:",
            "",
            r"- a \*b\* &#96;c&#96; \<T> : [https://a.com/\_x\_/\[b\]](https://a.com/_x_/%5Bb%5D)",
            "",
            "",
            '[r]: https://a.com/_x_/%5Bb%5D "a *b* `c` <T>"',
        ],
    ),
    "title-block-marker": (
        '[a][r1] [b][r2] [c][r3]\n\n[r1]: https://a.com/1 "1. Intro"\n[r2]: https://a.com/2 "# x"\n'
        '[r3]: https://a.com/3 "    x"\n',
        [
            '[a](https://a.com/1 "1. Intro") [b](https://a.com/2 "# x") [c](https://a.com/3 "    x")',
            "",
            "",
            "",
            "Reference:",
            "",
            r"- 1\. Intro : [https://a.com/1](https://a.com/1)",
            "",
            r"- \# x : [https://a.com/2](https://a.com/2)",
            "",
            "- x : [https://a.com/3](https://a.com/3)",
            "",
            "",
            '[r1]: https://a.com/1 "1. Intro"',
            '[r2]: https://a.com/2 "# x"',
            '[r3]: https://a.com/3 "    x"',
        ],
    ),
    "url-char-reference": (
        "[x][r]\n\n[r]: https://a.com/?q=%26copy;\n",
        [
            "[x](https://a.com/?q=%26copy;)",
            "",
            "",
            "",
            "Reference:",
            "",
            r"- r : [https://a.com/?q=\&copy;](https://a.com/?q=%26copy;)",
            "",
            "",
            "[r]: https://a.com/?q=%26copy;",
        ],
    ),
    "front-matter": (
        '---\nrefs:\n  - r: <no such.pdf> "Paper"\n---\n[x][r]\n',
        [
            '[x](no%20such.pdf "Paper")',
            "",
            "",
            "",
            "Reference:",
            "",
            "- Paper : [no such.pdf](no%20such.pdf)",
            "",
            "",
            '[r]: no%20such.pdf "Paper"',
        ],
    ),
}

# The inputs of the examples of mistune's test fixtures, as name: markdown.
with open(os.path.join(test_data, "robust", "examples.json"), encoding="utf-8") as f:
    robust_examples = json.load(f)

# The CommonMark examples about code, emphasis, links and lists, by number: the sections "Indented code blocks",
# "Fenced code blocks", "Link reference definitions", "List items", "Lists", "Code spans",
# "Emphasis and strong emphasis", "Links" and "Autolinks".
# And 19, 40, 56, 62 and 201, whose paragraph has a line that would start a block where md2zhihu writes it.
# And 31, whose list item holds a thematic break.
meaning_examples = [
    19,
    31,
    40,
    56,
    62,
    *range(76, 116),
    *range(159, 182),
    201,
    *range(216, 288),
    *range(314, 331),
    *range(331, 459),
    *range(459, 543),
    *range(565, 584),
]

# The examples above whose meaning md2zhihu changes, as number: what changes.
meaning_changes = {
    469: "the URL is written percent-encoded, as encoded_destinations shows",
    470: "the URL is written percent-encoded, as encoded_destinations shows",
    471: "the URL is written percent-encoded, as encoded_destinations shows",
}

# The examples above whose URL has an unpaired "(" or ")", as number: the markdown that md2zhihu writes.
# md2zhihu percent-encodes each parenthesis, so that the written link parses back as one link.
encoded_destinations = {
    469: "[link](foo%28and%28bar%29)\n",
    470: "[link](foo%28and%28bar%29)\n",
    471: "[link](foo%29:)\n",
}

# Emphases that start or end a strong emphasis or an emphasis, as markdown: the markdown that md2zhihu writes.
nested_emphases = {
    # A "_" after "b" would touch the letter "c" and close nothing, so the outer emphasis takes "_".
    "_*b*c_\n": "_*b*c_\n",
    "_a*b*_\n": "_a*b*_\n",
    "_*强调*文字_\n": "_*强调*文字_\n",
    # A strong emphasis keeps "**", so the inner emphasis keeps "*", which still closes before a letter.
    "__*b*c__\n": "***b*c**\n",
    # With "*", the markers would join into "***x***", an emphasis that holds a strong emphasis.
    "**_x_**\n": "**_x_**\n",
    # With "*", the markers would join into "****x****", two strong emphases.
    "*__*x*__*\n": "***_x_***\n",
}

# Emphases in an emphasis next to a code span or math that the platform writes as plain text,
# as (platform, markdown): the markdown that md2zhihu writes.
plain_text_neighbors = {
    ("simple", "_*b*`c`_\n"): "_*b*c_\n",
    ("weibo", "_*b*`c`_\n"): "_*b*c_\n",
    ("weibo", "_`c`*b*_\n"): "_c*b*_\n",
    ("weibo", "_*b*$x$_\n"): "_*b*x_\n",
}

# A backslash escape or a character reference in markdown text, each of which writes one char, such as "\*" or "&#96;".
char_escape = re.compile(r"\\[!-/:-@\[-`{-~]|&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]*);")


def fake_convert(input_typ, content, output_typ, opt=None):
    """
    Replace ``k3down2.convert``, which needs a browser or LaTeX tools.

    The output shows the whole request in a marker: the converter, its options if any, and its input,
    such as `{code:jpg {"html": {"width": 600}}}print(1){/code}`. An image holds the marker as bytes.
    So two different requests make two different images, and a golden file changes when md2zhihu passes another request.
    """
    request = input_typ + ":" + output_typ
    if opt is not None:
        opt = copy.deepcopy(opt)
        has_asset_base = "asset_base" in opt.get("html", {})
        if has_asset_base:
            # The absolute path of the folder of the markdown, which differs between runs.
            opt["html"]["asset_base"] = os.path.relpath(opt["html"]["asset_base"])
        request += " " + json.dumps(opt, sort_keys=True)

    marker = "{%s}%s{/%s}" % (request, content, input_typ)
    if output_typ == "jpg":
        return marker.encode("utf-8")
    return marker


def file_contents(folder):
    """
    Return each file under `folder`, as its path relative to `folder`: its content.
    As git does, a file with a NUL byte counts as binary, such as a copied image, and its content shows as an md5 of it.
    """
    contents = {}
    for root, _, names in os.walk(folder):
        for name in names:
            path = os.path.join(root, name)
            with open(path, "rb") as f:
                data = f.read()

            rel = os.path.relpath(path, folder)
            is_binary = b"\0" in data
            if is_binary:
                contents[rel] = "md5 " + hashlib.md5(data).hexdigest()
            else:
                contents[rel] = data.decode("utf-8")
    return contents


def check_golden(golden_path, got):
    if update_golden:
        os.makedirs(os.path.dirname(golden_path), exist_ok=True)
        with open(golden_path, "w", encoding="utf-8") as f:
            f.write(got)
        return

    with open(golden_path, encoding="utf-8") as f:
        want = f.read()
    assert got == want


@pytest.mark.parametrize("name", sorted(e2e_conversions))
def test_e2e_conversion(name, tmp_path, monkeypatch):
    work_dir, args, result_path = e2e_conversions[name]

    # Convert a copy, so that no output lands in the source tree.
    case = work_dir.split("/")[0]
    shutil.copytree(os.path.join(test_data, case, "src"), tmp_path / case / "src")

    monkeypatch.chdir(tmp_path / work_dir)
    inputs = file_contents(".")
    monkeypatch.setattr(sys, "argv", ["md2zhihu"] + args)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    md2zhihu.main()

    with open(result_path, encoding="utf-8") as f:
        got = f.read()
    check_golden(os.path.join(golden_base, "e2e", name + ".md"), got)

    # Every other file that md2zhihu writes, such as an image, with its content.
    assets = {}
    for path, content in file_contents(".").items():
        if path not in inputs and path != result_path:
            assets[path] = content
    got_assets = json.dumps(assets, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    check_golden(os.path.join(golden_base, "e2e", name + ".assets.json"), got_assets)


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
        warning = re.search(r"undefined reference (.*) in 'warn\.md'", record.getMessage())
        if warning:
            got.append(warning.group(1))
    assert got == want


@pytest.mark.parametrize("src, want", rebase_cases)
def test_rebase_url(src, want):
    got = md2zhihu.parser.rebase_url("src/sub", "src", src)
    assert got == want


def test_crlf_line_ends(tmp_path):
    # The front matter is found, and its references are loaded, as with "\n" line ends.
    md_text = "---\r\ntitle: x\r\nrefs:\r\n  - a: http://a\r\n---\r\n\r\n[a][]\r\n"
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [])

    got = md2zhihu.Article(parser_config, conf, md_text).render()
    want = md2zhihu.Article(parser_config, conf, md_text.replace("\r\n", "\n")).render()
    assert got == want


def test_code_join():
    # The text of a code image, as wechat makes one, has a fence that the fence in the code does not close.
    node = {"type": "block_code", "info": "markdown", "text": "```python\nprint(1)\n```\n"}
    got = md2zhihu.converters.code_join(node)
    assert got == "````markdown\n```python\nprint(1)\n```\n````\n"


def test_linked_file(tmp_path, monkeypatch):
    (tmp_path / "paper 1.pdf").write_bytes(b"pdf")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "[paper](<paper 1.pdf>)").render()

    # md2zhihu copies the file into the asset folder, under its name with "-" for the space, and points the link at the copy.
    stored = "paper-1.pdf"
    assert os.listdir("out/a") == [stored]
    assert (tmp_path / "out" / "a" / stored).read_bytes() == b"pdf"
    assert lines[0] == "[paper](a/" + stored + ")"


def test_linked_files_of_one_name(tmp_path, monkeypatch):
    for folder, content in [("old", b"1"), ("new", b"2"), ("copy", b"1")]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "x.pdf").write_bytes(content)
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)
    parser_config = md2zhihu.ParserConfig(True, [])

    # Files of one name share one copy, so md2zhihu stops before a file of another content replaces the copy.
    article = md2zhihu.Article(parser_config, conf, "[old](old/x.pdf) [new](new/x.pdf)\n")
    with pytest.raises(NameClashError) as e:
        article.render()
    want = "linked files 'old/x.pdf' and 'new/x.pdf' differ, but both would be copied to 'out/a/x.pdf', used in 'a.md'"
    assert str(e.value) == want
    assert (tmp_path / "out" / "a" / "x.pdf").read_bytes() == b"1"

    # Files of the same content share the copy.
    lines = md2zhihu.Article(parser_config, conf, "[old](old/x.pdf) [copy](copy/x.pdf)\n").render()
    assert lines[0] == "[old](a/x.pdf) [copy](a/x.pdf)"


def test_linked_file_in_table(tmp_path, monkeypatch):
    for folder, content in [("old", b"1"), ("new", b"2")]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "x.pdf").write_bytes(content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)
    parser_config = md2zhihu.ParserConfig(True, [])

    # zhihu converts a table to html, and a link in it points at the copy of the file, as a link outside a table does.
    lines = md2zhihu.Article(parser_config, conf, "| file |\n| --- |\n| [old](old/x.pdf) |\n").render()
    assert lines == ["{table:html}| file |", "| --- |", "| [old](a/x.pdf) |", "{/table}", "", "", ""]
    assert (tmp_path / "out" / "a" / "x.pdf").read_bytes() == b"1"

    # A link in a table and a link outside it are checked against each other for files of one name.
    md_text = "[old](old/x.pdf)\n\n| file |\n| --- |\n| [new](new/x.pdf) |\n"
    with pytest.raises(NameClashError) as e:
        md2zhihu.Article(parser_config, conf, md_text).render()
    want = "linked files 'old/x.pdf' and 'new/x.pdf' differ, but both would be copied to 'out/a/x.pdf', used in 'a.md'"
    assert str(e.value) == want


@pytest.mark.parametrize("name", sorted(local_images))
def test_local_image(name, tmp_path, monkeypatch):
    fn, url, stored, stored_url = local_images[name]
    (tmp_path / fn).write_bytes(b"img")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "![](" + url + ")\n").render()

    content_md5 = hashlib.md5(b"img").hexdigest()[:16]
    assert os.listdir("out/a") == [content_md5 + "-" + stored]
    assert (tmp_path / "out" / "a" / (content_md5 + "-" + stored)).read_bytes() == b"img"
    # A markdown parser reads the whole URL of the copy back from the output.
    ast, _, _ = md2zhihu.parser.mistune3.parse("\n".join(lines), {}, True)
    image = ast[0]["children"][0]
    assert image["src"] == "a/" + content_md5 + "-" + stored_url


@pytest.mark.parametrize("url", ["data:image/png;base64,iVBORw0KGgo=", "//example.com/x.png"])
def test_image_url_as_written(url, tmp_path):
    # md2zhihu copies local images only: a data: URI holds the image itself, and "//example.com/x.png" is on the web.
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "![](" + url + ")\n").render()

    assert lines == ["![](" + url + ")", "", "", ""]


@pytest.mark.parametrize("url, want", link_destinations)
def test_link_destination(url, want):
    got = md2zhihu.renderer.md_render.link_destination(url)
    assert got == want


def test_reference_to_linked_file(tmp_path, monkeypatch):
    (tmp_path / "paper 1.pdf").write_bytes(b"pdf")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)
    md_text = '[paper][r]\n\n[r]: <paper 1.pdf> "Paper"\n'

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text).render()

    # As for an inline link, md2zhihu copies the file and points the link, the list and the definition at the copy.
    url = "a/paper-1.pdf"
    assert (tmp_path / "out" / url).read_bytes() == b"pdf"
    want = [
        f'[paper]({url} "Paper")',
        "",
        "",
        "",
        "Reference:",
        "",
        f"- Paper : [{url}]({url})",
        "",
        "",
        f'[r]: {url} "Paper"',
    ]
    assert lines == want


@pytest.mark.parametrize("name", sorted(ref_definitions))
def test_reference_definition(name, tmp_path, monkeypatch):
    md_text, want = ref_definitions[name]
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/")

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text).render()

    assert lines == want


@pytest.mark.parametrize("name", sorted(embed_cycles))
def test_embed_cycle(name, tmp_path, monkeypatch):
    files, want = embed_cycles[name]
    monkeypatch.chdir(tmp_path)
    for path, content in files.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if content is None:
            os.symlink("a.md", path)
        else:
            (tmp_path / path).write_text(content)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")

    with pytest.raises(EmbedCycleError) as e:
        md2zhihu.Article(md2zhihu.ParserConfig(True, [r"[.]md$"]), conf, files["src/a.md"])

    assert str(e.value) == want


def test_embed_failed_child(tmp_path, monkeypatch):
    (tmp_path / "src" / "sub").mkdir(parents=True)
    (tmp_path / "src" / "sub" / "b.md").write_text("![](nope.md)\n")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")

    with pytest.raises(MissingFileError) as e:
        md2zhihu.Article(md2zhihu.ParserConfig(True, [r"[.]md$"]), conf, "![](sub/b.md)\n")

    assert str(e.value) == "embedded markdown not found: 'src/sub/nope.md', used in 'src/sub/b.md'"
    # The embedded article read its path from its own config, so the config of src/a.md keeps its path.
    assert conf.src_path == "src/a.md"


def test_embed_encoded_path(tmp_path, monkeypatch):
    # mistune percent-encodes the URL, and md2zhihu matches the --embed regex with the path and opens it.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "子 文档.md").write_text("b\n")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")

    article = md2zhihu.Article(md2zhihu.ParserConfig(True, [r"子 文档[.]md$"]), conf, "![](<子 文档.md>)\n")

    assert article.render() == ["b", "", "", ""]


def test_embed_same_file_twice(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "b.md").write_text("b\n")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")

    article = md2zhihu.Article(md2zhihu.ParserConfig(True, [r"[.]md$"]), conf, "![](b.md)\n\n![](b.md)\n")

    assert article.render() == ["b", "", "b", "", "", ""]


@pytest.mark.parametrize("populate", sorted(embed_ref_links))
def test_embed_ref_name_clash(populate, tmp_path, monkeypatch):
    (tmp_path / "src" / "sub").mkdir(parents=True)
    (tmp_path / "src" / "sub" / "b.md").write_text("[y][r] and [s][]\n\n[r]: http://child.example/\n[s]: ../../s.pdf\n")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")
    md_text = "[x][r] and [s][]\n\n![](sub/b.md)\n\n[r]: http://parent.example/\n[s]: ../s.pdf\n"

    lines = md2zhihu.Article(md2zhihu.ParserConfig(populate, [r"[.]md$"]), conf, md_text).render()

    want = embed_ref_links[populate] + [
        "",
        "",
        "",
        "Reference:",
        "",
        "- r : [http://parent.example/](http://parent.example/)",
        "",
        "- r-2 : [http://child.example/](http://child.example/)",
        "",
        "- s : [../s.pdf](../s.pdf)",
        "",
        "",
        "[r]: http://parent.example/",
        "[r-2]: http://child.example/",
        "[s]: ../s.pdf",
    ]
    assert lines == want


def test_embed_remote_url(tmp_path):
    # md2zhihu embeds local markdown only, so the image of a markdown on the web stays as written.
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")

    article = md2zhihu.Article(md2zhihu.ParserConfig(True, [r"[.]md$"]), conf, "![](https://example.com/readme.md)\n")

    assert article.render() == ["![](https://example.com/readme.md)", "", "", ""]


@pytest.mark.parametrize("start", [99, 100, 999])
def test_ordered_list_start(start, tmp_path):
    # Each block of the first item starts at the column of its text, such as column 5 after "100. ".
    pad = " " * len(f"{start}. ")
    first_item = [
        f"{start}. first",
        "",
        pad + "continuation",
        "",
        pad + "- nested",
        "",
        pad + "```",
        pad + "code",
        pad + "```",
    ]
    md_text = "\n".join(first_item) + f"\n\n{start + 1}. next\n"
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("a.md", "zhihu", out_dir, out_dir, md_output_path=out_dir + "/")

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text).render()

    # The output parses to the same list: two items, the first with a paragraph, a nested list and code after its text.
    want, _, _ = md2zhihu.parser.mistune3.parse(md_text, {}, True)
    got, _, _ = md2zhihu.parser.mistune3.parse("\n".join(lines), {}, True)
    assert got == want


def test_render_twice(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.png").write_bytes(b"png")
    (tmp_path / "src" / "f.pdf").write_bytes(b"pdf")
    monkeypatch.chdir(tmp_path)
    conf = md2zhihu.Config("src/a.md", "zhihu", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)
    article = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "![](x.png) [f](f.pdf)\n")
    ast = copy.deepcopy(article.ast)
    conf_attrs = dict(vars(conf))

    renders = [article.render(), article.render()]
    chunks = [list(article.chunks()), list(article.chunks())]

    # Each render copies the files again and points the image and the link at the copies.
    img = "a/" + hashlib.md5(b"png").hexdigest()[:16] + "-x.png"
    pdf = "a/f.pdf"
    text = f"![]({img}) [f]({pdf})"
    assert renders == [[text, "", "", ""], [text, "", "", ""]]
    want_chunks = [("content", "paragraph", text + "\n"), ("ref_def", "", "")]
    assert chunks == [want_chunks, want_chunks]
    assert article.ast == ast
    assert vars(conf) == conf_attrs


def test_each_conversion_has_its_own_image(tmp_path, monkeypatch):
    # $x$ and $$x$$ convert x with two converters, and two runs convert one code block at two widths into one folder.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    md_text = "inline $x$.\n\n$$x$$\n\n```\ncode\n```\n"

    urls = []
    for width in [600, 800]:
        conf = md2zhihu.Config("a.md", "simple", "out", "out", md_output_path="out/", plain_code_width=width)
        os.makedirs(conf.asset_output_dir, exist_ok=True)
        lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text).render()
        urls.extend(re.findall(r"!\[\]\((.*?)\)", "\n".join(lines)))

    got = [(tmp_path / "out" / url).read_bytes() for url in urls]
    want = [
        fake_convert("tex_inline", "x", "jpg"),
        fake_convert("tex_block", "x", "jpg"),
        fake_convert("code", "```\ncode\n```\n", "jpg", {"html": {"width": 600}}),
        fake_convert("tex_inline", "x", "jpg"),
        fake_convert("tex_block", "x", "jpg"),
        fake_convert("code", "```\ncode\n```\n", "jpg", {"html": {"width": 800}}),
    ]
    assert got == want
    # The folder holds one file for each of the 4 different requests.
    stored = sorted(os.listdir(tmp_path / "out" / "a"))
    assert stored == sorted({os.path.basename(url) for url in urls})


def test_repeated_conversion(tmp_path, monkeypatch):
    # Two code blocks of one text make one request twice, and share its image.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(k3down2, "convert", fake_convert)
    conf = md2zhihu.Config("a.md", "simple", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)

    lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "```\nx\n```\n\n```\nx\n```\n").render()

    img = "a/x-48733fc970b587af.jpg"
    assert lines == [f"![]({img})", "", f"![]({img})", "", "", ""]
    assert file_contents("out") == {img: '{code:jpg {"html": {"width": 1000}}}```\nx\n```\n{/code}'}


def test_converter_failure(tmp_path, monkeypatch):
    # A failed conversion stops md2zhihu before it writes an image, or a markdown that would refer to the image.
    def convert(input_typ, content, output_typ, opt=None):
        raise RuntimeError("mermaid: parse error")

    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("```mermaid\ngraph\n```\n")
    monkeypatch.setattr(k3down2, "convert", convert)
    monkeypatch.setattr(sys, "argv", ["md2zhihu", "a.md"])

    with pytest.raises(RuntimeError) as e:
        md2zhihu.main()

    assert str(e.value) == "mermaid: parse error"
    assert file_contents(tmp_path) == {"a.md": "```mermaid\ngraph\n```\n"}


@pytest.fixture
def www(tmp_path):
    """Serve the files in tmp_path/www over HTTP on this machine. Yield the folder and its URL."""
    folder = tmp_path / "www"
    folder.mkdir()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield folder, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def download_article(url):
    """Return an Article of the image at `url`, which md2zhihu downloads into out/a/ in the working directory."""
    conf = md2zhihu.Config("a.md", "zhihu", "out", "out", md_output_path="out/", download=True)
    os.makedirs(conf.asset_output_dir)
    return md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "![](" + url + ")")


def test_download_image_name(tmp_path, monkeypatch, www):
    folder, base_url = www
    (folder / "图片 1.png").write_bytes(b"png")
    # The URL is percent-encoded, as mistune writes it.
    url = base_url + "/%E5%9B%BE%E7%89%87%201.png"
    monkeypatch.chdir(tmp_path)

    lines = download_article(url).render()

    # md2zhihu stores the image under the decoded file name, with "-" for the space, and refers to it by that name.
    url_md5 = hashlib.md5(url.encode()).hexdigest()[:16]
    stored = url_md5 + "-图片-1.png"
    assert os.listdir("out/a") == [stored]
    assert (tmp_path / "out" / "a" / stored).read_bytes() == b"png"
    assert lines[0] == "![](a/" + stored + ")"


def test_download_missing_image(tmp_path, monkeypatch, www):
    _, base_url = www
    url = base_url + "/x.png"
    monkeypatch.chdir(tmp_path)

    with pytest.raises(DownloadError) as exc_info:
        download_article(url).render()
    assert str(exc_info.value) == "failed to download " + url + ": HTTP status 404"


def test_download_stalled_server(tmp_path, monkeypatch):
    # The server accepts a connection, but never answers.
    server = socket.create_server(("127.0.0.1", 0))
    url = f"http://127.0.0.1:{server.getsockname()[1]}/x.png"
    monkeypatch.setattr(md2zhihu.asset, "download_timeout", urllib3.Timeout(connect=1.0, read=0.1))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(DownloadError) as exc_info:
        download_article(url).render()
    server.close()

    message = str(exc_info.value)
    assert message.startswith("failed to download " + url + ": ")
    assert "Read timed out" in message


def test_unknown_node_type(tmp_path):
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("a.md", "null", out_dir, out_dir, md_output_path=out_dir + "/")
    mdr = md2zhihu.MDRender(conf, features={})
    paragraph = {"type": "paragraph", "children": [{"type": "nope"}]}
    root = md2zhihu.RenderNode({"type": "ROOT", "children": [paragraph]})

    with pytest.raises(TypeError) as exc_info:
        mdr.render(root)
    assert str(exc_info.value) == "MDRender can not render a node of type 'nope', at ROOT -> paragraph -> nope"


def test_examples_convert(tmp_path):
    # Platform "null" has no features, so only the parser and MDRender run.
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("example.md", "null", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [])

    got = {}
    for example_id, md_text in robust_examples.items():
        # MDRender raises TypeError for a node type that it does not know.
        try:
            article = md2zhihu.Article(parser_config, conf, md_text)
            article.render()
        except Exception as e:
            got[example_id] = type(e).__name__

    assert got == {}


def test_examples_keep_meaning(tmp_path):
    """
    The markdown that md2zhihu writes for an example parses to the AST of the example:
    the same code text, emphasis, link destinations and titles, and list nesting.
    The ASTs are compared instead of the texts, because md2zhihu rewrites the whitespace that decides the nesting.
    """
    changed = []
    for number in meaning_examples:
        md_text = robust_examples["commonmark-%d" % number]
        want, _, _ = md2zhihu.parser.mistune3.parse(md_text, {}, True)
        got_md = write_example(md_text, tmp_path)
        got, _, _ = md2zhihu.parser.mistune3.parse(got_md, {}, True)
        want = plain_text(want)
        got = plain_text(got)
        if got != want:
            changed.append(number)

    assert changed == sorted(meaning_changes)


def plain_text(nodes):
    """
    Return a copy of the AST `nodes` without the text differences that mean nothing:
    each text has its backslash escapes and character references decoded, such as "\\*" to "*" and "&#96;" to "`",
    and an empty text is dropped.
    The parser keeps the text as written, and md2zhihu escapes each "*" and "`" in text.
    mistune leaves an empty text where it uses up a run of emphasis markers, such as on both sides of "_foo_" in "*_foo_*".
    """
    rst = []
    for n in nodes:
        n = dict(n)
        if n["type"] == "text":
            n["text"] = char_escape.sub(decode_char, n["text"])
            if n["text"] == "":
                continue
        if "children" in n:
            n["children"] = plain_text(n["children"])
        rst.append(n)
    return rst


def decode_char(m):
    """Return the char that the match of `char_escape` writes, such as "*" for "\\*" or "`" for "&#96;"."""
    s = m.group(0)
    if s.startswith("\\"):
        return s[1:]
    return html.unescape(s)


@pytest.mark.parametrize("number", sorted(encoded_destinations))
def test_example_encoded_destination(number, tmp_path):
    md_text = robust_examples["commonmark-%d" % number]

    got = write_example(md_text, tmp_path)

    assert got == encoded_destinations[number]


@pytest.mark.parametrize("md_text", sorted(nested_emphases))
def test_nested_emphasis(md_text, tmp_path):
    got_md = write_example(md_text, tmp_path)

    assert got_md == nested_emphases[md_text]

    want, _, _ = md2zhihu.parser.mistune3.parse(md_text, {}, True)
    got, _, _ = md2zhihu.parser.mistune3.parse(got_md, {}, True)
    want = plain_text(want)
    got = plain_text(got)
    assert got == want


@pytest.mark.parametrize("platform, md_text", sorted(plain_text_neighbors))
def test_emphasis_next_to_plain_text(platform, md_text, tmp_path):
    got = write_example(md_text, tmp_path, platform)

    assert got == plain_text_neighbors[(platform, md_text)]


def test_emphasis_neighbor_converted_once(tmp_path, monkeypatch):
    # md2zhihu renders the math after the inner emphasis early, to read the char next to its marker,
    # and reuses that render, so that it converts the math once.
    monkeypatch.chdir(tmp_path)
    requests = []

    def convert(input_typ, content, output_typ, opt=None):
        requests.append((input_typ, content, output_typ))
        return fake_convert(input_typ, content, output_typ, opt)

    monkeypatch.setattr(k3down2, "convert", convert)
    conf = md2zhihu.Config("a.md", "simple", "out", "out", md_output_path="out/")
    os.makedirs(conf.asset_output_dir)

    md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "_*b*$x$_\n").render()

    assert requests == [("tex_inline", "x", "jpg")]


def write_example(md_text, tmp_path, platform="null"):
    """
    Convert md_text with `platform`, and return the markdown that md2zhihu writes,
    without the list of the used references that Article.render() appends.
    """
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("example.md", platform, out_dir, out_dir, md_output_path=out_dir + "/")
    article = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text)
    mdr = md2zhihu.MDRender(conf, features=conf.features)
    root = md2zhihu.RenderNode({"type": "ROOT", "children": article.ast})
    lines = mdr.render(root)
    return "\n".join(lines)
