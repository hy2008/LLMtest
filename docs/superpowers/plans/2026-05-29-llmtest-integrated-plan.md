# LLMtest v3.0 综合改进计划

> **文档性质**: 供审查团队评审的完整改进计划，综合了《评估设计五维度审查报告》19项改进建议与《改进规范》15个架构Task。
> **项目初衷**: Mac Studio M4 Max 128GB + LM Studio 部署本地大语言模型 → 筛选适合 OpenClaw/Hermes 的模型
> **当前基线**: v2.3 Phase 3 | 加权总分 29.5% | 全量评估耗时 ~32min | 30个子类别 | 11个run_*.py脚本
> **目标**: v3.0 | 科学评分 + 场景化评估 + 统一架构 | quick模式5min | full模式30min

---

## 一、两份文档的改进项交叉映射

五维度审查报告中 19 项改进与改进规范中 15 个 Task 的对应关系：

| 审查项 | 维度 | 优先级 | 映射到规范Task | 覆盖状态 |
|--------|------|:---:|------|:---:|
| **S-1** 修复聚合归一化 | 科学性 | P0 | ⚠️ 未覆盖 | **需新增** |
| **S-2** 对齐外部基准(HumanEval/MATH) | 科学性 | P1 | ⚠️ 未覆盖 | **需新增** |
| **S-3** 增加反向验证 | 科学性 | P1 | ⚠️ 未覆盖 | **需新增** |
| S-4 扩充题库(≥5用例/子类别) | 科学性 | P2 | P1-1 JSON外置 | 部分覆盖 |
| S-5 消除eval()改用ast | 科学性 | P1 | ⚠️ 未覆盖 | **需新增** |
| **R-1** Performance维度纳入 | 合理性 | P0 | P2-4 性能细化 | 部分覆盖(侧重不同) |
| R-2 场景化权重(OpenClaw/Hermes) | 合理性 | P0 | P0-1 profiles段 | ✅ 已覆盖 |
| R-3 剔除浏览器自动化 | 合理性 | P1 | ⚠️ 未覆盖 | **需新增** |
| R-4 调整权重匹配业务 | 合理性 | P1 | P0-1 category_weights | ✅ 已覆盖 |
| R-5 端到端验证(代码可运行/工具结果) | 合理性 | P2 | P1-4 E2EEvaluator | ✅ 已覆盖 |
| C-1 扩充语言覆盖(JS/Shell/SQL) | 完整性 | P1 | ⚠️ 未覆盖 | **需新增** |
| C-2 增加RAG评估 | 完整性 | P1 | ⚠️ 未覆盖 | **需新增** |
| C-3 边界条件测试 | 完整性 | P2 | ⚠️ 未覆盖 | **需新增** |
| C-4 实现采样模式(samples生效) | 完整性 | P2 | P0-1 eval_modes段 | ✅ 已覆盖 |
| C-5 多温度评估(temp=0+0.7) | 完整性 | P2 | ⚠️ 未覆盖 | **需新增** |
| F-1 分级评估quick/standard/full | 可行性 | P0 | P0-1/P0-2 | ✅ 已覆盖 |
| F-2 加固代码沙箱 | 可行性 | P1 | P2-2 SandboxExecutor | ✅ 已覆盖 |
| F-3 延长执行超时(5s→15s) | 可行性 | P1 | ⚠️ 未覆盖 | **需新增** |
| F-4 统一入口脚本 | 可行性 | P2 | P0-2 子命令体系 | ✅ 已覆盖 |
| F-5 配置外置 | 可行性 | P2 | P0-1/P1-1 | ✅ 已覆盖 |
| **P-1** 剔除浏览器自动化 | 精简化 | P0 | ⚠️ 未覆盖 | **需新增** |
| P-2 合并重叠子类别 | 精简化 | P1 | ⚠️ 未覆盖 | **需新增** |
| P-3 统一多步评估 | 精简化 | P1 | ⚠️ 未覆盖 | **需新增** |
| P-4 评分策略分层文档化 | 精简化 | P2 | ⚠️ 未覆盖 | **需新增** |
| P-5 快速评估模式 | 精简化 | P0 | P0-1 eval_modes | ✅ 已覆盖 |

**统计**: 19项中 10项已覆盖、9项未覆盖需要新增。新增项集中在：**评分数学缺陷修复**(S-1/S-5)、**外部基准对齐**(S-2/S-3)、**题库扩展**(C-1/C-2/C-3/C-5)、**子类别精简**(P-1/P-2/P-3)、**安全超时**(F-3)。

