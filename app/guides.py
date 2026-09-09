"""Public, server-rendered product explanations and a functional calculator."""

from flask import Blueprint, abort, current_app, render_template, send_from_directory

guides = Blueprint("guides", __name__)
PAGES = {
    "parallel-time": (
        "Parallel agent time calculator",
        "Calculate elapsed time, agent-minutes, and human effort when people and agents work in parallel.",
    ),
    "mcp": (
        "Connect an agent to Timerrr with MCP",
        "Set up the Timerrr MCP bridge, record work receipts, enforce execution budgets, and draft human time for review.",
    ),
    "agent-timekeeping": (
        "Human effort, agent execution, and billable time",
        "How Timerrr separates human effort from agent execution and waiting, with reviewable work receipts and timesheet drafts.",
    ),
}


@guides.get("/guides/<slug>")
def guide(slug):
    if slug not in PAGES:
        abort(404)
    title, description = PAGES[slug]
    return render_template(
        "guide.html", slug=slug, page_title=title, description=description
    )


@guides.get("/agent-setup/prompt.md")
def agent_setup_prompt():
    return send_from_directory(
        current_app.static_folder, "agent-setup/prompt.md", mimetype="text/markdown"
    )
