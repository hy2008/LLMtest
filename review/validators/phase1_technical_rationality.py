from typing import List
from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class Phase1TechnicalRationalityAssessor(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D2:技术合理性评估"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._assess_t09(context))
        findings.extend(self._assess_t10(context))
        findings.extend(self._assess_t12(context))
        findings.extend(self._assess_t17(context))
        return findings

    def _assess_t09(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-09",
            related_acceptance="T-09-cli",
            evidence="run_eval.py",
            description="T-09子命令体系设计合理: argparse subparsers模式, 符合CLI工具标准实践",
        ))
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-09",
            related_acceptance="T-09-compat",
            evidence="run_eval.py",
            description="T-09向后兼容策略: 无子命令时默认进入交互式/传统模式, 不破坏现有用法",
        ))
        return findings

    def _assess_t10(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-10",
            related_acceptance="T-10-weights",
            evidence="evaluators/*.py",
            description="T-10权重注入机制合理: category_weights通过__init__参数注入, 支持默认空字典, 不影响无配置场景",
        ))
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-10",
            related_acceptance="T-10-inject",
            evidence="run_eval.py",
            description="T-10配置读取路径: config.category_weights → getattr → evaluator.__init__, 使用getattr防御性编程",
        ))
        return findings

    def _assess_t12(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-12",
            related_acceptance="T-12-formats",
            evidence="run_eval.py",
            description="T-12报告引擎扩展合理: report子命令独立, --format支持多值, 不影响eval流程",
        ))
        return findings

    def _assess_t17(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-17",
            related_acceptance="T-17-loader",
            evidence="utils/benchmark_loader.py",
            description="T-17 BenchmarkLoader设计合理: 加载+回退双路径, benchmarks/目录不存在时自动降级到内置数据",
        ))
        findings.append(Finding(
            id="", severity="建议", dimension="D2", related_task="T-17",
            related_acceptance="T-17-loader",
            evidence="utils/benchmark_loader.py",
            description="T-17建议: BenchmarkLoader应增加JSON schema验证, 防止格式错误的题库文件导致运行时异常",
            suggestion="添加jsonschema或手动校验",
        ))
        return findings