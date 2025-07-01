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
    def prompt(self) -> str:
        """系统提示词"""
        return system_prompt_1
    
    def _get_script_murder_functions(self):
        """定义剧本杀相关的工具函数"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "exit_agent",
                    "description": "退出剧本杀智能体 - 当用户想要退出剧本杀功能时调用。注意要判断用户是否是要退出剧本杀功能。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

    def _generate(self, dialogue: Dialogue):
        """生成响应 - 支持function calling模式"""
        try:
            # 检查是否需要使用工具函数
            functions = self._get_script_murder_functions()
            
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
                # 使用基类的公共方法处理函数调用
                result = self.handle_function_call(function_call_data)
                print(result)
                yield from self.handle_agent_function_result(result, function_call_data)
                
        except Exception as e:
            return self._handle_error(f"处理对话时发生错误: {str(e)}")

    def _suggest_generate(self, dialogue: Dialogue):
        _prompt = suggest_prompt + dialogue.get_dialogue_str()

        _dialogue = [
                {"role": "system", "content": _prompt},
                {"role": "user", "content": "请生成指令"}
            ]
        return self.llm.response(self.session_id, _dialogue)