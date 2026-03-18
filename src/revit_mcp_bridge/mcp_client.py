"""MCP client that connects over HTTP+SSE."""

import asyncio
import json
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

        # Persistent SSE connection state
        self._sse_response: httpx.Response | None = None
        self._sse_task: asyncio.Task | None = None
        self._pending_requests: dict[int, asyncio.Queue] = {}
        self._sse_connected = asyncio.Event()
        self._request_counter = 0
        self._closed = False

    async def connect(self) -> None:
        """Connect to MCP server and establish persistent SSE session."""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._closed = False

        # Open persistent SSE connection
        sse_url = f"{self.base_url}/sse"

        try:
            # Use send() with stream=True to get a response we can keep open
            request = self._client.build_request("GET", sse_url)
            self._sse_response = await self._client.send(request, stream=True)

            if self._sse_response.status_code != 200:
                raise MCPError(
                    f"Failed to connect to MCP server: HTTP {self._sse_response.status_code}"
                )

            # Wait for the endpoint event to get session info
            event_type = None
            async for line in self._sse_response.aiter_lines():
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

                        # Start background task to read SSE events
                        self._sse_task = asyncio.create_task(self._read_sse_loop())
                        return

            raise MCPError("Did not receive endpoint event from MCP server")

        except httpx.ConnectError as e:
            await self._cleanup()
            raise MCPError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            await self._cleanup()
            raise MCPError(f"Connection timeout: {e}") from e
        except Exception:
            await self._cleanup()
            raise

    async def _read_sse_loop(self) -> None:
        """Background task that continuously reads SSE events."""
        event_type = None

        try:
            async for line in self._sse_response.aiter_lines():
                if self._closed:
                    break

                line = line.strip()

                if not line:
                    # Empty line marks end of event
                    event_type = None
                    continue

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()

                    # Ignore heartbeat events
                    if event_type == "heartbeat":
                        continue

                    # Handle message events (responses)
                    if event_type == "message" and data:
                        try:
                            response_data = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        # Route response to the waiting request
                        request_id = response_data.get("id")
                        if request_id is not None and request_id in self._pending_requests:
                            queue = self._pending_requests[request_id]
                            await queue.put(response_data)

        except Exception:
            # SSE connection closed or errored
            pass
        finally:
            # Signal to any waiting requests that the connection is dead
            for queue in self._pending_requests.values():
                await queue.put(None)

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
        """Send JSON-RPC request and wait for response via existing SSE connection."""
        if not self._client or not self.message_endpoint:
            raise MCPError("Not connected to MCP server")

        if not self._sse_response or self._sse_response.is_closed:
            raise MCPError("SSE connection is closed")

        # Generate unique request ID
        self._request_counter += 1
        request_id = self._request_counter

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Create queue for this request's response
        response_queue: asyncio.Queue = asyncio.Queue()
        self._pending_requests[request_id] = response_queue

        try:
            # POST the request to the message endpoint
            post_url = urljoin(self.base_url + "/", self.message_endpoint)

            response = await self._client.post(
                post_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200 and response.status_code != 202:
                raise MCPError(
                    f"Request failed: HTTP {response.status_code} - {response.text}"
                )

            # Wait for response on the SSE stream
            try:
                response_data = await asyncio.wait_for(
                    response_queue.get(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                raise MCPError(f"Timeout waiting for response to {method}")

            # None means SSE connection died
            if response_data is None:
                raise MCPError("SSE connection closed while waiting for response")

            # Check for JSON-RPC error
            if "error" in response_data:
                error = response_data["error"]
                raise MCPError(
                    message=error.get("message", "Unknown error"),
                    code=error.get("code"),
                    data=error.get("data"),
                )

            return response_data.get("result", {})

        except httpx.ConnectError as e:
            raise MCPError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise MCPError(f"Request timeout: {e}") from e
        finally:
            # Clean up the pending request
            self._pending_requests.pop(request_id, None)

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._closed = True

        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
            self._sse_task = None

        if self._sse_response:
            await self._sse_response.aclose()
            self._sse_response = None

        if self._client:
            await self._client.aclose()
            self._client = None

        self.session_id = None
        self.message_endpoint = None
        self._initialized = False
        self._pending_requests.clear()

    async def close(self) -> None:
        """Close the connection."""
        await self._cleanup()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()
