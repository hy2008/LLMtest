import pytest
from utils.score_engine import ScoreEngine


class TestReverseValidationCode:
    def test_no_code_blocks(self):
        result = ScoreEngine.reverse_validation("没有代码的普通文本", "code")
        assert result["passed"] is True
        assert result["score"] == 50

    def test_valid_code_passes(self):
        response = "```python\nprint('hello')\n```"
        result = ScoreEngine.reverse_validation(response, "code")
        assert result["passed"] is True
        assert result["score"] == 100

    def test_dangerous_code_rejected(self):
        response = "```python\nimport os\nos.system('rm -rf /')\n```"
        result = ScoreEngine.reverse_validation(response, "code")
        assert result["passed"] is False
        assert result["score"] == 0

    def test_syntax_error_code_fails(self):
        response = "```python\nthis is not valid python syntax !!!\n```"
        result = ScoreEngine.reverse_validation(response, "code")
        assert result["passed"] is False

    def test_empty_response(self):
        result = ScoreEngine.reverse_validation("", "code")
        assert result["passed"] is True
        assert result["score"] == 50


class TestReverseValidationLogic:
    def test_no_absolute_claims(self):
        response = "根据数据，冰淇淋销量和溺水事故可能存在相关性。"
        result = ScoreEngine.reverse_validation(response, "logic")
        assert result["passed"] is True
        assert result["score"] == 100

    def test_absolute_claim_with_counter(self):
        response = "所有优化都能提升性能。但需要注意，某些优化可能引入额外开销，不一定总是有效。"
        result = ScoreEngine.reverse_validation(response, "logic")
        assert result["passed"] is True

    def test_absolute_claim_without_counter(self):
        response = "所有优化都一定能提升性能，这是必然的。"
        result = ScoreEngine.reverse_validation(response, "logic")
        assert result["passed"] is False

    def test_unknown_type(self):
        result = ScoreEngine.reverse_validation("test", "unknown")
        assert result["passed"] is False
        assert result["score"] == 0


class TestRAGEvaluator:
    def test_import(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        assert len(RAG_BENCHMARKS) == 5

    def test_score_retrieval(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = RAG_BENCHMARKS[0]
        response = "LLMtest v3.0使用归一化评分公式score/max_score，支持coding、agent、reasoning、performance维度"
        score, detail = evaluator._score_retrieval(response, test)
        assert score > 0
        assert detail["found_facts"] > 0

    def test_score_hallucination(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = RAG_BENCHMARKS[0]
        clean_response = "LLMtest v3.0使用归一化评分公式，支持多种评估维度"
        score1, _ = evaluator._score_hallucination(clean_response, test)
        hallucinated_response = "LLMtest v3.0支持GPU加速和分布式评估，使用Redis存储"
        score2, _ = evaluator._score_hallucination(hallucinated_response, test)
        assert score1 >= score2

    def test_score_generation_quality(self):
        from evaluators.rag_eval import RAGEvaluator, RAG_BENCHMARKS
        evaluator = RAGEvaluator.__new__(RAGEvaluator)
        test = RAG_BENCHMARKS[0]
        good_response = "1. 评分公式: 归一化公式 score/max_score × 100 × weight\n2. 维度: coding, agent, reasoning, performance"
        score1, _ = evaluator._score_generation_quality(good_response, test)
        score2, _ = evaluator._score_generation_quality("", test)
        assert score1 > score2


class TestTokenCalibration:
    def test_estimate_tokens_calibrated_no_factor(self):
        from utils.client import LMStudioClient
        client = LMStudioClient.__new__(LMStudioClient)
        client._token_calibration_factor = None
        assert client.estimate_tokens_calibrated("hello world") > 0

    def test_estimate_tokens_calibrated_with_factor(self):
        from utils.client import LMStudioClient
        client = LMStudioClient.__new__(LMStudioClient)
        client._token_calibration_factor = 1.5
        result = client.estimate_tokens_calibrated("hello world")
        assert result > 0

    def test_calibrate_text_exists(self):
        from utils.client import LMStudioClient
        assert len(LMStudioClient.TOKEN_CALIBRATION_TEXT) > 0