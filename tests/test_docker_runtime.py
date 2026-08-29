import json
from pathlib import Path
import re
import subprocess


PUBLISH_WORKFLOW = Path(".github/workflows/publish-container.yml")
PUBLIC_COMPOSE = Path("compose.yml")
DEV_COMPOSE = Path("compose.dev.yml")
README = Path("README.md")
RELEASE_GUIDE = Path("docs/RELEASE.md")

EXPECTED_HEALTHCHECK = {
    "test": [
        "CMD",
        "python",
        "-c",
        "import socket; s=socket.create_connection(('127.0.0.1', 3000), 3); s.close()",
    ],
    "interval": "30s",
    "timeout": "5s",
    "retries": 3,
    "start_period": "20s",
}
EXPECTED_PORTS = [
    {
        "mode": "ingress",
        "target": 3000,
        "published": "3000",
        "protocol": "tcp",
    }
]


def _compose_service(compose_file: Path) -> dict:
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "config", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["services"]["infinite-canvas"]


def _volume_target_sources(service: dict) -> dict[str, str]:
    return {volume["target"]: volume["source"] for volume in service["volumes"]}


def test_public_compose_runs_the_published_image_without_a_build_definition():
    """A public deployment must pull the published image instead of building locally."""
    service = _compose_service(PUBLIC_COMPOSE)

    assert service["image"] == "ghcr.io/yanwo-lab/infinite-canvas:latest"
    assert "build" not in service


def test_dev_compose_keeps_the_local_build_and_runtime_contract():
    """Local development needs a build while retaining the container runtime contract."""
    assert DEV_COMPOSE.is_file()

    service = _compose_service(DEV_COMPOSE)

    assert service["build"]["context"] == str(Path.cwd())
    assert service["restart"] == "unless-stopped"
    assert service["init"] is True
    assert service["ports"] == EXPECTED_PORTS
    assert service["healthcheck"] == EXPECTED_HEALTHCHECK


def test_compose_files_keep_existing_storage_and_add_the_external_plugin_mount():
    """Every runtime variant must expose all persistent paths, including plugins."""
    expected_environment = {
        "CANVAS_DATA_DIR": "/data/app",
        "CANVAS_UPLOADS_DIR": "/data/uploads",
        "CANVAS_CACHE_DIR": "/data/cache",
        "CANVAS_OUTPUT_DIR": "/data/output",
        "CANVAS_EXTERNAL_PLUGINS_DIR": "/data/plugins",
    }
    expected_volume_sources = {
        "/data/app": str(Path.cwd() / "docker-data/data"),
        "/data/uploads": str(Path.cwd() / "docker-data/uploads"),
        "/data/cache": str(Path.cwd() / "docker-data/cache"),
        "/data/output": str(Path.cwd() / "docker-data/output"),
        "/data/plugins": str(Path.cwd() / "docker-data/plugins"),
    }

    for compose_file in (PUBLIC_COMPOSE, DEV_COMPOSE):
        assert compose_file.is_file()
        service = _compose_service(compose_file)
        assert service["restart"] == "unless-stopped"
        assert service["init"] is True
        assert service["ports"] == EXPECTED_PORTS
        assert service["healthcheck"] == EXPECTED_HEALTHCHECK
        assert service["environment"] == expected_environment
        assert _volume_target_sources(service) == expected_volume_sources


def test_env_example_documents_the_external_plugin_host_path_default():
    """Operators need the same default external-plugin host path as Compose."""
    env_lines = Path(".env.example").read_text(encoding="utf-8").splitlines()

    assert "CANVAS_HOST_EXTERNAL_PLUGINS_DIR=./docker-data/plugins" in env_lines


def test_readme_has_a_clone_free_docker_quick_start_with_the_runtime_contract():
    """Removing a public runtime setting from the Quick Start must be caught."""
    readme = README.read_text(encoding="utf-8")

    assert "## Docker Quick Start" in readme
    assert "ghcr.io/yanwo-lab/infinite-canvas:latest" in readme
    assert "mkdir -p docker-data/{data,uploads,cache,output,plugins}" in readme
    assert "docker compose up -d" in readme
    assert "restart: unless-stopped" in readme
    assert "init: true" in readme
    assert "healthcheck:" in readme
    assert "start_period: 20s" in readme

    expected_runtime_paths = {
        "CANVAS_DATA_DIR: /data/app": "./docker-data/data:/data/app",
        "CANVAS_UPLOADS_DIR: /data/uploads": "./docker-data/uploads:/data/uploads",
        "CANVAS_CACHE_DIR: /data/cache": "./docker-data/cache:/data/cache",
        "CANVAS_OUTPUT_DIR: /data/output": "./docker-data/output:/data/output",
        "CANVAS_EXTERNAL_PLUGINS_DIR: /data/plugins": "./docker-data/plugins:/data/plugins",
    }
    for environment_value, volume in expected_runtime_paths.items():
        assert environment_value in readme
        assert volume in readme


