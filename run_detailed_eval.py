#!/usr/bin/env python3
"""
逐项详细评估脚本 — 记录每个子类别的详细测试结果
用于分析测试用例的科学性和合理性
"""

import os
import sys
import json
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_config
from utils.client import LMStudioClient, ChatMessage
from evaluators.coding import CodingEvaluator
from evaluators.agent import AgentEvaluator
from evaluators.reasoning import ReasoningEvaluator

MODEL = "qwen3.6-35b-a3b-claude-4.6-opus-reasoning-distilled"

results = {}
errors = {}


async def test_dimension(name, evaluator, eval_kwargs, dim_key):
    """测试单个维度，逐项记录"""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    results[name] = {}
    try:
        categories = await evaluator.evaluate(**eval_kwargs)
        for cat in categories:
            cat_name = cat.category
            score = cat.score
            max_score = cat.max_score
            pct = round(score / max_score * 100, 1) if max_score > 0 else 0
            results[name][cat_name] = {
                "score": score,
                "max_score": max_score,
                "percentage": pct,
                "weight": cat.weight,
                "details": cat.details
            }
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            print(f"  {cat_name:20s} [{bar}] {score:.0f}/{max_score} ({pct}%)")
            # 打印每个测试用例详情
            if cat.details:
                for d in cat.details:
                    dname = d.get("name", d.get("test_name", "?"))
                    dscore = d.get("score", d.get("score_raw", 0))
                    dmax = d.get("max_score", 0)
                    print(f"    - {dname}: {dscore}/{dmax}")
    except Exception as e:
        errors[name] = str(e)
        print(f"  ❌ 失败: {e}")


async def main():
    cfg = load_config()
    client = LMStudioClient(
        base_url=cfg.api.base_url,
        api_key=cfg.api.api_key,
        timeout=cfg.api.timeout,
        sock_read_timeout=cfg.api.sock_read_timeout
    )

    connected = await client.check_connection()
    if not connected:
        print("无法连接到 LM Studio")
        return

    print(f"模型: {MODEL}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    cat_weights = getattr(cfg, "category_weights", None)

    # 1. 代码能力
    c_weights = getattr(cat_weights, "coding", {}) if cat_weights else {}
    coding = CodingEvaluator(client, cfg, category_weights=c_weights)
    await test_dimension("代码能力", coding, {
        "model": MODEL,
        "temperature": cfg.evaluation.temperature,
        "max_tokens": cfg.evaluation.max_tokens,
        "include_practical": True
    }, "coding")

    # 2. Agent能力
    a_weights = getattr(cat_weights, "agent", {}) if cat_weights else {}
    agent = AgentEvaluator(client, cfg, category_weights=a_weights)
    await test_dimension("Agent能力", agent, {
        "model": MODEL,
        "temperature": cfg.evaluation.temperature,
        "max_tokens": cfg.evaluation.max_tokens,
        "include_practical": True
    }, "agent")

    # 3. 通用推理
    r_weights = getattr(cat_weights, "reasoning", {}) if cat_weights else {}
    reasoning = ReasoningEvaluator(client, cfg, category_weights=r_weights)
    await test_dimension("通用推理", reasoning, {
        "model": MODEL,
        "temperature": cfg.evaluation.temperature,
        "max_tokens": cfg.evaluation.max_tokens,
        "include_practical": True
    }, "reasoning")

    await client.close()

    # 汇总输出
    print(f"\n{'='*60}")
    print(f"  汇总")
    print(f"{'='*60}")

    total_score = 0
    total_max = 0
    for dim_name, cats in results.items():
        dim_score = sum(c["score"] for c in cats.values())
        dim_max = sum(c["max_score"] for c in cats.values())
        dim_pct = round(dim_score / dim_max * 100, 1) if dim_max > 0 else 0
        print(f"  {dim_name}: {dim_score:.0f}/{dim_max} ({dim_pct}%)")
        total_score += dim_score
        total_max += dim_max
        for cat_name, cat in cats.items():
            print(f"    {cat_name}: {cat['score']}/{cat['max_score']} ({cat['percentage']}%)")

    overall = round(total_score / total_max * 100, 2) if total_max > 0 else 0
    print(f"\n  综合: {total_score:.0f}/{total_max} ({overall}%)")

    if errors:
        print(f"\n  错误:")
        for dim, err in errors.items():
            print(f"    {dim}: {err}")

    # 保存详细结果
    output = {
        "model": MODEL,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dimensions": results,
        "errors": errors,
        "summary": {
            "total_score": total_score,
            "total_max": total_max,
            "overall_percentage": overall
        }
    }
    os.makedirs("results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"results/detailed_eval_{MODEL.replace('/', '_')}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  详细结果已保存: {path}")


asyncio.run(main())
