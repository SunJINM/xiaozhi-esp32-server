import os
import re
import time
import random
import traceback
import requests
from pathlib import Path
from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.utils.api_config import api_config
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__

STORY_CACHE = {}

play_story_function_desc = {
    "type": "function",
    "function": {
        "name": "play_story",
        "description": "播放故事的方法。当用户想要听故事，或听指定故事时调用, 根据上下文判断用户是否是想要听故事，如果是，就调用该工具",
        "parameters": {
            "type": "object",
            "properties": {
                "story_name": {
                    "type": "string",
                    "description": "故事名称，如果用户没有指定具体故事名则为空字符串或random, 明确指定的时返回故事的名字 示例: ```用户:播放小松鼠的故事\n参数：小松鼠``` ```用户:播放故事 \n参数：random ```",
                }
            },
            "required": ["story_name"],
        },
    },
}


@register_function("play_story", play_story_function_desc, ToolType.SYSTEM_CTL)
def play_story(conn, story_name: str):
    try:
        story_intent = (
            f"播放故事 {story_name}" if story_name not in ("", "random") else "随机播放故事"
        )

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 提交异步任务
        task = conn.loop.create_task(
            handle_story_command(conn, story_intent, story_name)
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()
                conn.logger.bind(tag=TAG).info("故事播放完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"故事播放失败: {e}")

        task.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在为您播放故事"
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理故事意图错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放故事时出错了"
        )


async def handle_story_command(conn, text, story_name=""):
    """处理故事播放指令"""
    conn.logger.bind(tag=TAG).debug(f"处理故事播放命令: {text}")
    
    # 调用故事API获取故事信息
    story_info = await get_story_info(conn, story_name)
    if story_info:
        # 下载并播放故事
        await download_and_play_story(conn, story_info)
    else:
        conn.logger.bind(tag=TAG).error("未能获取故事信息")


async def get_story_info(conn, story_name=""):
    """调用故事API获取故事信息"""
    try:
        api_url = f"{api_config.ai_photo_ybt_url}/robot/story/getStoryByName"
        
        # 准备请求参数
        params = {}
        if story_name and story_name not in ("", "random"):
            params["storyName"] = story_name
        
        conn.logger.bind(tag=TAG).info(f"请求故事API: {api_url}, 参数: {params}")
        
        # 发送API请求
        response = requests.post(api_url, json=params, timeout=10)
        response.raise_for_status()
        
        story_data = response.json()
        conn.logger.bind(tag=TAG).info(f"获取故事信息成功: {story_data}")
        
        return story_data
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"请求故事API失败: {e}")
        return None
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"获取故事信息失败: {e}")
        return None


async def download_and_play_story(conn, story_info):
    """下载故事音频文件并播放"""
    try:
        story_name = story_info.get("storyName", "未知故事")
        story_url = story_info.get("storyFileUrl", "")
        story_digest = story_info.get("storyDigest", "")
        timelen = story_info.get("timelen", "")
        
        if not story_url:
            conn.logger.bind(tag=TAG).error("故事音频URL为空")
            return
        
        # 创建tmp目录（如果不存在）
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)
        
        # 生成本地文件名
        file_extension = os.path.splitext(story_url)[1] or '.mp3'
        local_filename = f"story_{story_info.get('storyId', int(time.time()))}{file_extension}"
        local_path = tmp_dir / local_filename
        
        conn.logger.bind(tag=TAG).info(f"开始下载故事音频: {story_url} -> {local_path}")
        
        # 下载音频文件
        response = requests.get(story_url, timeout=30)
        response.raise_for_status()
        
        # 保存文件
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        conn.logger.bind(tag=TAG).info(f"故事音频下载完成: {local_path}")
        
        # 播放故事
        await play_local_story(conn, str(local_path), story_name, story_digest, timelen)
        
    except requests.exceptions.RequestException as e:
        conn.logger.bind(tag=TAG).error(f"下载故事音频失败: {e}")
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"下载和播放故事失败: {e}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")


def _get_random_story_prompt(story_name, story_digest, timelen):
    """生成随机故事播放引导语"""
    prompts = [
        f"正在为您播放故事《{story_name}》，时长{timelen}",
        f"请欣赏故事《{story_name}》",
        f"即将为您播放《{story_name}》的故事",
        f"现在为您带来故事《{story_name}》",
        f"让我们一起聆听《{story_name}》的故事",
        f"接下来请欣赏故事《{story_name}》",
        f"此刻为您献上《{story_name}》",
    ]
    
    # 如果有故事简介，有几率添加简介信息
    if story_digest and random.random() < 0.3:
        prompts.append(f"为您播放《{story_name}》，{story_digest}")
    
    return random.choice(prompts)


async def play_local_story(conn, story_path, story_name, story_digest="", timelen=""):
    """播放本地故事音频文件"""
    try:
        if not os.path.exists(story_path):
            conn.logger.bind(tag=TAG).error(f"故事文件不存在: {story_path}")
            return
        
        # 生成故事介绍文本
        intro_text = f"为您播放故事《{story_name}》"
        
        # 发送故事介绍
        await send_stt_message(conn, intro_text)
        conn.dialogue.put(Message(role="assistant", content=intro_text))

        # 发送TTS消息 - 开始
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )
        
        # 播放故事介绍
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=intro_text,
            )
        )
        
        #如果有故事简介，先播放简介
        if story_digest:
            await send_stt_message(conn, story_digest)
            conn.dialogue.put(Message(role="assistant", content=story_digest))
            
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=story_digest,
                )
            )
        
        # 播放故事音频文件
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=story_path,
            )
        )
        
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )
        
        conn.logger.bind(tag=TAG).info(f"故事播放任务已提交: {story_name}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放故事失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")