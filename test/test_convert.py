"""
Fast golden tests of md2zhihu's markdown output.

They run md2zhihu in the test process, and need no browser, LaTeX tool, network or git remote.
Run them with MD2ZHIHU_UPDATE_GOLDEN=1 to rewrite the golden files from the current output.
"""

import functools
import hashlib
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


@pytest.mark.parametrize("name", sorted(e2e_conversions))
def test_e2e_conversion(name, tmp_path, monkeypatch, restore_logger):
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

    # md2zhihu copies the file into the asset folder, with "-" for the space, and points the link at the copy.
    content_md5 = hashlib.md5(b"pdf").hexdigest()[:16]
    stored = content_md5 + "-paper-1.pdf"
    assert os.listdir("out/a") == [stored]
    assert (tmp_path / "out" / "a" / stored).read_bytes() == b"pdf"
    assert lines[0] == "[paper](a/" + stored + ")"


def request_convert(input_typ, content, output_typ, opt=None):
    """Replace ``k3down2.convert``: an image holds the whole request, so that two different requests make different images."""
    return json.dumps([input_typ, content, output_typ, opt]).encode("utf-8")


def test_each_conversion_has_its_own_image(tmp_path, monkeypatch):
    # $x$ and $$x$$ convert x with two converters, and two runs convert one code block at two widths into one folder.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(k3down2, "convert", request_convert)
    md_text = "inline $x$.\n\n$$x$$\n\n```\ncode\n```\n"

    urls = []
    for width in [600, 800]:
        conf = md2zhihu.Config("a.md", "simple", "out", "out", md_output_path="out/", plain_code_width=width)
        os.makedirs(conf.asset_output_dir, exist_ok=True)
        lines = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, md_text).render()
        urls.extend(re.findall(r"!\[\]\((.*?)\)", "\n".join(lines)))

    got = [(tmp_path / "out" / url).read_bytes() for url in urls]
    want = [
        request_convert("tex_inline", "x", "jpg"),
        request_convert("tex_block", "x", "jpg"),
        request_convert("code", "```\ncode\n```\n", "jpg", {"html": {"width": 600}}),
        request_convert("tex_inline", "x", "jpg"),
        request_convert("tex_block", "x", "jpg"),
        request_convert("code", "```\ncode\n```\n", "jpg", {"html": {"width": 800}}),
    ]
    assert got == want
    # The folder holds one file for each of the 4 different requests.
    stored = sorted(os.listdir(tmp_path / "out" / "a"))
    assert stored == sorted({os.path.basename(url) for url in urls})


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
    with open(os.path.join(test_data, "robust", "examples.json"), encoding="utf-8") as f:
        examples = json.load(f)
    out_dir = str(tmp_path)
    conf = md2zhihu.Config("example.md", "null", out_dir, out_dir, md_output_path=out_dir + "/")
    parser_config = md2zhihu.ParserConfig(True, [])

    got = {}
    for example_id, md_text in examples.items():
        # MDRender raises TypeError for a node type that it does not know.
        try:
            article = md2zhihu.Article(parser_config, conf, md_text)
            article.render()
        except Exception as e:
            got[example_id] = type(e).__name__

    assert got == {}
