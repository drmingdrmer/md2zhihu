-   `pattern`:

    file pattern to convert

    **required**: True
    **default**: `**/*.md`

-   `output_dir`:

    dir to store converted markdown.

    **required**: True
    **default**: `_md2zhihu`

-   `asset_repo`:

    Specify the git repo for asset storage.

    The converted markdown will reference images in this repo. Supported providers include `github.com` and `gitee.com`.
    When this option is absent, assets are pushed to the current repo: `https://github.com/{{ github.repository }}.git`.

    To push assets to `gitee.com`:

    1. On gitee.com, create a access token at https://gitee.com/personal_access_tokens, to enable pushing assets to gitee.com;

    2. Add a secret to the GitHub markdown repository that contains your gitee.com username and token (e.g., `GITEE_AUTH=drdrxp:abcd...xyz`) at `https://github.com/<username>/<repo>/settings/secrets/actions`.

    3. Set `asset_repo` to the gitee.com repo push URL with the auth token, such as:
       `asset_repo: https://[dollar]{{ secrets.GITEE_AUTH }}@gitee.com/drdrxp/bed.git`

    **required**: False
    **default**: the local repo: 'https://github.com/${{github.repository}}.git'

-   `asset_branch`:

    The branch in which assets are stored. This branch must NOT be removed otherwise the assets will not be accessed.

    **required**: True
    **default**: `<branch-name>-md2zhihu-asset`

-   `target_platform`:

    The platform that the converted markdown should be compatible to.
    Currently supported platforms are zhihu, wechat, weibo, simple. `simple` converts almost everything to images and removes most text styles. E.g. inline code block is converted to normal text.

    **required**: True
    **default**: `zhihu`


-   `output_branch`:

    Commit and push the `output_dir` to a branch of this repo.
    Set this to "" to disable push, in which case, user commit and push it manually.

    **required**: True
    **default**: '<branch-name>-md2zhihu'
