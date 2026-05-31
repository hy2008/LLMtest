"""
评分引擎模块
负责评分计算、结果聚合和排行榜生成
"""

import json
import os
import re
import tempfile
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class CategoryScore:
    """单个类别的评分"""
    category: str
    score: float  # 0-100
    max_score: float
    details: List[Dict[str, Any]] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class DimensionScore:
    """评估维度的评分"""
    dimension: str  # coding, agent, reasoning, performance
    score: float  # 加权平均分 0-100
    categories: List[CategoryScore] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class ModelEvalResult:
    """单个模型的评估结果"""
    model_name: str
    model_id: str
    eval_time: str
    dimensions: Dict[str, DimensionScore] = field(default_factory=dict)
    overall_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_overall(self, weights: Dict[str, float]):
        """计算加权总分"""
        total_weight = 0
        weighted_sum = 0
        for dim_name, weight in weights.items():
            if dim_name in self.dimensions:
                weighted_sum += self.dimensions[dim_name].score * weight
                total_weight += weight
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "eval_time": self.eval_time,
            "overall_score": round(self.overall_score, 2),
            "dimensions": {}
        }
        for dim_name, dim_score in self.dimensions.items():
            result["dimensions"][dim_name] = {
                "score": round(dim_score.score, 2),
                "weight": dim_score.weight,
                "categories": {}
            }
            for cat in dim_score.categories:
                result["dimensions"][dim_name]["categories"][cat.category] = {
                    "score": round(cat.score, 2),
                    "max_score": cat.max_score,
                    "weight": cat.weight,
                    "details": cat.details
                }
        result["metadata"] = self.metadata
        return result


