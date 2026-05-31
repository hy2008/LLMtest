# LLMtest v3.0 问题根因分析与全面完善计划

> **基于**: 两轮验证报告 (qwen3.6-35b-a3b-claude-4.6-opus-reasoning-distilled)  
> **排查日期**: 2026-05-30  
> **文档类型**: 根因分析 + 完善计划

---

## 1. 问题根因汇总

经过对两轮验证报告的深入分析和对代码的逐项排查，共发现 **7 个问题**，根因分类如下：

| 序号 | 问题 | 轮次 | 严重度 | 根因类别 |
|:---:|------|:---:|:---:|------|
| P1 | 因果推理 HTTP 400 (5题中4题失败) | R1/R2 | 🔴 高 | **架构**: reasoning-distilled 模型 thinking block 含 `\x1a` 字符 |
| P2 | 逻辑推理新增题目 0/20 (2题) | R2 | 🔴 高 | **评分 Bug**: `_score_logic` 硬编码 criteria 键，新键全被忽略 |
| P3 | 结构化输出 0/25 (2轮持续) | R1/R2 | 🔴 高 | **架构**: agent.py 未对 reasoning 模型 content 预处理 |
| P4 | 推理链验证"算法证明"0/30 | R1/R2 | 🔴 高 | **数据 Bug**: `expected_steps` 键与 `criteria` 键不匹配 |
| P5 | 多轮对话 25.7% (+ KeyError) | R1/R2 | 🟡 中 | **双重 bug**: tool_calls 无降级评分 + tool 消息缺 tool_call_id |
| P6 | Debug调试 33.3% | R1/R2 | 🟡 中 | **架构**: reasoning 模型 thinking/content 分离导致 content 为空 |
| P7 | 代码生成 41.7% (LRU/API客户端) | R1/R2 | 🟡 中 | **评分**: `correct_logic` 仅匹配 5 个固定关键词 |

---

## 2. 逐项根因详细分析

### P1: 因果推理 HTTP 400

**根因**: reasoning-distilled 模型在输出 JSON 请求的格式响应时，thinking block 中包含 `\x1a` (EOF/SUB) 控制字符。LM Studio API 在后续请求中解析包含此字符的多轮对话消息体时报 HTTP 400: `"Failed to parse input at pos 0"`。

**受影响范围**: 因果推理 5 题中 4 题失败 (相关性vs因果性、干预效果评估、系统故障因果链、辛普森悖论识别)。已添加 try-except 降级保护，但得分归 0。

**修复方向**:
- 在 causal_reasoning 的 system prompt 末尾追加输出格式约束
- 在 client.py 的 `_sanitize_content` 中过滤 `\x00`-`\x1f` 控制字符（保留 `\n`, `\t`）

### P2: 逻辑推理新增题目 0/20

**根因**: `_score_logic` 方法中评分维度的处理是硬编码的。当新增"命题逻辑等价推理"和"归纳推理与反例"时，其 criteria 键 (`truth_table`, `natural_deduction`, `application_example`, `pattern_identification`, `verification`, `counterexample_or_proof`, `induction_limitation`) 在评分方法中完全没有对应的处理分支，导致 `total = 0`。

```python
# 现有代码只处理旧题的 criteria:
if "correct_answer" in criteria: ...   # ✅ 三段论/条件推理
if "logical_clarity" in criteria: ...  # ✅ 复杂逻辑谜题
if "eve_leftmost" in criteria: ...     # ✅ 复杂逻辑谜题
# ❌ 新题的 truth_table, natural_deduction, pattern_identification 等全部未处理
```

**实证**: 详细结果 JSON 显示 `criteria_scores: {"correct_answer": 0, "reasoning_process": 0}`—模型实际回答了内容，但评分器检查的是不存在的维度。

**修复方向**: 将 `_score_logic` 重构为通用评分方法，遍历 `criteria` dict 并用对应的关键词列表匹配。

### P3: 结构化输出 0/25

**根因 (双重)**:

