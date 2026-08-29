# Docker Distribution and Plugin Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish Infinite Canvas through stable multi-architecture GHCR releases, support immutable built-in plus persistent external plugins, and add a safe built-in GitHub Plugin Manager v1.

**Architecture:** Keep one `/plugins/<id>/<path>` browser namespace while a root-aware backend validates and resolves built-in/external content. Put GitHub archive acquisition and lifecycle operations in a focused service using staged validation, atomic replacement, external metadata, and a process lock. Publish release tags in one GitHub Release-triggered Buildx invocation and migrate production only after complete acceptance.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, httpx, ZIP standard library, ES modules, Node test runner, pytest, Docker Compose/Buildx, GitHub Actions, Playwright/Chromium.

**Spec:** `docs/superpowers/specs/2026-08-29-docker-plugin-distribution-design.md`

## Global Constraints

- Do not add Grouped Media, Media Naming, ZIP Export, Cartesian Product, Nested Loop, or business workflow nodes.
- Do not change Plugin Host execution semantics, existing Loop behavior, or upstream `VERSION`.
- Do not implement sandboxing, permissions, signing, marketplace, private repositories, Git installation, dependency resolution, or enable/disable.
- Do not fix the 14 historical `test_canvas_log_cleanup.py` failures.
- Do not modify production until Phases A-C and final acceptance pass.
- Every Phase ends with acceptance, commit, push, remote verification, and a clean worktree.
- Never move an existing release tag or force push.

## File map

- `.github/workflows/publish-container.yml`: stable-release-only multiarch GHCR publisher.
- `compose.yml`: public image deployment; `compose.dev.yml`: source-build development.
- `.env.example`, `README.md`, `docs/RELEASE.md`: public runtime, trust, and release contract.
- `runtime_paths.py`: external plugin root.
- `plugin_discovery.py`: shared validation, two-root discovery, safe assets.
- `plugin_manager.py`: GitHub client, archive validation, metadata, lifecycle, API router.
- `main.py`: minimal route/service wiring.
- `plugins/plugin-manager/`: trusted toolbar UI.
- Python/Node tests: TDD and compatibility gates; `tests/fixtures/external-plugin/`: inert acceptance fixture only.

---

### Task 1: Phase A GHCR release workflow

**Files:** Create `.github/workflows/publish-container.yml`; modify `tests/test_docker_runtime.py`.

**Interfaces:** Produces a stable `release.published` workflow that emits `latest`, exact release tag, and seven-character release SHA from one multiarch build.

- [ ] **Step 1: Write failing workflow contract tests.** Assert release-only trigger, no main push, tag validation, exact checkout, `packages: write`, GHCR login, `linux/amd64,linux/arm64`, one build-push step, repository name, and all three tags.
- [ ] **Step 2: Run `python -m pytest tests/test_docker_runtime.py -q`.** Expected: FAIL because the workflow is absent.
- [ ] **Step 3: Implement minimal workflow.** Use checkout v4, QEMU v3, Buildx v3, login v3, build-push v6. A shell step accepts only `v[0-9]+.[0-9]+.[0-9]+` and emits `${GITHUB_SHA::7}`. Skip prerelease/draft. Build and push both platforms once with the three raw tags and full-revision OCI label.
- [ ] **Step 4: Rerun focused tests.** Expected: PASS.

### Task 2: Phase A Compose split

**Files:** Modify `compose.yml`, `.env.example`, `tests/test_docker_runtime.py`; create `compose.dev.yml`.

**Interfaces:** Public Compose consumes `${CANVAS_IMAGE:-ghcr.io/yanwo-lab/infinite-canvas:latest}`; dev Compose builds `.`; both map `${CANVAS_HOST_EXTERNAL_PLUGINS_DIR}` to `/data/plugins` and set `CANVAS_EXTERNAL_PLUGINS_DIR`.

- [ ] **Step 1: Add failing tests.** Public Compose must have image/no build, dev must have build context, both must preserve four existing mounts/healthcheck and add only external plugins.
- [ ] **Step 2: Run focused tests.** Expected: FAIL on split/path.
- [ ] **Step 3: Implement the split.** Add `CANVAS_HOST_EXTERNAL_PLUGINS_DIR=./docker-data/plugins` to `.env.example`.
- [ ] **Step 4: Run `docker compose -f compose.yml config` and `docker compose -f compose.dev.yml config`.** Expected: both render with distinct responsibilities.

### Task 3: Phase A public docs and gate

**Files:** Modify `README.md`, `docs/RELEASE.md`, `tests/test_docker_runtime.py`.

**Interfaces:** Produces clone-free Quick Start, source-build instructions, trust warning, GHCR identities, and owner-production `latest` policy.

