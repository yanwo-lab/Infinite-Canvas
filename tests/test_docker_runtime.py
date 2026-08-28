from pathlib import Path


def test_runtime_dependencies_include_websocket_backend():
    requirements = {
        line.strip().lower()
        for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "websockets" in requirements or "wsproto" in requirements
