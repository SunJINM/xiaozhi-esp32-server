import os
import re
import time
import random
import asyncio
import aiohttp
import traceback
import tempfile
import difflib
from pathlib import Path
from core.handle.sendAudioHandle import send_stt_message
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__

# 缓存音乐的目录 - 使用src下的music目录
MUSIC_CACHE_DIR = "music/online_cache"

play_online_music_function_desc = {
    "type": "function",
    "function": {
        "name": "play_online_music",
        "description": "播放在线音乐的方法，支持搜索和播放QQ音乐资源。",
        "parameters": {
            "type": "object",
            "properties": {
                "song_name": {
                    "type": "string",
                    "description": "歌曲名称或歌手名，如果用户没有指定具体歌名则为'random'。示例: ```用户:播放周杰伦的稻香\n参数：稻香``` ```用户:在线播放音乐 \n参数：random```",
                }
            },
            "required": ["song_name"],
        },
    },
}


@register_function("play_online_music", play_online_music_function_desc, ToolType.SYSTEM_CTL)
def play_online_music(conn, song_name: str):
    try:
        music_intent = f"在线播放音乐 {song_name}" if song_name != "random" else "随机在线播放音乐"

        # 检查事件循环状态
        if not conn.loop.is_running():
            conn.logger.bind(tag=TAG).error("事件循环未运行，无法提交任务")
            return ActionResponse(
                action=Action.RESPONSE, result="系统繁忙", response="请稍后再试"
            )

        # 提交异步任务
        task = conn.loop.create_task(
            handle_online_music_command(conn, song_name)
        )

        # 非阻塞回调处理
        def handle_done(f):
            try:
                f.result()
                conn.logger.bind(tag=TAG).info("在线音乐播放完成")
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"在线音乐播放失败: {e}")

        task.add_done_callback(handle_done)

        return ActionResponse(
            action=Action.NONE, result="指令已接收", response="正在为您搜索并播放在线音乐"
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"处理在线音乐意图错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE, result=str(e), response="播放在线音乐时出错了"
        )


def ensure_cache_dir():
    """确保缓存目录存在"""
    if not os.path.exists(MUSIC_CACHE_DIR):
        os.makedirs(MUSIC_CACHE_DIR, exist_ok=True)

    # 确保tmp目录也存在
    tmp_dir = "tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, exist_ok=True)


def search_local_music(song_name):
    """在本地music目录搜索音乐文件"""
    if not os.path.exists(MUSIC_CACHE_DIR):
        return None

    # 支持的音频格式
    audio_extensions = ['.mp3', '.flac', '.wav', '.m4a']

    # 搜索缓存目录中的文件
    for file_path in Path(MUSIC_CACHE_DIR).rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in audio_extensions:
            filename = file_path.stem  # 不包含扩展名的文件名

            # 使用模糊匹配检查文件名是否包含搜索关键词
            similarity = difflib.SequenceMatcher(None, song_name.lower(), filename.lower()).ratio()
            if similarity > 0.5 or song_name.lower() in filename.lower():
                return {
                    "file_path": str(file_path),
                    "name": filename,
                    "source": "local_cache"
                }

    return None

