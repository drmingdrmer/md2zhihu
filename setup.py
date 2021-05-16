#!/usr/bin/env python
# coding: utf-8

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
    description='convert markdown to zhihu compatible format. https://github.com/drmingdrmer/md2zhihu',
    long_description='See: https://github.com/drmingdrmer/md2zhihu',
    long_description_content_type="text/markdown",
    author='Zhang Yanpo',
    author_email='drdr.xp@gmail.com',
    url='https://github.com/drmingdrmer/md2zhihu',
    keywords=['python', 'markdown', 'zhihu'],
    python_requires='>=3.0',

    entry_points = {
        'console_scripts': [
            'md2zhihu = md2zhihu:main',
        ],
    },

    install_requires=[
        'PyYAML>=5.3.1',
        'k3color>=0.1.2',
        'k3down2>=0.1.15',
        'k3fs>=0.1.5',
        'k3git>=0.1.6',
        'k3handy>=0.1.5',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
    ] + ['Programming Language :: Python :: 3'],
)
