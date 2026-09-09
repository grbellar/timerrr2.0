# Agent timekeeping and MCP

Timerrr now separates client work into sessions, actor intervals, and source-labeled events. The browser and agent API use the same transactional service. Human-reviewed drafts create ordinary `TimeEntry` rows, so existing CSV timesheets continue to work.

## Run locally

```sh
uv sync --extra mcp
DATABASE_PATH=/tmp/timerrr-development.db uv run python run.py
```

Or install `requirements.txt` with pip for the web app, and `requirements-mcp.txt` for the optional local MCP bridge. The MCP dependency is pinned to the official Python SDK 1.26.0, using its 2025-11-25 stdio protocol. `uv.lock` includes the optional dependency. The web deployment does not need MCP installed.

Open `/work`, create a client if necessary, and start a human session. Create a token in Connections. Use the public `/guides/mcp` page for a complete host configuration with absolute paths to the Python executable and `mcp_server.py`.

The bridge reads `TIMERRR_URL` (default `https://timerrr.app`) and `TIMERRR_TOKEN`. Remote URLs require HTTPS; localhost can use HTTP. These variables belong in the local bridge/runner environment, not the Flask deployment. The bridge requires no database access. This is a stdio bridge backed by a bearer-authenticated application API, not a public remote MCP/OAuth server.

## Tools and permissions

| Tool | Scope | Behavior |
| --- | --- | --- |
| `list_clients` | `work:read` | Return owned client IDs and names |
| `get_active_work` | `work:read` | Active receipts, 50 per page; follow `next_before_id` |
| `get_work` | `work:read` | One receipt with actor intervals and evidence |
| `start_work` | `work:write` | Create a session and first actor |
| `record_work_event` | `work:write` | Start/stop actors, heartbeat, add notes/artifacts |
| `finish_work` | `work:write` | Close all actors and record a summary |
| `draft_timesheet` | `draft:write` | Propose recorded human intervals for review |
| `get_draft` | `work:read` | Read a draft and its review outcome |

Every mutation requires `request_id`. Retries must reuse the ID and exact arguments; changed arguments return 409. SQLite `BEGIN IMMEDIATE` serializes mutation checks and commits, and a unique user/request constraint protects replay. Tokens are random, hashed at rest, expire after 90 days, and are revocable. Account ownership and subscription access are checked for each request. Browser mutations and token management require a session-bound CSRF header. Tokens cannot approve drafts. The workspace remains available to revoke tokens even after account access expires.

`/api/agent/<tool_name>` accepts JSON over POST, including for reads. The website also uses `list_work`, `list_drafts`, and `approve_draft`. Private work/token responses use `Cache-Control: no-store`.

## Accounting rules

- Server-generated UTC timestamps define activity boundaries. Human corrections are explicit at review time.
- Elapsed time runs from session start to finish, including periods with no recorded actor.
- Human effort is the union of human intervals **within a session**. Cross-session overlaps are rejected during approval, rather than silently billed twice.
- Agent time sums each actor's recorded execution. Concurrent agent-minutes can exceed elapsed time.
- Waiting is explicitly recorded under a waiting actor and excluded from draft proposals. It is not inferred from missing events.
- Agent leases last up to 120 seconds. Renew every 30 seconds. Reads cap time at lease expiry even before the next mutation materializes the expiry event. A disconnected actor cannot resurrect its old span with a late heartbeat.
- The budget is an elapsed deadline measured from session start (1–86400 seconds), shared by all agents. It is not a pooled agent-minute or monetary budget. Human review may continue after the deadline.
- Execution is observed/reported command lifetime, not an attestation of productive CPU time. Artifact references are not fetched or independently verified, and never imply human hours.

## Runner

```sh
# Set TIMERRR_URL and TIMERRR_TOKEN in your environment first.
uv run --extra mcp python -m agent_tools.runner \
  --client-id 1 --title 'Checkout fix' --budget 1200 \
  -- python your_agent_task.py
```

