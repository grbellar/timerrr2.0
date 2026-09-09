"""Official MCP SDK stdio server forwarding to Timerrr's scoped API.

Run with python -m agent_tools.server. Uses the pinned v1 SDK for broad
2025-11-25 host compatibility; transport changes stay outside Flask.
"""

import asyncio
import json
from pathlib import Path

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from agent_tools.client import TimerrrClient

server = Server("timerrr")
UI_URI = "ui://timerrr/work.html"
S = {"type": "string", "minLength": 1, "maxLength": 100}
ID = {"type": "integer", "minimum": 1}
WORK = {"work_id": ID}
ACTOR = {
    "actor_id": S,
    "actor_kind": {"type": "string", "enum": ["human", "agent", "waiting"]},
}
# Explicit keys make tool intent and replay behavior visible to the host.
DEFINITIONS = {
    "list_clients": ("List your clients and their IDs.", {}, [], False),
    "get_active_work": (
        "Read active work, separate effort totals, and lease/budget state. Follow next_before_id to paginate.",
        {"before_id": ID},
        [],
        False,
    ),
    "get_work": (
        "Read a work receipt, evidence, and budget. Recorded execution is not proof of human effort.",
        WORK,
        ["work_id"],
        False,
    ),
    "start_work": (
        "Start a client work session and its first actor. Agent execution must heartbeat every 30 seconds; the 120-second lease bounds accounting. budget_seconds limits elapsed agent execution from session start. Reuse request_id only for retries of identical arguments.",
        {
            "client_id": ID,
            "title": {"type": "string", "minLength": 1, "maxLength": 300},
            "budget_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
            **ACTOR,
            "request_id": S,
        },
        [
            "client_id",
            "title",
            "budget_seconds",
            "actor_id",
            "actor_kind",
            "request_id",
        ],
        True,
    ),
    "record_work_event": (
        "Record actor_started, actor_stopped, heartbeat, note, or artifact. Starting requires actor_id and actor_kind; stopping/heartbeat requires actor_id; note/artifact requires text, and artifact also requires url. Heartbeats after expiry return continue_work=false. Never infer human hours from artifacts. Reuse request_id for retries.",
        {
            **WORK,
            **ACTOR,
            "kind": {
                "type": "string",
                "enum": [
                    "actor_started",
                    "actor_stopped",
                    "heartbeat",
                    "note",
                    "artifact",
                ],
            },
            "text": {"type": "string", "maxLength": 4000},
            "url": {"type": "string", "maxLength": 2000},
            "request_id": S,
        },
        ["work_id", "kind", "request_id"],
        True,
    ),
    "finish_work": (
        "Finish the whole session, close all actors, and attach a summary. Does not bill any time. Reuse request_id for retries.",
        {**WORK, "summary": {"type": "string", "maxLength": 4000}, "request_id": S},
        ["work_id", "request_id"],
        True,
    ),
    "draft_timesheet": (
        "Draft human time from finished, unapproved sessions fully inside an ISO timestamp range (max 93 days). Includes receipts and uncertainty. Approval is only available on the Timerrr website. Reuse request_id for retries.",
        {"start_time": S, "end_time": S, "request_id": S},
        ["start_time", "end_time", "request_id"],
        True,
    ),
    "get_draft": (
        "Read a timesheet draft and its human review outcome.",
        {"draft_id": ID},
        ["draft_id"],
        False,
    ),
}


@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name=name,
            description=description,
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            annotations=types.ToolAnnotations(
                readOnlyHint=not write,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            **(
                {"_meta": {"ui": {"resourceUri": UI_URI}}}
                if name in ("get_active_work", "get_work")
                else {}
            ),
        )
        for name, (description, properties, required, write) in DEFINITIONS.items()
    ]


@server.call_tool()
async def call_tool(name, arguments):
    if name not in DEFINITIONS:
        raise ValueError("Unknown tool.")
    result = await asyncio.to_thread(
        TimerrrClient().call, name, arguments, DEFINITIONS[name][3]
    )
    # Return structured data for the MCP App and text for hosts without Apps.
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(result))],
        structuredContent=result,
    )


@server.list_resources()
async def list_resources():
    return [
        types.Resource(
            uri=UI_URI, name="Timerrr work card", mimeType="text/html;profile=mcp-app"
        )
    ]


@server.read_resource()
async def read_resource(uri):
    if str(uri) != UI_URI:
        raise ValueError("Unknown resource.")
    from mcp.server.lowlevel.helper_types import ReadResourceContents

    return [
        ReadResourceContents(
            content=Path(__file__).with_name("work_app.html").read_text(),
            mime_type="text/html;profile=mcp-app",
            meta={
                "ui": {
                    "prefersBorder": True,
                    "csp": {"connectDomains": [], "resourceDomains": []},
                }
            },
        )
    ]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
