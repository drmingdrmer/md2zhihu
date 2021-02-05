#!/bin/sh

pip uninstall -y md2zhihu

cp setup.py ..
(
cd ..
rm dist/*
python setup.py sdist bdist_wheel
pip install dist/*.tar.gz
)

PYTHONPATH="$(cd ..; pwd)" pytest -x
