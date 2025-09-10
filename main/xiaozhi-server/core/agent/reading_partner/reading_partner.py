import asyncio

from ...utils.dialogue import Dialogue
from core.agent.base import Agent
from core.agent.reading_partner.prompts import PROMPT
from core.agent.reading_partner.reading_partner_functions import exit_agent

TAG = "ReadingPartner"

class ReadingPartner(Agent):
    functions: dict = {
        "exit_agent": exit_agent
    }
    
    @property
    def prompt(self) -> str:
        return PROMPT

    @property 
    def get_agent_name(self) -> str:
        return "reading_partner"

    @property 
    def get_desc(self) -> str:
        return {
                "type": "function",
                "function": {
                    "name": "reading_partner",
                    "description": (
                        "陪伴阅读的方法，可以陪伴用户读书。"
                        "当用户说'进入伴读模式'、'陪我读书'、'一起读书'时调用该智能体。"
                        "提供阅读指导、讨论书籍内容、回答阅读相关问题。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
    
    def _get_functions(self):
        """定义伴读相关的工具函数"""
        return [
            self.get_exit_agent_function_desc("伴读")
        ]

    def _handle_memory(self, dialogue: Dialogue, **kwargs):
        """处理记忆相关逻辑"""
        # 使用智能体自己的记忆管理
        last_user_message = next(
            (msg for msg in reversed(dialogue.dialogue) if msg.role == "user"), None
        )
        if last_user_message and self.memory:
            future = asyncio.run_coroutine_threadsafe(
                self.memory.query_memory(last_user_message.content, limit=3), self.conn.loop
            )
            knowledge = future.result()
            self.logger.bind(tag=TAG).info(
                f"knowledge={knowledge}"
            )
            return knowledge
        return None
    
    def _generate(self, dialogue: Dialogue, **kwargs):
        """生成响应 - 支持function calling模式"""
        memory = kwargs.get("memory", None)
        print(f"记忆：{memory}")
        
        functions = self._get_functions()
        yield from self._generate_with_functions(dialogue, functions, **kwargs)

    def _suggest_generate(self, dialogue: Dialogue):
        pass