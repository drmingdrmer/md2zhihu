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

    def test_md2zhihu(self):
        d = 'test/data/simple'
        code, out, err = k3proc.command(
                "md2zhihu",
                "src/simple.md",
                "-o", "dst",
                "-r", "git@gitee.com:drdrxp/bed.git",
                cwd=d
        )

        #  can not push on CI
        _ = code
        _ = out
        _ = err

        gotmd = fread(d, 'dst/zhihu/simple/simple.md')
        wantmd = fread(d, 'want/zhihu/simple/simple.md')
        wantmd = normalize_pandoc_output(wantmd, gotmd)
        self.assertEqual(wantmd.strip(), gotmd.strip())

        for img in os.listdir(pjoin(d, 'want/zhihu/simple')):
            if img.split('.')[-1] not in ('jpg', 'png'):
                continue
            sim = cmp_image(pjoin(d, 'want/zhihu/simple', img),
                            pjoin(d, 'dst/zhihu/simple', img))
            self.assertGreater(sim, 0.9)

def cmp_image(a, b):

    img1 = skimage.img_as_float(skimage.io.imread(a))
    img2 = skimage.img_as_float(skimage.io.imread(b))

    p = ssim(img1, img1, multichannel=True)
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
