"""CLI entrypoint for revit-mcp-bridge."""

import asyncio
import json
import os
import sys
from typing import Any

import click

from .mcp_client import MCPClient, MCPError


def get_base_url() -> str:
    """Get MCP server base URL from environment or default."""
    return os.environ.get("REVIT_MCP_URL", "http://localhost:8080")


def output_json(data: Any) -> None:
    """Output data as JSON to stdout."""
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def handle_error(error: Exception) -> None:
    """Handle and output error, then exit."""
    if isinstance(error, MCPError):
        output_json({
            "error": True,
            "message": str(error),
            "code": error.code,
            "data": error.data,
        })
    else:
        output_json({
            "error": True,
            "message": str(error),
        })
    sys.exit(1)


@click.group()
@click.option(
    "--url",
    "-u",
    envvar="REVIT_MCP_URL",
    help="Base URL of the MCP server (default: http://localhost:8080)",
)
@click.option(
    "--timeout",
    "-t",
    default=30.0,
    help="Request timeout in seconds (default: 30)",
)
@click.pass_context
def main(ctx: click.Context, url: str | None, timeout: float) -> None:
    """Revit MCP Bridge - Connect to remote Revit MCP server over HTTP+SSE."""
    ctx.ensure_object(dict)
    ctx.obj["url"] = url or get_base_url()
    ctx.obj["timeout"] = timeout


@main.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Check health by initializing connection to MCP server."""
    async def run() -> None:
        client = MCPClient(
            base_url=ctx.obj["url"],
            timeout=ctx.obj["timeout"],
        )
        try:
            async with client:
                result = await client.initialize()
                output_json({
                    "status": "healthy",
                    "session_id": client.session_id,
                    "server_info": result.get("serverInfo", {}),
                    "protocol_version": result.get("protocolVersion"),
                })
        except Exception as e:
            handle_error(e)

    asyncio.run(run())


@main.group()
def tools() -> None:
    """Interact with MCP tools."""
    pass


@tools.command("list")
@click.pass_context
def tools_list(ctx: click.Context) -> None:
    """List available tools from MCP server."""
    async def run() -> None:
        client = MCPClient(
            base_url=ctx.obj["url"],
            timeout=ctx.obj["timeout"],
        )
        try:
            async with client:
                result = await client.tools_list()
                output_json(result)
        except Exception as e:
            handle_error(e)

    asyncio.run(run())


@tools.command("call")
@click.argument("name")
@click.option(
    "--args",
    "-a",
    "args_json",
    default="{}",
    help="JSON arguments for the tool (default: {})",
)
@click.pass_context
def tools_call(ctx: click.Context, name: str, args_json: str) -> None:
    """Call a tool on the MCP server.

    NAME is the name of the tool to call.

    Example:
        revit-mcp tools call get_element --args '{"elementId": 123}'
    """
    # Parse JSON args
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as e:
        output_json({
            "error": True,
            "message": f"Invalid JSON arguments: {e}",
        })
        sys.exit(1)

    if not isinstance(arguments, dict):
        output_json({
            "error": True,
            "message": "Arguments must be a JSON object",
        })
        sys.exit(1)

    async def run() -> None:
        client = MCPClient(
            base_url=ctx.obj["url"],
            timeout=ctx.obj["timeout"],
        )
        try:
            async with client:
                result = await client.tools_call(name, arguments)
                output_json(result)
        except Exception as e:
            handle_error(e)

    asyncio.run(run())


if __name__ == "__main__":
    main()
