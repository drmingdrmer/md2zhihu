#!/usr/bin/env python
# coding: utf-8

import doctest
import imp
import os
import sys

import jinja2
import yaml

# xxx/_building/build_readme.py
this_base = os.path.dirname(__file__)

j2vars = {}

# let it be able to find indirectly dependent package locally
# e.g.: `k3fs` depends on `k3confloader`
sys.path.insert(0, os.path.abspath('..'))

# load package name from __init__.py
pkg = imp.load_source("_foo", '__init__.py')
j2vars["name"] = pkg.__name__


def get_gh_config():
    with open('.github/settings.yml', 'r') as f:
        cont = f.read()

    cfg = yaml.safe_load(cont)
    tags = cfg['repository']['topics'].split(',')
    tags = [x.strip() for x in tags]
    cfg['repository']['topics'] = tags
    return cfg


cfg = get_gh_config()
j2vars['description'] = cfg['repository']['description']


def get_examples(pkg):
    doc = pkg.__doc__
    parser = doctest.DocTestParser()
    es = parser.get_examples(doc)
    rst = []
    for e in es:
        rst.append('>>> ' + e.source.strip())
        rst.append(e.want.strip())

    rst = '\n'.join(rst)

    for fn in ("synopsis.txt",
               "synopsis.py",
               ):
        try:
            with open(fn, 'r') as f:
                rst += '\n' + f.read()

        except FileNotFoundError:
            pass

    return rst


j2vars['synopsis'] = get_examples(pkg)
j2vars['package_doc'] = pkg.__doc__


def render_j2(tmpl_path, tmpl_vars, output_path):
    template_loader = jinja2.FileSystemLoader(searchpath='./')
    template_env = jinja2.Environment(loader=template_loader,
                                      undefined=jinja2.StrictUndefined)
    template = template_env.get_template(tmpl_path)

    txt = template.render(tmpl_vars)

    with open(output_path, 'w') as f:
        f.write(txt)


if __name__ == "__main__":
    render_j2('_building/README.md.j2',
              j2vars,
              'README.md')
