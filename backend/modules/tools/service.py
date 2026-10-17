from langchain_core.tools import BaseTool

from modules.tools.hello_world import get_random_token, get_system_profile


class ToolsService:
    def hello_world_tools(self) -> list[BaseTool]:
        return [get_random_token, get_system_profile]
