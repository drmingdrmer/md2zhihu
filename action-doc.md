-   `pattern`:

    file pattern to convert

    **required**: True
    **default**: `**/*.md`

-   `output_dir`:

    dir to store converted markdown.

    **required**: True
    **default**: `_md2zhihu`

-   `asset_branch`:

    The branch in which assets are stored. This branch must NOT be removed otherwise the assets will not be accessed.

    **required**: True
    **default**: `<branch-name>-md2zhihu-asset`

-   `target_platform`:

    The platform that the converted markdown should be compatible to.
    Currently supported platforms are zhihu, wechat, weibo, simple. `simple` converts almost everything to images and removes most text styles. E.g. inline code block is converted to normal text.

    **required**: True
    **default**: `zhihu`