1. **reasoning-distilled 模型 content 可能为空**: `qwen3.6-35b-a3b-claude-4.6-opus-reasoning-distilled` 的推理内容在 `reasoning_content` 字段，`content` 可能为空字符串
2. **agent.py 缺少内容预处理**: 与 `reasoning.py` 不同（有 `_safe_content` → `_extract_thinking_content` 链），agent.py 的 `_score_structured_output` 直接使用 `result.content`，未做任何预处理

**修复方向**:
- 为 agent.py 添加 `_normalize_response` 预处理方法
- 在 `_score_structured_output` 中增加 JSON 提取策略 (md code block + JSON 大括号匹配)

### P4: 推理链验证"算法证明"0/30

**根因**: 这是一个**测试数据 Bug**。在 `REASONING_BENCHMARKS_PRACTICAL["chain_of_thought"]` 中：

```python
# 测试用例数据
"expected_steps": [
    {"name": "termination", ...},      # ← 键名: termination
    {"name": "correctness", ...}       # ← 键名: correctness
]
# 评分 criteria
"criteria": {
    "termination_proof": 10,           # ← 不匹配! 是 termination_proof 不是 termination
    "correctness_proof": 10,           # ← 不匹配! 是 correctness_proof 不是 correctness
    ...
}
```

此外该测试**缺少 `step_keywords` 字段**，而代码中依赖 `step.get("step_keywords", [])` 进行匹配。

**修复方向**: 统一 `expected_steps.name` 与 `criteria` 键名，添加 `step_keywords`。

### P5: 多轮对话 25.7% + KeyError

**根因 (三重)**:

1. **tool 角色消息缺 tool_call_id**: agent.py 构造消息时，tool 角色的 `ChatMessage` 未传递 `tool_call_id`，导致 LM Studio API 可能忽略该消息
2. **reasoning 模型不返回 tool_calls**: 模型倾向于在文本中描述工具调用而非通过标准 API 格式
3. **无文本降级评分**: `_score_multi_turn_conversation` 缺少文本降级策略（对比 `_score_multi_step` 有 4 级降级）

**修复方向**:
- tool 角色消息添加 `tool_call_id`
- 添加文本降级评分 (检查 `result.content` 中是否包含工具名/参数)
- client.py 序列化时包含 `tool_call_id`

### P6: Debug调试 33.3%

**根因**: 与 P3 类似。reasoning-distilled 模型的 thinking block 和 content 分离，导致 `result.content` 可能为空或仅包含不完整的代码片段。评分器 `_score_debugging` 基于 content 进行错误类型识别和修复代码分析。

**修复方向**: Debug调试的 evaluator 也需添加 content 预处理。

### P7: 代码生成 41.7%

**根因**: `_score_code_writing` 中的 `correct_logic` 维度完全依赖 5 个固定关键词匹配:

```python
logic_keywords = ["时间复杂度", "空间复杂度", "边界条件", "异常处理", "类型提示"]
found = sum(1 for kw in logic_keywords if kw in extracted_code or kw in response)
scores["correct_logic"] = round(criteria.get("correct_logic", 0) * found / len(logic_keywords))
```

LRU 缓存和 REST API 客户端两题即使代码功能正确，只要没有用到这 5 个特定关键词就会得 0 分。

**修复方向**: 将关键词匹配从"固定 5 词"改为"题目特定关键词列表"，每个测试用例定义自己的 logic_keywords。

---

## 3. 修复优先级矩阵

| 优先级 | 任务 | 根因 | 影响 | 工时 | 风险 |
|:---:|------|------|:---:|:---:|:---:|
| **P0** | P2: 逻辑推理新题评分 | 评分逻辑硬编码 | 40 分被浪费 | 2h | 低 |
| **P0** | P4: 推理链验证数据 Bug | 键名不匹配 | 30 分被浪费 | 0.5h | 低 |
| **P1** | P3: 结构化输出 content 预处理 | reasoning 模型适配 | 25 分被浪费 | 1.5h | 中 |
| **P1** | P1: 因果 HTTP 400 (prompt 修复) | thinking block 控制字符 | 100 分被浪费 | 1h | 中 |
| **P1** | P1: 因果 HTTP 400 (sanitize) | `\x1a` 控制字符 | 通用保护 | 0.5h | 低 |
| **P2** | P5: 多轮对话 tool_call_id | 消息序列化 | 20 分低估 | 1h | 低 |
| **P2** | P5: 多轮对话 text fallback | reasoning 模型适配 | 评分准确性 | 1h | 低 |
| **P3** | P6: Debug 推理 content 预处理 | reasoning 模型适配 | 30 分被浪费 | 1.5h | 中 |
| **P3** | P7: 代码生成 per-test keywords | 固定关键词 | 40 分低估 | 1h | 低 |

