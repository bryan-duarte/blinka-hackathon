# Stub Modules (Guardrails, MCP Gateway, Tools)

## Overview

Three seams with real contracts and pass-through/skeleton behavior: guardrails (pass-through `check()`), MCP gateway (skeleton), tools (skeleton seam). Enforcement/real implementations land later without changing any caller.

## Files to Create

### Guardrails (pass-through stub)

- `backend/modules/guardrails/__init__.py` — facade: `GuardrailsService`, `GuardrailRejectionError`, `GuardrailUnavailableError`
- `backend/modules/guardrails/errors.py`:

```python
class GuardrailRejectionError(Exception):      # -> 422 via app exception handler
    def __init__(self, verdict: GuardrailVerdict) -> None: ...
class GuardrailUnavailableError(Exception): ... # -> 503 (future: LLM screen down)
```

- `backend/modules/guardrails/service.py`:

```python
class GuardrailsService:
    def __init__(self, enforce: bool) -> None: ...     # BLINKA_GUARDRAILS_ENFORCE, default False
    async def check(self, request: GuardrailCheckRequest) -> GuardrailVerdict:
        # stub: always allowed ; when enforce flips True later, screens go here
        return GuardrailVerdict(allowed=True, violations=[])
```

- `backend/clients/guardrails.py` — `GuardrailsClient.check`.
- `contracts/guardrails.py` — per 03-design.md.

### MCP Gateway (skeleton)

- `backend/modules/mcp_gateway/__init__.py` — facade: `McpGatewayService`, `McpNotConfiguredError`
- `backend/modules/mcp_gateway/errors.py` — `McpNotConfiguredError`
- `backend/modules/mcp_gateway/service.py`:

```python
class McpGatewayService:
    async def list_tools(self) -> list[McpToolInfo]:
        raise McpNotConfiguredError("no MCP servers configured in base")
    async def call_tool(self, name: str, arguments: dict) -> McpToolResult:
        raise McpNotConfiguredError("no MCP servers configured in base")
```

- `backend/clients/mcp.py` — `McpGatewayClient.list_tools`, `call_tool`.
- `contracts/mcp.py` — `McpToolInfo(name: str, description: str)`, `McpToolResult(name: str, content: str)`.

### Tools (skeleton seam)

- `backend/modules/tools/__init__.py` — facade: `ToolsService`
- `backend/modules/tools/service.py` — `ToolsService` placeholder class (docstring: future home of the shared tool registry; `initiate_payments` currently lives inline in `modules/orchestrator/tools.py` and migrates here).
- `backend/clients/tools.py` — `ToolsClient` (constructor + pass-through `list_tools() -> list[str]` returning `[]` for now).

## Implementation Guidelines

- Every stub still: takes contracts in/out, has an errors module, a client, a facade — so callers are written against the FINAL shape today.
- `GuardrailRejectionError` handler in `api/app.py`: 422 with body `{"violations": [{"code", "message"}]}` — mirrors the reference repo's rejection contract.
- Do not add config plumbing for MCP servers yet (user: skeleton only).

## Dependencies

02-backend-skeleton (contracts/_base, container).

## Integration Notes

- `clients.guardrails` is called by chat routes + payments route (the 422 path is real even while the verdict is always allowed).
- `clients.mcp` and `clients.tools` exist in `Clients` so later wiring is additive.
