# Docker Distribution and Plugin Management Design

**Date:** 2026-08-29  
**Status:** Approved for implementation after self-review  
**Scope:** Public GHCR distribution, built-in/external plugin roots, and Plugin Manager v1

## 1. Goals and non-goals

This change makes Infinite Canvas runnable from a public multi-architecture image, keeps image-supplied plugins separate from user-installed plugins, and provides a minimal built-in manager for public GitHub plugin repositories.

It does not add workflow nodes or business features. It does not implement a marketplace, dependency solver, enable/disable state, private repositories, Git-based installation, signatures, permissions, iframe/Worker isolation, or a capability sandbox. Plugins remain trusted same-page ES modules. Installing a third-party plugin is equivalent to executing that repository's browser code with the application's page privileges.

The upstream `VERSION` file remains independent from Yanwo releases.

## 2. Audited baseline

- `main.py` discovers only repository-local `plugins/` and exposes the entire directory through `StaticFiles` at `/plugins`.
- `plugin_discovery.py` validates required manifest fields, API version, directory/id equality, and simple relative main/style paths. It does not defend against symlink escape and supports only one root.
- `static/js/plugin-host.js` consumes stable `moduleUrl` and `styleUrls`, isolates discovery/import/activation/UI errors, and exposes the toolbar extension slot. It needs no root-specific logic.
- The six built-ins are `example-text`, `example-toolbar`, `for-each`, `if`, `list`, and `yanwo-ui`.
- `runtime_paths.py` centralizes runtime paths. Docker has no external-plugin data domain.
- `compose.yml` builds from source. There is no GHCR publishing workflow.
- The existing Plugin Host and Phase 1-8 tests are the compatibility baseline. The 14 `test_canvas_log_cleanup.py` failures remain an excluded historical baseline.

## 3. Chosen architecture

### 3.1 Alternatives considered

1. **Mount external plugins over `/app/plugins`.** Rejected because the mount hides image-supplied plugins and permits user content to replace built-ins.
2. **Expose separate built-in and external static URLs.** Viable, but leaks root knowledge into the browser and duplicates load handling.
3. **Merge discovery behind one validated URL namespace.** Chosen. The browser keeps `/plugins/<id>/<path>` while the backend resolves each ID to its authoritative root and serves only safe files beneath that validated directory.

The design has three focused layers:

- **Distribution:** a stable GitHub Release drives one immutable multi-architecture image source and its three tags.
- **Runtime discovery:** a root-aware module validates built-in/external plugins and owns safe asset resolution.
- **Management:** a separate service downloads GitHub archives, validates in staging, and atomically manages only external plugins. A built-in toolbar plugin supplies the UI.

`main.py` only constructs services, includes the router, and delegates discovery/assets. It receives no plugin-id or business-node special cases.

## 4. Phase A: public GHCR distribution

### 4.1 Release workflow

Create `.github/workflows/publish-container.yml` with:

- Trigger `release: types: [published]`; draft and prerelease releases are skipped.
- Validate the release tag as `vMAJOR.MINOR.PATCH`.
- Checkout the exact release tag/commit.
- Use `contents: read`, `packages: write`, QEMU, and Buildx.
- Log in with `github.actor` and `GITHUB_TOKEN`.
- Use one `docker/build-push-action` invocation for `linux/amd64,linux/arm64` and tags:
  - `ghcr.io/yanwo-lab/infinite-canvas:<release-tag>`
  - `ghcr.io/yanwo-lab/infinite-canvas:latest`
  - `ghcr.io/yanwo-lab/infinite-canvas:<7-character-release-sha>`
- Record the full revision and release source as OCI labels.

One Buildx invocation makes all tags reference the same multi-architecture manifest. A normal `main` push is not a publish trigger and cannot move `latest`. Existing tags are never force-updated.

GitHub may create the package as private and Actions cannot reliably change organization package visibility. If anonymous pull fails, the sole manual action is GitHub package settings → `infinite-canvas` → Change visibility → Public. This must be reported, not hidden.

### 4.2 Compose responsibilities

- `compose.yml` becomes the public image deployment and defaults to `ghcr.io/yanwo-lab/infinite-canvas:latest`; `CANVAS_IMAGE` may pin a version/digest.
- `compose.dev.yml` remains the source-build developer definition using `Dockerfile`.
- Both retain ports, environment paths, healthcheck, and data/upload/cache/output mounts.
- Both add a dedicated external-plugin host mount at `/data/plugins`.
- `.env.example` distinguishes `CANVAS_HOST_EXTERNAL_PLUGINS_DIR` from container `CANVAS_EXTERNAL_PLUGINS_DIR`.

README contains a standalone Compose snippet requiring no clone, explains `latest` versus immutable versions, and separately documents source build.

### 4.3 Release identities

`docs/RELEASE.md` distinguishes upstream `VERSION`, Yanwo SemVer, Git revision, and GHCR tag/manifest digest. Public users should pin a version/digest for reproducibility. The project owner's production intentionally follows stable `latest`; rollback records always include its exact version, SHA, and digest.