`--work-id` joins an existing session and leaves it open after stopping the runner's own actor. `--artifact` adds a URL to the receipt. The runner starts a POSIX process group, renews leases in a background thread, stops execution on budget/lease expiry or API errors, and removes `TIMERRR_TOKEN` from the child environment. Cutoffs return exit code 124, interruptions 130, otherwise the child's exit code. It uses SIGTERM followed by SIGKILL, so termination can include a two-second grace period. The local monotonic deadline is conservatively bounded by server-reported remaining time.

This runner cannot stop remote jobs or commands deliberately escaping its process group. Those execution environments must implement their own enforcement. An MCP connection alone cannot force a host's agent to stop.

## Draft reconstruction and receipts

Drafts include only finished, unreviewed sessions fully contained in the chosen timezone-aware range, up to 93 days. They propose exact merged human intervals, carry source receipt snapshots and warnings, and do not guess hours from issues or commits. A session crossing a range boundary must be included using a wider range.

Users can adjust interval boundaries within the source session, edit notes, or exclude intervals. Approval is transactional, rejects overlaps with accepted rows and existing time entries, and marks all source sessions reviewed. Concurrent/repeated drafts cannot convert the same session twice. Exclusions finalize those sessions too. Further corrections use Entries. Review outcomes are appended to receipts; snapshots preserve the original evidence. Client deletion is blocked when work receipts reference the client.

MCP Apps-compatible hosts can render `ui://timerrr/work.html` from the read tools. The card uses the Apps JSON-RPC bridge to refresh totals, add notes, and finish a session. It does not contain a token or make direct network calls. Hosts without Apps receive text plus structured results. Host compatibility needs to be checked for each client; the resource does not imply universal UI support.

## AEO and design

The server-rendered homepage and three guide pages have canonical URLs, descriptions, structured data matching visible content, and sitemap entries. The parallel-time calculator has a textual explanation that remains useful without JavaScript. Public pages explain actual shipped behavior and limitations. Account pages are noindex and excluded from the sitemap. `robots.txt` is a crawler hint, not access control.

The shared design uses a quiet paper background, bordered work surfaces, tabular time, compact navigation, visible focus states, and status color. The landing page demonstrates a timer; the calculator demonstrates concurrency. No special AI ranking markup or ranking guarantees are assumed.

## Database and deployment

Six new tables are created additively by the existing `db.create_all()` startup path: `agent_tokens`, `work_sessions`, `work_spans`, `work_events`, `work_operations`, and `work_drafts`. Existing time entries and timesheets are unchanged. No new web environment variable or Stripe setting is required. Use the existing persistent `DATABASE_PATH` in deployment. Work mutation locking is SQLite-specific, matching the app's configured database; a future PostgreSQL migration needs equivalent transaction locking.

## Verification

```sh
python -m unittest discover -s tests -v
```

Tests use a temporary SQLite database, never the configured production database. Coverage includes access/scopes, CSRF, retry conflicts, parallel accounting, leases/budgets, draft conversion and overlap rejection, and public pages. Optional protocol and runner integration checks require `requirements-mcp.txt`; see `tests/test_agent_integration.py`.

Manual UI flow: start a human session, switch to waiting and back, attach a URL, finish, build a date-range draft, edit/exclude proposed rows, approve, and export from Timesheets. Check desktop and narrow mobile layouts. Stripe actions require separately configured test keys.

### Optional browser verification

```sh
pip install playwright
python -m playwright install chromium
python tests/browser_checks.py
python tests/mcp_app_checks.py
```

The first script provisions a disposable server/database, checks desktop and mobile layouts, approves a draft without losing timestamp precision, exercises original timer controls, checks note escaping, downloads a CSV, and edits a client name containing an apostrophe. The second uses a simulated MCP Apps host to check the UI handshake, receipt rendering, note saving, and finish control. Actual third-party host integration still depends on that host's extension support. Chromium may require its usual OS libraries and fonts.

Screenshots from the browser checks are available in [screenshots](screenshots/). Stripe billing was not exercised because test keys were not configured.
