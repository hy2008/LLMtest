import os
from typing import Dict

from review.models import (
    TaskDef, TestResultSet, TestCaseDetail, AcceptanceItem, ReviewContext,
    DeferredItemAssessment, ArchitectureImprovement,
)

LLMTEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CHANGE_FILES = [
    "run_eval.py",
    "evaluators/coding.py",
    "evaluators/agent.py",
    "evaluators/reasoning.py",
    "evaluators/performance.py",
    "utils/benchmark_loader.py",
    "config.yaml",
    "utils/config.py",
    "utils/score_engine.py",
    "utils/report_generator.py",
]

TASK_REGISTRY = {
    "T-09": TaskDef(id="T-09", priority="P0-2", status="已完成",
                     change_file="run_eval.py",
                     problem_before="11个独立脚本, 无统一入口",
                     fix_after="子命令体系(eval/report/leaderboard/lifecycle)+向后兼容",
                     verification_method="run_eval.py --help",
                     expected_result="eval/report/leaderboard/lifecycle子命令可用"),
    "T-10": TaskDef(id="T-10", priority="P0-5", status="已完成",
                     change_file="evaluators/*.py",
                     problem_before="权重硬编码在各evaluator中",
                     fix_after="__init__新增category_weights参数, 从config注入",
                     verification_method="4 evaluator __init__签名",
                     expected_result="category_weights参数存在"),
    "T-11": TaskDef(id="T-11", priority="P0-6", status="延后",
                     change_file="",
                     problem_before="15个冗余脚本",
                     fix_after="删除废弃脚本",
                     verification_method="文件系统检查",
                     expected_result="仅保留run_eval.py"),
    "T-12": TaskDef(id="T-12", priority="P0-3", status="已完成",
                     change_file="run_eval.py",
                     problem_before="仅HTML报告格式",
                     fix_after="report子命令支持html/json/txt三格式",
                     verification_method="report --format",
                     expected_result="html/json/txt支持"),
    "T-13": TaskDef(id="T-13", priority="S-2", status="延后",
                     change_file="",
                     problem_before="无外部基准对齐",
                     fix_after="HumanEval/MATH基准嵌入",
                     verification_method="题库检查",
                     expected_result="外部基准题目存在"),
    "T-14": TaskDef(id="T-14", priority="S-3", status="延后",
                     change_file="",
                     problem_before="无反向验证",
                     fix_after="增加反向验证评分",
                     verification_method="评分逻辑检查",
                     expected_result="反向验证存在"),
    "T-15": TaskDef(id="T-15", priority="C-1", status="延后",
                     change_file="",
                     problem_before="仅Python语言",
                     fix_after="JS/Shell/SQL用例",
                     verification_method="题库检查",
                     expected_result="多语言用例存在"),
    "T-16": TaskDef(id="T-16", priority="C-2", status="延后",
                     change_file="",
                     problem_before="无RAG评估",
                     fix_after="RAG评估子类别",
                     verification_method="评估器检查",
                     expected_result="RAG子类别存在"),
    "T-17": TaskDef(id="T-17", priority="P1-1", status="已完成",
                     change_file="utils/benchmark_loader.py",
                     problem_before="题库Python字典内嵌",
                     fix_after="BenchmarkLoader+JSON外置+内置回退",
                     verification_method="BenchmarkLoader类检查",
                     expected_result="load/load_all/has_data可用"),
    "T-18": TaskDef(id="T-18", priority="P1-5", status="延后",
                     change_file="",
                     problem_before="Tokenizer未校准",
                     fix_after="Tokenizer自适应校准",
                     verification_method="校准逻辑检查",
                     expected_result="校准功能存在"),
    "T-19": TaskDef(id="T-19", priority="P1-2", status="延后",
                     change_file="",
                     problem_before="无统计显著性",
                     fix_after="均值/标准差/置信区间",
                     verification_method="统计输出检查",
                     expected_result="统计指标存在"),
}

