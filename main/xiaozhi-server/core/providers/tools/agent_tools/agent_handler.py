"""Agent工具处理器"""

from typing import Dict, Any, List
from config.logger import setup_logging
from plugins_func.register import ActionResponse
from .agent_executor import AgentToolExecutor


class AgentToolHandler:
    """Agent工具处理器"""

    def __init__(self, conn):
        self.conn = conn
        self.logger = setup_logging()
        self.executor = AgentToolExecutor(conn)

    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return list(self.executor.agent_tools.keys())

    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """获取工具描述"""
        return self.executor.get_function_descriptions()

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ActionResponse:
        """执行工具"""
        return await self.executor.execute_tool(tool_name, arguments)

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定工具"""
        return self.executor.has_tool(tool_name)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": self.executor.get_tool_count(),
            "available_tools": self.get_available_tools()
        }