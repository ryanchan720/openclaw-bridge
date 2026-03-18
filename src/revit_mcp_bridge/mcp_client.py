"""MCP client that connects over HTTP+SSE."""

import json
import os
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs

import httpx


class MCPError(Exception):
    """Error from MCP server or protocol."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class MCPClient:
    """Client for connecting to MCP server over HTTP+SSE."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: str | None = None
        self.message_endpoint: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    async def connect(self) -> None:
        """Connect to MCP server and establish SSE session."""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(timeout=self.timeout)

        # Open SSE connection to get session
        sse_url = f"{self.base_url}/sse"

        try:
            async with self._client.stream("GET", sse_url) as response:
                if response.status_code != 200:
                    raise MCPError(
                        f"Failed to connect to MCP server: HTTP {response.status_code}"
                    )

                # Read SSE events until we get the endpoint event
                async for line in response.aiter_lines():
                    line = line.strip()

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()

                        if event_type == "endpoint" and data:
                            # Parse the message endpoint URL
                            self.message_endpoint = data
                            if "?" in data:
                                # Extract sessionId from query params
                                parsed = urlparse(data)
                                params = parse_qs(parsed.query)
                                if "sessionId" in params:
                                    self.session_id = params["sessionId"][0]
                            return
        except httpx.ConnectError as e:
            raise MCPError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise MCPError(f"Connection timeout: {e}") from e

        raise MCPError("Did not receive endpoint event from MCP server")

    async def initialize(self) -> dict:
        """Send initialize request to MCP server."""
        if not self.message_endpoint:
            await self.connect()

        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "revit-mcp-bridge",
                "version": "0.1.0",
            },
        })

        self._initialized = True
        return result

    async def tools_list(self) -> dict:
        """List available tools from MCP server."""
        if not self._initialized:
            await self.initialize()

        return await self._send_request("tools/list", {})

    async def tools_call(self, name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        if not self._initialized:
            await self.initialize()

        return await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })

    async def _send_request(self, method: str, params: dict) -> dict:
        """Send JSON-RPC request and wait for response via SSE."""
        if not self._client or not self.message_endpoint:
            raise MCPError("Not connected to MCP server")

        request_id = id(method)  # Simple ID generation
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # POST the request to the message endpoint
        post_url = urljoin(self.base_url + "/", self.message_endpoint)

        try:
            response = await self._client.post(
                post_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200 and response.status_code != 202:
                raise MCPError(
                    f"Request failed: HTTP {response.status_code} - {response.text}"
                )
        except httpx.ConnectError as e:
            raise MCPError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise MCPError(f"Request timeout: {e}") from e

        # Now read the response from SSE
        sse_url = f"{self.base_url}/sse"

        try:
            async with self._client.stream("GET", sse_url) as sse_response:
                if sse_response.status_code != 200:
                    raise MCPError(
                        f"Failed to read SSE response: HTTP {sse_response.status_code}"
                    )

                event_type = None
                async for line in sse_response.aiter_lines():
                    line = line.strip()

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()

                        if event_type == "message" and data:
                            try:
                                response_data = json.loads(data)
                            except json.JSONDecodeError as e:
                                raise MCPError(f"Invalid JSON response: {e}") from e

                            # Check if this is our response
                            if response_data.get("id") == request_id:
                                if "error" in response_data:
                                    error = response_data["error"]
                                    raise MCPError(
                                        message=error.get("message", "Unknown error"),
                                        code=error.get("code"),
                                        data=error.get("data"),
                                    )
                                return response_data.get("result", {})
        except httpx.ConnectError as e:
            raise MCPError(f"Connection failed while reading response: {e}") from e
        except httpx.TimeoutException as e:
            raise MCPError(f"Timeout waiting for response: {e}") from e

        raise MCPError("Did not receive response from MCP server")

    async def close(self) -> None:
        """Close the connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self.session_id = None
            self.message_endpoint = None
            self._initialized = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()