## 5. Phase B: built-in and external plugin roots

### 5.1 Runtime paths

`RuntimePaths` gains `external_plugins_dir`:

- override: `CANVAS_EXTERNAL_PLUGINS_DIR`;
- Docker: Compose sets `/data/plugins`;
- source default: `<data_dir>/plugins`, an ignored runtime tree that never pollutes repository `plugins/`;
- built-in root remains `<base_dir>/plugins` (`/app/plugins` in the image).

### 5.2 Discovery model

Discovery returns the existing `{plugins, errors}` shape and adds stable source fields:

```json
{
  "plugins": [{"id":"list","source":"builtin","moduleUrl":"/plugins/list/index.js"}],
  "errors": [{"plugin":"list","source":"external","error":"duplicate plugin id conflicts with builtin"}]
}
```

Rules:

- Scan built-in then external, deterministically sorted. A valid built-in ID wins; a conflicting external is omitted with an error.
- Invalid built-ins do not reserve IDs; their errors remain visible.
- Directory name equals manifest `id`; IDs match `^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`.
- Required fields remain `id`, `name`, `version`, `apiVersion`, `main`.
- `apiVersion` is integer `1` and booleans are rejected.
- `main` and each `styles` entry are non-empty POSIX-relative regular files within the plugin.
- Reject absolute paths, `.`, `..`, hidden components, backslashes, NUL/control characters, symlinks, and non-files.
- Missing external root is an empty source.
- Successful records include `source: builtin|external` and stable `/plugins/<id>/...` URLs.

Unknown Plugin preservation/restoration is unchanged because node types and Plugin Host registration do not change.

### 5.3 Safe asset resolution

Replace broad `/plugins` `StaticFiles` with `GET /plugins/{plugin_id}/{asset_path:path}` backed by `resolve_plugin_asset(...)`. It returns `FileResponse` only when the plugin is currently valid/selected, all components are visible and safe, the target is a regular non-symlink file, and the resolved path remains below the selected plugin directory.

The resolver may serve safe module dependencies and `assets/` beneath a validated plugin, not merely manifest entry points. It never serves `.git`, dot paths, manager metadata, staging paths, or host files. Failures are 404 without filesystem leakage.

## 6. Phase C: Plugin Manager v1

### 6.1 Components and UI

- `plugin_manager.py`: GitHub parsing/client, archive extraction, digest, metadata, lifecycle service, and router factory.
- `plugins/plugin-manager/{plugin.json,index.js,style.css}`: built-in toolbar UI.
- `main.py`: minimal service/router wiring only.

The trusted built-in module creates a `<dialog>` and calls same-origin APIs with `fetch`. Its activation disposer removes UI/listeners. No Plugin Host API change is needed. After lifecycle operations the UI asks for/reloads the Canvas; hot plugin reload is outside v1.

### 6.2 API

- `GET /api/plugin-manager/plugins`
- `POST /api/plugin-manager/install` with `{"repositoryUrl":"https://github.com/owner/repo","ref":"optional"}`
- `POST /api/plugin-manager/plugins/{plugin_id}/check-update`
- `POST /api/plugin-manager/plugins/{plugin_id}/update`
- `DELETE /api/plugin-manager/plugins/{plugin_id}`

States include `installed`, `up-to-date`, `update-available`, `updated`, and `uninstalled`. Validation uses 400/422, not found 404, dirty/conflict/lock contention 409, remote errors 502/504, and unexpected failures generic 500 without paths.

Lists show built-ins read-only and external plugins with name, id, version, source, repository, requested ref, resolved commit, installed time, integrity, and update state.

### 6.3 GitHub source rules

Accept only `https://github.com/<owner>/<repo>` with optional terminal `.git`. Reject credentials, query/fragment, extra path, SSH, `git://`, `file://`, arbitrary URLs, and unknown hosts. Strictly validate owner/repo/ref lengths and characters.

Use public GitHub REST APIs to resolve the default branch or requested ref to a 40-character SHA and download that commit's source archive. Follow redirects only across HTTPS and an explicit GitHub archive host allowlist. Never invoke Git/shell, accept private tokens, or accept filesystem paths.

### 6.4 Limits and archive safety

- connect/read timeout: 10/30 seconds;
- compressed archive maximum: 50 MiB;
- entry maximum: 2,048;
- total declared uncompressed maximum: 200 MiB;
- individual file maximum: 50 MiB.

Stream downloads and stop at the compressed limit. Reject encrypted entries, absolute/drive paths, backslashes, empty/`.`/`..` components, NUL/control characters, duplicate normalized names, symlinks, and non-regular Unix file types. Write entries individually with exclusive creation; never call unrestricted `extractall`.

Require exactly one GitHub-generated top-level directory, strip it, and require `plugin.json` at repository root. Nested manifests are invalid.

### 6.5 Staging, atomic lifecycle, and dirty policy

