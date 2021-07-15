#!/bin/sh

pip uninstall -y md2zhihu

cp setup.py ..
(
cd ..
python setup.py install
)

# PYTHONPATH="$(cd ..; pwd)" pytest -x -v
PYTHONPATH="$(cd ..; pwd)" pytest -x -v -k test_zhihu_abspath
