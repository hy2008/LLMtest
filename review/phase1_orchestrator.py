import logging
from typing import List, Tuple

from review.models import Finding, ReviewContext
from review.phase1_context_builder import Phase1ContextBuilder
from review.validators.phase1_completeness import Phase1CompletenessValidator
from review.validators.phase1_technical_rationality import Phase1TechnicalRationalityAssessor
from review.validators.phase1_test_sufficiency import Phase1TestSufficiencyChecker
from review.validators.phase1_impact_scope import Phase1ImpactScopeAssessor
from review.validators.deferred_item_assessor import DeferredItemAssessor
from review.validators.suggestion_generator import SuggestionGenerator
from review.report.phase1_generator import Phase1ReportGenerator


class Phase1Orchestrator:
    def __init__(self):
        self.d1 = Phase1CompletenessValidator()
        self.d2 = Phase1TechnicalRationalityAssessor()
        self.d3 = Phase1TestSufficiencyChecker()
        self.d5 = Phase1ImpactScopeAssessor()
        self.d7 = DeferredItemAssessor()
        self.d8 = SuggestionGenerator()
        self.generator = Phase1ReportGenerator()
        self.builder = Phase1ContextBuilder()

    def _execute_dimension(self, validator, context: ReviewContext) -> List[Finding]:
        try:
            return validator.execute(context)
        except Exception as e:
            logging.error(f"{validator.get_name()}执行异常: {e}")
            return [Finding(
                id="", severity="严重", dimension="D0",
                related_task="T-09", related_acceptance="T-09-cli",
                evidence=validator.get_name(),
                description=f"{validator.get_name()}执行异常: {e}",
                suggestion="检查执行器实现", estimated_fix_time="2h",
            )]

    def run(self) -> Tuple[str, ReviewContext]:
        context = self.builder.build()

        dimensions = [self.d1, self.d2, self.d3, self.d5, self.d7, self.d8]
        for dim in dimensions:
            findings = self._execute_dimension(dim, context)
            context.findings.extend(findings)

        report = self.generator.generate(context)
        return report, context