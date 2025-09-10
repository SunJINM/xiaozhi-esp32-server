import re
import requests
import traceback
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.api_config import api_config

TAG = __name__

# 全局变量存储当前题目信息
CURRENT_QUIZ = {}

quiz_function_desc = {
    "type": "function",
    "function": {
        "name": "quiz",
        "description": (
            "出题功能。当用户想要做题、出题、考试、测试时调用; 或者当前用户感到无聊时，可以先询问用户是否做一些题"
            "如果用户指定想做测评题，需要获取的测评的图书名称，可以从记忆、当前阅读情况中获取，如果没法获取到，需要询问用户图书名称"
            "当用户说：想做题时，如果没有指定想做测评题，且无法获取到用户当前在读书籍，book_name参数不需要指定"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "difficulty": {
                    "type": "string",
                    "description": "题目难度，可选值：简单、中等、困难。如果用户没有指定则为空字符串",
                },
                "num": {
                    "type": "integer",
                    "description": "题目数量，默认为1。用户指定数量时使用指定值",
                },
                "book_name": {
                    "type": "string",
                    "description": "图书名称。用户指定或从用户的阅读记录中获取",
                }
            },
            "required": [],
        },
    },
}

answer_quiz_function_desc = {
    "type": "function",
    "function": {
        "name": "answer_quiz",
        "description": "回答题目。当用户给出题目答案时调用，如回答A、B、C、D或选项内容",
        "parameters": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "用户的答案，可以是选项代码(A/B/C/D)或选项内容",
                }
            },
            "required": ["answer"],
        },
    },
}


@register_function("quiz", quiz_function_desc, ToolType.SYSTEM_CTL)
def quiz(conn, difficulty: str = "", book_name: str = None, num: int = 1):
    try:
        conn.logger.bind(tag=TAG).info(f"获取题目: 难度={difficulty}, 数量={num}")
        
        # 获取题目
        if book_name is not None and len(book_name) > 0:
            questions = get_book_etest(conn, book_name)
        else:
            questions = get_questions(conn, difficulty, num)
        if not questions:
            return ActionResponse(
                action=Action.RESPONSE, 
                result="获取题目失败", 
                response="抱歉，无法获取题目，请稍后再试"
            )
        
        # 存储题目信息
        global CURRENT_QUIZ
        CURRENT_QUIZ['questions'] = questions
        CURRENT_QUIZ['current_index'] = 0
        CURRENT_QUIZ['total'] = len(questions)
        
        # 组装第一道题的文本
        question_text = format_single_question(0)
        
        # 确保question_text不为空
        if not question_text or question_text.strip() == "":
            question_text = "题目格式化失败，请重新尝试"
        
        return ActionResponse(
            action=Action.RESPONSE, 
            result="题目获取成功", 
            response=question_text
        )
        
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"出题失败: {e}")
        return ActionResponse(
            action=Action.RESPONSE, 
            result=str(e), 
            response="出题时出错了，请稍后再试"
        )


@register_function("answer_quiz", answer_quiz_function_desc, ToolType.SYSTEM_CTL)
def answer_quiz(conn, answer: str):
    try:
        global CURRENT_QUIZ
        
        if 'questions' not in CURRENT_QUIZ or not CURRENT_QUIZ['questions']:
            return ActionResponse(
                action=Action.RESPONSE, 
                result="没有进行中的题目", 
                response="当前没有题目，请先出题"
            )
        
        current_index = CURRENT_QUIZ.get('current_index', 0)
        if current_index >= len(CURRENT_QUIZ['questions']):
            return ActionResponse(
                action=Action.RESPONSE, 
                result="所有题目已完成", 
                response="所有题目已完成，可以重新出题"
            )
        
        current_question = CURRENT_QUIZ['questions'][current_index]
        correct_answer = current_question.get('correctAnswer', '')
        
        # 标准化用户答案
        user_answer = normalize_answer(answer, current_question.get('options', []))
        
        # 判断答案是否正确
        is_correct = user_answer.upper() == correct_answer.upper()
        
        # 生成反馈信息
        if is_correct:
            feedback = f"答案正确！正确答案是{correct_answer}。"
        else:
            feedback = f"答案错误。正确答案是{correct_answer}。"
        
        # 移动到下一题
        CURRENT_QUIZ['current_index'] += 1
        
        # 检查是否还有下一题
        if CURRENT_QUIZ['current_index'] < CURRENT_QUIZ['total']:
            # 还有下一题，组装下一题
            next_question_text = format_single_question(CURRENT_QUIZ['current_index'])
            response_text = f"{feedback}\n\n{next_question_text}"
        else:
            # 所有题目完成
            response_text = f"{feedback}\n\n恭喜您完成了所有{CURRENT_QUIZ['total']}道题目！"
            CURRENT_QUIZ.clear()  # 清空题目信息
        
        return ActionResponse(
            action=Action.RESPONSE, 
            result="答案处理完成", 
            response=response_text
        )
        
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"答题处理失败: {e}")
        return ActionResponse(
            action=Action.RESPONSE, 
            result=str(e), 
            response="处理答案时出错了"
        )