- [ ] **Step 1: Add failing documentation tests.** Require standalone Compose, commands, latest/version distinction, `compose.dev.yml`, same-page trust warning, stable-only latest, immutable version/SHA, digest recording, preserved v1.0.0, and unchanged upstream `VERSION`.
- [ ] **Step 2: Run focused tests.** Expected: FAIL on missing public/release text.
- [ ] **Step 3: Write concise docs.** Include five host paths, package-visibility limitation, SemVer flow, public pinning guidance, and rollback by version/digest.
- [ ] **Step 4: Run Phase A gate:** Docker/runtime tests, both Compose configs, workflow review, and `git diff --check`. Expected: PASS and main cannot publish latest.
- [ ] **Step 5: Commit and push.** Commit `feat: publish stable Docker releases to GHCR`, push `origin main`, compare local/remote SHA, and require empty status.

---

### Task 4: Phase B runtime path

**Files:** Modify `runtime_paths.py`, `tests/test_runtime_paths.py`.

**Interfaces:** Produces `RuntimePaths.external_plugins_dir: str`, overridden by `CANVAS_EXTERNAL_PLUGINS_DIR`, default `<data_dir>/plugins`.

- [ ] **Step 1: Add failing default/override tests.** Default must be below resolved data, never built-in `<base>/plugins`; override resolves exactly.
- [ ] **Step 2: Run `python -m pytest tests/test_runtime_paths.py -q`.** Expected: missing attribute failure.
- [ ] **Step 3: Add the frozen dataclass field.** Compute it with `_configured_path("CANVAS_EXTERNAL_PLUGINS_DIR", data / "plugins")`.
- [ ] **Step 4: Rerun tests.** Expected: PASS.

### Task 5: Phase B validation and dual discovery

**Files:** Modify `plugin_discovery.py`, `tests/test_plugin_discovery.py`.

**Interfaces:** Produces `validate_plugin_directory(plugin_dir: Path, source: str)`, `discover_plugins(builtin_root, external_root=None)`, stable source fields/URLs, and internal validated root records without leaking paths in JSON.

- [ ] **Step 1: Add failing parameterized tests.** Cover built-in-only, external-only, mixed order, duplicate priority/error, malformed manifest, boolean/unsupported API, bad ID, unsafe main/style, symlink entry/parent escape, missing external root, source, and URLs.
- [ ] **Step 2: Run discovery tests.** Expected: new cases fail.
- [ ] **Step 3: Implement strict reusable validation.** Use `lstat`, POSIX components, ID regex, `resolve(strict=True)`, and `commonpath`; reject hidden/control/backslash/dot/traversal/symlink/non-file cases.
- [ ] **Step 4: Implement deterministic built-in-first discovery.** Invalid built-ins report errors but do not reserve IDs; valid duplicates report external conflict.
- [ ] **Step 5: Rerun tests.** Expected: PASS.

### Task 6: Phase B safe asset integration and gate

**Files:** Modify `plugin_discovery.py`, `main.py`, `tests/test_plugin_discovery.py`, `tests/test_plugin_canvas_integration.py`.

**Interfaces:** Produces `resolve_plugin_asset(builtin_root, external_root, plugin_id, asset_path) -> Path | None`; dual-root `/api/plugins`; safe `GET /plugins/{plugin_id}/{asset_path:path}`.

- [ ] **Step 1: Add failing resolver/HTTP tests.** Cover entry/style/nested assets, built-in duplicate resolution, traversal/backslash/dot/.git/hidden, symlink file/dir, invalid plugin, non-file, missing external root, and no path leakage.
- [ ] **Step 2: Run focused tests.** Expected: resolver absent/broad static failures.
- [ ] **Step 3: Implement resolver and replace only the `/plugins` StaticFiles mount with FileResponse route.** Wire/create external root through `RUNTIME_PATHS`; keep all other mounts.
- [ ] **Step 4: Run Phase B gate:** runtime/discovery/integration pytest, Plugin Host/UI Node tests, Python compile, and diff check. Expected: PASS and six old built-ins remain.
- [ ] **Step 5: Commit and push.** Commit `feat: support persistent external plugins`, push, verify remote SHA, require clean status.

---

### Task 7: Phase C GitHub client and archive extraction

**Files:** Create `plugin_manager.py`, `tests/test_plugin_manager.py`.

**Interfaces:** Produces `GitHubRepository`, `parse_github_repository`, injected `GitHubArchiveClient.resolve/download`, `extract_github_archive`, and typed `PluginManagerError(status_code, code, message)`.

