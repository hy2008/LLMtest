#!/usr/bin/env python3
"""
LM Studio 模型评估套件 - 完整增强版
包含：代码能力、Agent能力、通用推理（增强）、性能基准（含4线程并发）
"""

import os, sys, time, requests, json, re, ast, threading, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.score_engine import ScoreEngine, CategoryScore

API_URL = "http://59.55.125.214:1024"
API_KEY = "sk-lm-kkZxEu1e:YagcQehqsGQGNQD0cyIH"

class SyncClient:
    def __init__(self, base_url, api_key, timeout=180):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        self.timeout = timeout

    def chat(self, messages, model, max_tokens=4096):
        start = time.time()
        resp = self.session.post(f"{self.base_url}/v1/chat/completions",
            json={"model": model, "messages": messages, "temperature": 0.0, "max_tokens": max_tokens},
            timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "") or msg.get("reasoning_content", "")
        usage = data.get("usage", {})
        return {"content": content, "completion_tokens": usage.get("completion_tokens", 0), 
                "latency_ms": (time.time()-start)*1000, "success": True}

    def chat_simple(self, messages, model, max_tokens=512):
        """简化版，用于并发测试"""
        try:
            return self.chat(messages, model, max_tokens)
        except:
            return {"content": "", "completion_tokens": 0, "latency_ms": 0, "success": False}


# ============================================================
# 增强版代码能力测试
# ============================================================

CODING_TESTS = [
    {
        "name": "并发安全LRU缓存",
        "prompt": """请实现一个线程安全的 LRU 缓存类，要求：
1. 支持 get(key), put(key, value, ttl_seconds) 方法
2. 支持 TTL 过期机制，过期自动删除
3. 线程安全，支持高并发读写
4. 容量满时淘汰最近最少使用且未过期的条目
5. 提供一个 cleanup() 方法清理所有过期条目
请提供完整可运行的代码，包含必要的导入语句。只输出代码。""",
        "check": lambda code: (
            ("threading" in code.lower() or "Lock" in code or "RLock" in code) and
            ("ttl" in code.lower() or "expire" in code.lower()) and
            ("def get" in code) and ("def put" in code) and ("def cleanup" in code.lower())
        ),
        "max_score": 25,
        "deductions": {"missing_lock": -5, "missing_ttl": -5, "missing_cleanup": -3, "syntax_error": -10}
    },
    {
        "name": "表达式解析器",
        "prompt": """请实现一个数学表达式解析器和计算器，要求：
1. 支持四则运算: +, -, *, /
2. 支持括号改变优先级
3. 支持负数，如: -5 + 3
4. 支持浮点数
5. 处理除零错误，返回 None
6. 函数签名: def evaluate(expression: str) -> Optional[float]
示例: evaluate("2 + 3 * 4") = 14.0, evaluate("(2 + 3) * 4") = 20.0
只输出代码。""",
        "check": lambda code: (
            ("def evaluate" in code) and ("+" in code and "*" in code) and
            ("(" in code and ")" in code) and ("None" in code)
        ),
        "max_score": 25,
        "deductions": {"no_bracket": -5, "no_negative": -3, "no_div_zero": -5, "syntax_error": -10}
    },
    {
        "name": "异步任务调度器",
        "prompt": """请实现一个异步任务调度器，要求：
1. 支持添加任务: add_task(coro, priority=0)
2. 支持任务依赖: add_task(coro, dependencies=[task_id1, task_id2])
3. 支持并发限制: max_concurrent 参数
4. 支持任务取消和重试
5. 提供 run() 方法执行所有任务
6. 返回任务结果字典 {task_id: result}
使用 asyncio 实现，只输出代码。""",
        "check": lambda code: (
            ("asyncio" in code.lower()) and ("async def" in code) and ("add_task" in code) and
            ("priority" in code.lower() or "depend" in code.lower()) and ("max_concurrent" in code.lower())
        ),
        "max_score": 25,
        "deductions": {"no_priority": -3, "no_dependencies": -5, "no_concurrent_limit": -5, "no_retry": -3, "syntax_error": -10}
    },
    {
        "name": "SQL解析与验证",
        "prompt": """请实现一个简单的 SQL 解析器，要求：
1. 解析 SELECT 语句，提取: 表名、字段列表、WHERE条件、ORDER BY、LIMIT
2. 验证 SQL 语法是否正确
3. 检测潜在的 SQL 注入风险
4. 函数签名: def parse_select(sql: str) -> dict
返回格式: {"valid": True/False, "table": "...", "columns": [...], "where": "...", "order_by": [...], "limit": 10, "injection_risk": True/False}
只输出代码。""",
        "check": lambda code: (
            ("def parse" in code) and ("SELECT" in code.upper() or "select" in code.lower()) and
            ("WHERE" in code.upper() or "where" in code.lower()) and ("injection" in code.lower())
        ),
        "max_score": 25,
        "deductions": {"no_injection_check": -5, "no_order_by": -3, "no_limit": -2, "syntax_error": -10}
    }
]