class ScoreEngine:
    """评分引擎"""

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or {
            "coding": 0.30,
            "agent": 0.30,
            "reasoning": 0.25,
            "performance": 0.15
        }
        self.results: List[ModelEvalResult] = []

    def create_result(self, model_name: str, model_id: str) -> ModelEvalResult:
        """创建新的评估结果"""
        result = ModelEvalResult(
            model_name=model_name,
            model_id=model_id,
            eval_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        return result

    def add_dimension_score(self, result: ModelEvalResult,
                            dimension: str, categories: List[CategoryScore]):
        """添加维度评分 — 归一化聚合: (score/max_score×100)×weight"""
        dim_weight = self.weights.get(dimension, 1.0)
        # 归一化: 每子类别先转为百分比, 再加权平均
        total_weight = sum(c.weight for c in categories)
        weighted_sum = sum(
            (c.score / c.max_score * 100 if c.max_score > 0 else 0) * c.weight
            for c in categories
        )
        dim_score = weighted_sum / total_weight if total_weight > 0 else 0

        dim = DimensionScore(
            dimension=dimension,
            score=dim_score,
            categories=categories,
            weight=dim_weight
        )
        result.dimensions[dimension] = dim

    def finalize(self, result: ModelEvalResult) -> ModelEvalResult:
        """计算最终分数"""
        result.calculate_overall(self.weights)
        self.results.append(result)
        return result

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """获取排行榜"""
        sorted_results = sorted(self.results, key=lambda r: r.overall_score, reverse=True)
        leaderboard = []
        for rank, result in enumerate(sorted_results, 1):
            entry = {
                "rank": rank,
                "model_name": result.model_name,
                "model_id": result.model_id,
                "overall_score": round(result.overall_score, 2),
                "eval_time": result.eval_time,
                "dimensions": {}
            }
            for dim_name, dim_score in result.dimensions.items():
                entry["dimensions"][dim_name] = round(dim_score.score, 2)
            leaderboard.append(entry)
        return leaderboard

    def save_result(self, result: ModelEvalResult, results_dir: str = "results"):
        """保存评估结果到 JSON 文件"""
        os.makedirs(results_dir, exist_ok=True)
        safe_name = result.model_id.replace("/", "_").replace(":", "_")
        filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(results_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    def load_results(self, results_dir: str = "results") -> List[ModelEvalResult]:
        """从目录加载历史评估结果"""
        if not os.path.exists(results_dir):
            return []

        loaded = []
        for filename in os.listdir(results_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(results_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 跳过列表格式的汇总文件 (eval_summary_*.json)
                if isinstance(data, list):
                    continue
                # 重建 ModelEvalResult
                result = ModelEvalResult(
                    model_name=data.get("model_name", ""),
                    model_id=data.get("model_id", ""),
                    eval_time=data.get("eval_time", ""),
                    overall_score=data.get("overall_score", 0),
                    metadata=data.get("metadata", {})
                )
                for dim_name, dim_data in data.get("dimensions", {}).items():
                    categories = []
                    cats = dim_data.get("categories", {})
                    if isinstance(cats, dict):
                        for cat_name, cat_data in cats.items():
                            categories.append(CategoryScore(
                                category=cat_name,
                                score=cat_data.get("score", 0),
                                max_score=cat_data.get("max_score", 100),
                                details=cat_data.get("details", []),
                                weight=cat_data.get("weight", 1.0)
                            ))
                    elif isinstance(cats, list):
                        for cat_data in cats:
                            categories.append(CategoryScore(
                                category=cat_data.get("category", cat_data.get("name", "")),
                                score=cat_data.get("score", 0),
                                max_score=cat_data.get("max_score", 100),
                                details=cat_data.get("details", []),
                                weight=cat_data.get("weight", 1.0)
                            ))
                    result.dimensions[dim_name] = DimensionScore(
                        dimension=dim_name,
                        score=dim_data.get("score", 0),
                        categories=categories,
                        weight=dim_data.get("weight", 1.0)
                    )
                loaded.append(result)
            except (json.JSONDecodeError, KeyError):
                continue

        self.results.extend(loaded)
        return loaded

    @staticmethod
    def reverse_validation(
        response: str,
        validation_type: str = "code",
        test_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """反向验证：检验模型能否识别错误/拒绝无效输入。

        Args:
            response: 模型的原始响应文本
            validation_type: "code"（代码执行验证）或 "logic"（反例检测）
            test_cases: 可选的自定义测试用例列表

        Returns:
            dict: {
                "passed": bool,
                "score": float (0-100),
                "details": list of validation detail dicts
            }
        """
        if validation_type == "code":
            return ScoreEngine._reverse_validate_code(response, test_cases)
        elif validation_type == "logic":
            return ScoreEngine._reverse_validate_logic(response, test_cases)
        else:
            return {"passed": False, "score": 0, "details": [{"error": f"未知验证类型: {validation_type}"}]}

    @staticmethod
    def _reverse_validate_code(response: str, test_cases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """代码反向验证：提取模型建议的修复代码并实际执行，验证修复是否真正有效。"""
        code_blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', response, re.DOTALL)
        if not code_blocks:
            return {"passed": True, "score": 50, "details": [{"note": "未提取到可执行代码块，跳过执行验证"}]}

        details = []
        passed_count = 0
        total = len(code_blocks)

        for i, code in enumerate(code_blocks):
            code = code.strip()
            if not code or len(code) < 10:
                details.append({"block": i + 1, "status": "skipped", "reason": "代码过短"})
                passed_count += 1
                continue

            dangerous_patterns = [r'\bos\.system\b', r'\bsubprocess\.call\b', r'\brm\s+-rf',
                                  r'\bshutil\.rmtree\b', r'\beval\s*\(', r'\bexec\s*\(',
                                  r'\bopen\s*\(.+["\']w', r'\bsocket\b']
            is_dangerous = any(re.search(p, code) for p in dangerous_patterns)
            if is_dangerous:
                details.append({"block": i + 1, "status": "rejected", "reason": "检测到危险操作模式"})
                continue

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=True, encoding='utf-8') as f:
                f.write(code)
                f.flush()
                try:
                    result = subprocess.run(
                        ['python3', f.name],
                        capture_output=True, text=True, timeout=5,
                        env={**os.environ, 'PYTHONPATH': os.getcwd()}
                    )
                    if result.returncode == 0:
                        details.append({"block": i + 1, "status": "passed", "returncode": 0})
                        passed_count += 1
                    else:
                        details.append({
                            "block": i + 1, "status": "failed",
                            "returncode": result.returncode,
                            "stderr": result.stderr[:200]
                        })
                except subprocess.TimeoutExpired:
                    details.append({"block": i + 1, "status": "timeout"})
                except Exception as e:
                    details.append({"block": i + 1, "status": "error", "message": str(e)[:100]})

        score = (passed_count / total * 100) if total > 0 else 0
        return {"passed": passed_count == total, "score": score, "details": details}

    @staticmethod
    def _reverse_validate_logic(response: str, test_cases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """逻辑反向验证：检查推理结论是否排除了明显反例，验证推理链完备性。"""
        if test_cases is None:
            test_cases = [
                {"claim_pattern": r"所有\s*(\S+)\s*都", "counter_needed": True,
                 "description": "全称命题需考虑反例"},
                {"claim_pattern": r"一定|必然|肯定", "counter_needed": True,
                 "description": "绝对化表述需考虑例外"},
                {"claim_pattern": r"只要\s*.+\s*就", "counter_needed": True,
                 "description": "充分条件需验证必要性"},
            ]

        details = []
        passed_count = 0
        total = len(test_cases)

        for tc in test_cases:
            pattern = tc.get("claim_pattern", "")
            counter_needed = tc.get("counter_needed", False)
            desc = tc.get("description", "")

            has_absolute_claim = bool(re.search(pattern, response))
            if not has_absolute_claim:
                details.append({"test": desc, "status": "passed", "reason": "未发现绝对化表述"})
                passed_count += 1
                continue

            counter_indicators = ["反例", "例外", "不一定", "可能不", "前提条件",
                                  "counter.?example", "exception", "caveat",
                                  "但在", "然而", "不过", "需要注意的是"]
            has_counter = any(re.search(ind, response, re.IGNORECASE) for ind in counter_indicators)

            if has_counter:
                details.append({"test": desc, "status": "passed", "reason": "发现反例/限制条件讨论"})
                passed_count += 1
            else:
                details.append({"test": desc, "status": "failed", "reason": "绝对化表述缺少反例讨论"})

        score = (passed_count / total * 100) if total > 0 else 0
        return {"passed": passed_count == total, "score": score, "details": details}

    @staticmethod
    def compute_stability(scores_temp0: Dict[str, float],
                          scores_temp07: Dict[str, float],
                          max_scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """计算多温度评估的稳定性指标。

        Args:
            scores_temp0: temperature=0 时各子类别得分 {category: score}
            scores_temp07: temperature=0.7 时各子类别得分 {category: score}
            max_scores: 各子类别满分 {category: max_score}，默认100

        Returns:
            dict: {
                "categories": {category: {score_temp0, score_temp0.7, stability_index, variance}},
                "overall_stability": float,
                "stable_categories": int,
                "unstable_categories": int
            }
        """
        if max_scores is None:
            max_scores = {k: 100 for k in scores_temp0}

        categories_result = {}
        stability_values = []

        all_categories = set(scores_temp0.keys()) | set(scores_temp07.keys())
        for cat in all_categories:
            s0 = scores_temp0.get(cat, 0)
            s07 = scores_temp07.get(cat, 0)
            mx = max_scores.get(cat, 100)

            variance = abs(s0 - s07)
            stability_index = 1 - (variance / mx) if mx > 0 else 0
            stability_values.append(stability_index)

            categories_result[cat] = {
                "score_temp0": s0,
                "score_temp0.7": s07,
                "stability_index": round(stability_index, 4),
                "variance": round(variance, 2)
            }

        overall = sum(stability_values) / len(stability_values) if stability_values else 0
        stable = sum(1 for v in stability_values if v >= 0.9)
        unstable = sum(1 for v in stability_values if v < 0.7)

        return {
            "categories": categories_result,
            "overall_stability": round(overall, 4),
            "stable_categories": stable,
            "unstable_categories": unstable
        }
