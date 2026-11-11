-   `pattern`:

    file pattern to convert

    **required**: False
    **default**: `**/*.md`

-   `output_dir`:

    dir to store converted markdown.

    **required**: False
    **default**: `_md2zhihu`

-   `asset_url_prefix`:

    The public URL of `output_dir` once a later step of the workflow publishes it.
    md2zhihu puts it before each relative URL of the converted markdown, such as `post/<hash>-a.png` of an image of `post.md`,
    so that a platform such as zhihu.com loads the image from there.
    The action pushes nothing, so the URL works only after the workflow publishes `output_dir` at that place.

    The default is the URL that jsDelivr serves `_md2zhihu/` at, on the branch `<branch>-md2zhihu` of this repo,
    which the example workflow in README.md pushes.
    Change it together with `output_dir`, or with the branch that the workflow pushes.

    A relative link to another file, such as `../other.md`, also gets the prefix.
    Set it to "" to keep every relative URL as it is.

    **required**: False
    **default**: `https://cdn.jsdelivr.net/gh/${{ github.repository }}@${{ github.ref_name }}-md2zhihu/_md2zhihu/`

-   `target_platform`:

    The platform that the converted markdown should be compatible to.

    Currently supported platforms are zhihu, wechat, weibo, simple.
    `simple` converts almost everything to images and removes most text styles.
    E.g. inline code block is converted to normal text.

    **required**: False
    **default**: `zhihu`

-   `image`:

    The docker image that runs md2zhihu. The action pulls it from its registry before each run.
    Set it to a release, such as `ghcr.io/drmingdrmer/md2zhihu:v0.23`, to keep using that release.
    An image of 0.22 or earlier can not run this action. To keep the push of 0.22, use `drmingdrmer/md2zhihu@v0.22`.

    **required**: False
    **default**: `ghcr.io/drmingdrmer/md2zhihu:latest`
