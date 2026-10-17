from typing import TYPE_CHECKING

from contracts.mcp import McpToolInfo, McpToolResult

if TYPE_CHECKING:
    from modules.mcp_gateway.service import McpGatewayService


class McpGatewayClient:
    def __init__(self, service: "McpGatewayService") -> None:
        self._service = service

    async def list_tools(self) -> list[McpToolInfo]:
        return await self._service.list_tools()

    async def call_tool(self, name: str, arguments: dict) -> McpToolResult:
        return await self._service.call_tool(name, arguments)