---

## 二、统一实施路线图

```
Phase 0（本次执行）─ 关键Bug修复 + 配置重构
  ├── T-01 S-1: 修复聚合归一化公式 (score/max_score × weight)
  ├── T-02 S-5: 消除eval()风险 (改用ast.literal_eval)
  ├── T-03 F-3: 延长沙箱执行超时 (5s→15s)
  ├── T-04 R-1: 编写PerformanceEvaluator评估逻辑
  ├── T-05 P-1/R-3: 剔除/降级浏览器自动化子类别
  ├── T-06 P-2: 合并重叠子类别 (代码生成+实际开发, 阅读+知识)
  ├── T-07 P0-1: 重构config.yaml (profiles/category_weights/eval_modes)
  └── T-08 P0-4: 同步更新config.py配置类

Phase 1（后续执行）─ 科学性与业务对齐增强
  ├── T-09 P0-2: 统一CLI入口 (子命令体系)
  ├── T-10 P0-5: 评估器权重适配
  ├── T-11 P0-6: 清理废弃脚本
  ├── T-12 P0-3: 统一报告引擎
  ├── T-13 S-2: 对齐HumanEval/MATH基准
  ├── T-14 S-3: 增加反向验证评分
  ├── T-15 C-1: 扩充语言覆盖 (JS/Shell/SQL)
  ├── T-16 C-2: 增加RAG评估子类别
  ├── T-17 P1-1: 测试用例JSON外置
  ├── T-18 P1-5: Tokenizer自适应校准
  └── T-19 P1-2: 统计显著性支持

Phase 2（计划执行）─ 覆盖面扩展与基础设施
  ├── T-20 P2-1: SQLite断点续传
  ├── T-21 P2-2: 沙箱安全加固
  ├── T-22 P2-3: Docker化部署
  ├── T-23 P2-4: 性能测试细化(冷/热/唤醒)
  ├── T-24 C-3: 边界条件测试
  ├── T-25 C-5: 多温度评估
  ├── T-26 P-4: 评分策略分层文档化
  └── T-27 S-4: 扩充题库至≥5用例/子类别
```

---

## 三、Phase 0 详细执行方案（本次执行）

### T-01 [S-1] 修复聚合归一化公式 ⭐ P0关键

**问题**: `score_engine.py` 的 `add_dimension_score()` 使用 `score * weight` 聚合原始分（非百分比），导致 max_score 大的子类别（实际开发场景 110分）远大于 max_score 小的子类别（API接口开发 55分），权重体系名存实亡。

**当前公式**:
```python
weighted = sum(s * w for s, w in zip(scores, weights))
```

**修复后公式**:
```python
weighted = sum((s / ms) * 100 * w for s, ms, w in zip(scores, max_scores, weights))
weighted = weighted / sum(weights) if sum(weights) > 0 else 0
```

**文件**: `utils/score_engine.py:add_dimension_score()`

**影响估算**:
| 维度 | 当前得分 | 预计归一化后 | 变化 |
|------|:---:|:---:|:---:|
| Coding | 28.3% | ~35-40% | +7-12pp |
| Agent | 27.3% | ~30-35% | +3-8pp |
| Reasoning | 33.5% | ~38-42% | +5-9pp |
| 加权总分 | 29.5% | ~35-40% | +5-10pp |

**验证**: 运行 `tests/test_phase3.py` 并确认 Phase 3 评估结果的变化幅度在预期范围内。

---

### T-02 [S-5] 消除 eval() 安全风险 ⭐ P0关键

**问题**: `reasoning.py` 中数学评分使用 `eval()` 对模型输出进行数值比较，模型生成的文本不可信，存在代码注入风险。

**修复**: 替换为 `ast.literal_eval()` + 正则提取数值的复合方案。

```python
import ast
import re

def _safe_parse_numeric(text: str):
    """安全解析模型输出中的数值"""
    cleaned = re.sub(r'[^\d.eE+\-*/()]', '', text)
    if not cleaned:
        return None
    try:
        return ast.literal_eval(cleaned)
    except (ValueError, SyntaxError):
        nums = re.findall(r'[\d.]+(?:[eE][+-]?\d+)?', text)
        if nums:
            return float(nums[0])
    return None
```

**文件**: `evaluators/reasoning.py:_score_math()`

