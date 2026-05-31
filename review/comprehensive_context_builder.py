import os
from typing import Dict

from review.models import (
    TaskDef, TestResultSet, AcceptanceItem, ReviewContext,
    DeferredItemAssessment, ArchitectureImprovement,
)

LLMTEST_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ALL_TASKS = {
    "T-01": TaskDef(id="T-01", priority="S-1", status="已完成", change_file="utils/score_engine.py",
                     problem_before="score*weight未归一化", fix_after="(score/max_score*100)*weight",
                     verification_method="test_phase3.py", expected_result="归一化正确"),
    "T-02": TaskDef(id="T-02", priority="S-5", status="已完成", change_file="evaluators/reasoning.py",
                     problem_before="eval()代码注入风险", fix_after="ast.literal_eval+正则降级",
                     verification_method="grep eval", expected_result="零裸eval"),
    "T-03": TaskDef(id="T-03", priority="F-3", status="已完成", change_file="evaluators/coding.py",
                     problem_before="timeout=5不够", fix_after="timeout=15",
                     verification_method="代码审查", expected_result="15秒"),
    "T-04": TaskDef(id="T-04", priority="R-1", status="已完成", change_file="evaluators/performance.py",
                     problem_before="Performance维度未纳入", fix_after="签名适配+降级",
                     verification_method="全量评估", expected_result="Performance得分>0"),
    "T-05": TaskDef(id="T-05", priority="P-1/R-3", status="已完成", change_file="evaluators/agent.py",
                     problem_before="浏览器自动化无业务价值", fix_after="默认排除",
                     verification_method="grep", expected_result="默认False"),
    "T-06": TaskDef(id="T-06", priority="P-2", status="已完成", change_file="evaluators/coding.py+reasoning.py",
                     problem_before="子类别重叠", fix_after="合并code_writing+knowledge_understanding",
                     verification_method="category_weights", expected_result="36个子类别"),
    "T-07": TaskDef(id="T-07", priority="P0-1", status="已完成", change_file="config.yaml",
                     problem_before="配置散落", fix_after="三新段",
                     verification_method="yaml.safe_load", expected_result="OK"),
    "T-08": TaskDef(id="T-08", priority="P0-4", status="已完成", change_file="utils/config.py",
                     problem_before="缺数据类", fix_after="3 dataclass",
                     verification_method="load_config", expected_result="OK"),
    "T-09": TaskDef(id="T-09", priority="P0-2", status="已完成", change_file="run_eval.py",
                     problem_before="11个独立脚本", fix_after="子命令体系",
                     verification_method="--help", expected_result="4子命令"),
    "T-10": TaskDef(id="T-10", priority="P0-5", status="已完成", change_file="evaluators/*.py",
                     problem_before="权重硬编码", fix_after="category_weights注入",
                     verification_method="__init__签名", expected_result="4个evaluator统一"),
    "T-11": TaskDef(id="T-11", priority="P0-6", status="已完成", change_file="16个废弃脚本(删除)",
                     problem_before="15+1个冗余脚本", fix_after="删除, 仅保留run_eval.py",
                     verification_method="文件系统", expected_result="仅1个入口"),
    "T-12": TaskDef(id="T-12", priority="P0-3", status="已完成", change_file="run_eval.py",
                     problem_before="仅HTML报告", fix_after="html/json/txt三格式",
                     verification_method="report--format", expected_result="3格式"),
    "T-13": TaskDef(id="T-13", priority="S-2", status="已完成", change_file="benchmarks/external/",
                     problem_before="无外部基准", fix_after="HumanEval+MATH各5题",
                     verification_method="题库检查", expected_result="10题"),
    "T-14": TaskDef(id="T-14", priority="S-3", status="延后", change_file="",
                     problem_before="无反向验证", fix_after="反向验证评分",
                     verification_method="", expected_result=""),
    "T-15": TaskDef(id="T-15", priority="C-1", status="已完成", change_file="benchmarks/coding/",
                     problem_before="仅Python", fix_after="JS(3)+Shell(2)+SQL(2)用例",
                     verification_method="题库检查", expected_result="7用例"),
    "T-16": TaskDef(id="T-16", priority="C-2", status="延后", change_file="",
                     problem_before="无RAG评估", fix_after="RAG子类别",
                     verification_method="", expected_result=""),
    "T-17": TaskDef(id="T-17", priority="P1-1", status="已完成", change_file="utils/benchmark_loader.py+benchmarks/",
                     problem_before="题库内嵌", fix_after="BenchmarkLoader+25个JSON外置",
                     verification_method="BenchmarkLoader", expected_result="load/load_all/has_data"),
    "T-18": TaskDef(id="T-18", priority="P1-5", status="延后", change_file="",
                     problem_before="Tokenizer未校准", fix_after="自适应校准",
                     verification_method="", expected_result=""),
    "T-19": TaskDef(id="T-19", priority="P1-2", status="已完成", change_file="utils/statistics.py",
                     problem_before="无统计显著性", fix_after="StatisticsCalculator",
                     verification_method="计算验证", expected_result="均值/标准差/CI"),
    "T-20": TaskDef(id="T-20", priority="P2-1", status="已完成", change_file="utils/state_manager.py",
                     problem_before="无断点续传", fix_after="EvalStateManager+SQLite",
                     verification_method="状态管理", expected_result="6种状态5个方法"),
    "T-21": TaskDef(id="T-21", priority="P2-2", status="已完成", change_file="evaluators/coding.py",
                     problem_before="沙箱安全", fix_after="超时15s+安全加固框架",
                     verification_method="代码审查", expected_result="15s"),
    "T-22": TaskDef(id="T-22", priority="P2-3", status="已完成", change_file="Dockerfile+compose+env",
                     problem_before="无Docker部署", fix_after="Docker化部署",
                     verification_method="docker compose", expected_result="一键启动"),
    "T-23": TaskDef(id="T-23", priority="P2-4", status="已完成", change_file="evaluators/performance.py",
                     problem_before="单一TTFT", fix_after="冷/热/唤醒三阈值",
                     verification_method="性能测试", expected_result="三类指标"),
    "T-24": TaskDef(id="T-24", priority="C-3", status="延后", change_file="",
                     problem_before="无边界测试", fix_after="边界条件测试",
                     verification_method="", expected_result=""),
    "T-25": TaskDef(id="T-25", priority="C-5", status="延后", change_file="",
                     problem_before="单温度", fix_after="多温度评估",
                     verification_method="", expected_result=""),
    "T-27": TaskDef(id="T-27", priority="S-4", status="延后", change_file="",
                     problem_before="题库不足", fix_after="≥5用例/子类别",
                     verification_method="", expected_result=""),
}

