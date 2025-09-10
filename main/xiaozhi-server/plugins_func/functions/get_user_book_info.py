
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()


GET_CLASS_INFO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_user_book_info",
        "description": (
            "获取用户最近的阅读书籍，当用户询问起自己最近阅读哪些书时，调用此工具！"
        ),
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
        }
    }
}


@register_function('get_user_book_info', GET_CLASS_INFO_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_user_book_info(function_args=None):
    """
    获取用户作业信息
    """
    return ActionResponse(Action.REQ_USER_LLM, "tools_get_user_book_info", None)
