import unittest
from . import translate
from . import fnmap

class TestFnMap(unittest.TestCase):
    def test_translate(self):
        pass
        self.assertEqual(r'(?s:(foo/)((?:[^/\\]|\\/|\\\\)*?)(\.md))\Z', translate(r'foo/*.md'))
        self.assertEqual(r'(?s:(foo/)(.*?)(/)((?:[^/\\]|\\/|\\\\)*?)(\.md))\Z', translate(r'foo/**/*.md'))
        self.assertEqual(r'(?s:(foo/)(.*?)(/d/)((?:[^/\\]|\\/|\\\\)*?)(\.md))\Z', translate(r'foo/**/d/*.md'))

    def test_fnmap(self):

        src = r'foo/x/y/z/d/bar.md'

        self.assertEqual(r'bar/x/y/z/d/bar.cn.md', fnmap(src, r'foo/**/*.md', r'bar/**/*.cn.md'))
        self.assertEqual(r'bar/x/y/z/d/bar.cn.md', fnmap(src, r'foo/**/d/*.md', r'bar/**/d/*.cn.md'))
        self.assertEqual(r'bar/x/y/z/d/f/bar.cn.md', fnmap(src, r'foo/**/*.md', r'bar/**/f/*.cn.md'))