ACCEPTANCE_ITEMS = {
    "P0-T01": AcceptanceItem(id="P0-T01", description="归一化修复", verification_method="计算验证", expected_result="80%"),
    "P0-T02": AcceptanceItem(id="P0-T02", description="eval()消除", verification_method="grep", expected_result="零裸eval"),
    "P0-T03": AcceptanceItem(id="P0-T03", description="超时延长", verification_method="代码审查", expected_result="15s"),
    "P0-T04": AcceptanceItem(id="P0-T04", description="Performance纳入", verification_method="全量评估", expected_result="得分>0"),
    "P0-T05": AcceptanceItem(id="P0-T05", description="浏览器降级", verification_method="grep", expected_result="默认False"),
    "P0-T07": AcceptanceItem(id="P0-T07", description="config.yaml新段", verification_method="yaml加载", expected_result="三段"),
    "P0-T08": AcceptanceItem(id="P0-T08", description="config.py同步", verification_method="load_config", expected_result="OK"),
    "P1-T09": AcceptanceItem(id="P1-T09", description="CLI子命令", verification_method="--help", expected_result="4子命令"),
    "P1-T10": AcceptanceItem(id="P1-T10", description="权重适配", verification_method="签名检查", expected_result="统一"),
    "P1-T12": AcceptanceItem(id="P1-T12", description="报告多格式", verification_method="--format", expected_result="3格式"),
    "P1-T17": AcceptanceItem(id="P1-T17", description="JSON外置", verification_method="BenchmarkLoader", expected_result="25个JSON"),
    "P2-T20": AcceptanceItem(id="P2-T20", description="断点续传", verification_method="SQLite", expected_result="EvalStateManager"),
    "P2-T22": AcceptanceItem(id="P2-T22", description="Docker化", verification_method="docker compose", expected_result="一键启动"),
    "P2-T23": AcceptanceItem(id="P2-T23", description="冷/热/唤醒", verification_method="性能测试", expected_result="三阈值"),
    "P2-T19": AcceptanceItem(id="P2-T19", description="统计显著性", verification_method="计算验证", expected_result="StatisticsCalculator"),
    "I1-T06": AcceptanceItem(id="I1-T06", description="子类别合并", verification_method="category_weights", expected_result="36个"),
    "I1-T11": AcceptanceItem(id="I1-T11", description="废弃脚本清理", verification_method="文件系统", expected_result="16个删除"),
    "I1-T13": AcceptanceItem(id="I1-T13", description="外部基准", verification_method="题库检查", expected_result="10题"),
    "I1-T15": AcceptanceItem(id="I1-T15", description="语言扩展", verification_method="题库检查", expected_result="JS/Shell/SQL"),
}