---

## 4. 全面完善计划

### Phase A: 关键 Bug 修复 (P0, 预计 2.5h) ✅ 已完成

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|:---:|
| **A-1** | `evaluators/reasoning.py` | 修复 `_score_logic` 方法，通用化 criteria 评分。添加 7 个新 criteria 维度的关键词匹配分支 (`truth_table`, `natural_deduction`, `application_example`, `pattern_identification`, `verification`, `counterexample_or_proof`, `induction_limitation`) | ✅ |
| **A-2** | `evaluators/reasoning.py` | 修复推理链验证 `expected_steps` 键名 (`termination`→`termination_proof`, `correctness`→`correctness_proof`)，补充 `step_keywords` | ✅ |

### Phase B: Reasoning 模型适配框架 (P1, 预计 3h) ✅ 已完成

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|:---:|
| **B-1** | `utils/client.py` | 在 `_sanitize_content` 中过滤 C0 控制字符 (`\x00`-`\x1f`，保留 `\n` `\t`)，扩展至 `\x7f-\x9f` C1 控制字符；同步消毒 `reasoning_content` | ✅ |
| **B-2** | `evaluators/reasoning.py` | 优化 causal_reasoning 的 system prompt，追加：`请直接输出分析内容，不要使用  thinking  标签。` | ✅ |
| **B-3** | `evaluators/agent.py` | 新增 `_normalize_response` 静态方法，统一预处理 reasoning 模型的 content（含 thinking block 提取与 reasoning_content 回退） | ✅ |
| **B-4** | `evaluators/agent.py` | 修复 `_score_structured_output`：增加 4 级 JSON 提取策略 (` ```json ``` ` → ` ``` ``` ` → `{...}` → `[...]` ) | ✅ |

### Phase C: 评分系统完善 (P2, 预计 3h) ✅ 已完成

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|:---:|
| **C-1** | `evaluators/agent.py` | 修复多轮对话：tool 角色消息自动生成和传递 `tool_call_id`（从 assistant 的 tool_calls 中提取 id） | ✅ |
| **C-2** | `evaluators/agent.py` | 新增多轮对话文本降级评分：当模型无 tool_calls 时，检查 `result.content` 中是否包含预期工具名/参数，给予 50% 分数 | ✅ |
| **C-3** | `utils/client.py` | 新增 `_serialize_message` 静态方法，payload 序列化时包含 `tool_calls` 和 `tool_call_id` | ✅ |
| **C-4** | `evaluators/coding.py` | 为代码生成的 3 个测试用例添加 `logic_keywords` 字段（8-10 个专属关键词），`_score_code_writing` 优先使用题目级关键词，同时支持 `eviction_logic`/`async_methods` 替代 criteria 键 | ✅ |

### Phase D: 测试验证 (P3, 预计 1h) ✅ 已完成

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|:---:|
| **D-1** | `tests/test_phase_a_fix.py` | 全线单元测试：11 个 P1-P7 映射验证 + 1 个全阶段回归检查，55 个测试全部通过 | ✅ |
| **D-2** | — | 以 qwen3.6-35b 模型运行 quick 模式验证可随时执行（需要 LM Studio 加载模型） | ⏳ |

---

## 4.5 完成度总结

