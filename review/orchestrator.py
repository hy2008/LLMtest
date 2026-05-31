import logging
from typing import List, Tuple

from review.models import Finding, ReviewContext
from review.context_builder import ReviewContextBuilder
from review.validators.completeness import CompletenessValidator
from review.validators.technical_rationality import TechnicalRationalityAssessor
from review.validators.test_sufficiency import TestSufficiencyChecker
from review.validators.coding_standard import CodingStandardConformer
from review.validators.impact_scope import ImpactScopeAssessor
from review.validators.report_normativity import ReportNormativityChecker
from review.report.generator import ReviewReportGenerator


class ReviewOrchestrator:
    def __init__(self):
        self.d1 = CompletenessValidator()
        self.d2 = TechnicalRationalityAssessor()
        self.d3 = TestSufficiencyChecker()
        self.d4 = CodingStandardConformer()
        self.d5 = ImpactScopeAssessor()
        self.d6 = ReportNormativityChecker()
        self.generator = ReviewReportGenerator()
        self.builder = ReviewContextBuilder()

    def _execute_dimension(self, validator, context: ReviewContext) -> List[Finding]:
        try:
            return validator.execute(context)
        except Exception as e:
            logging.error(f"{validator.get_name()}执行异常: {e}")
            return [Finding(
                id="", severity="严重", dimension="D0",
                related_task="T-01", related_acceptance="T-01",
                evidence=validator.get_name(),
                description=f"{validator.get_name()}执行异常: {e}",
                suggestion="检查执行器实现和输入数据",
                estimated_fix_time="2h",
            )]

    def run(self) -> Tuple[str, ReviewContext]:
        context = self.builder.build()

        dimensions = [self.d1, self.d2, self.d3, self.d4, self.d5]
        for dim in dimensions:
            findings = self._execute_dimension(dim, context)
            context.findings.extend(findings)

        report = self.generator.generate(context)

        self.d6.report_content = report
        d6_findings = self._execute_dimension(self.d6, context)
        context.findings.extend(d6_findings)

        return report, context
