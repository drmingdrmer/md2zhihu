#!/usr/bin/env python
# coding: utf-8

import textwrap

import yaml

with open("action.yml", "r") as f:
    cont = f.read()

y = yaml.safe_load(cont)

with open("action-doc.md", "w") as f:
    for i, (k, v) in enumerate(y["inputs"].items()):
        # A blank line between items, but none after the last one.
        if i > 0:
            f.write("\n")
        f.write("-   `{k}`:".format(k=k))
        f.write("\n")
        f.write("\n")
        f.write(textwrap.indent(v["description"].strip(), "    ") + "\n")
        f.write("\n")
        f.write("    **required**: {required}\n    **default**: `{default}`".format(**v))
        f.write("\n")
