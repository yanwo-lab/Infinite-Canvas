# Phase 8 final acceptance

Date: 2026-08-28

Phase 8 completes the compatibility and deployment-readiness roadmap at
`42b4ed7`. The validation used isolated Docker projects, ports, and bind mounts;
the legacy deployment at `/opt/docker/canvas/app` was not modified.

## Automated verification

- Node/plugin suite: 41 passed, 0 failed.
- Focused Python compatibility suite: 8 passed, 0 failed.
- Full Python suite: 8 passed and the same 14 historical failures in
  `tests/test_canvas_log_cleanup.py`. Those tests target cleanup functions
  removed by historical commit `a581fbb` and remain outside this roadmap.
- All 27 core/plugin JavaScript files passed `node --check`; Python runtime
  modules passed `py_compile`; `git diff --check` passed.

## Browser compatibility

Real Chromium 151 acceptance passed at 1440x900 and 390x844 with zero uncaught
page errors. It covered old and new Canvas JSON, legacy and named-port
connections, List -> For Each -> IF execution, old Loop coexistence,
missing-plugin -> Unknown Plugin -> restore, Yanwo UI enabled/disabled, and
save/refresh/restore with opaque data preserved.

## Docker compatibility

- Final `docker compose build --no-cache` passed from `42b4ed7`.
- Fresh data returned an empty Canvas list and discovered all six repository
  plugins without errors.
- Existing old/new Canvas records, uploads, output, and cache markers retained
  identical SHA-256 hashes through container recreation and restart.
- Healthcheck, plugin JavaScript/CSS, uploads/output serving, and Canvas APIs
  passed. `ffmpeg` and `ffprobe` are present in the image.
- `/ws/stats` completed a real WebSocket connection and `ping`/`pong` exchange.
  Commit `42b4ed7` adds the missing runtime backend and its regression test.

## Upstream compatibility

The disposable rehearsal used upstream `67f49e4` with merge base `1c141a5`.
The branches diverged by 8 upstream-only and 16 fork-only commits. The rehearsal
found one direct conflict in `static/smart-canvas.html`, limited to the
`smart-canvas.js` cache-buster. `static/js/smart-canvas.js` auto-merged but
remains the main semantic review surface for future merges. Most fork work is
additive and concentrated under `plugins/`, `static/js/plugin-host.js`, tests,
and Docker/runtime-path files. The rehearsal branch and worktree were removed;
no rehearsal merge entered `main`.

## Release ruling

Plugin Host, Example Plugin, List, For Each, IF, generic workflow execution,
UI extensions, Yanwo UI, old Canvas compatibility, Docker runtime behavior, and
upstream merge maintainability all meet the Phase 8 acceptance criteria. The
14 cleanup failures remain a documented pre-existing baseline rather than a
release regression.
