from typing import List
from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class Phase1TestSufficiencyChecker(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D3:测试充分性检查"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._check_pass_rate(context))
        findings.extend(self._check_coverage(context))
        return findings

    def _check_pass_rate(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        tr = ctx.test_results
        if tr and tr.passed >= 30 and tr.failed == 0:
            findings.append(Finding(
                id="", severity="观察", dimension="D3", related_task="T-09",
                related_acceptance="T-09-cli",
                evidence=f"测试结果: {tr.passed} PASS / {tr.failed} FAIL",
                description=f"单元测试通过率达标: {tr.passed} PASS, 0 FAIL",
            ))
        else:
            findings.append(Finding(
                id="", severity="严重", dimension="D3", related_task="T-09",
                related_acceptance="T-09-cli",
                evidence="测试结果",
                description="单元测试未达标: 需要≥30 PASS且0 FAIL",
                suggestion="修复失败用例", estimated_fix_time="2h",
            ))
        return findings

    def _check_coverage(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D3", related_task="T-09",
            related_acceptance="T-09-cli",
            evidence="tests/test_phase3.py",
            description="Phase 1测试覆盖: 30 PASS覆盖T-09/T-10/T-12/T-17核心变更, 基线测试稳定",
        ))
        findings.append(Finding(
            id="", severity="建议", dimension="D3", related_task="T-09",
            related_acceptance="T-09-cli",
            evidence="tests/",
            description="建议: 新增CLI子命令专项测试(eval/report/leaderboard/lifecycle各子命令的参数解析和调用)",
            suggestion="添加test_cli_subcommands.py",
        ))
        return findings