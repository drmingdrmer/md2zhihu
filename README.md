# md2zhihu

将markdown转换成 知乎 兼容的 markdown 格式

## Install

```sh
pip install md2zhihu
```

## Usage

```sh
md2zhihu your_great_work.md
```

这个命令将markdown 转换成 知乎 文章编辑器可直接导入的格式, 存储到 `_md2/your_great_work/your_great_work.md`.
`-o` 选项可以用来调整输出目录.

## Features

- 公式转换:

  例如

  ```
  $$
  ||X{\vec {\beta }}-Y||^{2}
  $$
  ```

  <img src="https://www.zhihu.com/equation?tex=%7C%7CX%7B%5Cvec%20%7B%5Cbeta%20%7D%7D-Y%7C%7C%5E%7B2%7D%5C%5C" alt="||X{\vec {\beta }}-Y||^{2}\\" class="ee_img tr_noresize" eeimg="1">

  转换成可以直接被知乎使用的tex渲染引擎的引用:

  ```
  <img src="https://www.zhihu.com/equation?tex=||X{\vec {\beta }}-Y||^{2}\\" alt="||X{\vec {\beta }}-Y||^{2}\\" class="ee_img tr_noresize" eeimg="1">
  ```

- 自动识别block的公式和inline的公式.

- 表格: 将markdown表格转换成html 以便支持知乎直接导入.

- 图片: md2zhihu 将图片上传到github, 并将markdown中的图片引用做替换.

  - 默认命令例如`md2zhihu your_great_work.md`要求当前工作目录是一个git(作者假设用户用git来保存自己的工作), md2zhihu将建立一个随机分支来保存所有图片.

  - 也可以使用指定的git repo来保存图片, 例如使用`github.com/openacid/openacid.github.io` 这个repo来保存图片:

    `md2zhihu your_great_work.md -r https://github.com/openacid/openacid.github.io.git `要求是对这个repo有push权限.

## Limitation

- 知乎的表格不支持table cell 中的markdown格式, 例如表格中的超链接, 无法渲染, 会被知乎转成纯文本.
- md2zhihu 无法处理jekyll/github page的功能标签例如 `{% octicon mark-github height:24 %}`. 这部分文本目前需要导入后手动删除或修改.
