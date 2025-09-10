from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional, List

from httpx import Cookies
from pydantic import BaseModel, ConfigDict, Field
from zoneinfo import ZoneInfo
import httpx
import hashlib
from core.utils.api_config import api_config


class BookInfo(BaseModel):
    name: str
    author: str
    press: str

class UserBookRead(BaseModel):
    curBooks: List[BookInfo]
    hisBooks: List[BookInfo]
    
    @property
    def format_read_info(self) -> str:
        """返回格式化的阅读信息
        
        Returns:
            str: 格式化后的用户信息字符串
        """
        # result = "<用户信息>\n\n"
        # result += "姓名：茉莉\n"
        # result += "性别：女\n"
        # result += "年龄：12\n"
        result = "当前阅读："
        for book in self.curBooks:
            result += f"《{book.name}》\n"
        result += "最近阅读："
        for book in self.hisBooks:
            result += f"《{book.name}》\n"
        result += "\n"
        return result


class UserHomework(BaseModel):
    """
    用户作业，此处的字段相比于接口的返回值省略了许多
    只保留了部分关键字段，后续可以加上其他字段。
    """
    taskId: int = Field(description="任务ID，即作业ID，因为目前任务只有作业一种")
    taskName: str = Field(description="任务名称，即作业名称")
    taskContent: str = Field(description="作业内容")
    publishUserId: int = Field(description="作业发布人ID")
    publishUserType: int = Field(description="作业发布人类型，0为老师身份")
    publishUserName: str = Field(description="作业发布人名称")
    # 注意时区，此处是+0时区
    sendDate: datetime = Field(description="作业发布时间")
    endDate: Optional[datetime] = Field(description="作业结束时间")
    finishStatus: int = Field(description="作业完成状态，0 未完成 1已完成 2 已过期")
    remind: Optional[bool] = Field(default=True, description="作业是否已经提醒了（当前会话相关）")

    @property
    def format_homework_info(self) -> str:
        """返回格式化的作业信息

        Returns:
            str: 格式化后的用户信息字符串
        """
        result = "\n当前作业："
        try:
            if self.finishStatus != 0:
                # 如果不存在未完成的作业，则认为没有作业
                result += "无"
            else:
                result += "\n作业内容：" + self.taskContent
                result += "\n作业发布人：" + self.publishUserName
                zoneInfo = ZoneInfo("Asia/Shanghai")
                result += "\n作业发布时间：" + self.sendDate.astimezone(zoneInfo).strftime("%Y-%m-%d %H:%M:%S")
                if self.endDate is not None:
                    result += "\n作业结束时间：" + self.endDate.astimezone(zoneInfo).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(e)
        return result + "\n\n"

class ExamScore(BaseModel):
    """
    存储用户的考试成绩
    """
    examId: Optional[int] = Field(description="考试ID")
    examName: Optional[str] = Field(description="考试成绩")
    totalScoreRankRate: Optional[float] = Field(description="学生总分科目百分比排名")
    stuSubjectScoreList: Optional[List[StuSubjectScoreListItem]] = Field(description="学生各科成绩列表")

    @property
    def format_exam_score(self) -> str:
        """返回格式化的成绩信息

        Returns:
            str: 格式化后的用户信息字符串
        """
        result = "\n最近成绩："
        if self.examId is None:
            result += "无"
        else:
            result += "\n最近考试：" + self.examName
            result += "\n各科成绩："
            if self.stuSubjectScoreList is not None and len(self.stuSubjectScoreList) > 0:
                for e in self.stuSubjectScoreList:
                    result += "\n  " + e.subjectName + "：" + e.score + "；排名：" + str(e.rank)
            else:
                result += "\n  无"
        return result + "\n\n"

class StuSubjectScoreListItem(BaseModel):
    subjectId: Optional[int] = Field(description="学科ID")
    subjectName: Optional[str] = Field(description="学科名称")
    score: Optional[str] = Field(description="得分")
    rank: Optional[int] = Field(description="排名")
    classRankRate: Optional[float] = Field(description="百分比排名")
    rankChange: Optional[int] = Field(description="排名同上次相比")

class DeviceAuthInfo(BaseModel):
    """
    在获取cookie之前，需要先或者access token，此处保存了access token以及对应的设备信息
    走通逻辑的前提：
    1、设备编号
    2、设备编号对应的激活码
    3、设备关联虹软sdk
    """
    accessToken: Optional[str] = None
    schoolId: Optional[int] = None
    schoolBranchId: Optional[int] = None
    schoolName: Optional[str] = None
    groupId: Optional[int] = None
    groupName: Optional[str] = None
    city: Optional[str] = None
    expireDate: Optional[datetime] = None
    arcKey: Optional[str] = None


