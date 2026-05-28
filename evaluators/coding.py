"""
代码能力评估模块
评估维度: 代码生成、代码补全、Debug、多语言编程
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import CategoryScore


# ============================================================
# 代码能力测试题库
# ============================================================

CODING_BENCHMARKS = {
    "code_generation": [
        {
            "name": "二分查找实现",
            "prompt": "请用 Python 实现一个通用的二分查找函数。要求:\n1. 函数签名: def binary_search(arr: list, target) -> int\n2. 在已排序数组中查找目标值\n3. 找到返回索引，未找到返回 -1\n4. 处理空数组和边界情况\n\n只输出代码，不要解释。",
            "language": "python",
            "validate": "binary_search",
            "max_score": 20,
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
n    def __init__(self):
n        self.listeners = {}

    def on(self, event, callback):
n        if event not in self.listeners:
n            self.listeners[event] = []
        self.listeners[event].append(callback)

    def emit(self, event, data):
n        for cb in self.listeners.get(event, []):
n            cb(data)""",
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


class CodingEvaluator:
    """代码能力评估器"""

    def __init__(self, client: LMStudioClient, config=None):
        self.client = client
        self.config = config

    async def evaluate(self, model: str, temperature: float = 0.0,
                       max_tokens: int = 2048) -> List[CategoryScore]:
        """执行完整的代码能力评估"""
        categories = []

        # 1. 代码生成
        gen_score = await self._evaluate_code_generation(model, temperature, max_tokens)
        categories.append(gen_score)

        # 2. 代码补全
        comp_score = await self._evaluate_code_completion(model, temperature, max_tokens)
        categories.append(comp_score)

        # 3. Debug
        debug_score = await self._evaluate_debugging(model, temperature, max_tokens)
        categories.append(debug_score)

        # 4. 多语言
        multi_score = await self._evaluate_multilingual(model, temperature, max_tokens)
        categories.append(multi_score)

        return categories

    async def _evaluate_code_generation(self, model: str, temperature: float,
                                         max_tokens: int) -> CategoryScore:
        """评估代码生成能力"""
        tests = CODING_BENCHMARKS["code_generation"]
        details = []
        total_score = 0
        max_total = 0

        for test in tests:
            messages = [
                ChatMessage(role="system", content="你是一个专业的程序员。请根据要求编写高质量的代码。只输出代码，不要任何解释。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_generation(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码生成",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.30
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
                ChatMessage(role="system", content="你是一个代码补全助手。请根据上下文补全代码，只输出补全部分。"),
                ChatMessage(role="user", content=f"请补全以下代码:\n\n{test['prefix']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_code_completion(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="代码补全",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
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
                ChatMessage(role="system", content="你是一个高级调试专家。请分析代码中的 Bug，给出修正方案和完整修正后的代码。"),
                ChatMessage(role="user", content=f"```python\n{test['buggy_code']}\n```\n\n{test['description']}")
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_debugging(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="Debug调试",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.25
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
                ChatMessage(role="system", content=f"你是一个精通 {test['language']} 的资深开发者。请编写高质量的代码。"),
                ChatMessage(role="user", content=test["prompt"])
            ]

            result = await self.client.chat_completion(
                messages=messages, model=model,
                temperature=temperature, max_tokens=max_tokens
            )

            score, detail = self._score_multilingual(result.content, test)
            total_score += score
            max_total += test["max_score"]
            details.append(detail)

        return CategoryScore(
            category="多语言编程",
            score=total_score,
            max_score=max_total,
            details=details,
            weight=0.20
        )

    # ============================================================
    # 评分方法
    # ============================================================

    def _score_code_generation(self, response: str, test: Dict) -> Tuple[float, Dict]:
        """评分代码生成"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        # 检查函数/类是否定义
        code_block = self._extract_code(response)
        if code_block:
            scores["function_defined"] = criteria.get("function_defined", criteria.get("class_defined", 0))
            total += scores["function_defined"]

        # 检查关键逻辑
        keywords = self._get_expected_keywords(test["validate"])
        found_keywords = sum(1 for kw in keywords if kw.lower() in response.lower())
        keyword_ratio = found_keywords / max(len(keywords), 1)
        logic_score = round(criteria.get("correct_logic", 0) * keyword_ratio)
        scores["correct_logic"] = logic_score
        total += logic_score

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
        """评分代码补全"""
        criteria = test["criteria"]
        scores = {}
        total = 0

        code = self._extract_code(response) or response

        # 检查预期模式
        patterns = test["expected_pattern"].split("|")
        pattern_count = sum(1 for p in patterns if p.lower() in code.lower())

        if "correct_merge" in criteria:
            scores["correct_merge"] = min(criteria["correct_merge"], pattern_count * 4)
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

        # 代码整洁度
        clean_score = criteria.get("clean_code", 0)
        if code.count("\n") > 1 and code.count("    ") > 0:
            scores["clean_code"] = clean_score
            total += clean_score

        detail = {
            "test": test["name"],
            "max_score": test["max_score"],
            "score": total,
            "criteria_scores": scores
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
    # 辅助方法
    # ============================================================

    def _extract_code(self, response: str) -> Optional[str]:
        """从响应中提取代码块"""
        patterns = [
            r"```[\w]*\n(.*?)```",
            r"```\n(.*?)```",
        ]
        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _get_expected_keywords(self, test_type: str) -> List[str]:
        """获取测试类型的关键词"""
        keyword_map = {
            "binary_search": ["mid", "left", "right", "return -1", "len(arr)"],
            "lru_cache": ["OrderedDict", "move_to_end", "popitem", "get", "put"],
            "api_client": ["aiohttp", "async def", "session", "json", "headers"],
        }
        return keyword_map.get(test_type, [])
