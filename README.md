# md2zhihu

将markdown转换成 知乎 兼容的 markdown 格式

|       | md源文件              | 导入知乎的效果          |
|:--    | :-:                   | :-:                     |
|使用前 | ![](assets/md.png)    |  ![](assets/before.png) |
|转换后 | ![](assets/built.png) |  ![](assets/after.png)  |

## Install

System requirement: MaxOS

```sh
# For rendering table to html
brew install pandoc imagemagick node
npm install -g @mermaid-js/mermaid-cli
```

```sh
pip install md2zhihu
```

## Usage

```sh
md2zhihu your_great_work.md
```

这个命令将markdown 转换成 知乎 文章编辑器可直接导入的格式, 存储到 `_md2/your_great_work/your_great_work.md`, 然后将图片等资源上传到**当前目录所在的git**的`_md2zhihu`分支. 转换后的markdown文档不依赖任何本地的图片文件或其他文件.

- `-d` 指定输出目录, 默认为`./_md2/`; 所有文章都会保存在这个目录中,
    名为`<article_name>` 的md转换之后保存在`_md2/zhihu/<article_name>/` 目录中,
    包括一个名为`<article_name>.md` 的md文件以及所有使用的图片等在同一个目录下.

    转换后所有输出内容将会push到`-r`指定的git repo中或当前目录下的git的repo中.

- `-r` 指定用于存储图片等资源的git repo url和上传的分支名; 要求是对这个repo有push权限.

    例如要将图片等上传到`github.com/openacid/foo`项目中的`bar`分支:
    ```
    md2zhihu great.md -r https://github.com/openacid/foo.git@bar
    ```

    默认使用当前目录下的git配置, (作者假设用户用git来保存自己的工作:DDD),
    如果没有指定分支名, md2zhihu 将建立一个`_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}`的分支来保存所有图片.

## Windows 下使用: github-action

md2zhihu 不支持windows, 可以通过github-action来实现远程转换:

- 要转换的markdown 全部放在github repo中, push 之后自动构建,
  例如 我自己的博客 https://github.com/drmingdrmer/drmingdrmer.github.io

- 生成github token, 让github action可以将转换的文档 push 回 git repo.
    https://github.com/settings/tokens/new

    具体步骤参考:
    https://docs.github.com/cn/github/authenticating-to-github/creating-a-personal-access-token

- 将上面生成的token 添加到markdown的repo, 名为 `GH_TOKEN`:
    https://github.com/drmingdrmer/drmingdrmer.github.io/settings/secrets/actions

- 在保存markdown 文档的 repo 中创建 action 描述文件:
    `.github/workflows/md2zhihu.yml`:

    ```yaml
    name: md2zhihu
    on:
      push:
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
        - uses: actions/checkout@v2
        - uses: actions/setup-python@v2
          with:
            python-version: 3.8
        - name: Install
          run: |
            pip install md2zhihu==0.1.21
            npm install @mermaid-js/mermaid-cli@8.8.4
            sudo apt-get install pandoc
        - name: Build zhihu compatible markdowns
          env:
            GITHUB_USERNAME: ${{ github.repository_owner }}
            GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
          run: |
            md2zhihu \
            --repo https://github.com/${{ github.repository }}.git@zhihu_branch \
            --code-width 600 \
            --asset-dir _md2zhihu \
            _posts/*.md
    ```

    以上配置在下一次push时, 将 repo 目录 `_posts/` 中所有的md文件进行转换,
    并保存到


## Features

- 公式转换:

  例如 ` $$ ||X{\vec {\beta }}-Y||^{2} $$ `
  ![](https://www.zhihu.com/equation?tex=%7C%7CX%7B%5Cvec%20%7B%5Cbeta%20%7D%7D-Y%7C%7C%5E%7B2%7D)
  转换成可以直接被知乎使用的tex渲染引擎的引用:

  ```
  <img src="https://www.zhihu.com/equation?tex=||X{\vec {\beta }}-Y||^{2}\\" ...>
  ```

- 自动识别block的公式和inline的公式.

- 表格: 将markdown表格转换成html 以便支持知乎直接导入.

- 图片: md2zhihu 将图片上传到github, 并将markdown中的图片引用做替换.

- mermaid: 将mermaid语法渲染成图片, 并上传. 例如:

    ```mermaid
    graph LR
        A[Hard edge] -->|Link text| B(Round edge)
        B --> C{Decision}
        C -->|One| D[Result one]
        C -->|Two| E[Result two]
    ```

    转换成:

    ![](assets/mermaid.jpg)

-   链接列表: 将 markdown 的 reference-style link 转成链接列表:

    | 源文件 | 转换后 | 导入后 |
    | :-: | :-: | :-: |
    | ![](assets/ref-list/src.png) | ![](assets/ref-list/dst.png) | ![](assets/ref-list/imported.png) |



## Limitation

- 知乎的表格不支持table cell 中的markdown格式, 例如表格中的超链接, 无法渲染, 会被知乎转成纯文本.
- md2zhihu 无法处理jekyll/github page的功能标签例如 `{% octicon mark-github height:24 %}`. 这部分文本目前需要导入后手动删除或修改.
