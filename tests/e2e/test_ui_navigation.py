"""Task 2 e2e: every sidebar link loads a real page, with no errors.

Run with::

    pytest -m e2e
"""

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.e2e

# (href, expected <title>, expected active href)
PAGES = [
    ("/", "Content Studio — Dashboard", "/"),
    ("/content-studio", "Content Studio — Content Studio", "/content-studio"),
    ("/ideas", "Content Studio — Ideas", "/ideas"),
    ("/content-pipeline", "Content Studio — Content Pipeline", "/content-pipeline"),
    ("/assets", "Content Studio — Assets", "/assets"),
    ("/projects", "Content Studio — Projects", "/projects"),
    ("/analytics", "Content Studio — Analytics", "/analytics"),
    ("/settings", "Content Studio — Settings", "/settings"),
]


def _open(page, server, href, expected_title, expected_active):
    page.goto(server.base_url + "/")
    expect(page.locator(".sidebar-nav")).to_be_visible()
    page.click(f'.sidebar-nav a[href="{href}"]')

    page.wait_for_url(server.base_url + href)
    assert page.title() == expected_title

    sidebar_text = page.locator(".sidebar-nav").inner_text()
    assert "&#" not in sidebar_text, sidebar_text

    active = page.locator(".sidebar-nav a.active")
    expect(active).to_have_count(1)
    assert active.get_attribute("href") == expected_active
    assert active.get_attribute("aria-current") == "page"

    current = page.locator('.sidebar-nav a[aria-current="page"]')
    expect(current).to_have_count(1)
    assert current.get_attribute("href") == expected_active


def test_sidebar_links_load_real_pages_without_errors(server):
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
        page.on("dialog", lambda dialog: dialog.accept())
        page.on(
            "response",
            lambda response: bad_responses.append(
                (response.status, response.url)
            )
            if response.status >= 400 and "/api/" in response.url
            else None,
        )

        for href, title, active in PAGES:
            _open(page, server, href, title, active)
            page.screenshot(
                path=str(
                    server.artifacts
                    / f"e2e_nav_{active.strip('/').replace('/', '_') or 'dashboard'}.png"
                ),
                full_page=True,
            )

        browser.close()

    assert console_errors == [], console_errors
    assert page_errors == [], page_errors
    assert bad_responses == [], bad_responses
