import unittest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestStripReasoningPrefix(unittest.TestCase):
    def setUp(self):
        from evaluators.coding import CodingEvaluator
        self.evaluator = CodingEvaluator.__new__(CodingEvaluator)

    def test_empty_string(self):
        self.assertEqual(self.evaluator._strip_reasoning_prefix(""), "")

    def test_no_prefix_just_code(self):
        code = "```python\ndef hello():\n    print('hello')\n```"
        self.assertEqual(self.evaluator._strip_reasoning_prefix(code), code)

    def test_thinking_process_prefix(self):
        text = "Thinking Process:\n1. First I need to...\n2. Then I'll...\n\n```python\ndef hello():\n    print('hello')\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertTrue(result.startswith("```python"))
        self.assertIn("def hello()", result)

    def test_chinese_analysis_prefix(self):
        text = "分析：\n1. 首先考虑输入\n2. 然后处理逻辑\n\n```python\ndef process(x):\n    return x * 2\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertTrue(result.startswith("```python"))
        self.assertIn("def process", result)

    def test_let_me_think_prefix(self):
        text = "Let me think about this...\n\n```python\ndef solve():\n    pass\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertTrue(result.startswith("```python"))

    def test_long_prefix_stripped(self):
        prefix = "A" * 150
        text = f"{prefix}\n```python\ndef f(): pass\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertTrue(result.startswith("```python"))

    def test_short_non_reasoning_prefix_kept(self):
        text = "Some note\n```python\ndef f(): pass\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertEqual(result, text)

    def test_no_fence_code_start(self):
        text = "Thinking about it...\n\ndef solve():\n    return 42"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertIn("def solve()", result)
        self.assertNotIn("Thinking", result)

    def test_no_fence_no_strip(self):
        text = "def solve():\n    return 42"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertEqual(result, text)

    def test_code_fence_at_start(self):
        text = "```python\ndef f(): pass\n```"
        result = self.evaluator._strip_reasoning_prefix(text)
        self.assertEqual(result, text)


class TestExtractToolCallsFromText(unittest.TestCase):
    def setUp(self):
        from utils.client import LMStudioClient
        self.client = LMStudioClient.__new__(LMStudioClient)

    def test_empty_text(self):
        self.assertIsNone(self.client._extract_tool_calls_from_text(""))

    def test_short_text(self):
        self.assertIsNone(self.client._extract_tool_calls_from_text("short"))

    def test_json_tool_call(self):
        text = 'I will call the function {"name": "get_weather", "arguments": {"city": "北京"}}'
        result = self.client._extract_tool_calls_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "get_weather")
        self.assertEqual(result[0]["function"]["arguments"]["city"], "北京")

    def test_multiple_json_tool_calls(self):
        text = (
            'First: {"name": "read_file", "arguments": {"path": "/tmp/a.txt"}} '
            'Then: {"name": "write_file", "arguments": {"path": "/tmp/b.txt", "content": "hello"}}'
        )
        result = self.client._extract_tool_calls_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["function"]["name"], "read_file")
        self.assertEqual(result[1]["function"]["name"], "write_file")

    def test_natural_language_tool_call(self):
        text = "I'll use function search_web with {\"query\": \"python tutorial\"}"
        result = self.client._extract_tool_calls_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["function"]["name"], "search_web")

    def test_no_tool_calls(self):
        text = "The weather in Beijing is sunny today. Temperature is 25 degrees."
        result = self.client._extract_tool_calls_from_text(text)
        self.assertIsNone(result)

    def test_call_function_pattern(self):
        text = "call function execute_code with {\"code\": \"print(1)\"}"
        result = self.client._extract_tool_calls_from_text(text)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["function"]["name"], "execute_code")


class TestHardwareConfig(unittest.TestCase):
    def test_default_values(self):
        from utils.config import HardwareConfig
        hw = HardwareConfig()
        self.assertEqual(hw.platform, "mac_studio_m4_max")
        self.assertEqual(hw.memory_gb, 128)
        self.assertEqual(hw.mlx.max_concurrency, 4)
        self.assertEqual(hw.mlx.max_model_size_gb, 40)
        self.assertEqual(hw.mlx.gpu_cores, 40)

    def test_custom_values(self):
        from utils.config import HardwareConfig, HardwareMLXConfig
        hw = HardwareConfig(
            platform="custom",
            memory_gb=64,
            mlx=HardwareMLXConfig(max_concurrency=2, max_model_size_gb=20, gpu_cores=20)
        )
        self.assertEqual(hw.platform, "custom")
        self.assertEqual(hw.memory_gb, 64)
        self.assertEqual(hw.mlx.max_concurrency, 2)


