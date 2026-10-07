import argparse


class SmartFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith("R|"):
            return text[2:].splitlines() + [""]
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width) + [""]


def create_parser() -> argparse.ArgumentParser:
    """Build the argument parser of the md2zhihu command."""
    parser = argparse.ArgumentParser(
        # Python 3.14 derives the default name from a "python -m" run, such as "python -m pytest".
        prog="md2zhihu",
        description="Convert markdown to zhihu compatible",
        formatter_class=SmartFormatter,
    )

    parser.add_argument("src_path", type=str, nargs="+", help="path to the markdowns to convert")

    parser.add_argument(
        "-d",
        "--output-dir",
        action="store",
        default="_md2",
        help="R|Sepcify dir path to store the outputs."
        "\n"
        "It is the root dir of the git repo to store the assets referenced by output markdowns."
        "\n"
        'Deafult: "_md2"',
    )

    parser.add_argument(
        "-o",
        "--md-output",
        action="store",
        help="R|Sepcify output path for converted mds."
        "\n"
        'If the path specified ends with "/", it is treated as output dir,'
        ' e.g., "--md-output foo/" output the converted md to foo/<fn>.md.'
        "\n"
        '"{title}" in the path is replaced with the md file name without date prefix and extension,'
        ' e.g., "--md-output foo/{title}/index.md".'
        "\n"
        "Default: <output-dir>/<fn>.md",
    )

    parser.add_argument(
        "--asset-output-dir",
        action="store",
        help="R|Sepcify dir to store assets"
        "\n"
        "If <asset-output-dir> is outside <output-dir>, nothing will be uploaded."
        "\n"
        "Default: <output-dir>",
    )

    parser.add_argument(
        "-r",
        "--repo",
        action="store",
        required=False,
        help="R|Sepcify the git url to store assets."
        "\n"
        "The url should be in a SSH form such as:"
        "\n"
        '    "git@github.com:openacid/openacid.github.io.git[@branch_name]".'
        "\n"
        "\n"
        "The repo has to be a public repo and you have the write access."
        "\n"
        "\n"
        "When absent, it works in local mode:"
        " assets are referenced by relative path and will not be pushed to remote."
        "\n"
        "\n"
        'If no branch is specified, a branch "_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}" is used,'
        " in which cwd_tail is the last segment of current working dir."
        "\n"
        "\n"
        '"--repo ." to use the git that is found in CWD',
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
        help="R|Convert to a platform compatible format."
        "\n"
        '"simple" is a special type that it produce simplest output, only plain text and images, there wont be table, code block, math etc.'
        "\n"
        'Default: "zhihu"',
    )

    parser.add_argument(
        "--keep-meta",
        action="store_true",
        required=False,
        default=False,
        help='If to keep meta header or not, the header is wrapped with two "---" at file beginning.',
    )

    parser.add_argument(
        "--jekyll",
        action="store_true",
        required=False,
        default=False,
        help="R|Respect jekyll syntax:"
        "\n"
        "1) It implies <keep-meta>: do not trim md header meta;"
        "\n"
        "2) It keep jekyll style file name with the date prefix: YYYY-MM-DD-TITLE.md.",
    )

    parser.add_argument(
        "--refs",
        action="append",
        required=False,
        help="R|Specify the external file that contains ref definitions."
        "\n"
        "A ref file is a yaml contains reference definitions in a dict of list."
        "\n"
        "A dict key is the platform name, only visible when it is enabeld by <platform> argument."
        "\n"
        '"universal" is visible in any <platform>.'
        "\n"
        "\n"
        "Example of ref file data:"
        "\n"
        '{ "universal": [{"grpc":"http:.."}, {"protobuf":"http:.."}],'
        "\n"
        '  "zhihu":     [{"grpc":"http:.."}, {"protobuf":"http:.."}]'
        "\n"
        "}."
        "\n"
        'With an external refs file being specified, in markdown one can just use the ref: e.g., "[grpc][]"',
    )

    parser.add_argument(
        "--rewrite",
        action="append",
        nargs=2,
        required=False,
        help="R|Rewrite generated image url."
        "\n"
        'E.g.: --rewrite "/asset/" "/resource/"'
        "\n"
        'will transform "/asset/banner.jpg" to "/resource/banner.jpg"'
        "\n"
        "Default: []",
    )

    parser.add_argument(
        "--download",
        action="store_true",
        required=False,
        default=False,
        help="R|Download remote image url if a image url starts with http[s]://.",
    )

    parser.add_argument(
        "--embed",
        action="store",
        nargs="+",
        required=False,
        default=[r"[.]md$"],
        help="R|Specifies regex of url in `![](url)` to embed."
        "\n"
        'Example: --embed "[.]md$" will replace ![](x.md) with the content of x.md'
        "\n"
        'Default: ["[.]md$"]',
    )

    parser.add_argument(
        "--code-width",
        action="store",
        type=int,
        required=False,
        default=1000,
        help="R|specifies code image width.\nDefault: 1000",
    )

    return parser
