include _building/common.mk

lint:
	ruff format
	ruff check --fix
