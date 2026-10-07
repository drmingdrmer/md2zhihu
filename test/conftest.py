import logging

import pytest


@pytest.fixture
def restore_root_logger():
    # md2zhihu.main() adds a stdout handler to the root logger on each call.
    handlers = list(logging.root.handlers)
    level = logging.root.level
    yield
    logging.root.handlers = handlers
    logging.root.setLevel(level)
