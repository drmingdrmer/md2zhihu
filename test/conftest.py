import logging

import pytest


@pytest.fixture
def restore_logger():
    # md2zhihu.main() adds a stderr handler to the "md2zhihu" logger on each call, and sets its level.
    logger = logging.getLogger("md2zhihu")
    handlers = list(logger.handlers)
    level = logger.level
    yield
    logger.handlers = handlers
    logger.setLevel(level)
