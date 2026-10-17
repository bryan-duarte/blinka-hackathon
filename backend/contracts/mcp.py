from contracts._base import StrictModel


class McpToolInfo(StrictModel):
    name: str
    description: str


class McpToolResult(StrictModel):
    name: str
    content: str
