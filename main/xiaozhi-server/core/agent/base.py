from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import json
from pydantic import BaseModel, ConfigDict, model_validator
from config.settings import load_config, check_config_file
from config.logger import setup_logging
from core.providers.llm.base import LLMProviderBase
from core.utils.dialogue import Message, Dialogue
from core.user import User
from plugins_func.register import ActionResponse, Action

TAG = "Agent"


class Agent(ABC, BaseModel):
    session_id: str
    llm: LLMProviderBase
    user: User
    conn: Any
    logger: Any = setup_logging()
    functions: dict = {}

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
    def prompt(self) -> str:
        """系统提示词"""
        pass

    @abstractmethod
    def _generate(self, dialogue: Dialogue):
        pass

    @abstractmethod
    def _suggest_generate(self, dialogue: Dialogue):
        pass

    def generate(self, dialogue: Dialogue):
        self.conn.logger.bind(tag=TAG).debug(
            f"智能体收到消息：{dialogue.get_llm_dialogue()}"
        )
        return self._generate(dialogue)
    
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
                yield text, None
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
                yield text, None
                self.conn.agent_dialogue.put(Message(role="assistant", content=text))
        else:
            pass
    
    def _handle_error(self, error_msg: str) -> str:
        """处理错误 - 公共方法"""
        return f"出现了一点小问题\n\n要不要再试一次？"
















