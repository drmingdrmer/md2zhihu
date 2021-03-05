#!/usr/bin/env python
# coding: utf-8

import yaml

with open("action.yml", 'r') as f:
    cont = f.read()

y = yaml.load(cont)

with open("action-doc.md", 'w') as f:

    for k, v in y['inputs'].items():
        f.write("-   `{k}`:".format(k=k))
        f.write("\n")
        f.write("\n")
        f.write("    {description}\n".format(description=v['description'].strip()))
        f.write("\n")
        f.write("    **required**: {required}\n    **default**: `{default}`".format(**v))
        f.write("\n")
        f.write("\n")
