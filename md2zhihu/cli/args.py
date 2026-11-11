import argparse
import importlib.metadata

from ..config import default_code_width
from ..config import default_plain_code_width
from ..config.rewrite import RewriteRule

epilog = """\
platforms:
  zhihu            math to zhihu equation images, tables to HTML, mermaid and
                   graphviz to images
  wechat           as zhihu, and code blocks to images too
  weibo            math blocks to equation images, inline math to text, tables
                   and code blocks to images
  github           math stays math, which GitHub shows; graphviz to images
  minimal_mistake  mermaid and graphviz to images, for the Jekyll theme
                   Minimal Mistakes
  hugo             as minimal_mistake, and each formula on one line, as block
                   math \\[...\\] if alone in its paragraph, else as inline math
                   $$...$$, for the passthrough extension of Hugo
  simple           math, tables and code blocks to images, and inline code to
                   plain text
  transparent      copy local images and linked files, and change nothing else

examples:
  md2zhihu a.md                     convert to _md2/a.md, with images in _md2/a/
                                    and the URL a/<image> in _md2/a.md
  md2zhihu a.md --rewrite-if '^a/' '^' 'https://cdn.example/_md2/'
                                    refer to each image by its URL after you
                                    publish _md2 at https://cdn.example/_md2/,
                                    such as https://cdn.example/_md2/a/<image>
  md2zhihu _drafts/*.md --jekyll -o _posts/
                                    keep the front matter and the date prefix

output layout, with the defaults:
  _md2/        -d, --output-dir: the folder of the output
    a.md       -o, --md-output: <output-dir>/<name>.md
    a/         --asset-output-dir: <asset-output-dir>/<name>/ holds the images
               and the linked files

rewrite rules:
  --rewrite, --rewrite-if and --rewrite-if-not change the destination of each
  link and image of the output, such as the URL of a stored image, of a remote
  image, or of a link to another page, but no other text. The rules apply in
  the order of the command line, each to the URL that the rule before it made,
  after md2zhihu has stored the images and the linked files. A rule sees the
  whole URL, with its query and fragment.
"""

# The usage error of the removed flags --repo and --branch, which tells how to publish the output instead.
removed_push = (
    "is removed: md2zhihu writes the output to --output-dir and pushes nothing;"
    " publish the folder yourself, such as with git push, and use --rewrite-if to refer to the images by the URL"
    " that they get there, or keep md2zhihu 0.22 for the push"
)


