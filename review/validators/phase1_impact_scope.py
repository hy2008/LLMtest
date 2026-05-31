from typing import List
from review.models import Finding, ReviewContext, ImpactEntry, ImpactMatrix
from review.validators import IReviewDimensionValidator


PHASE1_IMPACTS = [
    ImpactEntry(change_file="run_eval.py", affected_module="所有用户/CI脚本",
                impact_level="高", impact_description="CLI入口变更, 旧脚本调用方式需迁移"),
    ImpactEntry(change_file="run_eval.py", affected_module="run_*.py旧脚本",
                impact_level="中", impact_description="子命令体系替代旧脚本, 但旧脚本仍存在(未删除)"),
    ImpactEntry(change_file="evaluators/coding.py", affected_module="所有调用CodingEvaluator的代码",
                impact_level="中", impact_description="__init__签名变更, 新增category_weights参数"),
    ImpactEntry(change_file="evaluators/agent.py", affected_module="所有调用AgentEvaluator的代码",
                impact_level="中", impact_description="__init__签名变更"),
    ImpactEntry(change_file="evaluators/reasoning.py", affected_module="所有调用ReasoningEvaluator的代码",
                impact_level="中", impact_description="__init__签名变更"),
    ImpactEntry(change_file="evaluators/performance.py", affected_module="所有调用PerformanceEvaluator的代码",
                impact_level="中", impact_description="__init__签名变更"),
    ImpactEntry(change_file="utils/benchmark_loader.py", affected_module="evaluators/*.py",
                impact_level="低", impact_description="新增模块, 评估器可选择性使用"),
]


class Phase1ImpactScopeAssessor(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D5:影响范围评估"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        matrix = ImpactMatrix(entries=PHASE1_IMPACTS)
        context.impact_matrix = matrix

        high = matrix.get_high_impact_count()
        findings.append(Finding(
            id="", severity="观察", dimension="D5", related_task="T-09",
            related_acceptance="T-09-cli",
            evidence=f"影响矩阵: {high}个高影响",
            description=f"影响范围评估: run_eval.py CLI入口变更为高影响({high}项), 所有用户和CI脚本需适配",
        ))
        findings.append(Finding(
            id="", severity="观察", dimension="D5", related_task="T-10",
            related_acceptance="T-10-weights",
            evidence="影响矩阵",
            description="影响范围评估: 4个evaluator签名变更为中影响, 调用方需适配新参数(有默认值, 向后兼容)",
        ))
        return findings