from typing import List
from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class DeferredItemAssessor(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D7:延后项合理性评估"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        for da in context.deferred_assessments:
            if da.is_reasonable:
                findings.append(Finding(
                    id="", severity="观察", dimension="D7",
                    related_task=da.task_id, related_acceptance=da.task_id,
                    evidence=f"延后原因: {da.reason}",
                    description=f"{da.task_id}延后合理: {da.reason}, 合并方案: {da.merge_plan}, 风险等级: {da.risk_level}",
                ))
            else:
                findings.append(Finding(
                    id="", severity="一般", dimension="D7",
                    related_task=da.task_id, related_acceptance=da.task_id,
                    evidence=f"延后原因: {da.reason}",
                    description=f"{da.task_id}延后合理性存疑: {da.reason}",
                    suggestion=da.suggestion or "重新评估延后决策",
                    estimated_fix_time="1h",
                ))

        high_risk = [da for da in context.deferred_assessments if da.risk_level == "高"]
        if high_risk:
            findings.append(Finding(
                id="", severity="一般", dimension="D7", related_task="T-14",
                related_acceptance="T-14",
                evidence="延后项风险评估",
                description=f"高风险延后项: {[da.task_id for da in high_risk]}, 建议优先排期",
                suggestion="将高风险延后项纳入下一迭代优先级",
                estimated_fix_time="—",
            ))

        return findings