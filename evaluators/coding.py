"""
代码能力评估模块 - 增强版
评估维度: 代码生成、代码补全、Debug、多语言编程
新增维度: 可执行代码验证、实际开发场景、代码审查、API开发、数据处理

设计理念: 模拟 OpenClaw/Hermes 等框架的真实开发场景
"""

import re
import json
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Tuple, Optional
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


def _extract_thinking_content(text: str) -> str:
    """从模型输出中提取有效内容，处理 thinking block 场景。"""
    if not text or not text.strip():
        return ""
    stripped = text.strip()
    has_explicit_thinking = bool(re.search(r'<think>|</think>|<thinking>|</thinking>', stripped))
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
            return outside_thinking + "\n\n" + "\n\n".join(thinking_blocks)
        else:
            return stripped
    return stripped


# ============================================================
# 代码能力测试题库 - 基础测试
# ============================================================

CODING_BENCHMARKS = {
    "code_writing": [
        {
            "name": "二分查找实现",
            "prompt": "请用 Python 实现一个通用的二分查找函数。要求:\n1. 函数签名: def binary_search(arr: list, target) -> int\n2. 在已排序数组中查找目标值\n3. 找到返回索引，未找到返回 -1\n4. 处理空数组和边界情况\n\n只输出代码，不要解释。",
            "language": "python",
            "validate": "binary_search",
            "max_score": 20,
            "logic_keywords": ["mid", "left", "right", "len(arr)", "while", "// 2", "target <", "target >", "return -1", "binary_search"],
            "criteria": {
                "function_defined": 5,
                "correct_logic": 8,
                "edge_cases": 4,
                "type_hints": 3
            }
        },
        {
            "name": "LRU缓存实现",
            "prompt": "请用 Python 实现一个 LRU (最近最少使用) 缓存类。要求:\n1. 使用 OrderedDict 或双向链表\n2. 实现 get(key) 和 put(key, value) 方法\n3. 容量满时自动淘汰最近最少使用的元素\n4. get 和 put 时间复杂度 O(1)\n\n只输出代码，不要解释。",
            "language": "python",
            "validate": "lru_cache",
            "max_score": 20,
            "logic_keywords": ["OrderedDict", "move_to_end", "popitem", "capacity", "self.cache", "get(", "put(", "if len", "O(1)"],
            "criteria": {
                "class_defined": 4,
                "get_method": 5,
                "put_method": 5,
                "eviction_logic": 4,
                "complexity": 2
            }
        },
        {
            "name": "REST API 客户端",
            "prompt": "请用 Python 编写一个异步 REST API 客户端类，使用 aiohttp。要求:\n1. 支持 GET, POST, PUT, DELETE 方法\n2. 支持自定义请求头\n3. 支持超时和重试\n4. 支持 JSON 序列化/反序列化\n\n只输出代码，不要解释。",
            "language": "python",
            "validate": "api_client",
            "max_score": 20,
            "logic_keywords": ["aiohttp", "async def", "session", "json", "headers", "timeout", "retry", "ClientSession", "asyncio"],
            "criteria": {
                "class_defined": 3,
                "async_methods": 5,
                "error_handling": 5,
                "json_handling": 4,
                "retry_logic": 3
            }
        },
    ],
    "code_completion": [
        {
            "name": "排序算法补全",
            "prefix": "def merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    ",
            "expected_pattern": "merge",
            "language": "python",
            "max_score": 15,
            "criteria": {
                "correct_merge": 8,
                "handles_all_cases": 4,
                "clean_code": 3
            }
        },
        {
            "name": "装饰器补全",
            "prefix": "import functools\ndef retry(max_retries=3, delay=1):\n    def decorator(func):\n        @functools.wraps(func)\n        def wrapper(*args, **kwargs):\n            ",
            "expected_pattern": "try|except|retry",
            "language": "python",
            "max_score": 15,
            "criteria": {
                "try_except": 5,
                "retry_loop": 5,
                "delay_sleep": 3,
                "return_value": 2
            }
        },
        {
            "name": "数据库查询补全",
            "prefix": "class UserRepository:\n    def __init__(self, db_session):\n        self.db = db_session\n\n    async def get_user_by_email(self, email: str):\n        ",
            "expected_pattern": "select|query|filter",
            "language": "python",
            "max_score": 15,
            "criteria": {
                "query_construction": 5,
                "parameterization": 5,
                "error_handling": 3,
                "return_type": 2
            }
        },
    ],
    "debugging": [
        {
            "name": "列表推导式Bug",
            "buggy_code": """def get_even_squares(numbers):
    # 目标: 获取所有偶数的平方
    result = [n**2 for n in numbers if n % 2 == 1]
    return result""",
            "description": "上面的函数有 Bug，目标是获取所有偶数的平方，但筛选条件写错了。请找出 Bug 并给出修正后的完整代码。",
            "bug_line": "if n % 2 == 1",
            "fix_pattern": "n % 2 == 0",
            "max_score": 15,
            "criteria": {
                "bug_identified": 5,
                "correct_fix": 5,
                "explanation": 3,
                "complete_code": 2
            }
        },
        {
            "name": "并发竞态条件",
            "buggy_code": """import threading

class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        temp = self.value
        temp += 1
        self.value = temp""",
            "description": "上面的 Counter 类在多线程环境下有竞态条件问题。请找出问题并给出线程安全的修正版本。",
            "bug_line": "increment",
            "fix_pattern": "Lock|lock|RLock",
            "max_score": 15,
            "criteria": {
                "race_identified": 5,
                "lock_usage": 5,
                "correct_implementation": 3,
                "explanation": 2
            }
        },
        {
            "name": "内存泄漏",
            "buggy_code": """class EventBus:
    def __init__(self):
        self.listeners = {}

    def on(self, event, callback):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    def emit(self, event, data):
        for cb in self.listeners.get(event, []):
            cb(data)""",
            "description": "上面的 EventBus 类存在内存泄漏风险：注册的回调函数永远无法被移除。请修复这个问题，添加 off 方法来移除监听器。",
            "bug_line": "no off method",
            "fix_pattern": "off|remove|detach",
            "max_score": 15,
            "criteria": {
                "leak_identified": 5,
                "off_method": 5,
                "correct_implementation": 3,
                "edge_cases": 2
            }
        },
    ],
    "multilingual": [
        {
            "name": "TypeScript 泛型工具类型",
            "prompt": "请用 TypeScript 实现以下工具类型:\n1. DeepPartial<T> - 递归地将所有属性变为可选\n2. DeepReadonly<T> - 递归地将所有属性变为只读\n3. PathOf<T> - 获取对象所有嵌套路径的类型\n\n只输出类型定义代码。",
            "language": "typescript",
            "max_score": 15,
            "criteria": {
                "deep_partial": 5,
                "deep_readonly": 5,
                "path_of": 3,
                "type_safety": 2
            }
        },
        {
            "name": "Rust 所有权模式",
            "prompt": "请用 Rust 实现一个简单的文本编辑器缓冲区结构。要求:\n1. 支持插入、删除文本\n2. 支持撤销操作\n3. 正确处理所有权和借用\n4. 使用 Cargo 风格的模块结构\n\n只输出代码。",
            "language": "rust",
            "max_score": 15,
            "criteria": {
                "struct_definition": 3,
                "ownership_correct": 5,
                "undo_support": 4,
                "borrowing_correct": 3
            }
        },
        {
            "name": "Go 并发模式",
            "prompt": "请用 Go 实现一个 worker pool 模式。要求:\n1. 使用 channel 进行任务分发\n2. 支持动态调整 worker 数量\n3. 支持 graceful shutdown\n4. 处理 worker panic 恢复\n\n只输出代码。",
            "language": "go",
            "max_score": 15,
            "criteria": {
                "worker_pool": 4,
                "channel_usage": 4,
                "graceful_shutdown": 4,
                "panic_recovery": 3
            }
        },
    ]
}


