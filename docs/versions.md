# Versions

Liz4270's firmware is numbered by [semantic versioning](https://semver.org), `MAJOR.MINOR.PATCH`, from 0.6.0 (#132).

## Where the number lives

`project(liz4270 VERSION X.Y.Z ...)` in `firmware/CMakeLists.txt`. It changes only in a release's own pull request; feature work leaves it alone.

## What a build calls itself

Every build works out its name as it builds (`firmware/version.cmake`), so a new commit needs no reconfigure.

| The build | Version | Commit |
| --- | --- | --- |
| At the annotated tag `vX.Y.Z`, from a clean tree | `X.Y.Z` | the hash |
| Anything else: past the tag, from an edited tree, before any tag, without git or a repository of its own | `X.Y.Z+dev` | the hash, with `-dirty` from an edited tree, or `unknown` |

`+dev` is semver's build metadata: the build is no other release, and its commit says which build it is.

An edited tree is one with a tracked file changed, or with a file git neither tracks nor ignores, anywhere in it: the build reads whatever is there, such as a `CMakeUserPresets.json`. An empty directory isn't an edit.

Only annotated tags whose names match `v[0-9]*` count. A build from a clean tree at such a tag that isn't `v` + `project()`'s number stops with an error, naming both. From an edited tree it reads `X.Y.Z+dev` instead, so a release's pull request can set the new number while HEAD still carries the last release's tag.

The splash, the console's banner, `picotool info -a` and SetUp's About page (F10 on the Online Setup menu) all show the version and the commit.

## When the numbers go up

- **Patch:** fixes only.
- **Minor:** anything new that a user, a builder or the controller can see: a feature, a SetUp screen, a board revision.
- **Major,** from 1.0.0 on: an update that costs the builder something, such as saved settings lost, a board revision dropped, or something a controller relied on changed.

**1.0.0** is v1 proven and tested, feature-complete for the scope set for 1.0.0. That scope is ours to set, and it can grow before the release.

## Releasing

1. A pull request sets `project()` to the new number, with anything else the release needs.
2. Once it merges, tag its merge commit and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "Liz4270 X.Y.Z" MERGE_COMMIT
   git push origin vX.Y.Z
   ```

3. A build at the tag, from a clean checkout, reads `X.Y.Z`.
