"""
StatisticsCalculator — 统计显著性支持 (v3.0)
均值/标准差/置信区间/Bootstrap 检验
"""

import numpy as np
from dataclasses import dataclass
from typing import List


@dataclass
class StatResult:
    mean: float
    std: float
    ci_95_lower: float
    ci_95_upper: float
    n_samples: int
    raw_scores: List[float]

    def __str__(self):
        return f"{self.mean:.1f} ± {self.std:.1f} [95% CI: {self.ci_95_lower:.1f}-{self.ci_95_upper:.1f}] (n={self.n_samples})"


class StatisticsCalculator:
    @staticmethod
    def compute(scores: List[float]) -> StatResult:
        if not scores:
            return StatResult(mean=0, std=0, ci_95_lower=0, ci_95_upper=0,
                              n_samples=0, raw_scores=[])
        arr = np.array(scores)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        se = std_val / np.sqrt(len(arr)) if len(arr) > 1 else 0
        ci = 1.96 * se
        return StatResult(
            mean=mean_val,
            std=std_val,
            ci_95_lower=round(mean_val - ci, 2),
            ci_95_upper=round(mean_val + ci, 2),
            n_samples=len(arr),
            raw_scores=scores
        )

    @staticmethod
    def bootstrap_compare(scores_a, scores_b, n_iterations=10000):
        """Bootstrap 检验两组分数是否存在显著差异"""
        a, b = np.array(scores_a), np.array(scores_b)
        observed_diff = float(np.mean(a) - np.mean(b))
        pooled = np.concatenate([a - np.mean(a), b - np.mean(b)])
        diffs = []
        rng = np.random.default_rng(42)
        for _ in range(n_iterations):
            rng.shuffle(pooled)
            diff = float(np.mean(pooled[:len(a)]) - np.mean(pooled[len(a):]))
            diffs.append(diff)
        diffs = np.array(diffs)
        p_value = float(np.mean(np.abs(diffs) >= np.abs(observed_diff)))
        return {
            "observed_difference": observed_diff,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "ci_95": (float(np.percentile(diffs, 2.5)),
                      float(np.percentile(diffs, 97.5)))
        }
