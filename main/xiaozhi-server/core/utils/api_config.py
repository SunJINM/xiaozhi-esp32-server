"""
API 配置工具类
用于统一管理外部 API 的基础 URL 配置
"""
import os
from config.config_loader import load_config


class APIConfig:
    """API 配置管理类"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = load_config()
    
    @property
    def base_url(self) -> str:
        """
        获取 API 基础 URL
        根据环境变量 PYTHON_PROFILES_ACTIVATE 自动选择对应的 URL
        - test: 使用测试环境 https://rest-test.xxt.cn
        - 其他环境: 使用生产环境 https://rest.xxt.cn
        """
        env = os.environ.get('PYTHON_PROFILES_ACTIVATE', 'dev')
        
        # 从配置文件获取 API 配置
        api_config = self._config.get('api', {})
        
        if env == 'test' or env == 'dev':
            return api_config.get('test_base_url', 'https://rest-test.xxt.cn')
        else:
            return api_config.get('base_url', 'https://rest.xxt.cn')
    
    @property
    def book_reading_url(self) -> str:
        """获取阅读相关 API 的完整 URL"""
        return f"{self.base_url}/book-reading"
    
    @property
    def xinzx_resource_url(self) -> str:
        """获取新知学习资源 API 的完整 URL"""
        # 注意：原代码中有些用的是 http，这里统一使用 https
        return f"{self.base_url}/xinzx-resource"
    
    @property
    def ai_photo_ybt_url(self) -> str:
        """获取 AI 图片故事 API 的完整 URL"""
        # 注意：原代码中有些用的是 http，这里统一使用 https
        return f"{self.base_url}/ai-photo-ybt"
    
    @property 
    def task_center_url(self) -> str:
        """获取任务中心 API 的完整 URL"""
        return f"{self.base_url}/task-center"
    
    @property
    def login_v2_url(self) -> str:
        """获取登录 v2 API 的完整 URL"""
        return f"{self.base_url}/login-v2"
    
    @property
    def wisdom_url(self) -> str:
        """获取智慧平台 API 的完整 URL"""
        return f"{self.base_url}/wisdom"
    
    @property
    def exam_score_url(self) -> str:
        """获取考试成绩 API 的完整 URL"""
        return f"{self.base_url}/exam-score"


# 创建全局实例
api_config = APIConfig()