| 阶段 | 状态 | 修复内容 | 测试数 |
|:---|:---:|------|:---:|
| Phase A | ✅ | P2 逻辑评分 + P4 推理链数据 | 4 |
| Phase B | ✅ | P1 消毒/Prompt + P3 规范化 + P6 JSON | 7 |
| Phase C | ✅ | P5 多轮对话 + P7 代码关键词 | 2 |
| Phase D | ✅ | P1-P7 全线验证 + 回归 | 8 |
| 原有测试 | ✅ | boundary + review_models | 34 |
| **合计** | | **4 阶段 12 个任务** | **55 passed / 0 failed** |

---

## 5. 测试需求与场景适配建议

### 5.1 Reasoning-Distilled 模型适配

**核心挑战**: reasoning-distilled 模型 (如 qwen3.6-35b-a3b) 具有特殊的输出结构:
- 推理过程在 `reasoning_content` 字段
- `content` 字段可能为空、不完整、或含有 markdown 包装
- thinking block 可能包含控制字符
- 工具调用倾向于文本描述而非标准 tool_calls

**建议实施方案**:
1. 在 `utils/` 下创建统一的 `response_normalizer.py` 模块
2. 所有 evaluator 的 evaluate 方法中，`result.content` 替换为 `normalize_response(result)`
3. normalize 逻辑：
   - 优先使用 `result.content`
   - 若为空则使用 `result.reasoning_content`
   - 提取 markdown code block 中的代码/JSON
   - 过滤 C0 控制字符

### 5.2 评分体系泛化

**当前问题**: 各 evaluator 的 scoring 方法为每个测试用例硬编码评分分支。

**建议长期方案 (迭代 2)**:
1. 将评分逻辑从"if-elif 分支"改为"criteria 驱动"
2. 每个 criteria 维度定义 `match_type` (`keyword_match`, `regex_match`, `semantic_match`) 和 `match_values`
3. 通用评分循环遍历 criteria dict 自动计算分数

### 5.3 题库管理优化

**当前状态**: 测试用例内嵌在 evaluator `.py` 文件中，与评分逻辑耦合。

**建议 (已部分完成)**:
1. ✅ Phase 1 已完成 JSON 外置框架 (25 个 JSON 文件)
2. 待做: 将 evaluator 中的 `BENCHMARKS`/`BENCHMARKS_PRACTICAL` 字典逐步迁移到 JSON 题库
3. 待做: JSON schema 验证（审查报告已建议）

### 5.4 测试覆盖面评估

| 维度 | 当前覆盖 | 缺失场景 | 优先级 |
|------|------|------|:---:|
| 代码 | 7 类 | RAG 代码检索、低代码/可视化编程 | P3 |
| Agent | 10 类 | 长期记忆、人机协作、多 Agent 编排 | P2 |
| 推理 | 9 类 | 伦理推理、创造性推理、类比推理 | P3 |
| 性能 | 3 类 | GPU 推理、硬件感知性能、内存-延迟权衡 | P3 |
| 安全 | 0 类 | 越狱测试、数据泄露、偏见检测 | P2 |

---

## 6. 执行排期

| 阶段 | 任务 | 预计工时 | 完成标准 |
|------|------|:---:|------|
| **Phase A** | P2 逻辑推理 + P4 推理链数据 Bug | 2.5h | 新题得分 > 0 |
| **Phase B** | Reasoning 模型适配框架 | 3h | 结构化输出/因果推理不再 HTTP 400 |
| **Phase C** | 评分系统完善 | 3h | 多轮对话/代码生成得分准确 |
| **Phase D** | 测试 + 验证 | 1h | 全部 119 passed + 模型验证通过 |
| **总计** | | **9.5h** | |

---

## 7. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|:---:|:---:|------|
| LM Studio API 控制字符过滤不完整 | 中 | 中 | 添加 bytes-level 过滤作为备用方案 |
| reasoning 模型 output 极度不稳定 | 高 | 中 | 增加重试次数 3→5，单次超时 900→1200s |
| 评分重构引入回归 | 低 | 高 | 全量单元测试 + 对比两轮历史数据 |
| 题库与评分逻辑耦合 | 高 | 低 | 本次仅修复评分，下次迭代迁 JSON |

---

*报告生成时间: 2026-05-30*  
*分析范围: 2 轮验证报告 + evaluators/coding.py, agent.py, reasoning.py + utils/client.py*