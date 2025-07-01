"""Agent工具执行器"""

import asyncio
from typing import Dict, Any, List
from config.logger import setup_logging
from plugins_func.register import ActionResponse, Action
from ..base import ToolExecutor, ToolDefinition, ToolType


class AgentToolExecutor(ToolExecutor):
    """Agent工具执行器"""

    def __init__(self, conn):
        self.conn = conn
        self.logger = setup_logging()
        self.agent_tools = {}
        self._register_agent_tools()

    def _register_agent_tools(self):
        """注册agent工具"""
        try:
            # 注册漂流瓶工具
            self._register_tools()
            
            
            self.logger.info(f"已注册 {len(self.agent_tools)} 个Agent工具")
        except Exception as e:
            self.logger.error(f"注册Agent工具失败: {e}")

    def _register_tools(self):
        """注册漂流瓶工具"""
        try:
            SCRIPT_MURDER_DESC = {
                "type": "function",
                "function": {
                    "name": "script_murder",
                    "description": (
                        "当用户想要玩游戏或玩剧本杀时使用"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            DRIFT_BOTTLE_DESC = {
                "type": "function",
                "function": {
                    "name": "drift_bottle",
                    "description": (
                        "当用户想要玩漂流瓶时使用，或用户情绪低落时，可以询问是否扔一个漂流瓶"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }

            agent_models = {
                "script_murder": {
                    "type": "script_murder",
                    "description": SCRIPT_MURDER_DESC
                },
                "drift_bottle": {
                    "type": "drift_bottle",
                    "description": DRIFT_BOTTLE_DESC
                }
            }

            for agent_id, agent_config in agent_models.items():
                agent_tool_name = agent_config.get("type")
                desc = agent_config.get("description")
                self.agent_tools[agent_tool_name] = {
                    "function": agent_tool_name,
                    "description": desc
                }
            
        except ImportError as e:
            self.logger.warning(f"工具导入失败: {e}")
        except Exception as e:
            self.logger.error(f"注册工具失败: {e}")

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """获取工具定义列表"""
        definitions = []
        for tool_name, tool_info in self.agent_tools.items():
            definition = ToolDefinition(
                name=tool_name,
                description=tool_info["description"],
                tool_type=ToolType.AGENT_TOOLS
            )
            definitions.append(definition)
        return definitions

    def get_function_descriptions(self) -> List[Dict[str, Any]]:
        """获取函数描述列表"""
        return [tool_info["description"] for tool_info in self.agent_tools.values()]

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定工具"""
        return tool_name in self.agent_tools

    async def execute(self, conn, tool_name: str, arguments: Dict[str, Any]) -> ActionResponse:
        """执行工具调用（抽象方法实现）"""
        return await self.execute_tool(tool_name, arguments)

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取该执行器管理的所有工具（抽象方法实现）"""
        tools = {}
        for tool_name, tool_info in self.agent_tools.items():
            definition = ToolDefinition(
                name=tool_name,
                description=tool_info["description"],
                tool_type=ToolType.AGENT_TOOLS
            )
            tools[tool_name] = definition
        return tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ActionResponse:
        """执行工具"""
        try:
            if tool_name not in self.agent_tools:
                return ActionResponse(
                    action=Action.ERROR,
                    response=f"未找到工具: {tool_name}"
                )

            tool_function = self.agent_tools[tool_name]["function"]
            
            # 根据不同工具传递不同参数
            if tool_name in ["throw_bottle", "catch_bottle"]:
                # 漂流瓶工具需要user参数
                result = tool_function(user=self.conn.user, **arguments)
            elif tool_name == "exit_agent":
                # 剧本杀退出工具需要conn参数
                result = tool_function(conn=self.conn, **arguments)
            else:
                # 其他工具直接传递参数
                result = tool_function(**arguments)
            
            # 如果结果是协程，等待执行
            if asyncio.iscoroutine(result):
                result = await result
            
            return result
            
        except Exception as e:
            self.logger.error(f"执行Agent工具 {tool_name} 失败: {e}")
            return ActionResponse(
                action=Action.ERROR,
                response=f"执行工具失败: {str(e)}"
            )

    def get_tool_count(self) -> int:
        """获取工具数量"""
        return len(self.agent_tools)