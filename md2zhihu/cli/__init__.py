import argparse
import logging
import os
import re
import sys
from typing import Dict
from typing import List
from typing import Optional

from k3fs import fread

from ..config import Config
from ..config import Options
from ..config.rewrite import RewriteRule
from ..errors import UserError
from ..parser import Article
from ..parser import ParserConfig
from ..utils import debug
from ..utils import msg
from .args import create_parser
from .args import removed_push

# The parent logger of every md2zhihu module. The md2zhihu command prints what it logs.
# Other libraries log through other loggers, such as k3handy, whose messages md2zhihu does not print.
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


def convert_md(parser_config, conf, linked_files: Optional[Dict[str, str]] = None):
    """`linked_files` is the `MDRender.linked_files` of the run, which the articles of a run share."""
    os.makedirs(conf.asset_output_dir, exist_ok=True)
    os.makedirs(conf.md_output_base, exist_ok=True)

    md_text = fread(conf.src_path)

    article = Article(parser_config, conf, md_text, linked_files=linked_files)

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
    except (KeyError, IndexError, ValueError, AttributeError):
        # AttributeError is an attribute on the placeholder, such as {title.foo}.
        rule = "the only placeholder is {title}, and a brace in a name must be doubled, as {{ or }}"
        parser.error(f"-o {md_output}: {rule}")


def check_embed_patterns(parser: argparse.ArgumentParser, patterns: List[str]) -> None:
    """Exit with a usage error if an --embed pattern is not a regex."""
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            parser.error(f"--embed {pattern}: {e}")


def check_removed_flags(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Exit with a usage error if a flag of the push that md2zhihu no longer does is given, such as --repo."""
    removed = [("--repo", args.repo), ("--branch", args.branch)]
    for flag, value in removed:
        if value is not None:
            parser.error(f"{flag}: {removed_push}")


def check_rewrite_rules(parser: argparse.ArgumentParser, rules: List[RewriteRule]) -> None:
    """Exit with a usage error if a rewrite rule has a selector or a regex that is not a regex, or a bad replacement."""
    for rule in rules:
        if rule.selector is None:
            given = f"--rewrite {rule.pattern} {rule.repl}"
        else:
            flag = "--rewrite-if-not" if rule.negate else "--rewrite-if"
            given = f"{flag} {rule.selector} {rule.pattern} {rule.repl}"

        try:
            if rule.selector is not None:
                re.compile(rule.selector)
            # re reads the replacement before it searches, so a replacement that refers to a group that the regex
            # does not have, such as \2 of a regex with one group, fails also on an empty string.
            re.compile(rule.pattern).sub(rule.repl, "")
        except re.error as e:
            parser.error(f"{given}: {e}")
        except IndexError as e:
            # re raises IndexError for an unknown group name, such as \g<x>.
            parser.error(f"{given}: {e.args[0]}")


def file_identity(path: str) -> tuple:
    """
    Return a key that two paths of one file share: the device and inode of an existing file, which its links share,
    or else the path with symlinks and ".." resolved.
    """
    if not os.path.exists(path):
        return (os.path.realpath(path),)
    st = os.stat(path)
    return (st.st_dev, st.st_ino)


def check_md_outputs(parser: argparse.ArgumentParser, confs: List[Config]) -> None:
    """
    Exit with a usage error if an input converts to an existing folder, to another input,
    or to the same markdown file as another input does.
    md2zhihu writes an output before it reads the next input, so such an output would replace an input or an output.
    """
    src_by_file = {file_identity(conf.src_path): conf.src_path for conf in confs}
    conf_by_output: Dict[tuple, Config] = {}
    for conf in confs:
        output = conf.md_output_path
        if os.path.isdir(output):
            rule = '-o PATH is a folder only when it ends with "/"'
            parser.error(f"{conf.src_path} converts to {output}, which is a folder; {rule}")

        output_file = file_identity(output)
        src = src_by_file.get(output_file)
        # An input may convert to itself: md2zhihu reads it before it writes the output.
        is_other_input = src is not None and output_file != file_identity(conf.src_path)
        if is_other_input:
            parser.error(f"{conf.src_path} converts to {output}, which is the input {src}")

        other = conf_by_output.get(output_file)
        if other is not None:
            if other.md_output_path == output:
                parser.error(f"{other.src_path} and {conf.src_path} both convert to {output}")
            parser.error(
                f"{other.src_path} converts to {other.md_output_path} and {conf.src_path} converts to {output},"
                " which is the same file"
            )
        conf_by_output[output_file] = conf


def main():
    """
    Run the md2zhihu command.
    A failure that the user can fix ends with a one-line message on stderr and exit status 1.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(MessageFormatter(use_color(sys.stderr)))
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        run()
    except UserError as e:
        logger.error("%s", e)
        sys.exit(1)
    finally:
        # The next call, such as in a test, adds its own handler, and with this one each message would print twice.
        logger.removeHandler(handler)
        logger.setLevel(level)


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
    check_embed_patterns(parser, args.embed)
    check_removed_flags(parser, args)

    # A repeated flag that is not given, such as --refs, is None.
    ref_files = args.refs or []
    rewrite: List[RewriteRule] = args.rewrite or []
    check_rewrite_rules(parser, rewrite)

    debug("--platform: ", args.platform)
    debug("--output-dir: ", args.output_dir)
    debug("--md-output: ", args.md_output)
    debug("--asset-output-dir: ", args.asset_output_dir)

    options = Options(
        platform=args.platform,
        output_dir=args.output_dir,
        asset_output_dir=args.asset_output_dir,
        md_output=args.md_output,
        code_width=args.code_width,
        plain_code_width=args.plain_code_width,
        keep_meta=args.keep_front_matter,
        ref_files=ref_files,
        jekyll=args.jekyll,
        rewrite=rewrite,
        download=args.download,
    )

    confs = []
    for path in args.src_path:
        conf = Config.from_options(path, options)
        confs.append(conf)

    check_md_outputs(parser, confs)

    parser_config = ParserConfig(True, args.embed)

    # With --jekyll, posts of one name and two dates share an asset folder,
    # so the run keeps every copy of a linked file, and one copy can not replace another.
    linked_files: Dict[str, str] = {}
    for conf in confs:
        convert_md(parser_config, conf, linked_files)

        msg(conf.src_path, " -> ", conf.md_output_path)
