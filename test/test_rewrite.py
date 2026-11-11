"""
Tests of the rewrite rules, --rewrite, --rewrite-if and --rewrite-if-not, which change the URL destinations of the output.

They run md2zhihu.main() in the test process, on the platform transparent, which copies the local images and linked
files of a.md into _md2/a/ and changes nothing else, unless a test names another platform.
"""

import functools
import hashlib
import http.server
import sys
import threading

import k3down2
import pytest

import md2zhihu
from md2zhihu.config.rewrite import RewriteRule
from md2zhihu.config.rewrite import rewrite_url

# The URL of the copy of x.png, whose content is b"png": bff139fa05ac583f is from an md5 of the content.
x_png = "a/bff139fa05ac583f-x.png"

# The rule of the README that prefixes each relative destination,
# and leaves a URL with a scheme or a host, a root-relative path, and a query-only or fragment-only reference.
not_relative = "^([A-Za-z][A-Za-z0-9+.-]*:|//|/|[?#]|$)"
cdn = "https://cdn.example/assets/"
prefix_relative = ["--rewrite-if-not", not_relative, "^", cdn]

# Link destinations, as (destination in a.md, destination in the output with prefix_relative).
# A linked file is copied under its own name, such as x.png to a/x.png, and an image under an md5 prefix.
prefix_cases = [
    ("x.png", cdn + "a/x.png"),
    ("p.pdf", cdn + "a/p.pdf"),
    ("b.md", cdn + "b.md"),
    ("../other-post.md", cdn + "../other-post.md"),
    ("https://e.com/x", "https://e.com/x"),
    ("http://e.com/x", "http://e.com/x"),
    ("//e.com/x", "//e.com/x"),
    ("data:image/png;base64,AAAA", "data:image/png;base64,AAAA"),
    ("/root.md", "/root.md"),
    ("?q=1", "?q=1"),
    ("#top", "#top"),
    ("", ""),
]


