from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskDef:
    id: str
    priority: str
    status: str
    change_file: str
    problem_before: str
    fix_after: str
    verification_method: str
    expected_result: str


@dataclass
class TestCaseDetail:
    id: str
    name: str
    result: str
    skip_reason: Optional[str] = None
    related_task: Optional[str] = None


@dataclass
class TestResultSet:
    total: int
    passed: int
    failed: int
    skipped: int
    skip_reasons: Dict[str, str] = field(default_factory=dict)
    test_cases: List[TestCaseDetail] = field(default_factory=list)


@dataclass
class AcceptanceItem:
    id: str
    description: str
    verification_method: str
    expected_result: str
    actual_result: str = ""
    conclusion: str = ""


@dataclass
class Finding:
    id: str
    severity: str
    dimension: str
    related_task: str
    related_acceptance: str
    evidence: str
    description: str
    suggestion: Optional[str] = None
    estimated_fix_time: Optional[str] = None


@dataclass
class ImpactEntry:
    change_file: str
    affected_module: str
    impact_level: str
    impact_description: str


@dataclass
class ImpactMatrix:
    entries: List[ImpactEntry] = field(default_factory=list)

    def get_by_file(self, file: str) -> List[ImpactEntry]:
        return [e for e in self.entries if e.change_file == file]

    def get_by_level(self, level: str) -> List[ImpactEntry]:
        return [e for e in self.entries if e.impact_level == level]

    def get_high_impact_count(self) -> int:
        return len(self.get_by_level("高"))


@dataclass
class ReviewConclusion:
    verdict: str
    severe_count: int
    general_count: int
    observation_count: int
    suggestion_count: int
    deferred_count: int
    acceptance_coverage: float
    acceptance_results: Dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_findings(
        findings: List[Finding],
        acceptance_items: Dict[str, AcceptanceItem],
        deferred_count: int = 1,
    ) -> "ReviewConclusion":
        severe = sum(1 for f in findings if f.severity == "严重")
        general = sum(1 for f in findings if f.severity == "一般")
        observation = sum(1 for f in findings if f.severity == "观察")
        suggestion = sum(1 for f in findings if f.severity == "建议")

        if severe >= 1:
            verdict = "不通过"
        elif general >= 1:
            verdict = "有条件通过"
        else:
            verdict = "通过"

        total_acceptance = len(acceptance_items)
        judged_acceptance = sum(
            1
            for item in acceptance_items.values()
            if item.conclusion in ("通过", "不通过", "延后")
        )
        coverage = judged_acceptance / total_acceptance if total_acceptance > 0 else 0

        return ReviewConclusion(
            verdict=verdict,
            severe_count=severe,
            general_count=general,
            observation_count=observation,
            suggestion_count=suggestion,
            deferred_count=deferred_count,
            acceptance_coverage=coverage,
            acceptance_results={k: v.conclusion for k, v in acceptance_items.items()},
        )


@dataclass
class DeferredItemAssessment:
    task_id: str
    reason: str
    merge_plan: str
    is_reasonable: bool = True
    risk_level: str = "低"
    suggestion: str = ""


@dataclass
class ArchitectureImprovement:
    metric: str
    before: str
    after: str
    improvement: str


@dataclass
class SuggestionItem:
    priority: int
    category: str
    target: str
    description: str
    action: str
    estimated_effort: str = ""


@dataclass
class ReviewContext:
    task_registry: Dict[str, TaskDef] = field(default_factory=dict)
    change_files: Dict[str, str] = field(default_factory=dict)
    change_diffs: Dict[str, str] = field(default_factory=dict)
    test_results: Optional[TestResultSet] = None
    findings: List[Finding] = field(default_factory=list)
    acceptance_items: Dict[str, AcceptanceItem] = field(default_factory=dict)
    impact_matrix: Optional[ImpactMatrix] = None
    deferred_assessments: List[DeferredItemAssessment] = field(default_factory=list)
    architecture_improvements: List[ArchitectureImprovement] = field(default_factory=list)
    suggestions: List[SuggestionItem] = field(default_factory=list)