# ============================================================
# 新增测试题库 - 面向实际应用的测试
# ============================================================

CODING_BENCHMARKS_PRACTICAL = {
    # ============================================================
    # 1. 代码审查 (安全与质量)
    # ============================================================
    "code_review": [
        {
            "name": "SQL注入漏洞识别",
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return db.execute(query)
            """,
            "description": "请审查以上代码，识别所有安全问题并给出修正建议。",
            "expected_issues": ["SQL注入", "明文密码", "硬编码", "无输入验证"],
            "max_score": 20,
            "criteria": {
                "sql_injection_identified": 6,
                "plaintext_password": 4,
                "input_validation": 4,
                "correct_fix": 6
            }
        },
        {
            "name": "敏感信息泄露",
            "code": """
class APIClient:
    def __init__(self):
        self.api_key = "sk-1234567890abcdef"
        self.secret = "my_super_secret_key_123"
    
    def log_request(self, request):
        logger.info(f"Request: {request}, API Key: {self.api_key}")
            """,
            "description": "请审查以上代码，识别敏感信息处理问题并给出修正建议。",
            "expected_issues": ["硬编码密钥", "日志泄露", "无加密存储"],
            "max_score": 20,
            "criteria": {
                "hardcoded_key": 6,
                "log_leak": 6,
                "secure_storage": 4,
                "correct_fix": 4
            }
        },
        {
            "name": "并发安全问题",
            "code": """
class UserService:
    def __init__(self):
        self.users = {}
        self.next_id = 1
    
    def create_user(self, name):
        user_id = self.next_id
        self.users[user_id] = {"id": user_id, "name": name}
        self.next_id += 1
        return user_id
            """,
            "description": "请审查以上代码，识别并发安全问题并给出修正建议。",
            "expected_issues": ["竞态条件", "非原子操作", "线程不安全"],
            "max_score": 20,
            "criteria": {
                "race_condition": 7,
                "atomicity": 5,
                "thread_safety": 4,
                "correct_fix": 4
            }
        },
    ],
    
    # ============================================================
    # 2. 测试用例编写
    # ============================================================
    "test_writing": [
        {
            "name": "单元测试生成",
            "code": """
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def parse_date(date_str):
    from datetime import datetime
    return datetime.strptime(date_str, "%Y-%m-%d")
            """,
            "description": "请为以上函数编写完整的pytest单元测试，包括正常情况和异常情况。",
            "expected_tests": ["test_divide_normal", "test_divide_by_zero", "test_parse_date_valid", "test_parse_date_invalid"],
            "max_score": 25,
            "criteria": {
                "test_coverage": 10,
                "edge_cases": 5,
                "exception_testing": 5,
                "fixture_usage": 3,
                "assertions": 2
            }
        },
        {
            "name": "Mock测试编写",
            "code": """
class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway
    
    def process_payment(self, amount, currency):
        result = self.gateway.charge(amount, currency)
        return result["status"] == "success"
            """,
            "description": "请为PaymentService编写Mock测试，模拟支付网关的各种响应。",
            "expected_tests": ["mock_gateway", "success_case", "failure_case", "exception_case"],
            "max_score": 25,
            "criteria": {
                "mock_setup": 8,
                "success_case": 5,
                "failure_case": 5,
                "exception_case": 4,
                "assertions": 3
            }
        },
    ],
    
    # ============================================================
    # 3. API接口开发 (真实业务场景)
    # ============================================================
    "api_development": [
        {
            "name": "FastAPI CRUD接口",
            "prompt": """使用FastAPI实现一个用户管理API。

要求:
1. 模型: User(id, username, email, created_at)
2. 端点: GET /users, GET /users/{id}, POST /users, PUT /users/{id}, DELETE /users/{id}
3. 输入验证(Pydantic)
4. 错误处理(404, 400, 500)
5. 使用依赖注入
6. 分页支持

只输出代码。""",
            "language": "python",
            "max_score": 30,
            "criteria": {
                "model_definition": 5,
                "crud_endpoints": 10,
                "validation": 5,
                "error_handling": 5,
                "dependency_injection": 3,
                "pagination": 2
            }
        },
        {
            "name": "中间件实现",
            "prompt": """实现一个API请求日志和限流中间件。

要求:
1. 中间件名: LoggingRateLimitMiddleware
2. 记录每个请求(方法、路径、耗时、状态码)
3. 基于IP的限流(每分钟100请求)
4. 超限返回429状态码
5. 使用Redis存储计数
6. 异步支持

只输出代码。""",
            "language": "python",
            "max_score": 25,
            "criteria": {
                "logging": 6,
                "rate_limiting": 8,
                "redis_integration": 5,
                "async_support": 3,
                "error_handling": 3
            }
        },
    ],
}


_CODE_SUPPRESS_REASONING = " 不要输出推理过程或思考链，直接给出最终结果。"


class CodingEvaluator:
    """代码能力评估器 - 增强版"""

    def __init__(self, client: LMStudioClient, config=None, category_weights=None,
                 include_practical=True):
        self.client = client
        self.config = config
        self.category_weights = category_weights or {}
        self.include_practical = include_practical

    @staticmethod
    def _safe_content(content) -> str:
        """安全获取响应内容，处理 None/空值，并提取 thinking block 中的内容"""
        if content is None:
            return ""
        text = str(content).strip()
        return _extract_thinking_content(text)

    def _get_effective_max_tokens(self, default_max_tokens: int) -> int:
        """根据应用场景获取有效的 max_tokens。

        OpenClaw 场景: 代码任务给更多 token (代码可能很长)
        Hermes 场景: 代码任务也给更多 token (允许推理+代码)
        """
        if self.config and hasattr(self.config, 'application'):
            app = self.config.application
            if hasattr(app, 'openclaw') and app.openclaw.max_tokens_code:
                return app.openclaw.max_tokens_code
        return default_max_tokens

    def _should_suppress_reasoning(self) -> bool:
        """是否应抑制推理输出 (OpenClaw 场景默认抑制, Hermes 允许)"""
        if self.config and hasattr(self.config, 'application'):
            app = self.config.application
            if hasattr(app, 'openclaw') and app.openclaw.suppress_reasoning:
                return True
        return True

    async def evaluate(self, model: str, temperature: float = 0.0,
                       max_tokens: int = 2048, include_practical: bool = True) -> List[CategoryScore]:
        """执行完整的代码能力评估
        
        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            include_practical: 是否包含面向实际应用的测试
        """
        categories = []

        # 1. 代码生成 (基础)
        gen_score = await self._evaluate_code_writing(model, temperature, max_tokens)
        categories.append(gen_score)

        # 2. 代码补全 (基础)
        comp_score = await self._evaluate_code_completion(model, temperature, max_tokens)
        categories.append(comp_score)

        # 3. Debug (基础)
        debug_score = await self._evaluate_debugging(model, temperature, max_tokens)
        categories.append(debug_score)

        # 4. 多语言 (基础)
        multi_score = await self._evaluate_multilingual(model, temperature, max_tokens)
        categories.append(multi_score)

        # 5. 代码审查 (实际应用)
        if include_practical:
            review_score = await self._evaluate_code_review(model, temperature, max_tokens)
            categories.append(review_score)

        # 8. 测试用例编写 (实际应用)
        if include_practical:
            test_score = await self._evaluate_test_writing(model, temperature, max_tokens)
            categories.append(test_score)

        # 9. API接口开发 (实际应用)
        if include_practical:
            api_score = await self._evaluate_api_development(model, temperature, max_tokens)
            categories.append(api_score)

        return categories

    # ============================================================
    # 基础评估方法
    # ============================================================

    async def _evaluate_code_writing(self, model: str, temperature: float,
                                         max_tokens: int) -> CategoryScore:
        """评估代码生成能力"""
        tests = CODING_BENCHMARKS["code_writing"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个专业的程序员。请根据要求编写高质量的代码。只输出代码，不要任何解释。" + _CODE_SUPPRESS_REASONING),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_writing(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码生成",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.20
        )

    async def _evaluate_code_completion(self, model: str, temperature: float,
                                         max_tokens: int) -> CategoryScore:
        """评估代码补全能力"""
        tests = CODING_BENCHMARKS["code_completion"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个代码补全助手。请根据上下文补全代码，只输出补全部分。" + _CODE_SUPPRESS_REASONING),
                ChatMessage(role="user", content=f"请补全以下代码:\n\n{test['prefix']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_completion(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码补全",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.15
        )

    async def _evaluate_debugging(self, model: str, temperature: float,
                                   max_tokens: int) -> CategoryScore:
        """评估 Debug 能力"""
        tests = CODING_BENCHMARKS["debugging"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个高级调试专家。请分析代码中的 Bug，给出修正方案和完整修正后的代码。" + _CODE_SUPPRESS_REASONING),
                ChatMessage(role="user", content=f"```python\n{test['buggy_code']}\n```\n\n{test['description']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_debugging(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="Debug调试",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.15
        )

    async def _evaluate_multilingual(self, model: str, temperature: float,
                                     max_tokens: int) -> CategoryScore:
        """评估多语言编程能力"""
        tests = CODING_BENCHMARKS["multilingual"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content=f"你是一个精通 {test['language']} 的资深开发者。请编写高质量的代码。" + _CODE_SUPPRESS_REASONING),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_multilingual(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="多语言编程",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.10
        )

    # ============================================================
    # 实际应用评估方法
    # ============================================================

    async def _evaluate_code_review(self, model: str, temperature: float,
                                     max_tokens: int) -> CategoryScore:
        """评估代码审查能力"""
        tests = CODING_BENCHMARKS_PRACTICAL["code_review"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个代码安全审查专家。请仔细审查代码，识别所有安全问题并给出修正建议。"),
                ChatMessage(role="user", content=f"```python\n{test['code']}\n```\n\n{test['description']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_review(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码审查",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.08
        )

    async def _evaluate_test_writing(self, model: str, temperature: float,
                                      max_tokens: int) -> CategoryScore:
        """评估测试用例编写能力"""
        tests = CODING_BENCHMARKS_PRACTICAL["test_writing"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个测试专家。请为以下代码编写完整的pytest单元测试。"),
                ChatMessage(role="user", content=f"```python\n{test['code']}\n```\n\n{test['description']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_test_writing(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="测试用例编写",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.07
        )

    async def _evaluate_api_development(self, model: str, temperature: float,
                                         max_tokens: int) -> CategoryScore:
        """评估API接口开发能力"""
        tests = CODING_BENCHMARKS_PRACTICAL["api_development"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个API开发专家。请编写高质量的FastAPI代码。" + _CODE_SUPPRESS_REASONING),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_api_development(self._safe_content(result.content), test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="API接口开发",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.05
        )

    # ============================================================
    # 基础评分方法
    # ============================================================

    def _score_code_writing(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分代码生成"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # 检查函数/类是否定义
        code_block = self._extract_code(response)
        if code_block:
            scores["function_defined"] = criteria.get("function_defined", criteria.get("class_defined", 0))
            total += scores["function_defined"]

        # 检查关键逻辑 — 使用题目专属关键词
        logic_keywords = test.get("logic_keywords") or self._get_expected_keywords(test["validate"])
        if logic_keywords:
            found_keywords = sum(1 for kw in logic_keywords if kw.lower() in response.lower())
            keyword_ratio = found_keywords / max(len(logic_keywords), 1)
            if "correct_logic" in criteria:
                logic_score = round(criteria["correct_logic"] * keyword_ratio)
                scores["correct_logic"] = logic_score
                total += logic_score
            for alt_key in ("eviction_logic", "async_methods"):
                if alt_key in criteria:
                    scores[alt_key] = round(criteria[alt_key] * keyword_ratio)
                    total += scores[alt_key]

        # 检查边界情况处理
        edge_patterns = ["if not", "if len", "empty", "none", "null", "== 0", "return -1", "raise"]
        edge_count = sum(1 for p in edge_patterns if p.lower() in response.lower())
        edge_score = min(criteria.get("edge_cases", 0), edge_count * 2)
        scores["edge_cases"] = edge_score
        total += edge_score

        # 检查类型提示
        type_patterns = [": int", ": str", ": list", ": dict", "-> int", "-> str", "-> list", "-> None"]
        type_count = sum(1 for p in type_patterns if p in response)
        type_score = min(criteria.get("type_hints", 0), type_count * 2)
        scores["type_hints"] = type_score
        total += type_score

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "has_code_block": code_block is not None
        }
        return total, detail

    def _score_code_completion(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分代码补全 — 支持 prefix+completion 合并验证"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        code = self._extract_code(response) or response

        if not code.strip() or len(code.strip()) < 5:
            combined = test.get("prefix", "") + "\n" + response.strip()
            if self._extract_code(combined):
                code = self._extract_code(combined)
            else:
                combined_clean = re.sub(r'^(?:这里是|Here is|补全如下|Completion:)[^\n]*\n', '', combined, flags=re.IGNORECASE)
                code = combined_clean

        patterns = test["expected_pattern"].split("|")
        pattern_count = sum(1 for p in patterns if p.lower() in code.lower())

        if "correct_merge" in criteria:
            merge_primary = ["merge", "合并", "merging"]
            merge_semantic = ["sorted", "result", "while", "append", "i <", "j <", "left", "right"]
            if pattern_count > 0:
                scores["correct_merge"] = min(criteria["correct_merge"], pattern_count * 4)
            elif any(kw in code.lower() for kw in merge_semantic):
                semantic_count = sum(1 for kw in merge_semantic if kw in code.lower())
                scores["correct_merge"] = min(criteria["correct_merge"], round(semantic_count * 1.5))
            else:
                scores["correct_merge"] = 0
            total += scores["correct_merge"]

        if "try_except" in criteria:
            scores["try_except"] = criteria["try_except"] if "try" in code.lower() and "except" in code.lower() else 0
            total += scores["try_except"]
        if "retry_loop" in criteria:
            scores["retry_loop"] = criteria["retry_loop"] if any(w in code.lower() for w in ["for", "while", "range"]) else 0
            total += scores["retry_loop"]
        if "delay_sleep" in criteria:
            scores["delay_sleep"] = criteria["delay_sleep"] if "sleep" in code.lower() else 0
            total += scores["delay_sleep"]
        if "return_value" in criteria:
            scores["return_value"] = criteria["return_value"] if "return" in code.lower() else 0
            total += scores["return_value"]
        if "query_construction" in criteria:
            scores["query_construction"] = min(criteria["query_construction"], pattern_count * 3)
            total += scores["query_construction"]
        if "parameterization" in criteria:
            scores["parameterization"] = criteria["parameterization"] if any(w in code.lower() for w in ["param", "bind", "execute", "filter"]) else 0
            total += scores["parameterization"]
        if "error_handling" in criteria:
            scores["error_handling"] = criteria["error_handling"] if any(w in code.lower() for w in ["try", "except", "error", "catch"]) else 0
            total += scores["error_handling"]
        if "return_type" in criteria:
            scores["return_type"] = criteria["return_type"] if "return" in code.lower() else 0
            total += scores["return_type"]

        clean_score = criteria.get("clean_code", 0)
        if code.count("\n") > 1 and code.count("    ") > 0:
            scores["clean_code"] = clean_score
            total += clean_score

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "code_extracted_len": len(code)
        }
        return total, detail

    def _score_debugging(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分 Debug 能力"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # Bug 识别
        bug_keywords = ["bug", "错误", "问题", "修复", "fix", "wrong", "不正确"]
        bug_identified = any(kw in response.lower() for kw in bug_keywords)
        if bug_identified:
            scores["bug_identified"] = criteria.get("bug_identified", 0)
            total += scores["bug_identified"]

        # 修复正确性
        fix_patterns = test["fix_pattern"].split("|")
        fix_found = any(p.lower() in response.lower() for p in fix_patterns)
        if fix_found:
            scores["correct_fix"] = criteria.get("correct_fix", 0)
            total += scores["correct_fix"]

        # 解释质量
        explanation_keywords = ["因为", "原因", "because", "导致", "should", "应该"]
        has_explanation = any(kw in response.lower() for kw in explanation_keywords)
        if has_explanation:
            scores["explanation"] = criteria.get("explanation", 0)
            total += scores["explanation"]

        # 完整代码
        code = self._extract_code(response)
        if code and len(code) > 20:
            scores["complete_code"] = criteria.get("complete_code", 0)
            total += scores["complete_code"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    def _score_multilingual(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分多语言编程"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        lang = test["language"]
        code = self._extract_code(response) or response

        # 语言特征检测
        lang_features = {
            "typescript": ["interface", "type ", "generic", "<T>", "extends", "implements", ": string", ": number"],
            "rust": ["fn ", "let ", "mut ", "impl ", "struct ", "enum ", "&self", "pub ", "Vec<", "Option<"],
            "go": ["func ", "package ", "import ", "chan ", "go ", "select ", "defer ", "struct {", "interface {"]
        }

        features = lang_features.get(lang, [])
        feature_count = sum(1 for f in features if f in code)
        feature_ratio = feature_count / max(len(features), 1)

        # 按标准评分
        for key, max_pts in criteria.items():
            if key in ["deep_partial", "deep_readonly", "path_of"]:
                # TypeScript 特定
                type_keywords = {
                    "deep_partial": ["partial", "optional", "?", "recursive"],
                    "deep_readonly": ["readonly", "const", "never", "recursive"],
                    "path_of": ["path", "keyof", "infer", "string"]
                }
                kws = type_keywords.get(key, [])
                found = sum(1 for k in kws if k.lower() in code.lower())
                scores[key] = min(max_pts, found * 2)
            elif key in ["struct_definition", "worker_pool"]:
                scores[key] = min(max_pts, feature_count * 2)
            elif key in ["ownership_correct", "borrowing_correct"]:
                ownership_kw = ["&self", "&mut", "move", "clone", "borrow", "own", "Box<", "Rc<", "Arc<"]
                found = sum(1 for k in ownership_kw if k in code)
                scores[key] = min(max_pts, found * 2)
            elif key in ["channel_usage", "graceful_shutdown", "panic_recovery"]:
                go_kw = {
                    "channel_usage": ["chan", "<-", "go func"],
                    "graceful_shutdown": ["context", "done", "cancel", "shutdown", "waitgroup", "WaitGroup"],
                    "panic_recovery": ["recover", "defer", "panic"]
                }
                kws = go_kw.get(key, [])
                found = sum(1 for k in kws if k in code)
                scores[key] = min(max_pts, found * 2)
            elif key == "type_safety":
                scores[key] = min(max_pts, round(feature_ratio * max_pts))
            elif key == "undo_support":
                undo_kw = ["undo", "history", "stack", "revert", "restore"]
                found = sum(1 for k in undo_kw if k.lower() in code.lower())
                scores[key] = min(max_pts, found * 2)
            else:
                scores[key] = round(feature_ratio * max_pts)
            total += scores[key]

        detail = {
            "test": test["name"],
            "language": lang,
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
        }
        return total, detail

    # ============================================================
    # 实际应用评分方法
    # ============================================================

    def _score_code_review(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分代码审查 — 支持语义等价评分"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        expected_issues = test.get("expected_issues", [])
        response_lower = response.lower()

        if "sql_injection_identified" in criteria:
            sql_primary = ["sql注入", "sql injection", "注入攻击", "injection attack"]
            sql_semantic = [
                "f-string", "f\"", "字符串拼接", "string concatenation", "format(",
                "不安全", "unsafe", "参数化查询", "parameterized", "prepared statement",
                "预编译", "占位符", "placeholder", "?", "%s",
                "用户输入直接", "direct user input", "拼接sql", "拼接查询",
            ]
            primary_found = any(kw in response_lower for kw in sql_primary)
            semantic_found = any(kw in response_lower for kw in sql_semantic)
            if primary_found:
                scores["sql_injection_identified"] = criteria["sql_injection_identified"]
            elif semantic_found:
                scores["sql_injection_identified"] = round(criteria["sql_injection_identified"] * 0.7)
            else:
                scores["sql_injection_identified"] = 0
            total += scores["sql_injection_identified"]

        if "plaintext_password" in criteria:
            pwd_primary = ["明文", "plaintext", "密码存储", "password storage"]
            pwd_semantic = [
                "哈希", "hash", "加密", "encrypt", "bcrypt", "scrypt", "argon2",
                "不应存储", "should not store", "不安全存储", "insecure storage",
                "敏感信息", "sensitive", "脱敏", "mask",
            ]
            primary_found = any(kw in response_lower for kw in pwd_primary)
            semantic_found = any(kw in response_lower for kw in pwd_semantic)
            if primary_found:
                scores["plaintext_password"] = criteria["plaintext_password"]
            elif semantic_found:
                scores["plaintext_password"] = round(criteria["plaintext_password"] * 0.7)
            else:
                scores["plaintext_password"] = 0
            total += scores["plaintext_password"]

        if "input_validation" in criteria:
            valid_primary = ["验证", "validate", "sanitize", "清理", "检查输入"]
            valid_semantic = [
                "过滤", "filter", "清洗", "escape", "转义",
                "类型检查", "type check", "边界检查", "boundary",
                "不信任", "distrust", "不可信", "untrusted",
            ]
            primary_found = any(kw in response_lower for kw in valid_primary)
            semantic_found = any(kw in response_lower for kw in valid_semantic)
            if primary_found:
                scores["input_validation"] = criteria["input_validation"]
            elif semantic_found:
                scores["input_validation"] = round(criteria["input_validation"] * 0.7)
            else:
                scores["input_validation"] = 0
            total += scores["input_validation"]

        if "hardcoded_key" in criteria:
            key_primary = ["硬编码", "hardcoded", "hard-coded"]
            key_semantic = [
                "环境变量", "env", "配置文件", "config", "secrets",
                "不应写死", "不应直接", "不要直接", "密钥管理",
                "vault", "secret management", "动态获取",
            ]
            primary_found = any(kw in response_lower for kw in key_primary)
            semantic_found = any(kw in response_lower for kw in key_semantic)
            if primary_found:
                scores["hardcoded_key"] = criteria["hardcoded_key"]
            elif semantic_found:
                scores["hardcoded_key"] = round(criteria["hardcoded_key"] * 0.7)
            else:
                scores["hardcoded_key"] = 0
            total += scores["hardcoded_key"]

        if "race_condition" in criteria:
            race_primary = ["竞态", "race condition", "线程不安全", "thread-unsafe"]
            race_semantic = [
                "锁", "lock", "mutex", "同步", "synchronized", "atomic",
                "并发问题", "concurrency issue", "互斥", "加锁",
                "线程安全", "thread-safe", "threading",
            ]
            primary_found = any(kw in response_lower for kw in race_primary)
            semantic_found = any(kw in response_lower for kw in race_semantic)
            if primary_found:
                scores["race_condition"] = criteria["race_condition"]
            elif semantic_found:
                scores["race_condition"] = round(criteria["race_condition"] * 0.7)
            else:
                scores["race_condition"] = 0
            total += scores["race_condition"]

        if "correct_fix" in criteria:
            has_fix = self._extract_code(response) is not None and len(self._extract_code(response)) > 50
            fix_semantic = any(kw in response_lower for kw in [
                "修改建议", "修复代码", "corrected", "fixed code", "改进后",
            ])
            if has_fix:
                scores["correct_fix"] = criteria["correct_fix"]
            elif fix_semantic:
                scores["correct_fix"] = round(criteria["correct_fix"] * 0.5)
            else:
                scores["correct_fix"] = 0
            total += scores["correct_fix"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "issues_identified": len([s for s in scores.values() if s > 0])
        }
        return total, detail

    def _score_test_writing(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分测试用例编写"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        code = self._extract_code(response) or response
        expected_tests = test.get("expected_tests", [])

        # 测试覆盖率
        if "test_coverage" in criteria:
            test_kw = ["def test_", "pytest", "assert"]
            found = sum(1 for kw in test_kw if kw in code)
            scores["test_coverage"] = min(criteria["test_coverage"], found * 4)
            total += scores["test_coverage"]

        # 边界情况
        if "edge_cases" in criteria:
            edge_kw = ["empty", "None", "null", "0", "-1", "max", "min", "边界"]
            found = sum(1 for kw in edge_kw if kw.lower() in code.lower())
            scores["edge_cases"] = min(criteria["edge_cases"], found * 2)
            total += scores["edge_cases"]

        # 异常测试
        if "exception_testing" in criteria:
            exc_kw = ["raises", "pytest.raises", "except", "error", "Error"]
            found = sum(1 for kw in exc_kw if kw in code)
            scores["exception_testing"] = min(criteria["exception_testing"], found * 2)
            total += scores["exception_testing"]

        # Fixture使用
        if "fixture_usage" in criteria:
            fixture_kw = ["@pytest.fixture", "fixture"]
            found = sum(1 for kw in fixture_kw if kw in code)
            scores["fixture_usage"] = criteria["fixture_usage"] if found > 0 else 0
            total += scores["fixture_usage"]

        # Mock设置
        if "mock_setup" in criteria:
            mock_kw = ["mock", "Mock", "patch", "MagicMock", "return_value"]
            found = sum(1 for kw in mock_kw if kw in code)
            scores["mock_setup"] = min(criteria["mock_setup"], found * 2)
            total += scores["mock_setup"]

        # 断言
        if "assertions" in criteria:
            assert_count = code.count("assert")
            scores["assertions"] = min(criteria["assertions"], assert_count * 2)
            total += scores["assertions"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "test_functions_found": len([line for line in code.split('\n') if 'def test_' in line])
        }
        return total, detail

    def _score_api_development(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分API接口开发"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        code = self._extract_code(response) or response

        if "model_definition" in criteria:
            model_kw_strict = ["class ", "BaseModel"]
            model_kw_loose = ["class ", "dict", "TypedDict", "dataclass", "BaseModel", "Field", "pydantic", "type", "struct"]
            found_strict = sum(1 for kw in model_kw_strict if kw in code)
            found_loose = sum(1 for kw in model_kw_loose if kw in code)
            if found_strict >= 2:
                scores["model_definition"] = criteria["model_definition"]
            elif found_loose >= 2:
                scores["model_definition"] = round(criteria["model_definition"] * 0.7)
            elif found_loose >= 1:
                scores["model_definition"] = round(criteria["model_definition"] * 0.4)
            else:
                scores["model_definition"] = 0
            total += scores["model_definition"]

        if "crud_endpoints" in criteria:
            endpoint_kw = ["@app.get", "@app.post", "@app.put", "@app.delete",
                           "@router.get", "@router.post", "@router.put", "@router.delete"]
            endpoint_kw_loose = ["def get", "def post", "def put", "def delete",
                                 "def list", "def create", "def update", "def remove",
                                 "GET", "POST", "PUT", "DELETE", "route", "endpoint",
                                 "api/", "/api"]
            found_strict = sum(1 for kw in endpoint_kw if kw in code)
            found_loose = sum(1 for kw in endpoint_kw_loose if kw.lower() in code.lower())
            if found_strict >= 2:
                scores["crud_endpoints"] = criteria["crud_endpoints"]
            elif found_strict >= 1:
                scores["crud_endpoints"] = round(criteria["crud_endpoints"] * 0.6)
            elif found_loose >= 2:
                scores["crud_endpoints"] = round(criteria["crud_endpoints"] * 0.5)
            elif found_loose >= 1:
                scores["crud_endpoints"] = round(criteria["crud_endpoints"] * 0.3)
            else:
                scores["crud_endpoints"] = 0
            total += scores["crud_endpoints"]

        if "validation" in criteria:
            valid_kw = ["BaseModel", "Field", "validator", "ValidationError",
                        "validate", "check", "assert", "isinstance", "type hint",
                        "Optional", "Union", "Literal"]
            found = sum(1 for kw in valid_kw if kw.lower() in code.lower())
            scores["validation"] = min(criteria["validation"], max(found, 1) * 2)
            total += scores["validation"]

        if "error_handling" in criteria:
            error_kw = ["HTTPException", "try:", "except", "raise", "error",
                        "Error", "status_code", "response", "catch", "finally"]
            found = sum(1 for kw in error_kw if kw in code)
            scores["error_handling"] = min(criteria["error_handling"], max(found, 1) * 2)
            total += scores["error_handling"]

        if "dependency_injection" in criteria:
            di_kw = ["Depends", "dependency", "inject", "provider", "context",
                     "session", "db", "database", "get_db", "get_session"]
            found = sum(1 for kw in di_kw if kw.lower() in code.lower())
            scores["dependency_injection"] = min(criteria["dependency_injection"], found * 2) if found > 0 else 0
            total += scores["dependency_injection"]

        if "pagination" in criteria:
            page_kw = ["skip", "limit", "offset", "page", "size", "paginate",
                       "cursor", "next_page", "per_page"]
            found = sum(1 for kw in page_kw if kw.lower() in code.lower())
            scores["pagination"] = min(criteria["pagination"], found * 2) if found > 0 else 0
            total += scores["pagination"]

        if "rate_limiting" in criteria:
            rate_kw = ["rate", "limit", "throttle", "429", "count", "window",
                       "quota", "bucket", "token_bucket", "slowapi"]
            found = sum(1 for kw in rate_kw if kw.lower() in code.lower())
            scores["rate_limiting"] = min(criteria["rate_limiting"], found * 2)
            total += scores["rate_limiting"]

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores,
            "endpoints_found": len([line for line in code.split('\n') if '@app.' in line or '@router.' in line])
        }
        return total, detail

    # ============================================================
    # 辅助方法
    # ============================================================

    def _strip_reasoning_prefix(self, text: str) -> str:
        """剥离推理模型的 thinking/reasoning 前缀文本。

        推理模型 (如 Qwen/Qwopus) 可能在代码输出前附加推理过程:
        - "Thinking Process:\\n1. ...\\n\\n```python\\n..."
        - "Let me think...\\n\\n```python\\n..."
        - "分析:\\n1. ...\\n\\nHere is the code:\\n```python\\n..."

        本方法检测并剥离此类前缀, 保留代码部分。
        """
        if not text:
            return text

        fence_pos = text.find('```')
        if fence_pos < 0:
            code_start_patterns = [
                r'(?:^|\n)(def\s+\w+\s*\()',
                r'(?:^|\n)(class\s+\w+)',
                r'(?:^|\n)(import\s+\w+)',
                r'(?:^|\n)(from\s+\w+\s+import)',
                r'(?:^|\n)(async\s+def\s+\w+)',
            ]
            for pattern in code_start_patterns:
                match = re.search(pattern, text, re.MULTILINE)
                if match and match.start() > 0:
                    prefix = text[:match.start()].strip()
                    code_density = sum(
                        1 for kw in ['def ', 'class ', 'import ', 'return', ' = ']
                        if kw in prefix
                    )
                    total_lines = max(prefix.count('\n') + 1, 1)
                    if code_density / total_lines < 0.3:
                        return text[match.start():]
            return text

        if fence_pos > 0:
            prefix = text[:fence_pos].strip()
            reasoning_indicators = [
                "Thinking Process", "thinking", "Let me think", "Let me analyze",
                "分析", "推理", "思路", "步骤", "Reasoning", "Analysis",
                "I'll", "I will", "First,", "首先", "接下来", "Here's how",
                "Approach:", "Solution:", "解答",
            ]
            is_reasoning_prefix = any(ind in prefix for ind in reasoning_indicators)
            if is_reasoning_prefix or len(prefix) > 100:
                return text[fence_pos:]

        return text

    def _extract_code(self, response: str) -> Optional[str]:
        """
        从响应中提取代码块。支持多种 LLM 输出格式:

        0. 预处理: 剥离推理模型的 thinking/reasoning 前缀文本
        1. Markdown 围栏块: ```lang\\n...\\n``` (标准)
        2. Markdown 围栏块无语言标签: ```\\n...\\n```
        3. 缩进代码块: 以 4 空格/1 Tab 开头的连续行
        4. OpenClaw/Hermes 场景: 模型直接输出裸代码 (无 Markdown 包裹)
        5. 带前缀说明的代码: "Here is the code:\\n```..."

        返回按优先级提取的第一个有效代码块。
        若所有提取策略都不匹配, 尝试将整个响应作为代码。
        """
        if not response or not response.strip():
            return None

        response = self._strip_reasoning_prefix(response)

        # 策略 1: Markdown 围栏代码块 (```...```)
        fence_match = re.search(
            r'```(?:[\w+#-]*\s*\n)?(.*?)```',
            response, re.DOTALL
        )
        if fence_match:
            code = fence_match.group(1).strip()
            if len(code) >= 10 and any(
                keyword in code.lower()
                for keyword in ['def ', 'class ', 'import ', 'from ', 'async def', 'return', 'if ', 'for ', 'while ']
            ):
                return code

        # 策略 2: 缩进代码块 (4 空格或 Tab 缩进的连续行)
        lines = response.split('\n')
        indented_chunks = []
        current_chunk = []
        for line in lines:
            if line.startswith('    ') or line.startswith('\t'):
                current_chunk.append(line.lstrip('\t').lstrip(' ')[4:] if line.startswith('    ') else line[1:])
            else:
                if len(current_chunk) >= 3:
                    indented_chunks.append('\n'.join(current_chunk))
                current_chunk = []
        if len(current_chunk) >= 3:
            indented_chunks.append('\n'.join(current_chunk))

        if indented_chunks:
            best_chunk = max(indented_chunks, key=len)
            if any(kw in best_chunk.lower() for kw in ['def ', 'class ', 'import ', 'return', 'if __name__']):
                return best_chunk

        # 策略 3: 结构化代码特征检测 (裸代码兼容 OpenClaw/Hermes 输出)
        # 模型的输出可能包含叙述性文字 + 代码, 尝试用常见代码开头模式定位
        # 找到最早的代码特征匹配位置, 从该位置开始提取
        code_start_patterns = [
            r'(?:^|\n)(def\s+\w+\s*\()',
            r'(?:^|\n)(class\s+\w+)',
            r'(?:^|\n)(import\s+\w+)',
            r'(?:^|\n)(from\s+\w+\s+import)',
            r'(?:^|\n)(async\s+def\s+\w+)',
            r'(?:^|\n)(const\s+\w+)',
            r'(?:^|\n)(function\s+\w+)',
            r'(?:^|\n)(package\s+\w+)',
            r'(?:^|\n)(use\s+\w+)',
            r'(?:^|\n)(fn\s+\w+)',
            r'(?:^|\n)(let\s+mut\s+\w+)',
        ]
        earliest_start = len(response)
        for pattern in code_start_patterns:
            match = re.search(pattern, response, re.MULTILINE)
            if match and match.start() < earliest_start:
                earliest_start = match.start()

        if earliest_start < len(response):
            extracted = response[earliest_start:].strip()
            if len(extracted) >= 10:
                return extracted

        # 策略 4: 完全无标记, 检查整个响应的代码密度
        stripped = response.strip()
        code_indicators = sum(
            1 for kw in ['def ', 'class ', 'import ', 'return', '  ', ' = ', ': ']
            if kw in stripped
        )
        non_code_lines = sum(
            1 for line in stripped.split('\n')
            if not line.strip() or line.strip().startswith('#')
        )
        total_lines = max(stripped.count('\n') + 1, 1)
        if code_indicators >= 2 and (non_code_lines / total_lines) < 0.7:
            return stripped

        return None

    def _get_expected_keywords(self, test_type: str) -> List[str]:
        """获取测试类型的关键词"""
        keyword_map = {
            "binary_search": ["mid", "left", "right", "return -1", "len(arr)"],
            "lru_cache": ["OrderedDict", "move_to_end", "popitem", "get", "put"],
            "api_client": ["aiohttp", "async def", "session", "json", "headers"],
        }
        return keyword_map.get(test_type, [])
