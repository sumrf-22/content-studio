"""Shared browser-test fixture: a real ``run.py`` on a temporary data root."""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"

# Test-only Fernet key so the e2e run never writes a real secret to .env.
E2E_SECRET_KEY = "2aDelJn6IDCS6GLihHkWIDDBspTt3v8jMVm7J-4dL98="


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(base_url, proc, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"run.py exited early with code {proc.returncode}")
        try:
            with urllib.request.urlopen(base_url + "/api/state", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"server did not start on {base_url}")


@pytest.fixture()
def server(tmp_path):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    data_dir = tmp_path / "data"

    env = os.environ.copy()
    for key in (
        "OPENROUTER_API_KEY",
        "IMGBB_API_KEY",
        "CONTENT_STUDIO_TOKEN",
        "CONTENT_STUDIO_DEBUG",
        "CONTENT_STUDIO_SECRET_KEY",
    ):
        env.pop(key, None)
    env["CONTENT_STUDIO_HOST"] = "127.0.0.1"
    env["CONTENT_STUDIO_PORT"] = str(port)
    env["CONTENT_STUDIO_DATA_DIR"] = str(data_dir)
    # Fixed test-only key: provider saves never touch the real ``.env``.
    env["CONTENT_STUDIO_SECRET_KEY"] = E2E_SECRET_KEY

    log_path = ARTIFACTS / "e2e_server.log"
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "run.py")],
        cwd=str(ROOT),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, proc)
        yield SimpleNamespace(
            base_url=base_url,
            data=data_dir,
            log=log_path,
            artifacts=ARTIFACTS,
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        log_handle.close()
