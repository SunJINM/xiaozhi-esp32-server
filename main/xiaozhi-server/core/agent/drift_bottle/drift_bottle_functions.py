from core.agent.drift_bottle.drift_bottle_api import DriftBottleAPI
from core.user import User
from core.utils.dialogue import Dialogue, Message
from plugins_func.register import ActionResponse, Action
from core.connection import ConnectionHandler
from core.handle.sendAudioHandle import sendAudio
import asyncio

async def play_preset_audio(conn: ConnectionHandler, audio_file_path: str):
    """播放预置音效的辅助函数"""
    try:
        if conn and conn.tts:
            audios, _ = conn.tts.audio_to_opus_data(audio_file_path)
            await sendAudio(conn, audios, pre_buffer=False)
    except Exception as e:
        conn.logger.bind(tag="DriftBottle").error(f"播放音效失败: {str(e)}")

def throw_bottle(content: str, user: User, conn: ConnectionHandler = None, *args, **kwargs):
    """扔漂流瓶工具函数"""
    try:
        # 播放扔漂流瓶音效
        future = None
        if conn:
            asyncio.run_coroutine_threadsafe(
                play_preset_audio(conn, "config/assets/drift_bottle_throw.mp3"), conn.loop
            )
        
        api = DriftBottleAPI(user)
        # 调用API扔瓶子
        result = api.throw_bottle(
            content=content
        )
        
        if result.get("content"):
            res = f"你的漂流瓶已经扔到海里了！\n\n希望它能带给别人温暖，也希望你能收到回复~ "
        else:
            res = f"扔瓶子失败了\n\n要不要再试一次？"
            
    except Exception as e:
        res = f"扔瓶子时出现了问题\n\n要不要再试一次？"
    
    if future:
        future.result()
    return ActionResponse(Action.REQLLM, res, None)

def catch_bottle(user: User, num: int = 1, conn: ConnectionHandler = None, *args, **kwargs):
    """捞漂流瓶工具函数"""
    try:
        # 播放捞漂流瓶音效
        future = None
        if conn:
            future = asyncio.run_coroutine_threadsafe(
                play_preset_audio(conn, "config/assets/drift_bottle_catch.mp3"), conn.loop
            )
        
        api = DriftBottleAPI(user)
        result = api.catch_bottle(num=num)
        
        if result.get("limitReached"):
            if future:
                future.result()
            return ActionResponse(Action.RESPONSE, None, "今天你已经捞了5个瓶子啦！明天再来捞新的吧，或者扔个瓶子分享你的故事？")
        
        bottles = result.get("bottles", [])
        
        bottle_list = f"根据下面数据，回应用户的捞取漂流瓶请求：\n\n 瓶子数量： {len(bottles)}\n\n"

        if len(bottles) > 0:
            for bottle in bottles:
                content = bottle.get("content", "")
                bottle_id = bottle.get("bottleId", "")
                time_info = bottle.get("time", "")
                bottle_list += f"瓶子ID：{bottle_id}\n"
                bottle_list += f"瓶子内容：{content}\n\n"


        new_res = (
            f"{bottle_list}"
            f"如果漂流瓶数量为1个，请以自然流畅的语音播报漂流瓶的内容"
            f"如果漂流瓶数量大于1个，请播报第一个漂流瓶的内容，并询问用户是否要听下一个"
            f"如果用户说'听下一个'，请播报下一个漂流瓶的内容，并继续询问，直到所有瓶子都播报完毕"
            f"如果漂流瓶数量为0个，回复用户海面很平静，暂时没有捞到瓶子。要不要扔个瓶子，或者等会儿再试试？"
        )
        if future:
            future.result()
        return ActionResponse(Action.REQLLM, new_res, None)
            
    except Exception as e:
        return ActionResponse(Action.RESPONSE, None, f"捞瓶子时出现了问题\n\n要不要再试一次？")

