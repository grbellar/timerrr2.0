"""Optional standalone MCP App browser check with a simulated host."""

from pathlib import Path

from playwright.sync_api import sync_playwright

work = {
    "id": 42,
    "client_name": "Acme",
    "title": "Checkout fix",
    "human_seconds": 720,
    "agent_seconds": 1560,
    "elapsed_seconds": 2040,
    "budget_remaining_seconds": 60,
    "warnings": [],
    "finished_at": None,
}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 600, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content(
        '<iframe title="Timerrr" style="width:100%;height:750px;border:0"></iframe>'
    )
    page.evaluate(
        """(work) => {
 window.calls=[]; window.work=work;
 window.addEventListener('message', e => {
 const m=e.data; if(m.jsonrpc!=='2.0')return;
 if(m.method==='ui/initialize') {e.source.postMessage({jsonrpc:'2.0',id:m.id,result:{protocolVersion:'2026-01-26',hostInfo:{name:'test',version:'1'},hostCapabilities:{}}},'*');}
 if(m.method==='ui/notifications/initialized') {e.source.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:{work:window.work}}},'*');}
 if(m.method==='tools/call'){window.calls.push(m.params);if(m.params.name==='finish_work')window.work.finished_at='2026-09-08T12:00:00Z';e.source.postMessage({jsonrpc:'2.0',id:m.id,result:{content:[],structuredContent:{work:m.params.name==='get_active_work'?[window.work]:window.work}}},'*');}
 });
 }""",
        work,
    )
    page.locator("iframe").evaluate(
        "(el,html)=>el.srcdoc=html",
        Path(
            Path(__file__).resolve().parents[1] / "agent_tools/work_app.html"
        ).read_text(),
    )
    frame = page.frame_locator("iframe")
    frame.get_by_role("heading", name="Checkout fix").wait_for()
    frame.locator("input").fill("Tests passed; ready for review.")
    frame.get_by_role("button", name="Save note").click()
    page.wait_for_function(
        "window.calls.some(c=>c.name==='record_work_event')", timeout=3000
    )
    frame.get_by_role("button", name="Finish session").click()
    page.wait_for_function("window.calls.some(c=>c.name==='finish_work')")
    frame.get_by_text("Acme · #42 · Finished").wait_for()
    page.screenshot(path="/tmp/timerrr-screenshots/mcp-card.png", full_page=True)
    assert not errors, errors
    print(
        "MCP App host handshake, structured result rendering, note, finish, refresh passed."
    )
    browser.close()