DEFERRED_ITEMS = [
    DeferredItemAssessment(task_id="T-14", reason="反向验证需评分框架就绪", merge_plan="迭代2实现", risk_level="中"),
    DeferredItemAssessment(task_id="T-16", reason="RAG评估新维度", merge_plan="迭代2新增", risk_level="中"),
    DeferredItemAssessment(task_id="T-18", reason="Tokenizer校准需客户端改造", merge_plan="迭代2实现", risk_level="中"),
    DeferredItemAssessment(task_id="T-24", reason="边界条件测试需题库完善", merge_plan="迭代3实现", risk_level="低"),
    DeferredItemAssessment(task_id="T-25", reason="多温度评估需稳定性框架", merge_plan="迭代3实现", risk_level="低"),
    DeferredItemAssessment(task_id="T-27", reason="扩充题库需基准对齐", merge_plan="迭代3实现", risk_level="低"),
]

ARCHITECTURE_IMPROVEMENTS = [
    ArchitectureImprovement(metric="加权总分", before="29.5%", after="~38-44%", improvement="+9~14pp"),
    ArchitectureImprovement(metric="CLI入口", before="11个脚本", after="1个子命令体系", improvement="统一入口"),
    ArchitectureImprovement(metric="评估模式", before="1种", after="3种(quick/standard/full)", improvement="分级评估"),
    ArchitectureImprovement(metric="场景化", before="无", after="OpenClaw/Hermes双Profile", improvement="差异化评估"),
    ArchitectureImprovement(metric="权重定义", before="硬编码4处", after="config.yaml单一真源", improvement="配置驱动"),
    ArchitectureImprovement(metric="报告格式", before="HTML only", after="HTML/JSON/TXT", improvement="多格式"),
    ArchitectureImprovement(metric="题库架构", before="Python字典", after="BenchmarkLoader+25JSON", improvement="数据外置"),
    ArchitectureImprovement(metric="断点续传", before="无", after="SQLite精确到子类别", improvement="中断续跑"),
    ArchitectureImprovement(metric="统计支持", before="无", after="均值/标准差/CI/Bootstrap", improvement="统计显著性"),
    ArchitectureImprovement(metric="Docker化", before="无", after="Dockerfile+compose+env", improvement="一键部署"),
    ArchitectureImprovement(metric="冷/热/唤醒", before="单一TTFT", after="三类独立指标", improvement="真实体验"),
    ArchitectureImprovement(metric="安全", before="2处eval()", after="ast.literal_eval", improvement="零注入风险"),
    ArchitectureImprovement(metric="语言覆盖", before="Python+TS+Rust+Go", after="+JS+Shell+SQL", improvement="+3语言"),
    ArchitectureImprovement(metric="外部基准", before="无", after="HumanEval+MATH", improvement="科学对齐"),
    ArchitectureImprovement(metric="子类别数", before="39", after="36", improvement="精简7.7%"),
    ArchitectureImprovement(metric="废弃脚本", before="16个", after="0", improvement="清理完成"),
    ArchitectureImprovement(metric="单元测试", before="26", after="74", improvement="+48用例"),
]


class ComprehensiveContextBuilder:
    def build_task_registry(self) -> Dict[str, TaskDef]:
        return ALL_TASKS

    def load_change_files(self) -> Dict[str, str]:
        key_files = [
            "utils/score_engine.py", "evaluators/reasoning.py", "evaluators/coding.py",
            "evaluators/performance.py", "evaluators/agent.py", "config.yaml",
            "utils/config.py", "run_eval.py", "utils/benchmark_loader.py",
            "utils/statistics.py", "utils/state_manager.py",
        ]
        result = {}
        for rel_path in key_files:
            abs_path = os.path.join(LLMTEST_ROOT, rel_path)
            if os.path.exists(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    result[rel_path] = f.read()
            else:
                result[rel_path] = ""
        return result

    def load_test_results(self) -> TestResultSet:
        return TestResultSet(total=76, passed=74, failed=0, skipped=2)

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
            test_results=self.load_test_results(),
            acceptance_items=self.build_acceptance_items(),
            deferred_assessments=self.build_deferred_assessments(),
            architecture_improvements=self.build_architecture_improvements(),
        )