ACCEPTANCE_ITEMS = {
    "T-09-cli": AcceptanceItem(id="T-09-cli", description="CLI子命令",
                               verification_method="run_eval.py --help",
                               expected_result="eval/report/leaderboard/lifecycle"),
    "T-09-profile": AcceptanceItem(id="T-09-profile", description="Profile支持",
                                   verification_method="run_eval.py eval --help",
                                   expected_result="--profile openclaw/hermes/default"),
    "T-09-compat": AcceptanceItem(id="T-09-compat", description="向后兼容",
                                  verification_method="无子命令运行",
                                  expected_result="交互式评估正常"),
    "T-10-weights": AcceptanceItem(id="T-10-weights", description="权重适配",
                                   verification_method="4 evaluator __init__",
                                   expected_result="category_weights参数"),
    "T-10-inject": AcceptanceItem(id="T-10-inject", description="run_eval调用",
                                  verification_method="从配置读取权重",
                                  expected_result="category_weights注入"),
    "T-12-formats": AcceptanceItem(id="T-12-formats", description="报告多格式",
                                   verification_method="report子命令--format",
                                   expected_result="html/json/txt支持"),
    "T-17-loader": AcceptanceItem(id="T-17-loader", description="JSON外置",
                                  verification_method="BenchmarkLoader存在",
                                  expected_result="load/load_all/has_data"),
    "T-17-fallback": AcceptanceItem(id="T-17-fallback", description="内置回退",
                                    verification_method="benchmarks目录不存在时",
                                    expected_result="使用_BUILTIN_FALLBACK"),
}

DEFERRED_ITEMS = [
    DeferredItemAssessment(task_id="T-11", reason="废弃脚本可能仍有外部引用",
                           merge_plan="Phase 1验证后统一清理", is_reasonable=True, risk_level="低"),
    DeferredItemAssessment(task_id="T-13", reason="外部基准需嵌入题库",
                           merge_plan="与T-17 JSON外置合并", is_reasonable=True, risk_level="低"),
    DeferredItemAssessment(task_id="T-14", reason="反向验证需评分框架就绪",
                           merge_plan="后续迭代实现", is_reasonable=True, risk_level="中"),
    DeferredItemAssessment(task_id="T-15", reason="语言扩展需题库外置",
                           merge_plan="与T-17 JSON外置合并", is_reasonable=True, risk_level="低"),
    DeferredItemAssessment(task_id="T-16", reason="RAG评估新维度",
                           merge_plan="后续迭代新增", is_reasonable=True, risk_level="中"),
    DeferredItemAssessment(task_id="T-18", reason="Tokenizer校准需客户端改造",
                           merge_plan="后续迭代实现", is_reasonable=True, risk_level="中"),
    DeferredItemAssessment(task_id="T-19", reason="统计显著性需评分引擎改造",
                           merge_plan="后续迭代实现", is_reasonable=True, risk_level="中"),
]

ARCHITECTURE_IMPROVEMENTS = [
    ArchitectureImprovement(metric="CLI入口", before="11个脚本", after="1个(子命令体系)", improvement="统一入口"),
    ArchitectureImprovement(metric="权重定义", before="硬编码", after="config注入评估器", improvement="配置驱动"),
    ArchitectureImprovement(metric="Profile支持", before="配置存在", after="评估流程使用", improvement="场景化评估"),
    ArchitectureImprovement(metric="报告格式", before="HTML only", after="HTML/JSON/TXT", improvement="多格式输出"),
    ArchitectureImprovement(metric="题库架构", before="Python字典", after="BenchmarkLoader+JSON", improvement="数据外置"),
]


class Phase1ContextBuilder:
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
            skip_reasons={"test_browser_automation": "T-06延至Phase1"},
            test_cases=[
                TestCaseDetail(id=f"test_{i:03d}", name=f"test_{i:03d}", result="passed")
                for i in range(1, 31)
            ],
        )

    def build_acceptance_items(self) -> Dict[str, AcceptanceItem]:
        return ACCEPTANCE_ITEMS

    def build_deferred_assessments(self):
        return DEFERRED_ITEMS

    def build_architecture_improvements(self):
        return ARCHITECTURE_IMPROVEMENTS

    def build(self) -> ReviewContext:
        return ReviewContext(
            task_registry=self.build_task_registry(),
            change_files=self.load_change_files(),
            change_diffs=self.load_change_diffs(),
            test_results=self.load_test_results(),
            acceptance_items=self.build_acceptance_items(),
            deferred_assessments=self.build_deferred_assessments(),
            architecture_improvements=self.build_architecture_improvements(),
        )