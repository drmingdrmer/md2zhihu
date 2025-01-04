import glob
import os
import re
import unittest

import k3fs
import k3git
import k3proc
import k3ut
import skimage
import skimage.io
from k3handy import cmdx
from k3handy import pabs
from k3handy import pjoin
from skimage.metrics import structural_similarity

import md2zhihu

dd = k3ut.dd

this_base = os.path.dirname(__file__)
test_data = 'test/data'


class TestMd2zhihu(unittest.TestCase):

    def _clean(self):
        pass

    def setUp(self):
        self._clean()

    def tearDown(self):
        self._clean()

    def test_asset_repo(self):
        for url in (
                'git@github.com:drmingdrmer/home.git',
                'ssh://git@github.com/drmingdrmer/home',
                'https://github.com/drmingdrmer/home.git',
        ):
            a = md2zhihu.AssetRepo(url, cdn=False)
            self.assertEqual(False, a.cdn)
            self.assertRegex(a.branch, '_md2zhihu_md2zhihu_[a-z0-9]{8}')
            b = a.branch
            self.assertEqual('github.com', a.host)
            self.assertEqual('drmingdrmer', a.user)
            self.assertEqual('home', a.repo)
            self.assertEqual(
                'https://raw.githubusercontent.com/drmingdrmer/home/' + b + '/{path}', a.path_pattern)

        # specify branch

        url = 'git@github.com:drmingdrmer/home.git@abc'
        a = md2zhihu.AssetRepo(url, cdn=False)
        self.assertEqual(False, a.cdn)
        self.assertEqual('abc', a.branch)
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)
        self.assertEqual(
            'https://raw.githubusercontent.com/drmingdrmer/home/abc/{path}', a.path_pattern)

        #  with cdn

        a = md2zhihu.AssetRepo('git@github.com:drmingdrmer/home.git')
        self.assertEqual(True, a.cdn)
        self.assertRegex(a.branch, '_md2zhihu_md2zhihu_[a-z0-9]{8}')
        b = a.branch
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)
        self.assertEqual(
            'https://cdn.jsdelivr.net/gh/drmingdrmer/home@' + b + '/{path}', a.path_pattern)

        # https url with token

        a = md2zhihu.AssetRepo('https://aa:bb@github.com/drmingdrmer/home.git')
        self.assertEqual(True, a.cdn)
        self.assertEqual('https://aa:bb@github.com/drmingdrmer/home.git', a.url)
        self.assertRegex(a.branch, '_md2zhihu_md2zhihu_[a-z0-9]{8}')
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)

    def test_local_repo(self):
        cases = [
            ('./x.md', '.', '{path}'),
            ('./x.md', 'a/b', 'a/b/{path}'),
            ('a/b/x.md', 'a', '../{path}'),
            ('a/b/x.md', 'a/', '../{path}'),
            ('a/b/x.md', 'a/b', '{path}'),
            ('a/b/x.md', 'a/b/', '{path}'),
            ('a/b/x.md', 'a/b/c', 'c/{path}'),
            ('a/b/x.md', 'u/', '../../u/{path}'),
        ]

        for c in cases:
            md_path, asset_path, want = c
            dd(c)
            local = md2zhihu.LocalRepo(md_path, asset_path)
            self.assertEqual(want, local.path_pattern)


    def test_chunks(self):
        parser_config = md2zhihu.ParserConfig(False, [])
        conf = md2zhihu.Config(
            "foo.md", "null", "output_foo", "output_asset_dir",
            md_output_path="output_md",
        )

        md_text = k3fs.fread(test_data + '/simple/src/simple.md')

        article = md2zhihu.Article(
            parser_config,
            conf,
            md_text,
        )

        for c in article.chunks():
            print(c)

        got = list(article.chunks())

        want = [
            ('front_matter', '', '---\nrefs:\n    - "slim":      https://github.com/openacid/slim "slim"\n    - "slimarray": https://github.com/openacid/slimarray "slimarray"\n    - "vlink": https://vlink "vlink"\n\nplatform_refs:\n    zhihu:\n        - "vlink": https://vlink.zhihu "vlink"\n---'),
            ('content', 'newline', ''),
            ('content', 'heading', '# 场景和问题\n'),
            ('content', 'table', '|  | md源文件 | 导入知乎的效果 |\n| :-- | :-: | :-: |\n| 使用前 | a | c |\n| 转换后 | b | d |\n'),
            ('content', 'block_code', '```mermaid\ngraph LR\n    A[Hard edge] -->|Link text| B(Round edge)\n    B --> C{Decision}\n    C -->|One| D[Result one]\n    C -->|Two| E[Result two]\n```\n'),
            ('content', 'heading', '### graphviz\n'),
            ('content', 'block_code', '```graphviz\ndigraph R {\nnode [shape=plaintext]\nrankdir=LR\nX0X0 [ label="0-0"]\nX0X0 -> X1X0 [ color="#aaaadd"]\nX0X0 -> X2X3 [ color="#aaaadd"]\n}\n```\n'),
            ('content', 'paragraph', 'inline code: `foo = bar`\n'),
            ('content', 'paragraph', 'inline math $$ ||X{\\vec {\\beta }}-Y||^{2} $$ foo\n'),
            ('content', 'paragraph', 'inline math in codespan `$$ ||X{\\vec {\\beta }}-Y||^{2} $$`\n![](assets/slim.jpg)\n'),
            ('content', 'paragraph', '在时序数据库, 或列存储为基础的系统中, 很常见的形式就是存储一个整数数组,\n例如 [slim] 这个项目按天统计的 star 数:\n'),
            ('content', 'paragraph', '![](assets/slim.jpg)\n![](/src/assets/slim.jpg)\n'),
            ('content', 'paragraph', '我们可以利用数据分布的特点, 将整体数据的大小压缩到**几分之一**.\n'),
            ('content', 'table', '| Data size | Data Set | gzip size | slimarry size | avg size | ratio |\n| --: | :-- | --: | :-- | --: | --: |\n| 1,000 | rand u32: [0, 1000] | x | 824 byte | 6 bit/elt | 18% |\n| 1,000,000 | rand u32: [0, 1000,000] | x | 702 KB | 5 bit/elt | 15% |\n| 1,000,000 | IPv4 DB | 2 MB | 2 MB | 16 bit/elt | 50% |\n| 600 | [slim][] star count | 602 byte | 832 byte | 10 bit/elt | 26% |\n'),
            ('content', 'paragraph', '在达到gzip同等压缩率的前提下, 构建 slimarray 和 访问的性能也非常高:\n'),
            ('content', 'list_item', '-   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;\n'),
            ('content', 'list_item', '-   读取一个数组元素平均花费 7 ns/op.\n    -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;\n    -   读取一个数组元素平均花费 `7 ns/op`.\n'),
            ('content', 'new_line', ''),
            ('content', 'block_quote', '> 在达到gzip同等压缩率的前提下, 构建 slimarray 和 访问的性能也非常高:\n> \n> -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;\n> -   读取一个数组元素平均花费 7 ns/op.\n>     -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;\n>     -   读取一个数组元素平均花费 `7 ns/op`.\n'),
            ('content', 'newline', ''),
            ('content', 'paragraph', '按照这种思路, **在给定数组中找到一条曲线来描述点的趋势,**\n**再用一个比较小的delta数组修正曲线到实际点的距离, 得到原始值, 就可以实现大幅度的数据压缩. 而且所有的数据都无需解压全部数据就直接读取任意一个.**\n'),
            ('content', 'heading', '# 找到趋势函数\n'),
            ('content', 'paragraph', '寻找这样一条曲线就使用线性回归,\n例如在 [slimarray] 中使用2次曲线 `f(x) = β₁ + β₂x + β₃x²`, 所要做的就是确定每个βᵢ的值,\n以使得`f(xⱼ) - yⱼ`的均方差最小. xⱼ是数组下标0, 1, 2...; yⱼ是数组中每个元素的值.\n'),
            ('content', 'paragraph', '$$\nX = \\begin{bmatrix}\n1      & x_1    & x_1^2 \\\\\n1      & x_2    & x_2^2 \\\\\n\\vdots & \\vdots & \\vdots    \\\\\n1      & x_n    & x_n^2\n\\end{bmatrix}\n,\n\n\\vec{\\beta} =\n\\begin{bmatrix}\n\\beta_1 \\\\\n\\beta_2 \\\\\n\\beta_3 \\\\\n\\end{bmatrix}\n,\n\nY =\n\\begin{bmatrix}\ny_1 \\\\\ny_2 \\\\\n\\vdots \\\\\ny_n\n\\end{bmatrix}\n$$\n'),
            ('content', 'paragraph', '`spanIndex = OnesCount(bitmap & (1<<(i/16) - 1))`\n'),
            ('content', 'heading', '## 读取过程\n'),
            ('content', 'paragraph', '读取过程通过找span, 读取span配置,还原原始数据几个步骤完成, 假设 slimarray 的对象是`sa`:\n'),
            ('content', 'list_item', '-   通过下标`i` 得到 spanIndex: `spanIndex = OnesCount(sa.bitmap & (1<<(i/16) - 1))`;\n'),
            ('content', 'list_item', '-   通过 spanIndex 得到多项式的3个系数: `[b₀, b₁, b₂] = sa.polynomials[spanIndex: spanIndex + 3]`;\n'),
            ('content', 'list_item', '-   读取 delta 数组起始位置, 和 delta 数组中每个 delta 的 bit 宽度: `config=sa.configs[spanIndex]`;\n'),
            ('content', 'list_item', '-   delta 的值保存在 delta 数组的`config.offset + i*config.width`的位置, 从这个位置读取`width`个 bit 得到 delta 的值.\n'),
            ('content', 'list_item', '-   计算 `nums[i]` 的值: `b₀ + b₁*i + b₂*i²` 再加上 delta 的值.\n'),
            ('content', 'new_line', ''),
            ('content', 'paragraph', '简化的读取逻辑如下:\n'),
            ('content', 'block_code', '```go\nfunc (sm *SlimArray) Get(i int32) uint32 {\n\n    x := float64(i)\n\n    bm := sm.spansBitmap & bitmap.Mask[i>>4]\n    spanIdx := bits.OnesCount64(bm)\n\n    j := spanIdx * polyCoefCnt\n    p := sm.Polynomials\n    v := int64(p[j] + p[j+1]*x + p[j+2]*x*x)\n\n    config := sm.Configs[spanIdx]\n    deltaWidth := config & 0xff\n    offset := config >> 8\n\n    bitIdx := offset + int64(i)*deltaWidth\n\n    d := sm.Deltas[bitIdx>>6]\n    d = d >> uint(bitIdx&63)\n\n    return uint32(v + int64(d&bitmap.Mask[deltaWidth]))\n}\n```\n'),
            ('content', 'paragraph', 'formula in list:\n'),
            ('content', 'list_item', '-   对奇数节点, n = 2k+1, 还是沿用 **多数派** 节点的集合, 大部分场合都可以很好的工作:\n\n    $$\n    Q_{odd}(C) = M(C) = \\{ q : q \\subseteq C,  |q| > |C|/2 \\}\n    $$\n'),
            ('content', 'list_item', "-   对偶数节点, n = 2k, **因为n/2个节点跟n/2+1个节点一定有交集**,\n    我们可以向 M(C) 中加入几个大小为 n/2 的节点集合,\n\n    以本文的场景为例,\n\n    -   可以设置 Q' = M(abcd) ∪ {ab, bc, ca}, Q'中任意2个元素都有交集;\n    -   也可以是 Q' = M(abcd) ∪ {bc, cd, bd};\n\n    要找到一个更好的偶节点的 quorum 集合, 一个方法是可以把偶数节点的集群看做是一个奇数节点集群加上一个节点x:\n    $$ D = C \\cup \\{x\\} $$\n\n    于是偶数节点的 quorum 集合就可以是 M(D) 的一个扩张:\n\n    $$\n    Q_{even}(D)_x = M(D) \\cup M(D \\setminus \\{x\\})\n    $$\n\n    当然这个x可以随意选择, 例如在abcd的例子中, 如果选x = d, 那么\n    Q' = M(abcd) ∪ {ab, bc, ca};\n"),
            ('content', 'new_line', ''),
            ('content', 'paragraph', 'table in list:\n'),
            ('content', 'list_item', '-   链接列表:\n\n    | 源文件 | 转换后 | 导入后 |\n    | :-: | :-: | :-: |\n    | ![](assets/slim.jpg) | fo | bar |\n    | a | b | c |\n'),
            ('content', 'new_line', ''),
            ('ref_def', '', '[slim]: https://github.com/openacid/slim "slim"\n[slimarray]: https://github.com/openacid/slimarray "slimarray"'),
        ]

        self.assertEqual(want, got)

    def test_chunks_list(self):
        parser_config = md2zhihu.ParserConfig(False, [])
        conf = md2zhihu.Config(
            "foo.md", "null", "output_foo", "output_asset_dir",
            md_output_path="output_md",
        )

        article = md2zhihu.Article(
            parser_config,
            conf,"""# 本文结构

- 提出问题
- 协议推导
    - 定义 commit
    - 定义 系统状态(State)
- 协议描述
- 工程实践
- 成员变更
- 使用 abstract-paxos 描述 paxos
- 使用 abstract-paxos 描述 raft
    ```rust
    block();
    ```
""",
        )

        got = list(article.chunks())

        want = [
            ('content', 'heading', '# 本文结构\n'),
            ('content', 'list_item', '-   提出问题\n'),
            ('content', 'list_item', '-   协议推导\n    -   定义 commit\n    -   定义 系统状态(State)\n'),
            ('content', 'list_item', '-   协议描述\n'),
            ('content', 'list_item', '-   工程实践\n'),
            ('content', 'list_item', '-   成员变更\n'),
            ('content', 'list_item', '-   使用 abstract-paxos 描述 paxos\n'),
            ('content', 'list_item', '-   使用 abstract-paxos 描述 raft\n    ```rust\n    block();\n    ```\n'),
            ('content', 'new_line', ''),
            ('ref_def', '', ''),
        ]

        self.assertEqual(want, got)

    def test_option_no_push(self):

        # - Without --repo, do not transform image url.
        # - Output to local dir, without pushing

        platform_type = 'zhihu-localrepo'

        d = pjoin('test/data', platform_type, 'src')
        want_dir = pjoin('test/data', platform_type, 'want')

        cmdx(
            "md2zhihu",
            "simple.md",
            "--md-output", "out.md",
            "--output-dir", ".",
            cwd=d
        )

        cmp_md(self, pjoin(want_dir, 'out.md'), pjoin(d, 'out.md') )
        cmp_all_images(self, d, want_dir)

        cmdx('git', 'clean', '-dxf', cwd=d)

    def test_option_use_local_remote_to_push(self):

        #  TODO output-dir is subdir and use the local git

        # - Use the source git as asset repo.
        # - Output to local dir and push everything to master
        # - Check the pushed data.

        platform_type = 'zhihu-pushall'

        case_dir = pjoin('test/data', platform_type)
        d = pjoin(case_dir, 'src')
        want_dir = pjoin(case_dir, 'want')
        clone_dir = pjoin(case_dir, 'tmp')
        k3fs.remove(clone_dir, onerror='ignore')

        remote_url = get_testing_repo_url()

        make_init_git(d, {"my_remote": remote_url})

        cmdx(
            "md2zhihu",
            "simple.md",
            "--md-output", "out.md",
            "--output-dir", ".",
            "--repo", "my_remote@my_branch",
            cwd=d
        )

        cmp_md(self, pjoin(want_dir, 'out.md'), pjoin(d, 'out.md'))
        cmp_all_images(self, d, want_dir)

        # clone pushed branch and check its content

        cmdx('git', 'clone', remote_url, '--branch', 'my_branch', 'tmp', cwd=case_dir)
        _, out, _ = cmdx('git', 'ls-files', cwd=clone_dir)

        self.assertEqual([
            "assets/slim.jpg",
            "out.md",
            "simple.md",
            "simple/18b61671112f3aeb-slim.jpg",
            "simple/digraphRnodeshape=plaintextrankd-e723805f61ebc412.jpg",
            "simple/graphLRAHardedge--LinktextBRound-38e149134ebbdae5.jpg",
        ], out)

        cmdx('git', 'clean', '-dxf', cwd=pjoin('test/data', platform_type))
        k3fs.remove(clone_dir, onerror='ignore')
        k3fs.remove(d, '.git', onerror='ignore')

    def test_option_use_local_remote_to_push_deep_asset_dir(self):

        # - Use the source git as asset repo.
        # - Output to local nested dir and push everything to master
        # - Check the pushed data.

        platform_type = 'zhihu-deep-asset-dir'

        case_dir = pjoin('test/data', platform_type)
        d = pjoin(case_dir, 'src')
        want_dir = pjoin(case_dir, 'want')
        clone_dir = pjoin(case_dir, 'tmp')

        k3fs.remove(clone_dir, onerror='ignore')

        remote_url = get_testing_repo_url()

        make_init_git(d, {"my_remote": remote_url})

        cmdx(
            "md2zhihu",
            "simple.md",
            "--md-output", "out.md",
            "--output-dir", ".",
            "--asset-output-dir", "foo/bar",
            "--repo", "my_remote@my_branch_deep",
            cwd=d
        )

        cmp_md(self, pjoin(want_dir, 'out.md'), pjoin(d, 'out.md'))
        cmp_all_images(self, d, want_dir)

        # clone pushed branch and check its content

        cmdx('git', 'clone', remote_url, '--branch', 'my_branch_deep', 'tmp', cwd=case_dir)
        _, out, _ = cmdx('git', 'ls-files', cwd=clone_dir)

        self.assertEqual([
            "assets/slim.jpg",
            "foo/bar/simple/18b61671112f3aeb-slim.jpg",
            "foo/bar/simple/digraphRnodeshape=plaintextrankd-e723805f61ebc412.jpg",
            "foo/bar/simple/graphLRAHardedge--LinktextBRound-38e149134ebbdae5.jpg",
            "out.md",
            "simple.md",
        ], out)

        cmdx('git', 'clean', '-dxf', cwd=case_dir)
        k3fs.remove(clone_dir, onerror='ignore')
        k3fs.remove(d, '.git', onerror='ignore')

    def test_option_md_output_fn(self):

        platform_type = 'zhihu-meta'

        d = 'test/data/{}'.format(platform_type)
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--output-dir", "dst2",
            "--md-output", "specified.md",
            "--repo", "git@gitee.com:drdrxp/bed.git",
            '--keep-meta',
            cwd=d
        )

        #  can not push on CI
        _ = code
        _ = out
        _ = err

        print(out)
        print(err)

        if not is_ci():
            self.assertEqual(0, code)

        cmp_md(self, pjoin(d, 'want/simple.md'), pjoin(d, 'specified.md'))

        rm(d, 'specified.md')
        k3fs.remove(d, 'dst2', onerror='ignore')

    def test_option_md_output_dir(self):

        platform_type = 'zhihu-meta'

        d = 'test/data/{}'.format(platform_type)
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--output-dir", "dst2",
            "--md-output", "foo/",
            "--repo", "git@gitee.com:drdrxp/bed.git",
            '--keep-meta',
            cwd=d
        )

        #  can not push on CI
        _ = code
        _ = out
        _ = err

        print(out)
        print(err)

        if not is_ci():
            self.assertEqual(0, code)

        cmp_md(self, pjoin(d, 'want/simple.md'), pjoin(d, 'foo/simple.md'))

        k3fs.remove(d, 'foo', onerror='ignore')
        k3fs.remove(d, 'dst2', onerror='ignore')

    def test_rules_to_features(self):
        rules = [
            'image:local_to_remote',
            'block_code/:to_jpg',
            'block_code/*:to_jpg',
        ]

        got = md2zhihu.md2zhihu.rules_to_features(rules)
        want = {
            'image': md2zhihu.md2zhihu.save_image_to_asset_dir,
            'block_code': {
                '': md2zhihu.md2zhihu.block_code_to_jpg,
                '*': md2zhihu.md2zhihu.block_code_to_fixwidth_jpg,
            }
        }
        self.assertEqual(want, got)

        #  unknown typ

        rules = ['unknown_typ:local_to_remote', ]

        with self.assertRaisesRegex(KeyError, 'unknown_typ'):
            md2zhihu.md2zhihu.rules_to_features(rules)

        #  unknown info

        rules = ['block_code/unknown_info:to_jpg', ]

        with self.assertRaisesRegex(KeyError, 'unknown_info'):
            md2zhihu.md2zhihu.rules_to_features(rules)

        #  unknown action

        rules = ['block_code/mermaid:to_foo', ]

        with self.assertRaisesRegex(KeyError, 'to_foo'):
            md2zhihu.md2zhihu.rules_to_features(rules)

    def test_zhihu_meta(self):
        self._test_platform('zhihu-meta', ['--keep-meta'])

    def test_zhihu_download(self):
        self._test_platform('zhihu-download', ['--download'])

    def test_zhihu_embed(self):
        self._test_platform('zhihu-embed', ['--embed', '[.]md$'])

    def test_zhihu_extrefs(self):
        self._test_platform('zhihu-extrefs', ['--refs', 'src/refs.yaml'])

    def test_zhihu_img_url(self):
        self._test_platform('zhihu-img-url', [])

    def test_zhihu_rewrite(self):
        self._test_platform_no_push('zhihu-rewrite', 'simple.md', ['--rewrite', '^s', '/foo/'])

    def test_zhihu_math_inline(self):
        self._test_platform_no_push('zhihu-math-inline', 'simple.md', [])

    def test_zhihu_jekyll(self):
        self._test_platform_no_push('zhihu-jekyll', '2021-06-11-simple.md', ['--jekyll'])

    def test_minimal_mistake(self):
        self._test_platform_no_push('minimal_mistake', 'simple.md', [])

    def test_zhihu(self):
        self._test_platform('zhihu', [])

    def test_github(self):
        self._test_platform('github', ['-p', 'github'])

    def test_wechat(self):
        self._test_platform('wechat', ['-p', 'wechat'])

    def test_weibo(self):
        self._test_platform('weibo', ['-p', 'weibo'])

    def test_simple(self):
        self._test_platform('simple', ['-p', 'simple'])

    def test_transparent(self):
        self._test_platform_no_push('transparent', 'transparent.md', ['-p', 'transparent'])

    def _test_platform(self, platform_type, args):

        d = 'test/data/{}'.format(platform_type)
        got_dir = 'dst'
        want_dir = 'want'
        got_asset_dir = 'dst/simple'
        want_asset_dir = 'want/simple'

        k3fs.remove(d, got_dir, onerror="ignore")

        #  do not check error, upload will fail
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--output-dir", "dst",
            "--repo", "git@gitee.com:drdrxp/bed.git@_md2zhihu_foo",
            *args,
            cwd=d
        )

        dd(err)

        #  can not push on CI
        _ = code
        _ = out
        _ = err

        print(out)
        print(err)

        if not is_ci():
            self.assertEqual(0, code)

        cmp_md(self, pjoin(d, want_dir, 'simple.md'), pjoin(d, got_dir, 'simple.md'))
        cmp_all_images(self, pjoin(d, want_asset_dir), pjoin(d, got_asset_dir))

        k3fs.remove(d, got_dir, onerror="ignore")

    def _test_platform_no_push(self, platform_type, fn, args):

        elts = platform_type.split('-', 1)
        platform = elts[0]

        d = 'test/data/{}'.format(platform_type)
        got_dir = 'dst'
        want_dir = 'want'

        # Derive asset directory from filename (remove extension)
        asset_name = fn.rsplit('.', 1)[0]
        got_asset_dir = pjoin('dst', asset_name)
        want_asset_dir = pjoin('want', asset_name)

        k3fs.remove(d, got_dir, onerror="ignore")

        cmdx(
            "md2zhihu",
            'src/' + fn,
            "--output-dir", "dst",
            '--platform', platform, 
            *args,
            cwd=d
        )

        cmp_md(self, pjoin(d, want_dir, fn), pjoin(d, got_dir, fn))
        cmp_all_images(self, pjoin(d, want_asset_dir), pjoin(d, got_asset_dir))

        k3fs.remove(d, got_dir, onerror="ignore")


