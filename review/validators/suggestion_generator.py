from typing import List
from review.models import Finding, ReviewContext, SuggestionItem
from review.validators import IReviewDimensionValidator


class SuggestionGenerator(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D8:建议意见反馈"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        suggestions = self._generate_suggestions(context)
        context.suggestions = suggestions

        findings.append(Finding(
            id="", severity="观察", dimension="D8", related_task="T-09",
            related_acceptance="T-09-cli",
            evidence=f"生成{len(suggestions)}条建议",
            description=f"建议意见反馈: 已生成{len(suggestions)}条面向开发团队的建议, 按优先级排序",
        ))
        return findings

    def _generate_suggestions(self, ctx: ReviewContext) -> List[SuggestionItem]:
        suggestions = [
            SuggestionItem(
                priority=1, category="架构", target="T-11",
                description="清理废弃脚本时机已成熟",
                action="Phase 1验证通过后, 执行T-11删除15个run_*.py旧脚本, 仅保留run_eval.py",
                estimated_effort="0.5天",
            ),
            SuggestionItem(
                priority=2, category="测试", target="T-09/T-10",
                description="补充CLI和权重适配专项测试",
                action="新增test_cli_subcommands.py和test_weight_injection.py, 覆盖子命令参数解析和权重注入路径",
                estimated_effort="1天",
            ),
            SuggestionItem(
                priority=3, category="数据", target="T-13/T-15",
                description="外部基准和多语言用例应与JSON外置同步推进",
                action="在benchmarks/目录下新增human_eval/和multilingual/子目录, 与T-17 BenchmarkLoader集成",
                estimated_effort="2天",
            ),
            SuggestionItem(
                priority=4, category="功能", target="T-14",
                description="反向验证是评分科学性的关键增强",
                action="在score_engine.py中增加reverse_validation方法, 代码审查增加修复代码执行验证",
                estimated_effort="1.5天",
            ),
            SuggestionItem(
                priority=5, category="架构", target="T-17",
                description="BenchmarkLoader应增加JSON schema验证",
                action="在load()方法中增加题库文件格式校验, 防止格式错误导致运行时异常",
                estimated_effort="0.5天",
            ),
            SuggestionItem(
                priority=6, category="功能", target="T-16",
                description="RAG评估是应用场景的重要维度",
                action="新增RAGEvaluator, 包含检索准确率/生成质量/幻觉检测3个子类别",
                estimated_effort="3天",
            ),
            SuggestionItem(
                priority=7, category="统计", target="T-18/T-19",
                description="Tokenizer校准和统计显著性提升评估科学性",
                action="T-18: 基于tokenizer计算真实token数校准评分; T-19: 多次运行计算均值/标准差/95%置信区间",
                estimated_effort="2天",
            ),
        ]
        return suggestions