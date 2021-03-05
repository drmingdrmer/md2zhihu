-   `pattern`:

    file pattern to convert

    **required**: True
    **default**: `**/*.md`

-   `output_dir`:

    dir to store converted markdown

    **required**: True
    **default**: `_md2zhihu`

-   `md_branch`:

    The branch name to push converted markdown to. A build overrides previous built branch. If you want to persist the built markdowns, merge this branch.

    **required**: True
    **default**: `_md2zhihu/md`

-   `asset_branch`:

    The branch name in which assets are stored.

    **required**: True
    **default**: `_md2zhihu/asset`

-   `target_platform`:

    The platform that the converted markdown should be compatible to.
Currently supported platforms are zhihu, wechat, weibo, simple. `simple` converts almost everything to images and removes most text styles. E.g. inline code block is converted to normal text.

    **required**: True
    **default**: `zhihu`