# ============================================================
# 增强版Agent能力测试
# ============================================================

AGENT_TESTS = [
    {
        "name": "多工具组合调用",
        "prompt": """你是一个智能助手，拥有以下工具：
1. search_web(query: str) - 搜索网络信息
2. get_weather(city: str) - 获取城市天气
3. send_email(to: str, subject: str, body: str) - 发送邮件
4. create_calendar_event(title: str, start_time: str, end_time: str) - 创建日历事件
5. query_database(sql: str) - 执行SQL查询

用户请求：请帮我查一下北京明天的天气，如果会下雨就发邮件提醒我带伞（发到 my@email.com），同时在日历上创建一个"带伞"提醒事件，明天上午9点。

请分析这个请求，按顺序列出你需要调用的所有工具及其参数。使用JSON数组格式输出。""",
        "check": lambda resp: (
            ("get_weather" in resp or "weather" in resp.lower()) and
            ("send_email" in resp or "email" in resp.lower()) and
            ("calendar" in resp.lower() or "event" in resp.lower()) and
            ("[" in resp and "]" in resp)
        ),
        "max_score": 25
    },
    {
        "name": "工具参数推断",
        "prompt": """你是一个数据分析助手，拥有以下工具：
1. load_data(filepath: str, format: str) - 加载数据文件
2. filter_data(data_id: str, column: str, operator: str, value: any) - 筛选数据
3. aggregate(data_id: str, column: str, operation: str) - 聚合计算
4. plot_chart(data_id: str, chart_type: str, x_column: str, y_column: str) - 绘制图表
5. export_result(result_id: str, filepath: str, format: str) - 导出结果

用户请求：分析 sales_2024.csv 文件，找出销售额最高的前10个产品，画出柱状图，然后导出结果到 top_products.xlsx。

请推断所有需要的参数值，输出完整的工具调用序列（JSON数组格式）。""",
        "check": lambda resp: (
            ("load_data" in resp or "load" in resp.lower()) and
            ("filter" in resp.lower() or "sort" in resp.lower()) and
            ("plot" in resp.lower() or "chart" in resp.lower()) and
            ("export" in resp.lower()) and ("[" in resp)
        ),
        "max_score": 25
    },
    {
        "name": "错误处理与重试",
        "prompt": """你是一个API调用助手，拥有以下工具：
1. call_api(endpoint: str, params: dict) -> dict - 调用外部API
2. retry(func_name: str, max_attempts: int, delay_seconds: int) - 重试某个操作
3. log_error(error_msg: str) - 记录错误日志
4. send_alert(message: str, channel: str) - 发送告警

场景：你需要调用 /api/payment/process 接口处理支付。已知该接口可能因网络问题失败（返回 {"success": false, "error": "network_timeout"}）。

请设计一个完整的调用方案，包含：初始调用、错误检测逻辑、重试策略、最终失败处理。
输出你的思考过程和工具调用序列。""",
        "check": lambda resp: (
            ("retry" in resp.lower() or "重试" in resp) and
            ("error" in resp.lower() or "错误" in resp) and
            ("log" in resp.lower() or "记录" in resp) and
            ("alert" in resp.lower() or "告警" in resp)
        ),
        "max_score": 25
    },
    {
        "name": "多轮对话工具链",
        "prompt": """你是一个客服机器人助手，拥有以下工具：
1. get_user_info(user_id: str) - 获取用户信息
2. get_order_status(order_id: str) - 获取订单状态
3. create_refund(order_id: str, amount: float, reason: str) - 创建退款
4. transfer_to_human(department: str, context: str) - 转人工客服
5. send_coupon(user_id: str, coupon_type: str, amount: float) - 发放优惠券

对话历史：
用户: 我的订单还没到，订单号是 ORD12345
助手: 让我查一下...您的订单正在配送中，预计明天到达。
用户: 太慢了，我要退款！
助手: 好的，我帮您处理退款。
用户: 等等，退款要多久？能补偿我吗？

请分析当前对话状态，输出：1.当前需要调用的工具 2.后续可能需要的工具 3.完整的工具调用序列
使用JSON格式输出。""",
        "check": lambda resp: (
            ("refund" in resp.lower() or "退款" in resp) and
            ("coupon" in resp.lower() or "补偿" in resp) and
            ("order" in resp.lower()) and ("[" in resp or "{" in resp)
        ),
        "max_score": 25
    }
]


