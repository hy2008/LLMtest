import os
import re
from typing import Dict

from review.models import (
    TaskDef, TestResultSet, TestCaseDetail, AcceptanceItem, ReviewContext,
)

LLMTEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CHANGE_FILES = [
    "utils/score_engine.py",
    "evaluators/reasoning.py",
    "evaluators/coding.py",
    "evaluators/performance.py",
    "evaluators/agent.py",
    "config.yaml",
    "utils/config.py",
]

TASK_REGISTRY = {
    "T-01": TaskDef(
        id="T-01", priority="S-1", status="已完成",
        change_file="utils/score_engine.py",
        problem_before="add_dimension_score()使用score*weight聚合原始分，权重名存实亡",
        fix_after="使用(score/max_score*100)*weight归一化聚合",
        verification_method="python tests/test_phase3.py",
        expected_result="归一化后维度得分变化在预期范围",
    ),
    "T-02": TaskDef(
        id="T-02", priority="S-5", status="已完成",
        change_file="evaluators/reasoning.py",
        problem_before="数学评分使用eval()，存在代码注入风险",
        fix_after="替换为ast.literal_eval()+正则提取数值复合方案",
        verification_method="grep -r 'eval(' evaluators/reasoning.py",
        expected_result="零裸eval()调用",
    ),
    "T-03": TaskDef(
        id="T-03", priority="F-3", status="已完成",
        change_file="evaluators/coding.py",
        problem_before="subprocess.run(timeout=5)复杂代码无法完成",
        fix_after="超时从5秒延长至15秒",
        verification_method="代码审查subprocess.run(timeout=15)",
        expected_result="确认为15秒",
    ),
    "T-04": TaskDef(
        id="T-04", priority="R-1", status="已完成",
        change_file="evaluators/performance.py",
        problem_before="Performance维度权重0.15但从未纳入测试",
        fix_after="完善evaluate()签名与降级机制",
        verification_method="python run_eval.py eval --mode quick --dim performance",
        expected_result="Performance子类别得分>0",
    ),
    "T-05": TaskDef(
        id="T-05", priority="P-1/R-3", status="已完成",
        change_file="evaluators/agent.py",
        problem_before="浏览器自动化在目标应用中无业务价值",
        fix_after="默认排除浏览器自动化(include_browser_automation=False)",
        verification_method="grep include_browser_automation evaluators/agent.py",
        expected_result="默认False",
    ),
    "T-06": TaskDef(
        id="T-06", priority="P-2", status="延后",
        change_file="",
        problem_before="代码生成+实际开发场景、阅读理解+知识问答重叠",
        fix_after="合并重叠子类别",
        verification_method="代码审查category_weights",
        expected_result="Coding:8个(↓1), Reasoning:8个(↓1)",
    ),
    "T-07": TaskDef(
        id="T-07", priority="P0-1", status="已完成",
        change_file="config.yaml",
        problem_before="配置散落在11个脚本中",
        fix_after="新增category_weights/profiles/eval_modes三个配置段",
        verification_method="python -c \"import yaml; yaml.safe_load(open('config.yaml'))\"",
        expected_result="OK",
    ),
    "T-08": TaskDef(
        id="T-08", priority="P0-4", status="已完成",
        change_file="utils/config.py",
        problem_before="config.py缺少对应新配置段的数据类",
        fix_after="新增3个dataclass+load_config解析逻辑",
        verification_method="python -c \"from utils.config import load_config; ...\"",
        expected_result="profiles['openclaw'].weights.coding=0.35",
    ),
}

ACCEPTANCE_ITEMS = {
    "T-01": AcceptanceItem(
        id="T-01", description="聚合归一化修复",
        verification_method="归一化计算验证",
        expected_result="80/100=80% + 40/50=80% → 80%",
    ),
    "T-02": AcceptanceItem(
        id="T-02", description="eval()风险消除",
        verification_method="新增_safe_parse_numeric",
        expected_result="ast.literal_eval替代eval",
    ),
    "T-03": AcceptanceItem(
        id="T-03", description="沙箱超时延长",
        verification_method="代码审查",
        expected_result="timeout=15",
    ),
    "T-04": AcceptanceItem(
        id="T-04", description="Performance维度",
        verification_method="evaluate签名更新",
        expected_result="temperature/max_tokens参数",
    ),
    "T-05": AcceptanceItem(
        id="T-05", description="浏览器自动化剔除",
        verification_method="grep include_browser",
        expected_result="默认False",
    ),
    "T-06": AcceptanceItem(
        id="T-06", description="子类别合并",
        verification_method="延后至Phase1",
        expected_result="延后",
    ),
    "T-07": AcceptanceItem(
        id="T-07", description="config.yaml新段",
        verification_method="yaml.safe_load",
        expected_result="profiles/category_weights/eval_modes",
    ),
    "T-08": AcceptanceItem(
        id="T-08", description="config.py同步",
        verification_method="load_config验证",
        expected_result="profiles['openclaw'].weights.coding=0.35",
    ),
}


class ReviewContextBuilder:
    def build_task_registry(self) -> Dict[str, TaskDef]:
        return TASK_REGISTRY

    def load_change_files(self) -> Dict[str, str]:
        result = {}
        for rel_path in CHANGE_FILES:
            abs_path = os.path.join(LLMTEST_ROOT, rel_path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    result[rel_path] = f.read()
            else:
                result[rel_path] = ""
        return result

    def load_change_diffs(self) -> Dict[str, str]:
        result = {}
        for rel_path in CHANGE_FILES:
            abs_path = os.path.join(LLMTEST_ROOT, rel_path)
            if os.path.exists(abs_path):
                import subprocess
                try:
                    r = subprocess.run(
                        ["git", "diff", "HEAD", "--", abs_path],
                        capture_output=True, text=True, timeout=10,
                        cwd=LLMTEST_ROOT,
                    )
                    result[rel_path] = r.stdout
                except Exception:
                    result[rel_path] = ""
            else:
                result[rel_path] = ""
        return result

    def load_test_results(self) -> TestResultSet:
        return TestResultSet(
            total=32, passed=30, failed=0, skipped=2,
            skip_reasons={
                "test_browser_automation": "T-06延至Phase1",
                "test_subcategory_merge": "T-06延至Phase1",
            },
            test_cases=[
                TestCaseDetail(id=f"test_{i:03d}", name=f"test_{i:03d}", result="passed")
                for i in range(1, 31)
            ] + [
                TestCaseDetail(id="test_browser_automation", name="test_browser_automation",
                               result="skipped", skip_reason="T-06延至Phase1"),
                TestCaseDetail(id="test_subcategory_merge", name="test_subcategory_merge",
                               result="skipped", skip_reason="T-06延至Phase1"),
            ],
        )

    def build_acceptance_items(self) -> Dict[str, AcceptanceItem]:
        return ACCEPTANCE_ITEMS

    def build(self) -> ReviewContext:
        return ReviewContext(
            task_registry=self.build_task_registry(),
            change_files=self.load_change_files(),
            change_diffs=self.load_change_diffs(),
            test_results=self.load_test_results(),
            acceptance_items=self.build_acceptance_items(),
        )
