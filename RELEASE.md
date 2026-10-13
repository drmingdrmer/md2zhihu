# Releasing md2zhihu

A release is one commit that sets the version in `pyproject.toml`, a tag
`v<version>` on that commit, and a GitHub release for the tag. Pushing the tag
starts two workflows:

- `Upload Python Package` builds the package and uploads it to
  [PyPI](https://pypi.org/project/md2zhihu/). It logs in with the repo secret
  `PYPI_PASSWORD`, which holds a PyPI API token.
- `Publish Docker image` builds the image for amd64 and arm64, and pushes it as
  `ghcr.io/drmingdrmer/md2zhihu:v<version>` and
  `ghcr.io/drmingdrmer/md2zhihu:latest`.

The GitHub Action pulls `ghcr.io/drmingdrmer/md2zhihu:latest` before each run,
unless its input `image` names another image. So every workflow that uses the
action runs the new release as soon as `Publish Docker image` finishes.

## Release steps, with 0.19 after 0.18 as the example

1. Set `version` in `pyproject.toml` to `0.19`. No other file holds the version.

2. Commit the change. The commit message is the release note, because the repo
   keeps no changelog:

   ```text
   chore: packaging: set the version to 0.19

   # Summary

   The tag v0.19 on this commit releases 0.19 to PyPI and as the images
   `ghcr.io/drmingdrmer/md2zhihu:v0.19` and `:latest`. <What 0.19 adds.>

   # Details

   <The commits since v0.18 that start with `change:`, and what a user
   changes to upgrade.>
   ```

   A commit that changes behavior that a script or a workflow may rely on
   starts with `change:`, and ends with an upgrade tip. This command lists them:

   ```sh
   git log --grep '^change:' v0.18..HEAD
   ```

   Commit with `git commit -F <file>`. An editor removes the lines that start
   with `#`, such as `# Summary`.

3. Push the commit to the branch `ci`, and wait until the workflow `unit_test`
   passes on it. `ci` is a scratch branch for testing a commit before `main`
   receives it:

   ```sh
   git push --force origin HEAD:ci
   ```

4. Push the same commit to `main`:

   ```sh
   git push origin HEAD:main
   ```

5. Tag the commit and push the tag. The push starts the two release workflows:

   ```sh
   git tag v0.19
   git push origin v0.19
   ```

6. Wait until `Upload Python Package` and `Publish Docker image` pass on
   `v0.19`. This command shows the runs of the tag:

   ```sh
   gh run list --repo drmingdrmer/md2zhihu --branch v0.19
   ```

   Then check what the two workflows published:

   ```sh
   # Lists 0.19 as the newest version.
   pip index versions md2zhihu

   # Each lists linux/amd64 and linux/arm64, and both print the same Digest.
   docker buildx imagetools inspect ghcr.io/drmingdrmer/md2zhihu:v0.19
   docker buildx imagetools inspect ghcr.io/drmingdrmer/md2zhihu:latest
   ```

7. Create a GitHub release for the tag, with the body of the version commit as
   its notes. GitHub shows every line break in release notes, so `pandoc` first
   joins the wrapped lines of each paragraph:

   ```sh
   git log -1 --format=%b v0.19 | pandoc -f gfm -t gfm --wrap=none -o notes.md
   gh release create v0.19 --title v0.19 --notes-file notes.md --verify-tag
   ```

   GitHub Marketplace offers the latest GitHub release, so its button "Use
   latest version" gives `uses: drmingdrmer/md2zhihu@v0.19`.

## A failed release workflow: rerun it, or release the next version

Read the log of the failed jobs:

```sh
gh run view <run-id> --repo drmingdrmer/md2zhihu --log-failed
```

If an outside service failed, such as the network or PyPI, rerun the failed
jobs:

```sh
gh run rerun <run-id> --repo drmingdrmer/md2zhihu --failed
```

If the code is wrong, fix it and release the next version, such as 0.20. PyPI
and ghcr.io may already hold the broken 0.19, and PyPI rejects a second upload
of 0.19.
