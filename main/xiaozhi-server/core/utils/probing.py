"""
大模型是否需要追问或主动式引导式用户问问题
"""
import asyncio

TAG = __name__

"""
问题列表，当第一个问题不需要再次询问的时候，依次会问第二个问题，直到都不需要询问。
"""
QUESTION_TYPE_LIST = [
    "姓名、生日、人际关系、年龄、居住地和重要日期、爱好、习惯",
]

class ProactiveManager:
    def __init__(self, custom_question_list = None, logger=None):
        self.logger = logger
        self.question_index = 0
        self.question_list = QUESTION_TYPE_LIST
        if custom_question_list is not None and len(custom_question_list) > 0:
            self.question_list = custom_question_list
        if len(self.question_list) > 0:
            self.question = self.question_list[self.question_index]
        if not self.question:
            raise ValueError("请确认问题类型或者自定义问题")
        # 是否需要主动引导
        self.need_proactive = False
        # 如果需要主动询问，则下面是需要附加到系统提示词的内容
        self.proactive_prompt = """
<主动式引导>
注意：在对话中，请务必在合适的时机，主动、自然地询问用户的以下信息：
- **""" + self.question + """** 
请确保问题要融入对话的上下文中，不要生硬地索要信息。

** 不要主动询问和 """ + self.question + """ 无关的话题 **
</主动式引导>
"""

    def init_proactive(self, llm, memory, loop):
        """
        根据用户的问题，以及用户的记忆，判断是否已经把用户信息补全，如果补全了，则不再需要主动引导
        """
        self.logger.bind(tag=TAG).info("need_proactive 开始初始化")
        if llm is None:
            self.logger.bind(tag=TAG).info("need_proactive llm 为空")
            self.need_proactive = False
            return
        if memory is None:
            self.logger.bind(tag=TAG).info("need_proactive memory 为空")
            self.need_proactive = False
            return
        need = self.__need_proactive_by_llm(llm, memory, loop)
        while not need and len(self.question_list) > self.question_index + 1:
            self.question_index = self.question_index + 1
            self.question = self.question_list[self.question_index]
            need = self.__need_proactive_by_llm(llm, memory, loop)
        self.need_proactive = need
        self.logger.bind(tag=TAG).info("need_proactive 初始化：" + str(self.need_proactive))

    def __need_proactive_by_llm(self, llm, memory, loop):
        future = asyncio.run_coroutine_threadsafe(
            memory.query_memory(self.question), loop
        )
        memory_str = future.result()
        if memory_str is None or len(memory_str) == 0:
            memory_str = "暂无"
        llm_result = llm.response_no_stream(
            system_prompt="""你是一个精确的记忆信息完整性检查器。你的任务是根据提供的“记忆文本”，严格判断其中是否完全包含了“用户查询”中要求的所有具体方面。

        **任务流程：**
        1.  你将收到一个“用户查询”，它是一个列表，包含了用户想确认的多个具体信息点（例如：["生日", "爱好"]）。
        2.  你将收到一段“记忆文本”，这是一段从数据库中搜索出来的关于某个用户的文本记录。
        3.  你需要逐一判断“记忆文本”中是否**明确地**包含了“用户查询”中列出的**每一个**信息点。

        **输出规则：**
        - 如果记忆文本中**明确包含了查询列表中的每一项信息**，则输出数字：`1`
        - 如果记忆文本中**缺少了查询列表中的任何一项信息**，则输出数字：`0`

        **注意：**
        - 只输出一个数字，不要输出任何其他解释、文字或符号。
        - 判断必须严格。信息必须是明确提及的，不能是靠推理或暗示得出的。例如，记忆文本说“他很喜欢运动”，这明确包含了“爱好”中的“运动”，可以算作存在。但如果记忆文本只说“他很有活力”，则不能推断出“爱好”，算作缺失。

        **示例 1:**
        - 用户查询：["生日", "爱好"]
        - 记忆文本：“小王出生于1990年5月1日。他的兴趣爱好是读书和爬山。”
        - 输出：`1`  （原因：明确提到了生日“1990年5月1日”和爱好“读书、爬山”）

        **示例 2:**
        - 用户查询：["生日", "爱好"]
        - 记忆文本：“小王的爱好是打游戏。他来自北京。”
        - 输出：`0`  （原因：虽然提到了“爱好”，但完全没有提及“生日”）

        **示例 3:**
        - 用户查询：["生日", "爱好"]
        - 记忆文本：“小王的生日是秘密。”
        - 输出：`0`  （原因：虽然提到了“生日”这个词，但并没有提供具体的信息（如日期），因此视为“生日”信息缺失。必须同时有信息点和具体内容。）

        **现在开始你的任务：**""",
            user_prompt="用户查询：" + self.question + "\n记忆文本：" + memory_str
        )
        self.logger.bind(tag=TAG).info("need_proactive 初始化：{}, {}",self.question, llm_result)
        if "1" in llm_result:
            return False
        else:
            return True

    def update_proactive(self, llm, llm_response):
        """
        根据大模型的回答，判断大模型的回答中，是否带有引导式的追问，如果带有，则本次会话不再进行引导
        """
        if llm is None or llm_response is None:
            return
        # 如果本身已经不需要追问，则不再需要更新了
        if not self.need_proactive:
            return
        llm_result = llm.response_no_stream(
            system_prompt="""你是一个文本分析器。请严格根据以下规则进行分析：

**任务**
判断“回答内容”中是否包含与“主题内容”**相关**的引导式追问。

**判断规则**
必须同时满足以下两个条件，才可判定为“1”：
1.  **是追问**：回答内容中包含试图引导另一方（如AI）就当前话题进行回答或发表看法的语句（例如：“你呢？”“你的看法是？”“你觉得怎么样？”）。
2.  **主题相关**：该追问的核心指向必须与提供的“主题内容”直接相关。如果追问引入了全新的、不相关的主题，则不算。

**输出要求**
- 如果包含相关追问，输出：`1`
- 如果不包含，或追问与主题无关，输出：`0`
- 只输出一个数字，不要任何其他解释。

**分析对象**
- 主题内容：[此处插入主题内容]
- 回答内容：[此处插入回答内容]""",
            user_prompt="主题内容：" + self.question + "\n回答内容：" + llm_response
        )
        self.logger.bind(tag=TAG).info("need_proactive 更新：{}, {}", llm_result, llm_response)
        # 有追问，则本次不再追问
        if "1" in llm_result:
            self.need_proactive = False
        else:
            self.need_proactive = True
