"""
边界条件与鲁棒性测试 (T-24)
测试评估框架在极端输入场景下的行为
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from utils.score_engine import ScoreEngine, CategoryScore
from utils.client import LMStudioClient, ChatMessage, CompletionResult, _sanitize_content


class TestBoundaryLongPrompt:
    def test_sanitize_long_text(self):
        long_text = "x" * 100000
        result = _sanitize_content(long_text)
        assert len(result) == 100000
        assert result == long_text

    def test_score_engine_handles_long_details(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        long_details = [{"data": "x" * 10000} for _ in range(100)]
        categories = [CategoryScore(category="test", score=50, max_score=100,
                                     details=long_details, weight=1.0)]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 50.0


class TestBoundaryEmptyInput:
    def test_sanitize_empty(self):
        assert _sanitize_content("") == ""
        assert _sanitize_content(None) is None

    def test_score_engine_zero_max_score(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        categories = [CategoryScore(category="test", score=0, max_score=0,
                                     details=[], weight=1.0)]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 0

    def test_reverse_validation_empty_response(self):
        result = ScoreEngine.reverse_validation("", "code")
        assert result["score"] >= 0

    def test_reverse_validation_none_response(self):
        result = ScoreEngine.reverse_validation("", "logic")
        assert result["score"] >= 0


class TestBoundaryControlCharacters:
    def test_sanitize_removes_all_control_chars(self):
        text = "a\x00b\x01c\x02d\x07e\x08f\x0bg\x0ch\x0ei\x0fj\x1ak\x1bl\x7fm"
        result = _sanitize_content(text)
        assert result == "abcdefghijklm"

    def test_sanitize_preserves_whitespace(self):
        text = "hello\tworld\nnew line\r\nwindows"
        result = _sanitize_content(text)
        assert result == text

    def test_sanitize_mixed_unicode_and_control(self):
        text = "你好\x1a世界\x00测试"
        result = _sanitize_content(text)
        assert result == "你好世界测试"


class TestBoundaryScoreEngine:
    def test_all_zero_scores(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        categories = [
            CategoryScore(category="c1", score=0, max_score=100, weight=1.0),
            CategoryScore(category="c2", score=0, max_score=100, weight=1.0),
        ]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 0

    def test_all_max_scores(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        categories = [
            CategoryScore(category="c1", score=100, max_score=100, weight=1.0),
            CategoryScore(category="c2", score=100, max_score=100, weight=1.0),
        ]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 100.0

    def test_extreme_weight_values(self):
        engine = ScoreEngine(weights={"a": 0.001, "b": 0.999})
        result = engine.create_result("test", "test-model")
        categories_a = [CategoryScore(category="c1", score=0, max_score=100, weight=1.0)]
        categories_b = [CategoryScore(category="c2", score=100, max_score=100, weight=1.0)]
        engine.add_dimension_score(result, "a", categories_a)
        engine.add_dimension_score(result, "b", categories_b)
        engine.finalize(result)
        assert 99 < result.overall_score <= 100

    def test_single_category(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        categories = [CategoryScore(category="only", score=75, max_score=100, weight=1.0)]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 75.0

    def test_many_categories(self):
        engine = ScoreEngine()
        result = engine.create_result("test", "test-model")
        categories = [CategoryScore(category=f"c{i}", score=50, max_score=100, weight=1.0)
                      for i in range(50)]
        engine.add_dimension_score(result, "test", categories)
        assert result.dimensions["test"].score == 50.0


class TestBoundaryReverseValidation:
    def test_code_many_blocks_mixed(self):
        response = "```python\nprint(1)\n```\nSome text\n```python\ninvalid !!!\n```"
        result = ScoreEngine.reverse_validation(response, "code")
        assert 0 < result["score"] < 100

    def test_logic_custom_test_cases(self):
        custom = [{"claim_pattern": r"必须", "counter_needed": True,
                   "description": "强制要求需考虑例外"}]
        result = ScoreEngine.reverse_validation("这个功能必须实现", "logic", test_cases=custom)
        assert result["score"] < 100

    def test_logic_all_passed(self):
        custom = [{"claim_pattern": r"不可能存在的模式xyz", "counter_needed": True,
                   "description": "无匹配模式"}]
        result = ScoreEngine.reverse_validation("普通文本", "logic", test_cases=custom)
        assert result["passed"] is True


class TestBoundaryRAGEvaluator:
    def test_empty_response_scoring(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = RAG_BENCHMARKS[0]
        score, detail = evaluator._score_generation_quality("", test)
        assert score == 0

    def test_hallucination_all_traps_triggered(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = RAG_BENCHMARKS[0]
        traps = test.get("hallucination_traps", [])
        hallucinated_response = " ".join(traps)
        score, detail = evaluator._score_hallucination(hallucinated_response, test)
        assert score == 0

    def test_retrieval_no_expected_facts(self):
        from evaluators.rag_eval import RAGEvaluator
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = {"criteria": {"retrieval_accuracy": 8}, "expected_facts": [], "name": "test"}
        score, detail = evaluator._score_retrieval("response", test)
        assert score == 8