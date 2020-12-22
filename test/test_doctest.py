import doctest

import tmpl


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(tmpl))
    return tests
