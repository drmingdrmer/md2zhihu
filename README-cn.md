# md2zhihu

将 markdown 转换成 [知乎](zhihu.com) 兼容的 markdown 格式

[md2zhihu on Marketplace](https://github.com/marketplace/actions/md2zhihu)

|           | md                    | 导入后                 |
| :--       | :-:                   | :-:                    |
| 原始文件  | ![](assets/md.png)    | ![](assets/before.png) |
| 转换后    | ![](assets/built.png) | ![](assets/after.png)  |

# 使用方法

**md2zhihu 不支持 Windows**：[Issue: no module termios](https://github.com/drmingdrmer/md2zhihu/issues/7)。
请通过 GitHub Action 远程使用：

## 1. 通过 GitHub Action 远程使用：


**注意**：强烈建议使用 `asset_repo` 指定一个 gitee.com 仓库，以便在导入 zhihu.com 时能顺利导入图片。

将 github-action 添加到 Markdown 文件所在的 git 仓库：
`.github/workflows/md2zhihu.yml`：

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

下一次推送它将转换 `_posts/` 目录中的 Markdown 文件，并将它们保存在 `_md2zhihu` 目录中。
并将创建一个新分支 `master-md2zhihu`：

分支 `master`：
```
▾ _posts/
    2013-01-31-jobq.markdown
    2013-01-31-resource.markdown
    ...
```

分支 `master-md2zhihu`：
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

其中一个转换后的[示例](https://github.com/drmingdrmer/drmingdrmer.github.io/blob/master/_md2zhihu/dict-cmp.md)
它的所有图片都存储在 gitee.com 上，因此可以直接导入这个文件到其他zhihu.com，而无需担心处理其依赖的资源。

获取转换后的 Markdown 文件有两种方法：
- `git fetch` 和 `git merge` `master-md2zhihu`分支。
- 或直接在 web 上访问此分支：
  [转换后的文件](https://github.com/drmingdrmer/drmingdrmer.github.io/blob/master/_md2zhihu/dict-cmp.md)

**md2zhihu 参数**

-   `pattern`：

    匹配要转换的文件

    **required**：True
    **default**：`**/*.md`

-   `output_dir`：

    存储转换后的 Markdown 的目录

    **required**：True
    **default**：`_md2zhihu`

-   `asset_repo`：

    指定用于图片的 git 仓库。

    转换后的 markdown 将引用这个仓库中的图片。支持的git平台包括 `github.com` 和 `gitee.com`。
    当此选项为空时，图片会保存在 markdown 文件所在的 git 仓库中。

    **required**：False
    **default**：`""`

-   `asset_branch`：

    存储图片资源的分支名

    **required**：False
    **default**: `${{ github.ref_name }}-md2zhihu-asset`

    -   `output_branch`:

    存储输出 Markdown 文件的分支名。
    将此设置为空字符串("")可以禁用push build后的输出文件，在这种情况下，用户需要手动提交和推送。

    **required**: True
    **default**: `${{ github.ref_name }}-md2zhihu`


-   `target_platform`:

    转换后的 Markdown 应与指定的平台兼容。
    目前支持的平台有`zhihu`, `wechat`, `weibo`, `simple`。`simple` 将几乎所有内容(公式, 图表等)转换为图片，并删除大部分文本样式。
    例如，将内联代码块转换为普通文本。

    **required**: True
    **default**: `zhihu`

## 2. 在笔记本上使用

**系统要求**

MaxOS

```sh
# 用于将表格渲染为 HTML
brew install pandoc imagemagick node
npm install -g @mermaid-js/mermaid-cli
pip install md2zhihu
```

**基本用法**：

在包含要转换的 Markdown 文件的 git 工作目录中：

```sh
md2zhihu your_great_work.md -r .
```

此命令将 `your_great_work.md` 转换为 `_md2/your_great_work.md`。
并且它引用的图片将上传到当前目录中找到的 git 仓库。

**使用另一个 git 存储图片**：

```
md2zhihu your_great_work.md -r git@github.com:drmingdrmer/md2test.git@test
```

您需要在 git 仓库上具有 **写入权限**，否则无法上传图片。

**其他选项**：`md2zhihu --help`

### 故障排查


- **command not found: md2zhihu**

  尝试以下步骤：

  - `pip install --verbose md2zhihu` 确认已成功安装。
  - `which md2zhihu` 确认可以找到二进制文件，例如：`/Users/drdrxp/xp/py3virtual/p38/bin/md2zhihu`。
  - `echo $PATH` 确认安装路径已包含在 `PATH` 中：`...:/Users/drdrxp/xp/py3virtual/p38/bin:...`

- Github workflow 报错: **remote: Permission to ... denied to github-actions**

  ```
  remote: Permission to <your_repo>.git denied to github-actions[bot].
  fatal: unable to access 'https://github.com/<your_name>/<your_repo>.git/': The requested URL returned error: 403
  ```

  尝试以下步骤：

  - 进入repo settings
  - 点击 "Action" 下拉菜单
  - 然后点击 "General"
  - 向下滚动一点，直到你看到 "Workflow permissions"
  - 它可能设置在 "Read repository contents and packages permissions"
  - 点击 "Read and write permissions"
  - 向下滚动并保存。

# Features

- 将 LaTeX 转换为图片：

  例如，` $$ ||X{\vec {\beta }}-Y||^{2} $$ ` 被转换为
  ![](https://www.zhihu.com/equation?tex=%7C%7CX%7B%5Cvec%20%7B%5Cbeta%20%7D%7D-Y%7C%7C%5E%7B2%7D)

- 将表格转换为 HTML。

- 将图片上传到指定的 git 仓库。

- 将 mermaid 代码块转换为图片：

    ```
    graph LR
        A[Hard edge] -->|Link text| B(Round edge)
        B --> C{Decision}
        C -->|One| D[Result one]
        C -->|Two| E[Result two]
    ```

    被转换为：

    ![](assets/mermaid.jpg)

- 将 graphviz 代码块转换为图片：

    ```graphviz
    digraph R {
        node [shape=plaintext]
        rankdir=LR
        X0X0 [ label="0-0"]
        X0X0 -> X1X0 [ color="#aaaadd"]
        X0X0 -> X2X3 [ color="#aaaadd"]
    }
    ```
    被转换为：

    ![](assets/graphviz.jpg)

- 生成链接列表：

    | 原始 | 转换后 | 导入后 |
    | :-: | :-: | :-: |
    | ![](assets/ref-list/src.png) | ![](assets/ref-list/dst.png) | ![](assets/ref-list/imported.png) |


# Limitation

- 知乎不支持表格单元格内的 Markdown 语法。
  这些在表格单元格内的内容将被转换为纯文本。

- md2zhihu 无法处理 Jekyll/GitHub 页面标签。例如，`{% octicon mark-github height:24 %}`。

