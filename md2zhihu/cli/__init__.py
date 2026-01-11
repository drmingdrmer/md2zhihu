import argparse
import logging
import os
import sys

from k3color import darkred
from k3color import darkyellow
from k3color import green
from k3fs import fread

from ..config import Config
from ..parser import Article
from ..parser import ParserConfig
from ..utils import msg
from ..utils import sj


def convert_md(parser_config, conf):
    os.makedirs(conf.output_dir, exist_ok=True)
    os.makedirs(conf.asset_output_dir, exist_ok=True)
    os.makedirs(conf.md_output_base, exist_ok=True)

    md_text = fread(conf.src_path)

    article = Article(parser_config, conf, md_text)

    output_lines = article.render()

    with open(conf.md_output_path, "w") as f:
        f.write(str("\n".join(output_lines)))

    return conf.md_output_path


class SmartFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith("R|"):
            return text[2:].splitlines() + [""]
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width) + [""]


def main():
    # Configure logging to output to stdout (same as original print())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("> %(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)

    # TODO refine arg names
    # md2zhihu a.md --output-dir res/ --platform xxx --md-output foo/
    # res/fn.md
    #    /assets/fn/xx.jpg
    #
    # md2zhihu a.md --output-dir res/ --repo a@branch --platform xxx --md-output b.md
    #
    # TODO then test drmingdrmer.github.io with action

    parser = argparse.ArgumentParser(
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
        required=False,
        default=1000,
        help="R|specifies code image width.\nDefault: 1000",
    )

    args = parser.parse_args()

    if args.md_output is None:
        args.md_output = args.output_dir + "/"

    if args.asset_output_dir is None:
        args.asset_output_dir = args.output_dir

    if args.jekyll:
        args.keep_meta = True

    msg(
        "Build markdown: ",
        darkyellow(args.src_path),
        " into ",
        darkyellow(args.md_output),
    )
    msg("Build assets to: ", darkyellow(args.asset_output_dir))
    msg("Git dir: ", darkyellow(args.output_dir))
    msg("Gid dir will be pushed to: ", darkyellow(args.repo))

    stat = []
    for path in args.src_path:
        #  TODO Config should accept only two arguments: the path and a args
        conf = Config(
            path,
            args.platform,
            args.output_dir,
            args.asset_output_dir,
            asset_repo_url=args.repo,
            md_output_path=args.md_output,
            code_width=args.code_width,
            keep_meta=args.keep_meta,
            ref_files=args.refs,
            jekyll=args.jekyll,
            rewrite=args.rewrite,
            download=args.download,
        )

        parser_config = ParserConfig(True, args.embed)

        # Check if file exists
        try:
            fread(conf.src_path)
        except FileNotFoundError:
            msg(darkred(sj("Warn: file not found: ", repr(conf.src_path))))
            continue

        convert_md(parser_config, conf)

        msg(sj("Done building ", darkyellow(conf.md_output_path)))

        stat.append([path, conf.md_output_path])

    if conf.asset_repo.is_local:
        msg("No git repo specified")
    else:
        msg(
            "Pushing ",
            darkyellow(conf.output_dir),
            " to ",
            darkyellow(conf.asset_repo.url),
            " branch: ",
            darkyellow(conf.asset_repo.branch),
        )
        conf.push(args, stat)

    msg(green(sj("Great job!!!")))
