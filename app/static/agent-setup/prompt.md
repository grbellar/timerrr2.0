# Set up Timerrr

Configure Timerrr for the user in their current agent environment. Timerrr tracks human effort, agent execution, and waiting separately. Use the user's existing account.

## 1. Check the environment

Identify the current agent host, its supported MCP configuration, Python availability, and any existing Timerrr connection. Reuse a working connection. The current Timerrr integration is a local stdio MCP server backed by an HTTPS API. A hosted remote MCP endpoint and OAuth login flow are not available.

If the host cannot run local stdio servers, explain that limitation and link to https://timerrr.app/guides/mcp. Do not configure the HTTPS application API as a remote MCP server.

## 2. Connect the account

The user signs in at https://timerrr.app/work#connections and creates a token with the permissions they want:

- `work:read`: list clients and read work receipts.
- `work:write`: start sessions and record work.
- `draft:write`: prepare timesheet drafts.

Tokens belong to the signed-in account, expire after 90 days, and can be revoked on the same page. An active trial or subscription is required to use the API.

Use the host's secure credential input or a local secret/environment configuration for `TIMERRR_TOKEN`. Do not ask the user to paste the token into the conversation, print it, or commit it. If secure credential input is unavailable, have the user enter it locally. Never ask for their Timerrr password.

## 3. Install the bridge

Source: https://github.com/grbellar/timerrr2.0

Reuse an existing Timerrr checkout, or clone that repository into an available local directory. Do not overwrite unrelated files. Use an isolated Python environment (Python 3.11 or newer) and install `requirements-mcp.txt`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.txt
```

On Windows, use the corresponding `.venv\Scripts\python.exe` path. If the environment already uses uv, `uv sync --extra mcp` is also supported and uses the project's Python requirement.

The bridge entry point is `mcp_server.py`. It does not need a local Flask server or database.

## 4. Configure the current host

Add a server named `timerrr` using the host's supported configuration format. Preserve other connections. Use absolute paths. For hosts using `mcpServers`, the shape is:

```json
{
  "mcpServers": {
    "timerrr": {
      "command": "/absolute/path/to/timerrr/.venv/bin/python",
      "args": ["/absolute/path/to/timerrr/mcp_server.py"],
      "env": {
        "TIMERRR_URL": "https://timerrr.app",
        "TIMERRR_TOKEN": "SET_LOCALLY_USING_SECURE_CREDENTIAL_INPUT"
      }
    }
  }
}
```

Use a secret reference or inherited environment variable instead of an inline token when the host supports it. Reload the MCP connection if required by the host.

## 5. Verify

Discover the Timerrr tools and call `list_clients`, then `get_active_work`. These are read-only. Do not create a sample client, work session, or billable entry to test setup.

Expected tools:

- `list_clients`
- `get_active_work`
- `get_work`
- `start_work`
- `record_work_event`
- `finish_work`
- `draft_timesheet`
- `get_draft`

Confirm setup only after an authenticated tool call succeeds. If verification fails, report the specific issue without exposing credentials. If the connection works but there are no clients, direct the user to https://timerrr.app/settings.

## Work tracking rules

Wait for the user to request work tracking. Never infer human hours from agent execution, artifact timestamps, or commits.

Every mutation requires a unique `request_id`. Retry uncertain requests with the same ID and identical arguments. Use distinct actor IDs for human, agent, and waiting activity. Agent execution uses a 120-second lease; renew it with a heartbeat every 30 seconds and stop when `continue_work` is false. The agent budget is an elapsed deadline from session start, shared across parallel actors.

A model remembering to call tools is not reliable execution enforcement. For a local command that must stop at its budget, use the provided POSIX runner with `TIMERRR_URL` and `TIMERRR_TOKEN` configured in its environment:

```sh
.venv/bin/python -m agent_tools.runner --client-id CLIENT_ID --title "Task" --budget 1200 -- COMMAND
```

Use actual values rather than the placeholders above. `--work-id` joins an existing session. Ordinary MCP calls cannot stop a remote agent process by themselves.

Finish sessions when work ends. Drafts propose recorded human intervals only. The user approves them on https://timerrr.app/work#review before they become time entries.

Reference: https://timerrr.app/guides/mcp
