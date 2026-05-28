#!/usr/bin/env python3
"""
LM Studio 模型评估套件 - 同步版本 (适配特定网络环境)
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.score_engine import ScoreEngine, CategoryScore

# ============================================================
# 同步 API 客户端
# ============================================================

class SyncLMStudioClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def chat_completion(self, messages: List[Dict], model: str, temperature: float = 0.0,
                        max_tokens: int = 2048, stream: bool = False) -> Dict:
        """发送聊天补全请求"""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }

        start_time = time.time()
        resp = self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=self.timeout
        )
        resp.raise_for_status()
        latency_ms = (time.time() - start_time) * 1000

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Handle reasoning models
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")
        if not content and reasoning:
            content = reasoning

        usage = data.get("usage", {})

        return {
            "content": content,
            "model": data.get("model", ""),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms
        }

    def measure_ttft(self, messages: List[Dict], model: str, runs: int = 2) -> Dict:
        """测量首 token 延迟"""
        ttft_values = []
        for _ in range(runs):
            start = time.time()
            result = self.chat_completion(messages, model, stream=False)
            ttft_values.append((time.time() - start) * 1000)

        return {
            "ttft_avg_ms": sum(ttft_values) / len(ttft_values),
            "ttft_min_ms": min(ttft_values),
            "ttft_max_ms": max(ttft_values)
        }

    def measure_throughput(self, messages: List[Dict], model: str, runs: int = 2) -> Dict:
        """测量吞吐量"""
        tps_values = []
        for _ in range(runs):
            result = self.chat_completion(messages, model, max_tokens=2048)
            if result["completion_tokens"] > 0:
                tps = (result["completion_tokens"] / result["latency_ms"]) * 1000
                tps_values.append(tps)

        return {
            "tps_avg": sum(tps_values) / len(tps_values) if tps_values else 0,
            "tps_min": min(tps_values) if tps_values else 0,
            "tps_max": max(tps_values) if tps_values else 0
        }

# ============================================================
# 简化版评估器
# ============================================================

class SimpleEvaluator:
    def __init__(self, client: SyncLMStudioClient, model: str):
        self.client = client
        self.model = model

    def evaluate_coding(self) -> CategoryScore:
        """代码能力评估 - 简化版"""
        tests = [
            {
                "name": "二分查找实现",
                "prompt": "请用 Python 实现一个通用的二分查找函数。要求:\n1. 函数签名: def binary_search(arr: list, target) -> int\n2. 在已排序数组中查找目标值\n3. 找到返回索引，未找到返回 -1\n4. 处理空数组和边界情况\n\n只输出代码，不要解释。",
                "keywords": ["def binary_search", "mid", "left", "right", "return -1"]
            },
            {
                "name": "LRU缓存实现",
                "prompt": "请用 Python 实现一个 LRU (最近最少使用) 缓存类。要求:\n1. 实现 get(key) 和 put(key, value) 方法\n2. 容量满时自动淘汰最近最少使用的元素\n\n只输出代码。",
                "keywords": ["class", "get", "put", "LRU", "cache"]
            },
            {
                "name": "Debug Bug修复",
                "prompt": "下面的函数有 Bug，请找出并修复:\n\ndef get_even_squares(numbers):\n    result = [n**2 for n in numbers if n % 2 == 1]\n    return result\n\n目标是获取所有偶数的平方。",
                "keywords": ["n % 2 == 0", "偶数", "修复", "even"]
            }
        ]

        total_score = 0
        max_score = 60
        details = []

        for test in tests:
            messages = [
                {"role": "system", "content": "你是一个专业的程序员。"},
                {"role": "user", "content": test["prompt"]}
            ]

            try:
                result = self.client.chat_completion(messages, self.model, max_tokens=1024)
                content = result["content"].lower()

                # 评分
                found_keywords = sum(1 for kw in test["keywords"] if kw.lower() in content)
                score = min(20, found_keywords * 5)
                total_score += score

                details.append({
                    "test": test["name"],
                    "score": score,
                    "max_score": 20,
                    "found_keywords": found_keywords
                })
            except Exception as e:
                details.append({"test": test["name"], "error": str(e), "score": 0})

        return CategoryScore(
            category="代码能力",
            score=total_score,
            max_score=max_score,
            details=details,
            weight=1.0
        )

    def evaluate_agent(self) -> CategoryScore:
        """Agent能力评估 - 简化版"""
        tests = [
            {
                "name": "工具调用理解",
                "prompt": "用户说: '帮我查一下北京今天的天气'。\n假设你有 get_weather(city, unit) 工具，你会如何调用？请用JSON格式输出调用参数。",
                "keywords": ["city", "北京", "celsius", "weather", "{", "}"]
            },
            {
                "name": "多步推理",
                "prompt": "一个袋子里有3个红球和5个蓝球。不放回地连续取2个球。两个都是红球的概率是多少？请给出计算过程。",
                "keywords": ["3/28", "3/8", "2/7", "概率", "计算"]
            },
            {
                "name": "指令遵循",
                "prompt": "请用恰好3句话总结机器学习的核心概念。每句话不超过20个字。",
                "check": lambda x: len([s for s in x.split('。') if s.strip()]) == 3
            }
        ]

        total_score = 0
        max_score = 60
        details = []

        for test in tests:
            messages = [
                {"role": "system", "content": "你是一个智能助手。"},
                {"role": "user", "content": test["prompt"]}
            ]

            try:
                result = self.client.chat_completion(messages, self.model, max_tokens=1024)
                content = result["content"]

                if "check" in test:
                    score = 20 if test["check"](content) else 10
                else:
                    found_keywords = sum(1 for kw in test["keywords"] if kw.lower() in content.lower())
                    score = min(20, found_keywords * 5)

                total_score += score
                details.append({"test": test["name"], "score": score, "max_score": 20})
            except Exception as e:
                details.append({"test": test["name"], "error": str(e), "score": 0})

        return CategoryScore(
            category="Agent能力",
            score=total_score,
            max_score=max_score,
            details=details,
            weight=1.0
        )

    def evaluate_reasoning(self) -> CategoryScore:
        """通用推理评估 - 简化版"""
        tests = [
            {
                "name": "逻辑推理",
                "prompt": "前提1: 所有程序员都懂逻辑。前提2: 小明是程序员。问: 小明懂逻辑吗？",
                "keywords": ["懂", "是的", "因为", "所以", "正确"]
            },
            {
                "name": "阅读理解",
                "prompt": "Redis 是一个开源的内存数据结构存储系统。Redis 为什么能提供极高的读写性能？",
                "keywords": ["内存", "memory", "存储", "数据结构"]
            },
            {
                "name": "知识问答",
                "prompt": "请解释什么是 CAP 定理。",
                "keywords": ["一致性", "可用性", "分区容错", "consistency", "availability", "partition"]
            }
        ]

        total_score = 0
        max_score = 60
        details = []

        for test in tests:
            messages = [
                {"role": "system", "content": "你是一个推理专家。"},
                {"role": "user", "content": test["prompt"]}
            ]

            try:
                result = self.client.chat_completion(messages, self.model, max_tokens=1024)
                content = result["content"].lower()
                found_keywords = sum(1 for kw in test["keywords"] if kw.lower() in content)
                score = min(20, found_keywords * 5)
                total_score += score
                details.append({"test": test["name"], "score": score, "max_score": 20})
            except Exception as e:
                details.append({"test": test["name"], "error": str(e), "score": 0})

        return CategoryScore(
            category="通用推理",
            score=total_score,
            max_score=max_score,
            details=details,
            weight=1.0
        )

    def evaluate_performance(self) -> CategoryScore:
        """性能基准测试 - 简化版"""
        details = []
        total_score = 0

        # TTFT 测试
        try:
            messages = [{"role": "user", "content": "请解释什么是机器学习。"}]
            ttft_result = self.client.measure_ttft(messages, self.model, runs=2)
            avg_ttft = ttft_result["ttft_avg_ms"]

            if avg_ttft <= 500:
                ttft_score = 30
            elif avg_ttft <= 1500:
                ttft_score = 22
            elif avg_ttft <= 3000:
                ttft_score = 15
            else:
                ttft_score = 8

            total_score += ttft_score
            details.append({
                "test": "首Token延迟",
                "score": ttft_score,
                "max_score": 30,
                "metrics": {"avg_ttft_ms": round(avg_ttft, 2)}
            })
        except Exception as e:
            details.append({"test": "首Token延迟", "error": str(e), "score": 0})

        # 吞吐量测试
        try:
            messages = [{"role": "user", "content": "请写一篇关于人工智能的文章，至少500字。"}]
            tps_result = self.client.measure_throughput(messages, self.model, runs=2)
            avg_tps = tps_result["tps_avg"]

            if avg_tps >= 30:
                tps_score = 25
            elif avg_tps >= 15:
                tps_score = 18
            elif avg_tps >= 5:
                tps_score = 10
            else:
                tps_score = 5

            total_score += tps_score
            details.append({
                "test": "吞吐量",
                "score": tps_score,
                "max_score": 25,
                "metrics": {"avg_tps": round(avg_tps, 2)}
            })
        except Exception as e:
            details.append({"test": "吞吐量", "error": str(e), "score": 0})

        # 简单响应测试
        try:
            start = time.time()
            messages = [{"role": "user", "content": "你好"}]
            self.client.chat_completion(messages, self.model, max_tokens=100)
            latency = (time.time() - start) * 1000

            if latency < 1000:
                resp_score = 15
            elif latency < 3000:
                resp_score = 10
            else:
                resp_score = 5

            total_score += resp_score
            details.append({
                "test": "响应速度",
                "score": resp_score,
                "max_score": 15,
                "metrics": {"latency_ms": round(latency, 2)}
            })
        except Exception as e:
            details.append({"test": "响应速度", "error": str(e), "score": 0})

        return CategoryScore(
            category="性能基准",
            score=total_score,
            max_score=70,
            details=details,
            weight=1.0
        )

# ============================================================
# 主函数
# ============================================================

def main():
    # 配置
    API_URL = "http://59.55.125.214:1024"
    API_KEY = "sk-lm-kkZxEu1e:YagcQehqsGQGNQD0cyIH"
    MODEL_ID = "qwopus3.6-35b-a3b-v1-mtp"
    MODEL_NAME = "qwopus3.6-35b-a3b-v1-mtp"

    print("=" * 60)
    print("🤖 LM Studio 模型评估套件 (同步版本)")
    print("=" * 60)
    print(f"模型: {MODEL_NAME}")
    print(f"API: {API_URL}")
    print("=" * 60)

    client = SyncLMStudioClient(API_URL, API_KEY)
    evaluator = SimpleEvaluator(client, MODEL_ID)
    score_engine = ScoreEngine()
    result = score_engine.create_result(MODEL_NAME, MODEL_ID)

    # 1. 代码能力
    print("\n[1/4] 💻 代码能力评估中...")
    coding_score = evaluator.evaluate_coding()
    score_engine.add_dimension_score(result, "coding", [coding_score])
    print(f"  ✅ 代码能力: {coding_score.score:.1f} 分")

    # 2. Agent能力
    print("\n[2/4] 🤖 Agent能力评估中...")
    agent_score = evaluator.evaluate_agent()
    score_engine.add_dimension_score(result, "agent", [agent_score])
    print(f"  ✅ Agent能力: {agent_score.score:.1f} 分")

    # 3. 通用推理
    print("\n[3/4] 🧠 通用推理评估中...")
    reasoning_score = evaluator.evaluate_reasoning()
    score_engine.add_dimension_score(result, "reasoning", [reasoning_score])
    print(f"  ✅ 通用推理: {reasoning_score.score:.1f} 分")

    # 4. 性能基准
    print("\n[4/4] ⚡ 性能基准测试中...")
    perf_score = evaluator.evaluate_performance()
    score_engine.add_dimension_score(result, "performance", [perf_score])
    print(f"  ✅ 性能基准: {perf_score.score:.1f} 分")
    for detail in perf_score.details:
        if "metrics" in detail:
            print(f"     - {detail['test']}: {detail['score']}/{detail['max_score']}")
            for k, v in detail["metrics"].items():
                print(f"       {k}: {v}")

    # 计算总分
    score_engine.finalize(result)

    # 保存结果
    os.makedirs("results", exist_ok=True)
    result_path = score_engine.save_result(result, "results")
    print(f"\n📁 结果已保存: {result_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 评估结果摘要")
    print("=" * 60)
    print(f"模型: {result.model_name}")
    print(f"时间: {result.eval_time}")
    print("-" * 60)
    label_map = {"coding": "代码能力", "agent": "Agent能力", "reasoning": "通用推理", "performance": "性能基准"}
    for dim_name, dim_score in result.dimensions.items():
        label = label_map.get(dim_name, dim_name)
        print(f"{label:12s}: {dim_score.score:6.2f} 分")
    print("-" * 60)
    print(f"{'综合评分':12s}: {result.overall_score:6.2f} / 100")
    print("=" * 60)

    return result

if __name__ == "__main__":
    main()
