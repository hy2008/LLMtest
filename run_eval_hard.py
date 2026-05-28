#!/usr/bin/env python3
"""
LM Studio 模型评估套件 - 增强版
提升测试难度，更精准区分模型能力差异
"""

import os, sys, time, requests, json, re, ast
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
        return {"content": content, "completion_tokens": usage.get("completion_tokens", 0), "latency_ms": (time.time()-start)*1000}


# ============================================================
# 增强版代码能力测试
# ============================================================

CODING_TESTS_HARD = [
    {
        "name": "并发安全LRU缓存",
        "prompt": """请实现一个线程安全的 LRU 缓存类，要求：

1. 支持 get(key), put(key, value, ttl_seconds) 方法
2. 支持 TTL 过期机制，过期自动删除
3. 线程安全，支持高并发读写
4. 容量满时淘汰最近最少使用且未过期的条目
5. 提供一个 cleanup() 方法清理所有过期条目

请提供完整可运行的代码，包含必要的导入语句。
只输出代码，不要解释。""",
        "check": lambda code: (
            # 必须包含的关键元素
            ("threading" in code.lower() or "Lock" in code or "RLock" in code) and  # 线程安全
            ("ttl" in code.lower() or "expire" in code.lower() or "timeout" in code.lower()) and  # TTL支持
            ("def get" in code or "def get(" in code) and  # get方法
            ("def put" in code or "def put(" in code) and  # put方法
            ("def cleanup" in code.lower() or "def _cleanup" in code.lower()) and  # cleanup方法
            ("class" in code)  # 类定义
        ),
        "max_score": 25,
        "deductions": {
            "missing_lock": -5,
            "missing_ttl": -5,
            "missing_cleanup": -3,
            "syntax_error": -10
        }
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

示例:
- evaluate("2 + 3 * 4") = 14.0
- evaluate("(2 + 3) * 4") = 20.0
- evaluate("-5 + 10") = 5.0
- evaluate("10 / 0") = None

只输出代码，不要解释。""",
        "check": lambda code: (
            ("def evaluate" in code) and
            ("+" in code and "*" in code) and
            ("(" in code and ")" in code) and
            ("None" in code or "return None" in code) and
            ("float" in code.lower() or "int" in code.lower())
        ),
        "max_score": 25,
        "deductions": {
            "no_bracket_support": -5,
            "no_negative": -3,
            "no_div_zero_check": -5,
            "syntax_error": -10
        }
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
            ("asyncio" in code.lower()) and
            ("async def" in code) and
            ("add_task" in code) and
            ("priority" in code.lower() or "depend" in code.lower()) and
            ("max_concurrent" in code.lower() or "semaphore" in code.lower())
        ),
        "max_score": 25,
        "deductions": {
            "no_priority": -3,
            "no_dependencies": -5,
            "no_concurrent_limit": -5,
            "no_retry": -3,
            "syntax_error": -10
        }
    },
    {
        "name": "SQL解析与验证",
        "prompt": """请实现一个简单的 SQL 解析器，要求：

1. 解析 SELECT 语句，提取: 表名、字段列表、WHERE条件、ORDER BY、LIMIT
2. 验证 SQL 语法是否正确（基础验证即可）
3. 检测潜在的 SQL 注入风险（简单规则）
4. 函数签名: def parse_select(sql: str) -> dict

返回格式:
{
    "valid": True/False,
    "table": "table_name",
    "columns": ["col1", "col2"],
    "where": "condition",
    "order_by": [("col1", "ASC")],
    "limit": 10,
    "injection_risk": True/False
}

只输出代码。""",
        "check": lambda code: (
            ("def parse_select" in code or "def parse" in code) and
            ("SELECT" in code.upper() or "select" in code.lower()) and
            ("WHERE" in code.upper() or "where" in code.lower()) and
            ("injection" in code.lower() or "risk" in code.lower()) and
            ("valid" in code.lower())
        ),
        "max_score": 25,
        "deductions": {
            "no_injection_check": -5,
            "no_order_by": -3,
            "no_limit": -2,
            "syntax_error": -10
        }
    }
]


# ============================================================
# 增强版Agent能力测试
# ============================================================

AGENT_TESTS_HARD = [
    {
        "name": "多工具组合调用",
        "prompt": """你是一个智能助手，拥有以下工具：

1. search_web(query: str) - 搜索网络信息
2. get_weather(city: str) - 获取城市天气
3. send_email(to: str, subject: str, body: str) - 发送邮件
4. create_calendar_event(title: str, start_time: str, end_time: str) - 创建日历事件
5. query_database(sql: str) - 执行SQL查询

用户请求：请帮我查一下北京明天的天气，如果会下雨就发邮件提醒我带伞（发到 my@email.com），同时在日历上创建一个"带伞"提醒事件，明天上午9点。

请分析这个请求，按顺序列出你需要调用的所有工具及其参数。使用JSON数组格式输出：
[
  {"tool": "工具名", "args": {"参数名": "参数值"}, "reason": "调用原因"},
  ...
]""",
        "check": lambda resp: (
            # 应该先查天气
            ("get_weather" in resp or "weather" in resp.lower()) and
            # 应该有条件判断逻辑
            ("if" in resp.lower() or "如果" in resp or "下雨" in resp) and
            # 应该发邮件
            ("send_email" in resp or "email" in resp.lower()) and
            # 应该创建日历事件
            ("calendar" in resp.lower() or "event" in resp.lower()) and
            # 应该是JSON格式
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

请推断所有需要的参数值，输出完整的工具调用序列（JSON数组格式）。注意：你需要推断合理的列名、操作类型等参数。""",
        "check": lambda resp: (
            ("load_data" in resp or "load" in resp.lower()) and
            ("filter" in resp.lower() or "sort" in resp.lower() or "top" in resp.lower()) and
            ("aggregate" in resp.lower() or "sum" in resp.lower() or "max" in resp.lower()) and
            ("plot" in resp.lower() or "chart" in resp.lower()) and
            ("export" in resp.lower() or "xlsx" in resp.lower()) and
            ("[" in resp and "]" in resp)
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

请设计一个完整的调用方案，包含：
1. 初始调用
2. 错误检测逻辑
3. 重试策略
4. 最终失败处理

输出你的思考过程和工具调用序列。""",
        "check": lambda resp: (
            ("retry" in resp.lower() or "重试" in resp) and
            ("error" in resp.lower() or "错误" in resp or "fail" in resp.lower()) and
            ("log" in resp.lower() or "记录" in resp) and
            ("alert" in resp.lower() or "告警" in resp or "通知" in resp) and
            ("attempt" in resp.lower() or "次数" in resp or "max" in resp.lower())
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

请分析当前对话状态，输出：
1. 当前需要调用的工具
2. 后续可能需要的工具
3. 完整的工具调用序列

使用JSON格式输出。""",
        "check": lambda resp: (
            ("refund" in resp.lower() or "退款" in resp) and
            ("coupon" in resp.lower() or "补偿" in resp or "优惠" in resp) and
            ("order" in resp.lower() or "订单" in resp) and
            ("user" in resp.lower() or "用户" in resp) and
            ("[" in resp or "{" in resp)
        ),
        "max_score": 25
    }
]


def extract_code(response: str) -> str:
    """从响应中提取代码块"""
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


def evaluate_coding_hard(client, model):
    """增强版代码能力评估"""
    print("\n" + "="*60)
    print("💻 代码能力评估 (增强版)")
    print("="*60)
    
    total_score = 0
    max_total = 100
    details = []
    
    for test in CODING_TESTS_HARD:
        print(f"\n  测试: {test['name']}")
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个资深软件工程师。请编写高质量、可运行的代码。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=4096)
            
            code = extract_code(result['content'])
            code_lower = code.lower()
            
            # 基础检查
            base_passed = test['check'](code)
            
            # 语法检查
            syntax_ok, syntax_err = check_syntax(code)
            
            # 计算分数
            score = test['max_score'] if base_passed else test['max_score'] // 3
            
            # 扣分
            if not syntax_ok:
                score += test['deductions'].get('syntax_error', -5)
                print(f"    ⚠️ 语法错误: {syntax_err[:50]}...")
            
            # 检查缺失项
            if "Lock" not in code and "threading" not in code_lower:
                if "missing_lock" in test['deductions']:
                    score += test['deductions']['missing_lock']
                    print(f"    ⚠️ 缺少线程安全机制")
            
            if "ttl" not in code_lower and "expire" not in code_lower:
                if "missing_ttl" in test['deductions']:
                    score += test['deductions']['missing_ttl']
                    print(f"    ⚠️ 缺少TTL机制")
            
            score = max(0, score)
            total_score += score
            
            status = "✅" if score >= test['max_score'] * 0.7 else "⚠️" if score >= test['max_score'] * 0.4 else "❌"
            print(f"    {status} 得分: {score}/{test['max_score']}")
            
            details.append({
                "test": test['name'],
                "score": score,
                "max_score": test['max_score'],
                "syntax_ok": syntax_ok,
                "code_length": len(code)
            })
            
        except Exception as e:
            print(f"    ❌ 错误: {str(e)[:50]}")
            details.append({"test": test['name'], "error": str(e), "score": 0})
    
    return CategoryScore("代码能力(增强)", total_score, max_total, details)


