# md2zhihu

将markdown转换成 知乎 兼容的 markdown 格式

|       | md源文件              | 导入知乎的效果          |
|:--    | :-:                   | :-:                     |
|使用前 | ![](assets/md.png)    |  ![](assets/before.png) |
|转换后 | ![](assets/built.png) |  ![](assets/after.png)  |


## Install

```sh
pip install md2zhihu
```

## Usage

```sh
md2zhihu your_great_work.md
```

这个命令将markdown 转换成 知乎 文章编辑器可直接导入的格式, 存储到 `_md2/your_great_work/your_great_work.md`, 然后将图片等资源上传到**当前目录所在的git**的`_md2zhihu`分支. 转换后的markdown文档不依赖任何本地的图片文件或其他文件.

- `-o` 指定输出目录, 默认为`./_md2/`; 所有文章都会保存在这个目录中,
    名为`<article_name>` 的md转换之后保存在`_md2/zhihu/<article_name>/` 目录中,
    包括一个名为`<article_name>.md` 的md文件以及所有使用的图片等在同一个目录下.

    转换后所有输出内容将会push到`-r`指定的git repo中或当前目录下的git的repo中.

- `-r` 指定用于存储图片等资源的git repo url和上传的分支名; 要求是对这个repo有push权限.

    例如要将图片等上传到`github.com/openacid/foo`项目中的`bar`分支:
    ```
    md2zhihu great.md -r https://github.com/openacid/foo.git@bar
    ```

    默认使用当前目录下的git配置, (作者假设用户用git来保存自己的工作:DDD),
    如果没有指定分支名, md2zhihu 将建立一个`_md2zhihu`的分支来保存所有图片.


## Requirements

```
# For rendering table to html
brew install pandoc imagemagick node
npm install -g @mermaid-js/mermaid-cli
```

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


## Limitation

- 知乎的表格不支持table cell 中的markdown格式, 例如表格中的超链接, 无法渲染, 会被知乎转成纯文本.
- md2zhihu 无法处理jekyll/github page的功能标签例如 `{% octicon mark-github height:24 %}`. 这部分文本目前需要导入后手动删除或修改.
