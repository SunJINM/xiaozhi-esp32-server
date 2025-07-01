from __future__ import annotations
from typing import Dict, Optional, List
from pydantic import BaseModel, ConfigDict
import httpx


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
        result += "\n</用户信息>"
        return result

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

    model_config = ConfigDict(
        extra='forbid',
        arbitrary_types_allowed=True
    )

    def get_user_read_info(self) -> UserBookRead:
        """获取用户阅读信息
        
        Returns:
            UserBookRead: 包含当前在读和历史阅读的书籍信息
        """
        # if self.read_info is not None:
        #     return read_info
        try:
            with httpx.Client() as client:
                response = client.post(
                    'http://rest-test.xxt.cn/book-reading/robot/get-user-read-info',
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
                    'http://rest-test.xxt.cn/book-reading/robot/get-robot-bind-user',
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
                    school_id=data.get('schoolId')
                )
        except Exception as e:
            return None

if __name__ == "__main__":
    # user = User(user_type = 1, user_id = 61064)
    # book_info = user.get_user_read_info()
    # print(book_info.format_read_info)
    user = User.get_robot_bind_user("00:11:22:33:44:55")
    print(user)
