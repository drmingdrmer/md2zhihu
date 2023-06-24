# md2zhihu

中文介绍在: [md2zhihu-中文介绍](README-cn.md).

Converts markdown into a single-file version without local asset dependencies,
which can be directly imported into [zhihu.com](zhihu.com) or other social
platforms with a single click.

[md2zhihu on Marketplace](https://github.com/marketplace/actions/md2zhihu)

|           | md                    | imported               |
| :--       | :-:                   | :-:                    |
| original  | ![](assets/md.png)    | ![](assets/before.png) |
| converted | ![](assets/built.png) | ![](assets/after.png)  |

# Usage

**md2zhihu DOES NOT support Windows**: [Issue: no module termios](https://github.com/drmingdrmer/md2zhihu/issues/7).
Use it remotely with GitHub Action:

## 1. Use it remotely with GitHub Action:

This is the recommended method since you do not need to install anything
locally. Only `git` is required. See: [md2zhihu on
Marketplace](https://github.com/marketplace/actions/md2zhihu)

**Note**: use `asset_repo` to specify a gitee.com repo so that zhihu.com load images from it when importing.

Add the action configuration into the git repository where your markdown files
are located for conversion:
`.github/workflows/md2zhihu.yml`:

```yaml
name: md2zhihu
on: [push]
jobs:
  md2zhihu:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: drmingdrmer/md2zhihu@main
      env:
        GITHUB_USERNAME: ${{ github.repository_owner }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        pattern: >
            _posts/*.md
            _posts/*.markdown

        asset_repo: https://${{ secrets.GITEE_PUSH_DRDRXP_REPO }}@gitee.com/drdrxp/bed.git
```

The conversion will be triggered on the next push:

It will convert markdown files in the `_posts/` directory and save them in the `_md2zhihu` directory.
A new branch `master-md2zhihu` containing these outputs will be created:

Branch `master`:
```
▾ _posts/
    2013-01-31-jobq.markdown
    2013-01-31-resource.markdown
    ...
```

Branch `master-md2zhihu`:
```
▾ _posts/
    2013-01-31-jobq.md
    2013-01-31-resource.md
    ...
▾ _md2zhihu/
    jobq.md
    resource.md
    ...
```

For example, one of the converted [single-file examples](https://github.com/drmingdrmer/drmingdrmer.github.io/blob/master/_md2zhihu/dict-cmp.md)
has all its assets stored remotely on gitee.com, so it can be safely used
anywhere without worrying about handling its dependency assets.

There are two ways to get the converted markdown files:
- `git fetch` and `git merge` the branch `master-md2zhihu`.
- Or access this branch directly on the web:
  [single-file example](https://github.com/drmingdrmer/drmingdrmer.github.io/blob/master/_md2zhihu/dict-cmp.md)

**Action Options for md2zhihu**

-   `pattern`:

    File pattern to convert

    **required**: True
    **default**: `**/*.md`

-   `output_dir`:

    Directory to store converted markdown

    **required**: True
    **default**: `_md2zhihu`

-   `asset_repo`:

    Specify the git repo for asset storage.

    The converted markdown will reference images in this repo. Supported providers include `github.com` and `gitee.com`.
    When this option is absent, assets are pushed to the current repo: `https://github.com/{{ github.repository }}.git`.

    To push assets to `gitee.com`:

    1. On gitee.com, create an access token at https://gitee.com/personal_access_tokens, to enable pushing assets to gitee.com;
       The token must enable `projects` privileges.

    2. Add a secret to the GitHub markdown repository that contains your gitee.com username and token (e.g., `GITEE_AUTH=drdrxp:abcd...xyz`) at `https://github.com/<username>/<repo>/settings/secrets/actions`.

    3. Set `asset_repo` to the gitee.com repo push URL with the auth token, such as:

       ```markdown
       - uses: drmingdrmer/md2zhihu@main
         with:
           pattern: _posts/*.md
           asset_repo: https://${{ secrets.GITEE_AUTH }}@gitee.com/drdrxp/bed.git
       ```

    **required**: False
    **default**: the local repo: 'https://github.com/${{github.repository}}.git'

-   `asset_branch`:

    The branch name in which assets are stored.

    **required**: True
    **default**: `${{ github.ref_name }}-md2zhihu-asset`

-   `output_branch`:

    The branch name to which output markdowns are stored.
    Set this to "" to disable push, in which case, user commit and push it manually.

    **required**: True
    **default**: `${{ github.ref_name }}-md2zhihu`

-   `target_platform`:

    The platform that the converted markdown should be compatible toṫCurrently supported platforms are zhihu, wechat, weibo, simple. `simple` converts almost everything to images and removes most text styles. E.g. inline code block is converted to normal text.

    **required**: True
    **default**: `zhihu`


## 2. Use it on your laptop

**System requirements**

MaxOS

```sh
# For rendering table to html
brew install pandoc imagemagick node
npm install -g @mermaid-js/mermaid-cli
pip install md2zhihu
```

**Basic usage**:

In a git working dir that contains markdowns to convert:

```sh
md2zhihu your_great_work.md -r .
```

This command converts `your_great_work.md` to `_md2/your_great_work.md`.
And the assets it references are uploaded to the git repo found in current dir.


**Use another git to store assets**:

```
md2zhihu your_great_work.md -r git@github.com:drmingdrmer/md2test.git@test
```

And you need **write access** on the git repo otherwise the assests can not be
uploaded.

**Other options**: `md2zhihu --help`

### Trouble shoot

**command not found: md2zhihu**

- `pip install --verbose md2zhihu` Confirm that install done successfully.
- `which md2zhihu` Confirm that the binary can be found: e.g.: `/Users/drdrxp/xp/py3virtual/p38/bin/md2zhihu`.
- `echo $PATH` Confirmat that the install path is included in `PATH`: `...:/Users/drdrxp/xp/py3virtual/p38/bin:...`

# Features

- Transform latex to image:

  E.g. ` $$ ||X{\vec {\beta }}-Y||^{2} $$ ` is converted to 
  ![](https://www.zhihu.com/equation?tex=%7C%7CX%7B%5Cvec%20%7B%5Cbeta%20%7D%7D-Y%7C%7C%5E%7B2%7D)

- Transform table to HTML.

- Upload images to specified git repo.

- Transform mermaid code block to image:

    ```
    graph LR
        A[Hard edge] -->|Link text| B(Round edge)
        B --> C{Decision}
        C -->|One| D[Result one]
        C -->|Two| E[Result two]
    ```

    is converted to:

    ![](assets/mermaid.jpg)


- Transform graphviz code block to image:

    ```graphviz
    digraph R {
        node [shape=plaintext]
        rankdir=LR
        X0X0 [ label="0-0"]
        X0X0 -> X1X0 [ color="#aaaadd"]
        X0X0 -> X2X3 [ color="#aaaadd"]
    }
    ```
    is converted to:

    ![](assets/graphviz.jpg)


-   Generate link list:

    | original | converted | imported |
    | :-: | :-: | :-: |
    | ![](assets/ref-list/src.png) | ![](assets/ref-list/dst.png) | ![](assets/ref-list/imported.png) |


# Limitation

- zhihu.com does not support markdown syntax inside a table cell.
  These in-table-cell content are transformed into plain text.

- md2zhihu can not deal with jekyll/github page tags. E.g. `{% octicon mark-github height:24 %}`.
