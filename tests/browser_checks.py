"""Optional browser checks. Run: python tests/browser_checks.py.

Requires playwright plus Chromium. Uses a disposable local database/server.
Screenshots are written to /tmp/timerrr-screenshots.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_agent_integration import AgentIntegrationTests

from app.models import User, db

AgentIntegrationTests.setUpClass()
fixture = AgentIntegrationTests
with fixture.app.app_context():
    user = User.query.first()
    user.set_password("local-preview")
    db.session.commit()
from app.socketio_events import socketio

# Werkzeug's test server uses threading; production keeps its gevent worker.
socketio.init_app(fixture.app, async_mode="threading")
BASE_URL = fixture.env["TIMERRR_URL"]
from playwright.sync_api import sync_playwright

os.makedirs("/tmp/timerrr-screenshots", exist_ok=True)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}, device_scale_factor=1
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE_URL + "/")
        page.get_by_role("button", name="Start timer", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#demo-clock').textContent !== '0:00:00'"
        )
        page.get_by_role("button", name="Stop timer").click()
        page.locator("#calc-duration").fill("20")
        assert "60 agent-min" in page.locator("#calc-result").inner_text()
        page.screenshot(
            path="/tmp/timerrr-screenshots/home-desktop.png", full_page=True
        )
        page.goto(BASE_URL + "/login")
        page.locator("[name=email]").fill("protocol@example.com")
        page.locator("[name=password]").fill("local-preview")
        page.get_by_role("button", name="Login", exact=True).click()
        page.wait_for_url("**/timer")
        page.screenshot(
            path="/tmp/timerrr-screenshots/timers-desktop.png", full_page=True
        )
        page.goto(BASE_URL + "/work")
        page.locator("#start-work [name=title]").fill("Checkout fix / human review")
        page.get_by_role("button", name="Start my work", exact=True).click()
        page.wait_for_selector(".work-card")
        page.wait_for_timeout(1200)
        page.get_by_role("button", name="Add evidence", exact=True).first.click()
        page.locator("#evidence-dialog [name=text]").fill(
            "Reviewed checkout behavior and test results."
        )
        page.locator("#evidence-dialog [name=url]").fill("https://example.com/pull/42")
        page.get_by_role("button", name="Save evidence").click()
        page.wait_for_selector("#evidence-dialog", state="hidden")
        page.get_by_role("button", name="Finish session", exact=True).first.click()
        page.wait_for_timeout(600)
        page.get_by_role("button", name="Build draft").click()
        page.wait_for_selector("#approve-form")
        page.get_by_role("button", name="Approve reviewed intervals").click()
        page.wait_for_function(
            "document.querySelector('#draft-review').textContent.includes('time entries created')"
        )
        page.locator(".work-card summary").first.click()
        page.screenshot(
            path="/tmp/timerrr-screenshots/work-desktop.png", full_page=True
        )
        for path in [
            "/entries",
            "/timesheets",
            "/settings",
            "/work",
            "/timer",
            "/guides/mcp",
        ]:
            assert page.goto(BASE_URL + path).status == 200, path
            page.wait_for_timeout(300)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), path
        # Exercise the existing timer and CSV flow, including untrusted note text.
        page.goto(BASE_URL + "/timer")
        page.locator(".timer-button").first.click()
        page.wait_for_selector(".timer-button[data-running=true]")
        page.locator(".timer-notes").first.fill(
            '<img src=x onerror="window.agentNoteExecuted=true">'
        )
        page.wait_for_timeout(1100)
        page.locator(".timer-button").first.click()
        page.wait_for_selector(".timer-button[data-running=false]")
        page.goto(BASE_URL + "/entries")
        page.wait_for_function(
            "document.querySelector('#entries-container').textContent.includes('onerror')"
        )
        assert page.evaluate("window.agentNoteExecuted !== true")
        assert page.locator("#entries-container img").count() == 0
        page.goto(BASE_URL + "/timesheets")
        page.wait_for_selector("#client-select option:nth-child(2)", state="attached")
        page.locator("#client-select").select_option(str(fixture.client_id))
        page.get_by_role("button", name="Generate CSV").click()
        page.wait_for_selector("#success-message:not(.hidden)")
        with page.expect_download() as downloaded:
            page.get_by_role("button", name="Download", exact=True).first.click()
        assert downloaded.value.suggested_filename.endswith(".csv")
        # Client names with apostrophes remain editable before and after reload.
        page.goto(BASE_URL + "/settings")
        page.locator("#add-client-btn").click()
        page.locator("#client-name-input").fill("Mira's Studio")
        page.locator("#client-rate-input").fill("120")
        page.get_by_role("button", name="Save", exact=True).click()
        page.wait_for_selector("#client-form", state="hidden")
        page.locator("[data-edit-client]").last.click()
        assert page.locator("#client-name-input").input_value() == "Mira's Studio"
        page.get_by_role("button", name="Cancel", exact=True).click()
        page.reload()
        page.locator("[data-edit-client]").last.click()
        assert page.locator("#client-name-input").input_value() == "Mira's Studio"
        page.get_by_role("button", name="Cancel", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        for path, label in [
            ("/work", "work"),
            ("/timer", "timers"),
            ("/entries", "entries"),
            ("/timesheets", "timesheets"),
            ("/settings", "settings"),
            ("/guides/mcp", "guide"),
        ]:
            assert page.goto(BASE_URL + path).status == 200, path
            page.wait_for_timeout(400)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), path
            page.screenshot(
                path="/tmp/timerrr-screenshots/" + label + "-mobile.png", full_page=True
            )
        page.goto(BASE_URL + "/logout")
        page.goto(BASE_URL + "/")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path="/tmp/timerrr-screenshots/home-mobile.png", full_page=True)
        print("Browser flow completed; page errors:", errors)
        assert not errors
        browser.close()
finally:
    fixture.tearDownClass()