Use same-filesystem `/data/plugins/.staging/<random-id>`, which is hidden from discovery/static serving. Validate extracted content with the runtime manifest validator. The manifest ID determines `/data/plugins/<id>`.

Install rejects an existing external ID or built-in collision, then atomically renames validated staging to target and atomically writes metadata.

Update checks recorded integrity first. Same commit returns `up-to-date`; a different commit is downloaded and validated, with the same plugin ID required. Rename old target to a private backup, staging to target, atomically update metadata, and remove backup after success. Any failure restores old files/metadata.

If the installed tree digest differs from metadata, return 409 and do not overwrite. V1 has no force update or merge; users explicitly uninstall/reinstall after preserving edits.

Uninstall only accepts validated external IDs, rejects built-ins, verifies realpath/commonpath and symlinks, moves target to private removal staging, commits metadata, then removes staged content. Failures before metadata commit restore it. Saved nodes remain and use existing Unknown Plugin behavior.

### 6.6 Metadata and concurrency

Store metadata outside plugins at `<CANVAS_DATA_DIR>/plugin-manager/installed.json` with:

- `sourceType: github`
- normalized `repository` and `repositoryUrl`
- nullable `requestedRef`
- full `resolvedCommit`
- UTC ISO `installedAt`
- `pluginVersion`
- SHA-256 `treeDigest` over sorted relative paths, modes, sizes, and bytes.

Write JSON through a flushed/fsynced temporary file and atomic replace. Plugin trees contain no manager metadata.

One process-wide non-blocking lock serializes install/update/uninstall; contention returns 409. This matches the single-process Uvicorn deployment. Distributed locking is outside v1. Stale hidden staging/backup paths are reported, not exposed; ambiguous destructive recovery is deferred.

## 7. Security boundary

The installer protects filesystem and package acquisition integrity; it does not sandbox JavaScript. README and Manager state: **Third-party plugins run with the same page privileges as Infinite Canvas. Install only repositories you trust.** Backend APIs never accept arbitrary download URLs, filesystem paths, or commands. Built-ins are immutable through Manager. Discovery, serving, and installation share validation primitives.

## 8. Testing and acceptance

### 8.1 Automated

TDD with mocked HTTP covers discovery built-in/external/mixed/duplicate/malformed/API/path/symlink/missing-root/source cases and asset denials. Manager tests cover valid install/default/ref, invalid URL/host/redirect, limits, traversal, symlink/non-regular entries, root manifest, schema/API, collision, same/different update, dirty rejection, failed-update preservation, uninstall boundaries, malicious IDs, metadata, and lock contention.

Run all existing Node/plugin tests, Python compatibility tests, JS syntax, `python -m py_compile`, and `git diff --check`. Full Python may contain only the known 14 cleanup baseline failures.

### 8.2 Browser

Chromium verifies desktop and 390px UI, six existing plugins plus Manager, fixture-plugin install/list/JS/CSS/refresh/update/uninstall, Unknown Plugin/reinstall restore, save/refresh/restore, and zero uncaught errors. Fixture content never becomes a business plugin.

### 8.3 Docker

Build local amd64 and verify `/app/plugins`, persistent `/data/plugins` across restart/core recreate, fresh and existing volumes, APIs, safe assets, Canvas, ffmpeg/ffprobe, healthcheck, WebSocket ping/pong, and that the workflow defines amd64/arm64 from one release source.

## 9. Release and production migration

Only after Phases A/B/C and final regression pass:

1. Confirm `v1.1.0` is absent locally/remotely; stop rather than overwrite.
2. Tag the accepted release commit with annotated `v1.1.0`, push, and publish a stable GitHub Release.
3. Verify `latest`, `v1.1.0`, and seven-character SHA share one multiarch digest and support amd64/arm64.
4. Verify anonymous pull; report the single package-visibility UI action if blocked.
5. Only then back up production Compose/rollback records, create a dedicated external-plugin host directory, and add only that mount.
6. Change `/opt/docker/canvas/green/compose.yml` to `ghcr.io/yanwo-lab/infinite-canvas:latest`, pull/recreate, and smoke-test without changing Nginx or existing data mounts.
7. Record release, SHA, and digest. Fast rollback changes image to retained local `v1.0.0` (or prior digest) and recreates `canvas-green`; no build.

No Canvas data, uploads, output, cache, API configuration, old deployment, Nginx upstream, or upstream `VERSION` is reorganized/deleted.

## 10. Delivery and self-review

- Spec and plan are committed separately before implementation.
- Every Phase is accepted, committed, pushed, remotely verified, and leaves a clean worktree.
- Production stays on its accepted image until the verified GHCR release.
- Stop only for production-data risk, release-tag overwrite/force push, or unavailable GitHub permissions.
- All explicit non-goals remain excluded.
- Stable-release-only `latest`, dual roots/source/conflict behavior, unified safe URLs, archive safety, atomic lifecycle, dirty policy, UI/API, tests, release, production, and rollback are covered.
- No requirement changes upstream `VERSION`, existing data layouts, Plugin Host execution semantics, or business nodes.
