import os
import re
import unittest

import k3proc
import k3ut
import k3fs
import skimage
import skimage.io
from skimage.metrics import structural_similarity as ssim

import md2zhihu

dd = k3ut.dd

this_base = os.path.dirname(__file__)


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
                'https://raw.githubusercontent.com/drmingdrmer/home/'+b+'/{path}', a.path_pattern)

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
            'https://cdn.jsdelivr.net/gh/drmingdrmer/home@'+b+'/{path}', a.path_pattern)

        # https url with token

        a = md2zhihu.AssetRepo('https://aa:bb@github.com/drmingdrmer/home.git')
        self.assertEqual(True, a.cdn)
        self.assertEqual('https://aa:bb@github.com/drmingdrmer/home.git', a.url)
        self.assertRegex(a.branch, '_md2zhihu_md2zhihu_[a-z0-9]{8}')
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)

    def test_option_md_output_fn(self):

        platform_type = 'zhihu-meta'
        segs = platform_type.split('-') + ['']
        platform = segs[0]

        d = 'test/data/{}'.format(platform_type)
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--asset-dir", "dst2",
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

        wantdir = 'want/{}/simple'.format(platform)

        gotmd = fread(d, 'specified.md')
        wantmd = fread(d, 'want/simple.md')
        wantmd = normalize_pandoc_output(wantmd, gotmd)
        self.assertEqual(wantmd.strip(), gotmd.strip())

        rm(d, 'specified.md')
        k3fs.remove(d, 'dst2', onerror='ignore')

    def test_option_md_output_dir(self):

        platform_type = 'zhihu-meta'
        segs = platform_type.split('-') + ['']
        platform = segs[0]

        d = 'test/data/{}'.format(platform_type)
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--asset-dir", "dst2",
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

        wantdir = 'want/{}/simple'.format(platform)

        gotmd = fread(d, 'foo/simple.md')
        wantmd = fread(d, 'want/simple.md')
        wantmd = normalize_pandoc_output(wantmd, gotmd)
        self.assertEqual(wantmd.strip(), gotmd.strip())

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
                        '*':md2zhihu.md2zhihu.block_code_to_fixwidth_jpg, 
                }
        }
        self.assertEqual(want, got)

        #  unknown typ

        rules = [ 'unknown_typ:local_to_remote', ]

        with self.assertRaisesRegex(KeyError, 'unknown_typ'):
            md2zhihu.md2zhihu.rules_to_features(rules)

        #  unknown info

        rules = [ 'block_code/unknown_info:to_jpg', ]

        with self.assertRaisesRegex(KeyError, 'unknown_info'):
            md2zhihu.md2zhihu.rules_to_features(rules)

        #  unknown action

        rules = [ 'block_code/mermaid:to_foo', ]

        with self.assertRaisesRegex(KeyError, 'to_foo'):
            md2zhihu.md2zhihu.rules_to_features(rules)

    def test_zhihu_meta(self): self._test_platform('zhihu-meta', ['--keep-meta'])
    def test_zhihu(self):      self._test_platform('zhihu', [])
    def test_wechat(self):     self._test_platform('wechat', ['-p', 'wechat'])
    def test_weibo(self):      self._test_platform('weibo', ['-p', 'weibo'])
    def test_simple(self):     self._test_platform('simple', ['-p', 'simple'])

    def _test_platform(self, platform_type, args):

        segs = platform_type.split('-') + ['']
        platform = segs[0]

        d = 'test/data/{}'.format(platform_type)
        gotdir = 'dst'
        wantdir = 'want'
        gotassdir = 'dst/{}/simple'.format(platform)
        wantassdir = 'want/{}/simple'.format(platform)

        k3fs.remove(d, gotdir, onerror="ignore")

        #  do not check error, upload will fail
        code, out, err = k3proc.command(
            "md2zhihu",
            "src/simple.md",
            "--asset-dir", "dst",
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


        gotmd = fread(d, gotdir, 'simple.md')
        wantmd = fread(d, wantdir, 'simple.md')
        wantmd = normalize_pandoc_output(wantmd, gotmd)
        self.assertEqual(wantmd.strip(), gotmd.strip())

        for img in os.listdir(pjoin(d, wantassdir)):
            if img.split('.')[-1] not in ('jpg', 'png'):
                continue
            sim = cmp_image(pjoin(d, wantassdir, img),
                            pjoin(d, gotassdir, img))
            self.assertGreater(sim, 0.7)

        for img in os.listdir(pjoin(d, gotassdir)):
            if img.split('.')[-1] not in ('jpg', 'png'):
                continue
            sim = cmp_image(pjoin(d, wantassdir, img),
                            pjoin(d, gotassdir, img))
            self.assertGreater(sim, 0.7)

        k3fs.remove(d, gotdir, onerror="ignore")


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

    p = ssim(img1, img2, multichannel=True)
    return p


def normalize_pandoc_output(want, got):
    #  pandoc may output different style html:
    #  '<tab[25 chars]n<th style="text-align: left;">a</th>\n<th sty[427 chars]ble>' !=
    #  '<tab[25 chars]n<th align="left">a</th>\n<th align="right">b<[310 chars]ble>'

    if 'align="' in got:
        want = re.sub(r'style="text-align: (left|right|center);"',
                      r'align="\1"', want)
    return want


def pjoin(*p):
    return os.path.join(*p)


def rm(*p):

    try:
        os.unlink(os.path.join(*p))
    except OSError:
        pass


def fwrite(*p):
    cont = p[-1]
    p = p[:-1]
    with open(os.path.join(*p), 'wb') as f:
        f.write(cont)


def fread(*p):
    with open(os.path.join(*p), 'r') as f:
        return f.read()


def is_ci():
    # github ci
    return os.environ.get('CI') is not None
