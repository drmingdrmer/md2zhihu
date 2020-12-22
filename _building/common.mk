all: test readme doc

.PHONY: test
test:
	sudo env "PATH=$$PATH" UT_DEBUG=0 PYTHONPATH="$$(cd ..; pwd)" python -m unittest discover -c --failfast -s .

doc:
	make -C docs html

readme:
	python _building/build_readme.py

release:
	PYTHONPATH="$$(cd ..; pwd)" python _building/build_setup.py
