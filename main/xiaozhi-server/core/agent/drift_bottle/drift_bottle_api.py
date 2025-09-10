""" 业务api调用与数据缓存 """
import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from config.logger import setup_logging
from core.user import User
from core.utils.api_config import api_config

class DriftBottleAPI:
    """漂流瓶API调用和数据缓存管理"""
    
    def __init__(self, user: User, base_url: Optional[str] = None):
        self.base_url = base_url or api_config.book_reading_url
        self.logger = setup_logging()
        self.user = user
        # 简单的内存缓存
        self.cache = {
            "user_status": {},
            "pending_replies": {},
            "daily_limits": {}
        }
        
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """统一的API请求方法"""
        url = f"{self.base_url}{endpoint}"
        self.logger.info(f"API请求 {method} {endpoint}, data: {data}")
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=data, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
                
            response.raise_for_status()
            res = response.json()
            self.logger.info(f"API请求成功 {endpoint}: {res}")
            return res
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API请求失败 {endpoint}: {e}")
            return {"error": str(e), "success": False}
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败 {endpoint}: {e}")
            return {"error": "响应格式错误", "success": False}
    
    def get_user_status(self) -> Dict[str, Any]:
        """获取用户状态
        API: /book-reading/drift-bottle/user-status
        """
        # 检查缓存
        user_id = self.user.user_id
        # API调用
        result = self._make_request(
            "POST", 
            "/drift-bottle/get-user-status", 
            {
                "userId": self.user.user_id,
                "userType": self.user.user_type
            }
        )
        return result
    
    def get_pending_replies(
        self, 
        num: int = 1
    ) -> Dict[str, Any]:
        """获取待收听的回复
        API: /book-reading/drift-bottle/pending-replies
        """
        user_id = self.user.user_id
        
        result = self._make_request(
            "POST", 
            "/drift-bottle/get-pending-replies", 
            {
                "userId": self.user.user_id,
                "userType": self.user.user_type,
                "userName": self.user.user_name,
                "unitId": self.user.group_id,
                "schoolId": self.user.school_id,
                "num": num
            }
        )
        
        return result
    
    def catch_bottle(
        self, 
        num: int = 1,
    ) -> Dict[str, Any]:
        """捞取漂流瓶
        API: /book-reading/drift-bottle/catch
        """
        user_id = self.user.user_id
        
        result = self._make_request(
            "POST", 
            "/drift-bottle/catch-drift-bottle", 
            {
                "userId": self.user.user_id,
                "userType": self.user.user_type,
                "userName": self.user.user_name,
                "unitId": self.user.group_id,
                "schoolId": self.user.school_id,
                "num": num
            }
        )
        
        return result
    
    def throw_bottle(
        self,
        content: str, 
        audio_url: str = None
    ) -> Dict[str, Any]:
        """扔漂流瓶
        API: /book-reading/drift-bottle/throw
        """
        user_id = self.user.user_id
        user_type = self.user.user_type
        data = {
            "userId": user_id,
            "userType": user_type,
            "userName": self.user.user_name,
            "unitId": self.user.group_id,
            "schoolId": self.user.school_id,
            "content": content
        }
        if audio_url:
            data["audio_url"] = audio_url
        
        result = self._make_request("POST", "/drift-bottle/create-drift-bottle", data)
        
        return result
    
    def reply_bottle(self, bottle_id: int, content: str, audio_url: str = None) -> Dict[str, Any]:
        """回复漂流瓶
        API: /book-reading/drift-bottle/reply
        """
        user_id = self.user.user_id
        user_type = self.user.user_type
        data = {
            "bottleId": bottle_id,
            "userId": user_id,
            "userType": user_type,
            "userName": self.user.user_name,
            "unitId": self.user.group_id,
            "schoolId": self.user.school_id,
            "content": content
        }
        if audio_url:
            data["audio_url"] = audio_url
        
        result = self._make_request("POST", "/drift-bottle/reply", data)
        
        return result
    
    def get_preset_bottle(self, user_id: str) -> Dict[str, Any]:
        """获取预设瓶子（当捞不到瓶子时）
        API: /book-reading/drift-bottle/preset
        """
        return self._make_request("GET", "/book-reading/drift-bottle/preset", {"user_id": user_id})
    
    def _check_daily_limit(self, user_id: str, action: str, limit: int) -> bool:
        """检查每日操作次数限制"""
        today = datetime.now().date().isoformat()
        cache_key = f"{user_id}_{action}_{today}"
        
        if cache_key not in self.cache["daily_limits"]:
            self.cache["daily_limits"][cache_key] = 0
        
        return self.cache["daily_limits"][cache_key] < limit
    
    def _update_daily_count(self, user_id: str, action: str):
        """更新每日操作次数"""
        today = datetime.now().date().isoformat()
        cache_key = f"{user_id}_{action}_{today}"
        
        if cache_key not in self.cache["daily_limits"]:
            self.cache["daily_limits"][cache_key] = 0
        
        self.cache["daily_limits"][cache_key] += 1
    
    def _clear_user_cache(self, user_id: str):
        """清除用户相关缓存"""
        # 清除用户状态缓存
        cache_key = f"user_status_{user_id}"
        if cache_key in self.cache["user_status"]:
            del self.cache["user_status"][cache_key]
        
        # 清除待回复缓存
        cache_key = f"pending_replies_{user_id}"
        if cache_key in self.cache["pending_replies"]:
            del self.cache["pending_replies"][cache_key]
    
    def get_daily_stats(self, user_id: str) -> Dict[str, int]:
        """获取用户今日统计信息"""
        today = datetime.now().date().isoformat()
        catch_key = f"{user_id}_catch_{today}"
        throw_key = f"{user_id}_throw_{today}"
        
        return {
            "catch_count": self.cache["daily_limits"].get(catch_key, 0),
            "throw_count": self.cache["daily_limits"].get(throw_key, 0),
            "catch_remaining": max(0, 5 - self.cache["daily_limits"].get(catch_key, 0))
        }
    
    def mark_listened(self, type: int, target_id: int, listen_type: int = 1):
        """标记已收听"""
        user_id = self.user.user_id
        user_type = self.user.user_type
        data = {
            "userId": user_id,
            "userType": user_type,
            "userName": self.user.user_name,
            "unitId": self.user.group_id,
            "schoolId": self.user.school_id,
            "type": type,
            "targetId": target_id,
            "listenType": listen_type
        }
        return self._make_request("POST", "/drift-bottle/mark-listened", data)