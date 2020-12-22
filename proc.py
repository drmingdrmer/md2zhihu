#!/usr/bin/env python
# coding: utf-8

import logging
import sys

logger = logging.getLogger(__name__)

defenc = None

if hasattr(sys, 'getfilesystemencoding'):
    defenc = sys.getfilesystemencoding()

if defenc is None:
    defenc = sys.getdefaultencoding()

class SomeError(Exception):
    pass

def foo():
    pass
