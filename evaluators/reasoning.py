"""
通用推理评估模块 - 增强版
评估维度: 逻辑推理、阅读理解、数学能力、知识问答
新增维度: 推理链验证、业务场景推理、代码逻辑推理、自我修正能力、故障排查

设计理念: 模拟 OpenClaw/Hermes 等框架的真实推理场景
"""

import re
import ast
from typing import Dict, Any, List, Tuple
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


def _safe_parse_numeric(text: str):
    """安全解析文本中的数值表达式，避免 eval() 代码注入风险。"""
    try:
        cleaned = re.sub(r'[^\d.eE+\-*/()]', '', text.strip())
        if not cleaned:
            return None
        return ast.literal_eval(cleaned)
    except (ValueError, SyntaxError):
        nums = re.findall(r'[\d.]+(?:[eE][+-]?\d+)?', text)
        return float(nums[0]) if nums else None


def _semantic_keyword_score(response_lower: str, primary_keywords: list, semantic_keywords: list, max_pts: float) -> float:
    """语义关键词评分: 精确匹配满分, 语义匹配70%分, 都不匹配0分。"""
    primary_found = any(kw in response_lower for kw in primary_keywords)
    semantic_found = any(kw in response_lower for kw in semantic_keywords)
    if primary_found:
        return max_pts
    elif semantic_found:
        return round(max_pts * 0.7)
    return 0.0


def _extract_thinking_content(text: str) -> str:
    """从模型输出中提取有效内容，处理 thinking block 场景。

    许多推理模型(如 Qwen/Qwopus)会将推理过程放在 thinking block 中，
    而 response 部分可能为空或只包含简洁结论。

    策略:
    1. 如果内容非空，直接返回
    2. 如果内容为空，尝试从 thinking block 中提取推理内容
    3. 将 thinking + response 合并，确保评分时能覆盖完整推理链
    """
    if not text or not text.strip():
        return ""

    stripped = text.strip()

    has_explicit_thinking = bool(
        re.search(r'<![CDATA[<think>|</think>|<thinking>|</thinking>]]>', stripped)
    )

    if has_explicit_thinking:
        thinking_blocks = []
        for pattern in [r'<think>(.*?)</think>', r'<thinking>(.*?)</thinking>']:
            for m in re.finditer(pattern, stripped, re.DOTALL):
                thinking_blocks.append(m.group(1).strip())

        outside_thinking = stripped
        for pattern in [r'<think>.*?</think>', r'<thinking>.*?</thinking>']:
            outside_thinking = re.sub(pattern, '', outside_thinking, flags=re.DOTALL)
        outside_thinking = outside_thinking.strip()

        if thinking_blocks and not outside_thinking:
            return "\n\n".join(thinking_blocks)
        elif thinking_blocks and outside_thinking:
            return outside_thinking + "\n\n【推理过程】\n" + "\n\n".join(thinking_blocks)
        else:
            return stripped

    return stripped


# ============================================================
# 通用推理测试题库 - 基础测试
# ============================================================

REASONING_BENCHMARKS = {
    "logic": [
        {
            "name": "三段论推理",
            "prompt": "请回答以下逻辑推理问题:\n\n前提1: 所有程序员都懂逻辑\n前提2: 小明是程序员\n\n问: 小明懂逻辑吗？请给出推理过程。",
            "expected_answer": "懂",
            "expected_keywords": ["懂", "是的", "正确", "因为", "前提", "所以"],
            "max_score": 15,
            "criteria": {
                "correct_answer": 6,
                "reasoning_process": 5,
                "logical_clarity": 4
            }
        },
        {
            "name": "条件推理",
            "prompt": "分析以下条件推理:\n\n规则: 如果下雨，地面就会湿。\n事实: 地面是干的。\n\n问: 是否下雨了？请解释你的推理。",
            "expected_answer": "没有下雨",
            "expected_keywords": ["没有", "否", "逆否", "否定后件", "modus tollens", "干"],
            "max_score": 15,
            "criteria": {
                "correct_answer": 6,
                "reasoning_process": 5,
                "logical_validity": 4
            }
        },
        {
            "name": "复杂逻辑谜题",
            "prompt": "五个朋友(Alice, Bob, Carol, Dave, Eve)坐成一排。已知:\n1. Alice 不坐在两端\n2. Bob 紧挨着 Carol 的右边\n3. Dave 不坐在 Alice 的旁边\n4. Eve 坐在最左边\n\n请给出所有可能的座位排列。",
            "expected_answer_pattern": ["Eve", "Alice"],
            "max_score": 20,
            "criteria": {
                "eve_leftmost": 4,
                "bob_carol_adjacent": 5,
                "alice_not_ends": 4,
                "dave_not_near_alice": 4,
                "complete_arrangement": 3
            }
        },
        {
            "name": "命题逻辑等价推理",
            "prompt": "证明或反驳以下逻辑等价:\n\n¬(P ∧ Q) ≡ ¬P ∨ ¬Q  (德摩根定律)\n\n要求:\n1. 使用真值表方法验证\n2. 使用自然推理规则证明\n3. 给出一个具体的应用示例",
            "expected_keywords": ["真值表", "德摩根", "De Morgan", "等价", "否定", "分配", "应用"],
            "max_score": 20,
            "criteria": {
                "truth_table": 7,
                "natural_deduction": 8,
                "application_example": 5
            }
        },
        {
            "name": "归纳推理与反例",
            "prompt": "观察以下数列的前几项: 2, 3, 5, 7, 11, 13\n\n有人提出猜想: '这个数列的所有项都是质数'\n\n请:\n1. 描述这个数列的生成规律\n2. 验证猜想对前6项是否成立\n3. 找到猜想的反例(或证明猜想成立)\n4. 讨论归纳推理的局限性",
            "expected_keywords": ["质数", "素数", "反例", "归纳", "局限", "验证", "prime"],
            "max_score": 20,
            "criteria": {
                "pattern_identification": 5,
                "verification": 5,
                "counterexample_or_proof": 5,
                "induction_limitation": 5
            }
        },
    ],
    "knowledge_understanding": [
        {
            "name": "技术文档理解",
            "passage": """Redis 是一个开源的内存数据结构存储系统，可以用作数据库、缓存和消息代理。
它支持多种数据结构，如字符串(Strings)、哈希(Hashes)、列表(Lists)、集合(Sets)、
有序集合(Sorted Sets)等。Redis 通过将数据存储在内存中来提供极高的读写性能，
同时也支持将数据持久化到磁盘。Redis 采用单线程模型处理命令，但通过 I/O 多路复用
技术实现了高并发处理能力。""",
            "questions": [
                "Redis 支持哪些数据结构？",
                "Redis 为什么能提供极高的读写性能？",
                "Redis 如何实现高并发？"
            ],
            "expected_answers": [
                ["字符串", "哈希", "列表", "集合", "有序集合", "Strings", "Hashes", "Lists", "Sets"],
                ["内存", "memory"],
                ["单线程", "I/O多路复用", "多路复用", "multiplexing"]
            ],
            "max_score": 20,
            "criteria": {
                "q1_data_structures": 7,
                "q2_performance": 7,
                "q3_concurrency": 6
            }
        },
        {
            "name": "隐含信息推断",
            "passage": """某公司的API服务在过去三个月中，响应时间从平均200ms增加到了800ms。
同时，用户投诉量增加了300%。开发团队发现数据库查询是主要瓶颈，特别是几个
复杂的JOIN操作。团队决定引入Redis缓存层，将热点数据缓存起来。""",
            "questions": [
                "根据文本，性能下降的主要原因是什么？",
                "引入Redis缓存能解决什么问题？",
                "文本暗示了什么优化策略？"
            ],
            "expected_answers": [
                ["数据库", "JOIN", "查询", "database", "query"],
                ["热点数据", "缓存", "cache", "响应时间"],
                ["缓存", "减少数据库查询", "热点数据", "优化"]
            ],
            "max_score": 20,
            "criteria": {
                "q1_root_cause": 7,
                "q2_solution": 7,
                "q3_implication": 6
            }
        },
        {
            "name": "系统设计概念",
            "prompt": "请解释以下分布式系统概念，每个用1-2句话:\n\n1. CAP 定理\n2. 最终一致性\n3. 幂等性\n4. 电路断路器模式",
            "expected_keywords": {
                "CAP": ["一致性", "可用性", "分区容错", "consistency", "availability", "partition"],
                "最终一致性": ["最终", "一致", "延迟", "eventual", "replica"],
                "幂等性": ["多次", "相同", "结果", "idempotent", "same result"],
                "断路器": ["熔断", "降级", "恢复", "circuit", "breaker", "fault"]
            },
            "max_score": 20,
            "criteria": {
                "cap_theorem": 5,
                "eventual_consistency": 5,
                "idempotency": 5,
                "circuit_breaker": 5
            }
        },
        {
            "name": "编程范式对比",
            "prompt": "请对比以下三对编程概念，说明各自的特点和适用场景:\n\n1. 编译型语言 vs 解释型语言\n2. 强类型 vs 弱类型\n3. 面向对象 vs 函数式编程",
            "expected_keywords": [
                ["编译", "运行前", "机器码", "compile", "解释", "运行时", "interpreter"],
                ["类型检查", "转换", "安全", "type check", "coercion"],
                ["对象", "类", "封装", "object", "class", "函数", "纯函数", "不可变", "pure", "immutable"]
            ],
            "max_score": 20,
            "criteria": {
                "compiled_vs_interpreted": 7,
                "strong_vs_weak_typing": 7,
                "oop_vs_functional": 6
            }
        },
    ],
    "math": [
        {
            "name": "算法复杂度分析",
            "prompt": "分析以下代码的时间复杂度:\n\n```python\ndef func(n):\n    result = 0\n    for i in range(n):\n        for j in range(i, n):\n            result += i * j\n    return result\n```\n\n请给出:\n1. 时间复杂度 (大O表示法)\n2. 详细分析过程\n3. 空间复杂度",
            "expected_answer": "O(n^2)",
            "max_score": 15,
            "criteria": {
                "correct_complexity": 6,
                "analysis_process": 5,
                "space_complexity": 4
            }
        },
        {
            "name": "概率计算",
            "prompt": "一个袋子里有3个红球和5个蓝球。不放回地连续取2个球。\n\n请计算:\n1. 两个都是红球的概率\n2. 两个都是蓝球的概率\n3. 一个红球一个蓝球的概率\n\n请给出计算过程。",
            "expected_answers": {
                "both_red": "3/28",
                "both_blue": "10/28",
                "one_each": "15/28"
            },
            "max_score": 15,
            "criteria": {
                "both_red": 5,
                "both_blue": 5,
                "one_each": 5
            }
        },
        {
            "name": "数学建模",
            "prompt": "一个电商平台的日活跃用户数每天增长5%。当前日活跃用户数为10,000人。\n\n请计算:\n1. 30天后的日活跃用户数\n2. 达到100,000用户需要多少天\n3. 如果要控制在60天内达到50,000用户，日增长率应该调整为多少？\n\n请给出公式和计算过程。",
            "max_score": 20,
            "criteria": {
                "q1_projection": 6,
                "q2_days_needed": 7,
                "q3_growth_rate": 7
            }
        },
    ],
}