- [ ] **Step 1: Write failing URL/client tests with `httpx.MockTransport`.** Valid `.git`, default/ref/full SHA, credentials/query/fragment/path/host/scheme rejection, status/timeout, redirect allowlist, streamed cutoff.
- [ ] **Step 2: Write failing ZIP tests.** Valid root, traversal, absolute/drive/backslash, duplicate, symlink, device/non-regular, encrypted, entry/file/total limits, multiple roots, missing root manifest.
- [ ] **Step 3: Run manager tests.** Expected: module failure.
- [ ] **Step 4: Implement strict parser/client/extractor.** Use exact spec limits, manual exclusive extraction, Unix-mode checks, one root, and no `extractall`.
- [ ] **Step 5: Rerun security subset.** Expected: PASS.

### Task 8: Phase C metadata and lifecycle

**Files:** Modify `plugin_manager.py`, `tests/test_plugin_manager.py`.

**Interfaces:** Produces `PluginMetadataStore.load/save`, `tree_digest`, and `PluginManagerService.list_plugins/install/check_update/update/uninstall` under a non-blocking process lock.

- [ ] **Step 1: Add failing metadata/digest tests.** Determinism, path/bytes/mode changes, atomic JSON, corrupt store error, no metadata in plugin.
- [ ] **Step 2: Add failing lifecycle tests.** Valid install, built-in/external collision, manifest/API/id failure, same/different commit, successful update, dirty 409, failed update preserves files/metadata, uninstall boundaries, malicious ID, lock contention.
- [ ] **Step 3: Run tests.** Expected: missing service/store.
- [ ] **Step 4: Implement lifecycle operations.** Use same-filesystem `.staging`, `os.replace`, rollback blocks, shared manifest validation, fsync, and deletion only for proven manager-owned staging paths.
- [ ] **Step 5: Rerun all manager unit tests.** Expected: PASS.

### Task 9: Phase C API

**Files:** Modify `plugin_manager.py`, `main.py`, `tests/test_plugin_manager.py`.

**Interfaces:** Produces `create_plugin_manager_router(service) -> APIRouter` at the five spec endpoints with strict Pydantic bodies/error mapping.

- [ ] **Step 1: Add failing test-app API tests.** Schemas, states, 404/409/502, rejection of filesystem/download fields, and typed service calls only.
- [ ] **Step 2: Run tests.** Expected: router absent.
- [ ] **Step 3: Implement router and minimal wiring.** Use built-in root, external root, and `<DATA_DIR>/plugin-manager/installed.json`; keep lifecycle out of `main.py`.
- [ ] **Step 4: Run manager/integration pytest and `python -m py_compile plugin_manager.py main.py`.** Expected: PASS.

### Task 10: Phase C built-in UI

**Files:** Create `plugins/plugin-manager/plugin.json`, `index.js`, `style.css`, `tests/plugin-manager-ui.test.mjs`; modify discovery count assertions.

**Interfaces:** Produces toolbar item `plugin-manager:manage-plugins`, modal list/install/check/update/uninstall, refresh prompt/action, activation disposer.

- [ ] **Step 1: Add failing minimal-DOM/fetch tests.** Registration, built-in read-only, external fields/actions, install payload, check/update/delete, uninstall confirm, backend error, trust warning, refresh prompt, mobile structure, disposer.
- [ ] **Step 2: Run Node test.** Expected: plugin absent.
- [ ] **Step 3: Implement accessible dialog.** Use DOM `textContent`, disabled busy controls, same-origin fetch, one toolbar item, returned disposer; register no node and add no Host privilege.
- [ ] **Step 4: Run UI extension/discovery tests.** Expected: PASS and seven built-ins.

### Task 11: Phase C gate and commit

**Files:** Only Task 7-10 outputs.

**Interfaces:** Produces clean, remotely verified Phase C.

- [ ] **Step 1: Run Phase C and existing regressions.** Manager/discovery/integration pytest; all plugin/Host/UI/workflow Node tests; JS checks; Python compile; diff check. Expected: all pass.
- [ ] **Step 2: Commit and push.** Commit `feat: add built-in GitHub plugin manager`, push, compare remote SHA, and require empty status.

---

### Task 12: Final browser and Docker acceptance

**Files:** Create inert test-only `tests/fixtures/external-plugin/{plugin.json,index.js,style.css}` if needed; record evidence only in an existing repository convention.

**Interfaces:** Produces objective release evidence without a business plugin.

