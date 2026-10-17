# Tools Layer Implementation

## Overview

This fills in the stub tools module with two dummy `@tool`s. Together they prove the agent can call tools and read their structured results. `ToolsService` and `ToolsClient` expose them as a toolset.

## Files to Modify/Create

All paths are under `backend/`.

| File | Change |
|---|---|
| `contracts/tools.py` (new) | `RandomToken`, `SystemProfile` (StrictModel), as defined in `03-design.md`. |
| `modules/tools/hello_world.py` (new) | `get_random_token`, `get_system_profile`, plus their constants. |
| `modules/tools/service.py` | Replace the docstring-only class body with `hello_world_tools()`. |
| `modules/tools/__init__.py` | Keep exporting `ToolsService`. |
| `clients/tools.py` | Replace `async list_tools() -> list[str]` with `hello_world_tools() -> list["BaseTool"]`. `list_tools` has no callers, which a grep confirms. |

## Implementation Guidelines

The snippets below are orientative only.

```python
# modules/tools/hello_world.py
RANDOM_TOKEN_BYTES = 8
SYSTEM_PROFILE = SystemProfile(
    name="blinka",
    environment="diagnostics",
    version="0.1.0",
    capabilities=["chat", "invoice_ingestion", "payments"],
)


@tool("get_random_token")
async def get_random_token() -> dict:
    """Return a freshly generated random token and the UTC time it was generated."""
    random_token = RandomToken(
        token=secrets.token_hex(RANDOM_TOKEN_BYTES),
        generated_at=datetime.now(UTC).isoformat(),
    )
    return random_token.model_dump()


@tool("get_system_profile")
async def get_system_profile() -> dict:
    """Return the fixed profile of the Blinka system: name, environment, version, capabilities."""
    return SYSTEM_PROFILE.model_dump()
```

```python
# modules/tools/service.py
class ToolsService:
    def hello_world_tools(self) -> list[BaseTool]:
        return [get_random_token, get_system_profile]
```

```python
# clients/tools.py
class ToolsClient:
    def __init__(self, service: "ToolsService") -> None:
        self._service = service

    def hello_world_tools(self) -> list["BaseTool"]:
        return self._service.hello_world_tools()
```

- The tools are async and return `dict`, following `modules/payments/agent.py::execute_payment`.
- The tool names must match the names the `HELLO_WORLD_TASK` prompt mentions (module 01): `get_random_token` and `get_system_profile`.
- The docstrings become the tool descriptions the model sees, so they must stay.

## Dependencies

- `langchain_core.tools.tool` and `BaseTool`
- From the stdlib: `secrets` and `datetime.UTC`

## Integration Notes

- `container.py` already builds `tools = ToolsClient(ToolsService())`.
- Module 04 injects `tools` into `OrchestratorService` and calls `self._tools.hello_world_tools()`.