**验证**: 单元测试确认 `_safe_parse_numeric("43000") → 43000`、`_safe_parse_numeric("__import__('os').system('ls')") → None`

---

### T-03 [F-3] 延长沙箱执行超时

**问题**: `coding.py` 中可执行代码验证使用 `subprocess.run(timeout=5)`，复杂排序/数据处理管道可能在5秒内无法完成。

**修复**: 超时从5秒延长至15秒，与 config.yaml 的 `exec_timeout` 解耦。

```python
# coding.py
EXEC_TIMEOUT = 15  # 从 5 秒延长

result = subprocess.run(
    ["python3", tmp_path],
    capture_output=True, text=True,
    timeout=EXEC_TIMEOUT
)
```

**文件**: `evaluators/coding.py:_evaluate_executable_code()`

**验证**: 确认 `config.yaml` 中可新增 `exec_timeout: 15` 配置项。

---

### T-04 [R-1] 编写 PerformanceEvaluator 评估逻辑 ⭐ P0关键

**问题**: Performance 维度权重 0.15 但从未纳入全量测试，所有模型 Performance 得分为 0，**总分被人为拉低 15%**。

**方案**: 复用现有 `evaluators/performance.py` 的 `PerformanceEvaluator` 类（已有 TTFT/TPS/并发 三个子类别结构），确保其与 Coding/Agent/Reasoning 评估器返回相同的 `List[CategoryScore]` 接口。

**关键修复点**:
1. 确认 `evaluate()` 返回 `List[CategoryScore]` 格式
2. 确认 `ScoreEngine.add_dimension_score()` 可以正确处理 performance 维度
3. 在 `run_eval.py` / 新的 CLI 入口中默认包含 performance 维度

```python
# performance.py 确认返回格式
async def evaluate(self, model, temperature=0.0, max_tokens=2048):
    categories = []
    
    # TTFT 子类别
    ttft_result = await self._evaluate_ttft(model, runs=3)
    categories.append(CategoryScore(
        category="ttft",
        score=ttft_result["score"],
        max_score=ttft_result["max_score"],
        details=ttft_result,
        weight=0.40
    ))
    
    # TPS 子类别
    tps_result = await self._evaluate_throughput(model, runs=3)
    categories.append(CategoryScore(
        category="throughput",
        score=tps_result["score"],
        max_score=tps_result["max_score"],
        details=tps_result,
        weight=0.35
    ))
    
    # 并发 子类别
    concurrent_result = await self._evaluate_concurrent(model)
    categories.append(CategoryScore(
        category="concurrent",
        score=concurrent_result["score"],
        max_score=concurrent_result["max_score"],
        details=concurrent_result,
        weight=0.25
    ))
    
    return categories
```

**文件**: `evaluators/performance.py: evaluate()`

**影响估算**: 假设中等模型 Performance 得分 60%，加权总分从 29.5% 提升至 29.5%×0.85 + 60%×0.15 = **33.6%** (+4.1pp)。

**验证**: 全量评估确认 Performance 维度出现在最终报告中。

---

### T-05 [P-1][R-3] 剔除/降级浏览器自动化子类别

**问题**: 浏览器自动化（权重 0.06，max_score=65）在两个目标应用 OpenClaw 和 Hermes 中均无业务价值，Phase3 得分仅 6.2%（全维度最低），且需要 Playwright/浏览器驱动支持。

**方案**: 从核心 Agent 评估中移除，移至 `AGENT_BENCHMARKS_OPTIONAL` 标记为可选扩展。

```python
# agent.py
AGENT_BENCHMARKS_OPTIONAL = {
    "browser_automation": {
        "weight": 0.06,
        "tests": [...],
        "category": "browser_automation",
        "display_name": "浏览器自动化",
        "optional": True
    }
}
```

**Agent 维度权重重分配**（browser_automation 的 0.06 重新分配）:
| 子类别 | 当前权重 | 调整后 |
|--------|:---:|:---:|
| function_calling | 0.15 | 0.16 |
| tool_selection | 0.12 | 0.13 |
| multi_step_reasoning | 0.12 | 0.13 |
| tool_orchestration | 0.18 | 0.19 |
| long_task_planning | 0.10 | 0.11 |
| 其余子类别 | 不变 | 不变 |

**文件**: `evaluators/agent.py`

---

### T-06 [P-2] 合并重叠子类别

**问题清单**:

