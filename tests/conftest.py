"""Shared fixtures.

Every fixture that touches storage redirects it at a temporary folder so the
real ``data/`` directory (and the operator's pipeline) is never modified.
"""

import pytest

import core.settings as settings_module
import core.state as state_module
import dashboard.app as app_module
from agents import kite, orin

# A throwaway Fernet key for tests only. It is never used by the real app.
TEST_SECRET_KEY = "2aDelJn6IDCS6GLihHkWIDDBspTt3v8jMVm7J-4dL98="


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
def isolate_provider_settings(tmp_path, monkeypatch):
    """Keep provider files and the generated secret out of the real project."""
    provider_dir = tmp_path / "provider_settings"
    monkeypatch.setattr(settings_module, "_settings_dir", lambda: provider_dir)
    monkeypatch.setattr(settings_module, "ENV_FILE", tmp_path / "provider.env")
    monkeypatch.setenv(settings_module.SECRET_ENV, TEST_SECRET_KEY)
    return provider_dir
