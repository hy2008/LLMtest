#!/usr/bin/env python3
"""
LM Studio 模型评估套件 - 主入口
用法: python run_eval.py
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_config, Config
from utils.client import LMStudioClient, ChatMessage
from utils.score_engine import ScoreEngine, ModelEvalResult
from utils.report_generator import ReportGenerator
from evaluators.coding import CodingEvaluator
from evaluators.agent import AgentEvaluator
from evaluators.reasoning import ReasoningEvaluator
from evaluators.performance import PerformanceEvaluator


# ============================================================
# Rich 风格的终端输出 (不依赖 rich 库)
# ============================================================

class Console:
    """终端输出工具"""

    COLORS = {
        "header": "\033[1;36m",    # 青色加粗
        "success": "\033[1;32m",   # 绿色加粗
        "warning": "\033[1;33m",   # 黄色加粗
        "error": "\033[1;31m",     # 红色加粗
        "info": "\033[0;34m",      # 蓝色
        "dim": "\033[2m",          # 暗色
        "bold": "\033[1m",         # 加粗
        "reset": "\033[0m",        # 重置
    }

    @staticmethod
    def print(text: str, color: str = ""):
        prefix = Console.COLORS.get(color, "")
        suffix = Console.COLORS["reset"] if prefix else ""
        print(f"{prefix}{text}{suffix}")

    @staticmethod
    def header(text: str):
        width = 60
        print()
        Console.print("═" * width, "header")
        Console.print(f"  {text}", "header")
        Console.print("═" * width, "header")
        print()

    @staticmethod
    def step(text: str, step_num: int = 0):
        prefix = f"[{step_num}] " if step_num else "▸ "
        Console.print(f"  {prefix}{text}", "info")

    @staticmethod
    def success(text: str):
        Console.print(f"  ✅ {text}", "success")

    @staticmethod
    def warning(text: str):
        Console.print(f"  ⚠️  {text}", "warning")

    @staticmethod
    def error(text: str):
        Console.print(f"  ❌ {text}", "error")

    @staticmethod
    def result(label: str, value: str, color: str = ""):
        Console.print(f"    {label}: {value}", color)

    @staticmethod
    def score_bar(label: str, score: float, max_score: float = 100):
        ratio = score / max_score if max_score > 0 else 0
        filled = int(ratio * 20)
        bar = "█" * filled + "░" * (20 - filled)
        color = "success" if ratio >= 0.7 else "warning" if ratio >= 0.4 else "error"
        Console.print(f"    {label:20s} [{bar}] {score:.1f}/{max_score}", color)

    @staticmethod
    def divider():
        print("  " + "─" * 56)

    def input(self, prompt: str) -> str:
        return input(f"  {prompt}: ").strip()


console = Console()


# ============================================================
# 评估流程
# ============================================================

async def check_connection(client: LMStudioClient, config: Config) -> bool:
    """检查 LM Studio 连接"""
    console.step("检查 LM Studio API 连接...")
    connected = await client.check_connection()
    if connected:
        console.success(f"已连接到 {config.api.base_url}")
        return True
    else:
        console.error(f"无法连接到 {config.api.base_url}")
        console.print("  请确保 LM Studio 正在运行且已加载模型", "dim")
        return False


async def get_model_info(client: LMStudioClient) -> tuple:
    """获取当前加载的模型信息"""
    console.step("获取模型信息...")
    model = await client.get_loaded_model()
    if model:
        console.success(f"当前模型: {model.id}")
        return model.id, model.id
    else:
        console.warning("未检测到已加载的模型，将使用默认模型名")
        return "loaded", "未知模型"


def select_dimensions() -> list:
    """选择评估维度"""
    console.print("\n  可选评估维度:", "bold")
    console.print("    1. 代码能力 (生成/补全/Debug/多语言)")
    console.print("    2. Agent能力 (Function Calling/工具选择/多步推理/指令遵循)")
    console.print("    3. 通用推理 (逻辑/阅读/数学/知识)")
    console.print("    4. 性能基准 (TTFT/TPS/并发)")
    console.print("    5. 全部评估 (1+2+3+4)")
    print()

    choice = console.input("请选择评估维度 (1-5)")
    dim_map = {
        "1": ["coding"],
        "2": ["agent"],
        "3": ["reasoning"],
        "4": ["performance"],
        "5": ["coding", "agent", "reasoning", "performance"]
    }
    return dim_map.get(choice, ["coding", "agent", "reasoning", "performance"])


async def run_evaluation(model_id: str, model_name: str,
                         dimensions: list, config: Config,
                         client: LMStudioClient) -> ModelEvalResult:
    """运行评估"""
    score_engine = ScoreEngine(
        weights={
            "coding": config.weights.coding,
            "agent": config.weights.agent,
            "reasoning": config.weights.reasoning,
            "performance": config.weights.performance
        }
    )

    result = score_engine.create_result(model_name, model_id)
    total_steps = len(dimensions)
    step = 0

    # 代码能力评估
    if "coding" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] 代码能力评估")
        evaluator = CodingEvaluator(client, config)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens
            )
            score_engine.add_dimension_score(result, "coding", categories)
            for cat in categories:
                console.score_bar(cat.category, cat.score, cat.max_score)
            console.success(f"代码能力评估完成: {result.dimensions['coding'].score:.1f} 分")
        except Exception as e:
            console.error(f"代码能力评估失败: {e}")

    # Agent能力评估
    if "agent" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] Agent/工具调用评估")
        evaluator = AgentEvaluator(client, config)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens
            )
            score_engine.add_dimension_score(result, "agent", categories)
            for cat in categories:
                console.score_bar(cat.category, cat.score, cat.max_score)
            console.success(f"Agent能力评估完成: {result.dimensions['agent'].score:.1f} 分")
        except Exception as e:
            console.error(f"Agent能力评估失败: {e}")

    # 通用推理评估
    if "reasoning" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] 通用推理评估")
        evaluator = ReasoningEvaluator(client, config)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens
            )
            score_engine.add_dimension_score(result, "reasoning", categories)
            for cat in categories:
                console.score_bar(cat.category, cat.score, cat.max_score)
            console.success(f"通用推理评估完成: {result.dimensions['reasoning'].score:.1f} 分")
        except Exception as e:
            console.error(f"通用推理评估失败: {e}")

    # 性能基准测试
    if "performance" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] 性能基准测试")
        evaluator = PerformanceEvaluator(client, config)
        try:
            benchmark_cfg = {
                "ttft_prompt": config.benchmark.ttft_prompt,
                "throughput_prompt": config.benchmark.throughput_prompt,
                "throughput_runs": config.benchmark.throughput_runs,
                "concurrent_requests": config.benchmark.concurrent_requests
            }
            categories = await evaluator.evaluate(
                model=model_id,
                benchmark_config=benchmark_cfg
            )
            score_engine.add_dimension_score(result, "performance", categories)
            for cat in categories:
                console.score_bar(cat.category, cat.score, cat.max_score)
                # 显示性能指标
                if cat.details:
                    for detail in cat.details:
                        metrics = detail.get("metrics", {})
                        if metrics:
                            for k, v in metrics.items():
                                if isinstance(v, (int, float)):
                                    unit = "ms" if "ms" in k else "tok/s" if "tps" in k else ""
                                    console.result(f"  {k}", f"{v:.1f} {unit}" if unit else str(v))
            console.success(f"性能基准测试完成: {result.dimensions['performance'].score:.1f} 分")
        except Exception as e:
            console.error(f"性能基准测试失败: {e}")

    # 计算总分
    score_engine.finalize(result)

    return result, score_engine


def show_summary(result: ModelEvalResult):
    """显示评估摘要"""
    console.header("评估结果摘要")
    console.print(f"  模型: {result.model_name}", "bold")
    console.print(f"  ID: {result.model_id}", "dim")
    console.print(f"  时间: {result.eval_time}", "dim")
    console.divider()

    for dim_name, dim_score in result.dimensions.items():
        label_map = {
            "coding": "代码能力",
            "agent": "Agent能力",
            "reasoning": "通用推理",
            "performance": "性能基准"
        }
        label = label_map.get(dim_name, dim_name)
        console.score_bar(label, dim_score.score)

    console.divider()
    color = "success" if result.overall_score >= 70 else "warning" if result.overall_score >= 40 else "error"
    console.print(f"  综合评分: {result.overall_score:.2f} / 100", color)
    print()


async def show_leaderboard(score_engine: ScoreEngine):
    """显示排行榜"""
    leaderboard = score_engine.get_leaderboard()
    if len(leaderboard) < 2:
        console.warning("至少需要 2 个模型的评估结果才能生成排行榜")
        return

    console.header("🏆 模型排行榜")
    print(f"  {'排名':<6}{'模型':<30}{'代码':<8}{'Agent':<8}{'推理':<8}{'性能':<8}{'总分':<8}")
    console.divider()

    for entry in leaderboard:
        rank = entry["rank"]
        name = entry["model_name"][:28]
        dims = entry.get("dimensions", {})
        color = "success" if rank == 1 else "warning" if rank == 2 else "" if rank == 3 else "dim"
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f" {rank}"
        print(f"  {medal:<6}{name:<30}"
              f"{dims.get('coding', '-'):>6}  "
              f"{dims.get('agent', '-'):>6}  "
              f"{dims.get('reasoning', '-'):>6}  "
              f"{dims.get('performance', '-'):>6}  "
              f"{entry['overall_score']:>6.1f}")
    print()


# ============================================================
# 主函数
# ============================================================

async def main():
    parser = argparse.ArgumentParser(
        description="LM Studio 模型评估套件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_eval.py                    # 交互式运行
  python run_eval.py --all              # 全维度评估
  python run_eval.py --dim coding agent # 只评估代码和Agent
  python run_eval.py --report           # 生成报告
  python run_eval.py --leaderboard      # 查看排行榜
        """
    )
    parser.add_argument("--config", "-c", help="配置文件路径", default=None)
    parser.add_argument("--all", "-a", help="全维度评估", action="store_true")
    parser.add_argument("--dim", "-d", nargs="+", choices=["coding", "agent", "reasoning", "performance"],
                        help="指定评估维度")
    parser.add_argument("--model", "-m", help="手动指定模型名称")
    parser.add_argument("--report", "-r", help="生成HTML报告", action="store_true")
    parser.add_argument("--leaderboard", "-l", help="显示排行榜", action="store_true")
    parser.add_argument("--api-url", help="LM Studio API 地址", default=None)

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    if args.api_url:
        config.api.base_url = args.api_url

    console.header("🤖 LM Studio 模型评估套件")
    console.print(f"  API 地址: {config.api.base_url}", "dim")
    console.print(f"  评估权重: 代码={config.weights.coding} Agent={config.weights.agent} "
                  f"推理={config.weights.reasoning} 性能={config.weights.performance}", "dim")

    # 初始化客户端
    client = LMStudioClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
        max_retries=config.api.max_retries
    )

    # 排行榜模式
    if args.leaderboard:
        score_engine = ScoreEngine(
            weights={"coding": config.weights.coding, "agent": config.weights.agent,
                     "reasoning": config.weights.reasoning, "performance": config.weights.performance}
        )
        score_engine.load_results(config.report.results_dir)
        await show_leaderboard(score_engine)
        await client.close()
        return

    # 检查连接
    if not await check_connection(client, config):
        await client.close()
        sys.exit(1)

    # 获取模型信息
    if args.model:
        model_id, model_name = args.model, args.model
    else:
        model_id, model_name = await get_model_info(client)

    # 选择评估维度
    if args.all:
        dimensions = ["coding", "agent", "reasoning", "performance"]
    elif args.dim:
        dimensions = args.dim
    else:
        dimensions = select_dimensions()

    dim_labels = {
        "coding": "代码能力",
        "agent": "Agent能力",
        "reasoning": "通用推理",
        "performance": "性能基准"
    }
    console.print(f"\n  评估维度: {', '.join(dim_labels.get(d, d) for d in dimensions)}", "info")
    console.print(f"  目标模型: {model_name}", "info")
    console.print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", "dim")

    # 运行评估
    try:
        result, score_engine = await run_evaluation(
            model_id=model_id,
            model_name=model_name,
            dimensions=dimensions,
            config=config,
            client=client
        )

        # 显示摘要
        show_summary(result)

        # 保存结果
        result_path = score_engine.save_result(result, config.report.results_dir)
        console.success(f"评估结果已保存: {result_path}")

        # 加载历史结果并显示排行榜
        score_engine.load_results(config.report.results_dir)
        await show_leaderboard(score_engine)

        # 生成报告
        if args.report or len(score_engine.results) >= 1:
            try:
                generator = ReportGenerator(score_engine, config.report.output_dir)
                report_path = generator.generate_report()
                console.success(f"HTML 报告已生成: {report_path}")
            except Exception as e:
                console.warning(f"报告生成失败: {e}")

    except KeyboardInterrupt:
        console.warning("\n评估已取消")
    except Exception as e:
        console.error(f"评估过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
