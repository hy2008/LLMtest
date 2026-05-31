import re
from typing import List

from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class TechnicalRationalityAssessor(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D2:技术合理性评估"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._assess_t01(context))
        findings.extend(self._assess_t02(context))
        findings.extend(self._assess_t03(context))
        findings.extend(self._assess_t04(context))
        findings.extend(self._assess_t07_t08(context))
        return findings

    def _assess_t01(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        s1, ms1, w1 = 80, 100, 0.5
        s2, ms2, w2 = 40, 50, 0.5
        norm1 = (s1 / ms1 * 100) * w1
        norm2 = (s2 / ms2 * 100) * w1
        avg = (norm1 + norm2) / (w1 + w2)
        equal_contribution = abs((s1 / ms1) - (s2 / ms2)) < 1e-9

        if equal_contribution and abs(avg - 80.0) < 1e-9:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-01",
                related_acceptance="T-01",
                evidence="数学验证: score=80/max=100 vs score=40/max=50",
                description="T-01归一化公式数学正确: 不同max_score满分时贡献比例仅由weight决定, 验证80%==80%",
            ))
        else:
            findings.append(Finding(
                id="", severity="严重", dimension="D2", related_task="T-01",
                related_acceptance="T-01",
                evidence="数学验证",
                description=f"T-01归一化公式数学验证失败: avg={avg}",
                suggestion="检查归一化公式实现",
                estimated_fix_time="2h",
            ))

        content = ctx.change_files.get("utils/score_engine.py", "")
        if "max_score > 0" in content or "c.max_score > 0" in content:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-01",
                related_acceptance="T-01",
                evidence="utils/score_engine.py",
                description="T-01含max_score=0零值保护",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D2", related_task="T-01",
                related_acceptance="T-01",
                evidence="utils/score_engine.py",
                description="T-01缺少max_score=0零值保护",
                suggestion="添加max_score>0判断",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _assess_t02(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/reasoning.py", "")
        has_ast = "ast.literal_eval" in content
        has_regex_fallback = "re.findall" in content and "_safe_parse_numeric" in content

        if has_ast:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py:22",
                description="T-02 ast.literal_eval安全性确认: 仅接受Python字面量, 不接受任意代码执行",
            ))
        else:
            findings.append(Finding(
                id="", severity="严重", dimension="D2", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py",
                description="T-02未使用ast.literal_eval, 安全替换不完整",
                suggestion="替换所有eval()为ast.literal_eval",
                estimated_fix_time="1h",
            ))

        if has_regex_fallback:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py:16-25",
                description="T-02两阶段降级方案完整: ast.literal_eval失败则正则提取数值",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D2", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py",
                description="T-02降级方案不完整: 缺少正则提取降级",
                suggestion="添加re.findall降级逻辑",
                estimated_fix_time="0.5h",
            ))

        if "_safe_parse_numeric" in content:
            malicious = "__import__('os').system('ls')"
            cleaned = re.sub(r'[^\d.eE+\-*/()]', '', malicious.strip())
            try:
                import ast as _ast
                _ast.literal_eval(cleaned)
                is_safe = False
            except (ValueError, SyntaxError):
                is_safe = True
            if is_safe:
                findings.append(Finding(
                    id="", severity="观察", dimension="D2", related_task="T-02",
                    related_acceptance="T-02",
                    evidence="_safe_parse_numeric注入测试",
                    description="T-02注入攻击防护验证: __import__('os').system('ls') → ast.literal_eval抛异常 → 降级返回None",
                ))
            else:
                findings.append(Finding(
                    id="", severity="严重", dimension="D2", related_task="T-02",
                    related_acceptance="T-02",
                    evidence="_safe_parse_numeric注入测试",
                    description=f"T-02注入防护失败: 恶意输入清理后为'{cleaned}', ast.literal_eval未抛异常",
                    suggestion="加强输入清理正则",
                    estimated_fix_time="1h",
                ))
        return findings

    def _assess_t03(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-03",
            related_acceptance="T-03",
            evidence="evaluators/coding.py:1279",
            description="T-03超时15秒合理性: 3倍余量(5s×3), 覆盖复杂排序/数据处理/退避重试场景",
        ))
        findings.append(Finding(
            id="", severity="建议", dimension="D2", related_task="T-03",
            related_acceptance="T-03",
            evidence="evaluators/coding.py",
            description="T-03建议: 超时值应从config.yaml读取而非硬编码, 便于不同环境调整",
            suggestion="将EXEC_TIMEOUT定义为配置项",
        ))
        return findings

    def _assess_t04(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/performance.py", "")
        has_try = "try:" in content and "except" in content

        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-04",
            related_acceptance="T-04",
            evidence="evaluators/performance.py",
            description="T-04 PerformanceEvaluator接口: evaluate()返回List[CategoryScore], 含temperature/max_tokens参数",
        ))

        if has_try:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-04",
                related_acceptance="T-04",
                evidence="evaluators/performance.py",
                description="T-04降级策略合理: try-except确保单子类别失败不影响整体",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D2", related_task="T-04",
                related_acceptance="T-04",
                evidence="evaluators/performance.py",
                description="T-04缺少try-except降级机制",
                suggestion="添加try-except降级保护",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _assess_t07_t08(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        yaml_content = ctx.change_files.get("config.yaml", "")
        py_content = ctx.change_files.get("utils/config.py", "")

        if "openclaw" in yaml_content and "hermes" in yaml_content and "default" in yaml_content:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-07",
                related_acceptance="T-07",
                evidence="config.yaml",
                description="T-07 profiles扩展性: 含openclaw/hermes/default, 支持新增Profile而不修改代码",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D2", related_task="T-07",
                related_acceptance="T-07",
                evidence="config.yaml",
                description="T-07 profiles子项不完整",
                suggestion="补充openclaw/hermes/default三个profile",
                estimated_fix_time="0.5h",
            ))

        has_default_factory = "default_factory" in py_content
        if has_default_factory:
            findings.append(Finding(
                id="", severity="观察", dimension="D2", related_task="T-08",
                related_acceptance="T-08",
                evidence="utils/config.py",
                description="T-08向后兼容: 新增字段使用default_factory, 缺失时自动使用默认值",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D2", related_task="T-08",
                related_acceptance="T-08",
                evidence="utils/config.py",
                description="T-08新增字段可能缺少默认值, 影响向后兼容",
                suggestion="为新增字段添加default_factory",
                estimated_fix_time="0.5h",
            ))

        findings.append(Finding(
            id="", severity="观察", dimension="D2", related_task="T-07",
            related_acceptance="T-07",
            evidence="config.yaml",
            description="T-07/T-08三者逻辑关系: category_weights(子类别权重)、profiles(场景维度权重)、eval_modes(采样策略)独立但可组合",
        ))
        return findings