| 重叠对 | 当前分属 | 合并方案 |
|--------|---------|---------|
| 代码生成 + 实际开发场景 | Coding 两个子类别 | 合并为 `code_generation`（基础+进阶），基础×3题 + 进阶×3题 |
| 阅读理解 + 知识问答 | Reasoning 两个子类别 | 合并为 `knowledge_comprehension`（阅读理解×3题 + 知识问答×3题） |
| 多步推理(Agent) + 多步决策推理(Reasoning) | 两个维度 | **不合并**（评估目的不同：Agent侧重工具链，Reasoning侧重逻辑链），但统一评分方法 |

**实施**:
```python
# coding.py — 合并代码生成 + 实际开发场景
CODING_BENCHMARKS["code_generation"] = {
    "weight": 0.25,  # 原 0.20 + 0.10 合并
    "tests": CODING_BENCHMARKS["code_generation"]["tests"] + 
             CODING_BENCHMARKS_PRACTICAL["real_world_scenarios"]["tests"],
    "category": "code_generation",
    "display_name": "代码生成（基础+进阶）",
}

# 删除 real_world_scenarios 独立子类别
del BENCHMARKS["real_world_scenarios"]
```

```python
# reasoning.py — 合并阅读理解 + 知识问答
REASONING_BENCHMARKS["knowledge_comprehension"] = {
    "weight": 0.18,  # 原 0.13 + 0.10 合并(含优化)
    "tests": REASONING_BENCHMARKS["reading_comprehension"]["tests"] +
             REASONING_BENCHMARKS["knowledge"]["tests"],
    "category": "knowledge_comprehension",
    "display_name": "知识理解与应用",
}

del REASONING_BENCHMARKS["reading_comprehension"]
del REASONING_BENCHMARKS["knowledge"]
```

**子类别总数变化**: 30 → 27 (Coding -1, Reasoning -1, Agent -1(browser))

**文件**: `evaluators/coding.py`, `evaluators/reasoning.py`

---

### T-07 [P0-1] 重构 config.yaml — 单一真源配置

将散落在 11 个脚本中的配置集中到 `config.yaml`，新增三个配置段。

**新增 segment 1: `category_weights`**

```yaml
category_weights:
  coding:
    code_generation: 0.25       # 合并后 (原0.20+0.10)
    code_completion: 0.15
    debugging: 0.15
    multilingual: 0.10
    executable_code: 0.10
    code_review: 0.08
    test_writing: 0.07
    api_development: 0.10       # 从0.05提升(API接口对OpenClaw重要)
  agent:
    function_calling: 0.16      # 重分配
    tool_selection: 0.13
    multi_step_reasoning: 0.13
    instruction_following: 0.08
    filesystem_operations: 0.06  # 从0.05提升
    shell_execution: 0.06        # 从0.05提升
    tool_orchestration: 0.19     # 重分配
    multi_turn_conversation: 0.05
    structured_output: 0.05      # 从0.04提升(对API开发重要)
    long_task_planning: 0.09     # 重分配后 (原0.10)
  reasoning:
    logic: 0.15
    knowledge_comprehension: 0.18   # 合并后 (原0.13+0.10)
    math: 0.08                     # 从0.10降低(业务价值低)
    chain_of_thought: 0.10
    business_reasoning: 0.10
    code_reasoning: 0.10           # 从0.08提升
    self_correction: 0.08          # 从0.06提升(对Hermes重要)
    multi_step_decision: 0.10
    causal_reasoning: 0.11         # 从0.08提升(对Hermes重要)
```

**新增 segment 2: `profiles`**

```yaml
profiles:
  openclaw:
    description: "面向 OpenClaw 代码代理框架"
    prompt_style: "code_first"
    suppress_reasoning: true
    max_tokens_code: 4096
    max_tokens_agent: 2048
    weights:
      coding: 0.35
      agent: 0.35
      reasoning: 0.15
      performance: 0.15
  hermes:
    description: "面向 Hermes 推理框架"
    prompt_style: "reasoning_allowed"
    suppress_reasoning: false
    max_tokens_code: 4096
    max_tokens_agent: 4096
    weights:
      coding: 0.20
      agent: 0.30
      reasoning: 0.35
      performance: 0.15
  default:
    description: "通用评估模式"
    prompt_style: "code_first"
    suppress_reasoning: false
    weights:
      coding: 0.30
      agent: 0.30
      reasoning: 0.25
      performance: 0.15
```

**新增 segment 3: `eval_modes`**