# ============================================================
# 增强版通用推理测试
# ============================================================

REASONING_TESTS = [
    {
        "name": "复杂逻辑推理",
        "prompt": """请解答以下逻辑推理题：

有五个人（A、B、C、D、E）参加一场比赛，已知：
1. A不是第一名也不是最后一名
2. B的排名比C高，但比D低
3. E的排名紧挨着A（前后都可）
4. C不是最后一名

请确定每个人的具体排名（1-5名），并给出完整的推理过程。""",
        "check": lambda resp: (
            # 应该包含排名信息
            any(x in resp for x in ["A", "B", "C", "D", "E"]) and
            # 应该有推理过程
            any(kw in resp.lower() for kw in ["因为", "所以", "推理", "因此", "根据"]) and
            # 应该有具体排名
            any(str(i) in resp for i in ["1", "2", "3", "4", "5"])
        ),
        "max_score": 25,
        "keywords": ["A", "B", "C", "D", "E", "排名", "第一", "第二", "第三", "第四", "第五"]
    },
    {
        "name": "数学建模与优化",
        "prompt": """请解决以下数学问题：

一个电商平台有100万用户，需要设计一个推荐系统。已知：
1. 每个用户每天平均浏览50个商品
2. 推荐系统需要在100ms内返回结果
3. 推荐准确率每提升1%，日活提升0.5%
4. 服务器成本：每增加一台服务器，月成本增加5000元，可支持10万用户

问题：
1. 如果当前推荐准确率是70%，要达到日活提升10%，需要提升到多少准确率？
2. 需要多少台服务器才能满足性能要求？
3. 总月成本是多少？

请给出详细的计算过程和公式。""",
        "check": lambda resp: (
            # 应该有计算过程
            any(kw in resp for kw in ["计算", "公式", "=", "%", "台", "元"]) and
            # 应该有具体数字答案
            any(str(i) in resp for i in ["80", "90", "10", "5000", "1000000"])
        ),
        "max_score": 25,
        "keywords": ["准确率", "服务器", "成本", "日活", "提升", "计算", "公式"]
    },
    {
        "name": "复杂阅读理解",
        "prompt": """请阅读以下技术文档并回答问题：

"分布式事务的Saga模式是一种长事务解决方案。它将一个大事务拆分为多个本地事务，每个本地事务有对应的补偿操作。如果某个本地事务失败，Saga会执行之前所有已完成事务的补偿操作，使系统回到一致状态。

Saga有两种协调方式：
1. 编排式（Choreography）：每个本地事务完成后发送事件，触发下一个事务
2. 编排式（Orchestration）：由中央协调器统一调度各事务的执行

Saga适用于以下场景：
- 业务流程较长，需要跨多个服务
- 对实时一致性要求不高，可接受最终一致性
- 每个本地事务都有明确的补偿操作

但Saga也有局限性：
- 补偿操作可能复杂且难以实现
- 隔离性问题：在事务执行过程中，其他操作可能看到中间状态
- 无法处理补偿操作本身失败的情况"

问题：
1. Saga模式的核心思想是什么？
2. 两种协调方式各有什么优缺点？
3. 什么情况下不适合使用Saga模式？
4. 文中提到的"隔离性问题"具体指什么？""",
        "check": lambda resp: (
            # 应该回答所有4个问题
            len([s for s in resp.split("\n") if s.strip().startswith(("1.", "2.", "3.", "4.", "一、", "二、", "三、", "四、"))]) >= 4 or
            resp.count("。") >= 4
        ),
        "max_score": 25,
        "keywords": ["本地事务", "补偿", "协调", "编排", "最终一致性", "隔离性", "中间状态"]
    },
    {
        "name": "深度知识问答",
        "prompt": """请详细解释以下概念，并比较它们的异同：

1. 强一致性（Strong Consistency）
2. 弱一致性（Weak Consistency）
3. 最终一致性（Eventual Consistency）
4. 因果一致性（Causal Consistency）

要求：
- 每个概念给出定义和典型应用场景
- 说明它们之间的包含关系或层级关系
- 举例说明在什么情况下应该选择哪种一致性模型
- 分析CAP定理与这些一致性模型的关系""",
        "check": lambda resp: (
            # 应该包含所有4种一致性
            all(kw in resp.lower() for kw in ["强一致性", "弱一致性", "最终一致性", "因果一致性"]) or
            all(kw in resp.lower() for kw in ["strong", "weak", "eventual", "causal"])
        ),
        "max_score": 25,
        "keywords": ["一致性", "CAP", "分布式", "场景", "包含", "层级", "强", "弱", "最终", "因果"]
    }
]


