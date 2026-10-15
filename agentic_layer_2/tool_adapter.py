from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .audit import AuditLog, utc_now
from .config import settings
from .state import MAX_TOOL_CALLS

CUSTOM_CAPABILITIES = {
    "plot_status": "get_plot_status",
    "telemetry": "analyze_crop_telemetry",
    "calendar": "evaluate_calendar_window",
    "draft": "draft_advisory_for_approval",
}
HISTORY_CAPABILITIES = {"history": "read_query"}


class MCPToolError(RuntimeError):
    """A valid MCP response reported a tool/business error; retrying cannot help."""


def _decode(result: Any) -> Any:
    if getattr(result, "isError", False):
        raise MCPToolError("MCP returned a tool error")
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    chunks = [getattr(c, "text", "") for c in getattr(result, "content", [])]
    if len(chunks) == 1:
        try:
            return json.loads(chunks[0])
        except (ValueError, TypeError):
            return chunks[0]
    return chunks


class MCPTools:
    """Dynamically discovers and calls the two configured stdio MCP servers."""

    def __init__(self, audit: AuditLog):
        self.audit = audit
        self.contracts: dict[str, dict[str, Any]] = {}
        self.call_counts: dict[str, int] = {}
        self.cache: dict[str, tuple[float, Any, str]] = {}
        self._cache_lock = asyncio.Lock()
        self._failures: dict[str, int] = {}
        self._circuit_until: dict[str, float] = {}
        self.servers = {
            "agrimind": self._parameters(settings.agrimind_command, ["-m", "mcp_server.server"], Path.cwd()),
            "historical": self._parameters(
                settings.historical_command,
                ["-c", "import mcp_server_sqlite; mcp_server_sqlite.main()", "--db-path", str(settings.historical_db.resolve())],
                Path.cwd(),
            ),
        }

    @staticmethod
    def _parameters(command: str, args: list[str], cwd: Path) -> StdioServerParameters:
        if command:
            # Commands are intentionally supplied as one executable; argument contracts stay fixed.
            return StdioServerParameters(command=command, args=args, cwd=str(cwd), env=None)
        return StdioServerParameters(command=sys.executable, args=args, cwd=str(cwd), env=None)

    @asynccontextmanager
    async def _session(self, server: str) -> AsyncIterator[ClientSession]:
        async with stdio_client(self.servers[server]) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def discover(self) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for server in self.servers:
            async with self._session(server) as session:
                listing = await session.list_tools()
                tools = {tool.name: tool for tool in listing.tools}
                self.contracts[server] = {
                    name: getattr(tool, "inputSchema", {}) for name, tool in tools.items()
                }
                found[server] = list(tools)
        required = {
            "agrimind": set(CUSTOM_CAPABILITIES.values()),
            "historical": {"read_query"},
        }
        for server, names in required.items():
            missing = names - set(self.contracts.get(server, {}))
            if missing:
                raise RuntimeError(f"Required MCP capabilities missing from {server}: {sorted(missing)}")
        return found

    async def call(self, server: str, name: str, arguments: dict[str, Any], execution_id: str, thread_id: str, prior_count: int = 0) -> Any:
        self.call_counts[thread_id] = max(self.call_counts.get(thread_id, 0), prior_count)
        schema = self.contracts.get(server, {}).get(name)
        if schema is None:
            await self.discover()
            schema = self.contracts.get(server, {}).get(name)
        if schema is None:
            raise RuntimeError(f"Tool {name} was not discovered on {server}")
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
        if not set(arguments) <= set(props) or not required <= set(arguments):
            raise ValueError(f"Arguments do not satisfy discovered schema for {name}")
        cacheable = (server == "historical" and name == "read_query") or (
            server == "agrimind" and name in {"get_plot_status", "analyze_crop_telemetry", "evaluate_calendar_window"}
        )
        execution_scoped = name != "read_query"
        cache_key = json.dumps([server, name, arguments], sort_keys=True, separators=(",", ":"))
        cache_lock = self._cache_lock if cacheable else None
        if cacheable:
            assert cache_lock is not None
            await cache_lock.acquire()
            cached = self.cache.get(cache_key)
            valid_scope = cached is not None and (not execution_scoped or cached[2] == execution_id)
            if cached and valid_scope and time.monotonic() - cached[0] < 300:
                cached_value = cached[1]
                self.audit.write({"event": "mcp_cache_hit", "execution_id": execution_id, "thread_id": thread_id, "server": server, "tool": name, "inputs": arguments, "outputs": _redact(cached_value), "cache_hit": True, "external_call": False, "retries": 0})
                cache_lock.release()
                if execution_scoped and isinstance(cached_value, dict):
                    cached_value = dict(cached_value)
                    cached_value["_layer2_cache_hit"] = True
                return cached_value
            if cached:
                self.cache.pop(cache_key, None)
        started = time.monotonic()
        started_at = utc_now()
        retries = 0
        error = None
        output = None
        for attempt in range(3):
            if time.monotonic() < self._circuit_until.get(server, 0):
                error = "CIRCUIT_OPEN"
                break
            count = max(self.call_counts.get(thread_id, 0), prior_count)
            if count >= MAX_TOOL_CALLS:
                error = "MAX_TOOL_CALLS_EXCEEDED"
                break
            self.call_counts[thread_id] = count + 1
            try:
                async with self._session(server) as session:
                    result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=20)
                output = _decode(result)
                self._failures[server] = 0
                break
            except MCPToolError as exc:
                error = type(exc).__name__
                break
            except (TimeoutError, OSError, RuntimeError) as exc:
                error = type(exc).__name__
                self._failures[server] = self._failures.get(server, 0) + 1
                if self._failures[server] >= 3:
                    self._circuit_until[server] = time.monotonic() + 15
                if attempt >= 2 or name == CUSTOM_CAPABILITIES["draft"]:
                    break
                retries += 1
                await asyncio.sleep(0.15 * (2**attempt))
        self.audit.write({
            "event": "mcp_tool_call", "execution_id": execution_id, "thread_id": thread_id,
            "server": server, "tool": name, "inputs": _redact(arguments), "outputs": _redact(output),
            "started_at": started_at, "duration_ms": round((time.monotonic() - started) * 1000),
            "success": error is None, "error": error, "cache_hit": False, "retries": retries,
        })
        if cacheable and error is None:
            self.cache[cache_key] = (time.monotonic(), output, execution_id)
            if len(self.cache) > 256:
                oldest = min(self.cache, key=lambda key: self.cache[key][0])
                self.cache.pop(oldest, None)
        if cacheable:
            cache_lock.release()
        if error:
            if error == "MAX_TOOL_CALLS_EXCEEDED":
                raise RuntimeError(error)
            raise RuntimeError(f"MCP call failed: {server}.{name} ({error})")
        return output

    def count(self, thread_id: str) -> int:
        return self.call_counts.get(thread_id, 0)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if any(word in str(key).lower() for word in ("phone", "farmer", "household", "address", "email", "contact", "name")):
                safe[key] = "[REDACTED]"
            else:
                safe[key] = _redact(item)
        return safe
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