class TestApplicationConfig(unittest.TestCase):
    def test_openclaw_defaults(self):
        from utils.config import ApplicationConfig
        app = ApplicationConfig()
        self.assertEqual(app.openclaw.prompt_style, "code_first")
        self.assertTrue(app.openclaw.suppress_reasoning)
        self.assertEqual(app.openclaw.max_tokens_code, 4096)
        self.assertEqual(app.openclaw.max_tokens_agent, 2048)

    def test_hermes_defaults(self):
        from utils.config import ApplicationConfig
        app = ApplicationConfig()
        self.assertEqual(app.hermes.prompt_style, "reasoning_allowed")
        self.assertFalse(app.hermes.suppress_reasoning)
        self.assertEqual(app.hermes.max_tokens_code, 4096)
        self.assertEqual(app.hermes.max_tokens_agent, 4096)

    def test_openclaw_vs_hermes_differences(self):
        from utils.config import ApplicationConfig
        app = ApplicationConfig()
        self.assertNotEqual(
            app.openclaw.prompt_style, app.hermes.prompt_style
        )
        self.assertNotEqual(
            app.openclaw.suppress_reasoning, app.hermes.suppress_reasoning
        )
        self.assertNotEqual(
            app.openclaw.max_tokens_agent, app.hermes.max_tokens_agent
        )


class TestConfigYamlLoading(unittest.TestCase):
    def test_config_yaml_has_hardware_section(self):
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        self.assertIn('hardware', cfg)
        self.assertIn('application', cfg)

    def test_config_yaml_hardware_values(self):
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        hw = cfg['hardware']
        self.assertEqual(hw.get('platform'), 'mac_studio_m4_max')
        self.assertEqual(hw.get('memory_gb'), 128)

    def test_config_yaml_application_values(self):
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        app = cfg['application']
        self.assertIn('openclaw', app)
        self.assertIn('hermes', app)
        self.assertTrue(app['openclaw'].get('suppress_reasoning'))
        self.assertFalse(app['hermes'].get('suppress_reasoning'))


class TestExtractThinkingContent(unittest.TestCase):
    def test_client_extract_thinking(self):
        from utils.client import LMStudioClient
        if hasattr(LMStudioClient, '_extract_thinking_content'):
            client = LMStudioClient.__new__(LMStudioClient)
            result = client._extract_thinking_content(
                content="",
                reasoning_content="I need to think about this...\nThe answer is 42"
            )
            self.assertIn("42", result)
        else:
            self.skipTest("_extract_thinking_content not found in LMStudioClient")

    def test_content_takes_priority(self):
        from utils.client import LMStudioClient
        if hasattr(LMStudioClient, '_extract_thinking_content'):
            client = LMStudioClient.__new__(LMStudioClient)
            result = client._extract_thinking_content(
                content="Actual response",
                reasoning_content="Internal thinking"
            )
            self.assertIn("Actual response", result)
        else:
            self.skipTest("_extract_thinking_content not found in LMStudioClient")

    def test_coding_should_suppress_reasoning(self):
        from evaluators.coding import CodingEvaluator
        ev = CodingEvaluator.__new__(CodingEvaluator)
        self.assertTrue(hasattr(ev, '_should_suppress_reasoning'))

    def test_agent_should_suppress_reasoning(self):
        from evaluators.agent import AgentEvaluator
        ev = AgentEvaluator.__new__(AgentEvaluator)
        self.assertTrue(hasattr(ev, '_should_suppress_reasoning'))


class TestTimeoutConfig(unittest.TestCase):
    def test_config_timeout_values(self):
        from utils.config import load_config
        cfg = load_config()
        self.assertEqual(cfg.api.timeout, 900)
        self.assertEqual(cfg.api.sock_read_timeout, 300)

    def test_client_with_sock_read_timeout(self):
        from utils.client import LMStudioClient
        import aiohttp
        client = LMStudioClient(timeout=600, sock_read_timeout=120)
        self.assertEqual(client.timeout.total, 600)
        self.assertEqual(client.timeout.sock_read, 120)

    def test_client_without_sock_read_timeout(self):
        from utils.client import LMStudioClient
        client = LMStudioClient(timeout=600)
        self.assertEqual(client.timeout.total, 600)
        self.assertIsNone(client.timeout.sock_read)


if __name__ == '__main__':
    unittest.main(verbosity=2)
