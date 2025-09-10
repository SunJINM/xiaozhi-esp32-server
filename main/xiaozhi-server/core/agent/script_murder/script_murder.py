import json
from ...utils.dialogue import Dialogue
from core.agent.base import Agent
from core.agent.script_murder.prompts import system_prompt_1, suggest_prompt
from core.agent.script_murder.script_murder_functions import exit_agent

TAG = "ScriptMurder"

class ScriptMurder(Agent):
    suggest_prompt: str = suggest_prompt
    functions: dict = {
        "exit_agent": exit_agent
    }

    @property 
    def get_agent_name(self) -> str:
        return None

    @property
    def prompt(self) -> str:
        """系统提示词"""
        return system_prompt_1

    @property
    def get_desc(self) -> str:
        return {
                "type": "function",
                "function": {
                    "name": "script_murder",
                    "description": (
                        "玩剧本杀的方法。当用户无聊时，可以询问是否要玩剧本杀。"
                        "当用户想要玩游戏、玩剧本杀、或说'我想玩游戏'时调用此功能。"
                        "提供角色扮演类推理游戏体验。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
    
    def _get_script_murder_functions(self):
        """定义剧本杀相关的工具函数"""
        return [
            self.get_exit_agent_function_desc("剧本杀")
        ]

    def _generate(self, dialogue: Dialogue, **kwargs):
        """生成响应 - 支持function calling模式"""
        functions = self._get_script_murder_functions()
        yield from self._generate_with_functions(dialogue, functions, **kwargs)

    def _suggest_generate(self, dialogue: Dialogue):
        _prompt = suggest_prompt + dialogue.get_dialogue_str()

        _dialogue = [
                {"role": "system", "content": _prompt},
                {"role": "user", "content": "请生成指令"}
            ]
        return self.llm.response(self.session_id, _dialogue)