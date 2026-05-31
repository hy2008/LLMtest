from typing import Dict, List
from review.models import (
    Finding, ReviewContext, ReviewConclusion, AcceptanceItem,
)


class Phase1ReportGenerator:
    def classify_findings(self, findings: List[Finding]) -> Dict[str, List[Finding]]:
        result = {"严重": [], "一般": [], "观察": [], "建议": []}
        for f in findings:
            if f.severity in result:
                result[f.severity].append(f)
            else:
                result["观察"].append(f)
        return result

    def determine_conclusion(self, findings: List[Finding], acceptance_items: Dict[str, AcceptanceItem]) -> ReviewConclusion:
        return ReviewConclusion.from_findings(findings, acceptance_items, deferred_count=7)

    def match_acceptance_items(self, findings: List[Finding], acceptance_items: Dict[str, AcceptanceItem]) -> Dict[str, str]:
        task_findings: Dict[str, List[Finding]] = {}
        for f in findings:
            task_findings.setdefault(f.related_task, []).append(f)
            task_findings.setdefault(f.related_acceptance, []).append(f)

        results = {}
        for item_id, item in acceptance_items.items():
            item_findings = task_findings.get(item_id, [])
            if not item_findings:
                item.conclusion = "证据不足"
                item.actual_result = "无对应审查发现"
            elif any(f.severity == "严重" for f in item_findings):
                item.conclusion = "不通过"
                item.actual_result = f"发现严重不符合项"
            else:
                item.conclusion = "通过"
                obs = sum(1 for f in item_findings if f.severity in ("观察", "建议"))
                gen = sum(1 for f in item_findings if f.severity == "一般")
                item.actual_result = f"观察项{obs}个, 一般项{gen}个"
            results[item_id] = item.conclusion
        return results

    def generate(self, context: ReviewContext) -> str:
        classified = self.classify_findings(context.findings)
        self.match_acceptance_items(context.findings, context.acceptance_items)
        conclusion = self.determine_conclusion(context.findings, context.acceptance_items)

        finding_id = 1
        for f in context.findings:
            f.id = f"F-{finding_id:02d}"
            finding_id += 1

        sections = []
        sections.append(self._render_background())
        sections.append(self._render_scope(context))
        sections.append(self._render_dimensions())
        sections.append(self._render_findings(classified))
        sections.append(self._render_conclusion(conclusion))
        sections.append(self._render_acceptance(context))
        sections.append(self._render_impact_matrix(context))
        sections.append(self._render_deferred(context))
        sections.append(self._render_architecture(context))
        sections.append(self._render_suggestions(context))

        return "\n\n".join(sections)

    def _render_background(self) -> str:
        return """# Phase 1 审查报告

## 1. 审查背景

- **审查对象**: LLMtest v3.0 Phase 1 (T-09至T-19) 变更成果
- **审查范围**: 6个文件修改 + 4个文件新增, 涉及CLI入口、评估器、报告引擎、题库架构
- **审查日期**: 2026-05-29
- **审查依据**: Phase1执行总结(phase1-execution-summary.md)及综合改进计划
- **审查团队**: 审查负责人、技术审查员、质量保证人员"""

    def _render_scope(self, ctx: ReviewContext) -> str:
        rows = []
        for tid, task in ctx.task_registry.items():
            icon = "✅" if task.status == "已完成" else "⏸️" if task.status == "延后" else "❌"
            rows.append(f"| {tid} | {task.priority} | {task.change_file or '—'} | {icon} {task.status} |")
        return f"""## 2. 审查范围

| 编号 | 优先级 | 变更文件 | 状态 |
|------|--------|---------|------|
{chr(10).join(rows)}"""

    def _render_dimensions(self) -> str:
        return """## 3. 审查维度与方法

| 维度 | 名称 | 方法 |
|------|------|------|
| D1 | 修复完整性验证 | 逐任务验证T-09/T-10/T-12/T-17修复完整性+延后项确认 |
| D2 | 技术合理性评估 | 评估子命令体系/权重注入/报告引擎/BenchmarkLoader设计 |
| D3 | 测试充分性检查 | 验证测试覆盖率+专项测试建议 |
| D5 | 影响范围评估 | 构建变更文件×受影响模块影响矩阵 |
| D7 | 延后项合理性评估 | 评估7项延后任务的合理性和风险 |
| D8 | 建议意见反馈 | 生成面向开发团队的建议清单 |"""

    def _render_findings(self, classified: Dict[str, List[Finding]]) -> str:
        sections = ["## 4. 审查发现"]
        for severity in ["严重", "一般", "观察", "建议"]:
            items = classified.get(severity, [])
            header_map = {"严重": "4.1 严重不符合项", "一般": "4.2 一般不符合项",
                          "观察": "4.3 观察项", "建议": "4.4 最佳实践建议"}
            sections.append(f"\n### {header_map[severity]}")
            if not items:
                sections.append("无")
            else:
                for f in items:
                    s_text = f"\n   - **建议措施**: {f.suggestion}" if f.suggestion else ""
                    t_text = f"\n   - **预计修复时间**: {f.estimated_fix_time}" if f.estimated_fix_time else ""
                    sections.append(f"- **{f.id}** [{f.dimension}/{f.related_task}] {f.description}\n   - **证据**: {f.evidence}{s_text}{t_text}")
        return "\n".join(sections)

    def _render_conclusion(self, conclusion: ReviewConclusion) -> str:
        verdict_map = {"通过": "✅ 通过", "有条件通过": "⚠️ 有条件通过", "不通过": "❌ 不通过"}
        return f"""## 5. 审查结论

- **判定结果**: {verdict_map.get(conclusion.verdict, conclusion.verdict)}
- **严重不符合项**: {conclusion.severe_count}个
- **一般不符合项**: {conclusion.general_count}个
- **观察项**: {conclusion.observation_count}个
- **建议项**: {conclusion.suggestion_count}个
- **延后项**: {conclusion.deferred_count}个
- **验收清单覆盖率**: {conclusion.acceptance_coverage:.0%}"""

    def _render_acceptance(self, ctx: ReviewContext) -> str:
        rows = []
        c_map = {"通过": "✅ 通过", "不通过": "❌ 不通过", "延后": "⏸️ 延后", "证据不足": "❓ 证据不足"}
        for item_id, item in ctx.acceptance_items.items():
            c = c_map.get(item.conclusion, item.conclusion)
            rows.append(f"| {item_id} | {item.description} | {item.actual_result or '—'} | {c} |")
        return f"""## 6. 验收清单对照

| 编号 | 验收项 | 实际结果 | 结论 |
|------|--------|---------|------|
{chr(10).join(rows)}"""

    def _render_impact_matrix(self, ctx: ReviewContext) -> str:
        if not ctx.impact_matrix or not ctx.impact_matrix.entries:
            return "## 7. 变更影响矩阵\n\n无"
        icons = {"高": "🔴", "中": "🟡", "低": "🟢", "无": "⚪"}
        rows = [f"| {e.change_file} | {e.affected_module} | {icons.get(e.impact_level,'')} {e.impact_level} | {e.impact_description} |"
                for e in ctx.impact_matrix.entries]
        return f"""## 7. 变更影响矩阵

| 变更文件 | 受影响模块 | 影响等级 | 影响描述 |
|---------|-----------|:---:|---------|
{chr(10).join(rows)}"""

    def _render_deferred(self, ctx: ReviewContext) -> str:
        rows = []
        for da in ctx.deferred_assessments:
            icon = "✅" if da.is_reasonable else "⚠️"
            rows.append(f"| {da.task_id} | {da.reason} | {da.merge_plan} | {icon} {'合理' if da.is_reasonable else '存疑'} | {da.risk_level} |")
        return f"""## 8. 延后项评估

| 任务 | 延后原因 | 合并方案 | 合理性 | 风险等级 |
|------|---------|---------|:---:|:---:|
{chr(10).join(rows)}"""

    def _render_architecture(self, ctx: ReviewContext) -> str:
        rows = [f"| {ai.metric} | {ai.before} | {ai.after} | {ai.improvement} |"
                for ai in ctx.architecture_improvements]
        return f"""## 9. 架构改善评估

| 指标 | 改进前 | 改进后 | 改善 |
|------|:---:|:---:|------|
{chr(10).join(rows)}"""

    def _render_suggestions(self, ctx: ReviewContext) -> str:
        rows = [f"| {s.priority} | {s.category} | {s.target} | {s.description} | {s.action} | {s.estimated_effort} |"
                for s in ctx.suggestions]
        return f"""## 10. 建议意见（面向开发团队）

| 优先级 | 类别 | 目标 | 描述 | 行动 | 预估工时 |
|:---:|------|------|------|------|---------|
{chr(10).join(rows)}

### 风险提示

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:---:|:---:|---------|
| CLI入口变更影响CI脚本 | 高 | 中 | 向后兼容模式保留, 旧参数仍可用 |
| evaluator签名变更影响外部调用 | 中 | 中 | 新参数有默认值, 无配置时行为不变 |
| 延后项累积导致技术债 | 中 | 中 | 按优先级逐步推进, 每迭代完成2-3项 |
| BenchmarkLoader无schema验证 | 低 | 中 | 建议增加JSON格式校验 |"""