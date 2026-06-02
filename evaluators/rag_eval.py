"""
RAG评估模块 - 检索增强生成能力评估
评估维度: 检索准确率、生成质量、幻觉检测
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


RAG_BENCHMARKS = [
    {
        "name": "文档检索与回答",
        "context": """项目文档摘要:
- LLMtest v3.0 是一个本地LLM评估套件，支持多种评估维度
- 系统使用归一化评分公式: (score/max_score × 100) × weight
- 支持的评估维度: coding(0.30), agent(0.30), reasoning(0.25), performance(0.15)
- CLI入口: python run_eval.py eval --mode quick|standard|full
- 配置文件: config.yaml，支持权重配置和应用场景配置
- SQLite断点续传: utils/state_manager.py 管理评估状态持久化
- 报告格式: HTML, JSON, TXT 三种格式
- Docker支持: Dockerfile 和 docker-compose.yml 已提供""",
        "question": "LLMtest v3.0的评分公式是什么？支持哪些评估维度？",
        "expected_facts": ["归一化", "score/max_score", "coding", "agent", "reasoning", "performance"],
        "hallucination_traps": ["支持GPU加速", "支持分布式评估", "使用Redis存储", "支持GPT-4评估"],
        "max_score": 20,
        "criteria": {"retrieval_accuracy": 8, "generation_quality": 7, "hallucination_free": 5}
    },
    {
        "name": "代码库检索与解释",
        "context": """代码库结构:
- evaluators/coding.py: 代码能力评估，包含代码生成、补全、Debug等7个子类别
- evaluators/agent.py: Agent能力评估，包含工具调用、多轮对话、结构化输出等5个子类别
- evaluators/reasoning.py: 推理能力评估，包含数学推理、逻辑推理、因果推理等5个子类别
- utils/client.py: LM Studio API客户端，支持流式和非流式请求
- utils/score_engine.py: 评分引擎，负责评分计算和结果聚合
- utils/config.py: 配置管理，支持YAML配置文件加载""",
        "question": "代码能力评估器在哪个文件？它包含哪些子类别？",
        "expected_facts": ["coding.py", "代码生成", "补全", "Debug", "7个子类别"],
        "hallucination_traps": ["使用TensorFlow", "支持Jupyter Notebook", "包含图像识别", "基于LangChain"],
        "max_score": 20,
        "criteria": {"retrieval_accuracy": 8, "generation_quality": 7, "hallucination_free": 5}
    },
    {
        "name": "配置检索与修改建议",
        "context": """当前配置:
- 默认模型: loaded (使用LM Studio当前加载的模型)
- 温度: 0.0 (确定性输出)
- 最大token: 2048
- 评估模式: standard (包含coding+agent+reasoning)
- 权重: coding=0.30, agent=0.30, reasoning=0.25, performance=0.15
- 超时: 120秒
- 重试: 3次""",
        "question": "如何修改配置使评估包含性能测试？当前性能维度的权重是多少？",
        "expected_facts": ["performance", "0.15", "full", "模式"],
        "hallucination_traps": ["需要重启LM Studio", "修改需要编译", "权重固定不可改", "性能测试需要GPU"],
        "max_score": 20,
        "criteria": {"retrieval_accuracy": 8, "generation_quality": 7, "hallucination_free": 5}
    },
    {
        "name": "错误信息诊断",
        "context": """已知问题记录:
- HTTP 400错误: 模型输出包含控制字符(如\\x1a)，导致API解析失败
- 多轮对话KeyError: assistant消息缺少content字段
- 逻辑推理天花板效应: 当前题库难度不足，所有模型均接近100%
- API开发评分过严: 当前评分标准导致得分仅10%左右
- quick模式缺少Performance维度: quick模式不包含性能测试""",
        "question": "HTTP 400错误的原因是什么？如何修复？",
        "expected_facts": ["控制字符", "\\x1a", "API解析失败", "过滤", "sanitize"],
        "hallucination_traps": ["服务器内存不足", "需要升级LM Studio", "是网络问题", "需要更换模型"],
        "max_score": 20,
        "criteria": {"retrieval_accuracy": 8, "generation_quality": 7, "hallucination_free": 5}
    },
    {
        "name": "跨文档综合推理",
        "context": """文档A - 评估流程:
评估启动后，系统依次执行coding→agent→reasoning→performance四个维度。
每个维度包含多个子类别，子类别评分经归一化后加权聚合为维度分。
最终维度分按权重加权平均得到总分。

文档B - 报告生成:
评估完成后，系统生成HTML/JSON/TXT三种格式报告。
报告包含各维度详细评分、子类别分析、模型对比排行榜。
历史结果存储在results/目录下，支持跨次评估对比。