def test_readme_explains_image_pinning_source_development_and_plugin_trust():
    """The public guide must not make floating images or untrusted plugins look safe."""
    readme = README.read_text(encoding="utf-8")
    normalized_readme = re.sub(r"\s+", " ", readme).lower()

    assert "latest" in readme
    assert "vX.Y.Z" in readme
    assert "digest" in readme
    assert "git clone" in readme
    assert "docker compose -f compose.dev.yml up -d --build" in readme
    assert "same page privileges" in readme
    assert "trusted repositories" in readme
    assert "not a sandbox or marketplace" in normalized_readme


def test_release_guide_records_public_ghcr_identity_and_owner_rollback_policy():
    """A release guide missing immutable identity or rollback evidence is unsafe."""
    guide = RELEASE_GUIDE.read_text(encoding="utf-8")
    normalized_guide = re.sub(r"\s+", " ", guide)

    assert "v1.0.0" in guide
    assert "a20833d61b7a86dc8b189d3d6dad306d5c800ff9" in guide
    assert "upstream `VERSION`" in guide
    assert "do not modify it" in guide
    assert "ghcr.io/yanwo-lab/infinite-canvas" in guide
    assert "manifest digest" in guide
    assert "GitHub Release" in guide
    assert "vX.Y.Z" in guide
    assert "immutable" in guide
    assert "short SHA" in guide
    assert "latest" in guide
    assert "stable" in guide
    assert "pin" in guide
    assert "owner production" in normalized_guide.lower()
    assert "version, SHA, and digest" in normalized_guide
    assert "Change visibility" in normalized_guide
    assert "Public" in guide


def _top_level_workflow_trigger_names(workflow: str) -> set[str]:
    """Return trigger keys from the YAML ``on`` mapping without parsing ``on``."""
    on_match = re.search(r"^on:\s*$", workflow, re.MULTILINE)
    assert on_match is not None
    following_text = workflow[on_match.end() :]
    next_top_level_section = re.search(r"^[^\s#].*:\s*$", following_text, re.MULTILINE)
    trigger_mapping = following_text[
        : next_top_level_section.start() if next_top_level_section else None
    ]
    return set(
        re.findall(r"^  ([A-Za-z][A-Za-z0-9_-]*):", trigger_mapping, re.MULTILINE)
    )


def test_top_level_workflow_trigger_names_detect_inline_event_mappings():
    """An inline event mapping must be rejected as an extra publish trigger."""
    workflow_with_inline_push = """\
on:
  release:
    types: [published]
  push: {branches: [main]}

permissions:
  contents: read
"""

    assert _top_level_workflow_trigger_names(workflow_with_inline_push) == {
        "release",
        "push",
    }


def test_runtime_dependencies_include_websocket_backend():
    requirements = {
        line.strip().lower()
        for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "websockets" in requirements or "wsproto" in requirements


def test_release_publisher_is_stable_release_only_and_checks_out_the_release_tag():
    """A branch push or non-stable release must never publish ``latest``."""
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    assert _top_level_workflow_trigger_names(workflow) == {"release"}
    assert "release:" in workflow
    assert "types: [published]" in workflow
    assert not re.search(r"^\s{0,2}push:\s*$", workflow, re.MULTILINE)
    assert "draft == false" in workflow
    assert "prerelease == false" in workflow
    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+$" in workflow
    assert "actions/checkout@v4" in workflow
    assert "ref: ${{ github.event.release.tag_name }}" in workflow
    assert workflow.index("actions/checkout@v4") < workflow.index(
        "git rev-parse --short=7 HEAD"
    )
    assert "contents: read" in workflow
    assert "packages: write" in workflow


def test_release_publisher_builds_and_pushes_all_stable_ghcr_tags_from_one_build():
    """A published stable tag maps to exactly one multi-arch GHCR build."""
    workflow = PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    assert "docker/setup-qemu-action@v3" in workflow
    assert "docker/setup-buildx-action@v3" in workflow
    assert "docker/login-action@v3" in workflow
    assert "registry: ghcr.io" in workflow
    assert "username: ${{ github.actor }}" in workflow
    assert "password: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert workflow.count("docker/build-push-action@v6") == 1
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "push: true" in workflow
    assert "ghcr.io/yanwo-lab/infinite-canvas:${{ github.event.release.tag_name }}" in workflow
    assert "ghcr.io/yanwo-lab/infinite-canvas:latest" in workflow
    assert "git rev-parse --short=7 HEAD" in workflow
    assert "ghcr.io/yanwo-lab/infinite-canvas:${{ steps.revision.outputs.short_sha }}" in workflow
    assert "org.opencontainers.image.revision=${{ steps.revision.outputs.full_sha }}" in workflow
    assert "org.opencontainers.image.source=${{ github.event.release.html_url }}" in workflow
