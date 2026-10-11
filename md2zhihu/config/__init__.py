"""Configuration classes for md2zhihu"""

import os
import re
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional
from typing import Union

from k3handy import pjoin

from ..platform import platform_feature_dict
from .asset_repo import AssetRepo
from .local_repo import LocalRepo

# The width of the image of a code block with a language, such as ```python, and of one without, such as an ASCII diagram.
default_code_width = 600
default_plain_code_width = 1000


@dataclass(frozen=True)
class Options:
    """
    The options of one md2zhihu run, which every input shares.
    `Config.from_options()` derives the paths of one input from them.
    """

    platform: str

    # The folder of the output, which asset_repo pushes.
    output_dir: str

    # Each input stores its images in a folder named after the input, in this folder.
    asset_output_dir: str

    # The path of the result markdown, or of its folder if it ends with "/".
    # ``{title}`` in it is replaced with the article name.
    md_output: str

    # The repo that output_dir is pushed to. Without it, the markdown refers to each image by its relative path.
    asset_repo: Optional[AssetRepo] = None

    # None stands for the default width, which Config fills in.
    code_width: Optional[int] = None
    plain_code_width: Optional[int] = None

    keep_meta: bool = False
    ref_files: List[str] = field(default_factory=list)
    jekyll: bool = False
    rewrite: List[List[str]] = field(default_factory=list)
    download: bool = False


class Config(object):
    #  TODO refactor var names
    def __init__(
        self,
        src_path,
        platform,
        output_dir,
        asset_output_dir,
        asset_repo=None,
        md_output_path=None,
        code_width=None,
        keep_meta=None,
        ref_files=None,
        jekyll=False,
        rewrite=None,
        download=False,
        plain_code_width=None,
    ):
        """
        Config of markdown rendering

        This form builds the `Options` from the arguments below, for the callers that predate `Options`.
        `Config.from_options()` takes the options of a run.

        Args:
            src_path(str): path to markdown to convert.

            platform(str): target platform the converted markdown compatible with.

            output_dir(str): the output dir path to which converted/generated file saves.

            asset_repo(AssetRepo): git repo to upload output files, i.e.
                    result markdown, moved image or generated images.

            md_output_path(str): when present, specifies the path of the result markdown or result dir.
                    ``{title}`` in it is replaced with the article name.

            code_width(int): the width of the image of each code block.
                    Default: 600 for a block with a language, and 1000 for a block without one.

            plain_code_width(int): the width of the image of a code block without a language,
                    such as an ASCII diagram. Default: code_width if given, else 1000.

            keep_meta(bool): whether to keep the jekyll meta file header.

        """

        if keep_meta is None:
            keep_meta = False

        if ref_files is None:
            ref_files = []

        if rewrite is None:
            rewrite = []

        assert md_output_path is not None

        options = Options(
            platform=platform,
            output_dir=output_dir,
            asset_output_dir=asset_output_dir,
            md_output=md_output_path,
            asset_repo=asset_repo,
            code_width=code_width,
            plain_code_width=plain_code_width,
            keep_meta=keep_meta,
            ref_files=ref_files,
            jekyll=jekyll,
            rewrite=rewrite,
            download=download,
        )
        self._set_input(src_path, options)

    @classmethod
    def from_options(cls, src_path: str, options: Options) -> "Config":
        """Build the config of the input `src_path`, in a run with `options`."""
        conf = cls.__new__(cls)
        conf._set_input(src_path, options)
        return conf

    def _set_input(self, src_path: str, options: Options) -> None:
        """Keep `options`, and derive from them the paths of the input `src_path`."""
        self.options = options
        self.features: dict = platform_feature_dict.get(options.platform, dict())
        self.src_path = src_path

        # A width given for every code block also applies to a block without a language.
        plain_code_width = options.plain_code_width
        if plain_code_width is None:
            plain_code_width = options.code_width
        if plain_code_width is None:
            plain_code_width = default_plain_code_width
        self.plain_code_width = plain_code_width

        code_width = options.code_width
        if code_width is None:
            code_width = default_code_width
        self.code_width = code_width

        fn = os.path.split(self.src_path)[-1]

        dated = re.match(r"\d\d\d\d-\d\d-\d\d-(.*)", fn)
        if dated:
            trim_fn = dated.groups()[0]
        else:
            trim_fn = fn

        if not options.jekyll:
            fn = trim_fn

        self.article_name = trim_fn.rsplit(".", 1)[0]

        self.asset_output_dir = pjoin(options.asset_output_dir, self.article_name)

        self.md_output_path = options.md_output.format(title=self.article_name)

        if self.md_output_path.endswith("/"):
            self.md_output_base = self.md_output_path
            self.md_output_path = pjoin(self.md_output_path, fn)
        else:
            self.md_output_base = os.path.split(os.path.abspath(self.md_output_path))[0]

        self.asset_repo: Union[LocalRepo, AssetRepo]
        if options.asset_repo is None:
            # The URL of an asset is its path from the markdown, so that it does not depend on output_dir.
            self.asset_repo = LocalRepo(self.md_output_path, self.asset_output_dir)
            self.rel_dir = ""
        else:
            # The repo holds output_dir, so the URL of an asset has the path of the asset in output_dir.
            self.asset_repo = options.asset_repo
            self.rel_dir = os.path.relpath(self.asset_output_dir, options.output_dir)

    def img_url(self, fn):
        url = self.asset_repo.path_pattern.format(path=pjoin(self.rel_dir, fn))

        for pattern, repl in self.options.rewrite:
            url = re.sub(pattern, repl, url)

        return url

    def relpath_from_cwd(self, p):
        """
        If ``p`` starts with "/", it is path starts from CWD.
        Otherwise, it is relative to the md src path.

        :return the path that can be used to read or write.
        """

        if p.startswith("/"):
            # absolute path from CWD.
            p = p[1:]
        else:
            # relative path from markdown containing dir.
            p = os.path.join(os.path.split(self.src_path)[0], p)
            abs_path = os.path.abspath(p)
            p = os.path.relpath(abs_path, start=os.getcwd())

        return p
