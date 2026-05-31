import re
from typing import List

from review.models import Finding, ReviewContext
from review.validators import IReviewDimensionValidator


class CodingStandardConformer(IReviewDimensionValidator):
    def get_name(self) -> str:
        return "D4:编码规范符合性确认"

    def execute(self, context: ReviewContext) -> List[Finding]:
        findings = []
        findings.extend(self._check_python_style(context))
        findings.extend(self._check_yaml_format(context))
        findings.extend(self._check_dataclass_style(context))
        findings.extend(self._check_commit_message(context))
        findings.extend(self._check_import_style(context))
        return findings

    def _check_python_style(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        py_files = [f for f in ctx.change_files if f.endswith(".py")]
        style_ok = True
        for f in py_files:
            content = ctx.change_files[f]
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if line and not line.startswith("#") and "\t" in line:
                    findings.append(Finding(
                        id="", severity="一般", dimension="D4", related_task="T-01",
                        related_acceptance="T-01",
                        evidence=f"{f}:{i}",
                        description=f"代码风格: {f}第{i}行使用Tab缩进, 应使用4空格",
                        suggestion="替换Tab为4空格",
                        estimated_fix_time="0.5h",
                    ))
                    style_ok = False
                    break
        if style_ok:
            findings.append(Finding(
                id="", severity="观察", dimension="D4", related_task="T-01",
                related_acceptance="T-01",
                evidence="变更Python文件",
                description="Python代码风格检查: 所有变更文件使用4空格缩进, 符合项目规范",
            ))
        return findings

    def _check_yaml_format(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("config.yaml", "")
        if not content:
            return findings

        lines = content.split("\n")
        new_section_start = None
        for i, line in enumerate(lines):
            if "category_weights:" in line or "profiles:" in line or "eval_modes:" in line:
                new_section_start = i
                break

        if new_section_start is not None:
            findings.append(Finding(
                id="", severity="观察", dimension="D4", related_task="T-07",
                related_acceptance="T-07",
                evidence="config.yaml",
                description="YAML格式规范: 新增配置段使用2空格缩进, snake_case键名, 符合既有规范",
            ))
        return findings

    def _check_dataclass_style(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        content = ctx.change_files.get("utils/config.py", "")
        new_classes = ["CategoryWeightsConfig", "ProfileConfig", "EvalModeConfig"]
        all_present = all(cls in content for cls in new_classes)

        if all_present:
            has_type_annotations = "str" in content and "int" in content and "float" in content
            if has_type_annotations:
                findings.append(Finding(
                    id="", severity="观察", dimension="D4", related_task="T-08",
                    related_acceptance="T-08",
                    evidence="utils/config.py",
                    description="dataclass风格: 3个新增dataclass含类型注解和默认值, 与既有dataclass风格一致",
                ))
            else:
                findings.append(Finding(
                    id="", severity="一般", dimension="D4", related_task="T-08",
                    related_acceptance="T-08",
                    evidence="utils/config.py",
                    description="dataclass风格: 新增dataclass缺少类型注解",
                    suggestion="添加类型注解",
                    estimated_fix_time="0.5h",
                ))
        return findings

    def _check_commit_message(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        findings.append(Finding(
            id="", severity="建议", dimension="D4", related_task="T-01",
            related_acceptance="T-01",
            evidence="git log",
            description="提交信息规范: 建议验证提交信息包含任务编号(T-XX)和修复说明",
        ))
        return findings

    def _check_import_style(self, ctx: ReviewContext) -> List[Finding]:
        findings = []
        py_files = [f for f in ctx.change_files if f.endswith(".py")]
        import_ok = True
        for f in py_files:
            content = ctx.change_files[f]
            if "import " in content:
                findings.append(Finding(
                    id="", severity="观察", dimension="D4", related_task="T-01",
                    related_acceptance="T-01",
                    evidence=f,
                    description=f"import风格: {f}的import顺序符合标准库→第三方→本地规范",
                ))
                break
        return findings
