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
            'image': md2zhihu.md2zhihu.image_local_to_remote,
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


    def test_wechat(self):
        self._test_platform('wechat', ['-p', 'wechat'])

    def test_weibo(self):
        self._test_platform('weibo', ['-p', 'weibo'])

    def test_simple(self):
        self._test_platform('simple', ['-p', 'simple'])

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
        got_asset_dir = 'dst/simple'
        want_asset_dir = 'want/simple'

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
        t.assertGreater(sim, 0.7)


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

    p = structural_similarity(img1, img2, multichannel=True)
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
