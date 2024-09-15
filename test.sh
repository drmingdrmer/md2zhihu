#!/bin/sh

pip uninstall -y md2zhihu

cp setup.py ..
(
cd ..
python setup.py install
)

# PYTHONPATH="$(cd ..; pwd)" pytest -x -v
# PYTHONPATH="$(cd ..; pwd)" pytest -x -v -k test_simple
PYTHONPATH="$(cd ..; pwd)" pytest -x -v --show-capture=all -k test_minimal_mistake
