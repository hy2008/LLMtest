import re
from typing import List

from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class CompletenessValidator(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D1:修复完整性验证"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._check_t01(context))
        findings.extend(self._check_t02(context))
        findings.extend(self._check_t03(context))
        findings.extend(self._check_t04(context))
        findings.extend(self._check_t05(context))
        findings.extend(self._check_t06(context))
        findings.extend(self._check_t07(context))
        findings.extend(self._check_t08(context))
        return findings

    def _check_t01(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("utils/score_engine.py", "")
        has_norm = "c.score / c.max_score * 100" in content or "score / c.max_score * 100" in content
        has_zero_guard = "c.max_score > 0" in content or "max_score > 0" in content
        no_old_formula = "c.score * c.weight" not in content.replace(
            "(c.score / c.max_score * 100 if c.max_score > 0 else 0) * c.weight", ""
        )

        if has_norm and has_zero_guard:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-01",
                related_acceptance="T-01",
                evidence="utils/score_engine.py:104-106",
                description="T-01归一化公式修复完整: 使用(score/max_score*100)*weight，含max_score>0零值保护",
            ))
        else:
            desc = []
            if not has_norm:
                desc.append("归一化公式未找到")
            if not has_zero_guard:
                desc.append("零值保护缺失")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-01",
                related_acceptance="T-01",
                evidence="utils/score_engine.py",
                description=f"T-01归一化公式修复不完整: {', '.join(desc)}",
                suggestion="确认add_dimension_score()使用(score/max_score*100)*weight并含max_score>0保护",
                estimated_fix_time="0.5h",
            ))

        if not no_old_formula:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-01",
                related_acceptance="T-01",
                evidence="utils/score_engine.py",
                description="T-01发现旧公式score*weight残留",
                suggestion="移除所有旧公式调用",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_t02(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/reasoning.py", "")
        has_safe_func = "_safe_parse_numeric" in content
        has_ast = "ast.literal_eval" in content

        eval_pattern = re.compile(r'(?<!def )(?<![_\w])eval\s*\(')
        code_lines = content.split("\n")
        bare_eval_lines = []
        for i, line in enumerate(code_lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if "docstring" in stripped.lower() or "避免 eval()" in stripped or "eval()" in stripped and "=" not in stripped.split("eval")[0]:
                continue
            if eval_pattern.search(line) and "ast.literal_eval" not in line:
                bare_eval_lines.append(i)

        if has_safe_func and has_ast and len(bare_eval_lines) == 0:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py:16-25",
                description="T-02 eval()消除完整: _safe_parse_numeric()存在, ast.literal_eval替换完成, 无裸eval()残留",
            ))
        else:
            desc = []
            if not has_safe_func:
                desc.append("_safe_parse_numeric函数缺失")
            if not has_ast:
                desc.append("ast.literal_eval未使用")
            if bare_eval_lines:
                desc.append(f"裸eval()残留于行{bare_eval_lines}")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-02",
                related_acceptance="T-02",
                evidence="evaluators/reasoning.py",
                description=f"T-02 eval()消除不完整: {', '.join(desc)}",
                suggestion="确保所有eval()替换为_safe_parse_numeric()",
                estimated_fix_time="1h",
            ))
        return findings

    def _check_t03(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/coding.py", "")
        has_timeout_15 = "timeout=15" in content

        if has_timeout_15:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-03",
                related_acceptance="T-03",
                evidence="evaluators/coding.py:1279",
                description="T-03沙箱超时延长完整: timeout=15",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-03",
                related_acceptance="T-03",
                evidence="evaluators/coding.py",
                description="T-03未找到timeout=15",
                suggestion="确认subprocess.run(timeout=15)存在",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_t04(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/performance.py", "")
        has_temperature = "temperature" in content
        has_try_except = "try:" in content and "except" in content

        if has_temperature and has_try_except:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-04",
                related_acceptance="T-04",
                evidence="evaluators/performance.py",
                description="T-04 PerformanceEvaluator完善: 含temperature参数和try-except降级",
            ))
        else:
            desc = []
            if not has_temperature:
                desc.append("temperature参数缺失")
            if not has_try_except:
                desc.append("try-except降级缺失")
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-04",
                related_acceptance="T-04",
                evidence="evaluators/performance.py",
                description=f"T-04 PerformanceEvaluator不完整: {', '.join(desc)}",
                suggestion="补充evaluate()签名参数和降级机制",
                estimated_fix_time="1h",
            ))
        return findings

    def _check_t05(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("evaluators/agent.py", "")
        has_flag = "include_browser_automation = False" in content
        has_gate = 'getattr(self, "include_browser_automation", False)' in content

        if has_flag and has_gate:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-05",
                related_acceptance="T-05",
                evidence="evaluators/agent.py:986,1035",
                description="T-05浏览器自动化降级完整: 默认False+门控条件",
            ))
        else:
            desc = []
            if not has_flag:
                desc.append("include_browser_automation=False缺失")
            if not has_gate:
                desc.append("门控条件缺失")
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-05",
                related_acceptance="T-05",
                evidence="evaluators/agent.py",
                description=f"T-05浏览器降级不完整: {', '.join(desc)}",
                suggestion="添加include_browser_automation属性和门控条件",
                estimated_fix_time="1h",
            ))
        return findings

    def _check_t06(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        task = ctx.task_registry.get("T-06")
        if task and task.status == "延后":
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-06",
                related_acceptance="T-06",
                evidence="task_registry[T-06].status",
                description="T-06确认延至Phase1, 延后原因: 与JSON外置合并避免二次修改",
            ))
        else:
            findings.append(Finding(
                id="", severity="一般", dimension="D1", related_task="T-06",
                related_acceptance="T-06",
                evidence="task_registry[T-06]",
                description="T-06延后状态未确认",
                suggestion="确认T-06标记为延后并说明原因",
                estimated_fix_time="0.5h",
            ))
        return findings

    def _check_t07(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("config.yaml", "")
        has_cw = "category_weights" in content
        has_profiles = "profiles" in content
        has_modes = "eval_modes" in content
        has_openclaw = "openclaw" in content
        has_hermes = "hermes" in content

        if has_cw and has_profiles and has_modes and has_openclaw and has_hermes:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-07",
                related_acceptance="T-07",
                evidence="config.yaml",
                description="T-07 config.yaml重构完整: 含category_weights/profiles(含openclaw,hermes)/eval_modes",
            ))
        else:
            missing = []
            if not has_cw:
                missing.append("category_weights")
            if not has_profiles:
                missing.append("profiles")
            if not has_modes:
                missing.append("eval_modes")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-07",
                related_acceptance="T-07",
                evidence="config.yaml",
                description=f"T-07 config.yaml配置段缺失: {', '.join(missing)}",
                suggestion="补充缺失配置段",
                estimated_fix_time="1h",
            ))
        return findings

    def _check_t08(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("utils/config.py", "")
        has_cw_dc = "CategoryWeightsConfig" in content
        has_profile_dc = "ProfileConfig" in content
        has_mode_dc = "EvalModeConfig" in content
        has_config_fields = "category_weights" in content and "profiles" in content and "eval_modes" in content

        if has_cw_dc and has_profile_dc and has_mode_dc and has_config_fields:
            findings.append(Finding(
                id="", severity="观察", dimension="D1", related_task="T-08",
                related_acceptance="T-08",
                evidence="utils/config.py",
                description="T-08 config.py同步完整: 3个dataclass+Config新增字段",
            ))
        else:
            missing = []
            if not has_cw_dc:
                missing.append("CategoryWeightsConfig")
            if not has_profile_dc:
                missing.append("ProfileConfig")
            if not has_mode_dc:
                missing.append("EvalModeConfig")
            findings.append(Finding(
                id="", severity="严重", dimension="D1", related_task="T-08",
                related_acceptance="T-08",
                evidence="utils/config.py",
                description=f"T-08 config.py数据类缺失: {', '.join(missing)}",
                suggestion="补充缺失的dataclass定义",
                estimated_fix_time="1h",
            ))
        return findings
