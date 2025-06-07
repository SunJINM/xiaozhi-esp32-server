import google.generativeai as genai
from core.utils.util import check_model_key
from core.providers.llm.base import LLMProviderBase
from config.logger import setup_logging
import requests
import json

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        """初始化Gemini LLM Provider"""
        self.model_name = config.get("model_name", "gemini-1.5-pro")
        self.api_key = config.get("api_key")
        self.http_proxy = config.get("http_proxy")
        self.https_proxy = config.get("https_proxy")
        have_key = check_model_key("LLM", self.api_key)

        if not check_model_key("LLM", self.api_key):
            raise ValueError("无效的Gemini API Key，请检查是否配置正确")

        if http_proxy or https_proxy:
            log.bind(tag=TAG).info(
                f"检测到Gemini代理配置，开始测试代理连通性和设置代理环境..."
            )
            setup_proxy_env(http_proxy, https_proxy)
            log.bind(tag=TAG).info(
                f"Gemini 代理设置成功 - HTTP: {http_proxy}, HTTPS: {https_proxy}"
            )
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

        self.gen_cfg = GenerationConfig(
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            max_output_tokens=2048,
        )

    @staticmethod
    def _build_tools(funcs: List[Dict[str, Any]] | None):
        if not funcs:
            return None
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=f["function"]["name"],
                        description=f["function"]["description"],
                        parameters=f["function"]["parameters"],
                    )
                    for f in funcs
                ]
            )
        ]

    # Gemini文档提到，无需维护session-id，直接用dialogue拼接而成
    def response(self, session_id, dialogue, **kwargs):
        yield from self._generate(dialogue, None)

    def response_with_functions(self, session_id, dialogue, functions=None):
        yield from self._generate(dialogue, self._build_tools(functions))

    def _generate(self, dialogue, tools):
        role_map = {"assistant": "model", "user": "user"}
        contents: list = []
        # 拼接对话
        for m in dialogue:
            r = m["role"]

            if r == "assistant" and "tool_calls" in m:
                tc = m["tool_calls"][0]
                contents.append(
                    {
                        "role": "model",
                        "parts": [
                            {
                                "function_call": {
                                    "name": tc["function"]["name"],
                                    "args": json.loads(tc["function"]["arguments"]),
                                }
                            }
                        ],
                    }
                )
                continue

            if r == "tool":
                contents.append(
                    {
                        "role": "model",
                        "parts": [{"text": str(m.get("content", ""))}],
                    }
                )
                continue

            contents.append(
                {
                    "role": role_map.get(r, "user"),
                    "parts": [{"text": str(m.get("content", ""))}],
                }
            )

        stream: GenerateContentResponse = self.model.generate_content(
            contents=contents,
            generation_config=self.gen_cfg,
            tools=tools,
            stream=True,
        )

        try:
            # 初始化Gemini客户端
            # 配置代理（如果提供了代理配置）
            self.proxies = None
            if self.http_proxy is not "" or self.https_proxy is not "":

                self.proxies = {
                    "http": self.http_proxy,
                    "https": self.https_proxy,
                }
                logger.bind(tag=TAG).info(f"Gemini set proxys:{self.proxies}")
                # 使用猴子补丁修改 google-generativeai 库的请求会话

                # 使用 session 对象配置 genai

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)

            # 设置生成参数
            self.generation_config = {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            self.chat = None
        except Exception as e:
            logger.bind(tag=TAG).error(f"Gemini初始化失败: {e}")
            self.model = None

    def response(self, session_id, dialogue):
        """生成Gemini对话响应"""
        if not self.model:
            yield "【Gemini服务未正确初始化】"
            return

        try:
            # 处理对话历史
            chat_history = []
            for msg in dialogue[:-1]:  # 历史对话
                role = "model" if msg["role"] == "assistant" else "user"
                content = msg["content"].strip()
                if content:
                    chat_history.append({"role": role, "parts": [{"text": content}]})

            # 获取当前消息
            current_msg = dialogue[-1]["content"]

            # 构建请求体
            request_body = {
                "contents": chat_history
                + [{"role": "user", "parts": [{"text": current_msg}]}],
                "generationConfig": self.generation_config,
            }

            # 构建请求URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

            # 构建请求头
            headers = {
                "Content-Type": "application/json",
            }

            # 发送POST请求,经测试手动 request 无法使用 stream 模式
            if self.proxies:
                response = requests.post(
                    url,
                    headers=headers,
                    json=request_body,
                    stream=False,
                    proxies=self.proxies,
                )
                try:
                    data = response.json()  # 直接解析JSON
                    if "candidates" in data and data["candidates"]:
                        yield data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        yield "未找到候选回复。"
                except json.JSONDecodeError as e:
                    yield f"JSON解码错误：{e}"
                except Exception as e:
                    yield f"发生错误：{e}"
            else:
                logger.bind(tag=TAG).info(f"Gemini stream mode ")
                chat = self.model.start_chat(history=chat_history)

                # 发送消息并获取流式响应
                response = chat.send_message(
                    current_msg, stream=True, generation_config=self.generation_config
                )
                # 处理流式响应
                for chunk in response:
                    if hasattr(chunk, "text") and chunk.text:
                        yield chunk.text

        except Exception as e:
            error_msg = str(e)
            logger.bind(tag=TAG).error(f"Gemini响应生成错误: {error_msg}")

            # 针对不同错误返回友好提示
            if "Rate limit" in error_msg:
                yield "【Gemini服务请求太频繁,请稍后再试】"
            elif "Invalid API key" in error_msg:
                yield "【Gemini API key无效】"
            else:
                yield f"【Gemini服务响应异常: {error_msg}】"

        except requests.exceptions.RequestException as e:
            yield f"请求失败：{e}"
        except json.JSONDecodeError as e:
            yield f"JSON解码错误：{e}"
        except Exception as e:
            yield f"发生错误：{e}"

    def response_with_functions(self, session_id, dialogue, functions=None):
        logger.bind(tag=TAG).info(f"gemini暂未实现完整的工具调用（function call）")
        return self.response(session_id, dialogue)
