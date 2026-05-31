import pytest
from review.models import (
    TaskDef, Finding, TestResultSet, TestCaseDetail, AcceptanceItem,
    ReviewContext, ImpactEntry, ImpactMatrix, ReviewConclusion,
)


class TestTaskDef:
    def test_create(self):
        t = TaskDef(id="T-01", priority="S-1", status="已完成",
                     change_file="a.py", problem_before="bug",
                     fix_after="fix", verification_method="test",
                     expected_result="pass")
        assert t.id == "T-01"
        assert t.status == "已完成"


class TestFinding:
    def test_create(self):
        f = Finding(id="F-01", severity="严重", dimension="D1",
                     related_task="T-01", related_acceptance="T-01",
                     evidence="a.py:10", description="发现严重问题",
                     suggestion="修复", estimated_fix_time="1h")
        assert f.severity == "严重"
        assert f.suggestion == "修复"

    def test_optional_fields(self):
        f = Finding(id="F-02", severity="观察", dimension="D1",
                     related_task="T-01", related_acceptance="T-01",
                     evidence="test", description="观察项")
        assert f.suggestion is None
        assert f.estimated_fix_time is None


class TestTestResultSet:
    def test_create(self):
        tr = TestResultSet(total=32, passed=30, failed=0, skipped=2)
        assert tr.passed == 30
        assert tr.failed == 0

    def test_with_details(self):
        tc = TestCaseDetail(id="t1", name="test1", result="passed")
        tr = TestResultSet(total=1, passed=1, failed=0, skipped=0, test_cases=[tc])
        assert len(tr.test_cases) == 1


class TestAcceptanceItem:
    def test_create(self):
        ai = AcceptanceItem(id="T-01", description="测试", verification_method="method",
                             expected_result="pass")
        assert ai.actual_result == ""
        assert ai.conclusion == ""


class TestImpactMatrix:
    def test_get_by_file(self):
        entries = [
            ImpactEntry(change_file="a.py", affected_module="m1", impact_level="高", impact_description="desc1"),
            ImpactEntry(change_file="b.py", affected_module="m2", impact_level="低", impact_description="desc2"),
        ]
        m = ImpactMatrix(entries=entries)
        assert len(m.get_by_file("a.py")) == 1
        assert len(m.get_by_file("b.py")) == 1
        assert len(m.get_by_file("c.py")) == 0

    def test_get_by_level(self):
        entries = [
            ImpactEntry(change_file="a.py", affected_module="m1", impact_level="高", impact_description="d1"),
            ImpactEntry(change_file="b.py", affected_module="m2", impact_level="低", impact_description="d2"),
            ImpactEntry(change_file="c.py", affected_module="m3", impact_level="高", impact_description="d3"),
        ]
        m = ImpactMatrix(entries=entries)
        assert len(m.get_by_level("高")) == 2
        assert len(m.get_by_level("低")) == 1

    def test_get_high_impact_count(self):
        entries = [
            ImpactEntry(change_file="a.py", affected_module="m1", impact_level="高", impact_description="d"),
            ImpactEntry(change_file="b.py", affected_module="m2", impact_level="中", impact_description="d"),
        ]
        m = ImpactMatrix(entries=entries)
        assert m.get_high_impact_count() == 1


class TestReviewConclusion:
    def test_pass(self):
        findings = [
            Finding(id="F-01", severity="观察", dimension="D1", related_task="T-01",
                     related_acceptance="T-01", evidence="e", description="d"),
            Finding(id="F-02", severity="建议", dimension="D1", related_task="T-01",
                     related_acceptance="T-01", evidence="e", description="d"),
        ]
        ai = {"T-01": AcceptanceItem(id="T-01", description="t", verification_method="m",
                                      expected_result="r", conclusion="通过")}
        c = ReviewConclusion.from_findings(findings, ai)
        assert c.verdict == "通过"
        assert c.observation_count == 1
        assert c.suggestion_count == 1

    def test_conditional_pass(self):
        findings = [
            Finding(id="F-01", severity="一般", dimension="D1", related_task="T-01",
                     related_acceptance="T-01", evidence="e", description="d"),
        ]
        ai = {"T-01": AcceptanceItem(id="T-01", description="t", verification_method="m",
                                      expected_result="r", conclusion="通过")}
        c = ReviewConclusion.from_findings(findings, ai)
        assert c.verdict == "有条件通过"

    def test_fail(self):
        findings = [
            Finding(id="F-01", severity="严重", dimension="D1", related_task="T-01",
                     related_acceptance="T-01", evidence="e", description="d"),
        ]
        ai = {"T-01": AcceptanceItem(id="T-01", description="t", verification_method="m",
                                      expected_result="r", conclusion="不通过")}
        c = ReviewConclusion.from_findings(findings, ai)
        assert c.verdict == "不通过"
        assert c.severe_count == 1

    def test_acceptance_coverage(self):
        ai = {
            "T-01": AcceptanceItem(id="T-01", description="t", verification_method="m",
                                    expected_result="r", conclusion="通过"),
            "T-02": AcceptanceItem(id="T-02", description="t", verification_method="m",
                                    expected_result="r", conclusion="延后"),
        }
        c = ReviewConclusion.from_findings([], ai)
        assert c.acceptance_coverage == 1.0


class TestReviewContext:
    def test_default(self):
        ctx = ReviewContext()
        assert ctx.task_registry == {}
        assert ctx.findings == []
        assert ctx.test_results is None
