import re
from typing import Dict, Any, Optional
from core.agent.base import Agent
from core.connection import ConnectionHandler
from core.utils.dialogue import Dialogue, Message
from core.agent.drift_bottle.drift_bottle_functions import (
    get_user_status,
    throw_bottle,
    catch_bottle,
    listen_replies,
    reply_to_bottle,
    marked_listened,
    exit_agent
)
from .prompts import DRIFT_BOTTLE_SYSTEM_PROMPT
from .drift_bottle_api import DriftBottleAPI

TAG = "DriftBottle"

class DriftBottle(Agent):
    """漂流瓶智能体 - 基于工具调用的自主判断模式"""
    functions: dict = {
        "get_user_status": get_user_status,
        "throw_bottle": throw_bottle,
        "catch_bottle": catch_bottle,
        "listen_replies": listen_replies,
        "reply_to_bottle": reply_to_bottle,
        "exit_agent": exit_agent
    }
    
    @property
    def prompt(self) -> str:
        """系统提示词"""
        return DRIFT_BOTTLE_SYSTEM_PROMPT
    
    def _get_drift_bottle_functions(self):
        """定义漂流瓶相关的工具函数"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_user_status",
                    "description": (
                        "获取用户漂流瓶使用状态 - 当用户想要了解自己的漂流瓶使用情况时调用,比如自己创建的漂流瓶数量、自己漂流瓶被回复的数量等。"
                        "该方法每次只能获取当前用户的状态。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "throw_bottle",
                    "description": (
                        "扔漂流瓶 - 当用户想要分享心情、想法或故事时调用。"
                        "重要：每次调用只能扔一个瓶子，如果用户要扔多个瓶子，请告知用户每次只能扔一个瓶子。"
                        "不要尝试在一次调用中处理多个瓶子内容。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "单个漂流瓶的内容，只能包含一个瓶子的内容"
                            }
                        },
                        "required": ["content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "catch_bottle",
                    "description": "捞漂流瓶 - 当用户想要获取别人的漂流瓶、寻求陪伴或想看看别人的分享时调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "num": {
                                "type": "integer",
                                "description": "要捞的瓶子数量，可选值为1或5, 根据用户的要求判断，如果用户没有指定，则默认为1，如果用户指定超过5个，则默认为5"
                            }
                        },
                        "required": ["num"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "listen_replies",
                    "description": "收听回复 - 当用户想要查看自己扔出的漂流瓶收到的回复时调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "num": {
                                "type": "integer",
                                "description": "要查看的回复数量，可选值为1或5根据用户的要求判断，如果用户没有指定，则默认为1，如果用户指定超过5个，则默认为5"
                            }
                        },
                        "required": ["num"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reply_to_bottle",
                    "description": "回复漂流瓶 - 当用户想要回复刚捞到的漂流瓶时调用。需要先捞到瓶子才能回复。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bottle_id": {
                                "type": "integer",
                                "description": "要回复的漂流瓶ID，该参数从捞取的瓶子信息中获取"
                            },
                            "reply_content": {
                                "type": "string",
                                "description": "回复的内容"
                            }
                        },
                        "required": ["bottle_id", "reply_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "exit_agent",
                    "description": "退出 - 当用户想要退出漂流瓶或者不想玩漂流瓶时调用。重点关注用户是否有退出意图。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

    def _generate(self, dialogue: Dialogue):
        """生成响应 - 使用function calling模式"""
        try:
            # 定义可用的工具函数
            functions = self._get_drift_bottle_functions()
            
            # 更新系统消息
            dialogue_list = dialogue.dialogue
            if len(dialogue_list) < 4:
                dialogue.update_system_message(self.prompt)
            
            # 使用带function calling的LLM响应
            llm_response = self.llm.response_with_functions(
                self.session_id, 
                dialogue.get_llm_dialogue(), 
                functions
            )
            tool_call_flag = False
            function_arguments = ""
            function_name = ""
            function_id = ""
            for response in llm_response:
                content, tools_call = response
                if content is not None and len(content) > 0:
                    yield content, None

                if tools_call is not None:
                    tool_call_flag = True
                    if tools_call[0].id is not None:
                        function_id = tools_call[0].id
                    if tools_call[0].function.name is not None:
                        function_name = tools_call[0].function.name
                    if tools_call[0].function.arguments is not None:
                        function_arguments += tools_call[0].function.arguments
            
            if tool_call_flag:
                self.logger.bind(tag=TAG).debug(
                    f"function_name={function_name}, function_id={function_id}, function_arguments={function_arguments}"
                )
                function_call_data = {
                    "name": function_name,
                    "id": function_id,
                    "arguments": function_arguments,
                }
                result = self.handle_function_call(function_call_data)
                yield from self.handle_agent_function_result(result, function_call_data)
                
        except Exception as e:
            raise e
            return self._handle_error(f"处理对话时发生错误: {str(e)}")


    
    def _suggest_generate(self, dialogue: Dialogue):
        """生成建议"""
        pass