文档C - 断点续传:
评估过程通过SQLite数据库记录进度。
中断后重新运行时，已完成的维度会跳过，从断点处继续。
状态管理器位于utils/state_manager.py。""",
        "question": "如果评估在reasoning维度中断，重新运行时会怎样？结果如何保存？",
        "expected_facts": ["跳过", "coding", "agent", "断点", "续传", "SQLite", "results"],
        "hallucination_traps": ["需要从头开始", "数据会丢失", "使用Redis缓存", "不支持断点续传"],
        "max_score": 20,
        "criteria": {"retrieval_accuracy": 8, "generation_quality": 7, "hallucination_free": 5}
    },
]


class RAGEvaluator:
    """RAG评估器"""

    def __init__(self, client: LMStudioClient, config=None, category_weights=None,
                 include_practical=True):
        self.client = client
        self.config = config
        self.category_weights = category_weights or {}
        self.include_practical = include_practical

    @staticmethod
    def _safe_content(content) -> str:
        if content is None:
            return ""
        return str(content).strip()

    async def evaluate(self, model: str, temperature: float = 0.0,
                       max_tokens: int = 2048, include_practical: bool = True) -> List[CategoryScore]:
        categories = []
        categories.append(await self._evaluate_retrieval_accuracy(model, temperature, max_tokens))
        categories.append(await self._evaluate_generation_quality(model, temperature, max_tokens))
        categories.append(await self._evaluate_hallucination_detection(model, temperature, max_tokens))
        return categories

    async def _evaluate_retrieval_accuracy(self, model: str, temperature: float,
                                            max_tokens: int) -> CategoryScore:
        tests = RAG_BENCHMARKS
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个文档检索助手。请根据提供的上下文信息准确回答问题，不要编造上下文中没有的信息。"),
                ChatMessage(role="user", content=f"上下文:\n{test['context']}\n\n问题: {test['question']}")
            ]

            try:
                result = await self.client.chat_completion(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens
                )
                score, detail = self._score_retrieval(self._safe_content(result.content), test)
            except Exception as e:
                score = 0
                detail = {"name": test["name"], "score": 0, "max_score": test["criteria"]["retrieval_accuracy"],
                          "error": str(e)[:100]}

            total_score += score
            max_total += test["criteria"]["retrieval_accuracy"]
            details.append(detail)

        weight = self.category_weights.get("retrieval_accuracy", 0.35)
        return CategoryScore(category="检索准确率", score=total_score, max_score=max_total,
                             details=details, weight=weight)

    async def _evaluate_generation_quality(self, model: str, temperature: float,
                                            max_tokens: int) -> CategoryScore:
        tests = RAG_BENCHMARKS
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个文档检索助手。请根据提供的上下文信息准确回答问题，回答应完整、连贯、有条理。"),
                ChatMessage(role="user", content=f"上下文:\n{test['context']}\n\n问题: {test['question']}")
            ]

            try:
                result = await self.client.chat_completion(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens
                )
                score, detail = self._score_generation_quality(self._safe_content(result.content), test)
            except Exception as e:
                score = 0
                detail = {"name": test["name"], "score": 0, "max_score": test["criteria"]["generation_quality"],
                          "error": str(e)[:100]}

            total_score += score
            max_total += test["criteria"]["generation_quality"]
            details.append(detail)

        weight = self.category_weights.get("generation_quality", 0.35)
        return CategoryScore(category="生成质量", score=total_score, max_score=max_total,
                             details=details, weight=weight)

    async def _evaluate_hallucination_detection(self, model: str, temperature: float,
                                                  max_tokens: int) -> CategoryScore:
        tests = RAG_BENCHMARKS
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个文档检索助手。请严格根据提供的上下文信息回答问题。如果上下文中没有相关信息，请明确说明，不要编造。"),
                ChatMessage(role="user", content=f"上下文:\n{test['context']}\n\n问题: {test['question']}")
            ]

            try:
                result = await self.client.chat_completion(
                    messages=messages, model=model,
                    temperature=temperature, max_tokens=max_tokens
                )
                score, detail = self._score_hallucination(self._safe_content(result.content), test)
            except Exception as e:
                score = 0
                detail = {"name": test["name"], "score": 0, "max_score": test["criteria"]["hallucination_free"],
                          "error": str(e)[:100]}

            total_score += score
            max_total += test["criteria"]["hallucination_free"]
            details.append(detail)

        weight = self.category_weights.get("hallucination_free", 0.30)
        return CategoryScore(category="幻觉检测", score=total_score, max_score=max_total,
                             details=details, weight=weight)

    def _score_retrieval(self, response: str, test: Dict) -> Tuple[float, Dict]:
        criteria_val = test["criteria"]["retrieval_accuracy"]
        expected_facts = test.get("expected_facts", [])
        if not expected_facts:
            return criteria_val, {"name": test["name"], "score": criteria_val, "max_score": criteria_val}

        response_lower = response.lower()
        found = sum(1 for fact in expected_facts if fact.lower() in response_lower)
        ratio = found / len(expected_facts)
        score = round(criteria_val * ratio)
        return score, {"name": test["name"], "score": score, "max_score": criteria_val,
                        "found_facts": found, "total_facts": len(expected_facts)}

    def _score_generation_quality(self, response: str, test: Dict) -> Tuple[float, Dict]:
        criteria_val = test["criteria"]["generation_quality"]
        if not response:
            return 0, {"name": test["name"], "score": 0, "max_score": criteria_val, "reason": "空响应"}

        score = 0
        if len(response) >= 20:
            score += criteria_val * 0.3
        if any(sep in response for sep in ["1.", "2.", "-", "：", ":"]):
            score += criteria_val * 0.3
        expected_facts = test.get("expected_facts", [])
        if expected_facts:
            found = sum(1 for f in expected_facts if f.lower() in response.lower())
            score += criteria_val * 0.4 * (found / len(expected_facts))

        score = round(score)
        return score, {"name": test["name"], "score": score, "max_score": criteria_val,
                        "response_length": len(response)}

    def _score_hallucination(self, response: str, test: Dict) -> Tuple[float, Dict]:
        criteria_val = test["criteria"]["hallucination_free"]
        traps = test.get("hallucination_traps", [])
        if not traps:
            return criteria_val, {"name": test["name"], "score": criteria_val, "max_score": criteria_val}

        response_lower = response.lower()
        hallucinated = [trap for trap in traps if trap.lower() in response_lower]
        clean_ratio = 1 - (len(hallucinated) / len(traps))
        score = round(criteria_val * clean_ratio)
        return score, {"name": test["name"], "score": score, "max_score": criteria_val,
                        "hallucinated": hallucinated, "total_traps": len(traps)}