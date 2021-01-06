#!/bin/sh

cp setup.py ..
(
cd ..
python setup.py sdist bdist_wheel
pip install dist/*.tar.gz
)

PYTHONPATH="$(cd ..; pwd)" pytest
