import os
import re
import unittest

import md2zhihu
import k3proc
import k3ut
import skimage
import skimage.io
from skimage.metrics import structural_similarity as ssim


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
            self.assertEqual('_md2zhihu', a.branch)
            self.assertEqual('github.com', a.host)
            self.assertEqual('drmingdrmer', a.user)
            self.assertEqual('home', a.repo)
            self.assertEqual('https://raw.githubusercontent.com/drmingdrmer/home/_md2zhihu/{path}', a.path_pattern)

        # specify branch

        url = 'git@github.com:drmingdrmer/home.git@abc'
        a = md2zhihu.AssetRepo(url, cdn=False)
        self.assertEqual(False, a.cdn)
        self.assertEqual('abc', a.branch)
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)
        self.assertEqual('https://raw.githubusercontent.com/drmingdrmer/home/abc/{path}', a.path_pattern)

        #  with cdn

        a = md2zhihu.AssetRepo('git@github.com:drmingdrmer/home.git')
        self.assertEqual(True, a.cdn)
        self.assertEqual('_md2zhihu', a.branch)
        self.assertEqual('github.com', a.host)
        self.assertEqual('drmingdrmer', a.user)
        self.assertEqual('home', a.repo)
        self.assertEqual('https://cdn.jsdelivr.net/gh/drmingdrmer/home@_md2zhihu/{path}', a.path_pattern)

    def test_option_output(self):

        platform_type = 'zhihu-meta'
        segs = platform_type.split('-') + ['']
        platform = segs[0]

        d = 'test/data/{}'.format(platform_type)
        code, out, err = k3proc.command(
                "md2zhihu",
                "src/simple.md",
                "-d", "dst2",
                "-o", "specified.md",
                "-r", "git@gitee.com:drdrxp/bed.git",
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
        wantmd = fread(d, wantdir, 'simple.md')
        wantmd = normalize_pandoc_output(wantmd, gotmd)
        self.assertEqual(wantmd.strip(), gotmd.strip())

        rm(d, 'specified.md')


    def test_md2zhihu(self):
        for platform_type, args in (
                ('zhihu', []),
                ('zhihu-meta', ['--keep-meta']),
                ('wechat', ['-p', 'wechat']),
        ):

            segs = platform_type.split('-') + ['']
            platform = segs[0]
            typ = segs[1]

            d = 'test/data/{}'.format(platform_type)
            code, out, err = k3proc.command(
                    "md2zhihu",
                    "src/simple.md",
                    "-d", "dst",
                    "-r", "git@gitee.com:drdrxp/bed.git",
                    *args,
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

            gotdir = 'dst/{}/simple'.format(platform)
            wantdir = 'want/{}/simple'.format(platform)


            gotmd = fread(d, gotdir, 'simple.md')
            wantmd = fread(d, wantdir, 'simple.md')
            wantmd = normalize_pandoc_output(wantmd, gotmd)
            self.assertEqual(wantmd.strip(), gotmd.strip())

            for img in os.listdir(pjoin(d, wantdir)):
                if img.split('.')[-1] not in ('jpg', 'png'):
                    continue
                sim = cmp_image(pjoin(d, wantdir, img),
                                pjoin(d, gotdir, img))
                self.assertGreater(sim, 0.8)

            for img in os.listdir(pjoin(d, gotdir)):
                if img.split('.')[-1] not in ('jpg', 'png'):
                    continue
                sim = cmp_image(pjoin(d, wantdir, img),
                                pjoin(d, gotdir, img))
                self.assertGreater(sim, 0.8)


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
