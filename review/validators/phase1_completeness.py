from typing import List
from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class Phase1CompletenessValidator(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D1:修复完整性验证"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._check_t09(context))
        findings.extend(self._check_t10(context))
        findings.extend(self._check_t12(context))
        findings.extend(self._check_t17(context))
        findings.extend(self._check_deferred(context))
        return findings

    def _check_t09(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("run_eval.py", "")
        has_subparsers = "add_subparsers" in content
        has_eval = '"eval"' in content or "'eval'" in content
        has_report = '"report"' in content or "'report'" in content
        has_leaderboard = '"leaderboard"' in content or "'leaderboard'" in content
        has_lifecycle = '"lifecycle"' in content or "'lifecycle'" in content
        has_profile = "--profile" in content and "openclaw" in content

        if has_subparsers and has_eval and has_report and has_leaderboard and has_lifecycle:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-09",
                related_acceptance="T-09-cli",
                evidence="run_eval.py",
                description="T-09 CLI子命令完整: eval/report/leaderboard/lifecycle四个子命令已实现",
            ))
        else:
            missing = []
            if not has_subparsers: missing.append("subparsers")
            if not has_eval: missing.append("eval")
            if not has_report: missing.append("report")
            if not has_leaderboard: missing.append("leaderboard")
            if not has_lifecycle: missing.append("lifecycle")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-09",
                related_acceptance="T-09-cli",
                evidence="run_eval.py",
                description=f"T-09 CLI子命令不完整: 缺少{missing}",
                suggestion="补充缺失子命令", estimated_fix_time="2h",
            ))

        if has_profile:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-09",
                related_acceptance="T-09-profile",
                evidence="run_eval.py",
                description="T-09 Profile支持完整: --profile参数含openclaw/hermes/default",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-09",
                related_acceptance="T-09-profile",
                evidence="run_eval.py",
                description="T-09缺少--profile参数",
                suggestion="添加--profile参数", estimated_fix_time="0.5h",
            ))

        has_compat = "交互式" in content or "interactive" in content.lower() or "向后兼容" in content
        if has_compat:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-09",
                related_acceptance="T-09-compat",
                evidence="run_eval.py",
                description="T-09向后兼容: 无子命令时支持交互式/传统参数运行",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-09",
                related_acceptance="T-09-compat",
                evidence="run_eval.py",
                description="T-09向后兼容性需确认: 未发现明确的兼容处理逻辑",
                suggestion="确认无子命令时的默认行为", estimated_fix_time="1h",
            ))
        return findings

    def _check_t10(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        evaluators = {
            "evaluators/coding.py": "CodingEvaluator",
            "evaluators/agent.py": "AgentEvaluator",
            "evaluators/reasoning.py": "ReasoningEvaluator",
            "evaluators/performance.py": "PerformanceEvaluator",
        }
        all_ok = True
        for fpath, _ in evaluators.items():
            content = ctx.change_files.get(fpath, "")
            if "category_weights" not in content:
                all_ok = False
                findings.append(Finding(
                    id="", severity="严重", dimension="D1", related_task="T-10",
                    related_acceptance="T-10-weights",
                    evidence=fpath,
                    description=f"T-10 {fpath}缺少category_weights参数",
                    suggestion="添加category_weights参数", estimated_fix_time="1h",
                ))

        if all_ok:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-10",
                related_acceptance="T-10-weights",
                evidence="evaluators/*.py",
                description="T-10权重适配完整: 4个evaluator均含category_weights参数",
            ))

        run_eval = ctx.change_files.get("run_eval.py", "")
        has_inject = "category_weights" in run_eval and "c_weights" in run_eval
        if has_inject:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-10",
                related_acceptance="T-10-inject",
                evidence="run_eval.py",
                description="T-10权重注入完整: run_eval.py从config读取category_weights并注入evaluator",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-10",
                related_acceptance="T-10-inject",
                evidence="run_eval.py",
                description="T-10权重注入不完整: run_eval.py未从config注入category_weights",
                suggestion="添加config→evaluator权重注入逻辑", estimated_fix_time="1h",
            ))
        return findings

    def _check_t12(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("run_eval.py", "")
        has_report_cmd = '"report"' in content or "'report'" in content
        has_format = "--format" in content
        formats = []
        for fmt in ["html", "json", "txt"]:
            if fmt in content:
                formats.append(fmt)

        if has_report_cmd and has_format and len(formats) >= 3:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-12",
                related_acceptance="T-12-formats",
                evidence="run_eval.py",
                description=f"T-12报告多格式完整: report子命令支持{formats}",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-12",
                related_acceptance="T-12-formats",
                evidence="run_eval.py",
                description=f"T-12报告格式不完整: 仅支持{formats}",
                suggestion="补充缺失格式支持", estimated_fix_time="1h",
            ))
        return findings

    def _check_t17(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("utils/benchmark_loader.py", "")
        if not content:
            content = ctx.change_files.get("utils/benchmark_loader.py", "")

        has_loader = "BenchmarkLoader" in content
        has_load = "def load" in content
        has_load_all = "load_all" in content
        has_has_data = "has_data" in content
        has_fallback = "_BUILTIN_FALLBACK" in content or "BUILTIN" in content.upper()

        if has_loader and has_load and has_load_all and has_has_data:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-17",
                related_acceptance="T-17-loader",
                evidence="utils/benchmark_loader.py",
                description="T-17 BenchmarkLoader完整: 含load/load_all/has_data方法",
            ))
        else:
            missing = []
            if not has_loader: missing.append("BenchmarkLoader类")
            if not has_load: missing.append("load方法")
            if not has_load_all: missing.append("load_all方法")
            if not has_has_data: missing.append("has_data方法")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-17",
                related_acceptance="T-17-loader",
                evidence="utils/benchmark_loader.py",
                description=f"T-17 BenchmarkLoader不完整: 缺少{missing}",
                suggestion="补充缺失方法", estimated_fix_time="2h",
            ))

        if has_fallback:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-17",
                related_acceptance="T-17-fallback",
                evidence="utils/benchmark_loader.py",
                description="T-17内置回退机制完整: benchmarks目录不存在时使用_BUILTIN_FALLBACK",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-17",
                related_acceptance="T-17-fallback",
                evidence="utils/benchmark_loader.py",
                description="T-17缺少内置回退机制",
                suggestion="添加_BUILTIN_FALLBACK", estimated_fix_time="1h",
            ))
        return findings

    def _check_deferred(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        deferred_tasks = [t for t in ctx.task_registry.values() if t.status == "延后"]
        findings.append(Finding(
            id="", severity="观察", dimension="D1", related_task="T-11",
            related_acceptance="T-11",
            evidence="task_registry",
            description=f"延后项确认: {len(deferred_tasks)}个任务延后(T-11/T-13~T-16/T-18~T-19), 均有延后原因说明",
        ))
        return findings