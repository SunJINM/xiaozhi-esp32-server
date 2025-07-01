def get_abort_prompt_for_agent(agent_name: str) -> str:
    """
    生成智能体退出提示信息
    """

    ABORT_PROMPT = f"""
====

你需要根据用户的输入、历史对话和当前所在的智能体，决策用户是否有退出当前智能体功能的意图。

# 决策结果格式

决策结果采用 JSON 风格的标签进行格式化。决策结果是 booler 类型，且只能是 True 或者 False 之一。
结构如下：

<judge_result>
{{
    "result": "决策结果"
}}
</judge_result>


例如：
如果用户输入： 我要退出游戏

你应该按照以下格式回复：

<judge_result>
{{
    "result": "True"
}}
</judge_result>

始终遵循决策结果格式，以确保能够正确解析。

# 决策结果指南

1. 决策结果必须单独成一条消息，不要添加额外想法。消息必须以 <judge_result> 开头，以 </judge_result> 结尾，中间是决策结果的 JSON 数据。不需要额外的回复内容。
2. 只有用户有明确的指令，是退出游戏或功能时，才认为是退出。

====

用户聊天内容:

"""

    return ABORT_PROMPT