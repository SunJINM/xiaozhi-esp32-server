import json
from ...utils.dialogue import Dialogue
from core.agent.base import Agent
from core.agent.script_murder.prompts import system_prompt_1, suggest_prompt


class ScriptMurder(Agent):
    prompt: str = system_prompt_1
    suggest_prompt: str = suggest_prompt


    def _generate(self, dialogue: Dialogue):
        dialogue_list = dialogue.dialogue
        if len(dialogue_list) is not None and len(dialogue_list) == 1:
            dialogue.update_system_message(self.prompt)
        return self.llm.response(self.session_id, dialogue.get_llm_dialogue())

    def _suggest_generate(self, dialogue: Dialogue):
        _prompt = suggest_prompt + dialogue.get_dialogue_str()

        _dialogue = [
                {"role": "system", "content": _prompt},
                {"role": "user", "content": "请生成三条指令"}
            ]
        return self.llm.response(self.session_id, _dialogue)