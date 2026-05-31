import re
from typing import List

from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


VAGUE_PATTERNS = [
    r"基本符合",
    r"大致完成",
    r"看起来没问题",
    r"差不多",
    r"还行",
    r"基本完成",
]

REQUIRED_SECTIONS = [
    "审查背景",
    "审查范围",
    "审查维度",
    "审查发现",
    "审查结论",
    "验收清单",
]


class ReportNormativityChecker(IReviewDimensionValidator):
    def __init__(self, report_content: str = ""):
        self.report_content = report_content

    def get_name(self) -> str:
        return "D6:报告规范性检查"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        if not self.report_content:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="报告生成阶段",
                description="D6将在报告生成后执行检查",
            ))
            return findings

        findings.extend(self._check_report_structure())
        findings.extend(self._check_finding_classification(context))
        findings.extend(self._check_conclusion_rule(context))
        findings.extend(self._check_evidence_traceability(context))
        findings.extend(self._check_no_vague_expressions())
        return findings

    def _check_report_structure(self) -> List[Finding]:
        findings = []
        missing = [s for s in REQUIRED_SECTIONS if s not in self.report_content]
        if not missing:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="审查报告",
                description="报告结构完整: 包含全部6个必需章节",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="审查报告",
                description=f"报告结构不完整: 缺少章节{missing}",
                suggestion=f"补充{missing}章节",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_finding_classification(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        valid_severities = {"严重", "一般", "观察", "建议"}
        invalid = [f for f in ctx.findings if f.severity not in valid_severities]
        if not invalid:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="findings列表",
                description="审查发现分类规范: 所有发现均标注了严重程度分类(严重/一般/观察/建议)",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="findings列表",
                description=f"审查发现分类不规范: {len(invalid)}项缺少有效严重程度分类",
                suggestion="为所有发现标注严重程度",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_conclusion_rule(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        from review.models import ReviewConclusion
        conclusion = ReviewConclusion.from_findings(ctx.findings, ctx.acceptance_items)

        severe_count = sum(1 for f in ctx.findings if f.severity == "严重")
        general_count = sum(1 for f in ctx.findings if f.severity == "一般")

        rule_ok = True
        if severe_count >= 1 and conclusion.verdict != "不通过":
            rule_ok = False
        elif severe_count == 0 and general_count >= 1 and conclusion.verdict != "有条件通过":
            rule_ok = False
        elif severe_count == 0 and general_count == 0 and conclusion.verdict != "通过":
            rule_ok = False

        if rule_ok:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence=f"结论判定: {conclusion.verdict}",
                description=f"审查结论判定合规: verdict={conclusion.verdict}, 严重={severe_count}, 一般={general_count}",
            ))
        return findings

    def _check_evidence_traceability(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        no_evidence = [f for f in ctx.findings if not f.evidence]
        if not no_evidence:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="findings列表",
                description="证据可追溯: 所有发现均附带证据引用",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="findings列表",
                description=f"证据不足: {len(no_evidence)}项发现缺少证据引用",
                suggestion="补充证据引用(文件名:行号或测试用例ID)",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_no_vague_expressions(self) -> List[Finding]:
        findings = []
        found_vague = []
        for pattern in VAGUE_PATTERNS:
            matches = re.findall(pattern, self.report_content)
            if matches:
                found_vague.extend(matches)

        if not found_vague:
            findings.append(Finding(
                id="", severity="观察", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="报告文本扫描",
                description="无模糊表述: 报告中未发现'基本符合''大致完成'等模糊表述",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D6", related_task="T-01",
                related_acceptance="T-01",
                evidence="报告文本扫描",
                description=f"发现模糊表述: {found_vague}",
                suggestion="替换为具体量化描述",
                estimated_fix_time="0.5h",
            ))
        return findings
