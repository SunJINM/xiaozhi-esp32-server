from core.connection import ConnectionHandler
from plugins_func.register import ActionResponse, Action
from core.utils.dialogue import Message

def exit_agent(conn: ConnectionHandler, *args, **kwargs):
    """退出剧本杀智能体功能"""
    conn.current_agent = None
    self = kwargs.get("self", None)
    if self:
        self.save_agent_memory()
    conn.agent_dialogue.clear()
    res = "已退出剧本杀功能"
    conn.dialogue.put(Message(role="user", content=res))
    return ActionResponse(Action.RESPONSE, res, res)