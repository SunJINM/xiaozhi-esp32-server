import json
from ...utils.dialogue import Dialogue
from core.agent.base import Agent
from core.agent.script_murder.prompts import system_prompt


class ScriptMurder(Agent):
    prompt: str = system_prompt


    def _generate(self, dialogue: Dialogue):
        dialogue_list = dialogue.dialogue
        if len(dialogue_list) is not None and len(dialogue_list) == 1:
            last_msg = dialogue_list[-1].content
            modify_msg = self.prompt + last_msg
            dialogue_list[-1].content = modify_msg
        return self.llm.response(self.session_id, dialogue.get_llm_dialogue())

