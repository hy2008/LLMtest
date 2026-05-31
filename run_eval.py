#!/usr/bin/env python3
"""
LM Studio 模型评估套件 v3.0 — 主入口
用法:
  python run_eval.py eval --mode quick|standard|full --profile openclaw|hermes
  python run_eval.py eval --all
  python run_eval.py report --input-dir results --format html json txt
  python run_eval.py leaderboard
  python run_eval.py lifecycle -m "model-id"
  python run_eval.py  # 交互式运行 (向后兼容)
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
from evaluators.rag_eval import RAGEvaluator


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
        "5": ["rag"],
        "6": ["coding", "agent", "reasoning", "performance", "rag"]
    }
    return dim_map.get(choice, ["coding", "agent", "reasoning", "performance", "rag"])


async def run_evaluation(model_id: str, model_name: str,
                         dimensions: list, config: Config,
                         client: LMStudioClient, weights=None) -> ModelEvalResult:
    """运行评估"""
    if weights is None:
        weights = {
            "coding": config.weights.coding,
            "agent": config.weights.agent,
            "reasoning": config.weights.reasoning,
            "performance": config.weights.performance
        }
    score_engine = ScoreEngine(weights=weights)

    result = score_engine.create_result(model_name, model_id)
    total_steps = len(dimensions)
    step = 0

    cat_weights = getattr(config, "category_weights", None)

    # 代码能力评估
    if "coding" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] 代码能力评估")
        c_weights = getattr(cat_weights, "coding", {}) if cat_weights else {}
        evaluator = CodingEvaluator(client, config, category_weights=c_weights)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens,
                include_practical=evaluator.include_practical
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
        a_weights = getattr(cat_weights, "agent", {}) if cat_weights else {}
        evaluator = AgentEvaluator(client, config, category_weights=a_weights)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens,
                include_practical=evaluator.include_practical
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
        r_weights = getattr(cat_weights, "reasoning", {}) if cat_weights else {}
        evaluator = ReasoningEvaluator(client, config, category_weights=r_weights)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens,
                include_practical=evaluator.include_practical
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
        p_weights = getattr(cat_weights, "performance", {}) if cat_weights else {}
        evaluator = PerformanceEvaluator(client, config, category_weights=p_weights)
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

    # RAG评估
    if "rag" in dimensions:
        step += 1
        console.header(f"[{step}/{total_steps}] RAG评估")
        r_weights = getattr(cat_weights, "rag", {}) if cat_weights else {}
        evaluator = RAGEvaluator(client, config, category_weights=r_weights)
        try:
            categories = await evaluator.evaluate(
                model=model_id,
                temperature=config.evaluation.temperature,
                max_tokens=config.evaluation.max_tokens,
                include_practical=evaluator.include_practical
            )
            score_engine.add_dimension_score(result, "rag", categories)
            for cat in categories:
                console.score_bar(cat.category, cat.score, cat.max_score)
            console.success(f"RAG评估完成: {result.dimensions['rag'].score:.1f} 分")
        except Exception as e:
            console.error(f"RAG评估失败: {e}")

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

def build_parser():
    """构建子命令体系"""
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description="LLMtest v3.0 — LM Studio 模型评估套件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_eval.py eval --mode quick                     # 快速筛选 (5-8min)
  python run_eval.py eval --mode standard --profile openclaw  # OpenClaw 标准评估
  python run_eval.py eval --all                             # 全维度评估 (向后兼容)
  python run_eval.py eval --dim coding agent                # 指定维度 (向后兼容)
  python run_eval.py report --input-dir results             # 生成报告
  python run_eval.py leaderboard                            # 查看排行榜
  python run_eval.py lifecycle -m "model-id"                # 全生命周期评估
  python run_eval.py                                        # 交互式运行 (向后兼容)
        """
    )
    parser.add_argument("--config", "-c", help="配置文件路径", default=None)
    parser.add_argument("--api-url", help="LM Studio API 地址", default=None)

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # eval 子命令
    eval_p = subparsers.add_parser("eval", help="执行模型评估")
    eval_p.add_argument("--mode", choices=["quick", "standard", "full"],
                        default=None, help="评估模式 (覆盖配置默认值)")
    eval_p.add_argument("--dim", nargs="+", default=None,
                        choices=["coding", "agent", "reasoning", "performance", "rag"],
                        help="指定评估维度")
    eval_p.add_argument("--all", "-a", action="store_true", help="全维度评估")
    eval_p.add_argument("--profile", choices=["openclaw", "hermes", "default"],
                        default=None, help="评估目标框架")
    eval_p.add_argument("--model", "-m", default=None, help="模型名称")
    eval_p.add_argument("--report", "-r", action="store_true", help="生成报告")
    eval_p.add_argument("--leaderboard", "-l", action="store_true", help="显示排行榜")
    eval_p.add_argument("--output-dir", default=None, help="结果输出目录")

    # report 子命令
    report_p = subparsers.add_parser("report", help="生成评估报告")
    report_p.add_argument("--input-dir", default="results", help="评估结果目录")
    report_p.add_argument("--output-dir", default="reports", help="报告输出目录")
    report_p.add_argument("--format", choices=["html", "json", "txt", "docx"],
                          nargs="+", default=["html"], help="报告格式")

    # leaderboard 子命令
    lb_p = subparsers.add_parser("leaderboard", help="查看排行榜")
    lb_p.add_argument("--results-dir", default="results", help="历史结果目录")
    lb_p.add_argument("--top", type=int, default=10, help="显示前N名")

    # lifecycle 子命令
    lc_p = subparsers.add_parser("lifecycle", help="完整生命周期评估")
    lc_p.add_argument("--model", "-m", required=True, help="模型ID")
    lc_p.add_argument("--profile", choices=["openclaw", "hermes", "default"],
                      default="default")
    lc_p.add_argument("--skip-load", action="store_true")
    lc_p.add_argument("--skip-unload", action="store_true")

    return parser