```yaml
eval_modes:
  quick:
    description: "快速筛选(5-8分钟)"
    samples_per_category: 1
    dimensions: ["coding", "agent", "reasoning"]
    temperature: 0.0
  standard:
    description: "标准评估(15-20分钟)"
    samples_per_category: 3
    dimensions: ["coding", "agent", "reasoning", "performance"]
    temperature: 0.0
  full:
    description: "全量评估(~30分钟)"
    samples_per_category: -1  # 全量
    dimensions: ["coding", "agent", "reasoning", "performance"]
    temperature: 0.0
```

**文件**: `config.yaml`（追加到现有内容末尾）

**验证**: `python -c "import yaml; yaml.safe_load(open('config.yaml')); print('OK')"`

---

### T-08 [P0-4] 同步更新 config.py 配置类

**新增数据类**:

```python
@dataclass
class ProfileConfig:
    description: str = ""
    prompt_style: str = "code_first"
    suppress_reasoning: bool = False
    max_tokens_code: int = 4096
    max_tokens_agent: int = 4096
    weights: WeightConfig = field(default_factory=WeightConfig)

@dataclass
class CategoryWeightsConfig:
    coding: dict = field(default_factory=dict)
    agent: dict = field(default_factory=dict)
    reasoning: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)

@dataclass
class EvalModeConfig:
    description: str = ""
    samples_per_category: int = 3
    dimensions: list = field(default_factory=list)
    temperature: float = 0.0
```

**Config 聚合类新增字段**:

```python
@dataclass
class Config:
    # ... 现有字段 ...
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)
    category_weights: CategoryWeightsConfig = field(default_factory=CategoryWeightsConfig)
    eval_modes: Dict[str, EvalModeConfig] = field(default_factory=dict)
```

**文件**: `utils/config.py`

---

## 四、Phase 1 执行概要（后续执行）

### T-09 [P0-2] 统一 CLI 入口

`run_eval.py` 重构为子命令体系（5 个子命令: `eval`/`verify`/`lifecycle`/`report`/`leaderboard`），详见改进规范 P0-2。

```
用法: python run_eval.py eval --mode quick|standard|full --profile openclaw|hermes
```

### T-10 [P0-5] 评估器权重适配

四个 Evaluator 的 `__init__()` 新增 `category_weights` 参数，`evaluate()` 从参数中读取权重而非硬编码。

### T-11 [P0-6] 清理废弃脚本

删除 15 个冗余脚本，详见改进规范 P0-6 清单。

### T-12 [P0-3] 统一报告引擎

报告引擎支持 `--format html|json|txt|docx` 四格式，详见改进规范 P0-3。

### T-13 [S-2] 对齐外部基准

从 HumanEval（Coding）和 MATH（Reasoning）中选取 5 道代表性题目嵌入到对应子类别的现有题库中，用公开 leaderboard 结果校准评分。

### T-14 [S-3] 增加反向验证

- **代码审查**: 增加"修复代码执行验证"——模型建议的修复方案写入临时文件并运行
- **逻辑推理**: 增加"反例检测"——检查推理结论是否排除了明显的反例

### T-15~T-16 题库扩展

- C-1: 新增 JavaScript/Shell/SQL 测试用例各 3 道
- C-2: 新增 RAG/检索增强生成子类别（5 道题，权重建议 0.08）

### T-17~T-19 数据驱动改造与校准

- P1-1: 30 个子类别题库 JSON 外置
- P1-5: Tokenizer 自适应校准
- P1-2: 统计显著性（均值/标准差/置信区间）

---

## 五、Phase 2 执行概要（计划执行）

### T-20~T-23 基础设施加固

- P2-1: SQLite 断点续传（`utils/state_manager.py`）
- P2-2: macOS sandbox-exec 沙箱加固 + Docker 容器隔离
- P2-3: `Dockerfile` + `docker-compose.yml` + `environment.yml`
- P2-4: 冷启动/热启动/空闲唤醒延迟三指标独立测量

### T-24~T-27 覆盖扩展

- C-3: 超长prompt(>8K)、空输入、并发极限、上下文填满测试
- C-5: temperature=0 + 0.7 双模式 + 稳定性评估
- P-4: 每子类别评分策略用决策树文档化
- S-4: 每子类别扩充至 ≥5 个用例

---

## 六、Phase 0 验收清单