async def stream_and_cache_music(music_url, song_info, conn):
    """用 pydub + ffmpeg-python 实现边下载边分割（无 FFmpeg 命令行依赖）"""
    import os
    import re
    import uuid
    import shutil
    import asyncio
    import aiohttp
    import pydub
    from pydub import AudioSegment
    from io import BytesIO
    import ffmpeg  # 需安装 ffmpeg-python（pip install ffmpeg-python）

    try:
        ensure_cache_dir()
        tmp_dir = "tmp"
        os.makedirs(tmp_dir, exist_ok=True)

        # 1. 文件名和格式处理（复用原有逻辑）
        safe_filename = f"{song_info['name']}_{song_info['artist']}"
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', safe_filename)
        if 'flac' in music_url.lower():
            file_extension = '.flac'
            audio_format = 'flac'
        elif 'm4a' in music_url.lower():
            file_extension = '.m4a'
            audio_format = 'm4a'
        else:
            file_extension = '.mp3'
            audio_format = 'mp3'
        cache_file_path = os.path.join(MUSIC_CACHE_DIR, f"{safe_filename}{file_extension}")
        session_id = uuid.uuid4().hex[:8]
        segment_duration = 10  # 每段10秒
        segment_files = []

        # 2. 初始化：内存缓冲区（存下载的二进制数据）+ 完整文件缓存句柄
        download_buffer = BytesIO()  # 临时存下载数据，供解码用
        cache_writer = open(cache_file_path, 'wb') if not os.path.exists(cache_file_path) else None
        segment_counter = 0
        current_segment = None  # 存当前正在累积的音频段（AudioSegment 对象）

        # 3. 流式下载 + 实时解码 + 切片
        async with aiohttp.ClientSession() as session:
            async with session.get(music_url, timeout=120) as response:
                if response.status != 200:
                    conn.logger.bind(tag=TAG).error(f"下载失败，HTTP状态码: {response.status}")
                    return None, False

                conn.logger.bind(tag=TAG).info("开始边下载边解码分割...")
                chunk_size = 32768  # 32KB/块，平衡速度和内存
                async for chunk in response.content.iter_chunked(chunk_size):
                    # ① 先把数据写入完整缓存文件（若需要）
                    if cache_writer:
                        cache_writer.write(chunk)
                    # ② 把数据写入内存缓冲区，供解码
                    download_buffer.write(chunk)
                    download_buffer.seek(0)  # 重置指针到开头，供 pydub 读取

                    try:
                        # ③ 用 pydub 加载缓冲区数据（流式解码，支持部分数据）
                        # 注：pydub 会自动调用 ffmpeg-python 解码，无需命令行
                        audio = AudioSegment.from_file(download_buffer, format=audio_format)
                        sample_rate = audio.frame_rate  # 采样率（如44100Hz）
                        channels = audio.channels        # 声道数（如2）
                        sample_width = audio.sample_width  # 采样深度（如2字节/样本）

                        # 计算每10秒音频对应的“字节数”（用于判断是否够一段）
                        bytes_per_second = sample_rate * channels * sample_width
                        bytes_per_segment = bytes_per_second * segment_duration

                        # ④ 累积音频段，达到10秒则保存
                        if current_segment is None:
                            current_segment = audio  # 初始化第一段
                        else:
                            current_segment += audio  # 拼接新解码的音频

                        # 检查当前段是否够10秒（用字节数判断，避免时间计算误差）
                        if len(current_segment.raw_data) >= bytes_per_segment:
                            # 截取前10秒数据（避免累积过多）
                            segment_audio = current_segment[:segment_duration * 1000]  # pydub 时间单位是毫秒
                            # 保存为文件
                            segment_filename = f"segment_{session_id}_{segment_counter:03d}{file_extension}"
                            segment_path = os.path.join(tmp_dir, segment_filename)
                            segment_audio.export(segment_path, format=audio_format)
                            # 加入播放队列
                            conn.tts.tts_text_queue.put(
                                TTSMessageDTO(
                                    sentence_id=conn.sentence_id,
                                    sentence_type=SentenceType.MIDDLE,
                                    content_type=ContentType.FILE,
                                    content_file=segment_path,
                                )
                            )
                            segment_files.append(segment_path)
                            conn.logger.bind(tag=TAG).info(f"生成片段: {segment_filename}")
                            # 重置当前段（保留剩余部分，避免丢数据）
                            remaining_audio = current_segment[segment_duration * 1000:]
                            current_segment = remaining_audio if len(remaining_audio.raw_data) > 0 else None
                            segment_counter += 1

                    except Exception as e:
                        # 若缓冲区数据不足（如刚开始下载），解码会失败，忽略并继续累积
                        if "Invalid data found when processing input" not in str(e):
                            conn.logger.bind(tag=TAG).warning(f"临时解码失败（数据不足）: {e}")
                        pass

                    # 重置缓冲区指针，准备接收下一块数据
                    download_buffer.seek(0)
                    download_buffer.truncate()  # 清空缓冲区，避免重复解码

        # 4. 处理最后一段（不足10秒的剩余部分）
        if current_segment is not None and len(current_segment.raw_data) > 1024:  # 过滤过小片段
            segment_filename = f"segment_{session_id}_{segment_counter:03d}{file_extension}"
            segment_path = os.path.join(tmp_dir, segment_filename)
            current_segment.export(segment_path, format=audio_format)
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.FILE,
                    content_file=segment_path,
                )
            )
            segment_files.append(segment_path)
            conn.logger.bind(tag=TAG).info(f"生成最后一段片段: {segment_filename}")

        # 5. 收尾：关闭缓存文件，清理缓冲区
        if cache_writer:
            cache_writer.close()
        download_buffer.close()
        conn.logger.bind(tag=TAG).info(f"分割完成，共生成 {len(segment_files)} 段，完整文件已缓存")

        return cache_file_path, len(segment_files) > 0

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"边下载边分割失败: {e}")
        # 清理资源
        if 'cache_writer' in locals() and cache_writer:
            cache_writer.close()
            if os.path.exists(cache_file_path) and os.path.getsize(cache_file_path) < 1024:
                os.remove(cache_file_path)
        if 'segment_files' in locals():
            for seg_path in segment_files:
                if os.path.exists(seg_path):
                    os.remove(seg_path)
        return None, False

