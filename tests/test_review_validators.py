import pytest
from review.models import Finding, ReviewContext, AcceptanceItem, TaskDef, TestResultSet
from review.validators.completeness import CompletenessValidator
from review.validators.technical_rationality import TechnicalRationalityAssessor
from review.validators.test_sufficiency import TestSufficiencyChecker
from review.validators.coding_standard import CodingStandardConformer
from review.validators.impact_scope import ImpactScopeAssessor
from review.validators.report_normativity import ReportNormativityChecker


def _make_context(score_engine="", reasoning="", coding="", performance="",
                  agent="", config_yaml="", config_py=""):
    return ReviewContext(
        task_registry={
            "T-01": TaskDef(id="T-01", priority="S-1", status="已完成", change_file="utils/score_engine.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-02": TaskDef(id="T-02", priority="S-5", status="已完成", change_file="evaluators/reasoning.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-03": TaskDef(id="T-03", priority="F-3", status="已完成", change_file="evaluators/coding.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-04": TaskDef(id="T-04", priority="R-1", status="已完成", change_file="evaluators/performance.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-05": TaskDef(id="T-05", priority="P-1", status="已完成", change_file="evaluators/agent.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-06": TaskDef(id="T-06", priority="P-2", status="延后", change_file="",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-07": TaskDef(id="T-07", priority="P0-1", status="已完成", change_file="config.yaml",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
            "T-08": TaskDef(id="T-08", priority="P0-4", status="已完成", change_file="utils/config.py",
                            problem_before="", fix_after="", verification_method="", expected_result=""),
        },
        change_files={
            "utils/score_engine.py": score_engine,
            "evaluators/reasoning.py": reasoning,
            "evaluators/coding.py": coding,
            "evaluators/performance.py": performance,
            "evaluators/agent.py": agent,
            "config.yaml": config_yaml,
            "utils/config.py": config_py,
        },
        test_results=TestResultSet(total=32, passed=30, failed=0, skipped=2,
                                    skip_reasons={"t1": "T-06延至Phase1"}),
        acceptance_items={
            "T-01": AcceptanceItem(id="T-01", description="", verification_method="", expected_result=""),
        },
    )


class TestCompletenessValidator:
    def test_t01_pass(self):
        ctx = _make_context(score_engine="(c.score / c.max_score * 100 if c.max_score > 0 else 0) * c.weight")
        v = CompletenessValidator()
        findings = v._check_t01(ctx)
        assert any(f.severity == "观察" for f in findings)

    def test_t01_fail(self):
        ctx = _make_context(score_engine="c.score * c.weight")
        v = CompletenessValidator()
        findings = v._check_t01(ctx)
        assert any(f.severity == "严重" for f in findings)

    def test_t02_pass(self):
        code = "def _safe_parse_numeric(text):\n    return ast.literal_eval(cleaned)\n"
        ctx = _make_context(reasoning=code)
        v = CompletenessValidator()
        findings = v._check_t02(ctx)
        assert any(f.severity == "观察" for f in findings)

    def test_t02_fail_eval(self):
        code = "result = eval(user_input)\n"
        ctx = _make_context(reasoning=code)
        v = CompletenessValidator()
        findings = v._check_t02(ctx)
        assert any(f.severity == "严重" for f in findings)

    def test_t03_pass(self):
        ctx = _make_context(coding="subprocess.run(timeout=15)")
        v = CompletenessValidator()
        findings = v._check_t03(ctx)
        assert any(f.severity == "观察" for f in findings)

    def test_t05_pass(self):
        code = 'self.include_browser_automation = False\nif getattr(self, "include_browser_automation", False):\n'
        ctx = _make_context(agent=code)
        v = CompletenessValidator()
        findings = v._check_t05(ctx)
        assert any(f.severity == "观察" for f in findings)

    def test_t06_deferred(self):
        ctx = _make_context()
        v = CompletenessValidator()
        findings = v._check_t06(ctx)
        assert any("延至Phase1" in f.description for f in findings)

    def test_t07_pass(self):
        yaml = "category_weights:\nprofiles:\n  openclaw:\n  hermes:\n  default:\neval_modes:\n"
        ctx = _make_context(config_yaml=yaml)
        v = CompletenessValidator()
        findings = v._check_t07(ctx)
        assert any(f.severity == "观察" for f in findings)


class TestTechnicalRationalityAssessor:
    def test_t01_math_correct(self):
        ctx = _make_context(score_engine="(c.score / c.max_score * 100 if c.max_score > 0 else 0) * c.weight")
        v = TechnicalRationalityAssessor()
        findings = v._assess_t01(ctx)
        assert any("数学正确" in f.description for f in findings)

    def test_t02_injection_safe(self):
        code = "def _safe_parse_numeric(text):\n    cleaned = re.sub(r'[^\\d.eE+\\-*/()]', '', text)\n    return ast.literal_eval(cleaned)\n    nums = re.findall(r'[\\d.]+', text)\n"
        ctx = _make_context(reasoning=code)
        v = TechnicalRationalityAssessor()
        findings = v._assess_t02(ctx)
        assert any("注入" in f.description and f.severity == "观察" for f in findings)


class TestTestSufficiencyChecker:
    def test_pass_rate_ok(self):
        ctx = _make_context()
        v = TestSufficiencyChecker()
        findings = v._check_pass_rate(ctx)
        assert any("达标" in f.description for f in findings)

    def test_pass_rate_fail(self):
        ctx = _make_context()
        ctx.test_results = TestResultSet(total=32, passed=25, failed=5, skipped=2)
        v = TestSufficiencyChecker()
        findings = v._check_pass_rate(ctx)
        assert any(f.severity == "严重" for f in findings)


class TestImpactScopeAssessor:
    def test_high_impact(self):
        ctx = _make_context()
        v = ImpactScopeAssessor()
        findings = v.execute(ctx)
        assert ctx.impact_matrix is not None
        assert ctx.impact_matrix.get_high_impact_count() >= 1

    def test_matrix_entries(self):
        ctx = _make_context()
        v = ImpactScopeAssessor()
        v.execute(ctx)
        assert len(ctx.impact_matrix.entries) == 8


class TestReportNormativityChecker:
    def test_empty_report(self):
        ctx = _make_context()
        v = ReportNormativityChecker()
        findings = v.execute(ctx)
        assert len(findings) > 0

    def test_complete_report(self):
        report = "# Phase 0 审查报告\n## 1. 审查背景\n## 2. 审查范围\n## 3. 审查维度\n## 4. 审查发现\n## 5. 审查结论\n## 6. 验收清单\n"
        ctx = _make_context()
        v = ReportNormativityChecker(report_content=report)
        findings = v._check_report_structure()
        assert any("完整" in f.description for f in findings)

    def test_vague_expressions(self):
        report = "修复基本符合要求"
        ctx = _make_context()
        v = ReportNormativityChecker(report_content=report)
        findings = v._check_no_vague_expressions()
        assert any(f.severity == "一般" for f in findings)