def cmp_md(t, want_path, got_path):
    got_md = k3fs.fread(got_path)
    want_md = k3fs.fread(want_path)
    want_md = normalize_pandoc_output(want_md, got_md)
    t.assertEqual(want_md.strip(), got_md.strip())


def cmp_all_images(t, want_dir, got_dir):
    contains_all_images(t, want_dir, got_dir)
    contains_all_images(t, got_dir, want_dir)


def contains_all_images(t, want_dir, got_dir):
    want_dir = pabs(want_dir)
    got_dir = pabs(got_dir)

    for img in glob.glob(want_dir + '**/*', recursive=True):

        if img.split('.')[-1] not in ('jpg', 'png'):
            continue

        sub = img[len(want_dir):]
        b = got_dir + sub

        sim = cmp_image(img, b)
        t.assertGreater(sim, 0.68)


def cmp_image(want, got):
    da = skimage.io.imread(want)
    db = skimage.io.imread(got)
    if da.shape != db.shape:
        k3proc.command_ex(
            'convert',
            # height then width
            '-resize', '%dx%d!' % (da.shape[1], da.shape[0]),
            got, got
        )
        db = skimage.io.imread(got)

    img1 = skimage.img_as_float(da)
    img2 = skimage.img_as_float(db)

    print("img1:-------------", want)
    print(img1.shape)
    print("img2:-------------", got)
    print(img2.shape)

    #  print(img1)
    #  print(img2)

    # shape is in form: (170, 270, 4): 4 channels
    #              or:  (170, 270):    1 channel

    if len(img1.shape) == 2:
        p = structural_similarity(img1, img2, data_range=1)
    else:
        # channel_axis=2 specifies img.shape[2] specifies the number of channels
        p = structural_similarity(img1, img2, channel_axis=2, data_range=1)

    print("p:", p)

    return p


