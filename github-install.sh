#!/bin/sh

npm install @mermaid-js/mermaid-cli@8.8.4
sudo apt-get install pandoc

pip3 install setuptools wheel
cp md2zhihu/setup.py .
python3 setup.py sdist bdist_wheel
pip3 install dist/*.tar.gz
