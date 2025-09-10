from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import asyncio
import json
import threading
from pydantic import BaseModel, ConfigDict, model_validator
from config.settings import load_config, check_config_file
from config.logger import setup_logging
from core.providers.llm.base import LLMProviderBase
from core.utils.dialogue import Message, Dialogue
from core.user import User
from plugins_func.register import ActionResponse, Action
from core.providers.memory.base import MemoryProviderBase

TAG = "Agent"


class Agent(ABC, BaseModel):
    session_id: str
    llm: LLMProviderBase
    user: User
    conn: Any
    logger: Any = setup_logging()
    functions: dict = {}
    memory: Optional[MemoryProviderBase] = None

    model_config = ConfigDict(
        extra='forbid',
        arbitrary_types_allowed=True
    )

    @model_validator(mode='before')
    def validate_environment(cls, values: Dict) -> Dict:
        if values["llm"] is None:
            raise ValueError("LLM必须初始化")
        return values

    @property
    @abstractmethod
    def get_desc(self) -> str:
        """智能体描述"""
        pass
    
    @property
    @abstractmethod
    def get_agent_name(self) -> str:
        """获取智能体名称"""
        pass
    
    def init_memory(self, memory_config: Dict[str, Any] = None):
        """初始化智能体记忆管理
        
        Args:
            memory_config: 记忆配置，如果为None则使用默认配置
        """
        try:
            from core.providers.memory.mem0ai.mem0ai import MemoryProvider
            
            # 使用智能体名称作为collection_name
            agent_name = self.get_agent_name
            if agent_name is None:
                self.memory = None
                return
            
            # 如果没有提供配置，使用默认配置
            if memory_config is None:
                memory_config = {"type": "mem0ai"}
            
            self.memory = MemoryProvider(
                config=memory_config,
                agent_name=agent_name
            )
            
            # 初始化记忆模块
            self.memory.init_memory(
                role_id=agent_name,
                llm=self.llm
            )
            
            self.logger.bind(tag="Agent").info(f"智能体 {agent_name} 记忆管理初始化成功")
            
        except Exception as e:
            self.logger.bind(tag="Agent").error(f"智能体记忆管理初始化失败: {str(e)}")
            self.memory = None

    @property
    @abstractmethod
    def prompt(self) -> str:
        """系统提示词"""
        pass

    @abstractmethod
    def _generate(self, dialogue: Dialogue, kwargs: Any = None):
        pass

    @abstractmethod
    def _suggest_generate(self, dialogue: Dialogue):
        pass
    
    def get_exit_agent_function_desc(self, agent_name: str):
        """获取退出智能体工具的标准描述"""
        return {
            "type": "function",
            "function": {
                "name": "exit_agent", 
                "description": f"退出{agent_name}功能 - 当用户想要退出{agent_name}或者不想继续使用时调用。注意要判断用户是否是要退出{agent_name}功能。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
    
    def _generate_with_functions(self, dialogue: Dialogue, functions: list, **kwargs):
        """通用的带函数调用的生成方法"""
        try:
            # 更新系统消息
            dialogue_list = dialogue.dialogue
            if len(dialogue_list) < 4:
                dialogue.update_system_message(self.prompt)
            
            # 处理记忆相关逻辑
            knowledge = None
            if hasattr(self, '_handle_memory'):
                knowledge = self._handle_memory(dialogue, **kwargs)
            
            # 获取记忆参数
            memory = kwargs.get("memory", None)
            
            # 使用带function calling的LLM响应
            llm_response = self.llm.response_with_functions(
                self.session_id,
                dialogue.get_agent_llm_dialogue(knowledge=knowledge, memory=memory) if knowledge or memory else dialogue.get_agent_llm_dialogue(),
                functions
            )
            
            tool_call_flag = False
            function_arguments = ""
            function_name = ""
            function_id = ""
            
            for response in llm_response:
                if hasattr(self.conn, 'client_abort') and self.conn.client_abort:
                    break
                    
                content, tools_call = response
                if content is not None and len(content) > 0:
                    yield content

                if tools_call is not None:
                    tool_call_flag = True
                    if tools_call[0].id is not None:
                        function_id = tools_call[0].id
                    if tools_call[0].function.name is not None:
                        function_name = tools_call[0].function.name
                    if tools_call[0].function.arguments is not None:
                        function_arguments += tools_call[0].function.arguments
            
            if tool_call_flag:
                self.logger.bind(tag=self.__class__.__name__).debug(
                    f"function_name={function_name}, function_id={function_id}, function_arguments={function_arguments}"
                )
                function_call_data = {
                    "name": function_name,
                    "id": function_id,  
                    "arguments": function_arguments,
                }
                # 使用基类的公共方法处理函数调用
                result = self.handle_function_call(function_call_data)
                yield from self.handle_agent_function_result(result, function_call_data)
                
        except Exception as e:
            yield self._handle_error(f"处理对话时发生错误: {str(e)}")

    def generate(self, dialogue: Dialogue, **kwargs):
        self.conn.logger.bind(tag=TAG).debug(
            f"智能体收到消息：{dialogue.get_agent_llm_dialogue()}"
        )
        return self._generate(dialogue, **kwargs)
    
    def suggest_generate(self, dialogue: Dialogue):
        return self._suggest_generate(dialogue)
    
    def handle_function_call(self, function_call: Dict[str, Any]) -> Optional[ActionResponse]:
        """处理函数调用 - 公共方法"""
        function_name = function_call.get("name")
        function_arguments = function_call.get("arguments")
        if isinstance(function_arguments, str):
            try:
                function_arguments = json.loads(function_arguments)
            except json.JSONDecodeError:
                return ActionResponse(action=Action.ERROR, result="参数格式错误，无法解析。")
        if not isinstance(function_arguments, dict):
            function_arguments = {}

        function_arguments["user"] = self.user
        function_arguments["conn"] = self.conn
        function_arguments["self"] = self
        
        # 调用对应的函数
        if function_name in self.functions:
            return self.functions.get(function_name)(**function_arguments)
        else:
            return ActionResponse(action=Action.NOTFOUND, result=f"未找到函数: {function_name}")
    
    def handle_agent_function_result(self, result: ActionResponse, function_call_data: Dict[str, Any]):
        """处理智能体函数调用结果 - 公共方法"""
        if result.action == Action.RESPONSE:
            text = result.response
            if text is not None and len(text) > 0:
                yield text
                self.conn.agent_dialogue.put(Message(role="assistant", content=text))
        elif result.action == Action.REQLLM: 
            text = result.result
            if text is not None and len(text) > 0:
                function_id = function_call_data["id"]
                function_name = function_call_data["name"]
                function_arguments = function_call_data["arguments"]
                self.conn.agent_dialogue.put(
                    Message(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": function_id,
                                "function": {
                                    "arguments": function_arguments,
                                    "name": function_name,
                                },
                                "type": "function",
                                "index": 0,
                            }
                        ],
                    )
                )

                self.conn.agent_dialogue.put(
                    Message(role="tool", tool_call_id=function_id, content=text)
                )
                yield from self._generate(self.conn.agent_dialogue)
        elif result.action == Action.NOTFOUND or result.action == Action.ERROR:
            text = result.result
            if text is not None and len(text) > 0:
                yield text
                self.conn.agent_dialogue.put(Message(role="assistant", content=text))
        else:
            pass
    
    def _handle_error(self, error_msg: str) -> str:
        """处理错误 - 公共方法"""
        return f"出现了一点小问题\n\n要不要再试一次？"


    def save_agent_memory(self):
        try:
            if self.conn.memory:
                self.logger.bind(tag=TAG).info(f"保存智能体记忆")
                # 使用线程池异步保存记忆
                def save_memory_task():
                    try:
                        # 创建新事件循环（避免与主循环冲突）
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            self.conn.memory.save_memory(self.conn.agent_dialogue.dialogue)
                        )
                    except Exception as e:
                        self.logger.bind(tag=TAG).error(f"保存记忆失败: {e}")
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass

                # 启动线程保存记忆，不等待完成
                threading.Thread(target=save_memory_task, daemon=True).start()
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"保存记忆失败: {e}")
















