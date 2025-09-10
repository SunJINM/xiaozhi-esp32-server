"""
TTS动态音色管理器
支持智能体与音色的映射关系管理
"""

from typing import Dict, Optional
from config.logger import setup_logging

TAG = "VoiceManager"
logger = setup_logging()


class VoiceManager:
    """TTS音色管理器"""
    
    def __init__(self):
        """初始化音色管理器"""
        # 智能体与音色的映射字典
        # 支持多种TTS Provider的音色，会根据当前使用的TTS自动选择对应音色
        self.agent_voice_map: Dict[str, str] = {
            # 剧本杀 - 使用成熟男声
            "script_murder": self._get_voice_mapping("male_mature"),
            # 阅读伙伴 - 使用温和女声  
            "reading_partner": self._get_voice_mapping("female_warm"),
            # 漂流瓶 - 使用青年男声
            "drift_bottle": self._get_voice_mapping("male_young"),
            # 默认音色 - 使用标准女声
            "default": self._get_voice_mapping("linjianvhai")
        }
    
    def _get_voice_mapping(self, voice_type: str) -> str:
        """
        根据音色类型返回对应的音色名称
        优先使用火山引擎音色，如果没有配置则降级到EdgeTTS
        """
        # 火山引擎TTS音色映射
        huoshan_voice_map = {
            "male_mature": "zh_male_lengkugege_emo_v2_mars_bigtts",     # 成熟男声 - 庄重
            "female_warm": "S_1AP67Oqj1",  # 猪八戒
            "male_young": "zh_male_yangguangqingnian_emo_v2_mars_bigtts",    # 青年男声 - 少年自信
            "female_standard": "zh_female_shuangkuaisisi_emo_v2_mars_bigtts",   # 标准女声 - 度小语
            "yuanqitianmei": "ICL_zh_female_wuxi_tob",        # 元气甜妹
            "linjianvhai": "zh_female_linjianvhai_moon_bigtts"
        }
        
        # EdgeTTS音色映射（降级选择）
        edge_voice_map = {
            "male_mature": "zh-CN-YunyeNeural",        # 成熟男声
            "female_warm": "zh-CN-XiaoxiaoNeural",     # 温和女声
            "male_young": "zh-CN-YunyangNeural",       # 青年男声  
            "female_standard": "zh-CN-XiaoxiaoNeural"  # 标准女声
        }
        
        # 优先返回火山引擎音色，如果没有则返回EdgeTTS音色
        return huoshan_voice_map.get(voice_type, edge_voice_map.get(voice_type, "zh-CN-XiaoxiaoNeural"))
        
    def get_voice_for_agent(self, agent_name: Optional[str]) -> Optional[str]:
        """
        根据智能体名称获取对应的音色
        
        Args:
            agent_name: 智能体名称
            
        Returns:
            str: 对应的音色名称，如果没有找到则返回默认音色
        """
        return self.agent_voice_map.get("default")
        if not agent_name:
            return self.agent_voice_map.get("default")
            
        voice = self.agent_voice_map.get(agent_name)
        if voice:
            logger.bind(tag=TAG).debug(f"智能体 {agent_name} 使用音色: {voice}")
            return voice
        else:
            default_voice = self.agent_voice_map.get("default")
            logger.bind(tag=TAG).debug(f"智能体 {agent_name} 未配置音色，使用默认音色: {default_voice}")
            return default_voice
    
    def set_agent_voice(self, agent_name: str, voice: str):
        """
        设置智能体的音色
        
        Args:
            agent_name: 智能体名称
            voice: 音色名称
        """
        self.agent_voice_map[agent_name] = voice
        logger.bind(tag=TAG).info(f"设置智能体 {agent_name} 音色为: {voice}")
    
    def get_all_mappings(self) -> Dict[str, str]:
        """
        获取所有智能体音色映射
        
        Returns:
            Dict[str, str]: 智能体与音色的映射字典
        """
        return self.agent_voice_map.copy()
    
    def update_mappings(self, mappings: Dict[str, str]):
        """
        批量更新智能体音色映射
        
        Args:
            mappings: 新的映射字典
        """
        self.agent_voice_map.update(mappings)
        logger.bind(tag=TAG).info(f"批量更新音色映射: {mappings}")


# 全局音色管理器实例
voice_manager = VoiceManager()