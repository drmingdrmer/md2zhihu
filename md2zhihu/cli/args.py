import argparse
import importlib.metadata

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
  simple           math, tables and code blocks to images, and inline code to
                   plain text
  transparent      copy local images and change nothing else

examples:
  md2zhihu a.md                     convert to _md2/a.md, with images in _md2/a/
  md2zhihu a.md -r .                also push _md2 to the remote of the git repo
                                    in the working directory
  md2zhihu _drafts/*.md --jekyll -o _posts/
                                    keep the front matter and the date prefix

output layout, with the defaults:
  _md2/        -d, --output-dir: the folder that --repo pushes
    a.md       -o, --md-output: <output-dir>/<name>.md
    a/         --asset-output-dir: <asset-output-dir>/<name>/ holds the images
"""


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
        "and store its images in a git repo.",
        epilog=epilog,
        formatter_class=SmartFormatter,
    )

    parser.add_argument("src_path", type=str, nargs="+", metavar="MARKDOWN", help="the markdown files to convert")

    parser.add_argument(
        "-d",
        "--output-dir",
        action="store",
        default="_md2",
        metavar="DIR",
        help="The folder of the output, which --repo pushes. Default: %(default)s",
    )

    parser.add_argument(
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

    parser.add_argument(
        "--asset-output-dir",
        action="store",
        metavar="DIR",
        help="The folder of the images. The images of a.md go into its subfolder a/."
        " --repo pushes only the images inside <output-dir>."
        " Default: <output-dir>",
    )

    parser.add_argument(
        "-r",
        "--repo",
        action="store",
        required=False,
        metavar="URL",
        help="Push <output-dir> to this public git repo on github.com or gitee.com,"
        " and refer to each image by its URL in the repo, such as"
        ' "git@github.com:me/assets.git@branch".'
        " Each run force-pushes <output-dir> as a new commit, which replaces everything on the branch,"
        ' so use a branch for md2zhihu only. "main" and "master" are refused.'
        ' Without "@branch", the branch is "_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}",'
        " in which cwd_tail is the last part of the working directory."
        ' "." stands for the remote of the git repo in the working directory,'
        ' and a remote name, such as "origin@branch", for that remote.'
        " Without --repo, the markdown refers to its images by relative path.",
    )

    parser.add_argument(
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
            "transparent",
        ],
        metavar="PLATFORM",
        help='The platform to convert for, one of the "platforms" below. Default: %(default)s',
    )

    parser.add_argument(
        "--keep-meta",
        action="store_true",
        required=False,
        default=False,
        help='Keep the front matter, the meta block between two "---" lines at the start of the markdown.',
    )

    parser.add_argument(
        "--jekyll",
        action="store_true",
        required=False,
        default=False,
        help="Keep the front matter, and the date prefix of the file name, such as 2021-06-11-title.md, as Jekyll needs.",
    )

    parser.add_argument(
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

    parser.add_argument(
        "--rewrite",
        action="append",
        nargs=2,
        required=False,
        metavar=("REGEX", "REPLACEMENT"),
        help="Change the URL of each image that md2zhihu stores with re.sub(REGEX, REPLACEMENT, url),"
        ' such as --rewrite "^/asset/" "/resource/". Repeat it to give more than one rule.',
    )

    parser.add_argument(
        "--download",
        action="store_true",
        required=False,
        default=False,
        help="Also download each remote image, whose URL starts with http:// or https://, and store it as a local image.",
    )

    parser.add_argument(
        "--embed",
        action="append",
        required=False,
        metavar="REGEX",
        help='Replace an image "![](url)" whose url matches REGEX with the content of the markdown at url.'
        ' Repeat it to give more than one regex. Default: "[.]md$"',
    )

    parser.add_argument(
        "--code-width",
        action="store",
        type=int,
        required=False,
        default=1000,
        metavar="PIXELS",
        help="The width of a code block image. Default: %(default)s",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also print the settings in effect, such as the branch that --repo pushes to.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + importlib.metadata.version("md2zhihu"),
    )

    return parser