def get_pending_replies(user: User, num: int = 1, *args, **kwargs):
    """收听回复工具函数"""
    try:
        api = DriftBottleAPI(user)
        result = api.get_pending_replies(num=num)

        res = f"根据下面的数据，回应用户的收听回复请求：\n\n回复数量： {len(result)}\n\n"

        if len(result) > 0:
            for reply in result:
                content = reply.get("replyContent", "")
                reply_id = reply.get("replyId", "")
                reply_time = reply.get("replyTime", "")
                bottle_content = reply.get("bottleContent", "")
                res += f"回复ID：{reply_id}\n"
                res += f"回复内容：{content}\n"
                res += f"被回复瓶子内容：{bottle_content}\n"

        new_res = (
            f"{res}"
            f"如果回复数量为1个，请以自然流畅的语音播报回复的内容"
            f"如果回复数量大于1个，请播报第一个回复的内容，并询问用户是否要听下一个"
            f"如果用户说'听下一个'，请播报下一个回复的内容，并继续询问，直到所有回复都播报完毕"
            f"如果回复数量为0个，回复暂时还没有收到回复呢，要不要扔个新瓶子或者捞个瓶子？"
        )

        return ActionResponse(Action.REQLLM, new_res, None)
            
    except Exception as e:
        res = f"查看回复时出现了问题\n\n要不要再试一次？"
        return ActionResponse(Action.RESPONSE, None, res)

def reply_to_bottle(user: User, bottle_id: str, reply_content: str, *args, **kwargs):
    """回复漂流瓶工具函数"""
    try:
        api = DriftBottleAPI(user)
        result = api.reply_bottle(
            bottle_id=bottle_id,
            content=reply_content
        )
        
        if result.get("content"):
            res = f"你的回复已经送达！\n\n希望你的话语能给TA带去温暖~ 你可以继续捞瓶子或扔瓶子。"
        else:
            error_msg = result.get("error", "未知错误")
            res = f"回复失败了\n\n要不要再试一次？"
            
    except Exception as e:
        res = f"回复时出现了问题\n\n要不要再试一次？"
    return ActionResponse(Action.RESPONSE, None, res)
    

def get_user_status(user: User, *args, **kwargs):
    """获取用户状态工具函数"""
    try:
        api = DriftBottleAPI(user)
        result = api.get_user_status()
        if result is not None:
            reply_num = result.get("pendingRepliesCount", 0)
            today_catch_num = result.get("todayCatchCount", 0)
            max_daily_catch_num = result.get("maxDailyCatch", 0)
            total_throw_num = result.get("totalBottlesCreated", 0)
            total_catch_num = result.get("totalBottlesCreated", 0)
        res = (
            f"根据下面的数据，回应用户的获取用户状态请求：\n\n"
            f"回复数量：{reply_num}\n"
            f"今天捞瓶子数量：{today_catch_num}\n"
            f"最大捞瓶子数量：{max_daily_catch_num}\n"
            f"总扔瓶子数量：{total_throw_num}\n"
            f"总捞瓶子数量：{total_catch_num}\n"
            f"(根据用户的提问和用户信息，回答用户的问题，如果信息不足，回复用户暂不清楚)"
        )
        return ActionResponse(Action.REQLLM, res, None)
    except Exception as e:
        res = f"获取相关信息时出现了问题\n\n要不要再试一次？"
        return ActionResponse(Action.RESPONSE, res, None)


def marked_listened(user: User, type: int, target_id: int, *args, **kwargs):
    """标记已收听工具函数"""
    try:
        api = DriftBottleAPI(user)
        result = api.mark_listened(type, target_id)
        return ActionResponse(Action.NONE, None, None)
    except Exception as e:
        return ActionResponse(Action.NONE, None, None)

def exit_agent(conn: ConnectionHandler, *args, **kwargs):
    """退出漂流瓶功能"""
    conn.current_agent = None
    self = kwargs.get("self", None)
    if self:
        self.save_agent_memory()
    conn.agent_dialogue.clear()
    res = "已退出漂流瓶功能"
    conn.dialogue.put(Message(role="user", content=res))
    return ActionResponse(Action.RESPONSE, res, res)