def extract_code(response: str) -> str:
    patterns = [r"```(?:\w*)\n(.*?)```", r"```\n(.*?)```"]
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
    return response


def check_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def evaluate_coding(client, model):
    print("\n" + "="*60)
    print("💻 代码能力评估")
    print("="*60)
    
    total_score = 0
    details = []
    
    for test in CODING_TESTS:
        print(f"\n  测试: {test['name']}")
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个资深软件工程师。请编写高质量、可运行的代码。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=4096)
            
            code = extract_code(result['content'])
            base_passed = test['check'](code)
            syntax_ok, syntax_err = check_syntax(code)
            
            score = test['max_score'] if base_passed else test['max_score'] // 3
            if not syntax_ok:
                score += test['deductions'].get('syntax_error', -10)
            
            score = max(0, score)
            total_score += score
            
            status = "✅" if score >= test['max_score'] * 0.7 else "⚠️" if score >= test['max_score'] * 0.4 else "❌"
            print(f"    {status} 得分: {score}/{test['max_score']}")
            details.append({"test": test['name'], "score": score, "max_score": test['max_score'], "syntax_ok": syntax_ok})
        except Exception as e:
            print(f"    ❌ 错误: {str(e)[:50]}")
            details.append({"test": test['name'], "error": str(e), "score": 0})
    
    return CategoryScore("代码能力", total_score, 100, details)


def evaluate_agent(client, model):
    print("\n" + "="*60)
    print("🤖 Agent能力评估")
    print("="*60)
    
    total_score = 0
    details = []
    
    for test in AGENT_TESTS:
        print(f"\n  测试: {test['name']}")
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个智能助手，擅长分析复杂任务并合理使用工具。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=2048)
            
            content = result['content']
            passed = test['check'](content)
            has_json = "[" in content and "]" in content or "{" in content and "}" in content
            has_reasoning = any(kw in content for kw in ["因为", "所以", "首先", "然后", "reason", "step"])
            
            score = test['max_score'] if passed else test['max_score'] // 3
            if has_json: score = min(score + 3, test['max_score'])
            if has_reasoning: score = min(score + 2, test['max_score'])
            
            total_score += score
            status = "✅" if score >= test['max_score'] * 0.7 else "⚠️" if score >= test['max_score'] * 0.4 else "❌"
            print(f"    {status} 得分: {score}/{test['max_score']}")
            details.append({"test": test['name'], "score": score, "max_score": test['max_score']})
        except Exception as e:
            print(f"    ❌ 错误: {str(e)[:50]}")
            details.append({"test": test['name'], "error": str(e), "score": 0})
    
    return CategoryScore("Agent能力", total_score, 100, details)


