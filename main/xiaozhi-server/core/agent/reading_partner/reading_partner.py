import json
from ...utils.dialogue import Dialogue
from core.agent.base import Agent
from core.agent.reading_partner.prompts import PROMPT
from core.agent.reading_partner.reading_partner_functions import exit_agent

TAG = "ReadingPartner"

class ReadingPartner(Agent):
    prompt: str = PROMPT
    functions: dict = {
        "exit_agent": exit_agent
    }

    @property 
    def get_desc(self) -> str:
        return {
                "type": "function",
                "function": {
                    "name": "reading_partner",
                    "description": (
                        "当用户说进入伴读模式时，调用该智能体"
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
            {
                "type": "function",
                "function": {
                    "name": "exit_agent",
                    "description": "退出伴读智能体 - 当用户想要退出伴读功能时调用。注意要判断用户是否是要退出伴读功能。",
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
            functions = self._get_functions()
            dialogue_list = dialogue.dialogue
            if len(dialogue_list) < 4:
                dialogue.update_system_message(PROMPT)
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
                if self.conn.client_abort:
                    break
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
                yield from self.handle_agent_function_result(result, function_call_data)
                
        except Exception as e:
            return self._handle_error(f"处理对话时发生错误: {str(e)}")

    def _suggest_generate(self, dialogue: Dialogue):
        pass