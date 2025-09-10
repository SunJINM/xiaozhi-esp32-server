
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import ContentType

TAG = __name__
logger = setup_logging()


GET_CLASS_INFO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_homework_info",
        "description": (
            "获取用户作业信息，当用户问起作业的时候，调用此函数，查询老师最近布置给用户的作业！"
        ),
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
        }
    }
}


@register_function('get_homework_info', GET_CLASS_INFO_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_homework_info(conn, function_args=None):
    """
    获取用户作业信息
    """
    text = "正在为您查询作业"
    conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=text)

    return ActionResponse(Action.REQ_USER_LLM, "tools_get_user_homework", None)
