from contracts.mcp import McpToolInfo, McpToolResult
from modules.mcp_gateway.errors import McpNotConfiguredError


class McpGatewayService:
    async def list_tools(self) -> list[McpToolInfo]:
        raise McpNotConfiguredError("no MCP servers configured in base")

    async def call_tool(self, name: str, arguments: dict) -> McpToolResult:
        raise McpNotConfiguredError("no MCP servers configured in base")
