"""
HTML 报告生成器
生成美观的评估报告和排行榜
"""

import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any
from utils.score_engine import ModelEvalResult, ScoreEngine


# ============================================================
# HTML 报告模板
# ============================================================

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LM Studio 模型评估报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 {
            text-align: center;
            font-size: 2em;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { text-align: center; color: #94a3b8; margin-bottom: 30px; }
        .section {
            background: #1e293b;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #334155;
        }
        .section h2 {
            font-size: 1.3em;
            margin-bottom: 16px;
            color: #60a5fa;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section h2::before {
            content: '';
            display: inline-block;
            width: 4px;
            height: 20px;
            background: linear-gradient(to bottom, #60a5fa, #a78bfa);
            border-radius: 2px;
        }

        /* 排行榜表格 */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }
        th {
            background: #334155;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #cbd5e1;
            border-bottom: 2px solid #475569;
        }
        td {
            padding: 12px 16px;
            border-bottom: 1px solid #1e293b;
        }
        tr:hover { background: #1e293b; }
        .rank-1 { color: #fbbf24; font-weight: bold; }
        .rank-2 { color: #94a3b8; font-weight: bold; }
        .rank-3 { color: #d97706; font-weight: bold; }

        /* 分数条 */
        .score-bar-container {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .score-bar {
            flex: 1;
            height: 8px;
            background: #334155;
            border-radius: 4px;
            overflow: hidden;
        }
        .score-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .score-excellent { background: linear-gradient(90deg, #22c55e, #4ade80); }
        .score-good { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        .score-average { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .score-poor { background: linear-gradient(90deg, #ef4444, #f87171); }

        /* 总分高亮 */
        .total-score {
            font-size: 1.4em;
            font-weight: bold;
            padding: 4px 12px;
            border-radius: 8px;
        }
        .score-high { color: #4ade80; }
        .score-mid { color: #fbbf24; }
        .score-low { color: #f87171; }

        /* 模型详情卡片 */
        .model-card {
            background: #0f172a;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
            border: 1px solid #334155;
        }
        .model-card h3 {
            color: #e2e8f0;
            margin-bottom: 12px;
            font-size: 1.1em;
        }
        .dimension-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
        }
        .dimension-item {
            background: #1e293b;
            border-radius: 8px;
            padding: 16px;
        }
        .dimension-item h4 {
            color: #94a3b8;
            font-size: 0.9em;
            margin-bottom: 8px;
        }
        .dimension-score {
            font-size: 1.8em;
            font-weight: bold;
        }
        .category-list {
            margin-top: 8px;
            font-size: 0.85em;
        }
        .category-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid #334155;
        }
        .category-item:last-child { border-bottom: none; }

        /* 性能指标 */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }
        .metric-card {
            background: #0f172a;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            border: 1px solid #334155;
        }
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #60a5fa;
        }
        .metric-label {
            color: #94a3b8;
            font-size: 0.85em;
            margin-top: 4px;
        }

        /* 雷达图占位 */
        .radar-placeholder {
            text-align: center;
            padding: 20px;
            color: #64748b;
        }

        /* 响应式 */
        @media (max-width: 768px) {
            body { padding: 10px; }
            .section { padding: 16px; }
            table { font-size: 0.85em; }
            th, td { padding: 8px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 LM Studio 模型评估报告</h1>
        <p class="subtitle">生成时间: {{ generated_at }} | 共评估 {{ model_count }} 个模型</p>

        <!-- 排行榜 -->
        <div class="section">
            <h2>🏆 综合排行榜</h2>
            <table>
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>模型</th>
                        <th>代码能力</th>
                        <th>Agent能力</th>
                        <th>通用推理</th>
                        <th>性能</th>
                        <th>综合评分</th>
                    </tr>
                </thead>
                <tbody>
                    {% for entry in leaderboard %}
                    <tr>
                        <td class="rank-{{ entry.rank }}">{{ entry.rank }}</td>
                        <td><strong>{{ entry.model_name }}</strong><br><small style="color:#64748b">{{ entry.model_id }}</small></td>
                        <td>{{ entry.dimensions.get('coding', '-') }}</td>
                        <td>{{ entry.dimensions.get('agent', '-') }}</td>
                        <td>{{ entry.dimensions.get('reasoning', '-') }}</td>
                        <td>{{ entry.dimensions.get('performance', '-') }}</td>
                        <td>
                            <span class="total-score {% if entry.overall_score >= 70 %}score-high{% elif entry.overall_score >= 40 %}score-mid{% else %}score-low{% endif %}">
                                {{ entry.overall_score }}
                            </span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- 模型详情 -->
        {% for model in models %}
        <div class="section">
            <h2>📋 {{ model.model_name }} 详细报告</h2>
            <p style="color:#64748b; margin-bottom:16px">评估时间: {{ model.eval_time }} | 模型ID: {{ model.model_id }}</p>

            <div class="dimension-grid">
                {% for dim_name, dim_data in model.dimensions.items() %}
                <div class="dimension-item">
                    <h4>{{ dim_data.label }}</h4>
                    <div class="dimension-score {% if dim_data.score >= 70 %}score-high{% elif dim_data.score >= 40 %}score-mid{% else %}score-low{% endif %}">
                        {{ dim_data.score }}
                    </div>
                    <div class="score-bar-container" style="margin: 8px 0">
                        <div class="score-bar">
                            <div class="score-bar-fill {% if dim_data.score >= 70 %}score-excellent{% elif dim_data.score >= 40 %}score-good{% elif dim_data.score >= 20 %}score-average{% else %}score-poor{% endif %}"
                                 style="width: {{ dim_data.score }}%"></div>
                        </div>
                    </div>
                    <div class="category-list">
                        {% for cat in dim_data.categories %}
                        <div class="category-item">
                            <span>{{ cat.category }}</span>
                            <span>{{ cat.score }}/{{ cat.max_score }}</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>

            {% if model.performance_metrics %}
            <h3 style="margin-top: 20px; color: #94a3b8">⚡ 性能指标</h3>
            <div class="metrics-grid">
                {% for metric in model.performance_metrics %}
                <div class="metric-card">
                    <div class="metric-value">{{ metric.value }}</div>
                    <div class="metric-label">{{ metric.label }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endfor %}

        <div class="section">
            <h2>📊 评估说明</h2>
            <div style="color: #94a3b8; font-size: 0.9em;">
                <p><strong>评分范围:</strong> 0-100 分，分数越高表示能力越强</p>
                <p><strong>代码能力 (权重30%):</strong> 代码生成、代码补全、Debug调试、多语言编程</p>
                <p><strong>Agent能力 (权重30%):</strong> Function Calling、工具选择、多步推理、指令遵循</p>
                <p><strong>通用推理 (权重25%):</strong> 逻辑推理、阅读理解、数学能力、知识问答</p>
                <p><strong>性能基准 (权重15%):</strong> 首Token延迟(TTFT)、吞吐量(TPS)、并发处理</p>
            </div>
        </div>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """HTML 报告生成器"""

    DIMENSION_LABELS = {
        "coding": "💻 代码能力",
        "agent": "🤖 Agent能力",
        "reasoning": "🧠 通用推理",
        "performance": "⚡ 性能基准"
    }

    def __init__(self, score_engine: ScoreEngine, output_dir: str = "reports"):
        self.score_engine = score_engine
        self.output_dir = output_dir

    def generate_report(self, results: List[ModelEvalResult] = None) -> str:
        """生成 HTML 评估报告"""
        if results is None:
            results = self.score_engine.results

        if not results:
            raise ValueError("没有可用的评估结果")

        leaderboard = self.score_engine.get_leaderboard()

        # 准备模板数据
        models_data = []
        for result in results:
            model_data = {
                "model_name": result.model_name,
                "model_id": result.model_id,
                "eval_time": result.eval_time,
                "overall_score": round(result.overall_score, 2),
                "dimensions": {},
                "performance_metrics": []
            }

            for dim_name, dim_score in result.dimensions.items():
                model_data["dimensions"][dim_name] = {
                    "label": self.DIMENSION_LABELS.get(dim_name, dim_name),
                    "score": round(dim_score.score, 2),
                    "categories": [
                        {
                            "category": cat.category,
                            "score": cat.score,
                            "max_score": cat.max_score
                        }
                        for cat in dim_score.categories
                    ]
                }

                # 提取性能指标
                if dim_name == "performance":
                    for cat in dim_score.categories:
                        if cat.details:
                            for detail in cat.details:
                                metrics = detail.get("metrics", {})
                                for metric_name, metric_value in metrics.items():
                                    label_map = {
                                        "avg_ttft_ms": "平均TTFT",
                                        "min_ttft_ms": "最小TTFT",
                                        "max_ttft_ms": "最大TTFT",
                                        "avg_tps": "平均TPS",
                                        "min_tps": "最小TPS",
                                        "max_tps": "最大TPS",
                                        "avg_total_tokens": "平均Token数",
                                        "avg_latency_ms": "平均延迟",
                                        "concurrency": "并发数",
                                        "successful_requests": "成功请求",
                                        "failed_requests": "失败请求",
                                        "success_rate": "成功率",
                                        "overall_tps": "整体TPS",
                                        "requests_per_second": "请求/秒"
                                    }
                                    unit_map = {
                                        "avg_ttft_ms": "ms",
                                        "min_ttft_ms": "ms",
                                        "max_ttft_ms": "ms",
                                        "avg_tps": "tok/s",
                                        "min_tps": "tok/s",
                                        "max_tps": "tok/s",
                                        "avg_total_tokens": "tokens",
                                        "avg_latency_ms": "ms",
                                        "overall_tps": "tok/s",
                                        "requests_per_second": "req/s",
                                        "success_rate": "%"
                                    }
                                    label = label_map.get(metric_name, metric_name)
                                    unit = unit_map.get(metric_name, "")
                                    value = f"{metric_value}{unit}" if unit else str(metric_value)
                                    model_data["performance_metrics"].append({
                                        "label": label,
                                        "value": value
                                    })

            models_data.append(model_data)

        # 简单的模板渲染 (不依赖 Jinja2 运行时)
        html = self._render_template(leaderboard, models_data)

        # 保存文件
        os.makedirs(self.output_dir, exist_ok=True)
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return filepath

    def _render_template(self, leaderboard: List[Dict], models: List[Dict]) -> str:
        """简单模板渲染"""
        html = REPORT_TEMPLATE
        html = html.replace("{{ generated_at }}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        html = html.replace("{{ model_count }}", str(len(models)))

        # 渲染排行榜
        rows = []
        for entry in leaderboard:
            dims = entry.get("dimensions", {})
            rows.append(f"""                    <tr>
                        <td class="rank-{entry['rank']}">{entry['rank']}</td>
                        <td><strong>{entry['model_name']}</strong><br><small style="color:#64748b">{entry['model_id']}</small></td>
                        <td>{dims.get('coding', '-')}</td>
                        <td>{dims.get('agent', '-')}</td>
                        <td>{dims.get('reasoning', '-')}</td>
                        <td>{dims.get('performance', '-')}</td>
                        <td>
                            <span class="total-score {'score-high' if entry['overall_score'] >= 70 else 'score-mid' if entry['overall_score'] >= 40 else 'score-low'}">
                                {entry['overall_score']}
                            </span>
                        </td>
                    </tr>""")
        html = html.replace("{% for entry in leaderboard %}", "")
        html = html.replace("{% endfor %}", "")
        # 找到排行榜 tbody 内容并替换
        tbody_start = html.find("<tbody>")
        tbody_end = html.find("</tbody>") + 8
        if tbody_start > 0 and tbody_end > 0:
            html = html[:tbody_start + 7] + "\n".join(rows) + "\n                " + html[tbody_end:]

        # 渲染模型详情
        model_sections = []
        for model in models:
            dim_items = []
            for dim_name, dim_data in model["dimensions"].items():
                score_class = "score-high" if dim_data["score"] >= 70 else "score-mid" if dim_data["score"] >= 40 else "score-low"
                bar_class = "score-excellent" if dim_data["score"] >= 70 else "score-good" if dim_data["score"] >= 40 else "score-average" if dim_data["score"] >= 20 else "score-poor"

                cat_items = []
                for cat in dim_data["categories"]:
                    cat_items.append(f"""                        <div class="category-item">
                            <span>{cat['category']}</span>
                            <span>{cat['score']}/{cat['max_score']}</span>
                        </div>""")

                dim_items.append(f"""                <div class="dimension-item">
                    <h4>{dim_data['label']}</h4>
                    <div class="dimension-score {score_class}">
                        {dim_data['score']}
                    </div>
                    <div class="score-bar-container" style="margin: 8px 0">
                        <div class="score-bar">
                            <div class="score-bar-fill {bar_class}"
                                 style="width: {dim_data['score']}%"></div>
                        </div>
                    </div>
                    <div class="category-list">
                    {"".join(cat_items)}
                    </div>
                </div>""")

            perf_section = ""
            if model.get("performance_metrics"):
                metric_cards = []
                for m in model["performance_metrics"]:
                    metric_cards.append(f"""                    <div class="metric-card">
                        <div class="metric-value">{m['value']}</div>
                        <div class="metric-label">{m['label']}</div>
                    </div>""")
                perf_section = f"""
            <h3 style="margin-top: 20px; color: #94a3b8">⚡ 性能指标</h3>
            <div class="metrics-grid">
            {"".join(metric_cards)}
            </div>"""

            model_sections.append(f"""        <div class="section">
            <h2>📋 {model['model_name']} 详细报告</h2>
            <p style="color:#64748b; margin-bottom:16px">评估时间: {model['eval_time']} | 模型ID: {model['model_id']}</p>

            <div class="dimension-grid">
            {"".join(dim_items)}
            </div>
            {perf_section}
        </div>""")

        # 替换模型详情部分
        detail_start = html.find("{% for model in models %}")
        detail_end = html.find("{% endfor %}")
        if detail_start > 0 and detail_end > 0:
            html = html[:detail_start] + "\n".join(model_sections) + "\n" + html[detail_end + len("{% endfor %}"):]

        # 清理剩余的模板标签
        html = re.sub(r'\{%.*?%\}', '', html)
        html = re.sub(r'\{\{.*?\}\}', '', html)

        return html
