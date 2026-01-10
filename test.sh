#!/bin/sh

pip uninstall -y md2zhihu
pip install -e ".[test]"

# PYTHONPATH="$(cd ..; pwd)" pytest -x -v
# PYTHONPATH="$(cd ..; pwd)" pytest -x -v -k test_simple
# PYTHONPATH="$(cd ..; pwd)" pytest -x -v --show-capture=all -k test_minimal_mistake
# PYTHONPATH="$(cd ..; pwd)" pytest -x -v --show-capture=all -k test_weibo
PYTHONPATH="$(cd ..; pwd)" pytest -x -v --show-capture=all -k test_chunks
# PYTHONPATH="$(cd ..; pwd)" pytest -x -v --show-capture=all -k test_chunks_list
