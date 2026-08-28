# Phase 8 Final Compatibility Plan

**Spec:** `docs/CODEX_ROADMAP.md`, Phase 8, with the user's approved code-server exceptions.

## Global constraints

- Preserve old Canvas JSON and legacy connections while validating named-port connections.
- Do not add core `node.type` special cases for plugin nodes or change old Loop semantics.
- Do not fix the 14 unrelated `test_canvas_log_cleanup.py` baseline failures.
- Keep the three Phase 7 commits unchanged.
- Defer Docker-daemon deployment validation and GitHub push until a capable host; record both explicitly.

## Task 1: Compatibility behavior and regression tests

Audit existing real behavior, then use TDD to add only missing coverage or fixes for old/new Canvas JSON, missing/restored plugins, legacy/named-port connections, List, For Each, IF, old Loop, and built-in/plugin mixed canvases. Run focused tests and commit the completed task.

## Task 2: Environment-independent final acceptance

Run the backend and frontend suites excluding only the acknowledged cleanup baseline, perform real browser acceptance, rehearse or assess an upstream merge in a disposable worktree, run static/diff checks, and record deferred Docker/deployment checks. Commit a Phase 8 milestone only after verification and review.
