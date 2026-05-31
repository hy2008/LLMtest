import pytest
from review.models import (
    TaskDef, Finding, ReviewContext, AcceptanceItem, TestResultSet,
    DeferredItemAssessment, ArchitectureImprovement, SuggestionItem,
    ReviewConclusion,
)
from review.validators.phase1_completeness import Phase1CompletenessValidator
from review.validators.phase1_technical_rationality import Phase1TechnicalRationalityAssessor
from review.validators.deferred_item_assessor import DeferredItemAssessor
from review.validators.suggestion_generator import SuggestionGenerator


def _make_ctx(run_eval="", coding="", agent="", reasoning="", performance="",
              benchmark_loader=""):
    return ReviewContext(
        task_registry={
            "T-09": TaskDef(id="T-09", priority="P0-2", status="已完成", change_file="run_eval.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-10": TaskDef(id="T-10", priority="P0-5", status="已完成", change_file="evaluators/*.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-11": TaskDef(id="T-11", priority="P0-6", status="延后", change_file="",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-12": TaskDef(id="T-12", priority="P0-3", status="已完成", change_file="run_eval.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-17": TaskDef(id="T-17", priority="P1-1", status="已完成", change_file="utils/benchmark_loader.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
        },
        change_files={
            "run_eval.py": run_eval,
            "evaluators/coding.py": coding,
            "evaluators/agent.py": agent,
            "evaluators/reasoning.py": reasoning,
            "evaluators/performance.py": performance,
            "utils/benchmark_loader.py": benchmark_loader,
        },
        test_results=TestResultSet(total=32, passed=30, failed=0, skipped=2),
        acceptance_items={
            "T-09-cli": AcceptanceItem(id="T-09-cli", description="", verification_method="", expected_result=""),
        },
        deferred_assessments=[
            DeferredItemAssessment(task_id="T-11", reason="废弃脚本可能仍有外部引用",
                                   merge_plan="验证后清理", is_reasonable=True, risk_level="低"),
        ],
    )


class TestPhase1CompletenessValidator:
    def test_t09_pass(self):
        code = 'subparsers = parser.add_subparsers(dest="command")\neval_p = subparsers.add_parser("eval")\nreport_p = subparsers.add_parser("report")\nlb_p = subparsers.add_parser("leaderboard")\nlc_p = subparsers.add_parser("lifecycle")\neval_p.add_argument("--profile", choices=["openclaw", "hermes", "default"])\n向后兼容\n交互式\n'
        ctx = _make_ctx(run_eval=code)
        v = Phase1CompletenessValidator()
        findings = v._check_t09(ctx)
        assert any("子命令完整" in f.description for f in findings)

    def test_t09_fail(self):
        ctx = _make_ctx(run_eval="print('hello')")
        v = Phase1CompletenessValidator()
        findings = v._check_t09(ctx)
        assert any(f.severity == "严重" for f in findings)

    def test_t10_pass(self):
        code = "def __init__(self, client, config=None, category_weights=None):\n    self.category_weights = category_weights or {}\n"
        ctx = _make_ctx(coding=code, agent=code, reasoning=code, performance=code,
                        run_eval="category_weights\nc_weights\n")
        v = Phase1CompletenessValidator()
        findings = v._check_t10(ctx)
        assert any("权重适配完整" in f.description for f in findings)

    def test_t12_pass(self):
        code = 'subparsers.add_parser("report")\nreport_p.add_argument("--format", choices=["html", "json", "txt"])\n'
        ctx = _make_ctx(run_eval=code)
        v = Phase1CompletenessValidator()
        findings = v._check_t12(ctx)
        assert any("多格式完整" in f.description for f in findings)

    def test_t17_pass(self):
        code = "class BenchmarkLoader:\n    def load(self):\n    def load_all(self):\n    def has_data(self):\n    _BUILTIN_FALLBACK\n"
        ctx = _make_ctx(benchmark_loader=code)
        v = Phase1CompletenessValidator()
        findings = v._check_t17(ctx)
        assert any("BenchmarkLoader完整" in f.description for f in findings)

    def test_t17_fail(self):
        ctx = _make_ctx(benchmark_loader="")
        v = Phase1CompletenessValidator()
        findings = v._check_t17(ctx)
        assert any(f.severity == "严重" for f in findings)


class TestDeferredItemAssessor:
    def test_reasonable(self):
        ctx = _make_ctx()
        v = DeferredItemAssessor()
        findings = v.execute(ctx)
        assert any("延后合理" in f.description for f in findings)

    def test_unreasonable(self):
        ctx = _make_ctx()
        ctx.deferred_assessments = [
            DeferredItemAssessment(task_id="T-XX", reason="无充分理由",
                                   merge_plan="无", is_reasonable=False, risk_level="高"),
        ]
        v = DeferredItemAssessor()
        findings = v.execute(ctx)
        assert any(f.severity == "一般" for f in findings)


class TestSuggestionGenerator:
    def test_generates_suggestions(self):
        ctx = _make_ctx()
        v = SuggestionGenerator()
        findings = v.execute(ctx)
        assert len(ctx.suggestions) > 0
        assert any("建议意见" in f.description for f in findings)

    def test_suggestions_sorted(self):
        ctx = _make_ctx()
        v = SuggestionGenerator()
        v.execute(ctx)
        priorities = [s.priority for s in ctx.suggestions]
        assert priorities == sorted(priorities)


class TestNewDataModels:
    def test_deferred_item(self):
        da = DeferredItemAssessment(task_id="T-11", reason="test", merge_plan="plan")
        assert da.is_reasonable is True
        assert da.risk_level == "低"

    def test_architecture_improvement(self):
        ai = ArchitectureImprovement(metric="CLI", before="11", after="1", improvement="统一")
        assert ai.metric == "CLI"

    def test_suggestion_item(self):
        si = SuggestionItem(priority=1, category="架构", target="T-11",
                            description="清理", action="删除脚本")
        assert si.estimated_effort == ""