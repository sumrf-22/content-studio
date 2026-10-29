"""Task 4 e2e: add a BYOK provider, see only the mask, then delete it.

The real ``run.py`` server runs against a temporary data root with a test-only
Fernet key, so no real key or ``.env`` entry is ever created.

Run with::

    pytest -m e2e
"""

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.e2e

RAW_KEY = "sk-or-v1-e2e-secret-key-ab12"
MASK = "sk-or-...ab12"


def test_settings_provider_add_mask_delete(server):
    console_errors = []
    page_errors = []
    bad_responses = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(30000)

        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: bad_responses.append(
                (response.status, response.url)
            )
            if response.status >= 400 and "/api/" in response.url
            else None,
        )
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(server.base_url + "/settings")
        expect(page.locator("#mode-title")).to_have_text("Mock mode")
        expect(page.locator(".provider-list .empty")).to_contain_text(
            "No providers yet"
        )
        page.screenshot(
            path=str(server.artifacts / "e2e_settings_empty.png"), full_page=True
        )

        # --- add ---------------------------------------------------------
        page.select_option("#provider-preset", "openrouter")
        assert page.input_value("#provider-base-url") == "https://openrouter.ai/api/v1"
        assert page.input_value("#provider-model") == "openrouter/free"

        page.fill("#provider-name", "E2E OpenRouter")
        page.fill("#provider-api-key", RAW_KEY)
        page.click("#save-provider")

        row = page.locator(".provider-row", has_text="E2E OpenRouter")
        expect(row).to_be_visible()
        expect(row).to_contain_text(MASK)
        expect(row).to_contain_text("openrouter/free")
        expect(row.locator(".badge-default")).to_have_text("Default")
        expect(row.locator(".badge-enabled")).to_have_text("Enabled")

        expect(page.locator("#mode-title")).to_have_text("Live — E2E OpenRouter")
        expect(page.locator("#mode-detail")).to_contain_text("openrouter/free")

        # The raw key must never reach the DOM, and the form must be reset.
        body = page.locator("body").inner_text()
        assert RAW_KEY not in body
        assert page.input_value("#provider-api-key") == ""
        assert page.input_value("#provider-name") == ""

        page.screenshot(
            path=str(server.artifacts / "e2e_settings_provider.png"), full_page=True
        )

        # --- edit keeps the stored key ------------------------------------
        row.locator('button[data-action="edit"]').click()
        expect(page.locator("#form-title")).to_have_text("Edit E2E OpenRouter")
        assert page.input_value("#provider-name") == "E2E OpenRouter"
        assert page.input_value("#provider-api-key") == ""
        expect(page.locator("#key-hint")).to_contain_text(MASK)
        page.click("#cancel-edit")

        # --- delete -------------------------------------------------------
        row.locator('button[data-action="delete"]').click()

        expect(page.locator(".provider-list .empty")).to_contain_text(
            "No providers yet"
        )
        expect(page.locator("#mode-title")).to_have_text("Mock mode")
        assert page.locator(".provider-row").count() == 0

        api_state = page.evaluate(
            "() => fetch('/api/settings/providers').then(r => r.json())"
        )
        assert api_state["providers"] == []
        assert api_state["mode"]["mode"] == "mock"

        page.screenshot(
            path=str(server.artifacts / "e2e_settings_deleted.png"), full_page=True
        )

        browser.close()

    assert console_errors == [], console_errors
    assert page_errors == [], page_errors
    assert bad_responses == [], bad_responses
