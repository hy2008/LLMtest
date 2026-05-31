from typing import Dict, List

from review.models import Finding, ReviewContext, ReviewConclusion, AcceptanceItem


class ReviewReportGenerator:
    def classify_findings(self, findings: List[Finding]) -> Dict[str, List[Finding]]:
        result = {"严重": [], "一般": [], "观察": [], "建议": []}
        for f in findings:
            if f.severity in result:
                result[f.severity].append(f)
            else:
                result["观察"].append(f)
        return result

    def determine_conclusion(self, findings: List[Finding], acceptance_items: Dict[str, AcceptanceItem]) -> ReviewConclusion:
        return ReviewConclusion.from_findings(findings, acceptance_items)

    def match_acceptance_items(self, findings: List[Finding], acceptance_items: Dict[str, AcceptanceItem]) -> Dict[str, str]:
        task_findings: Dict[str, List[Finding]] = {}
        for f in findings:
            task_findings.setdefault(f.related_task, []).append(f)

        results = {}
        for item_id, item in acceptance_items.items():
            item_findings = task_findings.get(item_id, [])
            if not item_findings:
                item.conclusion = "证据不足"
                item.actual_result = "无对应审查发现"
            elif any(f.severity == "严重" for f in item_findings):
                item.conclusion = "不通过"
                item.actual_result = f"发现{sum(1 for f in item_findings if f.severity=='严重')}个严重不符合项"
            elif item_id == "T-06":
                item.conclusion = "延后"
                item.actual_result = "延至Phase1与JSON外置合并"
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
        sections.append(self._render_background_section())
        sections.append(self._render_scope_section(context))
        sections.append(self._render_dimensions_section())
        sections.append(self._render_findings_section(classified))
        sections.append(self._render_conclusion_section(conclusion))
        sections.append(self._render_acceptance_section(context))
        sections.append(self._render_impact_matrix_section(context))
        sections.append(self._render_risk_section(context))

        return "\n\n".join(sections)

    def _render_background_section(self) -> str:
        return """# Phase 0 审查报告

## 1. 审查背景

- **审查对象**: LLMtest v3.0 Phase 0 (T-01至T-08) 变更成果
- **审查范围**: 5个文件修改 + 0个文件删除, 涉及评分引擎、评估器、配置系统
- **审查日期**: 2026-05-29
- **审查依据**: 综合改进计划(2026-05-29-llmtest-integrated-plan.md)及Phase0执行总结(2026-05-29-phase0-summary.md)
- **审查团队**: 审查负责人、技术审查员、质量保证人员"""

    def _render_scope_section(self, ctx: ReviewContext) -> str:
        task_rows = []
        for tid, task in ctx.task_registry.items():
            status_icon = "✅" if task.status == "已完成" else "⏸️" if task.status == "延后" else "❌"
            task_rows.append(f"| {tid} | {task.priority} | {task.change_file or '—'} | {status_icon} {task.status} |")

        return f"""## 2. 审查范围

### 2.1 任务清单

| 编号 | 优先级 | 变更文件 | 状态 |
|------|--------|---------|------|
{chr(10).join(task_rows)}

### 2.2 变更文件清单

| 序号 | 文件路径 | 涉及任务 |
|------|---------|---------|
| 1 | utils/score_engine.py | T-01 |
| 2 | evaluators/reasoning.py | T-02 |
| 3 | evaluators/coding.py | T-03 |
| 4 | evaluators/performance.py | T-04 |
| 5 | evaluators/agent.py | T-05 |
| 6 | config.yaml | T-07 |
| 7 | utils/config.py | T-08 |"""

    def _render_dimensions_section(self) -> str:
        return """## 3. 审查维度与方法

| 维度 | 名称 | 方法 |
|------|------|------|
| D1 | 修复完整性验证 | 逐任务验证修复措施是否完整解决报告问题 |
| D2 | 技术合理性评估 | 评估修复方案数学正确性、安全性、兼容性 |
| D3 | 测试充分性检查 | 验证测试覆盖率和安全专项测试 |
| D4 | 编码规范符合性确认 | 检查代码风格、配置格式、dataclass风格 |
| D5 | 影响范围评估 | 构建变更文件×受影响模块影响矩阵 |
| D6 | 报告规范性检查 | 验证报告结构、发现分类、证据可追溯 |"""

    def _render_findings_section(self, classified: Dict[str, List[Finding]]) -> str:
        sections = ["## 4. 审查发现"]

        for severity in ["严重", "一般", "观察", "建议"]:
            items = classified.get(severity, [])
            header_map = {"严重": "4.1 严重不符合项", "一般": "4.2 一般不符合项", "观察": "4.3 观察项", "建议": "4.4 最佳实践建议"}
            sections.append(f"\n### {header_map[severity]}")

            if not items:
                sections.append("无")
            else:
                for f in items:
                    suggestion_text = f"\n   - **建议措施**: {f.suggestion}" if f.suggestion else ""
                    fix_time_text = f"\n   - **预计修复时间**: {f.estimated_fix_time}" if f.estimated_fix_time else ""
                    sections.append(f"- **{f.id}** [{f.dimension}/{f.related_task}] {f.description}\n   - **证据**: {f.evidence}{suggestion_text}{fix_time_text}")

        return "\n".join(sections)

    def _render_conclusion_section(self, conclusion: ReviewConclusion) -> str:
        verdict_map = {"通过": "✅ 通过", "有条件通过": "⚠️ 有条件通过", "不通过": "❌ 不通过"}
        verdict_display = verdict_map.get(conclusion.verdict, conclusion.verdict)

        return f"""## 5. 审查结论

- **判定结果**: {verdict_display}
- **严重不符合项**: {conclusion.severe_count}个
- **一般不符合项**: {conclusion.general_count}个
- **观察项**: {conclusion.observation_count}个
- **建议项**: {conclusion.suggestion_count}个
- **延后项**: {conclusion.deferred_count}个 (T-06延至Phase1)
- **验收清单覆盖率**: {conclusion.acceptance_coverage:.0%}"""

    def _render_acceptance_section(self, ctx: ReviewContext) -> str:
        rows = []
        for item_id, item in ctx.acceptance_items.items():
            conclusion_map = {"通过": "✅ 通过", "不通过": "❌ 不通过", "延后": "⏸️ 延后", "证据不足": "❓ 证据不足"}
            c = conclusion_map.get(item.conclusion, item.conclusion)
            rows.append(f"| {item_id} | {item.description} | {item.actual_result or '—'} | {c} |")

        return f"""## 6. 验收清单对照

| 编号 | 验收项 | 实际结果 | 结论 |
|------|--------|---------|------|
{chr(10).join(rows)}"""

    def _render_impact_matrix_section(self, ctx: ReviewContext) -> str:
        if not ctx.impact_matrix or not ctx.impact_matrix.entries:
            return "## 7. 变更影响矩阵\n\n无影响矩阵数据"

        level_icons = {"高": "🔴", "中": "🟡", "低": "🟢", "无": "⚪"}
        rows = []
        for e in ctx.impact_matrix.entries:
            icon = level_icons.get(e.impact_level, "")
            rows.append(f"| {e.change_file} | {e.affected_module} | {icon} {e.impact_level} | {e.impact_description} |")

        return f"""## 7. 变更影响矩阵

| 变更文件 | 受影响模块 | 影响等级 | 影响描述 |
|---------|-----------|:---:|---------|
{chr(10).join(rows)}"""

    def _render_risk_section(self, ctx: ReviewContext) -> str:
        return """## 8. 风险提示与建议

### 8.1 遗留风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:---:|:---:|---------|
| 历史评估结果不可直接对比 | 高 | 中 | 新结果标注v3.0, 保留旧结果目录 |
| Performance首次运行异常 | 中 | 高 | try-except降级, 异常时记录0分继续 |
| T-06子类别合并延后 | — | 低 | 延至Phase1与JSON外置合并执行 |

### 8.2 后续行动

1. Phase 1执行: T-09统一CLI入口 → T-10评估器权重适配 → T-11清理废弃脚本
2. T-06执行: 与P1-1 JSON外置合并, 一次完成子类别合并和数据外置
3. 回归测试: Phase 0变更后执行全量回归, 确认评分结果在预期范围"""