def evaluate_reasoning(client, model):
    print("\n" + "="*60)
    print("🧠 通用推理评估（增强版）")
    print("="*60)
    
    total_score = 0
    details = []
    
    for test in REASONING_TESTS:
        print(f"\n  测试: {test['name']}")
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个推理专家，擅长逻辑分析、数学建模和知识整合。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=2048)
            
            content = result['content']
            passed = test['check'](content)
            
            # 关键词匹配
            found_keywords = sum(1 for kw in test['keywords'] if kw.lower() in content.lower())
            keyword_score = min(10, found_keywords * 2)
            
            # 结构完整性
            has_structure = len([s for s in content.split("\n") if s.strip()]) >= 5
            structure_score = 5 if has_structure else 2
            
            # 推理深度（字数作为简单指标）
            depth_score = 5 if len(content) > 200 else 3 if len(content) > 100 else 1
            
            score = (test['max_score'] * 0.6 if passed else test['max_score'] * 0.2) + keyword_score + structure_score + depth_score
            score = min(score, test['max_score'])
            
            total_score += score
            status = "✅" if score >= test['max_score'] * 0.7 else "⚠️" if score >= test['max_score'] * 0.4 else "❌"
            print(f"    {status} 得分: {score}/{test['max_score']} (关键词:{found_keywords}, 结构:{has_structure}, 深度:{len(content)}字)")
            details.append({"test": test['name'], "score": score, "max_score": test['max_score'], "content_length": len(content)})
        except Exception as e:
            print(f"    ❌ 错误: {str(e)[:50]}")
            details.append({"test": test['name'], "error": str(e), "score": 0})
    
    return CategoryScore("通用推理", total_score, 100, details)


