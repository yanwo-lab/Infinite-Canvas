# Yanwo release process

This document defines Yanwo releases for this fork. It does not change the
upstream `VERSION` file maintained by `hero8152/Infinite-Canvas`; upstream
`VERSION` and Yanwo release versions are independent.

## Release identities

Record these four identities for every release:

- **Upstream `VERSION`:** the upstream application version; do not modify it
  for a Yanwo release.
- **Yanwo SemVer:** the immutable GitHub Release tag, for example `vX.Y.Z`.
- **Full Git revision:** the exact 40-character commit SHA, with its immutable
  short SHA image tag.
- **GHCR image:** the `ghcr.io/yanwo-lab/infinite-canvas` version tag, short
  SHA tag, and multi-architecture manifest digest.

The preserved v1.0.0 history is:

- Yanwo release: `v1.0.0`
- Git revision: `a20833d61b7a86dc8b189d3d6dad306d5c800ff9`
- Docker image at the time: `local/infinite-canvas:v1.0.0`
- Upstream `VERSION`: unchanged (`2026.08.04` at release time)

## Stable GitHub Release workflow

For each stable `vX.Y.Z` release:

1. Complete acceptance on the exact commit, confirm `main` is synchronized,
   then create and push an annotated, never-moved tag named exactly `vX.Y.Z`.
2. Create and publish the GitHub Release from that exact tag. Draft and
   prerelease releases do not publish container images.
3. The release workflow checks out the release tag and performs one GHCR
   multiarch Buildx build for `linux/amd64,linux/arm64`. That one manifest is
   tagged `vX.Y.Z`, the release short SHA, and `latest`.
4. Version tags and short SHA tags are immutable. Move `latest` only for a
   stable published release; no branch push may publish or move it.
5. Record the full revision and the GHCR manifest digest from this release.

GHCR package visibility can require one manual GitHub UI action after the
first publish: open the `infinite-canvas` package settings, choose **Change
visibility**, and set it to **Public**. GitHub Actions does not reliably make
an organization package public automatically.

## Deployment and rollback

Public users who need reproducibility must pin either the immutable version
tag or the manifest digest, for example:

```text
ghcr.io/yanwo-lab/infinite-canvas:vX.Y.Z
ghcr.io/yanwo-lab/infinite-canvas@sha256:<manifest-digest>
```

Owner production intentionally follows stable `latest`. Each production
deployment and rollback record must capture the resolved version, SHA, and
digest. Roll back by selecting a previously recorded immutable version/digest,
then recreate with `--no-build`; never rebuild old source to reproduce a
release.

## Semantic versioning

Yanwo releases follow SemVer:

- **patch:** backward-compatible bug fixes;
- **minor:** backward-compatible new capabilities;
- **major:** incompatible behavior, data, API, or deployment changes.

## Verification commands

Replace the examples with the exact release values:

```bash
git status --short --branch
git rev-parse 'vX.Y.Z^{}'
git ls-remote --tags origin 'refs/tags/vX.Y.Z' 'refs/tags/vX.Y.Z^{}'
docker buildx imagetools inspect ghcr.io/yanwo-lab/infinite-canvas:vX.Y.Z
docker buildx imagetools inspect ghcr.io/yanwo-lab/infinite-canvas:latest
```

Keep the prior versioned image, production configuration, persistent data, and
Nginx rollback configuration until the new release has completed its rollback
retention period.
