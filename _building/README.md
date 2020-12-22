# building
building toolkit for pykit3 repos

This repo should be included in a package, e.g.:

```
vcs/pykit3/k3handy/
▸ .git/
▸ .github/
▸ __pycache__/
▾ _building/ <-- this repo
     ...
```

# Publish python package:

- `make release` does the following steps:
    - Builds the `setup.py` and commit it.
    - Add a git tag with the name of `"v" + __init__.__ver__`.

- Then `git push` the tag, github Action in the `.github/workflows/python-pubish.yml` will publish a package to `pypi`.

    The action spec is copied from template repo: `github.com/pykit3/tmpl`.
