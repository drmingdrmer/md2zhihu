# These targets always run, though the folder "test" exists.
.PHONY: lint test

lint:
	ruff format
	ruff check --fix

test:
	pytest
