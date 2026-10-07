import argparse
import logging
import os
import subprocess
import sys
from typing import Dict
from typing import List
from typing import Optional

from k3color import darkyellow
from k3color import green
from k3fs import fread

from ..config import AssetRepo
from ..config import Config
from ..parser import Article
from ..parser import ParserConfig
from ..utils import mask_url_credential
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


def check_src_paths(parser: argparse.ArgumentParser, paths: List[str]) -> None:
    """Exit with a usage error if a path is not a file."""
    for path in paths:
        if os.path.isdir(path):
            example = os.path.join(path, "*.md")
            parser.error(f"{path}: is a directory, pass the markdown files in it, such as {example}")
        if not os.path.isfile(path):
            parser.error(f"{path}: no such file")


def new_asset_repo(parser: argparse.ArgumentParser, url: Optional[str]) -> Optional[AssetRepo]:
    """Build the repo that --repo names, or exit with a usage error if it is bad."""
    if url is None:
        return None

    try:
        return AssetRepo(url)
    except ValueError as e:
        reason = str(e)
    except subprocess.CalledProcessError as e:
        # A shortcut such as "--repo ." runs git, which fails outside a git repo.
        reason = e.stderr.strip()
    parser.error(mask_url_credential(f"--repo {url}: {reason}"))


def check_md_outputs(parser: argparse.ArgumentParser, confs: List[Config]) -> None:
    """Exit with a usage error if two inputs convert to the same markdown file."""
    src_by_output: Dict[str, str] = {}
    for conf in confs:
        output = conf.md_output_path
        if output in src_by_output:
            parser.error(f"{src_by_output[output]} and {conf.src_path} both convert to {output}")
        src_by_output[output] = conf.src_path


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

    check_src_paths(parser, args.src_path)
    asset_repo = new_asset_repo(parser, args.repo)

    msg(
        "Build markdown: ",
        darkyellow(args.src_path),
        " into ",
        darkyellow(args.md_output),
    )
    msg("Build assets to: ", darkyellow(args.asset_output_dir))
    msg("Git dir: ", darkyellow(args.output_dir))
    msg("Gid dir will be pushed to: ", darkyellow(args.repo))

    confs = []
    for path in args.src_path:
        #  TODO Config should accept only two arguments: the path and a args
        conf = Config(
            path,
            args.platform,
            args.output_dir,
            args.asset_output_dir,
            asset_repo=asset_repo,
            md_output_path=args.md_output,
            code_width=args.code_width,
            keep_meta=args.keep_meta,
            ref_files=args.refs,
            jekyll=args.jekyll,
            rewrite=args.rewrite,
            download=args.download,
        )
        confs.append(conf)

    check_md_outputs(parser, confs)

    parser_config = ParserConfig(True, args.embed)

    stat = []
    for conf in confs:
        convert_md(parser_config, conf)

        msg(sj("Done building ", darkyellow(conf.md_output_path)))

        stat.append([conf.src_path, conf.md_output_path])

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