async def cache_music_file(music_url, song_info):
    """下载音乐文件并保存到缓存目录（非流式，用于备用）"""
    try:
        ensure_cache_dir()

        # 创建安全的文件名
        safe_filename = f"{song_info['name']}_{song_info['artist']}"
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', safe_filename)

        # 根据URL判断文件格式
        if 'flac' in music_url.lower():
            file_extension = '.flac'
        elif 'm4a' in music_url.lower():
            file_extension = '.m4a'
        else:
            file_extension = '.mp3'  # 默认为mp3

        cache_file_path = os.path.join(MUSIC_CACHE_DIR, f"{safe_filename}{file_extension}")

        async with aiohttp.ClientSession() as session:
            async with session.get(music_url, timeout=120) as response:
                if response.status == 200:
                    # 下载并保存文件
                    total_size = 0
                    with open(cache_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            total_size += len(chunk)
                        f.flush()  # 强制刷新缓冲区
                        os.fsync(f.fileno())  # 强制写入磁盘

                    if os.path.exists(cache_file_path) and total_size > 0:
                        return cache_file_path
                    else:
                        return None
                else:
                    return None

    except Exception as e:
        return None


async def search_qq_music(song_name, limit=5):
    """搜索音乐"""
    try:
        search_url = "https://api.vkeys.cn/v2/music/tencent/search/song"
        params = {
            "word": song_name,
            "page": 1,
            "num": min(limit, 10)
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # 检查响应结构
                    if data.get("code") == 200 and "data" in data:
                        song_list = data["data"]  # data字段直接就是歌曲列表

                        songs = []
                        for song in song_list:
                            song_info = {
                                "id": song.get("id"),
                                "mid": song.get("mid"),
                                "name": song.get("song", ""),  # 字段名是'song'不是'name'
                                "artist": ", ".join([singer.get("name", "") for singer in song.get("singer_list", [])]),  # 字段名是'singer_list'
                                "album": song.get("album", ""),  # album直接是字符串
                                "source": "qq"
                            }
                            songs.append(song_info)

                        return songs
                    else:
                        return []
                else:
                    return []

    except Exception as e:
        return []


async def get_qq_music_url(song_info):
    """获取音乐播放链接"""
    try:
        url_api = "https://api.vkeys.cn/v2/music/tencent/geturl"
        params = {
            "quality": 10  # Master 2.0 音质
        }

        # 优先使用mid，如果没有则使用id
        if song_info.get("mid"):
            params["mid"] = song_info["mid"]
        elif song_info.get("id"):
            params["id"] = song_info["id"]
        else:
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(url_api, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("code") == 200 and "data" in data:
                        # 直接从data字段获取url
                        play_url = data["data"].get("url")

                        if play_url and play_url != "":
                            return play_url
                        else:
                            return None
                    else:
                        return None
                else:
                    return None

    except Exception as e:
        return None


async def download_music_file(music_url, song_info):
    """下载音乐文件到临时目录"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(music_url, timeout=60) as response:
                if response.status == 200:
                    # 创建临时文件
                    safe_filename = f"{song_info['name']}_{song_info['artist']}.mp3"
                    # 清理文件名中的非法字符
                    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', safe_filename)
                    temp_dir = tempfile.gettempdir()
                    temp_file_path = os.path.join(temp_dir, f"online_music_{int(time.time())}_{safe_filename}")

                    # 下载并保存文件
                    total_size = 0
                    with open(temp_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            total_size += len(chunk)

                    if os.path.exists(temp_file_path) and total_size > 0:
                        return temp_file_path
                    else:
                        return None
                else:
                    return None

    except Exception as e:
        return None


def _get_online_play_prompt(song_info):
    """生成在线播放引导语"""
    if song_info:
        song_name = song_info["name"]
        artist = song_info["artist"]
        prompts = [
            f"正在为您在线播放，《{song_name}》- {artist}",
            f"请欣赏来自QQ音乐的歌曲，《{song_name}》- {artist}",
            f"即将为您在线播放，《{song_name}》- {artist}",
            f"现在为您带来，《{song_name}》- {artist}",
            f"让我们一起在线聆听，《{song_name}》- {artist}",
        ]
    else:
        prompts = [
            "正在为您搜索在线音乐",
            "即将为您播放网络音乐",
            "正在连接QQ音乐服务器"
        ]

    return random.choice(prompts)


async def play_local_cached_music(conn, local_music):
    """播放本地缓存的音乐"""
    try:
        file_path = local_music["file_path"]
        song_name = local_music["name"]

        # 生成播放提示
        text = f"正在为您播放音乐，《{song_name}》"
        conn.dialogue.put(Message(role="assistant", content=text))
        conn.logger.bind(tag=TAG).info(f"播放本地缓存音乐: {file_path}")

        # 发送TTS消息
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )

        # 播放提示文本
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            )
        )

        # 播放音乐文件
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=file_path,
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

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"播放本地缓存音乐失败: {e}")
        error_text = "播放本地音乐时出错了"
        conn.dialogue.put(Message(role="assistant", content=error_text))
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=error_text,
            )
        )

async def handle_online_music_command(conn, song_name):
    """处理在线音乐播放指令"""
    try:
        conn.logger.bind(tag=TAG).info(f"开始搜索音乐: {song_name}")

        # 处理随机播放
        if song_name == "random":
            popular_songs = ["稻香", "青花瓷", "告白气球", "七里香", "晴天", "夜曲", "不能说的秘密"]
            song_name = random.choice(popular_songs)

        # 本地缓存搜索（如需要可启用）
        # local_music = search_local_music(song_name)
        # if local_music:
        #     await play_local_cached_music(conn, local_music)
        #     return

        # 发送开始标记（仅对LLM意图）
        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )

        # 播放提示文本
        text = f"正在为您寻找音乐: {song_name}"
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            )
        )

        # 搜索音乐
        songs = await search_qq_music(song_name, limit=5)

        if not songs:
            conn.logger.bind(tag=TAG).error(f"未找到音乐: {song_name}")
            error_text = f"抱歉，没有找到《{song_name}》的在线资源"
            conn.dialogue.put(Message(role="assistant", content=error_text))

            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=error_text,
                )
            )
            
            # 发送结束标记
            if conn.intent_type == "intent_llm":
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.LAST,
                        content_type=ContentType.ACTION,
                    )
                )
            return

        # 尝试获取可播放的歌曲
        selected_song = None
        music_url = None

        for i, song in enumerate(songs):
            music_url = await get_qq_music_url(song)
            if music_url:
                selected_song = song
                break

        if not music_url or not selected_song:
            error_text = f"《{song_name}》暂时无法播放，请尝试其他歌曲"
            conn.dialogue.put(Message(role="assistant", content=error_text))
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=error_text,
                )
            )
            
            # 发送结束标记
            if conn.intent_type == "intent_llm":
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.LAST,
                        content_type=ContentType.ACTION,
                    )
                )
            return

        conn.logger.bind(tag=TAG).info(f"找到音乐: {selected_song['name']} - {selected_song['artist']}")

        # 生成播放提示
        text = _get_online_play_prompt(selected_song)
        conn.dialogue.put(Message(role="assistant", content=text))

        # 播放提示文本
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=text,
            )
        )

        # 开始流式播放音乐
        conn.logger.bind(tag=TAG).info("开始流式播放音乐...")
        cache_file_path, stream_started = await stream_and_cache_music(music_url, selected_song, conn)

        conn.logger.bind(tag=TAG).info(f"音乐播放和缓存完成: {cache_file_path}")

    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"在线音乐播放失败: {str(e)}")
        conn.logger.bind(tag=TAG).error(f"详细错误: {traceback.format_exc()}")