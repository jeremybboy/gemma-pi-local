# Release procedure

`VERSION` is the canonical release number. A release pull request must update
that file, `CHANGELOG.md`, and the matching file under `docs/releases/`.

After the pull request is reviewed and merged into `main`, the maintainer runs:

```bash
git switch main
git pull --ff-only
git tag -a "v$(cat VERSION)" -m "Gemma Pi Local v$(cat VERSION)"
git push origin "v$(cat VERSION)"
```

The tag must point to `main`. The release workflow rejects a tag that does not
equal `v` plus the contents of `VERSION`, then publishes the prepared release
notes when available. Creating a tag from an unmerged pull-request branch is
not an acceptable release.
