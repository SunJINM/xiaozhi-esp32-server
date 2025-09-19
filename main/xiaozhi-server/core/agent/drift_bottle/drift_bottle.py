import re
from typing import Dict, Any, Optional
from core.agent.base import Agent
from core.connection import ConnectionHandler
from core.utils.dialogue import Dialogue, Message
from core.agent.drift_bottle.drift_bottle_functions import (
    get_user_status,
    throw_bottle,
    catch_bottle,
    get_pending_replies,
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
        "get_pending_replies": get_pending_replies,
        "reply_to_bottle": reply_to_bottle,
        "exit_agent": exit_agent
    }


    @property 
    def get_agent_name(self) -> str:
        return None
    
    @property
    def prompt(self) -> str:
        """系统提示词"""
        return DRIFT_BOTTLE_SYSTEM_PROMPT

    @property
    def get_desc(self) -> str:
        return {
                "type": "function",
                "function": {
                    "name": "drift_bottle",
                    "description": (
                        "玩漂流瓶的方法。当用户想要玩漂流瓶时调用。"
                        "当用户情绪低落时，可以询问是否要扔一个漂流瓶或捞一个漂流瓶。"
                        "用户说'玩漂流瓶'、'扔漂流瓶'、'捞漂流瓶'时调用此功能。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
    
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
                        "如果没有不知道用户要扔的内容，请询问用户"
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
                    "name": "get_pending_replies",
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
            self.get_exit_agent_function_desc("漂流瓶")
        ]

    def _generate(self, dialogue: Dialogue, **kwargs):
        """生成响应 - 使用function calling模式"""
        functions = self._get_drift_bottle_functions()
        yield from self._generate_with_functions(dialogue, functions, **kwargs)


    
    def _suggest_generate(self, dialogue: Dialogue):
        """生成建议"""
        pass