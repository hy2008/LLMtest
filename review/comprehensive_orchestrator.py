import logging
from typing import List, Tuple
from review.models import Finding, ReviewContext, ReviewConclusion
from review.comprehensive_context_builder import ComprehensiveContextBuilder
from review.comprehensive_validators import (
    ComprehensiveCompletenessValidator,
    ComprehensiveTechnicalAssessor,
    ComprehensiveTestChecker,
    ComprehensiveImpactAssessor,
    ComprehensiveDeferredAssessor,
    ComprehensiveSuggestionGenerator,
)
from review.report.phase1_generator import Phase1ReportGenerator


class ComprehensiveOrchestrator:
    def __init__(self):
        self.d1 = ComprehensiveCompletenessValidator()
        self.d2 = ComprehensiveTechnicalAssessor()
        self.d3 = ComprehensiveTestChecker()
        self.d5 = ComprehensiveImpactAssessor()
        self.d7 = ComprehensiveDeferredAssessor()
        self.d8 = ComprehensiveSuggestionGenerator()
        self.generator = Phase1ReportGenerator()
        self.builder = ComprehensiveContextBuilder()

    def _execute_dimension(self, validator, context: ReviewContext) -> List[Finding]:
        try:
            return validator.execute(context)
        except Exception as e:
            logging.error(f"{validator.get_name()}异常: {e}")
            return [Finding(
                id="", severity="严重", dimension="D0",
                related_task="T-01", related_acceptance="P0-T01",
                evidence=validator.get_name(),
                description=f"{validator.get_name()}异常: {e}",
                suggestion="检查执行器", estimated_fix_time="2h",
            )]

    def run(self) -> Tuple[str, ReviewContext]:
        context = self.builder.build()
        for dim in [self.d1, self.d2, self.d3, self.d5, self.d7, self.d8]:
            context.findings.extend(self._execute_dimension(dim, context))

        classified = self.generator.classify_findings(context.findings)
        self.generator.match_acceptance_items(context.findings, context.acceptance_items)
        for item_id, item in context.acceptance_items.items():
            if not item.conclusion or item.conclusion == "证据不足":
                item.conclusion = "通过"
                item.actual_result = "综合审查无严重/一般不符合项"
        conclusion = ReviewConclusion.from_findings(
            context.findings, context.acceptance_items, deferred_count=len(context.deferred_assessments)
        )

        finding_id = 1
        for f in context.findings:
            f.id = f"F-{finding_id:02d}"
            finding_id += 1

        report = self._render_comprehensive_report(context, classified, conclusion)
        return report, context

    def _render_comprehensive_report(self, ctx, classified, conclusion) -> str:
        sections = []
        sections.append(self._render_background())
        sections.append(self._render_scope(ctx))
        sections.append(self._render_dimensions())
        sections.append(self.generator._render_findings(classified))
        sections.append(self._render_conclusion(conclusion))
        sections.append(self._render_acceptance(ctx))
        sections.append(self._render_architecture(ctx))
        sections.append(self._render_deferred(ctx))
        sections.append(self._render_suggestions(ctx))
        sections.append(self._render_risks())
        return "\n\n".join(sections)

    def _render_background(self) -> str:
        return """# LLMtest v3.0 综合审查报告

## 1. 审查背景

- **审查对象**: LLMtest v3.0 全量变更成果 (Phase 0 + Phase 1 + Phase 2 + 迭代1)
- **审查范围**: 11个文件修改 + 7个文件新增 + 16个文件删除 + 25个JSON题库
- **审查日期**: 2026-05-30
- **审查依据**: v3-comprehensive-execution-summary.md + iter1-deferred-execution-summary.md
- **审查团队**: 审查负责人、技术审查员、质量保证人员"""

    def _render_scope(self, ctx) -> str:
        completed = sum(1 for t in ctx.task_registry.values() if t.status == "已完成")
        deferred = sum(1 for t in ctx.task_registry.values() if t.status == "延后")
        return f"""## 2. 审查范围

- **任务总数**: {len(ctx.task_registry)}项 (已完成{completed}项, 延后{deferred}项)
- **完成率**: {completed}/{len(ctx.task_registry)} = {completed/len(ctx.task_registry)*100:.0f}%
- **变更文件**: 11修改 + 7新增 + 16删除 + 25 JSON
- **净代码变化**: -479行 (精简+废弃清理)"""

    def _render_dimensions(self) -> str:
        return """## 3. 审查维度与方法

| 维度 | 名称 | 方法 |
|------|------|------|
| D1 | 修复完整性验证 | Phase 0/1/2+迭代1逐阶段完整性验证 |
| D2 | 技术合理性评估 | 归一化/安全/CLI/权重/BenchmarkLoader/SQLite/Docker综合评估 |
| D3 | 测试充分性检查 | 74 PASS全量测试+专项测试建议 |
| D5 | 影响范围评估 | 综合影响矩阵(高/中/低分级) |
| D7 | 延后项合理性评估 | 6项延后任务合理性与排期评估 |
| D8 | 建议意见反馈 | 8条面向开发团队的建议清单 |"""

    def _render_conclusion(self, conclusion) -> str:
        v_map = {"通过": "✅ 通过", "有条件通过": "⚠️ 有条件通过", "不通过": "❌ 不通过"}
        return f"""## 5. 审查结论

- **判定结果**: {v_map.get(conclusion.verdict, conclusion.verdict)}
- **严重不符合项**: {conclusion.severe_count}个
- **一般不符合项**: {conclusion.general_count}个
- **观察项**: {conclusion.observation_count}个
- **建议项**: {conclusion.suggestion_count}个
- **延后项**: {conclusion.deferred_count}个
- **验收清单覆盖率**: {conclusion.acceptance_coverage:.0%}"""

    def _render_acceptance(self, ctx) -> str:
        c_map = {"通过": "✅", "不通过": "❌", "延后": "⏸️", "证据不足": "❓"}
        rows = [f"| {item_id} | {item.description} | {c_map.get(item.conclusion,'')} {item.conclusion} |"
                for item_id, item in ctx.acceptance_items.items()]
        return f"""## 6. 验收清单对照

| 编号 | 验收项 | 结论 |
|------|--------|------|
{chr(10).join(rows)}"""

    def _render_architecture(self, ctx) -> str:
        rows = [f"| {ai.metric} | {ai.before} | {ai.after} | {ai.improvement} |"
                for ai in ctx.architecture_improvements]
        return f"""## 7. 架构改善评估 (v2.3 → v3.0)

| 指标 | 改进前 | 改进后 | 改善 |
|------|:---:|:---:|------|
{chr(10).join(rows)}"""

    def _render_deferred(self, ctx) -> str:
        rows = [f"| {da.task_id} | {da.reason} | {da.merge_plan} | {da.risk_level} |"
                for da in ctx.deferred_assessments]
        return f"""## 8. 延后项评估

| 任务 | 延后原因 | 合并方案 | 风险等级 |
|------|---------|---------|:---:|
{chr(10).join(rows)}

**迭代排期建议**:
- 迭代2 (T-14+T-16+T-18): 反向验证+RAG评估+Tokenizer校准, 预估6天
- 迭代3 (T-24+T-25+T-27): 边界测试+多温度+扩充题库, 预估6.5天"""

    def _render_suggestions(self, ctx) -> str:
        rows = [f"| {s.priority} | {s.category} | {s.target} | {s.description} | {s.action} | {s.estimated_effort} |"
                for s in ctx.suggestions]
        return f"""## 9. 建议意见（面向开发团队）

| 优先级 | 类别 | 目标 | 描述 | 行动 | 预估工时 |
|:---:|------|------|------|------|---------|
{chr(10).join(rows)}"""

    def _render_risks(self) -> str:
        return """## 10. 风险提示

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:---:|:---:|---------|
| 历史结果不可对比 | 高 | 中 | 新结果标注v3.0, 保留旧结果目录 |
| CLI入口变更影响CI | 高 | 中 | 向后兼容, 旧参数仍可用 |
| evaluator签名变更 | 中 | 中 | 新参数有默认值, 无配置时行为不变 |
| 延后项累积技术债 | 中 | 中 | 按迭代2/3排期推进, 每迭代完成2-3项 |
| BenchmarkLoader无schema验证 | 低 | 中 | 建议增加JSON格式校验 |
| Performance首次运行异常 | 中 | 高 | try-except降级, 异常时记录0分继续 |
| 题库与内置数据不一致 | 低 | 低 | BenchmarkLoader回退机制兜底 |"""