def evaluate_agent_hard(client, model):
    """增强版Agent能力评估"""
    print("\n" + "="*60)
    print("🤖 Agent能力评估 (增强版)")
    print("="*60)
    
    total_score = 0
    max_total = 100
    details = []
    
    for test in AGENT_TESTS_HARD:
        print(f"\n  测试: {test['name']}")
        try:
            result = client.chat([
                {"role": "system", "content": "你是一个智能助手，擅长分析复杂任务并合理使用工具。"},
                {"role": "user", "content": test['prompt']}
            ], model, max_tokens=2048)
            
            content = result['content']
            
            # 检查是否包含所有必要元素
            passed = test['check'](content)
            
            # 检查JSON格式
            has_json = "[" in content and "]" in content or "{" in content and "}" in content
            
            # 检查推理过程
            has_reasoning = any(kw in content for kw in ["因为", "所以", "首先", "然后", "reason", "because", "step"])
            
            score = test['max_score'] if passed else test['max_score'] // 3
            if has_json:
                score = min(score + 3, test['max_score'])
            if has_reasoning:
                score = min(score + 2, test['max_score'])
            
            total_score += score
            
            status = "✅" if score >= test['max_score'] * 0.7 else "⚠️" if score >= test['max_score'] * 0.4 else "❌"
            print(f"    {status} 得分: {score}/{test['max_score']}")
            
            details.append({
                "test": test['name'],
                "score": score,
                "max_score": test['max_score'],
                "has_json": has_json,
                "has_reasoning": has_reasoning
            })
            
        except Exception as e:
            print(f"    ❌ 错误: {str(e)[:50]}")
            details.append({"test": test['name'], "error": str(e), "score": 0})
    
    return CategoryScore("Agent能力(增强)", total_score, max_total, details)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="增强版模型评估")
    parser.add_argument("--model", "-m", required=True, help="模型ID")
    args = parser.parse_args()
    
    client = SyncClient(API_URL, API_KEY)
    engine = ScoreEngine()
    result = engine.create_result(args.model, args.model)
    
    print("="*60)
    print("🔬 增强版模型评估")
    print("="*60)
    print(f"模型: {args.model}")
    
    # 代码能力评估
    coding_score = evaluate_coding_hard(client, args.model)
    engine.add_dimension_score(result, "coding", [coding_score])
    print(f"\n  💻 代码能力总分: {coding_score.score}/{coding_score.max_score}")
    
    # Agent能力评估
    agent_score = evaluate_agent_hard(client, args.model)
    engine.add_dimension_score(result, "agent", [agent_score])
    print(f"\n  🤖 Agent能力总分: {agent_score.score}/{agent_score.max_score}")
    
    # 计算总分 (只看这两个维度)
    result.dimensions["coding"].weight = 0.5
    result.dimensions["agent"].weight = 0.5
    engine.finalize(result)
    
    # 保存结果
    os.makedirs("results", exist_ok=True)
    result_path = engine.save_result(result, "results")
    
    print("\n" + "="*60)
    print("📊 增强版评估结果")
    print("="*60)
    print(f"  代码能力: {coding_score.score}/{coding_score.max_score}")
    print(f"  Agent能力: {agent_score.score}/{agent_score.max_score}")
    print("-"*60)
    print(f"  综合评分: {result.overall_score:.2f}/100")
    print("="*60)
    print(f"\n📁 结果已保存: {result_path}")
    
    return result


if __name__ == "__main__":
    main()
