import random
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()


GET_BOOK_INFO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_book_info",
        "description": (
            "获取书本信息的方法，用户可以指定书本名称，获取书本信息"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "book_name": {
                    "type": "string",
                    "description": "书本名称"
                }
            },
            "required": ["book_name"]
        }
    }
}

def fetch_book_info(book_name, cookie):
    """ 
    获取书本信息
    """
    url = "http://rest.xxt.cn/book-reading/book/get-book-list-by-filter"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json"
    }

    data = {
        "current": 1,
        "pageSize": 1,
        "search": {
            "searchText": book_name
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("resultList")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    
def fetch_book_detail(isbn, cookie):
    """
    获取书本详情
    """
    url = "http://rest.xxt.cn/book-reading/book/get-book-detail"
    headers = {
        "Cookie": cookie,
        "Content-Type": "application/json"
    }

    data = {
        "isbn": isbn
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("result")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

@register_function('get_book_info', GET_BOOK_INFO_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_book_info(conn, book_name: str = None, lang: str = "zh_CN"):
    """
    获取书本信息
    """
    cookie = ""
    book_infos = fetch_book_info(book_name, cookie)
    if not book_infos or len(book_infos) == 0:
        return ActionResponse(Action.REQLLM, "抱歉，没有找到相关的书本信息。", None)
    book_info = book_infos[0]
    isbn = book_info.get("isbn")
    book_name = book_info.get("bookName")
    book_author = book_info.get("author")
    book_publisher = book_info.get("press")

    # 构建详情报告
    detail_report = (
        f"根据下列数据，用{lang}回应用户的书籍信息查询请求：\n\n"
        f"书籍名称: {book_name}\n"
        f"书籍作者: {book_author}\n"
        f"书籍出版社: {book_publisher}\n\n"
        f"(请对上述书籍内容进行总结，提取关键信息，以自然、流畅的方式向用户播报，"
    )

    return ActionResponse(Action.REQLLM, detail_report, None)