def make_remote_git(*p):
    p = os.path.join(*p)
    os.makedirs(p, exist_ok=True)

    cmdx('git', 'init', '--bare', p)


def make_init_git(p, remotes):
    """
    Init a git work tree in path ``p``. Add remotes specified in ``remotes``.
    Commit an empty commit.
    """

    k3fs.remove(p, ".git", onerror='ignore')

    cmdx('git', 'init', p)
    cmdx('git',
         '-c', "user.name='drmingdrmer'",
         '-c', "user.email='drdr.xp@gmail.com'",
         'commit', '--allow-empty', '-m', "init", cwd=p)

    for name, url in remotes.items():
        #  If it is a local url, create it.
        try:
            k3git.GitUrl.parse(url)
        except ValueError:
            make_remote_git(url)

        cmdx('git', 'remote', 'add', name, url, cwd=p)


def normalize_pandoc_output(want, got):
    #  pandoc may output different style html:
    #  '<tab[25 chars]n<th style="text-align: left;">a</th>\n<th sty[427 chars]ble>' !=
    #  '<tab[25 chars]n<th align="left">a</th>\n<th align="right">b<[310 chars]ble>'

    if 'align="' in got:
        want = re.sub(r'style="text-align: (left|right|center);"',
                      r'align="\1"', want)
    return want


def rm(*p):
    k3fs.remove(*p, onerror="ignore")


def is_ci():
    # github ci
    return os.environ.get('CI') is not None


def get_testing_repo_url():
    if is_ci():
        c = os.environ.get('MD2TEST_USERNAME')
        t = os.environ.get('MD2TEST_TOKEN')
        #  use https on github action, it will be filled with token by k3git.GitUrl.parse
        return "https://{c}:{t}@github.com/drmingdrmer/md2test.git".format(c=c, t=t)
    else:
        # use ssh when testing on my laptop.
        return "git@github.com:drmingdrmer/md2test.git"