def convert(tmp_path, monkeypatch, md, args, platform="transparent"):
    """Convert `md` as a.md, next to x.png and p.pdf, with the md2zhihu arguments `args`. Return the output markdown."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text(md)
    (tmp_path / "x.png").write_bytes(b"png")
    (tmp_path / "p.pdf").write_bytes(b"pdf")
    monkeypatch.setattr(sys, "argv", ["md2zhihu", "a.md", "-p", platform] + args)

    md2zhihu.main()

    return (tmp_path / "_md2" / "a.md").read_text()


def first_line(text):
    return text.split("\n")[0]


def test_no_rule(tmp_path, monkeypatch):
    md = "![](x.png) ![](https://e.com/r.png) [p](p.pdf) [b](../b.md) [h](https://e.com/h)\n"

    got = convert(tmp_path, monkeypatch, md, [])

    # A stored file has a URL relative to the output markdown, and any other destination stays as written.
    want = "![](" + x_png + ") ![](https://e.com/r.png) [p](a/p.pdf) [b](../b.md) [h](https://e.com/h)"
    assert first_line(got) == want


def test_unconditional(tmp_path, monkeypatch):
    md = "![](x.png) ![](https://e.com/r.png) [b](../b.md) [h](https://e.com/h)\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite", "^", "P/"])

    # --rewrite changes every destination: a stored image, a remote image and the links.
    want = "![](P/" + x_png + ") ![](P/https://e.com/r.png) [b](P/../b.md) [h](P/https://e.com/h)"
    assert first_line(got) == want


def test_positive_selector(tmp_path, monkeypatch):
    md = "![](x.png) [b](b.md) [h](https://e.com/h)\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite-if", "^a/", "^", cdn])

    # Only the stored image is in the folder a/.
    assert first_line(got) == "![](" + cdn + x_png + ") [b](b.md) [h](https://e.com/h)"


def test_negative_selector(tmp_path, monkeypatch):
    md = "![](x.png) [b](b.md) [h](https://e.com/h)\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite-if-not", "^a/", "^", "P/"])

    assert first_line(got) == "![](" + x_png + ") [b](P/b.md) [h](P/https://e.com/h)"


@pytest.mark.parametrize("src, want", prefix_cases)
def test_prefix_relative(src, want, tmp_path, monkeypatch):
    got = convert(tmp_path, monkeypatch, "[t](" + src + ")\n", prefix_relative)

    assert first_line(got) == "[t](" + want + ")"


def test_prefix_relative_mixed(tmp_path, monkeypatch):
    # One document holds every kind of destination, as images and as links.
    srcs = [src for src, _ in prefix_cases]
    md = " ".join("[t](" + src + ")" for src in srcs) + "\n\n" + "![](x.png) ![](https://e.com/r.png)\n"

    got = convert(tmp_path, monkeypatch, md, prefix_relative)

    want = " ".join("[t](" + want + ")" for _, want in prefix_cases)
    assert got.split("\n")[0:3] == [want, "", "![](" + cdn + x_png + ") ![](https://e.com/r.png)"]


def test_selected_without_pattern_match(tmp_path, monkeypatch):
    got = convert(tmp_path, monkeypatch, "[b](b.md)\n", ["--rewrite-if", "b", "^nope", "X"])

    # The selector matches, but the pattern does not, so nothing changes.
    assert first_line(got) == "[b](b.md)"


def test_rule_order(tmp_path, monkeypatch):
    args = [
        "--rewrite",
        "^b",
        "c",
        # The selector sees the result of the rule before it: "b.md" is now "c.md".
        "--rewrite-if",
        "^c",
        "$",
        "?1",
        "--rewrite-if-not",
        "^c",
        "^",
        "N/",
        "--rewrite",
        "^",
        "/",
    ]

    got = convert(tmp_path, monkeypatch, "[b](b.md) [d](d.md)\n", args)

    assert first_line(got) == "[b](/c.md?1) [d](/N/d.md)"


def test_reference_rewritten_once(tmp_path, monkeypatch):
    # A rule that is not idempotent shows a destination that is changed twice.
    md = "[a][r] and [b](p.pdf), and p.pdf as text.\n\n[r]: p.pdf\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite", "^", "P/"])

    assert got.split("\n") == [
        "[a](P/a/p.pdf) and [b](P/a/p.pdf), and p.pdf as text.",
        "",
        "",
        "",
        "Reference:",
        "",
        "- r : [P/a/p.pdf](P/a/p.pdf)",
        "",
        "",
        "[r]: P/a/p.pdf",
    ]


def test_render_twice(tmp_path, monkeypatch):
    # render() and chunks() write the same nodes, and each writes each destination changed once.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.png").write_bytes(b"png")
    conf = md2zhihu.Config("a.md", "transparent", "out", "out", md_output_path="out/", rewrite=[["^", "P/"]])
    (tmp_path / "out" / "a").mkdir(parents=True)
    article = md2zhihu.Article(md2zhihu.ParserConfig(True, []), conf, "![](x.png)\n")

    first = article.render()
    second = article.render()
    chunks = list(article.chunks())

    want = "![](P/a/bff139fa05ac583f-x.png)"
    assert first[0] == want
    assert second[0] == want
    assert chunks[0] == ("content", "paragraph", want + "\n")


def test_query_and_fragment(tmp_path, monkeypatch):
    md = "![](x.png?v=1#f) [p](p.pdf#page=2)\n"

    got = convert(tmp_path, monkeypatch, md, [])
    # The copy keeps the query and the fragment of a local image, and the fragment of a linked file.
    assert first_line(got) == "![](" + x_png + "?v=1#f) [p](a/p.pdf#page=2)"

    # A rule sees the query and the fragment, and can change them.
    got = convert(tmp_path, monkeypatch, md, ["--rewrite", r"\?v=1", "?v=2", "--rewrite", "#.*$", ""])
    assert first_line(got) == "![](" + x_png + "?v=2) [p](a/p.pdf)"


def test_rendered_image(tmp_path, monkeypatch):
    def convert_mermaid(input_typ, content, output_typ, opt=None):
        return b"jpg"

    monkeypatch.setattr(k3down2, "convert", convert_mermaid)

    got = convert(tmp_path, monkeypatch, "```mermaid\ngraph LR\n```\n", ["--rewrite-if", "^a/", "^", cdn], "zhihu")

    # The image that md2zhihu renders gets a rewritten URL too.
    assert first_line(got).startswith("![](" + cdn + "a/")


def test_table_image_reads_local_paths(tmp_path, monkeypatch):
    converted = []

    def convert_table(input_typ, content, output_typ, opt=None):
        converted.append(content)
        return b"jpg"

    monkeypatch.setattr(k3down2, "convert", convert_table)
    md = "| a |\n| - |\n| ![](x.png) |\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite", "^", cdn], "simple")

    # The browser that renders the table loads the image from its path, and the output refers to the table image by the
    # rewritten URL.
    assert "![](x.png)" in converted[0]
    assert cdn not in converted[0]
    assert first_line(got).startswith("![](" + cdn + "a/")


def test_table_html(tmp_path, monkeypatch):
    def convert_table(input_typ, content, output_typ, opt=None):
        # pandoc would make HTML of the markdown, with the same URLs.
        return content

    monkeypatch.setattr(k3down2, "convert", convert_table)
    md = "| a | b |\n| - | - |\n| ![](x.png) | [r][r] |\n\n[r]: p.pdf\n"

    got = convert(tmp_path, monkeypatch, md, ["--rewrite", "^", "P/"], "zhihu")

    # The images, links and definitions of a table that becomes HTML are changed once, as those outside of it are.
    assert "![](P/" + x_png + ")" in got
    assert "[r](P/a/p.pdf)" in got
    assert "P/P/" not in got


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


def test_download(tmp_path, monkeypatch, www):
    folder, base_url = www
    (folder / "r.png").write_bytes(b"png")
    url = base_url + "/r.png#v"

    got = convert(tmp_path, monkeypatch, "![](" + url + ")\n", ["--download", "--rewrite-if", "^a/", "^", cdn])

    # The selector sees the URL of the downloaded copy, not the URL that it was downloaded from.
    url_md5 = hashlib.md5(url.encode()).hexdigest()[:16]
    assert first_line(got) == "![](" + cdn + "a/" + url_md5 + "-r.png#v)"


# Rules and URLs, as (rules, url, the result).
rule_cases = [
    ([], "a", "a"),
    ([RewriteRule("a", "b")], "aa", "bb"),
    ([RewriteRule("^", "p/", selector="x")], "x", "p/x"),
    ([RewriteRule("^", "p/", selector="x")], "y", "y"),
    ([RewriteRule("^", "p/", selector="x", negate=True)], "x", "x"),
    ([RewriteRule("^", "p/", selector="x", negate=True)], "y", "p/y"),
    # A pair of strings is an unconditional rule, as the --rewrite flags of earlier versions give.
    ([["a", "b"], RewriteRule("^b", "c", selector="^b")], "a", "c"),
]


@pytest.mark.parametrize("rules, url, want", rule_cases)
def test_rewrite_url(rules, url, want):
    assert rewrite_url(rules, url) == want