class AppendRule(argparse.Action):
    """
    Append a RewriteRule to the one list that --rewrite, --rewrite-if and --rewrite-if-not share,
    so that the rules keep the order of the command line.
    `const` is None for --rewrite, which has no selector, and else whether the rule applies to the URLs
    that the selector does not match.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        rules = getattr(namespace, self.dest, None) or []
        if self.const is None:
            pattern, repl = values
            rule = RewriteRule(pattern, repl)
        else:
            selector, pattern, repl = values
            rule = RewriteRule(pattern, repl, selector=selector, negate=self.const)
        setattr(namespace, self.dest, rules + [rule])


class SmartFormatter(argparse.RawDescriptionHelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith("R|"):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)


def create_parser() -> argparse.ArgumentParser:
    """Build the argument parser of the md2zhihu command."""
    parser = argparse.ArgumentParser(
        # Python 3.14 derives the default name from a "python -m" run, such as "python -m pytest".
        prog="md2zhihu",
        description="Convert markdown into one file that zhihu.com and other platforms can import,\n"
        "and write it with its images into a local folder.",
        epilog=epilog,
        formatter_class=SmartFormatter,
    )

    parser.add_argument("src_path", type=str, nargs="+", metavar="MARKDOWN", help="the markdown files to convert")

    where_to_write = parser.add_argument_group("where to write")

    where_to_write.add_argument(
        "-d",
        "--output-dir",
        action="store",
        default="_md2",
        metavar="DIR",
        help="The folder of the output. Default: %(default)s",
    )

    where_to_write.add_argument(
        "-o",
        "--md-output",
        action="store",
        metavar="PATH",
        help='Where to write each converted markdown. A PATH that ends with "/" is a folder,'
        " and the markdown gets the name of its input file."
        ' "{title}" in PATH is replaced with the name of the input file, without the date prefix and the extension,'
        ' such as -o "posts/{title}/index.md".'
        " Default: <output-dir>/",
    )

    where_to_write.add_argument(
        "--asset-output-dir",
        action="store",
        metavar="DIR",
        help="The folder of the images, and of the local files that links refer to, such as [a](paper.pdf)."
        " Those of a.md go into its subfolder a/."
        " Default: <output-dir>",
    )

    where_to_store = parser.add_argument_group("how to refer to the images")

    # The flags of the push that md2zhihu 0.22 and earlier did. run() rejects them, and --help does not show them.
    where_to_store.add_argument("-r", "--repo", action="store", metavar="URL", help=argparse.SUPPRESS)
    where_to_store.add_argument("-b", "--branch", action="store", metavar="NAME", help=argparse.SUPPRESS)

    where_to_store.add_argument(
        "--download",
        action="store_true",
        required=False,
        default=False,
        help="Also download each remote image, whose URL starts with http:// or https://, and store it as a local image.",
    )

    where_to_store.add_argument(
        "--rewrite",
        action=AppendRule,
        dest="rewrite",
        nargs=2,
        metavar=("REGEX", "REPLACEMENT"),
        help="Change the destination of each link and image with re.sub(REGEX, REPLACEMENT, url),"
        ' such as --rewrite "^/asset/" "/resource/". Repeat it to give more than one rule.'
        " It changes every destination, such as the URL of a remote image too;"
        " --rewrite-if and --rewrite-if-not choose the destinations to change.",
    )

    where_to_store.add_argument(
        "--rewrite-if",
        action=AppendRule,
        dest="rewrite",
        const=False,
        nargs=3,
        metavar=("SELECTOR", "REGEX", "REPLACEMENT"),
        help="As --rewrite, but only for a destination in which re.search(SELECTOR, url) finds a match,"
        " such as --rewrite-if '^a/' '^' 'https://cdn.example/' for the stored images of a.md."
        " A match of SELECTOR alone does not change the destination.",
    )

    where_to_store.add_argument(
        "--rewrite-if-not",
        action=AppendRule,
        dest="rewrite",
        const=True,
        nargs=3,
        metavar=("SELECTOR", "REGEX", "REPLACEMENT"),
        help="As --rewrite, but only for a destination in which re.search(SELECTOR, url) finds no match,"
        " such as --rewrite-if-not '^([A-Za-z][A-Za-z0-9+.-]*:|//|/|[?#]|$)' '^' 'https://cdn.example/'"
        " for every relative destination: a stored image, and also a link such as ../b.md.",
    )

    what_to_convert = parser.add_argument_group("what to convert")

    what_to_convert.add_argument(
        "-p",
        "--platform",
        action="store",
        required=False,
        default="zhihu",
        choices=[
            "zhihu",
            "github",
            "wechat",
            "weibo",
            "simple",
            "minimal_mistake",
            "hugo",
            "transparent",
        ],
        metavar="PLATFORM",
        help='The platform to convert for, one of the "platforms" below. Default: %(default)s',
    )

    what_to_convert.add_argument(
        "--keep-front-matter",
        "--keep-meta",
        action="store_true",
        required=False,
        default=False,
        help='Keep the front matter, the YAML block between two "---" lines at the start of the markdown.'
        " The old name --keep-meta still works, but is deprecated.",
    )

    what_to_convert.add_argument(
        "--jekyll",
        action="store_true",
        required=False,
        default=False,
        help="Same as --keep-front-matter, and also keep the date prefix of the file name,"
        " such as 2021-06-11-title.md, as Jekyll needs.",
    )

    what_to_convert.add_argument(
        "--embed",
        action="append",
        required=False,
        metavar="REGEX",
        help='Replace an image "![](url)" whose url matches REGEX with the content of the local markdown file at url.'
        ' Repeat it to give more than one regex. Default: "[.]md$".'
        ' Giving --embed replaces this default, so add --embed "[.]md$" to keep it.',
    )

    what_to_convert.add_argument(
        "--refs",
        action="append",
        required=False,
        metavar="YAML",
        help="R|A YAML file of reference definitions, which the"
        "\n"
        'markdown can use, such as "[grpc][]". Its "universal"'
        "\n"
        "list applies to every platform, and a list named"
        "\n"
        "after a platform applies to that platform only."
        "\n"
        "Repeat it to give more than one file. Such as:"
        "\n"
        "  universal:"
        "\n"
        "    - grpc: https://grpc.io"
        "\n"
        "  zhihu:"
        "\n"
        "    - grpc: https://zhuanlan.zhihu.com/p/123",
    )

    what_to_convert.add_argument(
        "--code-width",
        action="store",
        type=int,
        required=False,
        metavar="PIXELS",
        help="The width of each code block image. Only wechat, weibo and simple turn code blocks into images."
        f" Default: {default_code_width} for a code block with a language, such as ```python,"
        f" and {default_plain_code_width} for one without.",
    )

    what_to_convert.add_argument(
        "--plain-code-width",
        action="store",
        type=int,
        required=False,
        metavar="PIXELS",
        help="The width of the image of a code block without a language, such as an ASCII diagram."
        f" Default: --code-width if given, else {default_plain_code_width}.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also print the settings in effect.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + importlib.metadata.version("md2zhihu"),
    )

    return parser