- [ ] **Step 1: Run complete automated regression.** `node --test tests/*.test.mjs`; full pytest; py_compile; JS checks; diff check. Expected: Node all pass, Python only exactly 14 known cleanup failures, all static checks pass.
- [ ] **Step 2: Build fresh amd64 image with five temporary mounts.** Verify health, seven built-ins, JS/CSS, Canvas API, ffmpeg/ffprobe, WebSocket ping/pong.
- [ ] **Step 3: Verify external persistence.** Install fixture in controlled setup, record hashes/metadata, restart and recreate core without volume deletion, confirm external and existing data unchanged and built-ins unshadowed.
- [ ] **Step 4: Run Chromium desktop/390px.** Manager install/list/load/refresh/update/uninstall; Unknown Plugin after fixture removal; reinstall/restore; existing six plugins, legacy Loop, List/For Each/IF/Yanwo UI, old/new Canvas/connections, save/refresh/restore, zero page errors.
- [ ] **Step 5: Review the workflow.** Verify exact-release checkout, single build source, amd64/arm64, stable-only trigger, and tags. Do not claim remote manifests before workflow completes.
- [ ] **Step 6: Commit acceptance artifacts only if changed.** Use `test: verify plugin distribution compatibility`, push/verify/clean; otherwise create no empty commit.

### Task 13: v1.1.0 release and GHCR verification

**Files:** No source changes.

**Interfaces:** Produces annotated Git tag/GitHub Release and three equal multiarch manifest digests.

- [ ] **Step 1: Fetch tags and prove `v1.1.0` absent locally and via `git ls-remote`.** If present, stop without overwrite.
- [ ] **Step 2: Create the release tag.** Annotate accepted commit as `v1.1.0`, push only the tag, verify peeled remote SHA, and prove `v1.0.0` unchanged.
- [ ] **Step 3: Publish stable GitHub Release with authenticated `gh release create --verify-tag`.** If release/package permission is unavailable, stop and report exact permission.
- [ ] **Step 4: Wait for publisher and inspect `latest`, `v1.1.0`, short SHA.** Assert same manifest digest and amd64/arm64; test anonymous pull. If private, report the exact package visibility UI action.
- [ ] **Step 5: Accept the pulled image.** Run runtime/browser acceptance with temporary mounts before production.

### Task 14: Production canvas-green migration

**Files:** Outside Git only: `/opt/docker/canvas/green/compose.yml`, `/opt/docker/canvas/green/ROLLBACK.md`.

**Interfaces:** Produces production on verified GHCR stable `latest`, persistent external mount, exact rollback identity.

- [ ] **Step 1: Re-audit/backup.** Verify Nginx `canvas-green:3000`; record container/image/mount/network/health; checksum and timestamp-copy Compose/rollback. Do not touch old `/opt/docker/canvas/app`.
- [ ] **Step 2: Create a dedicated non-symlink external-plugin host directory proven distinct from current data domains.** Never reorganize existing data.
- [ ] **Step 3: Change only image to GHCR latest and add external environment/mount.** Preserve mounts, port, network, health, service/container, Nginx.
- [ ] **Step 4: Pull, verify digest, recreate without volume deletion.** Stop on any data risk.
- [ ] **Step 5: Run production acceptance.** Verify health/restarts/domain/no-502/seven built-ins/Manager/assets/Canvas/ffmpeg/ffprobe/WebSocket/desktop/mobile/save/restore/no page errors and compare key pre/post counts/hashes.
- [ ] **Step 6: Record rollback.** Record v1.1.0, full/short SHA, manifest digest, retained local v1.0.0 ID, backups, and rollback: restore old Compose or local v1.0.0 then recreate/verify; no build.

### Task 15: Final verification and report

**Files:** None.

- [ ] **Step 1: Verify Git invariants.** Confirm `main == origin/main`, clean status, no unpushed commits, v1.0.0 unchanged, v1.1.0 correct, no unintended worktrees, and upstream `VERSION` unchanged.
- [ ] **Step 2: Capture evidence.** Record workflow, visibility, manifests/platforms, production identity/health, Nginx/domain/WebSocket/browser, persistent path/data comparison, and rollback backup.
- [ ] **Step 3: Report completion.** Cover user fields A-AE and explicitly state whether any prohibited business plugin was implemented.

## Plan self-review

- **Spec coverage:** Distribution, dual roots, manager, security, tests, release, production, rollback, and report map to Tasks 1-15.
- **Phase boundaries:** Tasks 1-3, 4-6, and 7-11 each end with commit/push/remote/clean gates.
- **Type consistency:** Runtime path, discovery, resolver, service, router, and UI names are defined before consumption.
- **No expansion:** Current trusted toolbar/refresh model is reused; no node, sandbox, marketplace, Git command, credential, or enable/disable work.
- **Safety:** Tag absence, GHCR verification, production backups, mount isolation, digest evidence, and no volume deletion precede external changes.
