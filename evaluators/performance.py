"""
性能基准测试模块
评估维度: 首Token延迟(TTFT)、吞吐量(TPS)、并发处理能力
"""

from typing import Dict, Any, List
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


class PerformanceEvaluator:
    """性能基准测试评估器"""

    def __init__(self, client: LMStudioClient, config=None):
        self.client = client
        self.config = config

    async def evaluate(self, model: str, benchmark_config=None) -> List[CategoryScore]:
        """执行完整的性能基准测试"""
        categories = []

        # 1. 首Token延迟 (TTFT)
        ttft_score = await self._evaluate_ttft(model, benchmark_config)
        categories.append(ttft_score)

        # 2. 吞吐量 (TPS)
        tps_score = await self._evaluate_throughput(model, benchmark_config)
        categories.append(tps_score)

        # 3. 并发处理
        concurrent_score = await self._evaluate_concurrent(model, benchmark_config)
        categories.append(concurrent_score)

        return categories

    async def _evaluate_ttft(self, model: str, benchmark_config=None) -> CategoryScore:
        """评估首 Token 延迟"""
        config = benchmark_config or {}
        prompt = config.get("ttft_prompt", "请解释什么是机器学习。")
        runs = config.get("throughput_runs", 3)

        messages = [ChatMessage(role="user", content=prompt)]

        try:
            result = await self.client.measure_ttft(
                messages=messages,
                model=model,
                runs=runs
            )

            # 评分: TTFT 越低越好
            # < 200ms = 满分, 200-500ms = 良好, 500-1000ms = 一般, > 1000ms = 差
            avg_ttft = result["ttft_avg_ms"]
            if avg_ttft <= 200:
                score = 40
            elif avg_ttft <= 500:
                score = 35
            elif avg_ttft <= 1000:
                score = 25
            elif avg_ttft <= 2000:
                score = 15
            else:
                score = 5

            detail = {
                "test": "首Token延迟 (TTFT)",
                "score": score,
                "max_score": 40,
                "metrics": {
                    "avg_ttft_ms": round(avg_ttft, 2),
                    "min_ttft_ms": round(result["ttft_min_ms"], 2),
                    "max_ttft_ms": round(result["ttft_max_ms"], 2),
                    "p50_ttft_ms": round(result["ttft_p50_ms"], 2),
                    "runs": runs
                }
            }
        except Exception as e:
            score = 0
            detail = {
                "test": "首Token延迟 (TTFT)",
                "score": 0,
                "max_score": 40,
                "error": str(e)
            }

        return CategoryScore(
            category="首Token延迟",
            score=score,
            max_score=40,
            details=[detail],
            weight=0.40
        )

    async def _evaluate_throughput(self, model: str, benchmark_config=None) -> CategoryScore:
        """评估吞吐量"""
        config = benchmark_config or {}
        prompt = config.get("throughput_prompt", "请写一篇关于人工智能发展历史的详细文章，至少800字。")
        runs = config.get("throughput_runs", 3)

        messages = [ChatMessage(role="user", content=prompt)]

        try:
            result = await self.client.measure_throughput(
                messages=messages,
                model=model,
                runs=runs,
                max_tokens=4096
            )

            # 评分: TPS 越高越好
            # > 50 tps = 满分, 30-50 = 良好, 15-30 = 一般, < 15 = 差
            avg_tps = result["tps_avg"]
            if avg_tps >= 50:
                score = 35
            elif avg_tps >= 30:
                score = 30
            elif avg_tps >= 15:
                score = 22
            elif avg_tps >= 5:
                score = 15
            else:
                score = 5

            detail = {
                "test": "吞吐量 (TPS)",
                "score": score,
                "max_score": 35,
                "metrics": {
                    "avg_tps": round(avg_tps, 2),
                    "min_tps": round(result["tps_min"], 2),
                    "max_tps": round(result["tps_max"], 2),
                    "avg_total_tokens": round(result.get("avg_total_tokens", 0), 2),
                    "avg_latency_ms": round(result.get("avg_latency_ms", 0), 2),
                    "runs": runs
                }
            }
        except Exception as e:
            score = 0
            detail = {
                "test": "吞吐量 (TPS)",
                "score": 0,
                "max_score": 35,
                "error": str(e)
            }

        return CategoryScore(
            category="吞吐量",
            score=score,
            max_score=35,
            details=[detail],
            weight=0.35
        )

    async def _evaluate_concurrent(self, model: str, benchmark_config=None) -> CategoryScore:
        """评估并发处理能力"""
        config = benchmark_config or {}
        concurrency = config.get("concurrent_requests", 5)

        prompt = "请简要总结量子计算的核心原理，100字以内。"
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            result = await self.client.measure_concurrent_throughput(
                messages=messages,
                model=model,
                concurrency=concurrency,
                max_tokens=256
            )

            # 评分: 成功率 + 整体吞吐
            success_rate = result["successful_requests"] / max(result["concurrency"], 1)
            overall_tps = result["overall_tps"]

            # 成功率评分 (0-15)
            if success_rate >= 1.0:
                success_score = 15
            elif success_rate >= 0.8:
                success_score = 12
            elif success_rate >= 0.6:
                success_score = 8
            else:
                success_score = 3

            # 并发吞吐评分 (0-10)
            if overall_tps >= 30:
                tps_score = 10
            elif overall_tps >= 15:
                tps_score = 7
            elif overall_tps >= 5:
                tps_score = 4
            else:
                tps_score = 1

            score = success_score + tps_score

            detail = {
                "test": "并发处理",
                "score": score,
                "max_score": 25,
                "metrics": {
                    "concurrency": result["concurrency"],
                    "successful_requests": result["successful_requests"],
                    "failed_requests": result["failed_requests"],
                    "success_rate": round(success_rate, 2),
                    "total_time_ms": round(result["total_time_ms"], 2),
                    "requests_per_second": round(result["requests_per_second"], 2),
                    "overall_tps": round(overall_tps, 2),
                    "avg_latency_ms": round(result["avg_latency_ms"], 2)
                }
            }
        except Exception as e:
            score = 0
            detail = {
                "test": "并发处理",
                "score": 0,
                "max_score": 25,
                "error": str(e)
            }

        return CategoryScore(
            category="并发处理",
            score=score,
            max_score=25,
            details=[detail],
            weight=0.25
        )
