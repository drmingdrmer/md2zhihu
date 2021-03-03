#!/bin/sh

npm install @mermaid-js/mermaid-cli@8.8.4
sudo apt-get install pandoc

pip install setuptools wheel
cp md2zhihu/setup.py .
python setup.py sdist bdist_wheel
pip install dist/*.tar.gz
