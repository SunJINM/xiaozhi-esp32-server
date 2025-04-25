
import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()


GET_CLASS_INFO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_class_info",
        "description": (
            "获取班级信息的方法"
            "用户可以获取班级的学生人数、班主任信息"
        ),
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
        }
    }
}

def fetch_class_info(cookie):
    """ 
    获取书本信息
    """
    url = "http://rest.xxt.cn/user-data-v2/internal/get-class-teachers-job-share-internal"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json"
    }

    data = {
        "classId": 923001
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

@register_function('get_class_info', GET_CLASS_INFO_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_class_info(conn, lang: str = "zh_CN"):
    """
    获取班级信息
    """
    cookie = "_did__=1721089245037909763081805454094; NTKF_T2D_CLIENTID=guestCC1202B0-D683-D52E-3B48-D1E4AF09D5B8; xxtSessionId=2c65a62609b9d2cff6aba0454c673c935a3ea838; _PROV_CODE=1; _PROV_CHNG=true; _TSVID__=ae47ae1b6a3244389823d047125e852b; apt.uid=AP-YFGMCGUNNIFB-2-1744603050738-32797871.0.2.6b933aba-006b-4c12-b4b5-a0ddc2adfcf4; _bgid__=x3qcUNUp7zgrUpAtLRQDRgyL6MlbpJJ3Lm8mJPvFeNkDhtJ6ezlED0DdNBl29agu"
    class_info = fetch_class_info(cookie)
    class_master = class_info.get("classMaster")
    teacher_name = class_master.get("teacherName")
    mobile = class_master.get("mobile")

    teacher_name = teacher_name if teacher_name is not None else "暂无班主任"

    # 构建详情报告
    detail_report = (
        f"根据下列数据，用{lang}回应用户的班级信息查询请求：\n\n"
        f"班主任: {teacher_name}\n"
        f"班主任手机号: {mobile}\n\n"
        f"(请对上述班级内容进行总结，根据用户问题提取关键信息，只需要回答与问题相关的信息即可，以自然、流畅的方式向用户播报，"
    )

    return ActionResponse(Action.REQLLM, detail_report, None)