# ============================================================
# 新增测试题库 - 面向实际应用的推理测试
# ============================================================

REASONING_BENCHMARKS_PRACTICAL = {
    # ============================================================
    # 1. 推理链验证 (Chain-of-Thought)
    # ============================================================
    "chain_of_thought": [
        {
            "name": "复杂数学推导",
            "prompt": "证明：对于任意正整数n，1+2+...+n = n(n+1)/2\n\n请给出完整的数学归纳法证明，包括:\n1. 基础情况验证\n2. 归纳假设\n3. 归纳步骤\n4. 结论",
            "expected_steps": [
                "base_case",      # 基础情况验证
                "induction_hypothesis",  # 归纳假设
                "induction_step",  # 归纳步骤
                "conclusion"      # 结论
            ],
            "step_keywords": {
                "base_case": ["n=1", "基础", "base", "1 = 1"],
                "induction_hypothesis": ["假设", "hypothesis", "n=k", "k(k+1)/2"],
                "induction_step": ["n=k+1", "归纳步骤", "step", "k+1", "(k+1)(k+2)/2"],
                "conclusion": ["结论", "conclusion", "证毕", "QED", "对所有n成立"]
            },
            "max_score": 30,
            "criteria": {
                "base_case": 7,
                "induction_hypothesis": 7,
                "induction_step": 10,
                "conclusion": 6
            }
        },
        {
            "name": "算法正确性证明",
            "prompt": """证明以下快速排序算法的正确性:

```python
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
```

请从以下方面分析:
1. 终止性(Termination)
2. 正确性(Correctness)
3. 时间复杂度分析
4. 空间复杂度分析""",
            "expected_steps": ["termination_proof", "correctness_proof", "time_complexity", "space_complexity"],
            "step_keywords": {
                "termination_proof": ["终止", "termination", "递归", "base case", "len(arr)", "<= 1", "基本情况"],
                "correctness_proof": ["正确性", "correctness", "不变式", "invariant", "partition", "pivot", "小于"],
                "time_complexity": ["时间复杂度", "time complexity", "O(n log n)", "O(n²)", "平均", "average", "最坏", "worst"],
                "space_complexity": ["空间复杂度", "space complexity", "O(log n)", "O(n)", "递归栈", "call stack"]
            },
            "max_score": 30,
            "criteria": {
                "termination_proof": 7,
                "correctness_proof": 8,
                "time_complexity": 8,
                "space_complexity": 7
            }
        },
    ],
    
    # ============================================================
    # 2. 业务场景推理 (OpenClaw/Hermes核心场景)
    # ============================================================
    "business_reasoning": [
        {
            "name": "系统故障排查",
            "scenario": """系统症状:
- API响应时间从100ms增加到2000ms
- 数据库CPU使用率100%
- 错误日志显示大量连接超时
- 缓存命中率从95%下降到60%
- 最近部署了新的查询优化器

请给出:
1. 可能的原因分析(至少3个)
2. 排查步骤
3. 解决方案
4. 预防措施""",
            "expected_reasoning_chain": [
                "symptom_analysis",
                "root_cause_hypothesis", 
                "verification_plan",
                "solution_proposal",
                "prevention_measures"
            ],
            "max_score": 30,
            "criteria": {
                "symptom_analysis": 5,
                "root_cause_identification": 8,
                "verification_plan": 5,
                "solution_proposal": 7,
                "prevention_measures": 5
            }
        },
        {
            "name": "需求分析推理",
            "scenario": """产品经理提出需求:
"用户反馈说我们的搜索功能太慢了，需要优化。"

请给出:
1. 需要澄清的问题(至少5个)
2. 性能瓶颈的可能位置
3. 优化方案评估
4. 实施优先级建议""",
            "expected_reasoning_chain": [
                "clarification_questions",
                "bottleneck_analysis",
                "solution_evaluation",
                "priority_recommendation"
            ],
            "max_score": 25,
            "criteria": {
                "clarification_questions": 6,
                "bottleneck_analysis": 7,
                "solution_evaluation": 7,
                "priority_recommendation": 5
            }
        },
        {
            "name": "架构决策推理",
            "scenario": """团队需要为新的微服务选择消息队列:
- 日均消息量: 1000万条
- 峰值QPS: 5000
- 消息大小: 平均1KB，最大10MB
- 可靠性要求: 不能丢消息
- 延迟要求: 平均<100ms
- 团队熟悉度: Kafka>RabbitMQ>RocketMQ

请给出:
1. 各方案对比分析
2. 推荐方案及理由
3. 部署架构建议
4. 风险与缓解措施""",
            "expected_reasoning_chain": [
                "requirement_analysis",
                "option_comparison",
                "recommendation",
                "architecture_design",
                "risk_assessment"
            ],
            "max_score": 30,
            "criteria": {
                "requirement_analysis": 5,
                "option_comparison": 8,
                "recommendation": 6,
                "architecture_design": 6,
                "risk_assessment": 5
            }
        },
    ],
    
    # ============================================================
    # 3. 代码逻辑推理
    # ============================================================
    "code_reasoning": [
        {
            "name": "代码行为预测",
            "code": """
async def process_items(items):
    results = []
    for item in items:
        result = await fetch_data(item)
        results.append(result)
    return results
            """,
            "question": """分析以上代码:
1. 这段代码有什么问题？
2. 在大数据量下的性能影响?
3. 如何优化？给出优化后的代码
4. 优化前后的性能对比估算""",
            "expected_insights": [
                "sequential_execution",
                "blocking_behavior",
                "no_parallelism",
                "use_gather",
                "performance_improvement"
            ],
            "max_score": 25,
            "criteria": {
                "problem_identification": 6,
                "performance_impact": 5,
                "optimization_solution": 8,
                "performance_comparison": 6
            }
        },
        {
            "name": "并发问题分析",
            "code": """
class ConnectionPool:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self.connections = []
        self.in_use = set()

    def get_connection(self):
        if self.connections:
            conn = self.connections.pop()
            self.in_use.add(conn)
            return conn
        if len(self.in_use) < self.max_size:
            conn = create_connection()
            self.in_use.add(conn)
            return conn
        raise Exception("Pool exhausted")

    def release_connection(self, conn):
        self.in_use.remove(conn)
        self.connections.append(conn)
            """,
            "question": """分析以上连接池代码:
1. 存在的并发问题(至少2个)
2. 可能导致的后果
3. 修复方案
4. 使用示例""",
            "expected_insights": [
                "race_condition",
                "no_thread_safety",
                "missing_lock",
                "connection_leak",
                "fix_with_lock"
            ],
            "max_score": 25,
            "criteria": {
                "concurrency_issues": 8,
                "consequence_analysis": 5,
                "fix_solution": 8,
                "usage_example": 4
            }
        },
        {
            "name": "算法选择推理",
            "code": """
def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates
            """,
            "question": """分析以上代码:
1. 时间复杂度和空间复杂度
2. 存在的问题
3. 不同数据规模下的优化方案
4. 给出最优实现""",
            "expected_insights": [
                "O(n^2)_complexity",
                "inefficient",
                "set_optimization",
                "hash_based",
                "optimal_solution"
            ],
            "max_score": 25,
            "criteria": {
                "complexity_analysis": 6,
                "problem_identification": 5,
                "optimization_strategy": 7,
                "optimal_implementation": 7
            }
        },
    ],
    
    # ============================================================
    # 4. 自我修正能力
    # ============================================================
    "self_correction": [
        {
            "name": "推理纠错",
            "initial_wrong": """问题: 一个水池有两个进水管和一个排水管。
- 进水管A单独注满需要3小时
- 进水管B单独注满需要6小时
- 排水管单独排空需要4小时

错误推理:
"三个管子一起开，注满水池需要 3+6-4 = 5小时"

请:
1. 指出错误所在
2. 给出正确推理
3. 计算正确答案""",
            "expected_behavior": "identify_error_and_correct",
            "expected_steps": [
                "identify_error",
                "explain_why_wrong",
                "correct_reasoning",
                "correct_answer"
            ],
            "max_score": 25,
            "criteria": {
                "error_identification": 6,
                "explanation": 6,
                "correct_reasoning": 8,
                "correct_answer": 5
            }
        },
        {
            "name": "逻辑谬误识别",
            "scenario": """以下推理存在逻辑谬误:

"我们公司过去三年都在用MySQL，系统运行良好。
所以MySQL是最好的数据库，所有项目都应该用MySQL。"

请:
1. 识别逻辑谬误类型
2. 解释为什么这是谬误
3. 给出合理的评估框架
4. 举例说明如何正确选择数据库""",
            "expected_behavior": "identify_fallacy",
            "expected_steps": [
                "fallacy_identification",
                "explanation",
                "evaluation_framework",
                "correct_example"
            ],
            "max_score": 25,
            "criteria": {
                "fallacy_identification": 7,
                "explanation": 6,
                "evaluation_framework": 7,
                "correct_example": 5
            }
        },
    ],
    
    # ============================================================
    # 5. 多步决策推理
    # ============================================================
    "multi_step_decision": [
        {
            "name": "资源分配决策",
            "scenario": """团队有3个开发人员，需要在1个月内完成:
1. 修复50个Bug(每个Bug平均2小时)
2. 开发新功能A(预估80小时)
3. 开发新功能B(预估60小时)
4. 性能优化(预估40小时)
5. 技术债务清理(预估30小时)

约束:
- 每天工作8小时，每周5天
- Bug必须全部修复
- 新功能A是客户承诺的，必须完成
- 其他任务可部分完成

请给出:
1. 工作量计算
2. 优先级排序
3. 人员分配方案
4. 风险与应对""",
            "expected_steps": [
                "workload_calculation",
                "priority_sorting",
                "resource_allocation",
                "risk_assessment"
            ],
            "max_score": 30,
            "criteria": {
                "workload_calculation": 6,
                "priority_sorting": 7,
                "resource_allocation": 9,
                "risk_assessment": 8
            }
        },
        {
            "name": "技术债务权衡",
            "scenario": """当前系统存在以下技术债务:
1. 数据库查询未优化(影响性能)
2. 缺少单元测试(影响质量)
3. 代码重复度高(影响维护)
4. 文档缺失(影响新人上手)

业务压力:
- 下个月要发布重要功能
- 客户对性能投诉增多
- 团队有2名新人加入

请给出:
1. 技术债务影响评估
2. 偿还优先级
3. 短期和长期计划
4. 与业务目标的平衡策略""",
            "expected_steps": [
                "impact_assessment",
                "priority_ranking",
                "short_term_plan",
                "long_term_plan",
                "balance_strategy"
            ],
            "max_score": 30,
            "criteria": {
                "impact_assessment": 6,
                "priority_ranking": 7,
                "short_term_plan": 6,
                "long_term_plan": 6,
                "balance_strategy": 5
            }
        },
    ],
    
    # ============================================================
    # 6. 因果推理
    # ============================================================
    "causal_reasoning": [
        {
            "name": "相关性vs因果性",
            "scenario": """观察数据:
- 冰淇淋销量增加时，溺水事故也增加
- 周末时，网站流量和员工加班时长都增加
- 引入缓存后，数据库CPU下降，API响应时间也下降

请分析:
1. 哪些是相关性，哪些是因果性？
2. 如何区分相关性和因果性？
3. 在系统优化中如何避免因果误判？
4. 设计一个实验验证缓存对性能的影响""",
            "expected_steps": [
                "correlation_vs_causation",
                "differentiation_method",
                "avoiding_misjudgment",
                "experimental_design"
            ],
            "max_score": 25,
            "criteria": {
                "correlation_vs_causation": 7,
                "differentiation_method": 6,
                "avoiding_misjudgment": 6,
                "experimental_design": 6
            }
        },
        {
            "name": "根因分析",
            "scenario": """生产环境出现以下现象:
- 应用服务器CPU飙升
- 内存使用正常
- 网络IO正常
- 磁盘IO正常
- 线程数激增
- 日志显示大量超时

请进行根因分析:
1. 列出所有可能的原因
2. 设计验证方法
3. 给出最可能的根因
4. 提出修复方案""",
            "expected_steps": [
                "possible_causes",
                "verification_methods",
                "root_cause_identification",
                "fix_proposal"
            ],
            "max_score": 25,
            "criteria": {
                "possible_causes": 7,
                "verification_methods": 6,
                "root_cause_identification": 7,
                "fix_proposal": 5
            }
        },
        {
            "name": "干预效果评估",
            "scenario": """A/B测试结果:
- 实验组(新算法): 转化率提升15%, 但延迟增加50ms
- 对照组(旧算法): 转化率基线, 延迟正常
- 样本量: 各10000用户
- 测试周期: 2周

请分析:
1. 转化率提升是否可归因于新算法？
2. 延迟增加是否由新算法引起？
3. 是否存在混杂变量？
4. 如何决定是否上线新算法？""",
            "expected_steps": [
                "attribution_analysis",
                "side_effect_assessment",
                "confounding_check",
                "decision_framework"
            ],
            "max_score": 25,
            "criteria": {
                "attribution_analysis": 7,
                "side_effect_assessment": 6,
                "confounding_check": 6,
                "decision_framework": 6
            }
        },
        {
            "name": "系统故障因果链",
            "scenario": """微服务系统故障时间线:
09:00 - 数据库主从切换
09:05 - 缓存命中率骤降(95%→20%)
09:10 - API网关超时率上升
09:15 - 下游服务开始熔断
09:20 - 用户大量报错

请分析:
1. 完整的因果链是什么？
2. 哪些是直接原因，哪些是间接原因？
3. 如何打破这个因果链防止再次发生？
4. 设计监控预警方案""",
            "expected_steps": [
                "causal_chain_construction",
                "direct_indirect_classification",
                "chain_breaking_strategy",
                "monitoring_design"
            ],
            "max_score": 25,
            "criteria": {
                "causal_chain_construction": 7,
                "direct_indirect_classification": 6,
                "chain_breaking_strategy": 6,
                "monitoring_design": 6
            }
        },
        {
            "name": "辛普森悖论识别",
            "scenario": """两组治疗方案的数据:
方案A: 整体治愈率60%, 轻型患者治愈率90%, 重型患者治愈率30%
方案B: 整体治愈率55%, 轻型患者治愈率95%, 重型患者治愈率35%

轻型患者占比: 方案A 80%, 方案B 30%

请分析:
1. 哪个方案整体治愈率更高？
2. 哪个方案对轻型患者更好？对重型患者更好？
3. 这是否构成辛普森悖论？
4. 在实际决策中应如何选择？""",
            "expected_steps": [
                "overall_comparison",
                "subgroup_comparison",
                "paradox_identification",
                "decision_guidance"
            ],
            "max_score": 25,
            "criteria": {
                "overall_comparison": 6,
                "subgroup_comparison": 7,
                "paradox_identification": 7,
                "decision_guidance": 5
            }
        },
    ],
}