class User(BaseModel):
    user_type: Optional[int] = None
    """用户身份类型"""
    user_id: Optional[int] = None
    """用户编号"""
    user_name: Optional[str] = None
    """用户名"""
    group_id: Optional[int] = None
    """班级编号"""
    school_id: Optional[int] = None
    """学校编号"""
    read_info: Optional[UserBookRead] = None
    """作业信息"""
    homework_info: Optional[UserHomework] = None
    """考试成绩"""
    exam_score: Optional[UserHomework] = None
    """用户登录的cookie信息"""
    __cookies: Optional[Cookies] = None
    """cookie过期时间"""
    __cookie_expire_date: Optional[datetime] = None
    """包含access token"""
    device_auth_info: Optional[DeviceAuthInfo] = None
    """当前登录的用户所在的机器人的mac"""
    mac: Optional[str] = None

    model_config = ConfigDict(
        extra='forbid',
        arbitrary_types_allowed=True
    )

    def get_user_read_info(self) -> UserBookRead:
        """获取用户阅读信息
        
        Returns:
            UserBookRead: 包含当前在读和历史阅读的书籍信息
        """
        if self.read_info is not None:
            return self.read_info
        try:
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.book_reading_url}/robot/get-user-read-info',
                    json={
                        'userId': self.user_id,
                        'userType': int(self.user_type) if self.user_type else 1
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                self.read_info = UserBookRead(
                    curBooks=[BookInfo(**book) for book in data.get('curBooks', [])],
                    hisBooks=[BookInfo(**book) for book in data.get('hisBooks', [])]
                )
                return self.read_info
        except Exception:
            return UserBookRead(curBooks=[], hisBooks=[])
        

    @classmethod
    def get_robot_bind_user(cls, mac: str) -> Optional[User]:
        """获取机器人绑定用户信息

        Returns:
            Optional[User]: 用户实例，如果发生异常返回None
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.book_reading_url}/robot/get-robot-bind-user',
                    json={
                        'macAddress': mac
                    }
                )
                response.raise_for_status()
                data = response.json()
                return cls(
                    user_type=data.get('userType'),
                    user_id=data.get('userId'),
                    user_name=data.get('userName'),
                    group_id=data.get('groupId'),
                    school_id=data.get('schoolId'),
                    mac = mac,
                )
        except Exception as e:
            return None

    def get_user_homework(self):
        """
        获取用户的作业信息，目前只取1条数据
        """
        if self.homework_info is not None:
            return self.homework_info
        try:
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.task_center_url}/xiaozhi/get-task-details-by-internal',
                    json={
                        "search": {
                            "userId": self.user_id,
                            "userType": int(self.user_type) if self.user_type else 1,
                            "taskStatus": "1",
                            # "taskStatus": "2",
                            # "sendDate": "1736905342000"
                        },
                        "current": 1,
                        "pageSize": 1,
                    }
                )
                response.raise_for_status()
                data = response.json()
                resultList = data.get("resultList", [])
                if len(resultList) == 0:
                    print(f"未查询到作业: userId={self.user_id}, userType={self.user_type}")
                    return None
                result = resultList[0]
                self.homework_info = UserHomework(
                    taskId=result.get('taskId'),
                    taskName=result.get('taskName'),
                    taskContent=result.get('taskContent'),
                    publishUserId=result.get('publishUserId'),
                    publishUserType=result.get('publishUserType'),
                    publishUserName=result.get('publishUserName'),
                    sendDate=result.get('sendDate'),
                    endDate=result.get('endDate'),
                    finishStatus=result.get('finishStatus'),
                )
                return self.homework_info
        except Exception as e:
            print(e)
            return None

    def get_cookies(self):
        if self.__cookies is not None and self.__cookie_expire_date is not None:
            current_time = datetime.now()
            # 添加安全边际（提前5分钟刷新）
            safety_margin = 300  # 5分钟，单位秒
            expire_time_with_margin = self.__cookie_expire_date.timestamp() - safety_margin
            if current_time.timestamp() < expire_time_with_margin:
                return self.__cookies
        try:
            headers = {
                'Content-Type': 'application/json',
                'Device-Access-Token': self.get_access_token().accessToken,
            }
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.login_v2_url}/login/login-by-face-swiping',
                    json={
                        "userId": self.user_id,
                        "userType": int(self.user_type) if self.user_type else 1,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                print("登录后的用户：", response.text)
                self.__cookies = response.cookies
                # 新平台 redis session 过期设置的为 120*60s
                self.__cookie_expire_date = datetime.now() + timedelta(seconds=120 * 60)
                return self.__cookies
        except Exception as e:
            print(f"获取 cookie 异常：{e}")
            return None

    def get_access_token(self):
        if self.device_auth_info is not None and self.device_auth_info.expireDate is not None:
            # 判断是否在有效期内，如果不是，则需要重新请求
            current_time = datetime.now()
            # 添加安全边际（提前5分钟刷新）
            safety_margin = 300  # 5分钟，单位秒
            expire_time_with_margin = self.device_auth_info.expire_date.timestamp() - safety_margin
            if current_time.timestamp() < expire_time_with_margin:
                # 在有效期内（包含安全边际）
                return self.device_auth_info
        # 不存在、过期、即将过期的时候，均重新请求
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            device_no = self.mac
            credential = self.mac
            temp = device_no + credential
            sign = hashlib.sha1(temp.encode('utf-8')).hexdigest()
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.wisdom_url}/book-reading/device-auth',
                    json={
                        "deviceNo": device_no,
                        "sign": sign,
                        "timestamp": datetime.now().timestamp() * 1000,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                print("获取的设备信息：", response.text)
                access_token = response.json().get('accessToken')
                if access_token is None:
                    return None
                self.device_auth_info = DeviceAuthInfo.model_validate_json(response.text)
                return self.device_auth_info
        except Exception as e:
            print(f"获取access token 异常：{e}")
            return None

    def get_exam_score(self):
        """
        获取用户近1个月的成绩信息，此接口需要登录
        通过 get_cookies，可以获取cookie信息
        """
        if self.exam_score is not None:
            return self.exam_score
        try:
            # 带上cookie了
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.exam_score_url}/student-score/get-some-notice-exam-list',
                    json={},
                    cookies=self.get_cookies(),
                )
                response.raise_for_status()
                data = response.json()
                resultList = data.get("resultList")
                if resultList is None or len(resultList) == 0:
                    return None
                result = resultList[0]
                _exam_score = self.get_exam_detail(result.get('examId'))
                if _exam_score is not None:
                    _exam_score.examName = result.get('examName')
                return _exam_score
        except Exception as e:
            print(f"获取成绩 异常：{e}")
            return None

    def get_exam_detail(self, exam_id):
        try:
            # 带上cookie了
            with httpx.Client() as client:
                response = client.post(
                    f'{api_config.exam_score_url}/student-score/get-stu-exam-analysis',
                    json={
                        "examId": exam_id,
                    },
                    cookies=self.get_cookies(),
                )
                response.raise_for_status()
                data = response.json()
                total_score_rank_rate = data.get("totalScoreRankRate")
                _exam_score = ExamScore(examId=exam_id, examName = None,
                                        totalScoreRankRate=total_score_rank_rate, stuSubjectScoreList= None)
                stu_subject_score_list = data.get("stuSubjectScoreList")
                if stu_subject_score_list is None or len(stu_subject_score_list) == 0:
                    return _exam_score
                items = []
                print(data)
                for stu_subject_score in stu_subject_score_list:
                    item =  StuSubjectScoreListItem(subjectId=stu_subject_score.get('subjectId'),
                                                   subjectName=stu_subject_score.get('subjectName'),
                                                   score=stu_subject_score.get('score'),
                                                   rank=stu_subject_score.get('rank'),
                                                   classRankRate=stu_subject_score.get('classRankRate'),
                                                   rankChange=stu_subject_score.get('rankChange'),
                                                   )
                    items.append(item)
                _exam_score.stuSubjectScoreList = items
                return _exam_score
        except Exception as e:
            print(f"获取成绩 异常：{e}")
            return None

    def tools_get_user_homework(self):
        """
        封装方法，用于工具调研
        """
        homework = self.get_user_homework()
        if homework is None:
            return "当前作业：无"
        return homework.format_homework_info
         

    def tools_get_exam_score(self):
        """
        工具：查询用户的考试成绩
        """
        _exam_score = self.get_exam_score()
        if _exam_score is None:
            return "当前成绩：无"
        return _exam_score.format_exam_score

    def tools_get_user_book_info(self):
        """
        工具：查询用户的阅读信息
        """
        _book_info = self.get_user_read_info()
        if _book_info is None:
            return "当前阅读：无"
        return _book_info.format_read_info


if __name__ == "__main__":
    user = User(user_type = 1, user_id = 61078)
    # book_info = user.get_user_read_info()
    # print(book_info.format_read_info)
    # user = User.get_robot_bind_user("00:11:22:33:44:55")
    print(user)
    user = User.get_robot_bind_user("DA:7A:84:55:FE:59")
    user.user_type = 1
    user.user_id = 61027
    exam_score = user.get_exam_score()
    if exam_score:
        print(exam_score)
        print(exam_score.format_exam_score)
