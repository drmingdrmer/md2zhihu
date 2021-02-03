# DO NOT EDIT!!! built with `python _building/build_setup.py`
import setuptools

import imp

pseudo = "pseudo"
pkg = imp.load_source(pseudo, 'md2zhihu/version.py')

setuptools.setup(
    name="md2zhihu",
    packages=["md2zhihu",
              "md2zhihu.mistune",
              "md2zhihu.md2zhihu",
              "md2zhihu.mistune.plugins"],
    version=pkg.__version__,
    license='MIT',
    description='convert markdown to zhihu compatible format.',
    long_description='# md2zhihu\n\n将markdown转换成 知乎 兼容的 markdown 格式\n\n## Install\n\n```sh\npip install md2zhihu\n```\n\n## Usage\n\n```sh\nmd2zhihu your_great_work.md\n```\n\n这个命令将markdown 转换成 知乎 文章编辑器可直接导入的格式, 存储到 `_md2/your_great_work/your_great_work.md`.\n`-o` 选项可以用来调整输出目录.\n\n## Features\n\n- 公式转换:\n\n  例如\n\n  ```\n  $$\n  ||X{\\vec {\\beta }}-Y||^{2}\n  $$\n  ```\n\n  $$\n  ||X{\\vec {\\beta }}-Y||^{2}\n  $$\n\n  转换成可以直接被知乎使用的tex渲染引擎的引用:\n\n  ```\n  <img src="https://www.zhihu.com/equation?tex=%7C%7CX%7B%5Cvec%20%7B%5Cbeta%20%7D%7D-Y%7C%7C%5E%7B2%7D%5C%5C" alt="||X{\\vec {\\beta }}-Y||^{2}\\\\" class="ee_img tr_noresize" eeimg="1">\n  ```\n\n  md2zhihu 能自动识别block的公式和inline的公式.\n\n- 表格: 将markdown表格转换成html 以便支持知乎直接导入.\n\n- 图片: md2zhihu 将图片上传到github, 并将markdown中的图片引用做替换.\n\n  - 默认命令例如`md2zhihu your_great_work.md`要求当前工作目录是一个git(作者假设用户用git来保存自己的工作), md2zhihu将建立一个随机分支来保存所有图片.\n\n  - 也可以使用指定的git repo来保存图片, 例如:\n\n    `md2zhihu your_great_work.md -r https://github.com/openacid/openacid.github.io.git `要求是对这个repo有push权限.\n\n## Limitation\n\n- 知乎的表格不支持table cell 中的markdown格式, 例如表格中的超链接, 无法渲染, 会被知乎转成纯文本.\n',
    long_description_content_type="text/markdown",
    author='Zhang Yanpo',
    author_email='drdr.xp@gmail.com',
    url='https://github.com/pykit3/md2zhihu',
    keywords=['python', 'markdown', 'zhihu'],
    python_requires='>=3.0',

    entry_points = {
        'console_scripts': [
            'md2zhihu = md2zhihu:main',
        ],
    },

    install_requires=['PyYAML~=5.3.1', 'k3down2==0.1.13', 'k3handy', 'k3color~=0.1.2'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
    ] + ['Programming Language :: Python :: 3'],
)
