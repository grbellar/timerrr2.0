"""Absolute-path entry point for local MCP hosts; no Flask/database import."""

import asyncio

from agent_tools.server import main

if __name__ == "__main__":
    asyncio.run(main())
