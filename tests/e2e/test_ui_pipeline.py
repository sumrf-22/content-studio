"""Phase 5 end-to-end test: the browser UI drives the real pipeline.

A real ``run.py`` process is started against a throwaway data directory, then
Playwright clicks through the same buttons a person would: create an idea,
generate ideas, select one, approve copy, approve design, publish. Two formats
are exercised so the format routing and renderer both run in a real browser.

Run with::

    pytest -m e2e
"""

import json

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.e2e


def _card_for(page, topic):
    return page.locator(".approval-item", has_text=topic)


def _wait_for_previews(page, topic):
    page.wait_for_function(
        """(topic) => {
            const card = [...document.querySelectorAll('.approval-item')]
                .find(c => c.textContent.includes(topic));
            if (!card) return false;
            const imgs = [...card.querySelectorAll('img.preview-slide')];
            return imgs.length > 0 && imgs.every(i => i.complete && i.naturalWidth > 0);
        }""",
        arg=topic,
        timeout=30000,
    )


def _state_item(page, topic):
    state = page.evaluate("async () => await (await fetch('/api/state')).json()")
    return next(item for item in state["items"] if item["topic"] == topic)


def _run_pipeline(page, server, topic, idea_index, expected_format, expected_size):
    """Click one item from creation to published, using only the UI."""
    page.fill("#create-topic", topic)
    page.click("#create-btn")

    card = _card_for(page, topic)
    expect(card).to_be_visible(timeout=30000)
    item_id = card.locator("button[data-action]").first.get_attribute("data-item-id")
    assert item_id

    card.locator('button[data-action="approve_idea"]').click()
    select = card.locator('button[data-action="select_idea"]')
    expect(select).to_be_visible(timeout=30000)

    row = card.locator(".preview-stage-row").nth(idea_index)
    row.click()
    checked = page.eval_on_selector(
        f'input[name="select-idea-{item_id}"][value="{idea_index}"]',
        "input => input.checked",
    )
    assert checked, "clicking the idea row did not select it"
    select.click()

    approve_copy = card.locator('button[data-action="approve_copy"]')
    expect(approve_copy).to_be_visible(timeout=30000)
    approve_copy.click()

    approve_design = card.locator('button[data-action="approve_design"]')
    expect(approve_design).to_be_visible(timeout=30000)

    _wait_for_previews(page, topic)
    sizes = card.locator("img.preview-slide").evaluate_all(
        "(imgs) => imgs.map(i => [i.naturalWidth, i.naturalHeight])"
    )
    assert sizes, "design stage showed no preview images"
    for width, height in sizes:
        assert (width, height) == expected_size, f"{expected_format}: {width}x{height}"

    page.screenshot(
        path=str(server.artifacts / f"e2e_{expected_format.lower()}_design.png"),
        full_page=True,
    )

    approve_design.click()
    publish = card.locator('button[data-action="publish"]')
    expect(publish).to_be_visible(timeout=30000)
    publish.click()
    expect(card).to_have_count(0, timeout=30000)

    item = _state_item(page, topic)
    assert item["stage"] == "done"
    assert item["status"] == "published_local"
    assert item["published"] is True
    assert item["format"] == expected_format
    assert item["publish"]["mode"] == "mock"
    snapshot = json.loads(
        (server.data / "published" / f"item_{item_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert snapshot["publish"]["mode"] == "mock"
    assert snapshot["stage"] == "done"
    return item


def _assert_recent_toggle_label(page):
    """The toggle must render arrows as characters, never as HTML entities."""
    page.evaluate(
        "document.getElementById('recent-toggle').style.display = 'block'"
    )
    toggle = page.locator("#recent-toggle")

    toggle.click()
    expanded = toggle.inner_text()
    assert "&#" not in expanded, expanded
    assert "▴" in expanded and "Hide" in expanded, expanded

    toggle.click()
    collapsed = toggle.inner_text()
    assert "&#" not in collapsed, collapsed
    assert "▾" in collapsed and "View All" in collapsed, collapsed


def _assert_story_thumbnail_shows_content(page, topic):
    """A 1080x1920 card thumbnail must crop from the top, not the empty middle."""
    card = page.locator(".content-card", has_text=topic).first
    expect(card).to_be_visible(timeout=30000)
    image = card.locator(".content-thumb img").first
    expect(image).to_be_visible(timeout=30000)
    assert image.evaluate("img => img.complete && img.naturalWidth > 0")
    assert image.evaluate("img => [img.naturalWidth, img.naturalHeight]") == [
        1080,
        1920,
    ]
    position = image.evaluate("img => getComputedStyle(img).objectPosition")
    # Browsers normalise "top center" to "50% 0%" (x y); the vertical anchor
    # must be the top edge.
    assert position.split()[-1] == "0%", position


def test_ui_pipeline_publishes_two_formats_without_errors(server):
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

        page.goto(server.base_url + "/")
        expect(page.locator("#create-topic")).to_be_visible()
        _assert_recent_toggle_label(page)

        carousel = _run_pipeline(
            page, server, "E2E carousel topic", 0, "CAROUSEL", (1080, 1350)
        )
        story = _run_pipeline(
            page, server, "E2E story topic", 6, "STORY_POLL", (1080, 1920)
        )
        _assert_story_thumbnail_shows_content(page, "E2E story topic")

        page.screenshot(
            path=str(server.artifacts / "e2e_dashboard.png"), full_page=True
        )
        browser.close()

    assert carousel["stage"] == "done"
    assert story["stage"] == "done"
    assert console_errors == [], console_errors
    assert page_errors == [], page_errors
    assert bad_responses == [], bad_responses
