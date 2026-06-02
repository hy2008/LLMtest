"""单模型评估执行器 — 与 35b 框架使用同一套 evaluator"""
import sys, asyncio, os, time

sys.path.insert(0, "/Users/hy/test/LLMtest")
from utils.client import LMStudioClient, ChatMessage
from utils.config import load_config
from evaluators.coding import CodingEvaluator
from evaluators.agent import AgentEvaluator
from evaluators.reasoning import ReasoningEvaluator
from evaluators.performance import PerformanceEvaluator
from utils.score_engine import ScoreEngine

config = load_config()
RESULTS_DIR = getattr(config.report, "results_dir", "results")
LMS = "/Users/hy/.lmstudio/bin/lms"

async def test_one(model_id):
    print(f"\n{'='*60}")
    print(f"  Testing: {model_id}")
    print(f"{'='*60}")

    client = LMStudioClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
        sock_read_timeout=getattr(config.api, 'sock_read_timeout', 120),
        max_retries=config.api.max_retries
    )

    ok = await client.check_connection()
    if not ok:
        print("  ❌ No connection")
        await client.close()
        return None

    weights = {
        "coding": config.weights.coding,
        "agent": config.weights.agent,
        "reasoning": config.weights.reasoning,
        "performance": config.weights.performance
    }
    se = ScoreEngine(weights=weights)
    result = se.create_result(model_id, model_id)

    print(f"\n  [1/4] Coding...")
    try:
        ev = CodingEvaluator(client, config)
        cats = await ev.evaluate(model=model_id, temperature=0.0, max_tokens=config.evaluation.max_tokens)
        se.add_dimension_score(result, "coding", cats)
        print(f"  ✅ Coding: {result.dimensions['coding'].score:.1f}")
    except Exception as e:
        print(f"  ❌ Coding: {e}")

    print(f"\n  [2/4] Agent...")
    try:
        ev = AgentEvaluator(client, config)
        cats = await ev.evaluate(model=model_id, temperature=0.0, max_tokens=config.evaluation.max_tokens)
        se.add_dimension_score(result, "agent", cats)
        print(f"  ✅ Agent: {result.dimensions['agent'].score:.1f}")
    except Exception as e:
        print(f"  ❌ Agent: {e}")

    print(f"\n  [3/4] Reasoning...")
    try:
        ev = ReasoningEvaluator(client, config)
        cats = await ev.evaluate(model=model_id, temperature=0.0, max_tokens=config.evaluation.max_tokens)
        se.add_dimension_score(result, "reasoning", cats)
        print(f"  ✅ Reasoning: {result.dimensions['reasoning'].score:.1f}")
    except Exception as e:
        print(f"  ❌ Reasoning: {e}")

    print(f"\n  [4/4] Performance...")
    try:
        ev = PerformanceEvaluator(client, config)
        cats = await ev.evaluate(model=model_id)
        se.add_dimension_score(result, "performance", cats)
        print(f"  ✅ Performance: {result.dimensions['performance'].score:.1f}")
    except Exception as e:
        print(f"  ❌ Performance: {e}")

    se.finalize(result)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = se.save_result(result, RESULTS_DIR)
    print(f"\n  📁 Saved: {path}")

    dims = result.dimensions
    print(f"\n  {'='*40}")
    print(f"  {model_id}")
    print(f"  {'='*40}")
    for name, dim in dims.items():
        print(f"    {name}: {dim.score:.1f}")
    print(f"  {'─'*40}")
    print(f"  TOTAL: {result.total_score:.1f}")

    await client.close()
    return result

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else None
    if not model:
        print("Usage: python3 test_one_27b.py <model_id>")
        print("Available: qwopus3.6-27b-v2  qwopus3.6-27b-v2-mlx")
        sys.exit(1)
    asyncio.run(test_one(model))