def evaluate_performance(client, model):
    print("\n" + "="*60)
    print("⚡ 性能基准测试（含4线程并发）")
    print("="*60)
    
    details = []
    total_score = 0
    
    # TTFT测试
    try:
        ttfts = []
        for _ in range(2):
            start = time.time()
            client.chat([{"role": "user", "content": "请解释什么是机器学习。"}], model, 512)
            ttfts.append((time.time()-start)*1000)
        avg_ttft = sum(ttfts)/len(ttfts)
        ttft_s = 20 if avg_ttft<=500 else 15 if avg_ttft<=1500 else 10 if avg_ttft<=3000 else 5
        total_score += ttft_s
        details.append({"test": "首Token延迟", "score": ttft_s, "max_score": 20, "metrics": {"avg_ttft_ms": round(avg_ttft,2)}})
        print(f"  - 首Token延迟: {ttft_s}/20 (avg={avg_ttft:.0f}ms)")
    except Exception as e:
        details.append({"test": "首Token延迟", "error": str(e), "score": 0})
    
    # 吞吐量测试
    try:
        tps_list = []
        for _ in range(2):
            r = client.chat([{"role": "user", "content": "请写一篇关于人工智能的文章，至少500字。"}], model, 2048)
            if r["completion_tokens"]>0: tps_list.append((r["completion_tokens"]/r["latency_ms"])*1000)
        avg_tps = sum(tps_list)/len(tps_list) if tps_list else 0
        tps_s = 20 if avg_tps>=30 else 15 if avg_tps>=15 else 10 if avg_tps>=5 else 5
        total_score += tps_s
        details.append({"test": "吞吐量", "score": tps_s, "max_score": 20, "metrics": {"avg_tps": round(avg_tps,2)}})
        print(f"  - 吞吐量: {tps_s}/20 (avg={avg_tps:.1f} tok/s)")
    except Exception as e:
        details.append({"test": "吞吐量", "error": str(e), "score": 0})
    
    # 响应速度
    try:
        start = time.time()
        client.chat([{"role": "user", "content": "你好"}], model, 100)
        lat = (time.time()-start)*1000
        resp_s = 10 if lat<1000 else 7 if lat<3000 else 3
        total_score += resp_s
        details.append({"test": "响应速度", "score": resp_s, "max_score": 10, "metrics": {"latency_ms": round(lat,2)}})
        print(f"  - 响应速度: {resp_s}/10 (lat={lat:.0f}ms)")
    except Exception as e:
        details.append({"test": "响应速度", "error": str(e), "score": 0})
    
    # 4线程并发测试
    print("\n  [4线程并发测试]")
    try:
        prompt = "请简要介绍Python编程语言的特点，100字以内。"
        messages = [{"role": "user", "content": prompt}]
        
        def worker():
            try:
                start = time.time()
                r = client.chat_simple(messages, model, 256)
                return {"success": r["success"], "latency": (time.time()-start)*1000, "tokens": r["completion_tokens"]}
            except:
                return {"success": False, "latency": 0, "tokens": 0}
        
        start_total = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker) for _ in range(4)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        total_time = (time.time() - start_total) * 1000
        
        success_count = sum(1 for r in results if r["success"])
        avg_latency = sum(r["latency"] for r in results if r["success"]) / max(success_count, 1)
        total_tokens = sum(r["tokens"] for r in results)
        
        # 评分
        if success_count == 4 and avg_latency < 5000:
            concurrent_s = 50
        elif success_count >= 3 and avg_latency < 8000:
            concurrent_s = 40
        elif success_count >= 2:
            concurrent_s = 25
        else:
            concurrent_s = 10
        
        total_score += concurrent_s
        details.append({
            "test": "4线程并发",
            "score": concurrent_s,
            "max_score": 50,
            "metrics": {
                "success_count": success_count,
                "avg_latency_ms": round(avg_latency, 2),
                "total_time_ms": round(total_time, 2),
                "total_tokens": total_tokens
            }
        })
        print(f"    ✅ 4线程并发: {concurrent_s}/50")
        print(f"       成功: {success_count}/4, 平均延迟: {avg_latency:.0f}ms, 总时间: {total_time:.0f}ms")
    except Exception as e:
        print(f"    ❌ 4线程并发测试失败: {e}")
        details.append({"test": "4线程并发", "error": str(e), "score": 0})
    
    return CategoryScore("性能基准", total_score, 100, details)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="完整增强版模型评估")
    parser.add_argument("--model", "-m", required=True, help="模型ID")
    args = parser.parse_args()
    
    client = SyncClient(API_URL, API_KEY)
    engine = ScoreEngine()
    result = engine.create_result(args.model, args.model)
    
    print("="*60)
    print("🔬 完整增强版模型评估")
    print("="*60)
    print(f"模型: {args.model}")
    
    # 四个维度评估
    coding_score = evaluate_coding(client, args.model)
    engine.add_dimension_score(result, "coding", [coding_score])
    print(f"\n  💻 代码能力: {coding_score.score}/{coding_score.max_score}")
    
    agent_score = evaluate_agent(client, args.model)
    engine.add_dimension_score(result, "agent", [agent_score])
    print(f"\n  🤖 Agent能力: {agent_score.score}/{agent_score.max_score}")
    
    reasoning_score = evaluate_reasoning(client, args.model)
    engine.add_dimension_score(result, "reasoning", [reasoning_score])
    print(f"\n  🧠 通用推理: {reasoning_score.score}/{reasoning_score.max_score}")
    
    perf_score = evaluate_performance(client, args.model)
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
    print("\n" + "="*60)
    print("📊 完整增强版评估结果")
    print("="*60)
    print(f"  代码能力:   {coding_score.score:>3}/100")
    print(f"  Agent能力:  {agent_score.score:>3}/100")
    print(f"  通用推理:   {reasoning_score.score:>3}/100")
    print(f"  性能基准:   {perf_score.score:>3}/100")
    print("-"*60)
    print(f"  综合评分:   {result.overall_score:>6.2f}/100")
    print("="*60)
    print(f"\n📁 结果已保存: {result_path}")
    
    return result


if __name__ == "__main__":
    main()