| 编号 | 验收项 | 验证方法 | 预期结果 |
|:---:|------|---------|---------|
| T-01 | 聚合归一化修复 | `python tests/test_phase3.py` | 26 tests PASS，维度得分变化在预期范围 |
| T-02 | eval()风险消除 | `grep -r "eval(" evaluators/reasoning.py` | 无裸 eval() 调用 |
| T-03 | 沙箱超时延长 | 代码审查 `subprocess.run(timeout=15)` | 确认为 15 秒 |
| T-04 | Performance维度 | `python run_eval.py eval --mode quick --dim performance` | Performance 子类别得分 > 0 |
| T-05 | 浏览器自动化剔除 | `grep "browser_automation" evaluators/agent.py` | 标记为 OPTIONAL |
| T-06 | 子类别合并 | 代码审查 category_weights | Coding: 8个(↓1), Reasoning: 8个(↓1) |
| T-07 | config.yaml新段 | `python -c "import yaml; c=yaml.safe_load(open('config.yaml')); assert 'profiles' in c; assert 'category_weights' in c"` | OK |
| T-08 | config.py同步 | `python -c "from utils.config import load_config; c=load_config('config.yaml'); print(c.profiles['openclaw'].weights.coding)"` | 0.35 |

---

## 七、影响量化预估

### 7.1 得分影响

| 改进项 | 对总分的影响 | 方向 |
|--------|:---:|:---:|
| S-1 聚合归一化 | +5~10pp | ↑ 消除评分失真 |
| R-1 Performance纳入 | +4pp | ↑ 回收15%浪费权重 |
| P-1 剔除浏览器自动化 | ~0pp(影响小) | — 该维度本就极低 |
| P-2 合并重叠子类别 | 微小 | — 权重重新分配 |
| **Phase 0 合计** | **约 +9~14pp** | ↑ **29.5% → 38~44%** |

### 7.2 耗时影响

| 模式 | 改进前 | 改进后 | 变化 |
|------|:---:|:---:|:---:|
| quick (新增) | — | **5-8min** | 用于初筛 |
| standard | 无此模式 | 15-20min | 精细评估 Top3 |
| full | 32min | 28-32min | 受益于子类别精简 |

### 7.3 架构改善

| 指标 | 改进前 | 改进后 |
|------|:---:|:---:|
| run_*.py 脚本数 | 11 | 1 (run_eval.py) |
| 权重定义位置 | 4处(各Evaluator+各脚本) | 1处(config.yaml) |
| 子类别数 | 30 | 27 |
| 评估维度 | 3(无Performance) | 4(含Performance) |
| 评估模式 | 1种(全量) | 3种(quick/standard/full) |
| 场景化支持 | 无 | OpenClaw/Hermes双Profile |

---

## 八、风险与应对

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:---:|:---:|---------|
| 聚合归一化可能导致历史结果不可对比 | 高 | 中 | 保留旧结果目录，新结果标注 v3.0 |
| 子系统合并后评分标准变化 | 中 | 中 | T-06 执行前保存当前评分基线 |
| Performance 维度首次运行失败 | 中 | 高 | 增加 try-except 降级，失败时记录0分并继续 |
| 配置变更导致旧脚本不可用 | 高 | 中 | Phase 0 不删除旧脚本，Phase 1 才统一 |
| eval()替换遗漏 | 低 | 中 | grep 全量搜索确认 |

---

## 九、执行排期

```
Week 1: Phase 0 执行 + 审查
  Day 1: T-01(归一化) + T-02(eval安全) + T-03(超时)
  Day 2: T-04(Performance) + T-05(剔除浏览器) + T-06(合并子类别)
  Day 3: T-07(config.yaml) + T-08(config.py) + 集成测试
  Day 3-4: 审查团队评审 Phase 0 变更
  Day 5: 修复审查意见

Week 2: Phase 1 执行 + 审查
  Day 1-2: T-09(CLI) + T-10(权重适配) + T-11(清理) + T-12(报告)
  Day 3: T-13(对齐基准) + T-14(反向验证) + T-15~T-16(扩展)
  Day 4: T-17~T-19(数据驱动)
  Day 5: 审查团队评审 Phase 1

Week 3: Phase 2 执行
  Day 1-2: T-20~T-23(基础设施)
  Day 3-4: T-24~T-27(覆盖扩展)
  Day 5: 全量回归测试 + 审查团队最终评审
```

---

**报告状态**: 完整 ✅  | **建议审查重点**: Phase 0 的 T-01/T-04/T-05/T-06 四项对评分和题库结构有直接影响，建议优先评审。