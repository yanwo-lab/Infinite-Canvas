# Yanwo release process

This document defines the Yanwo release version for this fork. It is separate
from the upstream `VERSION` file maintained by `hero8152/Infinite-Canvas`.

## Version identities

Every production release records four distinct identities:

- **Yanwo release version:** the SemVer release tag, for example `v1.0.0`.
- **Git revision:** the exact release commit, for example `a20833d`.
- **Docker image tags:** the immutable release and revision tags plus `latest`.
- **Upstream version:** the contents of the repository's `VERSION` file; Yanwo
  releases do not modify it.

The first stable Yanwo release is:

- Yanwo release: `v1.0.0`
- Git revision: `a20833d61b7a86dc8b189d3d6dad306d5c800ff9`
- Docker image: `local/infinite-canvas:v1.0.0`
- Upstream `VERSION`: unchanged (`2026.08.04` at release time)

## Release checklist

For every stable `vX.Y.Z` release:

1. Confirm `main` is clean and synchronized with `origin/main`.
2. Complete the production acceptance matrix and select the exact release
   commit.
3. Create an annotated Git tag `vX.Y.Z` at that commit and push the tag to
   `origin`. Never move or replace an existing release tag.
4. Build or select one validated Docker image for the release.
5. Give that exact image all three local tags:

   ```text
   local/infinite-canvas:vX.Y.Z
   local/infinite-canvas:latest
   local/infinite-canvas:<short-sha>
   ```

6. Verify all three tags resolve to the same Docker image ID before deployment.
7. Treat `vX.Y.Z` and `<short-sha>` as immutable. Never retarget either tag to
   another image.
8. Move `latest` only when a newer stable release has passed acceptance.
9. Pin production Compose to `local/infinite-canvas:vX.Y.Z`; production must
   never run the floating `latest` tag.
10. Recreate production with `--no-build`, then verify health, HTTP, plugins,
    persistent mounts, WebSocket ping/pong, Nginx, and the public domain.
11. Roll back by pinning Compose to a previously retained `vX.Y.Z` image rather
    than rebuilding old source.
12. Do not change upstream `VERSION` as part of a Yanwo release.

## Semantic versioning

Yanwo releases follow SemVer:

- **patch:** backward-compatible bug fixes;
- **minor:** backward-compatible new capabilities;
- **major:** incompatible behavior, data, API, or deployment changes.

## Verification commands

Use the exact release values in place of the examples below:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git rev-parse 'vX.Y.Z^{}'
git ls-remote --tags origin 'refs/tags/vX.Y.Z' 'refs/tags/vX.Y.Z^{}'

docker image inspect \
  local/infinite-canvas:vX.Y.Z \
  local/infinite-canvas:latest \
  local/infinite-canvas:<short-sha> \
  --format '{{.Id}} {{json .RepoTags}}'
```

Keep the prior versioned image, production configuration, persistent data, and
Nginx rollback configuration until the new release has completed its rollback
retention period.
