import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from review.orchestrator import ReviewOrchestrator


def main():
    orchestrator = ReviewOrchestrator()
    report, context = orchestrator.run()

    output_dir = os.path.join(
        os.path.dirname(__file__), "..", "docs", "superpowers", "reports"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "phase0-review-report.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    from review.models import ReviewConclusion
    conclusion = ReviewConclusion.from_findings(context.findings, context.acceptance_items)

    print(f"审查完成: 结论={conclusion.verdict}")
    print(f"严重={conclusion.severe_count}, 一般={conclusion.general_count}, 观察={conclusion.observation_count}, 建议={conclusion.suggestion_count}")
    print(f"报告已输出至: {output_path}")


if __name__ == "__main__":
    main()