def get_questions(conn, difficulty="", num=1):
    """调用题目API获取题目"""
    try:
        api_url = f"{api_config.book_reading_url}/quiz-arena/get-questions-by-difficulty"
        
        # 准备请求参数
        params = {"num": num}
        if difficulty:
            params["difficulty"] = difficulty
        
        conn.logger.bind(tag=TAG).info(f"请求题目API: {api_url}, 参数: {params}")
        
        # 发送API请求
        response = requests.post(api_url, json=params, timeout=10)
        response.raise_for_status()
        
        quiz_data = response.json()
        conn.logger.bind(tag=TAG).info(f"获取题目成功，共{len(quiz_data.get('questions', []))}道题")
        
        return quiz_data.get('questions', [])
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"请求题目API失败: {e}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取题目失败: {e}")
        return None


def get_book_etest(conn, book_name=""):
    """调用题目API获取题目"""
    try:
        api_url = f"{api_config.xinzx_resource_url}/book-etest/get-questions-by-book-name"
        
        # 准备请求参数
        params = {"bookName": book_name}
        
        conn.logger.bind(tag=TAG).info(f"请求题目API: {api_url}, 参数: {params}")
        
        # 发送API请求
        response = requests.post(api_url, json=params, timeout=10)
        response.raise_for_status()
        
        quiz_data = response.json()
        conn.logger.bind(tag=TAG).info(f"获取题目成功，共{len(quiz_data.get('questions', []))}道题")
        
        return quiz_data.get('questions', [])
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"请求题目API失败: {e}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取题目失败: {e}")
        return None

def format_single_question(question_index):
    """格式化单道题目文本"""
    global CURRENT_QUIZ
    
    try:
        if 'questions' not in CURRENT_QUIZ or question_index >= len(CURRENT_QUIZ['questions']):
            return "题目信息错误"
            
        question = CURRENT_QUIZ['questions'][question_index]
        question_content = question.get('questionContent', '')
        options = question.get('options', [])
        difficulty = question.get('difficulty', '')
        
        # 检查必要字段
        if not question_content:
            return "题目内容为空"
        
        # 构建题目文本
        if CURRENT_QUIZ['total'] > 1:
            if difficulty:
                intro_text = f"第{question_index + 1}道题，难度：{difficulty}"
            else:
                intro_text = f"第{question_index + 1}道题"
        else:
            if difficulty:
                intro_text = f"题目难度：{difficulty}"
            else:
                intro_text = "请听题"
        
        question_text = f"{intro_text}。{question_content}"
        
        # 构建选项文本
        options_text = ""
        for option in options:
            option_code = option.get('optionCode', '')
            option_content = option.get('optionContent', '')
            if option_code and option_content:
                options_text += f"选项{option_code}：{option_content}。"
        
        # 检查选项是否为空
        if not options_text:
            options_text = "选项信息缺失。"
        
        # 完整的题目文本
        full_text = f"{question_text} {options_text}请选择您的答案。"
        
        # 最终检查，确保返回值不为空
        if not full_text or full_text.strip() == "":
            return "题目信息不完整，请重新获取题目。"
        
        return full_text

    except Exception as e:
        return f"格式化题目失败: {e}"


def normalize_answer(user_input, options):
    """标准化用户答案"""
    # 去除标点符号和空格
    clean_input = re.sub(r'[^\w\s]', '', user_input).strip().upper()
    
    # 如果直接是选项代码
    if clean_input in ['A', 'B', 'C', 'D']:
        return clean_input
    
    # 尝试从输入中提取选项代码
    for char in ['A', 'B', 'C', 'D']:
        if char in clean_input:
            return char
    
    # 尝试匹配选项内容
    for option in options:
        option_content = option.get('optionContent', '').strip()
        if option_content and option_content in user_input:
            return option.get('optionCode', '')
    
    # 如果都匹配不上，返回原输入的第一个字符（如果是字母）
    if clean_input and clean_input[0] in 'ABCD':
        return clean_input[0]
    
    return clean_input