class ReasoningEvaluator:
    """通用推理评估器 - 增强版"""

    def __init__(self, client: LMStudioClient, config=None, category_weights=None,
                 include_practical=True):
        self.client = client
        self.config = config
        self.category_weights = category_weights or {}
        self.include_practical = include_practical

    @staticmethod
    def _safe_content(content) -> str:
        """安全获取响应内容，处理 None/空值，并提取 thinking block 中的推理内容"""
        if content is None:
            return ""
        text = str(content).strip()
        return _extract_thinking_content(text)

    async def evaluate(self, model: str, temperature: float = 0.0,
                       max_tokens: int = 2048, include_practical: bool = True) -> List[CategoryScore]:
        """执行完整的通用推理评估
        
        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            include_practical: 是否包含面向实际应用的测试
        """
        categories = []

        # 1. 逻辑推理 (基础)
        logic_score = await self._evaluate_logic(model, temperature, max_tokens)
        categories.append(logic_score)

        # 2. 知识理解 (基础)
        ku_score = await self._evaluate_knowledge_understanding(model, temperature, max_tokens)
        categories.append(ku_score)

        # 3. 数学能力 (基础)
        math_score = await self._evaluate_math(model, temperature, max_tokens)
        categories.append(math_score)

        # 4. 推理链验证 (实际应用)
        if include_practical:
            cot_score = await self._evaluate_chain_of_thought(model, temperature, max_tokens)
            categories.append(cot_score)

        # 5. 业务场景推理 (实际应用)
        if include_practical:
            business_score = await self._evaluate_business_reasoning(model, temperature, max_tokens)
            categories.append(business_score)

        # 6. 代码逻辑推理 (实际应用)
        if include_practical:
            code_score = await self._evaluate_code_reasoning(model, temperature, max_tokens)
            categories.append(code_score)

        # 7. 自我修正能力 (实际应用)
        if include_practical:
            correction_score = await self._evaluate_self_correction(model, temperature, max_tokens)
            categories.append(correction_score)

        # 8. 多步决策推理 (实际应用)
        if include_practical:
            decision_score = await self._evaluate_multi_step_decision(model, temperature, max_tokens)
            categories.append(decision_score)

        # 9. 因果推理 (实际应用)
        if include_practical:
            causal_score = await self._evaluate_causal_reasoning(model, temperature, max_tokens)
            categories.append(causal_score)

        return categories

    # ============================================================
    # 基础评估方法
    # ============================================================

    async def _evaluate_logic(self, model: str, temperature: float,
                               max_tokens: int) -> CategoryScore:
        """评估逻辑推理"""
        tests = REASONING_BENCHMARKS["logic"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个逻辑推理专家。请仔细分析问题，给出清晰的推理过程和结论。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_logic(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="逻辑推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.15
        )

    async def _evaluate_knowledge_understanding(self, model: str, temperature: float,
                                               max_tokens: int) -> CategoryScore:
        """评估知识理解（支持阅读理解+知识问答两种格式）"""
        tests = REASONING_BENCHMARKS["knowledge_understanding"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            # 格式 1: 阅读理解类 (有 passage + questions + expected_answers)
            if "passage" in test and "questions" in test:
                questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(test["questions"]))
                prompt = f"请阅读以下文章并回答问题:\n\n{test['passage']}\n\n问题:\n{questions_text}"
                sys_msg = "你是一个阅读理解专家。请根据文章内容准确回答问题，引用文章中的关键信息。"
            # 格式 2: 知识问答类 (有 prompt + expected_keywords)
            elif "prompt" in test:
                prompt = test["prompt"]
                sys_msg = "你是一个知识专家。请根据问题准确回答，提供相关的知识和解释。"
            else:
                continue

            messages = [
                ChatMessage(role="system", content=sys_msg),
                ChatMessage(role="user", content=prompt)
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_knowledge_understanding(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="知识理解",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.13
        )

    async def _evaluate_math(self, model: str, temperature: float,
                              max_tokens: int) -> CategoryScore:
        """评估数学能力"""
        tests = REASONING_BENCHMARKS["math"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个数学专家。请给出详细的计算过程和最终答案。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_math(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="数学能力",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.10
        )

    # ============================================================
    # 实际应用评估方法
    # ============================================================

    async def _evaluate_chain_of_thought(self, model: str, temperature: float,
                                          max_tokens: int) -> CategoryScore:
        """评估推理链验证 (Chain-of-Thought)"""
        tests = REASONING_BENCHMARKS_PRACTICAL["chain_of_thought"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个严谨的数学和算法专家。请给出完整的推理过程，确保每一步都清晰可验证。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_chain_of_thought(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="推理链验证",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.10
        )

    async def _evaluate_business_reasoning(self, model: str, temperature: float,
                                            max_tokens: int) -> CategoryScore:
        """评估业务场景推理"""
        tests = REASONING_BENCHMARKS_PRACTICAL["business_reasoning"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个资深系统架构师和故障排查专家。请系统性地分析问题，给出专业的解决方案。"),
                ChatMessage(role="user", content=test["scenario"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_business_reasoning(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="业务场景推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.10
        )

    async def _evaluate_code_reasoning(self, model: str, temperature: float,
                                        max_tokens: int) -> CategoryScore:
        """评估代码逻辑推理"""
        tests = REASONING_BENCHMARKS_PRACTICAL["code_reasoning"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个代码分析和优化专家。请深入分析代码问题，给出专业的优化建议。"),
                ChatMessage(role="user", content=f"```python\n{test['code']}\n```\n\n{test['question']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_reasoning(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码逻辑推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.08
        )

    async def _evaluate_self_correction(self, model: str, temperature: float,
                                         max_tokens: int) -> CategoryScore:
        """评估自我修正能力"""
        tests = REASONING_BENCHMARKS_PRACTICAL["self_correction"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个批判性思维专家。请仔细分析给定的推理，识别错误并给出正确结论。"),
                ChatMessage(role="user", content=test.get("initial_wrong", test.get("scenario", "")))
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_self_correction(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="自我修正能力",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.06
        )

    async def _evaluate_multi_step_decision(self, model: str, temperature: float,
                                             max_tokens: int) -> CategoryScore:
        """评估多步决策推理"""
        tests = REASONING_BENCHMARKS_PRACTICAL["multi_step_decision"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个项目管理专家。请系统性地分析问题，给出合理的决策方案。"),
                ChatMessage(role="user", content=test["scenario"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_multi_step_decision(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="多步决策推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.10
        )

    async def _evaluate_causal_reasoning(self, model: str, temperature: float,
                                          max_tokens: int) -> CategoryScore:
        """评估因果推理"""
        tests = REASONING_BENCHMARKS_PRACTICAL["causal_reasoning"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个数据分析和因果推理专家。请准确区分相关性和因果性，给出严谨的推理。请直接输出分析内容，不要使用  thinking  标签。"),
                ChatMessage(role="user", content=test["scenario"])
            ]

            try:
                result = await self.client.chat_completion(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens
                )
                score, detail = self._score_causal_reasoning(self._safe_content(result.content), test)
            except Exception as e:
                error_msg = str(e)
                if "HTTP 400" in error_msg or "Failed to parse" in error_msg:
                    score, detail = 0, {"name": test["name"], "score": 0, "max_score": test["max_score"],
                                         "error": f"模型输出格式异常: {error_msg[:80]}"}
                else:
                    score, detail = 0, {"name": test["name"], "score": 0, "max_score": test["max_score"],
                                         "error": str(e)[:100]}

            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="因果推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.08
        )

    # ============================================================
    # 基础评分方法
    # ============================================================

    def _score_logic(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分逻辑推理 — 支持语义等价评分"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        expected = test.get("expected_answer", "")
        if expected:
            primary_match = expected in response
            semantic_matches = {
                "懂": ["是的", "正确", "成立", "true", "yes", "对的", "确实懂", "必然懂"],
                "没有下雨": ["未下雨", "没有下", "不是下雨", "否", "no", "未下", "不可能下雨"],
            }
            semantic_hit = False
            if expected in semantic_matches:
                semantic_hit = any(kw in response for kw in semantic_matches[expected])
            if primary_match:
                scores["correct_answer"] = criteria.get("correct_answer", 0)
            elif semantic_hit:
                scores["correct_answer"] = round(criteria.get("correct_answer", 0) * 0.85)
            else:
                keywords = test.get("expected_keywords", [])
                found = sum(1 for kw in keywords if kw in response)
                ratio = found / max(len(keywords), 1)
                scores["correct_answer"] = round(criteria.get("correct_answer", 0) * ratio)
        else:
            keywords = test.get("expected_keywords", [])
            found = sum(1 for kw in keywords if kw in response)
            ratio = found / max(len(keywords), 1)
            scores["correct_answer"] = round(criteria.get("correct_answer", 0) * ratio)
        total += scores.get("correct_answer", 0)

        reasoning_kw = ["因为", "所以", "由于", "因此", "根据", "because", "therefore", "since", "thus", "可知", "推出", "得出", "可得", "故"]
        has_reasoning = any(kw in response for kw in reasoning_kw)
        scores["reasoning_process"] = criteria.get("reasoning_process", 0) if has_reasoning else round(criteria.get("reasoning_process", 0) * 0.3)
        total += scores["reasoning_process"]

        if "logical_clarity" in criteria or "logical_validity" in criteria:
            key = "logical_clarity" if "logical_clarity" in criteria else "logical_validity"
            clarity_kw = ["逆否", "否定后件", "modus", "tollens", "contrapositive", "逻辑", "推导", "推理", "蕴含", "implication", "逆否命题"]
            found = sum(1 for kw in clarity_kw if kw in response)
            scores[key] = min(criteria[key], found * 2)
            total += scores[key]

        if "eve_leftmost" in criteria:
            scores["eve_leftmost"] = criteria["eve_leftmost"] if "Eve" in response and ("最左" in response or "第一个" in response or "leftmost" in response.lower() or "位置1" in response) else 0
            total += scores["eve_leftmost"]

            scores["bob_carol_adjacent"] = criteria["bob_carol_adjacent"] if "Bob" in response and "Carol" in response else 0
            total += scores["bob_carol_adjacent"]

            scores["alice_not_ends"] = criteria["alice_not_ends"] if "Alice" in response else 0
            total += scores["alice_not_ends"]

            scores["dave_not_near_alice"] = criteria["dave_not_near_alice"] if "Dave" in response else 0
            total += scores["dave_not_near_alice"]

            scores["complete_arrangement"] = criteria["complete_arrangement"] if all(n in response for n in ["Alice", "Bob", "Carol", "Dave", "Eve"]) else 0
            total += scores["complete_arrangement"]

        remaining_criteria = {k: v for k, v in criteria.items() if k not in scores}
        if remaining_criteria:
            criteria_keywords_map = {
                "truth_table": ["真值表", "truth table", "P Q", "T F", "真", "假", "true", "false", "P ∧ Q", "P ∨ Q", "P | Q"],
                "natural_deduction": ["自然推理", "自然演绎", "natural deduction", "推理规则", "推导", "proof", "证明", "蕴涵", "蕴含", "分配律", "distributive"],
                "application_example": ["应用", "示例", "例子", "例如", "example", "应用场景", "具体", "实例", "场景", "实际"],
                "pattern_identification": ["规律", "pattern", "质数", "素数", "数列", "生成", "识别", "发现", "prime", "sequence"],
                "verification": ["验证", "检验", "验证", "成立", "verif", "正确", "确认", "检查", "符合", "满足"],
                "counterexample_or_proof": ["反例", "counterexample", "证明", "proof", "不成立", "推翻", "反驳", "不是质数", "不符合", "counter"],
                "induction_limitation": ["局限", "limitation", "归纳", "induction", "不完备", "不完整", "推广", "generalize", "不能", "不一定", "并非总是"],
            }
            keywords = test.get("expected_keywords", [])
            for c_key, max_score in remaining_criteria.items():
                specific_kws = criteria_keywords_map.get(c_key, keywords if isinstance(keywords, list) else [])
                if specific_kws:
                    found = sum(1 for kw in specific_kws if kw.lower() in response.lower())
                    ratio = found / max(len(specific_kws), 1)
                    scores[c_key] = round(max_score * min(ratio * 2.5, 1.0))
                else:
                    scores[c_key] = 0
                total += scores[c_key]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_knowledge_understanding(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分知识理解 — 支持阅读理解和知识问答的统一评分"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # 阅读理解类测试（有 expected_answers）
        if "expected_answers" in test:
            for i, (expected_kws, criteria_key) in enumerate(zip(test["expected_answers"], criteria)):
                if isinstance(expected_kws, list):
                    found = sum(1 for kw in expected_kws if kw in response)
                    ratio = found / max(len(expected_kws), 1)
                    scores[criteria_key] = round(criteria[criteria_key] * min(ratio, 1.0))
                total += scores.get(criteria_key, 0)

        # 知识问答类测试（有 expected_keywords）
        elif isinstance(test.get("expected_keywords"), dict):
            semantic_extensions = {
                "CAP": ["不可能同时", "三者取其二", "trade-off", "权衡", "取舍", "CPA", "网络分区"],
                "最终一致性": ["弱一致性", "weak consistency", "异步复制", "async replication", "延迟同步", " eventual", "最终达到一致"],
                "幂等性": ["重复执行", "多次调用", "repeated call", "同一结果", "same effect", "无副作用", "no side effect"],
                "断路器": ["熔断器", "circuit breaker", "降级", "degradation", "fallback", "容错", "fault tolerance", "fail-fast"],
            }
            for concept, keywords in test["expected_keywords"].items():
                criteria_key = None
                for ck in criteria:
                    if concept.replace(" ", "_").lower() in ck.lower() or ck.lower() in concept.lower():
                        criteria_key = ck
                        break
                if criteria_key is None:
                    idx = list(test["expected_keywords"].keys()).index(concept)
                    criteria_key = list(criteria.keys())[idx] if idx < len(criteria) else None

                if criteria_key:
                    found = sum(1 for kw in keywords if kw in response)
                    ratio = found / max(len(keywords), 1)
                    score = round(criteria[criteria_key] * min(ratio, 1.0))
                    if score == 0 and concept in semantic_extensions:
                        ext_kws = semantic_extensions[concept]
                        ext_found = sum(1 for kw in ext_kws if kw.lower() in response.lower())
                        if ext_found > 0:
                            score = round(criteria[criteria_key] * min(ext_found / len(ext_kws) * 0.7, 1.0))
                    scores[criteria_key] = score
                    total += scores[criteria_key]

        elif isinstance(test.get("expected_keywords"), list):
            for i, keywords in enumerate(test["expected_keywords"]):
                criteria_key = list(criteria.keys())[i] if i < len(criteria) else None
                if criteria_key:
                    found = sum(1 for kw in keywords if kw in response)
                    ratio = found / max(len(keywords), 1)
                    scores[criteria_key] = round(criteria[criteria_key] * min(ratio, 1.0))
                    total += scores[criteria_key]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_math(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分数学能力"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # 检查复杂度分析
        if "correct_complexity" in criteria:
            expected = test.get("expected_answer", "")
            if expected.upper() in response.upper() or expected.replace("^", "**") in response:
                scores["correct_complexity"] = criteria["correct_complexity"]
            elif "O(n" in response:
                scores["correct_complexity"] = round(criteria["correct_complexity"] * 0.5)
            else:
                scores["correct_complexity"] = 0
            total += scores["correct_complexity"]

        if "analysis_process" in criteria:
            has_process = any(kw in response for kw in ["循环", "嵌套", "n(n-1)", "n*(n-1)", "loop", "nested", "i从0到n", "j从i到n"])
            scores["analysis_process"] = criteria["analysis_process"] if has_process else round(criteria["analysis_process"] * 0.3)
            total += scores["analysis_process"]

        if "space_complexity" in criteria:
            has_space = any(kw in response for kw in ["O(1)", "O(n)", "空间", "space", "常数", "constant"])
            scores["space_complexity"] = criteria["space_complexity"] if has_space else 0
            total += scores["space_complexity"]

        # 概率计算
        if "both_red" in criteria:
            expected = test.get("expected_answers", {})
            for key, expected_val in expected.items():
                if key in criteria:
                    # 检查是否包含正确答案
                    normalized = expected_val.replace("/", "除以").replace(" ", "")
                    if expected_val in response or normalized in response:
                        scores[key] = criteria[key]
                    else:
                        # 数值等价性比较：使用安全解析
                        try:
                            expected_num = _safe_parse_numeric(expected_val)
                            found_numbers = re.findall(r'\d+/\d+|\d+\.\d+', response)
                            numeric_match = False
                            for num_str in found_numbers:
                                try:
                                    num_val = _safe_parse_numeric(num_str)
                                    if num_val is not None and expected_num is not None and abs(num_val - expected_num) < 0.01:
                                        numeric_match = True
                                        break
                                except Exception:
                                    pass
                            scores[key] = round(criteria[key] * 0.5) if numeric_match else 0
                        except Exception:
                            scores[key] = 0
                    total += scores.get(key, 0)

        # 数学建模
        if "q1_projection" in criteria:
            # 检查是否有计算过程和合理结果
            has_formula = any(kw in response for kw in ["10000", "1.05", "增长", "公式", "formula", "指数"])
            # 数值等价性检查：10000 * 1.05^30 = 43219.43...
            has_result = False
            try:
                numbers_in_response = re.findall(r'[\d]+\.[\d]+|[\d]+', response)
                for num_str in numbers_in_response:
                    try:
                        num_val = float(num_str)
                        if 43000 <= num_val <= 43300:  # 允许合理误差范围
                            has_result = True
                            break
                    except:
                        pass
            except:
                pass
            # 也检查中文近似表达
            if not has_result:
                has_result = any(kw in response for kw in ["约4.3万", "4.3万", "43219", "43220"])
            scores["q1_projection"] = criteria["q1_projection"] if has_formula and has_result else (round(criteria["q1_projection"] * 0.5) if has_formula else 0)
            total += scores["q1_projection"]

            has_days = any(kw in response for kw in ["47", "48", "天", "days"])
            scores["q2_days_needed"] = criteria["q2_days_needed"] if has_days else round(criteria["q2_days_needed"] * 0.3)
            total += scores["q2_days_needed"]

            has_rate = any(kw in response for kw in ["增长率", "8.3", "0.083", "8%", "rate"])
            scores["q3_growth_rate"] = criteria["q3_growth_rate"] if has_rate else round(criteria["q3_growth_rate"] * 0.3)
            total += scores["q3_growth_rate"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    # ============================================================
    # 实际应用评分方法
    # ============================================================

    def _score_chain_of_thought(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分推理链验证"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        expected_steps = test.get("expected_steps", [])
        step_keywords = test.get("step_keywords", {})
        response_lower = response.lower()

        # 检查每个推理步骤
        for step in expected_steps:
            if step in criteria:
                keywords = step_keywords.get(step, [])
                found = sum(1 for kw in keywords if kw.lower() in response_lower)
                ratio = found / max(len(keywords), 1)
                scores[step] = round(criteria[step] * min(ratio, 1.0))
                total += scores[step]

        # 额外检查推理结构完整性
        structure_keywords = ["首先", "其次", "然后", "最后", "第一步", "第二步", "总结", "first", "second", "then", "finally", "step 1", "step 2"]
        structure_count = sum(1 for kw in structure_keywords if kw in response_lower)
        
        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "structure_indicators": structure_count
        }
        return total, detail

    def _score_business_reasoning(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分业务场景推理"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        response_lower = response.lower()

        # 症状分析
        if "symptom_analysis" in criteria:
            symptom_kw = ["症状", "现象", "表现", "symptom", "manifestation", "indicator"]
            found = sum(1 for kw in symptom_kw if kw in response_lower)
            scores["symptom_analysis"] = min(criteria["symptom_analysis"], found * 2)
            total += scores["symptom_analysis"]

        # 根因识别
        if "root_cause_identification" in criteria:
            cause_kw = ["原因", "根因", "cause", "root", "瓶颈", "bottleneck", "问题"]
            found = sum(1 for kw in cause_kw if kw in response_lower)
            scores["root_cause_identification"] = min(criteria["root_cause_identification"], found * 2)
            total += scores["root_cause_identification"]

        # 验证计划
        if "verification_plan" in criteria:
            verify_kw = ["验证", "检查", "测试", "verify", "check", "test", "排查"]
            found = sum(1 for kw in verify_kw if kw in response_lower)
            scores["verification_plan"] = min(criteria["verification_plan"], found * 2)
            total += scores["verification_plan"]

        # 解决方案
        if "solution_proposal" in criteria:
            solution_kw = ["解决", "方案", "优化", "改进", "solution", "optimize", "improve"]
            found = sum(1 for kw in solution_kw if kw in response_lower)
            scores["solution_proposal"] = min(criteria["solution_proposal"], found * 2)
            total += scores["solution_proposal"]

        # 预防措施
        if "prevention_measures" in criteria:
            prevent_kw = ["预防", "避免", "监控", "prevent", "avoid", "monitor", "alert"]
            found = sum(1 for kw in prevent_kw if kw in response_lower)
            scores["prevention_measures"] = min(criteria["prevention_measures"], found * 2)
            total += scores["prevention_measures"]

        # 架构设计相关
        if "architecture_design" in criteria:
            arch_kw = ["架构", "部署", "集群", "replica", "partition", "sharding"]
            found = sum(1 for kw in arch_kw if kw in response_lower)
            scores["architecture_design"] = min(criteria["architecture_design"], found * 2)
            total += scores["architecture_design"]

        # 风险评估
        if "risk_assessment" in criteria:
            risk_kw = ["风险", "缺点", "问题", "risk", "drawback", "issue", "trade-off"]
            found = sum(1 for kw in risk_kw if kw in response_lower)
            scores["risk_assessment"] = min(criteria["risk_assessment"], found * 2)
            total += scores["risk_assessment"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_code_reasoning(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分代码逻辑推理"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        response_lower = response.lower()

        # 问题识别
        if "problem_identification" in criteria:
            problem_kw = ["问题", "性能", "阻塞", "慢", "效率", "瓶颈", "problem", "performance", "blocking", "slow"]
            found = sum(1 for kw in problem_kw if kw in response_lower)
            scores["problem_identification"] = min(criteria["problem_identification"], found * 2)
            total += scores["problem_identification"]

        # 性能影响
        if "performance_impact" in criteria:
            impact_kw = ["复杂度", "O(n)", "时间", "空间", "complexity", "time", "space", "memory"]
            found = sum(1 for kw in impact_kw if kw in response_lower)
            scores["performance_impact"] = min(criteria["performance_impact"], found * 2)
            total += scores["performance_impact"]

        # 优化方案
        if "optimization_solution" in criteria:
            opt_kw = ["优化", "改进", "asyncio", "gather", "并发", "并行", "optimize", "improve", "concurrent", "parallel"]
            found = sum(1 for kw in opt_kw if kw in response_lower)
            scores["optimization_solution"] = min(criteria["optimization_solution"], found * 2)
            total += scores["optimization_solution"]

        # 性能对比
        if "performance_comparison" in criteria:
            compare_kw = ["对比", "提升", "加速", "倍", "compare", "improvement", "speedup", "x faster"]
            found = sum(1 for kw in compare_kw if kw in response_lower)
            scores["performance_comparison"] = min(criteria["performance_comparison"], found * 3)
            total += scores["performance_comparison"]

        # 并发问题
        if "concurrency_issues" in criteria:
            concurrency_kw = ["竞态", "race", "线程安全", "锁", "lock", "mutex", "同步", "sync"]
            found = sum(1 for kw in concurrency_kw if kw in response_lower)
            scores["concurrency_issues"] = min(criteria["concurrency_issues"], found * 2)
            total += scores["concurrency_issues"]

        # 后果分析
        if "consequence_analysis" in criteria:
            consequence_kw = ["结果", "后果", "导致", "result", "consequence", "lead to", "cause"]
            found = sum(1 for kw in consequence_kw if kw in response_lower)
            scores["consequence_analysis"] = min(criteria["consequence_analysis"], found * 2)
            total += scores["consequence_analysis"]

        # 复杂度分析
        if "complexity_analysis" in criteria:
            complexity_kw = ["O(", "复杂度", "complexity", "线性", "平方", "对数", "linear", "quadratic", "log"]
            found = sum(1 for kw in complexity_kw if kw in response_lower)
            scores["complexity_analysis"] = min(criteria["complexity_analysis"], found * 2)
            total += scores["complexity_analysis"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_self_correction(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分自我修正能力"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        response_lower = response.lower()

        # 错误识别
        if "error_identification" in criteria:
            error_kw = ["错误", "不对", "有问题", "error", "wrong", "incorrect", "mistake"]
            found = sum(1 for kw in error_kw if kw in response_lower)
            scores["error_identification"] = min(criteria["error_identification"], found * 2)
            total += scores["error_identification"]

        # 解释
        if "explanation" in criteria:
            explain_kw = ["因为", "原因", "应该", "正确", "because", "reason", "should", "correct"]
            found = sum(1 for kw in explain_kw if kw in response_lower)
            scores["explanation"] = min(criteria["explanation"], found * 2)
            total += scores["explanation"]

        # 正确推理
        if "correct_reasoning" in criteria:
            reasoning_kw = ["正确", "实际上", "事实上", "correct", "actually", "in fact", "properly"]
            found = sum(1 for kw in reasoning_kw if kw in response_lower)
            scores["correct_reasoning"] = min(criteria["correct_reasoning"], found * 2)
            total += scores["correct_reasoning"]

        # 正确答案
        if "correct_answer" in criteria:
            # 检查是否有数值计算或明确结论
            has_calculation = bool(re.search(r'\d+\.?\d*', response))
            has_conclusion = any(kw in response_lower for kw in ["答案", "结果", "answer", "result", "因此"])
            scores["correct_answer"] = criteria["correct_answer"] if has_calculation and has_conclusion else round(criteria["correct_answer"] * 0.5)
            total += scores["correct_answer"]

        # 谬误识别
        if "fallacy_identification" in criteria:
            fallacy_primary = ["谬误", "错误推理", "逻辑错误", "fallacy", "hasty generalization", "false cause"]
            fallacy_semantic = [
                "以偏概全", "overgeneraliz", "草率", "仓促", "片面",
                "不成立", "invalid", "不严谨", "不充分", "insufficient",
                "过度推广", "过度延伸", "样本不足", "不具代表性",
            ]
            primary_found = any(kw in response_lower for kw in fallacy_primary)
            semantic_found = any(kw in response_lower for kw in fallacy_semantic)
            if primary_found:
                scores["fallacy_identification"] = criteria["fallacy_identification"]
            elif semantic_found:
                scores["fallacy_identification"] = round(criteria["fallacy_identification"] * 0.7)
            else:
                scores["fallacy_identification"] = 0
            total += scores["fallacy_identification"]

        # 评估框架
        if "evaluation_framework" in criteria:
            framework_kw = ["框架", "标准", "评估", "framework", "criteria", "evaluate", "assess"]
            found = sum(1 for kw in framework_kw if kw in response_lower)
            scores["evaluation_framework"] = min(criteria["evaluation_framework"], found * 2)
            total += scores["evaluation_framework"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_multi_step_decision(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分多步决策推理"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        response_lower = response.lower()

        # 工作量计算
        if "workload_calculation" in criteria:
            workload_kw = ["小时", "天", "工作量", "计算", "hour", "day", "workload", "calculation"]
            found = sum(1 for kw in workload_kw if kw in response_lower)
            scores["workload_calculation"] = min(criteria["workload_calculation"], found * 2)
            total += scores["workload_calculation"]

        # 优先级排序
        if "priority_sorting" in criteria:
            priority_kw = ["优先级", "重要", "紧急", "priority", "important", "urgent", "排序"]
            found = sum(1 for kw in priority_kw if kw in response_lower)
            scores["priority_sorting"] = min(criteria["priority_sorting"], found * 2)
            total += scores["priority_sorting"]

        # 资源分配
        if "resource_allocation" in criteria:
            resource_kw = ["分配", "人员", "资源", "allocate", "assign", "resource", "personnel"]
            found = sum(1 for kw in resource_kw if kw in response_lower)
            scores["resource_allocation"] = min(criteria["resource_allocation"], found * 2)
            total += scores["resource_allocation"]

        # 风险评估
        if "risk_assessment" in criteria:
            risk_kw = ["风险", "问题", "应对", "risk", "issue", "mitigate", "handle"]
            found = sum(1 for kw in risk_kw if kw in response_lower)
            scores["risk_assessment"] = min(criteria["risk_assessment"], found * 2)
            total += scores["risk_assessment"]

        # 影响评估
        if "impact_assessment" in criteria:
            impact_kw = ["影响", "后果", "严重", "impact", "consequence", "severity"]
            found = sum(1 for kw in impact_kw if kw in response_lower)
            scores["impact_assessment"] = min(criteria["impact_assessment"], found * 2)
            total += scores["impact_assessment"]

        # 短期计划
        if "short_term_plan" in criteria:
            short_kw = ["短期", "立即", "现在", "short-term", "immediate", "now"]
            found = sum(1 for kw in short_kw if kw in response_lower)
            scores["short_term_plan"] = min(criteria["short_term_plan"], found * 2)
            total += scores["short_term_plan"]

        # 长期计划
        if "long_term_plan" in criteria:
            long_kw = ["长期", "未来", "规划", "long-term", "future", "plan"]
            found = sum(1 for kw in long_kw if kw in response_lower)
            scores["long_term_plan"] = min(criteria["long_term_plan"], found * 2)
            total += scores["long_term_plan"]

        # 平衡策略
        if "balance_strategy" in criteria:
            balance_kw = ["平衡", "权衡", "取舍", "balance", "trade-off", "compromise"]
            found = sum(1 for kw in balance_kw if kw in response_lower)
            scores["balance_strategy"] = min(criteria["balance_strategy"], found * 2)
            total += scores["balance_strategy"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_causal_reasoning(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分因果推理"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        response_lower = response.lower()

        # 相关性vs因果性
        if "correlation_vs_causation" in criteria:
            corr_kw = ["相关", "因果", "correlation", "causation", "因果性", "相关性"]
            found = sum(1 for kw in corr_kw if kw in response_lower)
            scores["correlation_vs_causation"] = min(criteria["correlation_vs_causation"], found * 3)
            total += scores["correlation_vs_causation"]

        # 区分方法
        if "differentiation_method" in criteria:
            diff_kw = ["实验", "控制", "变量", "experiment", "control", "variable", "对照"]
            found = sum(1 for kw in diff_kw if kw in response_lower)
            scores["differentiation_method"] = min(criteria["differentiation_method"], found * 2)
            total += scores["differentiation_method"]

        # 避免误判
        if "avoiding_misjudgment" in criteria:
            avoid_kw = ["误判", "混淆", "错误", "misjudgment", "confound", "spurious"]
            found = sum(1 for kw in avoid_kw if kw in response_lower)
            scores["avoiding_misjudgment"] = min(criteria["avoiding_misjudgment"], found * 2)
            total += scores["avoiding_misjudgment"]

        # 实验设计
        if "experimental_design" in criteria:
            exp_kw = ["实验", "设计", "假设", "验证", "experiment", "design", "hypothesis", "validate"]
            found = sum(1 for kw in exp_kw if kw in response_lower)
            scores["experimental_design"] = min(criteria["experimental_design"], found * 2)
            total += scores["experimental_design"]

        # 可能原因
        if "possible_causes" in criteria:
            cause_kw = ["原因", "可能", "导致", "cause", "possible", "lead to"]
            found = sum(1 for kw in cause_kw if kw in response_lower)
            scores["possible_causes"] = min(criteria["possible_causes"], found * 2)
            total += scores["possible_causes"]

        # 验证方法
        if "verification_methods" in criteria:
            verify_kw = ["验证", "检查", "测试", "verify", "check", "test", "inspect"]
            found = sum(1 for kw in verify_kw if kw in response_lower)
            scores["verification_methods"] = min(criteria["verification_methods"], found * 2)
            total += scores["verification_methods"]

        # 根因识别
        if "root_cause_identification" in criteria:
            root_kw = ["根因", "根本原因", "root cause", "underlying", "本质"]
            found = sum(1 for kw in root_kw if kw in response_lower)
            scores["root_cause_identification"] = min(criteria["root_cause_identification"], found * 3)
            total += scores["root_cause_identification"]

        # 修复方案
        if "fix_proposal" in criteria:
            fix_kw = ["修复", "解决", "方案", "fix", "solution", "resolve"]
            found = sum(1 for kw in fix_kw if kw in response_lower)
            scores["fix_proposal"] = min(criteria["fix_proposal"], found * 2)
            total += scores["fix_proposal"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail
