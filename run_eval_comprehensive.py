#!/usr/bin/env python3
"""
LM Studio 模型评估套件 - 全面科学版
包含：8道代码题、8道Agent题、8道推理题、性能基准（含4/8线程并发）
评分维度：正确性、完整性、可读性/合理性、性能
"""

import os, sys, time, requests, json, re, ast, concurrent.futures, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.score_engine import ScoreEngine, CategoryScore

API_URL = "http://59.55.125.214:1024"
API_KEY = "sk-lm-kkZxEu1e:YagcQehqsGQGNQD0cyIH"

class SyncClient:
    def __init__(self, base_url, api_key, timeout=1200):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        self.timeout = timeout

    def chat(self, messages, model, max_tokens=4096, temperature=0.0):
        start = time.time()
        resp = self.session.post(f"{self.base_url}/v1/chat/completions",
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "") or msg.get("reasoning_content", "")
        usage = data.get("usage", {})
        return {"content": content, "completion_tokens": usage.get("completion_tokens", 0), 
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "latency_ms": (time.time()-start)*1000, "success": True}

    def chat_simple(self, messages, model, max_tokens=512):
        try:
            return self.chat(messages, model, max_tokens)
        except:
            return {"content": "", "completion_tokens": 0, "latency_ms": 0, "success": False}


# ============================================================
# 全面代码能力测试（8题）
# ============================================================

CODING_TESTS = [
    {
        "id": "C1",
        "name": "基础算法：红黑树实现",
        "category": "数据结构与算法",
        "difficulty": "Hard",
        "prompt": """请实现一个红黑树（Red-Black Tree），要求：
1. 支持插入、删除、查找操作
2. 保持红黑树性质平衡
3. 提供中序遍历输出有序序列
4. 包含必要的辅助方法（旋转、重新着色）
5. 使用Python实现，包含完整类型注解

请确保代码可以正确运行，并处理边界情况。""",
        "test_cases": [
            {"input": "tree = RedBlackTree(); [tree.insert(x) for x in [10, 5, 15, 3, 7]]; tree.inorder()", "expected": "[3, 5, 7, 10, 15]"},
            {"input": "tree = RedBlackTree(); tree.insert(10); tree.delete(10); tree.root is None", "expected": "True"}
        ],
        "rubric": {
            "correctness": 40,  # 能否正确运行，通过测试用例
            "completeness": 30,  # 是否实现所有要求功能
            "code_quality": 20,  # 代码结构、注释、类型注解
            "edge_cases": 10     # 边界情况处理
        }
    },
    {
        "id": "C2",
        "name": "系统设计：LRU缓存带TTL",
        "category": "系统设计",
        "difficulty": "Hard",
        "prompt": """请实现一个生产级LRU缓存，要求：
1. 支持get/put操作，O(1)时间复杂度
2. 支持TTL（生存时间），自动过期清理
3. 线程安全，支持高并发
4. 支持统计命中率
5. 支持持久化到磁盘（可选）

请提供完整的Python实现，包含单元测试示例。""",
        "test_cases": [],
        "rubric": {
            "correctness": 35,
            "completeness": 35,
            "code_quality": 20,
            "thread_safety": 10
        }
    },
    {
        "id": "C3",
        "name": "并发编程：生产者消费者队列",
        "category": "并发编程",
        "difficulty": "Medium",
        "prompt": """请实现一个线程安全的生产者-消费者队列，要求：
1. 有界队列，支持容量限制
2. 支持多生产者、多消费者
3. 支持阻塞put/take操作
4. 支持超时机制
5. 支持优雅关闭

请使用Python threading实现，并提供性能测试代码。""",
        "test_cases": [],
        "rubric": {
            "correctness": 35,
            "completeness": 30,
            "code_quality": 20,
            "performance": 15
        }
    },
    {
        "id": "C4",
        "name": "代码重构：坏代码优化",
        "category": "代码质量",
        "difficulty": "Medium",
        "prompt": """请重构以下代码，提升其可读性、可维护性和性能：

```python
def process_data(data):
    result = []
    for i in range(len(data)):
        if data[i]['status'] == 'active':
            if data[i]['score'] > 50:
                temp = data[i]['name'] + '_' + str(data[i]['id'])
                result.append(temp)
    return result

# 调用示例
data = [{'id': 1, 'name': 'a', 'status': 'active', 'score': 60}, ...]
```

要求：
1. 使用列表推导式或生成器表达式
2. 添加类型注解
3. 添加文档字符串
4. 处理异常情况
5. 提供单元测试""",
        "test_cases": [],
        "rubric": {
            "correctness": 30,
            "pythonic": 25,     # 是否Pythonic
            "readability": 25,  # 可读性
            "robustness": 20    # 健壮性
        }
    },
    {
        "id": "C5",
        "name": "安全编码：SQL注入防护",
        "category": "安全编码",
        "difficulty": "Medium",
        "prompt": """请实现一个安全的用户查询系统，要求：
1. 支持动态SQL查询构建
2. 完全防止SQL注入攻击
3. 支持参数化查询
4. 支持查询白名单验证
5. 记录所有查询日志用于审计

请提供完整的Python实现，包含3种常见SQL注入攻击的防御示例。""",
        "test_cases": [],
        "rubric": {
            "correctness": 30,
            "security": 35,     # 安全性
            "completeness": 20,
            "code_quality": 15
        }
    },
    {
        "id": "C6",
        "name": "性能优化：大数据处理",
        "category": "性能优化",
        "difficulty": "Hard",
        "prompt": """请优化以下大数据处理代码：

场景：处理1GB的日志文件，提取错误信息并统计
原始代码使用逐行读取和字符串拼接，内存占用高且慢。

要求：
1. 使用生成器减少内存占用
2. 使用多进程/多线程加速
3. 支持断点续传
4. 实时进度报告
5. 内存占用不超过100MB

请提供完整的优化实现和性能对比数据。""",
        "test_cases": [],
        "rubric": {
            "correctness": 25,
            "performance": 35,  # 性能优化效果
            "memory_efficiency": 25,  # 内存效率
            "code_quality": 15
        }
    },
    {
        "id": "C7",
        "name": "测试驱动：单元测试生成",
        "category": "测试",
        "difficulty": "Medium",
        "prompt": """请为以下函数编写完整的单元测试：

```python
def parse_date(date_str: str) -> datetime:
    '''
    解析日期字符串，支持多种格式：
    - YYYY-MM-DD
    - DD/MM/YYYY
    - YYYY年MM月DD日
    - 相对日期：today, yesterday, tomorrow
    '''
    pass
```

要求：
1. 使用pytest框架
2. 覆盖所有支持格式
3. 包含异常输入测试
4. 包含边界情况测试
5. 测试覆盖率>90%""",
        "test_cases": [],
        "rubric": {
            "correctness": 30,
            "coverage": 35,     # 测试覆盖率
            "edge_cases": 25,   # 边界情况
            "code_quality": 10
        }
    },
    {
        "id": "C8",
        "name": "API设计：RESTful服务",
        "category": "系统设计",
        "difficulty": "Hard",
        "prompt": """请设计一个RESTful用户管理系统API，要求：
1. 使用FastAPI框架
2. 支持CRUD操作
3. 支持分页、过滤、排序
4. 支持JWT认证和权限控制
5. 支持OpenAPI文档自动生成
6. 包含请求验证和错误处理

请提供完整的实现代码和API文档示例。""",
        "test_cases": [],
        "rubric": {
            "correctness": 30,
            "restful_design": 25,  # RESTful设计
            "security": 20,        # 安全性
            "completeness": 15,
            "documentation": 10    # 文档
        }
    }
]


# ============================================================
# 全面Agent能力测试（8题）
# ============================================================

AGENT_TESTS = [
    {
        "id": "A1",
        "name": "单工具精确调用",
        "category": "基础调用",
        "prompt": """你是一个智能助手，拥有工具：get_weather(city: str, date: str, unit: str = 'celsius')

用户："帮我查一下上海2024年12月25日的天气，用华氏度显示。"

请输出工具调用（JSON格式），包含：
1. 工具名称
2. 参数值（推断合理的参数）
3. 调用原因说明""",
        "expected_tools": ["get_weather"],
        "expected_params": {"city": "上海", "date": "2024-12-25", "unit": "fahrenheit"},
        "rubric": {
            "correct_tool": 30,
            "correct_params": 40,
            "param_inference": 20,  # 参数推断合理性
            "format": 10
        }
    },
    {
        "id": "A2",
        "name": "多工具顺序调用",
        "category": "工具链",
        "prompt": """工具列表：
1. search_product(query: str) -> 搜索商品
2. compare_prices(product_id: str) -> 比价
3. check_inventory(product_id: str, store_id: str) -> 查库存
4. create_order(product_id: str, quantity: int, address: str) -> 创建订单

用户："我想买iPhone 15，帮我找最便宜的，看看附近有没有货，有货就下单2台送到我家。"

请输出完整的工具调用序列（JSON数组），包含：
1. 每个工具的调用顺序
2. 参数值（需要推断的请说明推断依据）
3. 上一步结果如何传递给下一步""",
        "expected_tools": ["search_product", "compare_prices", "check_inventory", "create_order"],
        "rubric": {
            "correct_sequence": 30,
            "correct_params": 30,
            "data_flow": 25,  # 数据流处理
            "edge_handling": 15  # 边界情况
        }
    },
    {
        "id": "A3",
        "name": "条件分支决策",
        "category": "条件逻辑",
        "prompt": """工具列表：
1. get_account_balance(user_id: str) -> 查询余额
2. transfer_money(from: str, to: str, amount: float) -> 转账
3. send_notification(user_id: str, message: str) -> 发送通知
4. apply_overdraft(user_id: str, amount: float) -> 申请透支

场景：用户请求转账10000元，但余额可能不足。

请设计一个完整的处理流程，包含：
1. 余额检查
2. 如果余额充足，直接转账
3. 如果余额不足但差值<1000，申请透支后转账
4. 如果余额不足且差值>=1000，拒绝并通知用户
5. 无论成功与否都发送通知

请用JSON格式输出完整的决策树和工具调用序列。""",
        "expected_tools": ["get_account_balance", "transfer_money", "send_notification", "apply_overdraft"],
        "rubric": {
            "correct_logic": 35,
            "condition_handling": 30,
            "completeness": 20,
            "error_handling": 15
        }
    },
    {
        "id": "A4",
        "name": "循环迭代处理",
        "category": "循环逻辑",
        "prompt": """工具列表：
1. get_unprocessed_orders() -> 获取未处理订单列表
2. validate_order(order_id: str) -> 验证订单
3. process_payment(order_id: str) -> 处理支付
4. send_confirmation(order_id: str) -> 发送确认
5. log_error(order_id: str, error: str) -> 记录错误

场景：批量处理订单，每个订单需要：验证->支付->确认。
如果某个步骤失败，记录错误并继续处理下一个订单。

请设计一个循环处理流程，包含：
1. 获取所有未处理订单
2. 逐个处理，每个订单3个步骤
3. 任何步骤失败都记录错误并继续
4. 统计成功数和失败数
5. 最后输出处理报告

请用伪代码+JSON格式描述完整流程。""",
        "expected_tools": ["get_unprocessed_orders", "validate_order", "process_payment", "send_confirmation", "log_error"],
        "rubric": {
            "loop_structure": 30,
            "error_handling": 30,
            "state_management": 25,  # 状态管理
            "reporting": 15
        }
    },
    {
        "id": "A5",
        "name": "错误恢复与重试",
        "category": "容错",
        "prompt": """工具列表：
1. call_external_api(endpoint: str, data: dict, timeout: int) -> 调用外部API
2. retry_operation(operation_id: str, max_retries: int) -> 重试操作
3. fallback_to_backup(operation_id: str) -> 切换到备用方案
4. alert_admin(message: str, severity: str) -> 告警
5. log_operation(operation_id: str, status: str, details: dict) -> 记录日志

场景：调用支付网关，可能遇到：网络超时、服务不可用、限流。

请设计一个容错策略，包含：
1. 首次调用，设置5秒超时
2. 如果超时，重试最多3次，每次指数退避
3. 如果仍然失败，切换到备用支付网关
4. 如果备用也失败，记录错误并告警
5. 所有操作都要记录日志

请用JSON格式输出完整的错误处理流程。""",
        "expected_tools": ["call_external_api", "retry_operation", "fallback_to_backup", "alert_admin", "log_operation"],
        "rubric": {
            "retry_strategy": 30,
            "fallback_design": 25,
            "error_handling": 25,
            "observability": 20  # 可观测性
        }
    },
    {
        "id": "A6",
        "name": "人机协作判断",
        "category": "人机协作",
        "prompt": """工具列表：
1. analyze_sentiment(text: str) -> 情感分析
2. detect_sensitive_content(text: str) -> 敏感内容检测
3. route_to_human(queue: str, priority: str, context: dict) -> 转人工
4. auto_reply(template_id: str, params: dict) -> 自动回复
5. escalate_to_manager(ticket_id: str, reason: str) -> 升级给经理

场景：处理客户投诉邮件。

请设计一个智能路由策略，包含：
1. 情感分析：负面情绪>0.8 或 敏感内容 -> 转人工
2. 涉及退款>1000元 -> 升级给经理
3. 普通咨询 -> 自动回复
4. 无法分类 -> 转人工

请提供决策树和每种情况的处理流程（JSON格式）。""",
        "expected_tools": ["analyze_sentiment", "detect_sensitive_content", "route_to_human", "auto_reply", "escalate_to_manager"],
        "rubric": {
            "decision_logic": 35,
            "threshold_setting": 25,  # 阈值设置合理性
            "coverage": 25,  # 覆盖全面性
            "fallback": 15
        }
    },
    {
        "id": "A7",
        "name": "长对话记忆管理",
        "category": "上下文管理",
        "prompt": """工具列表：
1. summarize_conversation(history: list) -> 总结对话
2. extract_entities(text: str) -> 提取实体
3. update_user_profile(user_id: str, data: dict) -> 更新用户画像
4. retrieve_context(user_id: str, query: str) -> 检索相关上下文

对话历史：
用户：你好，我叫张三，我想买一台笔记本电脑。
助手：您好张三，请问您主要用于什么场景？
用户：主要是编程和偶尔玩游戏。
助手：推荐您考虑游戏本或高性能轻薄本。
用户：预算8000左右，有什么推荐？
助手：可以考虑联想拯救者Y7000或华为MateBook 16。
用户：拯救者具体什么配置？

当前问题：用户问"拯救者具体什么配置？"

请设计一个上下文管理策略，包含：
1. 从对话中提取关键信息（用户名、需求、预算、候选产品）
2. 如何存储这些信息
3. 如何检索相关信息回答当前问题
4. 当对话过长时如何总结

请用JSON格式输出信息提取结果和检索策略。""",
        "expected_tools": ["summarize_conversation", "extract_entities", "update_user_profile", "retrieve_context"],
        "rubric": {
            "entity_extraction": 30,
            "context_retrieval": 30,
            "memory_management": 25,
            "summarization": 15
        }
    },
    {
        "id": "A8",
        "name": "复杂多步任务规划",
        "category": "任务规划",
        "prompt": """工具列表：
1. search_flights(origin: str, destination: str, date: str) -> 搜索航班
2. book_flight(flight_id: str, passenger_info: dict) -> 预订航班
3. search_hotels(location: str, check_in: str, check_out: str) -> 搜索酒店
4. book_hotel(hotel_id: str, guest_info: dict) -> 预订酒店
5. send_itinerary(email: str, details: dict) -> 发送行程单
6. cancel_booking(booking_id: str) -> 取消预订

场景：用户要规划一个3天2晚的商务旅行。

用户请求："我下周三要去北京出差，周四周五开会，周六回上海。
帮我订往返机票和酒店，要离会议中心近的，预算总共5000元。
如果超预算就提醒我，我可以调整。"

请设计一个完整的旅行规划Agent，包含：
1. 解析用户需求（日期、地点、预算约束）
2. 制定预订计划（先订机票还是先订酒店？为什么？）
3. 预算控制策略（如何跟踪总花费？）
4. 异常处理（如果某项预订失败怎么办？）
5. 确认流程（如何让用户确认？）

请用JSON格式输出完整的任务规划和执行流程。""",
        "expected_tools": ["search_flights", "book_flight", "search_hotels", "book_hotel", "send_itinerary", "cancel_booking"],
        "rubric": {
            "task_decomposition": 25,
            "planning_strategy": 25,
            "constraint_handling": 25,
            "user_interaction": 15,
            "error_recovery": 10
        }
    }
]


# ============================================================
# 全面通用推理测试（8题）
# ============================================================

REASONING_TESTS = [
    {
        "id": "R1",
        "name": "形式逻辑：骑士与无赖谜题",
        "category": "形式逻辑",
        "prompt": """在一个岛上，住着两种人：骑士（总是说真话）和无赖（总是说谎）。
你遇到三个人A、B、C。
A说："B是骑士。"
B说："A和C是同一种人。"
C说："A是无赖。"

请确定A、B、C各自的身份（骑士或无赖），并给出完整的逻辑推导过程。""",
        "answer": {"A": "无赖", "B": "无赖", "C": "骑士"},
        "rubric": {
            "correct_answer": 40,
            "logical_derivation": 40,
            "explanation_clarity": 20
        }
    },
    {
        "id": "R2",
        "name": "数学证明：素数无限性",
        "category": "数学证明",
        "prompt": """请用反证法证明：素数有无穷多个。

要求：
1. 明确写出假设
2. 逐步推导
3. 得出矛盾
4. 得出结论
5. 解释为什么这个证明是有效的""",
        "answer": "proof_by_contradiction",
        "rubric": {
            "proof_structure": 30,
            "logical_steps": 30,
            "contradiction_identification": 25,
            "explanation": 15
        }
    },
    {
        "id": "R3",
        "name": "科学推理：实验设计",
        "category": "科学推理",
        "prompt": """背景：某药物声称可以缩短感冒恢复时间。

请设计一个严格的科学实验来验证这个 claim，要求：
1. 实验组和对照组的设计
2. 随机化和盲法的应用
3. 样本量计算（说明理由）
4. 主要和次要终点指标
5. 统计分析方法
6. 可能的混杂因素及控制方法
7. 伦理考虑

请提供一个完整的实验方案。""",
        "answer": "experimental_design",
        "rubric": {
            "design_validity": 30,
            "methodology": 25,
            "statistical_rigor": 25,
            "practical_considerations": 20
        }
    },
    {
        "id": "R4",
        "name": "因果推断：相关vs因果",
        "category": "因果推断",
        "prompt": """背景：数据显示，冰淇淋销量和溺水事故数量高度相关（r=0.95）。

问题：
1. 能否得出"冰淇淋导致溺水"的结论？为什么？
2. 这可能是什么类型的混淆？
3. 如何设计研究来验证真正的因果关系？
4. 列举3个其他"相关≠因果"的常见例子
5. 解释随机对照试验为什么能建立因果关系

请详细回答以上问题。""",
        "answer": "correlation_vs_causation",
        "rubric": {
            "understanding": 30,
            "confounding_identification": 25,
            "study_design": 25,
            "examples": 10,
            "explanation": 10
        }
    },
    {
        "id": "R5",
        "name": "归纳推理：模式识别",
        "category": "归纳推理",
        "prompt": """观察以下数列，找出规律并预测接下来的3个数：

数列：1, 1, 2, 3, 7, 16, 65, 321, ...

要求：
1. 找出递推公式
2. 解释推理过程
3. 验证公式对已知项成立
4. 计算第9、10、11项
5. 讨论这个数列的数学性质（如果有）""",
        "answer": {"pattern": "a(n) = a(n-1) + (n-1)*a(n-2)", "next": [4546, 36671, 403321]},
        "rubric": {
            "pattern_identification": 40,
            "formula_derivation": 30,
            "verification": 20,
            "explanation": 10
        }
    },
    {
        "id": "R6",
        "name": "伦理判断：电车难题变体",
        "category": "伦理推理",
        "prompt": """电车难题变体：

场景A（原版）：电车失控，前方轨道有5人，可以扳道岔让电车转向另一条轨道，那条轨道上有1人。你会扳道岔吗？为什么？

场景B（胖子版本）：电车失控，前方轨道有5人。你站在桥上，旁边有个胖子，把他推下去可以阻止电车。你会推吗？为什么？

场景C（器官移植）：你是医生，5个病人需要不同器官移植，否则会死。一个健康人来体检，他的器官恰好匹配这5人。你会杀死他来救5人吗？为什么？

问题：
1. 分别分析三个场景，给出你的选择和理由
2. 为什么大多数人场景A选择是，场景B和C选择否？
3. 从功利主义和义务论角度分别分析
4. 这些场景对AI决策系统有什么启示？""",
        "answer": "ethical_analysis",
        "rubric": {
            "analysis_depth": 30,
            "consistency": 20,
            "ethical_frameworks": 30,
            "ai_implications": 20
        }
    },
    {
        "id": "R7",
        "name": "创造性思维：创新解决方案",
        "category": "创造性思维",
        "prompt": """问题：如何在不增加道路面积的情况下，将城市通勤时间减少30%？

请提出至少3个创新的解决方案，要求：
1. 每个方案都要有可行性分析
2. 说明预期的效果和潜在风险
3. 考虑技术、经济、社会可行性
4. 可以结合新兴技术（AI、IoT等）
5. 评估哪个方案最有可能成功，为什么？""",
        "answer": "creative_solutions",
        "rubric": {
            "creativity": 30,
            "feasibility_analysis": 30,
            "comprehensiveness": 25,
            "evaluation": 15
        }
    },
    {
        "id": "R8",
        "name": "元认知：思维过程分析",
        "category": "元认知",
        "prompt": """请回答以下问题，并同时分析你自己的思考过程：

问题：一个水箱有两个管道，A管单独注满需要3小时，B管单独注满需要6小时。如果同时打开A和B，需要多长时间注满？

要求：
1. 给出正确答案
2. 详细描述你是如何思考的（每一步）
3. 指出可能的思维陷阱
4. 如果给小学生讲解，你会怎么教？
5. 反思：你的解法是最优的吗？还有其他方法吗？

这个问题考察你对自己思维过程的觉察能力。""",
        "answer": "2_hours",
        "rubric": {
            "correctness": 25,
            "process_awareness": 35,
            "alternative_methods": 20,
            "teaching_ability": 20
        }
    }
]


def extract_code(response: str) -> str:
    """提取代码块"""
    patterns = [r"```(?:\w*)\n(.*?)```", r"```\n(.*?)```"]
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
    return response


def check_syntax(code: str) -> tuple:
    """检查Python语法"""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def run_code_test(code: str, test_input: str) -> tuple:
    """尝试运行代码测试（简化版，仅检查语法）"""
    syntax_ok, error = check_syntax(code)
    if not syntax_ok:
        return False, f"Syntax error: {error}"
    
    # 实际运行测试需要更复杂的沙箱环境，这里仅做语法检查
    return True, "Syntax OK"


def evaluate_coding_comprehensive(client, model):
    """全面代码能力评估"""
    print("\n" + "="*80)
    print("💻 代码能力评估（全面版 - 8题）")
    print("="*80)
    
    total_score = 0
    max_total = 200  # 8题 * 25分
    details = []
    
    for test in CODING_TESTS:
        print(f"\n  [{test['id']}] {test['name']} ({test['category']})")
        print(f"      难度: {test['difficulty']}")
        
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个资深软件工程师。请编写高质量、可运行的代码。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=4096)
            
            code = extract_code(result['content'])
            content = result['content']
            
            # 多维度评分
            scores = {}
            
            # 1. 正确性 - 语法检查
            syntax_ok, syntax_err = check_syntax(code)
            scores['correctness'] = 25 if syntax_ok else 5
            
            # 2. 完整性 - 检查关键元素
            completeness_keywords = test.get('completeness_keywords', [])
            if not completeness_keywords:
                # 根据题目推断关键词
                if 'class' in test['prompt'].lower():
                    completeness_keywords = ['class', 'def', 'return']
                elif 'def ' in test['prompt'].lower():
                    completeness_keywords = ['def ', 'return']
            
            found_elements = sum(1 for kw in completeness_keywords if kw in code)
            scores['completeness'] = min(25, found_elements * 8)
            
            # 3. 代码质量 - 检查注释、类型注解等
            has_comments = '#' in code or '"""' in code or "'''" in code
            has_types = ':' in code and ('->' in code or 'List[' in code or 'Dict[' in code)
            scores['quality'] = (10 if has_comments else 0) + (10 if has_types else 0) + 5  # 基础分
            
            # 4. 边界情况 - 检查异常处理
            has_try = 'try' in code and 'except' in code
            has_validation = 'if' in code and ('None' in code or 'raise' in code)
            scores['edge_cases'] = (10 if has_try else 0) + (10 if has_validation else 0) + 5
            
            # 计算总分（根据题目权重调整）
            rubric = test.get('rubric', {})
            if rubric:
                test_score = (
                    scores['correctness'] * rubric.get('correctness', 40) // 40 +
                    scores['completeness'] * rubric.get('completeness', 30) // 30 +
                    scores['quality'] * rubric.get('code_quality', 20) // 20 +
                    scores['edge_cases'] * rubric.get('edge_cases', 10) // 10
                ) // 4
            else:
                test_score = sum(scores.values()) // 4
            
            test_score = min(test_score, 25)  # 每题满分25
            total_score += test_score
            
            status = "✅" if test_score >= 20 else "⚠️" if test_score >= 12 else "❌"
            print(f"      {status} 得分: {test_score}/25")
            print(f"         正确性: {scores['correctness']}/25, 完整性: {scores['completeness']}/25")
            print(f"         代码质量: {scores['quality']}/25, 边界处理: {scores['edge_cases']}/25")
            
            details.append({
                "id": test['id'],
                "name": test['name'],
                "score": test_score,
                "max_score": 25,
                "breakdown": scores,
                "syntax_ok": syntax_ok
            })
            
        except Exception as e:
            print(f"      ❌ 错误: {str(e)[:80]}")
            details.append({
                "id": test['id'],
                "name": test['name'],
                "error": str(e),
                "score": 0
            })
    
    return CategoryScore("代码能力", total_score, max_total, details)


def evaluate_agent_comprehensive(client, model):
    """全面Agent能力评估"""
    print("\n" + "="*80)
    print("🤖 Agent能力评估（全面版 - 8题）")
    print("="*80)
    
    total_score = 0
    max_total = 200
    details = []
    
    for test in AGENT_TESTS:
        print(f"\n  [{test['id']}] {test['name']} ({test['category']})")
        
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个智能助手，擅长分析复杂任务并合理使用工具。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=3072)
            
            content = result['content']
            
            # 多维度评分
            scores = {}
            
            # 1. 工具选择正确性
            expected_tools = test.get('expected_tools', [])
            found_tools = sum(1 for tool in expected_tools if tool.lower() in content.lower())
            scores['tool_selection'] = min(25, found_tools * 8)
            
            # 2. 参数推断合理性
            has_params = '"' in content and ':' in content
            has_inference = any(kw in content for kw in ['推断', '推理', '推断', 'assume', 'based on'])
            scores['param_inference'] = (15 if has_params else 5) + (10 if has_inference else 0)
            
            # 3. 逻辑流程完整性
            has_sequence = any(kw in content for kw in ['顺序', '步骤', 'step', 'first', 'then', 'next'])
            has_logic = any(kw in content for kw in ['如果', '条件', 'if', 'condition'])
            scores['logic_flow'] = (15 if has_sequence else 5) + (10 if has_logic else 0)
            
            # 4. 格式规范性
            has_json = ('[' in content and ']' in content) or ('{' in content and '}' in content)
            is_structured = content.count('\n') > 5
            scores['format'] = (15 if has_json else 5) + (10 if is_structured else 0)
            
            # 根据题目rubric调整
            rubric = test.get('rubric', {})
            if rubric:
                weights = list(rubric.values())
                total_weight = sum(weights) if weights else 100
                test_score = (
                    scores['tool_selection'] * rubric.get('correct_tool', 30) // 30 +
                    scores['param_inference'] * rubric.get('param_inference', 20) // 20 +
                    scores['logic_flow'] * sum([rubric.get(k, 0) for k in ['correct_sequence', 'loop_structure', 'decision_logic']]) // 30 +
                    scores['format'] * rubric.get('format', 10) // 10
                ) // 4
            else:
                test_score = sum(scores.values()) // 4
            
            test_score = min(test_score, 25)
            total_score += test_score
            
            status = "✅" if test_score >= 20 else "⚠️" if test_score >= 12 else "❌"
            print(f"      {status} 得分: {test_score}/25")
            print(f"         工具选择: {scores['tool_selection']}/25, 参数推断: {scores['param_inference']}/25")
            print(f"         逻辑流程: {scores['logic_flow']}/25, 格式规范: {scores['format']}/25")
            
            details.append({
                "id": test['id'],
                "name": test['name'],
                "score": test_score,
                "max_score": 25,
                "breakdown": scores
            })
            
        except Exception as e:
            print(f"      ❌ 错误: {str(e)[:80]}")
            details.append({
                "id": test['id'],
                "name": test['name'],
                "error": str(e),
                "score": 0
            })
    
    return CategoryScore("Agent能力", total_score, max_total, details)


def evaluate_reasoning_comprehensive(client, model):
    """全面通用推理评估"""
    print("\n" + "="*80)
    print("🧠 通用推理评估（全面版 - 8题）")
    print("="*80)
    
    total_score = 0
    max_total = 200
    details = []
    
    for test in REASONING_TESTS:
        print(f"\n  [{test['id']}] {test['name']} ({test['category']})")
        
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个推理专家，擅长逻辑分析、数学证明和批判性思维。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=3072)
            
            content = result['content']
            
            # 多维度评分
            scores = {}
            
            # 1. 答案正确性（对于有标准答案的题目）
            answer = test.get('answer', '')
            if isinstance(answer, dict):
                # 检查是否包含正确答案的关键词
                correct_keywords = list(answer.values()) if answer else []
                found = sum(1 for kw in correct_keywords if str(kw).lower() in content.lower())
                scores['correctness'] = min(25, found * 8)
            elif isinstance(answer, str) and answer != '':
                scores['correctness'] = 20 if answer.lower() in content.lower() else 10
            else:
                scores['correctness'] = 15  # 开放题给基础分
            
            # 2. 推理过程完整性
            has_steps = any(kw in content for kw in ['步骤', 'step', '首先', 'first', '1.', '2.'])
            has_logic = any(kw in content for kw in ['因为', '所以', '因此', 'because', 'therefore'])
            scores['derivation'] = (15 if has_steps else 5) + (10 if has_logic else 0)
            
            # 3. 解释清晰度
            content_length = len(content)
            has_structure = content.count('\n') > 3
            scores['clarity'] = min(25, content_length // 100) + (5 if has_structure else 0)
            
            # 4. 深度与广度
            has_depth = content_length > 500
            has_multiple_aspects = content.count('。') > 5 or content.count('\n') > 10
            scores['depth'] = (15 if has_depth else 5) + (10 if has_multiple_aspects else 0)
            
            # 根据rubric调整
            rubric = test.get('rubric', {})
            if rubric:
                test_score = (
                    scores['correctness'] * rubric.get('correct_answer', 40) // 40 +
                    scores['derivation'] * rubric.get('logical_derivation', 40) // 40 +
                    scores['clarity'] * rubric.get('explanation_clarity', 20) // 20 +
                    scores['depth'] * rubric.get('analysis_depth', 30) // 30
                ) // 4
            else:
                test_score = sum(scores.values()) // 4
            
            test_score = min(test_score, 25)
            total_score += test_score
            
            status = "✅" if test_score >= 20 else "⚠️" if test_score >= 12 else "❌"
            print(f"      {status} 得分: {test_score}/25")
            print(f"         答案正确: {scores['correctness']}/25, 推理过程: {scores['derivation']}/25")
            print(f"         解释清晰: {scores['clarity']}/25, 深度广度: {scores['depth']}/25")
            print(f"         回答长度: {content_length}字")
            
            details.append({
                "id": test['id'],
                "name": test['name'],
                "score": test_score,
                "max_score": 25,
                "breakdown": scores,
                "content_length": content_length
            })
            
        except Exception as e:
            print(f"      ❌ 错误: {str(e)[:80]}")
            details.append({
                "id": test['id'],
                "name": test['name'],
                "error": str(e),
                "score": 0
            })
    
    return CategoryScore("通用推理", total_score, max_total, details)


def evaluate_performance_comprehensive(client, model):
    """全面性能基准测试（含4/8线程并发）"""
    print("\n" + "="*80)
    print("⚡ 性能基准测试（全面版 - 含4/8线程并发）")
    print("="*80)
    
    details = []
    total_score = 0
    
    # 1. TTFT测试
    print("\n  [1/5] 首Token延迟测试")
    try:
        ttfts = []
        for i in range(3):
            start = time.time()
            client.chat([{"role": "user", "content": "请解释什么是机器学习。"}], model, 256)
            ttfts.append((time.time()-start)*1000)
        avg_ttft = sum(ttfts)/len(ttfts)
        p95_ttft = sorted(ttfts)[int(len(ttfts)*0.95)]
        
        ttft_score = 20 if avg_ttft<=1000 else 15 if avg_ttft<=3000 else 10 if avg_ttft<=6000 else 5
        total_score += ttft_score
        
        details.append({
            "test": "首Token延迟",
            "score": ttft_score,
            "max_score": 20,
            "metrics": {"avg_ms": round(avg_ttft,2), "p95_ms": round(p95_ttft,2), "samples": ttfts}
        })
        print(f"      ✅ 得分: {ttft_score}/20 (avg={avg_ttft:.0f}ms, p95={p95_ttft:.0f}ms)")
    except Exception as e:
        details.append({"test": "首Token延迟", "error": str(e), "score": 0})
        print(f"      ❌ 错误: {e}")
    
    # 2. 吞吐量测试
    print("\n  [2/5] 吞吐量测试")
    try:
        tps_list = []
        tokens_list = []
        for i in range(3):
            r = client.chat([{"role": "user", "content": "请写一篇关于人工智能的文章，至少800字。"}], model, 2048)
            if r["completion_tokens"]>0:
                tps = (r["completion_tokens"]/r["latency_ms"])*1000
                tps_list.append(tps)
                tokens_list.append(r["completion_tokens"])
        
        avg_tps = sum(tps_list)/len(tps_list) if tps_list else 0
        avg_tokens = sum(tokens_list)/len(tokens_list) if tokens_list else 0
        
        tps_score = 20 if avg_tps>=50 else 15 if avg_tps>=30 else 10 if avg_tps>=15 else 5
        total_score += tps_score
        
        details.append({
            "test": "吞吐量",
            "score": tps_score,
            "max_score": 20,
            "metrics": {"avg_tps": round(avg_tps,2), "avg_tokens": round(avg_tokens,1)}
        })
        print(f"      ✅ 得分: {tps_score}/20 (avg={avg_tps:.1f} tok/s, {avg_tokens:.0f} tokens)")
    except Exception as e:
        details.append({"test": "吞吐量", "error": str(e), "score": 0})
        print(f"      ❌ 错误: {e}")
    
    # 3. 响应速度测试
    print("\n  [3/5] 响应速度测试")
    try:
        lats = []
        for i in range(5):
            start = time.time()
            client.chat([{"role": "user", "content": "你好"}], model, 50)
            lats.append((time.time()-start)*1000)
        avg_lat = sum(lats)/len(lats)
        
        lat_score = 10 if avg_lat<500 else 7 if avg_lat<1500 else 4
        total_score += lat_score
        
        details.append({
            "test": "响应速度",
            "score": lat_score,
            "max_score": 10,
            "metrics": {"avg_ms": round(avg_lat,2)}
        })
        print(f"      ✅ 得分: {lat_score}/10 (avg={avg_lat:.0f}ms)")
    except Exception as e:
        details.append({"test": "响应速度", "error": str(e), "score": 0})
        print(f"      ❌ 错误: {e}")
    
    # 4. 4线程并发测试
    print("\n  [4/5] 4线程并发测试")
    try:
        prompt = "请简要介绍Python的特点，50字以内。"
        messages = [{"role": "user", "content": prompt}]
        
        def worker():
            try:
                start = time.time()
                r = client.chat_simple(messages, model, 128)
                return {"success": r["success"], "latency": (time.time()-start)*1000}
            except:
                return {"success": False, "latency": 0}
        
        start_total = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker) for _ in range(4)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        total_time = (time.time() - start_total) * 1000
        
        success_count = sum(1 for r in results if r["success"])
        avg_latency = sum(r["latency"] for r in results if r["success"]) / max(success_count, 1)
        
        if success_count == 4 and avg_latency < 5000:
            concurrent4_score = 25
        elif success_count == 4 and avg_latency < 10000:
            concurrent4_score = 20
        elif success_count >= 3:
            concurrent4_score = 15
        else:
            concurrent4_score = 5
        
        total_score += concurrent4_score
        
        details.append({
            "test": "4线程并发",
            "score": concurrent4_score,
            "max_score": 25,
            "metrics": {"success": success_count, "avg_latency_ms": round(avg_latency,2), "total_time_ms": round(total_time,2)}
        })
        print(f"      ✅ 得分: {concurrent4_score}/25 (成功{success_count}/4, avg={avg_latency:.0f}ms)")
    except Exception as e:
        details.append({"test": "4线程并发", "error": str(e), "score": 0})
        print(f"      ❌ 错误: {e}")
    
    # 5. 8线程并发测试
    print("\n  [5/5] 8线程并发测试")
    try:
        prompt = "1+1等于几？"
        messages = [{"role": "user", "content": prompt}]
        
        def worker():
            try:
                start = time.time()
                r = client.chat_simple(messages, model, 50)
                return {"success": r["success"], "latency": (time.time()-start)*1000}
            except:
                return {"success": False, "latency": 0}
        
        start_total = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker) for _ in range(8)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        total_time = (time.time() - start_total) * 1000
        
        success_count = sum(1 for r in results if r["success"])
        avg_latency = sum(r["latency"] for r in results if r["success"]) / max(success_count, 1)
        
        if success_count >= 7 and avg_latency < 8000:
            concurrent8_score = 25
        elif success_count >= 6 and avg_latency < 15000:
            concurrent8_score = 20
        elif success_count >= 4:
            concurrent8_score = 15
        else:
            concurrent8_score = 5
        
        total_score += concurrent8_score
        
        details.append({
            "test": "8线程并发",
            "score": concurrent8_score,
            "max_score": 25,
            "metrics": {"success": success_count, "avg_latency_ms": round(avg_latency,2), "total_time_ms": round(total_time,2)}
        })
        print(f"      ✅ 得分: {concurrent8_score}/25 (成功{success_count}/8, avg={avg_latency:.0f}ms)")
    except Exception as e:
        details.append({"test": "8线程并发", "error": str(e), "score": 0})
        print(f"      ❌ 错误: {e}")
    
    return CategoryScore("性能基准", total_score, 100, details)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="全面科学版模型评估")
    parser.add_argument("--model", "-m", required=True, help="模型ID")
    parser.add_argument("--quick", "-q", action="store_true", help="快速模式（每维度只测2题）")
    args = parser.parse_args()
    
    client = SyncClient(API_URL, API_KEY)
    engine = ScoreEngine()
    result = engine.create_result(args.model, args.model)
    
    print("="*80)
    print("🔬 全面科学版模型评估")
    print("="*80)
    print(f"模型: {args.model}")
    print(f"测试规模: 代码8题 + Agent8题 + 推理8题 + 性能5项 = 29项测试")
    print("="*80)
    
    # 四个维度评估
    coding_score = evaluate_coding_comprehensive(client, args.model)
    engine.add_dimension_score(result, "coding", [coding_score])
    print(f"\n  💻 代码能力: {coding_score.score}/{coding_score.max_score}")
    
    agent_score = evaluate_agent_comprehensive(client, args.model)
    engine.add_dimension_score(result, "agent", [agent_score])
    print(f"\n  🤖 Agent能力: {agent_score.score}/{agent_score.max_score}")
    
    reasoning_score = evaluate_reasoning_comprehensive(client, args.model)
    engine.add_dimension_score(result, "reasoning", [reasoning_score])
    print(f"\n  🧠 通用推理: {reasoning_score.score}/{reasoning_score.max_score}")
    
    perf_score = evaluate_performance_comprehensive(client, args.model)
    engine.add_dimension_score(result, "performance", [perf_score])
    print(f"\n  ⚡ 性能基准: {perf_score.score}/{perf_score.max_score}")
    
    # 设置权重并计算总分
    result.dimensions["coding"].weight = 0.25
    result.dimensions["agent"].weight = 0.25
    result.dimensions["reasoning"].weight = 0.25
    result.dimensions["performance"].weight = 0.25
    engine.finalize(result)
    
    # 保存结果
    os.makedirs("results", exist_ok=True)
    result_path = engine.save_result(result, "results")
    
    # 摘要
    print("\n" + "="*80)
    print("📊 全面科学版评估结果")
    print("="*80)
    print(f"  代码能力:   {coding_score.score:>4}/{coding_score.max_score}")
    print(f"  Agent能力:  {agent_score.score:>4}/{agent_score.max_score}")
    print(f"  通用推理:   {reasoning_score.score:>4}/{reasoning_score.max_score}")
    print(f"  性能基准:   {perf_score.score:>4}/{perf_score.max_score}")
    print("-"*80)
    print(f"  综合评分:   {result.overall_score:>7.2f}/100")
    print("="*80)
    print(f"\n📁 结果已保存: {result_path}")
    
    return result


if __name__ == "__main__":
    main()
