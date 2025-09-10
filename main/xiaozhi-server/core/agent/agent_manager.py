import os, json
import importlib
import pkgutil
from typing import Dict, Any, List
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType
from config.config_loader import get_project_dir
from config.manage_api_client import get_agent_models
from core.utils.dialogue import Message, Dialogue
from core.agent.base import Agent


class AgentManager:
    """管理多个Agent服务的集中管理器"""

    def __init__(self, conn) -> None:
        """
        初始化Agent管理器
        """
        self.conn = conn
        self.logger = setup_logging()
        self.agents: Dict[str, Agent] = {}
        self.tools = []
        # 自动导入智能体模块
        self.auto_import_agents()

    def auto_import_agents(self):
        """
        自动导入智能体模块
        扫描core/agent目录下的所有子目录，每个子目录代表一个智能体
        """
        try:
            # 获取agent目录的绝对路径
            agent_dir = os.path.join(get_project_dir(), "core", "agent")
            
            # 遍历agent目录下的所有子目录
            for item in os.listdir(agent_dir):
                item_path = os.path.join(agent_dir, item)
                # 只处理目录，且排除__pycache__等特殊目录
                if os.path.isdir(item_path) and not item.startswith("__"):
                    try:
                        # 尝试导入智能体模块
                        module_name = f"core.agent.{item}.{item}"
                        module = importlib.import_module(module_name)
                        
                        # 获取智能体类名（首字母大写）
                        agent_class_name = item.replace("_", " ").title().replace(" ", "")
                        
                        # 获取智能体类
                        agent_class = getattr(module, agent_class_name)
                        
                        # 将智能体类添加到agents字典中
                        self.agents[item] = agent_class
                        
                        self.logger.bind(tag=__name__).info(f"智能体模块 '{module_name}' 已加载")
                    except Exception as e:
                        self.logger.bind(tag=__name__).error(f"加载智能体模块 '{item}' 失败: {e}")
                        
        except Exception as e:
            self.logger.bind(tag=__name__).error(f"加载智能体模块失败: {e}")

    async def initialize_servers(self) -> None:
        """初始化所有智能体"""
        try:
            
            if self.conn.user is None:
                self.logger.bind(tag=__name__).warning("未绑定用户")
                return
                
            # 初始化智能体
            for agent_name, agent_class in self.agents.items():
                try:
                    agent = agent_class(
                        session_id=self.conn.session_id,
                        llm=self.conn.llm,
                        user=self.conn.user,
                        conn=self.conn,
                    )
                    
                    # 自动初始化智能体记忆管理
                    agent.init_memory()

                    self.agents[agent_name] = agent
                    self.logger.bind(tag=__name__).info(f"初始化智能体成功: {agent_name}")

                    # 注册智能体工具 
                    desc = {
                        "name": agent_name,
                        "desc": agent.get_desc
                    }
                    self.tools.append(desc)

                except Exception as e:
                    self.logger.bind(tag=__name__).error(
                        f"初始化智能体失败 {agent_name}: {e}"
                    )
            
        except Exception as e:
            self.logger.bind(tag=__name__).error(f"获取智能体配置失败: {e}")
    
    def _get_agent_class(self, agent_type: str):
        """
        获取智能体类
        
        Args:
            agent_type: 智能体类型
            
        Returns:
            智能体类
            
        Raises:
            ValueError: 不支持的智能体类型
        """
        try:
            # 尝试从agent目录下的对应子目录中导入智能体类
            module_name = f"core.agent.{agent_type}.{agent_type}"
            if module_name in importlib.sys.modules:
                module = importlib.sys.modules[module_name]
            else:
                module = importlib.import_module(module_name)
            
            # 获取智能体类名（首字母大写）
            agent_class_name = agent_type.replace("_", " ").title().replace(" ", "")
            
            # 获取模块中的Agent类
            agent_class = getattr(module, agent_class_name, None)
            if agent_class:
                return agent_class
            
            # 如果没有找到对应的类，返回基础Agent类
            self.logger.bind(tag=__name__).warning(f"未找到智能体类型 {agent_type} 的类 {agent_class_name}，使用默认Agent")
            return Agent
            
        except ImportError:
            self.logger.bind(tag=__name__).warning(f"未找到智能体类型 {agent_type}，使用默认Agent")
            return Agent

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有智能体的工具function定义
        Returns:
            List[Dict[str, Any]]: 所有工具的function定义列表
        """
        return self.tools

    def is_agent_tool(self, tool_name: str) -> bool:
        """检查是否是智能体工具
        Args:
            tool_name: 工具名称
        Returns:
            bool: 是否是智能体工具
        """
        self.logger.bind(tag=__name__).info(f"检查是否是智能体工具: {tool_name}")
        for tool in self.tools:
            if (
                tool.get("name") != None
                and tool.get("name") == tool_name
            ):
                return True
        return False

    async def aexecute_tool(self, tool_name: str, dialogue: Dialogue) -> Any:
        """执行工具调用
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        Returns:
            Any: 工具执行结果
        Raises:
            ValueError: 工具未找到时抛出
        """
        self.logger.bind(tag=__name__).info(
            f"执行智能体 {tool_name}"
        )
        for agent_name, agent in self.agents.items():
            if agent_name == tool_name:
                return agent.generate(dialogue)

        raise ValueError(f"未找到工具 {tool_name}")
    
    def execute_tool(self, tool_name: str, dialogue: Dialogue, **kwargs) -> Any:
        """执行工具调用
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        Returns:
            Any: 工具执行结果
        Raises:
            ValueError: 工具未找到时抛出
        """
        self.logger.bind(tag=__name__).info(
            f"执行智能体 {tool_name}"
        )
        for agent_name, agent in self.agents.items():
            if agent_name == tool_name:
                return agent.generate(dialogue, **kwargs)

        raise ValueError(f"未找到工具 {tool_name}")
    
    async def atool_suggest(self, tool_name: str, dialogue: Dialogue) -> Any:
        """执行工具调用建议
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        Returns:
            Any: 工具执行结果
        Raises:
            ValueError: 工具未找到时抛出
        """
        self.logger.bind(tag=__name__).info(
            f"执行智能体 {tool_name}"
        )
        for agent_name, agent in self.agents.items():
            if agent_name == tool_name:
                return agent.suggest_generate(dialogue)

        raise ValueError(f"未找到工具 {tool_name}")

    async def cleanup_all(self) -> None:
        """清理所有智能体"""
        for name, agent in self.agents.items():
            try:
                await agent.cleanup()
                self.logger.bind(tag=__name__).info(f"清理智能体成功: {name}")
            except Exception as e:
                self.logger.bind(tag=__name__).error(
                    f"清理智能体失败 {name}: {e}"
                )
        self.agents.clear()