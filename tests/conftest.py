"""Shared fixtures.

Every fixture that touches storage redirects it at a temporary folder so the
real ``data/`` directory (and the operator's pipeline) is never modified.
"""

import pytest

import core.llm as llm
import core.state as state_module
import dashboard.app as app_module
from agents import kite, orin


@pytest.fixture()
def isolated_data(tmp_path, monkeypatch):
    """Point state, renders, publish output and the asset route at ``tmp_path``."""
    data = tmp_path / "data"
    data.mkdir()

    monkeypatch.setattr(state_module, "DATA", data)
    monkeypatch.setattr(state_module, "STATE", data / "state.json")
    monkeypatch.setattr(app_module, "DATA_ROOT", data)
    monkeypatch.setattr(kite, "DATA_ROOT", data)
    monkeypatch.setattr(kite, "RENDER_DIR", data / "renders")
    monkeypatch.setattr(orin, "DATA", data)
    return data


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    """Force mock mode so no test can call OpenRouter, whatever the local .env."""
    monkeypatch.setattr(llm, "MOCK_MODE", True)
    return True
