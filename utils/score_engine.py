"""
评分引擎模块
负责评分计算、结果聚合和排行榜生成
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
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
        """添加维度评分"""
        dim_weight = self.weights.get(dimension, 1.0)
        # 计算维度加权平均分
        total_weight = sum(c.weight for c in categories)
        weighted_sum = sum(c.score * c.weight for c in categories)
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
                    for cat_name, cat_data in dim_data.get("categories", {}).items():
                        categories.append(CategoryScore(
                            category=cat_name,
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
