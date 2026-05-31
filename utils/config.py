"""
配置管理模块
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class APIConfig:
    base_url: str = "http://localhost:10240/v1"
    api_key: str = "lm-studio"
    timeout: int = 600
    sock_read_timeout: int = 120
    max_retries: int = 3


@dataclass
class EvaluationConfig:
    samples_per_category: int = 3
    temperature: float = 0.0
    max_tokens: int = 4096
    concurrency: int = 4


@dataclass
class BenchmarkConfig:
    ttft_prompt: str = "请解释什么是机器学习。"
    throughput_prompt: str = "请写一篇关于人工智能发展历史的详细文章，至少800字。"
    throughput_runs: int = 3
    concurrent_requests: int = 4


@dataclass
class ReportConfig:
    output_dir: str = "reports"
    results_dir: str = "results"
    template: str = "report_template.html"


@dataclass
class WeightConfig:
    coding: float = 0.25
    agent: float = 0.25
    reasoning: float = 0.20
    performance: float = 0.12
    rag: float = 0.18


@dataclass
class HardwareMLXConfig:
    max_concurrency: int = 4
    max_model_size_gb: int = 40
    gpu_cores: int = 40


@dataclass
class HardwareConfig:
    platform: str = "mac_studio_m4_max"
    memory_gb: int = 128
    mlx: HardwareMLXConfig = field(default_factory=HardwareMLXConfig)


@dataclass
class OpenClawConfig:
    prompt_style: str = "code_first"
    suppress_reasoning: bool = True
    max_tokens_code: int = 4096
    max_tokens_agent: int = 2048


@dataclass
class HermesConfig:
    prompt_style: str = "reasoning_allowed"
    suppress_reasoning: bool = False
    max_tokens_code: int = 4096
    max_tokens_agent: int = 4096


@dataclass
class ApplicationConfig:
    openclaw: OpenClawConfig = field(default_factory=OpenClawConfig)
    hermes: HermesConfig = field(default_factory=HermesConfig)


@dataclass
class CategoryWeightsConfig:
    coding: dict = field(default_factory=dict)
    agent: dict = field(default_factory=dict)
    reasoning: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    rag: dict = field(default_factory=dict)


@dataclass
class ProfileConfig:
    description: str = ""
    prompt_style: str = "code_first"
    suppress_reasoning: bool = False
    max_tokens_code: int = 4096
    max_tokens_agent: int = 4096
    weights: WeightConfig = field(default_factory=WeightConfig)


@dataclass
class EvalModeConfig:
    description: str = ""
    samples_per_category: int = 3
    dimensions: list = field(default_factory=list)
    temperature: float = 0.0


@dataclass
class Config:
    api: APIConfig = field(default_factory=APIConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    weights: WeightConfig = field(default_factory=WeightConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    application: ApplicationConfig = field(default_factory=ApplicationConfig)
    category_weights: CategoryWeightsConfig = field(default_factory=CategoryWeightsConfig)
    profiles: dict = field(default_factory=dict)
    eval_modes: dict = field(default_factory=dict)


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

        # 解析硬件配置
        if "hardware" in data:
            hw = data["hardware"]
            for k, v in hw.items():
                if k == "mlx" and isinstance(v, dict):
                    for mk, mv in v.items():
                        if hasattr(config.hardware.mlx, mk):
                            setattr(config.hardware.mlx, mk, mv)
                elif hasattr(config.hardware, k):
                    setattr(config.hardware, k, v)

        # 解析应用场景配置
        if "application" in data:
            app = data["application"]
            for app_key in ["openclaw", "hermes"]:
                if app_key in app and isinstance(app[app_key], dict):
                    target = getattr(config.application, app_key)
                    for k, v in app[app_key].items():
                        if hasattr(target, k):
                            setattr(target, k, v)

        # 解析子类别权重配置
        if "category_weights" in data:
            cw = data["category_weights"]
            for dim in ["coding", "agent", "reasoning", "performance"]:
                if dim in cw and isinstance(cw[dim], dict):
                    setattr(config.category_weights, dim, cw[dim])

        # 解析 Profile 配置
        if "profiles" in data:
            prof_data = data["profiles"]
            for name, prof in prof_data.items():
                if isinstance(prof, dict):
                    prof_config = ProfileConfig(
                        description=prof.get("description", ""),
                        prompt_style=prof.get("prompt_style", "code_first"),
                        suppress_reasoning=prof.get("suppress_reasoning", False),
                        max_tokens_code=prof.get("max_tokens_code", 4096),
                        max_tokens_agent=prof.get("max_tokens_agent", 4096),
                    )
                    if "weights" in prof and isinstance(prof["weights"], dict):
                        w = prof["weights"]
                        prof_config.weights = WeightConfig(
                            coding=w.get("coding", 0.30),
                            agent=w.get("agent", 0.30),
                            reasoning=w.get("reasoning", 0.25),
                            performance=w.get("performance", 0.15),
                        )
                    config.profiles[name] = prof_config

        # 解析评估模式配置
        if "eval_modes" in data:
            mode_data = data["eval_modes"]
            for name, mode in mode_data.items():
                if isinstance(mode, dict):
                    config.eval_modes[name] = EvalModeConfig(
                        description=mode.get("description", ""),
                        samples_per_category=mode.get("samples_per_category", 3),
                        dimensions=mode.get("dimensions", ["coding", "agent", "reasoning", "performance"]),
                        temperature=mode.get("temperature", 0.0),
                    )

    return config
