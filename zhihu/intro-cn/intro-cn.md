# markdown一键导入知乎: md2zhihu

如果你的博客是用markdown编辑的, 例如使用jekyll 或 gihtub page托管,
本文介绍的 md2zhihu 小工具可以帮你实现自动的markdown转换,
将jekyll的markdown转换成知乎兼容的markdown格式.

<table>
<tr class="header">
<th style="text-align: left;"></th>
<th style="text-align: center;">md</th>
<th style="text-align: center;">imported</th>
</tr>
<tr class="odd">
<td style="text-align: left;">original</td>
<td style="text-align: center;"><img src="https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/md.png" /></td>
<td style="text-align: center;"><img src="https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/before.png" /></td>
</tr>
<tr class="even">
<td style="text-align: left;">converted</td>
<td style="text-align: center;"><img src="https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/built.png" /></td>
<td style="text-align: center;"><img src="https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/after.png" /></td>
</tr>
</table>

md2zhihu 通过 github action来自动完成,
只需要在保存博客文章的git repo中添加一个action定义:
创建action配置文件
`.github/workflows/md2zhihu.yml`:

```yaml
name: md2zhihu
on: [push]
jobs:
  md2zhihu:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: drmingdrmer/md2zhihu@v0.4
      env:
        GITHUB_USERNAME: ${{ github.repository_owner }}
        GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
      with:
        pattern: >
            _posts/*.md
            _posts/*.markdown
```

下次提交时, github action将自动把
 `_posts/` 目录下的markdown 转换成可以在知乎一键导入的格式,
 转换后的文件存储在另一个分支中:
`_md2zhihu/md`.

例如我自己的blog [drmingdrmer.github.io](https://drmingdrmer.github.io/)
就是用github page托管, 已经配置好了自动转换脚本:
https://github.com/drmingdrmer/drmingdrmer.github.io/blob/master/.github/workflows/md2zhihu.yml

最新push后自动转换的文章可以直接在线上看到:
https://github.com/drmingdrmer/drmingdrmer.github.io/tree/_md2zhihu/md/_md2zhihu

因为自动转换在github服务器上运行, 要使用转换后的文件,
可以直接 fetch then merge 分支
`_md2zhihu/md`.
或直接在github上打开这个分支看到内容, 例如可以看到我blog中的一篇文章转换后的效果:
https://github.com/drmingdrmer/drmingdrmer.github.io/blob/_md2zhihu/md/_md2zhihu/dict-cmp.md

上面的配置中需要一个名为 `GH_TOKEN` 的token
以授权github action可以将转换的文档 push 回 repo:

## 创建 token

通过以下链接创建:
https://github.com/settings/tokens/new

步骤可参考:
https://docs.github.com/cn/github/authenticating-to-github/creating-a-personal-access-token

创建后应该在以下页面看到刚创建的token:
https://github.com/settings/tokens

![](https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/create-token.png)

## 添加 token

将上面生成的token 添加到存储文章的 repo, 命名为 `GH_TOKEN`,
接着让 github-action 使用这个 token 来 push 代码:
在 repo 主页, 通过菜单 setting-Secrets-New repository secret 进入添加token页面.

添加后效果如下:

![](https://cdn.jsdelivr.net/gh/drmingdrmer/md2zhihu@_md2zhihu_md2zhihu_3959bd99/zhihu/intro-cn/add-token.png)

# Options

下面这些选项也可以使用`with`来传入, 控制转换的行为:

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

    The platform that the converted markdown should be compatible toṫCurrently supported platforms are zhihu, wechat, weibo, simple. `simple` converts almost everything to images and removes most text styles. E.g. inline code block is converted to normal text.

    **required**: True
    **default**: `zhihu`



Reference:

