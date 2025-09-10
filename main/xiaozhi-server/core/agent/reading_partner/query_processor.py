"""
阅读伙伴查询预处理模块 - 简化版
两步处理：1.查询优化改写 2.直接检索
"""
from typing import List, Dict


class SimpleQueryProcessor:
    """简化的查询预处理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        
        # 查询优化改写提示词
        self.rewrite_prompt = """
            你是一个专业的阅读记忆检索助手。请根据用户的查询和对话历史，将用户的问题改写为更适合检索的形式。

            用户当前查询：{current_query}
            对话历史：{dialogue_history}

            请输出一个优化后的查询文本，要求：
            1. 如果查询中有代词（他/她/它/这个/那个等），根据对话历史将其替换为具体的人物或事物
            2. 补充必要的上下文信息，使查询更加明确和具体
            3. 保持查询的核心意图不变
            4. 直接输出改写后的查询，不要额外解释

            改写后的查询："""
    
    def rewrite_query(self, query: str, dialogue_history: List[Dict] = None) -> str:
        """
        步骤1：优化改写用户查询
        
        Args:
            query: 原始查询文本
            dialogue_history: 历史对话记录
            
        Returns:
            str: 优化后的查询文本
        """
        # 如果没有大模型或对话历史，直接返回原查询
        if not self.llm or not dialogue_history:
            return query
        
        try:
            # 格式化对话历史
            history_text = self._format_dialogue_history(dialogue_history)
            
            # 构建改写提示
            prompt = self.rewrite_prompt.format(
                current_query=query,
                dialogue_history=history_text
            )
            
            # 调用大模型进行查询改写
            rewritten_query = self.llm.response_no_stream(
                system_prompt = prompt,
                user_prompt = "请进行优化"
            )
            
            # 清理响应，提取改写后的查询
            rewritten_query = rewritten_query.strip()
            if rewritten_query.startswith("改写后的查询："):
                rewritten_query = rewritten_query[7:].strip()
            
            return rewritten_query if rewritten_query else query
            
        except Exception as e:
            print(f"查询改写失败，使用原查询: {e}")
            return query
    
    def _format_dialogue_history(self, dialogue_history: List[Dict], max_turns: int = 5) -> str:
        """格式化对话历史"""
        if not dialogue_history:
            return "无历史对话"
        
        # 取最近的几轮对话
        recent_dialogue = dialogue_history[-max_turns*2:] if len(dialogue_history) > max_turns*2 else dialogue_history
        
        formatted_history = []
        for msg in recent_dialogue:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                formatted_history.append(f"用户: {content}")
            elif role == 'assistant':
                formatted_history.append(f"助手: {content}")
        
        return "\n".join(formatted_history) if formatted_history else "无历史对话"


class EnhancedMemoryQuery:
    """简化的增强记忆查询类"""
    
    def __init__(self, memory_provider, llm=None):
        self.memory = memory_provider
        self.processor = SimpleQueryProcessor(llm)
    
    async def query_memory_enhanced(
        self, 
        query: str, 
        dialogue_history: List[Dict] = None,
        limit: int = 5
    ) -> str:
        """
        简化的增强记忆查询方法
        
        Args:
            query: 查询文本
            dialogue_history: 历史对话记录
            limit: 返回结果数量限制
            
        Returns:
            str: 格式化的记忆字符串
        """
        # 步骤1：查询优化改写
        optimized_query = self.processor.rewrite_query(query, dialogue_history)
        
        # 步骤2：直接检索
        try:
            memory_str = await self.memory.query_memory(optimized_query, limit=limit)
            
            # 如果优化查询没有结果，尝试原查询
            if not memory_str and optimized_query != query:
                memory_str = await self.memory.query_memory(query, limit=limit)
            
            return memory_str or ""
            
        except Exception as e:
            print(f"记忆查询失败: {e}")
            return ""