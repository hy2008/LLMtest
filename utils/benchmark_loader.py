"""
BenchmarkLoader — 从 JSON 文件加载测试用例 (v3.0 数据驱动)
支持基准目录: benchmarks/{dimension}/{category}.json
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 内置题库回退 (当 benchmarks/ 目录不存在时使用)
_BUILTIN_FALLBACK = {
    "coding": {
        "base": ["code_writing", "code_completion", "debugging", "multilingual"],
        "practical": ["code_review", "test_writing", "api_development"]
    },
    "agent": {
        "base": ["function_calling", "tool_selection", "multi_step_reasoning", "instruction_following"],
        "practical": ["browser_automation", "filesystem_operations", "shell_execution",
                      "tool_orchestration", "multi_turn_conversation", "structured_output",
                      "long_task_planning"]
    },
    "reasoning": {
        "base": ["logic", "knowledge_understanding", "math"],
        "practical": ["chain_of_thought", "business_reasoning", "code_reasoning",
                      "self_correction", "multi_step_decision", "causal_reasoning"]
    }
}


class BenchmarkLoader:
    """从 benchmarks/ 目录加载测试用例 JSON 文件"""

    def __init__(self, base_dir: str = "benchmarks"):
        self.base_dir = Path(base_dir)

    def load(self, dimension: str, category: str) -> Optional[Dict[str, Any]]:
        """加载单个子类别的测试用例"""
        filepath = self.base_dir / dimension / f"{category}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all(self, dimension: str, practical: bool = True) -> Dict[str, Any]:
        """加载指定维度的所有测试用例"""
        dir_path = self.base_dir / dimension
        if not dir_path.exists():
            return {}
        benchmarks = {}
        base_cats = set(_BUILTIN_FALLBACK.get(dimension, {}).get("base", []))
        for f in sorted(dir_path.glob("*.json")):
            category = f.stem
            if not practical and category not in base_cats:
                continue
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    benchmarks[category] = json.load(fp)
            except (json.JSONDecodeError, IOError):
                continue
        return benchmarks

    def has_data(self) -> bool:
        """检查基准目录是否存在且有数据"""
        return self.base_dir.exists() and any(self.base_dir.rglob("*.json"))
