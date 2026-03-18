# Revit MCP Bridge

A minimal CLI bridge that connects to a remote Revit MCP server over HTTP+SSE.

## Purpose

This bridge enables Linux-based tools (like OpenClaw) to communicate with a remote
Revit MCP server that exposes tools for interacting with Autodesk Revit.

## Installation

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install click httpx
```

## Configuration

Set the MCP server URL via environment variable:

```bash
export REVIT_MCP_URL="http://your-revit-server:8080"
```

Or pass it via the `--url` flag to any command.

## Usage

### Check server health

```bash
revit-mcp health
```

Output:
```json
{
  "protocol_version": "2024-11-05",
  "server_info": {
    "name": "copilot-for-revit",
    "version": "1.0.0"
  },
  "session_id": "abc123",
  "status": "healthy"
}
```

### List available tools

```bash
revit-mcp tools list
```

Output:
```json
{
  "tools": [
    {
      "name": "get_element",
      "description": "Get element by ID",
      "inputSchema": {...}
    }
  ]
}
```

### Call a tool

```bash
revit-mcp tools call get_element --args '{"elementId": 123456}'
```

Output:
```json
{
  "content": [
    {
      "type": "text",
      "text": "{...element data...}"
    }
  ]
}
```

## Error Handling

All errors are returned as JSON with an `error` field:

```json
{
  "error": true,
  "message": "Connection failed: ...",
  "code": null,
  "data": null
}
```

Common errors:
- **Connection failure**: Server is unreachable
- **Timeout**: Request took too long (use `--timeout` to adjust)
- **Invalid JSON args**: `--args` contains malformed JSON
- **MCP error**: Server returned an error (includes `code` and `data`)

## Options

- `--url, -u`: MCP server base URL (default: `http://localhost:8080`)
- `--timeout, -t`: Request timeout in seconds (default: 30)

## Architecture

```
┌─────────────────┐     HTTP+SSE      ┌────────────────────┐
│  revit-mcp CLI  │ ◄───────────────► │  Revit MCP Server  │
│    (Linux)      │                   │  (Windows/Revit)   │
└─────────────────┘                   └────────────────────┘
```

The bridge:
1. Opens a GET connection to `/sse`
2. Receives an `endpoint` event with the message URL
3. POSTs JSON-RPC requests to the message endpoint
4. Reads responses from the SSE stream

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Run directly
python -m revit_mcp_bridge.cli health
```
