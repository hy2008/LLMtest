"""
配置管理模块
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class APIConfig:
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    timeout: int = 120
    max_retries: int = 3


@dataclass
class EvaluationConfig:
    samples_per_category: int = 3
    temperature: float = 0.0
    max_tokens: int = 2048
    concurrency: int = 1


@dataclass
class BenchmarkConfig:
    ttft_prompt: str = "请解释什么是机器学习。"
    throughput_prompt: str = "请写一篇关于人工智能发展历史的详细文章，至少800字。"
    throughput_runs: int = 3
    concurrent_requests: int = 5


@dataclass
class ReportConfig:
    output_dir: str = "reports"
    results_dir: str = "results"
    template: str = "report_template.html"


@dataclass
class WeightConfig:
    coding: float = 0.30
    agent: float = 0.30
    reasoning: float = 0.25
    performance: float = 0.15


@dataclass
class Config:
    api: APIConfig = field(default_factory=APIConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)


def load_config(config_path: Optional[str] = None) -> Config:
    """加载配置文件"""
    if config_path is None:
        # 查找默认配置文件
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
            "config.yaml",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                config_path = candidate
                break

    config = Config()

    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 解析 API 配置
        if "api" in data:
            for k, v in data["api"].items():
                if hasattr(config.api, k):
                    setattr(config.api, k, v)

        # 解析评估配置
        if "evaluation" in data:
            for k, v in data["evaluation"].items():
                if hasattr(config.evaluation, k):
                    setattr(config.evaluation, k, v)

        # 解析基准测试配置
        if "benchmark" in data:
            for k, v in data["benchmark"].items():
                if hasattr(config.benchmark, k):
                    setattr(config.benchmark, k, v)

        # 解析报告配置
        if "report" in data:
            for k, v in data["report"].items():
                if hasattr(config.report, k):
                    setattr(config.report, k, v)

        # 解析权重配置
        if "weights" in data:
            for k, v in data["weights"].items():
                if hasattr(config.weights, k):
                    setattr(config.weights, k, v)

    return config
