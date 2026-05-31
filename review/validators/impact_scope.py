from typing import List

from review.models import Finding, ReviewContext, ImpactEntry, ImpactMatrix
from review.validators import IReviewDimensionValidator


PREDEFINED_IMPACTS = [
    ImpactEntry(
        change_file="utils/score_engine.py",
        affected_module="run_eval.py, run_full_eval.py等所有评估脚本",
        impact_level="高",
        impact_description="聚合公式变更影响所有维度得分计算结果, 历史结果不可直接对比",
    ),
    ImpactEntry(
        change_file="utils/score_engine.py",
        affected_module="utils/report_generator.py",
        impact_level="中",
        impact_description="报告中展示的分数值因公式变更而改变",
    ),
    ImpactEntry(
        change_file="evaluators/reasoning.py",
        affected_module="所有执行Reasoning评估的脚本",
        impact_level="中",
        impact_description="评分逻辑变更可能影响数学能力评分结果(仅安全替换, 功能等价)",
    ),
    ImpactEntry(
        change_file="evaluators/coding.py",
        affected_module="所有执行Coding评估的脚本",
        impact_level="低",
        impact_description="超时延长仅影响执行时间上限, 不影响评分逻辑",
    ),
    ImpactEntry(
        change_file="evaluators/performance.py",
        affected_module="run_eval.py, run_full_eval.py等",
        impact_level="中",
        impact_description="接口变更需调用方适配temperature/max_tokens参数",
    ),
    ImpactEntry(
        change_file="evaluators/agent.py",
        affected_module="所有执行Agent评估的脚本",
        impact_level="低",
        impact_description="浏览器自动化默认关闭, 不影响核心评估逻辑",
    ),
    ImpactEntry(
        change_file="config.yaml",
        affected_module="utils/config.py的load_config()",
        impact_level="低",
        impact_description="新增配置段, 既有字段不变, 向后兼容",
    ),
    ImpactEntry(
        change_file="utils/config.py",
        affected_module="所有读取配置的模块",
        impact_level="低",
        impact_description="新增字段有default_factory默认值, 缺失不报错",
    ),
]


class ImpactScopeAssessor(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D5:影响范围评估"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        matrix = self._build_impact_matrix()
        context.impact_matrix = matrix

        high_impacts = matrix.get_high_impact_count()
        if high_impacts > 0:
            findings.append(Finding(
                id="", severity="观察", dimension="D5", related_task="T-01",
                related_acceptance="T-01",
                evidence=f"影响矩阵: {high_impacts}个高影响条目",
                description=f"影响范围评估: score_engine.py归一化公式变更为高影响({high_impacts}项), 所有评估脚本和报告生成受影响",
            ))
        else:
            findings.append(Finding(
                id="", severity="观察", dimension="D5", related_task="T-01",
                related_acceptance="T-01",
                evidence="影响矩阵",
                description="影响范围评估: 无高影响变更",
            ))

        findings.extend(self._assess_config_compatibility(context))
        findings.extend(self._assess_score_engine_impact(context))

        return findings

    def _build_impact_matrix(self) -> ImpactMatrix:
        return ImpactMatrix(entries=PREDEFINED_IMPACTS)

    def _assess_config_compatibility(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        py_content = ctx.change_files.get("utils/config.py", "")
        has_default = "default_factory" in py_content or "getattr" in py_content

        if has_default:
            findings.append(Finding(
                id="", severity="观察", dimension="D5", related_task="T-07",
                related_acceptance="T-07",
                evidence="utils/config.py",
                description="配置兼容性: 新增配置段使用default_factory/getattr, 旧版配置缺失新字段时不报错",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D5", related_task="T-07",
                related_acceptance="T-07",
                evidence="utils/config.py",
                description="配置兼容性风险: 新增配置段可能缺少默认值处理",
                suggestion="为新增字段添加default_factory或getattr默认值",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _assess_score_engine_impact(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D5", related_task="T-01",
            related_acceptance="T-01",
            evidence="utils/score_engine.py",
            description="score_engine.py专项影响: 归一化公式变更导致历史评估结果不可直接对比, 建议新结果标注v3.0",
        ))
        return findings
