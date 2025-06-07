import time
import aiohttp
import asyncio
from tabulate import tabulate
from typing import Dict, List
from core.utils.llm import create_instance as create_llm_instance
from core.utils.tts import create_instance as create_tts_instance
import statistics
from config.settings import load_config
import inspect
import os
import logging

# 设置全局日志级别为WARNING，抑制INFO级别日志
logging.basicConfig(level=logging.WARNING)


class AsyncPerformanceTester:
    def __init__(self):
        self.config = load_config()
        self.test_sentences = self.config.get("module_test", {}).get(
            "test_sentences",
            [
                "你好，请介绍一下你自己",
                "What's the weather like today?",
                "请用100字概括量子计算的基本原理和应用前景",
            ],
        )
        self.results = {"llm": {}, "tts": {}, "combinations": []}

    async def _check_ollama_service(self, base_url: str, model_name: str) -> bool:
        """异步检查Ollama服务状态"""
        async with aiohttp.ClientSession() as session:
            try:
                # 检查服务是否可用
                async with session.get(f"{base_url}/api/version") as response:
                    if response.status != 200:
                        print(f"🚫 Ollama服务未启动或无法访问: {base_url}")
                        return False

                # 检查模型是否存在
                async with session.get(f"{base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        if not any(model["name"] == model_name for model in models):
                            print(
                                f"🚫 Ollama模型 {model_name} 未找到，请先使用 ollama pull {model_name} 下载"
                            )
                            return False
                    else:
                        print(f"🚫 无法获取Ollama模型列表")
                        return False
                return True
            except Exception as e:
                print(f"🚫 无法连接到Ollama服务: {str(e)}")
                return False

    async def _test_tts(self, tts_name: str, config: Dict) -> Dict:
        """异步测试单个TTS性能"""
        try:
            logging.getLogger("core.providers.tts.base").setLevel(logging.WARNING)

            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and any(x in config[field] for x in ["你的", "placeholder"])
                for field in token_fields
            ):
                print(f"⏭️  TTS {tts_name} 未配置access_token/api_key，已跳过")
                return {"name": tts_name, "type": "tts", "errors": 1}

            module_type = config.get("type", tts_name)
            tts = create_tts_instance(module_type, config, delete_audio_file=True)

            print(f"🎵 测试 TTS: {tts_name}")

            tmp_file = tts.generate_filename()
            await tts.text_to_speak("连接测试", tmp_file)

            if not tmp_file or not os.path.exists(tmp_file):
                print(f"❌ {tts_name} 连接失败")
                return {"name": tts_name, "type": "tts", "errors": 1}

            total_time = 0
            test_count = len(self.test_sentences[:2])

            for i, sentence in enumerate(self.test_sentences[:2], 1):
                start = time.time()
                tmp_file = tts.generate_filename()
                await tts.text_to_speak(sentence, tmp_file)
                duration = time.time() - start
                total_time += duration

                if tmp_file and os.path.exists(tmp_file):
                    print(f"✓ {tts_name} [{i}/{test_count}]")
                else:
                    print(f"✗ {tts_name} [{i}/{test_count}]")
                    return {"name": tts_name, "type": "tts", "errors": 1}

            return {
                "name": tts_name,
                "type": "tts",
                "avg_time": total_time / test_count,
                "errors": 0,
            }

        except Exception as e:
            print(f"⚠️ {tts_name} 测试失败: {str(e)}")
            return {"name": tts_name, "type": "tts", "errors": 1}

    async def _test_stt(self, stt_name: str, config: Dict) -> Dict:
        """异步测试单个STT性能"""
        try:
            logging.getLogger("core.providers.asr.base").setLevel(logging.WARNING)
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and any(x in config[field] for x in ["你的", "placeholder"])
                for field in token_fields
            ):
                print(f"⏭️  STT {stt_name} 未配置access_token/api_key，已跳过")
                return {"name": stt_name, "type": "stt", "errors": 1}

            module_type = config.get("type", stt_name)
            stt = create_stt_instance(module_type, config, delete_audio_file=True)
            stt.audio_format = "pcm"

            print(f"🎵 测试 STT: {stt_name}")

            text, _ = await stt.speech_to_text(
                [self.test_wav_list[0]], "1", stt.audio_format
            )

            if text is None:
                print(f"❌ {stt_name} 连接失败")
                return {"name": stt_name, "type": "stt", "errors": 1}

            total_time = 0
            test_count = len(self.test_wav_list)

            for i, sentence in enumerate(self.test_wav_list, 1):
                start = time.time()
                text, _ = await stt.speech_to_text([sentence], "1", stt.audio_format)
                duration = time.time() - start
                total_time += duration

                if text:
                    print(f"✓ {stt_name} [{i}/{test_count}]")
                else:
                    print(f"✗ {stt_name} [{i}/{test_count}]")
                    return {"name": stt_name, "type": "stt", "errors": 1}

            return {
                "name": stt_name,
                "type": "stt",
                "avg_time": total_time / test_count,
                "errors": 0,
            }

        except Exception as e:
            print(f"⚠️ {stt_name} 测试失败: {str(e)}")
            return {"name": stt_name, "type": "stt", "errors": 1}

    async def _test_llm(self, llm_name: str, config: Dict) -> Dict:
        """异步测试单个LLM性能"""
        try:
            # 对于Ollama，跳过api_key检查并进行特殊处理
            if llm_name == "Ollama":
                base_url = config.get("base_url", "http://localhost:11434")
                model_name = config.get("model_name")
                if not model_name:
                    print(f"🚫 Ollama未配置model_name")
                    return {"name": llm_name, "type": "llm", "errors": 1}

                if not await self._check_ollama_service(base_url, model_name):
                    return {"name": llm_name, "type": "llm", "errors": 1}
            else:
                if "api_key" in config and any(
                    x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]
                ):
                    print(f"🚫 跳过未配置的LLM: {llm_name}")
                    return {"name": llm_name, "type": "llm", "errors": 1}

            # 获取实际类型（兼容旧配置）
            module_type = config.get("type", llm_name)
            llm = create_llm_instance(module_type, config)

            # 统一使用UTF-8编码
            test_sentences = [
                s.encode("utf-8").decode("utf-8") for s in self.test_sentences
            ]

            # 创建所有句子的测试任务
            sentence_tasks = []
            for sentence in test_sentences:
                sentence_tasks.append(
                    self._test_single_sentence(llm_name, llm, sentence)
                )

            # 并发执行所有句子测试
            sentence_results = await asyncio.gather(*sentence_tasks)

            # 处理结果
            valid_results = [r for r in sentence_results if r is not None]
            if not valid_results:
                print(f"⚠️  {llm_name} 无有效数据，可能配置错误")
                return {"name": llm_name, "type": "llm", "errors": 1}

            first_token_times = [r["first_token_time"] for r in valid_results]
            response_times = [r["response_time"] for r in valid_results]

            # 过滤异常数据
            mean = statistics.mean(response_times)
            stdev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            filtered_times = [t for t in response_times if t <= mean + 3 * stdev]

            if len(filtered_times) < len(test_sentences) * 0.5:
                print(f"⚠️  {llm_name} 有效数据不足，可能网络不稳定")
                return {"name": llm_name, "type": "llm", "errors": 1}

            return {
                "name": llm_name,
                "type": "llm",
                "avg_response": sum(response_times) / len(response_times),
                "avg_first_token": sum(first_token_times) / len(first_token_times),
                "std_first_token": (
                    statistics.stdev(first_token_times)
                    if len(first_token_times) > 1
                    else 0
                ),
                "std_response": (
                    statistics.stdev(response_times) if len(response_times) > 1 else 0
                ),
                "errors": 0,
            }
        except Exception as e:
            print(f"LLM {llm_name} 测试失败: {str(e)}")
            return {"name": llm_name, "type": "llm", "errors": 1}

    async def _test_single_sentence(self, llm_name: str, llm, sentence: str) -> Dict:
        """测试单个句子的性能"""
        try:
            print(f"📝 {llm_name} 开始测试: {sentence[:20]}...")
            sentence_start = time.time()
            first_token_received = False
            first_token_time = None

            async def process_response():
                nonlocal first_token_received, first_token_time
                for chunk in llm.response(
                    "perf_test", [{"role": "user", "content": sentence}]
                ):
                    if not first_token_received and chunk.strip() != "":
                        first_token_time = time.time() - sentence_start
                        first_token_received = True
                        print(f"✓ {llm_name} 首个Token: {first_token_time:.3f}s")
                    yield chunk

            response_chunks = []
            async for chunk in process_response():
                response_chunks.append(chunk)

            response_time = time.time() - sentence_start
            print(f"✓ {llm_name} 完成响应: {response_time:.3f}s")

            if first_token_time is None:
                first_token_time = (
                    response_time  # 如果没有检测到first token，使用总响应时间
                )

            return {
                "name": llm_name,
                "type": "llm",
                "first_token_time": first_token_time,
                "response_time": response_time,
            }
        except Exception as e:
            print(f"⚠️ {llm_name} 句子测试失败: {str(e)}")
            return None

    def _generate_combinations(self):
        """生成最佳组合建议"""
        valid_llms = [
            k
            for k, v in self.results["llm"].items()
            if v["errors"] == 0 and v["avg_first_token"] >= 0.05
        ]
        valid_tts = [k for k, v in self.results["tts"].items() if v["errors"] == 0]

        # 找出基准值
        min_first_token = (
            min([self.results["llm"][llm]["avg_first_token"] for llm in valid_llms])
            if valid_llms
            else 1
        )
        min_tts_time = (
            min([self.results["tts"][tts]["avg_time"] for tts in valid_tts])
            if valid_tts
            else 1
        )

        for llm in valid_llms:
            for tts in valid_tts:
                # 计算相对性能分数（越小越好）
                llm_score = (
                    self.results["llm"][llm]["avg_first_token"] / min_first_token
                )
                tts_score = self.results["tts"][tts]["avg_time"] / min_tts_time

                # 计算稳定性分数（标准差/平均值，越小越稳定）
                llm_stability = (
                    self.results["llm"][llm]["std_first_token"]
                    / self.results["llm"][llm]["avg_first_token"]
                )

                # 综合得分（考虑性能和稳定性）
                # 性能权重0.7，稳定性权重0.3
                llm_final_score = llm_score * 0.7 + llm_stability * 0.3

                # 总分 = LLM得分(70%) + TTS得分(30%)
                total_score = llm_final_score * 0.7 + tts_score * 0.3

                self.results["combinations"].append(
                    {
                        "llm": llm,
                        "tts": tts,
                        "score": total_score,
                        "details": {
                            "llm_first_token": self.results["llm"][llm][
                                "avg_first_token"
                            ],
                            "llm_stability": llm_stability,
                            "tts_time": self.results["tts"][tts]["avg_time"],
                        },
                    }
                )

        # 分数越小越好
        self.results["combinations"].sort(key=lambda x: x["score"])

    def _print_results(self):
        """打印测试结果"""
        llm_table = []
        for name, data in self.results["llm"].items():
            if data["errors"] == 0:
                stability = data["std_first_token"] / data["avg_first_token"]
                llm_table.append(
                    [
                        name,  # 不需要固定宽度，让tabulate自己处理对齐
                        f"{data['avg_first_token']:.3f}秒",
                        f"{data['avg_response']:.3f}秒",
                        f"{stability:.3f}",
                    ]
                )

        if llm_table:
            print("\nLLM 性能排行:")
            print(
                tabulate(
                    llm_table,
                    headers=["模型名称", "首字耗时", "总耗时", "稳定性"],
                    tablefmt="github",
                    colalign=("left", "right", "right", "right"),
                    disable_numparse=True,
                )
            )
        else:
            print("\n⚠️ 没有可用的LLM模块进行测试。")

        tts_table = []
        for name, data in self.results["tts"].items():
            if data["errors"] == 0:
                tts_table.append([name, f"{data['avg_time']:.3f}秒"])  # 不需要固定宽度

        if tts_table:
            print("\nTTS 性能排行:")
            print(
                tabulate(
                    tts_table,
                    headers=["模型名称", "合成耗时"],
                    tablefmt="github",
                    colalign=("left", "right"),
                    disable_numparse=True,
                )
            )
        else:
            print("\n⚠️ 没有可用的TTS模块进行测试。")

        if self.results["combinations"]:
            print("\n推荐配置组合 (得分越小越好):")
            combo_table = []
            for combo in self.results["combinations"][:5]:
                combo_table.append(
                    [
                        f"{combo['llm']} + {combo['tts']}",  # 不需要固定宽度
                        f"{combo['score']:.3f}",
                        f"{combo['details']['llm_first_token']:.3f}秒",
                        f"{combo['details']['llm_stability']:.3f}",
                        f"{combo['details']['tts_time']:.3f}秒",
                    ]
                )

            print(
                tabulate(
                    combo_table,
                    headers=[
                        "组合方案",
                        "综合得分",
                        "LLM首字耗时",
                        "稳定性",
                        "TTS合成耗时",
                    ],
                    tablefmt="github",
                    colalign=("left", "right", "right", "right", "right"),
                    disable_numparse=True,
                )
            )
        else:
            print("\n⚠️ 没有可用的模块组合建议。")

    def _process_results(self, all_results):
        """处理测试结果"""
        for result in all_results:
            if result["errors"] == 0:
                if result["type"] == "llm":
                    self.results["llm"][result["name"]] = result
                else:
                    self.results["tts"][result["name"]] = result

    async def run(self):
        """执行全量异步测试"""
        print("🔍 开始筛选可用模块...")

        # 创建所有测试任务
        all_tasks = []

        # LLM测试任务
        for llm_name, config in self.config.get("LLM", {}).items():
            # 检查配置有效性
            if llm_name == "CozeLLM":
                if any(x in config.get("bot_id", "") for x in ["你的"]) or any(
                    x in config.get("user_id", "") for x in ["你的"]
                ):
                    print(f"⏭️  LLM {llm_name} 未配置bot_id/user_id，已跳过")
                    continue
            elif "api_key" in config and any(
                x in config["api_key"] for x in ["你的", "placeholder", "sk-xxx"]
            ):
                print(f"⏭️  LLM {llm_name} 未配置api_key，已跳过")
                continue

            # 对于Ollama，先检查服务状态
            if llm_name == "Ollama":
                base_url = config.get("base_url", "http://localhost:11434")
                model_name = config.get("model_name")
                if not model_name:
                    print(f"🚫 Ollama未配置model_name")
                    continue

                if not await self._check_ollama_service(base_url, model_name):
                    continue

            print(f"📋 添加LLM测试任务: {llm_name}")
            module_type = config.get("type", llm_name)
            llm = create_llm_instance(module_type, config)

            # 为每个句子创建独立任务
            for sentence in self.test_sentences:
                sentence = sentence.encode("utf-8").decode("utf-8")
                all_tasks.append(self._test_single_sentence(llm_name, llm, sentence))

        # TTS测试任务
        for tts_name, config in self.config.get("TTS", {}).items():
            token_fields = ["access_token", "api_key", "token"]
            if any(
                field in config
                and any(x in config[field] for x in ["你的", "placeholder"])
                for field in token_fields
            ):
                print(f"⏭️  TTS {tts_name} 未配置access_token/api_key，已跳过")
                continue
            print(f"🎵 添加TTS测试任务: {tts_name}")
            all_tasks.append(self._test_tts(tts_name, config))

        print(
            f"\n✅ 找到 {len([t for t in all_tasks if 'test_single_sentence' in str(t)]) / len(self.test_sentences):.0f} 个可用LLM模块"
        )
        print(
            f"✅ 找到 {len([t for t in all_tasks if '_test_tts' in str(t)])} 个可用TTS模块"
        )
        print("\n⏳ 开始并发测试所有模块...\n")

        # 并发执行所有测试任务
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # 处理LLM结果
        llm_results = {}
        for result in [
            r
            for r in all_results
            if r and isinstance(r, dict) and r.get("type") == "llm"
        ]:
            llm_name = result["name"]
            if llm_name not in llm_results:
                llm_results[llm_name] = {
                    "name": llm_name,
                    "type": "llm",
                    "first_token_times": [],
                    "response_times": [],
                    "errors": 0,
                }
            llm_results[llm_name]["first_token_times"].append(
                result["first_token_time"]
            )
            llm_results[llm_name]["response_times"].append(result["response_time"])

        # 计算LLM平均值和标准差
        for llm_name, data in llm_results.items():
            if len(data["first_token_times"]) >= len(self.test_sentences) * 0.5:
                self.results["llm"][llm_name] = {
                    "name": llm_name,
                    "type": "llm",
                    "avg_response": sum(data["response_times"])
                    / len(data["response_times"]),
                    "avg_first_token": sum(data["first_token_times"])
                    / len(data["first_token_times"]),
                    "std_first_token": (
                        statistics.stdev(data["first_token_times"])
                        if len(data["first_token_times"]) > 1
                        else 0
                    ),
                    "std_response": (
                        statistics.stdev(data["response_times"])
                        if len(data["response_times"]) > 1
                        else 0
                    ),
                    "errors": 0,
                }

        # 处理TTS结果
        for result in [
            r
            for r in all_results
            if r and isinstance(r, dict) and r.get("type") == "tts"
        ]:
            if result["errors"] == 0:
                self.results["tts"][result["name"]] = result

        # 生成组合建议并打印结果
        print("\n📊 生成测试报告...")
        self._generate_combinations()
        self._print_results()


async def main():
    tester = AsyncPerformanceTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
