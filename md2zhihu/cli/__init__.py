import argparse
import logging
import os
import subprocess
import sys
from typing import Dict
from typing import List
from typing import Optional

from k3fs import fread

from ..config import AssetRepo
from ..config import Config
from ..errors import UserError
from ..parser import Article
from ..parser import ParserConfig
from ..utils import debug
from ..utils import mask_url_credential
from ..utils import msg
from .args import create_parser

# The parent logger of every md2zhihu module. The md2zhihu command prints what it logs.
# Other libraries log through other loggers, such as k3handy, which logs each command with the token in a push URL.
logger = logging.getLogger("md2zhihu")

# The ANSI color of the "md2zhihu: warning:" or "md2zhihu: error:" prefix, by log level.
prefix_colors = {logging.WARNING: "\x1b[33m", logging.ERROR: "\x1b[31m"}
color_reset = "\x1b[0m"


class MessageFormatter(logging.Formatter):
    """
    Format a message as md2zhihu prints it: a warning or an error starts with "md2zhihu: warning:" or "md2zhihu: error:".
    With `color`, this prefix is colored.
    """

    def __init__(self, color: bool) -> None:
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if record.levelno < logging.WARNING:
            return message

        prefix = "md2zhihu: " + record.levelname.lower() + ":"
        if self.color:
            prefix = prefix_colors.get(record.levelno, "") + prefix + color_reset
        return prefix + " " + message


def use_color(stream) -> bool:
    """Tell whether to color the messages: only on a terminal, and not if NO_COLOR is set, as https://no-color.org asks."""
    no_color = os.environ.get("NO_COLOR", "") != ""
    return stream.isatty() and not no_color


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


def check_md_output(parser: argparse.ArgumentParser, md_output: str) -> None:
    """Exit with a usage error if the -o path has a placeholder that Config can not fill in."""
    try:
        md_output.format(title="x")
    except (KeyError, IndexError, ValueError):
        rule = "the only placeholder is {title}, and a brace in a name must be doubled, as {{ or }}"
        parser.error(f"-o {md_output}: {rule}")


def check_asset_output_dir(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Exit with a usage error if --repo would not push the images, because they are outside --output-dir."""
    if args.repo is None:
        return

    rel = os.path.relpath(args.asset_output_dir, args.output_dir)
    outside = rel == os.pardir or rel.startswith(os.pardir + os.sep)
    if outside:
        rule = f"is outside --output-dir {args.output_dir}, which is the only folder that --repo pushes"
        parser.error(f"--asset-output-dir {args.asset_output_dir}: {rule}")


def new_asset_repo(parser: argparse.ArgumentParser, url: Optional[str], branch: Optional[str]) -> Optional[AssetRepo]:
    """Build the repo that --repo and --branch name, or exit with a usage error if they are bad."""
    if url is None:
        if branch is not None:
            parser.error(f"--branch {branch}: is the branch that --repo pushes to, so it needs --repo")
        return None

    try:
        return AssetRepo(url, branch=branch)
    except ValueError as e:
        reason = str(e)
    except subprocess.CalledProcessError as e:
        # A shortcut such as "--repo ." runs git, which fails outside a git repo.
        reason = e.stderr.strip()

    given = f"--repo {url}"
    if branch is not None:
        given += f" --branch {branch}"
    parser.error(mask_url_credential(f"{given}: {reason}"))


def check_md_outputs(parser: argparse.ArgumentParser, confs: List[Config]) -> None:
    """Exit with a usage error if an input converts to an existing folder, or two inputs convert to the same markdown file."""
    src_by_output: Dict[str, str] = {}
    for conf in confs:
        output = conf.md_output_path
        if os.path.isdir(output):
            rule = '-o PATH is a folder only when it ends with "/"'
            parser.error(f"{conf.src_path} converts to {output}, which is a folder; {rule}")
        if output in src_by_output:
            parser.error(f"{src_by_output[output]} and {conf.src_path} both convert to {output}")
        src_by_output[output] = conf.src_path


def main():
    """
    Run the md2zhihu command.
    A failure that the user can fix ends with a one-line message on stderr and exit status 1.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(MessageFormatter(use_color(sys.stderr)))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        run()
    except UserError as e:
        logger.error("%s", e)
        sys.exit(1)


def run():
    # TODO then test drmingdrmer.github.io with action

    parser = create_parser()

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.md_output is None:
        args.md_output = args.output_dir + "/"

    if args.asset_output_dir is None:
        args.asset_output_dir = args.output_dir

    # With action="append", a default list would be extended, not replaced, by the --embed flags.
    if args.embed is None:
        args.embed = [r"[.]md$"]

    if args.jekyll:
        args.keep_front_matter = True

    check_src_paths(parser, args.src_path)
    check_md_output(parser, args.md_output)
    check_asset_output_dir(parser, args)
    asset_repo = new_asset_repo(parser, args.repo, args.branch)

    debug("--platform: ", args.platform)
    debug("--output-dir: ", args.output_dir)
    debug("--md-output: ", args.md_output)
    debug("--asset-output-dir: ", args.asset_output_dir)
    if asset_repo is not None:
        debug("--repo: ", asset_repo.url, ", branch ", asset_repo.branch)

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
            plain_code_width=args.plain_code_width,
            keep_meta=args.keep_front_matter,
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

        msg(conf.src_path, " -> ", conf.md_output_path)

        stat.append([conf.src_path, conf.md_output_path])

    if conf.asset_repo.is_local:
        msg("no --repo, so images are referenced by relative path")
    else:
        conf.push(args, stat)
        msg(
            "pushed ",
            conf.output_dir,
            " to ",
            conf.asset_repo.url,
            ", branch ",
            conf.asset_repo.branch,
        )
