"""
通用推理评估模块
评估维度: 逻辑推理、阅读理解、数学能力、知识问答
"""

import re
from typing import Dict, Any, List, Tuple
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


# ============================================================
# 通用推理测试题库
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
    ],
    "reading_comprehension": [
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
    "knowledge": [
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
    ]
}


class ReasoningEvaluator:
    """通用推理评估器"""

    def __init__(self, client: LMStudioClient, config=None):
        self.client = client
        self.config = config

    async def evaluate(self, model: str, temperature: float = 0.0,
                       max_tokens: int = 2048) -> List[CategoryScore]:
        """执行完整的通用推理评估"""
        categories = []

        # 1. 逻辑推理
        logic_score = await self._evaluate_logic(model, temperature, max_tokens)
        categories.append(logic_score)

        # 2. 阅读理解
        rc_score = await self._evaluate_reading_comprehension(model, temperature, max_tokens)
        categories.append(rc_score)

        # 3. 数学能力
        math_score = await self._evaluate_math(model, temperature, max_tokens)
        categories.append(math_score)

        # 4. 知识问答
        knowledge_score = await self._evaluate_knowledge(model, temperature, max_tokens)
        categories.append(knowledge_score)

        return categories

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

            score, detail = self._score_logic(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="逻辑推理",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
        )

    async def _evaluate_reading_comprehension(self, model: str, temperature: float,
                                              max_tokens: int) -> CategoryScore:
        """评估阅读理解"""
        tests = REASONING_BENCHMARKS["reading_comprehension"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(test["questions"]))
            prompt = f"请阅读以下文章并回答问题:\n\n{test['passage']}\n\n问题:\n{questions_text}"

            messages = [
                ChatMessage(role="system", content="你是一个阅读理解专家。请根据文章内容准确回答问题，引用文章中的关键信息。"),
                ChatMessage(role="user", content=prompt)
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_reading_comprehension(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="阅读理解",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
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

            score, detail = self._score_math(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="数学能力",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
        )

    async def _evaluate_knowledge(self, model: str, temperature: float,
                                   max_tokens: int) -> CategoryScore:
        """评估知识问答"""
        tests = REASONING_BENCHMARKS["knowledge"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个技术知识专家。请准确、简洁地回答问题。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_knowledge(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="知识问答",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
        )

    # ============================================================
    # 评分方法
    # ============================================================

    def _score_logic(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分逻辑推理"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # 检查正确答案
        expected = test.get("expected_answer", "")
        if expected and expected in response:
            scores["correct_answer"] = criteria.get("correct_answer", 0)
        elif expected:
            # 部分匹配
            scores["correct_answer"] = round(criteria.get("correct_answer", 0) * 0.5)
        else:
            # 检查预期关键词
            keywords = test.get("expected_keywords", [])
            found = sum(1 for kw in keywords if kw in response)
            ratio = found / max(len(keywords), 1)
            scores["correct_answer"] = round(criteria.get("correct_answer", 0) * ratio)
        total += scores.get("correct_answer", 0)

        # 推理过程
        reasoning_kw = ["因为", "所以", "由于", "因此", "根据", "because", "therefore", "since", "thus"]
        has_reasoning = any(kw in response for kw in reasoning_kw)
        scores["reasoning_process"] = criteria.get("reasoning_process", 0) if has_reasoning else round(criteria.get("reasoning_process", 0) * 0.3)
        total += scores["reasoning_process"]

        # 逻辑清晰度
        if "logical_clarity" in criteria or "logical_validity" in criteria:
            key = "logical_clarity" if "logical_clarity" in criteria else "logical_validity"
            clarity_kw = ["逆否", "否定后件", "modus", "tollens", "contrapositive", "逻辑", "推导"]
            found = sum(1 for kw in clarity_kw if kw in response)
            scores[key] = min(criteria[key], found * 2)
            total += scores[key]

        # 复杂谜题特定评分
        if "eve_leftmost" in criteria:
            scores["eve_leftmost"] = criteria["eve_leftmost"] if "Eve" in response and ("最左" in response or "第一个" in response or "leftmost" in response.lower()) else 0
            total += scores["eve_leftmost"]

            scores["bob_carol_adjacent"] = criteria["bob_carol_adjacent"] if "Bob" in response and "Carol" in response else 0
            total += scores["bob_carol_adjacent"]

            scores["alice_not_ends"] = criteria["alice_not_ends"] if "Alice" in response else 0
            total += scores["alice_not_ends"]

            scores["dave_not_near_alice"] = criteria["dave_not_near_alice"] if "Dave" in response else 0
            total += scores["dave_not_near_alice"]

            scores["complete_arrangement"] = criteria["complete_arrangement"] if all(n in response for n in ["Alice", "Bob", "Carol", "Dave", "Eve"]) else 0
            total += scores["complete_arrangement"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_reading_comprehension(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分阅读理解"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        for i, (expected_kws, criteria_key) in enumerate(zip(test["expected_answers"], criteria)):
            if isinstance(expected_kws, list):
                found = sum(1 for kw in expected_kws if kw in response)
                ratio = found / max(len(expected_kws), 1)
                scores[criteria_key] = round(criteria[criteria_key] * min(ratio, 1.0))
            total += scores.get(criteria_key, 0)

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
                        # 检查是否有数值答案
                        numbers = re.findall(r'\d+/\d+|\d+\.\d+', response)
                        scores[key] = round(criteria[key] * 0.3) if numbers else 0
                    total += scores.get(key, 0)

        # 数学建模
        if "q1_projection" in criteria:
            # 检查是否有计算过程和合理结果
            has_formula = any(kw in response for kw in ["10000", "1.05", "增长", "公式", "formula", "指数"])
            has_result = any(kw in response for kw in ["43219", "43220", "43000", "约4.3万"])
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

    def _score_knowledge(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分知识问答"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        if "expected_keywords" in test:
            # 每个概念独立评分
            for concept, keywords in test["expected_keywords"].items():
                # 找到对应的 criteria key
                criteria_key = None
                for ck in criteria:
                    if concept.replace(" ", "_").lower() in ck.lower() or ck.lower() in concept.lower():
                        criteria_key = ck
                        break
                if criteria_key is None:
                    # 按顺序匹配
                    idx = list(test["expected_keywords"].keys()).index(concept)
                    criteria_key = list(criteria.keys())[idx] if idx < len(criteria) else None

                if criteria_key:
                    found = sum(1 for kw in keywords if kw in response)
                    ratio = found / max(len(keywords), 1)
                    scores[criteria_key] = round(criteria[criteria_key] * min(ratio, 1.0))
                    total += scores[criteria_key]

        elif "expected_keywords" not in test and "expected_keywords" in test:
            # 列表形式的预期关键词
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
