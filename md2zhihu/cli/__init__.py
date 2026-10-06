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
from .args import create_parser


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

    parser = create_parser()

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