async def handle_leaderboard_cmd(args, config):
    """处理 leaderboard 子命令"""
    results_dir = getattr(args, "results_dir", config.report.results_dir)
    score_engine = ScoreEngine(
        weights={"coding": config.weights.coding, "agent": config.weights.agent,
                 "reasoning": config.weights.reasoning, "performance": config.weights.performance,
                 "rag": config.weights.rag}
    )
    score_engine.load_results(results_dir)
    await show_leaderboard(score_engine)


async def handle_report_cmd(args, config):
    """处理 report 子命令"""
    input_dir = getattr(args, "input_dir", config.report.results_dir)
    output_dir = getattr(args, "output_dir", config.report.output_dir)
    formats = getattr(args, "format", ["html"])

    score_engine = ScoreEngine(
        weights={"coding": config.weights.coding, "agent": config.weights.agent,
                 "reasoning": config.weights.reasoning, "performance": config.weights.performance,
                 "rag": config.weights.rag}
    )
    score_engine.load_results(input_dir)

    if not score_engine.results:
        console.warning(f"结果目录 {input_dir} 中无评估结果")
        return

    generator = ReportGenerator(score_engine, output_dir)

    for fmt in formats:
        try:
            if fmt == "html":
                path = generator.generate_report(score_engine.results)
                console.success(f"HTML 报告: {path}")
            elif fmt == "json":
                os.makedirs(output_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(output_dir, f"eval_summary_{ts}.json")
                import json
                summary = {
                    "models": [
                        {
                            "model_name": r.model_name,
                            "model_id": r.model_id,
                            "eval_time": r.eval_time,
                            "overall_score": r.overall_score,
                            "dimensions": {n: {"score": d.score} for n, d in r.dimensions.items()}
                        }
                        for r in score_engine.results
                    ]
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
                console.success(f"JSON 报告: {path}")
            elif fmt == "txt":
                os.makedirs(output_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(output_dir, f"execution_log_{ts}.txt")
                lines = ["=" * 60, "LLMtest v3.0 评估执行日志", "=" * 60, ""]
                leaderboard = score_engine.get_leaderboard()
                for entry in leaderboard:
                    dims = entry.get("dimensions", {})
                    lines.append(f"排名 #{entry['rank']}: {entry['model_name']}")
                    lines.append(f"  综合评分: {entry['overall_score']:.1f}")
                    for dn in ["coding", "agent", "reasoning", "performance", "rag"]:
                        if dn in dims:
                            lines.append(f"  {dn}: {dims[dn]}")
                    lines.append("")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                console.success(f"TXT 日志: {path}")
            else:
                console.warning(f"暂不支持 {fmt} 格式 (支持: html, json, txt, docx)")
        except Exception as e:
            console.error(f"{fmt.upper()} 报告生成失败: {e}")


async def handle_lifecycle_cmd(args, config):
    """处理 lifecycle 子命令 (简化版: 跳过 lms 加载/卸载)"""
    model_id = args.model
    profile = getattr(args, "profile", "default")
    profile_config = config.profiles.get(profile, config.profiles["default"])

    if args.api_url:
        config.api.base_url = args.api_url

    client = LMStudioClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
        sock_read_timeout=getattr(config.api, 'sock_read_timeout', 120),
        max_retries=config.api.max_retries
    )

    console.header("🔄 全生命周期评估")
    console.print(f"  模型: {model_id}", "info")
    console.print(f"  Profile: {profile}", "info")

    if not await check_connection(client, config):
        await client.close()
        sys.exit(1)

    result, score_engine = await run_evaluation(
        model_id=model_id,
        model_name=model_id,
        dimensions=["coding", "agent", "reasoning", "performance", "rag"],
        config=config,
        client=client
    )

    show_summary(result)

    result_path = score_engine.save_result(result, config.report.results_dir)
    console.success(f"结果已保存: {result_path}")

    await show_leaderboard(score_engine)
    await client.close()


async def handle_eval_cmd(args, config):
    """处理 eval 子命令"""
    # Profile 支持
    profile = getattr(args, "profile", None) or "default"
    profile_config = config.profiles.get(profile, config.profiles["default"])

    # 权重使用 Profile 的权重
    weights = {
        "coding": profile_config.weights.coding,
        "agent": profile_config.weights.agent,
        "reasoning": profile_config.weights.reasoning,
        "performance": profile_config.weights.performance,
        "rag": profile_config.weights.rag
    }

    if args.api_url:
        config.api.base_url = args.api_url

    client = LMStudioClient(
        base_url=config.api.base_url,
        api_key=config.api.api_key,
        timeout=config.api.timeout,
        sock_read_timeout=getattr(config.api, 'sock_read_timeout', 120),
        max_retries=config.api.max_retries
    )

    console.header("🤖 LM Studio 模型评估套件 v3.0")
    console.print(f"  API 地址: {config.api.base_url}", "dim")
    console.print(f"  Profile: {profile}", "dim")
    console.print(f"  评估权重: 代码={weights['coding']} Agent={weights['agent']} "
                  f"推理={weights['reasoning']} 性能={weights['performance']} RAG={weights['rag']}", "dim")

    # 排行榜模式 (向后兼容)
    if getattr(args, "leaderboard", False):
        await handle_leaderboard_cmd(args, config)
        await client.close()
        return

    # 检查连接
    if not await check_connection(client, config):
        await client.close()
        sys.exit(1)

    # Token校准
    calibration = await client.calibrate_tokens()
    if calibration.get("status") == "calibrated":
        console.print(f"  Token校准: factor={calibration['calibration_factor']:.3f} "
                      f"(actual={calibration['actual_prompt_tokens']}, "
                      f"estimated={calibration['estimated_tokens']})", "dim")

    # 获取模型信息
    if args.model:
        model_id, model_name = args.model, args.model
    else:
        model_id, model_name = await get_model_info(client)

    # 选择评估维度
    mode = getattr(args, "mode", None)
    if getattr(args, "all", False):
        dimensions = ["coding", "agent", "reasoning", "performance", "rag"]
    elif getattr(args, "dim", None):
        dimensions = args.dim
    elif mode and hasattr(config, "eval_modes") and mode in config.eval_modes:
        mode_config = config.eval_modes[mode]
        dimensions = getattr(mode_config, "dimensions", ["coding", "agent", "reasoning"])
    else:
        dimensions = select_dimensions()

    # 评估模式 (quick 模式减少采样)
    if mode == "quick":
        console.print(f"  模式: quick (快速筛选)", "info")
    elif mode == "standard":
        console.print(f"  模式: standard (标准评估)", "info")
    elif mode == "full":
        console.print(f"  模式: full (全量评估)", "info")

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
            client=client,
            weights=weights
        )

        show_summary(result)

        result_path = score_engine.save_result(result, config.report.results_dir)
        console.success(f"评估结果已保存: {result_path}")

        score_engine.load_results(config.report.results_dir)
        await show_leaderboard(score_engine)

        if getattr(args, "report", False) or len(score_engine.results) >= 1:
            try:
                output_dir = getattr(args, "output_dir", None) or config.report.output_dir
                generator = ReportGenerator(score_engine, output_dir)
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


async def main():
    parser = build_parser()
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 无子命令: 交互式运行 (向后兼容)
    if args.command is None:
        console.header("🤖 LM Studio 模型评估套件")
        console.print(f"  API 地址: {config.api.base_url}", "dim")
        console.print(f"  评估权重: 代码={config.weights.coding} Agent={config.weights.agent} "
                      f"推理={config.weights.reasoning} 性能={config.weights.performance}", "dim")

        if args.api_url:
            config.api.base_url = args.api_url

        client = LMStudioClient(
            base_url=config.api.base_url,
            api_key=config.api.api_key,
            timeout=config.api.timeout,
            sock_read_timeout=getattr(config.api, 'sock_read_timeout', 120),
            max_retries=config.api.max_retries
        )

        if args.leaderboard:
            await handle_leaderboard_cmd(args, config)
            await client.close()
            return

        if not await check_connection(client, config):
            await client.close()
            sys.exit(1)

        if args.model:
            model_id, model_name = args.model, args.model
        else:
            model_id, model_name = await get_model_info(client)

        if args.all:
            dimensions = ["coding", "agent", "reasoning", "performance", "rag"]
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

        try:
            result, score_engine = await run_evaluation(
                model_id=model_id,
                model_name=model_name,
                dimensions=dimensions,
                config=config,
                client=client
            )

            show_summary(result)

            result_path = score_engine.save_result(result, config.report.results_dir)
            console.success(f"评估结果已保存: {result_path}")

            score_engine.load_results(config.report.results_dir)
            await show_leaderboard(score_engine)

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
        return

    # 子命令分发
    if args.command == "leaderboard":
        await handle_leaderboard_cmd(args, config)
    elif args.command == "report":
        await handle_report_cmd(args, config)
    elif args.command == "lifecycle":
        await handle_lifecycle_cmd(args, config)
    elif args.command == "eval":
        await handle_eval_cmd(args, config)


if __name__ == "__main__":
    asyncio.run(main())
