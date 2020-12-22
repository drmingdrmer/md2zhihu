#!/usr/bin/env python
# coding: utf-8

"""
build steup.py for this package.
"""

from string import Template
import subprocess
import sys
import imp

import yaml
import requirements

if hasattr(sys, 'getfilesystemencoding'):
    defenc = sys.getfilesystemencoding()
if defenc is None:
    defenc = sys.getdefaultencoding()


pseudo = "pseudo"


def get_name():
    pkg = imp.load_source(pseudo, '__init__.py')
    name = pkg.__name__
    return name


name = get_name()


def get_ver():
    pkg = imp.load_source(pseudo, '__init__.py')
    pkgver = pkg.__version__

    return pkgver


def get_gh_config():
    with open('.github/settings.yml', 'r') as f:
        cont = f.read()

    cfg = yaml.load(cont)
    tags = cfg['repository']['topics'].split(',')
    tags = [x.strip() for x in tags]
    cfg['repository']['topics'] = tags
    return cfg


def get_travis():
    try:
        with open('.travis.yml', 'r') as f:
            cont = f.read()
    except OSError:
        return None

    cfg = yaml.load(cont)
    return cfg


def get_compatible():

    # https://pypi.org/classifiers/

    rst = []
    t = get_travis()
    if t is None:
        return ["Programming Language :: Python :: 3"]

    for v in t['python']:
        if v.startswith('pypy'):
            v = "Implementation :: PyPy"
        rst.append("Programming Language :: Python :: {}".format(v))

    return rst


def get_req():
    try:
        with open('requirements.txt', 'r') as f:
            req = list(requirements.parse(f))
    except OSError:
        req = []

    # req.name, req.specs, req.extras
    # Django [('>=', '1.11'), ('<', '1.12')]
    # six [('==', '1.10.0')]
    req = [x.name + ','.join([a + b for a, b in x.specs])
           for x in req
           ]

    return req


cfg = get_gh_config()

ver = get_ver()
description = cfg['repository']['description']
long_description = open('README.md').read()
req = get_req()
prog = get_compatible()


tmpl = '''# DO NOT EDIT!!! built with `python _building/build_setup.py`
import setuptools
setuptools.setup(
    name="${name}",
    packages=["${name}"],
    version="$ver",
    license='MIT',
    description=$description,
    long_description=$long_description,
    long_description_content_type="text/markdown",
    author='Zhang Yanpo',
    author_email='drdr.xp@gmail.com',
    url='https://github.com/pykit3/$name',
    keywords=$topics,
    python_requires='>=3.0',

    install_requires=$req,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
    ] + $prog,
)
'''

s = Template(tmpl)
rst = s.substitute(
    name=name,
    ver=ver,
    description=repr(description),
    long_description=repr(long_description),
    topics=repr(cfg['repository']['topics']),
    req=repr(req),
    prog=repr(prog)
)
with open('setup.py', 'w') as f:
    f.write(rst)


sb = subprocess.Popen(["git", "add", "setup.py"],
                      encoding=defenc,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = sb.communicate()
if sb.returncode != 0:
    raise Exception("failure to add: ", out, err)

sb = subprocess.Popen(["git", "commit", "setup.py", "-m", "release: v" + ver],
                      encoding=defenc,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = sb.communicate()
if sb.returncode != 0:
    raise Exception("failure to commit new release: " + ver, out, err)


sb = subprocess.Popen(["git", "tag", "v" + ver],
                      encoding=defenc,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = sb.communicate()
if sb.returncode != 0:
    raise Exception("failure to add tag: " + ver, out, err)
