"""
LM Studio API 客户端模块
负责与 LM Studio 的 OpenAI 兼容 API 交互
"""

import re
import time
import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field


def _sanitize_content(text: str) -> str:
    if not text:
        return text
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数量。

    使用保守的字符/token 比率:
    - 英文: ~4 chars/token
    - 中文: ~1.5 chars/token (CJK 字符)
    - 代码: ~3 chars/token (符号较多)

    这作为流式响应无 usage 字段时的 fallback。
    当 API 返回 completion_tokens 时优先使用实际值。
    """
    if not text:
        return 0
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f')
    non_cjk = len(text) - cjk_count
    return max(1, int(cjk_count / 1.5 + non_cjk / 4.0))


@dataclass
class ModelInfo:
    """模型信息"""
    id: str
    owner: str = "local"
    object: str = "model"


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolDefinition:
    """工具定义"""
    type: str = "function"
    function: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionResult:
    """补全结果"""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""
    tool_calls: Optional[List[Dict]] = None
    latency_ms: float = 0.0
    ttft_ms: float = 0.0  # 首token延迟

    @property
    def tps(self) -> float:
        """实际 tokens/秒 (基于真实 token 计数)"""
        if self.completion_tokens > 0 and self.latency_ms > 0:
            return (self.completion_tokens / self.latency_ms) * 1000
        return 0.0


class LMStudioClient:
    """LM Studio API 客户端"""

    TOKEN_CALIBRATION_TEXT = (
        "Hello world. This is a test sentence for token calibration. "
        "你好世界。这是用于 token 校准的测试句子。"
    )

    def __init__(self, base_url: str = "http://localhost:1234/v1",
                 api_key: str = "lm-studio", timeout: int = 120,
                 sock_read_timeout: int = 0,
                 max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._token_calibration_factor: Optional[float] = None
        if sock_read_timeout > 0:
            self.timeout = aiohttp.ClientTimeout(total=timeout, sock_read=sock_read_timeout)
        else:
            self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # aiohttp requires base_url to end with '/'
            base_url = self.base_url if self.base_url.endswith('/') else self.base_url + '/'
            self._session = aiohttp.ClientSession(
                base_url=base_url,
                headers=headers,
                timeout=self.timeout
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _request_with_retry(self, method: str, path: str,
                                   json_data: Optional[Dict] = None) -> Optional[Dict]:
        """带重试的请求"""
        session = await self._get_session()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with session.request(method, path, json=json_data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        wait = 2 ** attempt
                        await asyncio.sleep(wait)
                        continue
                    else:
                        text = await resp.text()
                        last_error = f"HTTP {resp.status}: {text}"
                        break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise ConnectionError(f"API 请求失败 (重试 {self.max_retries} 次): {last_error}")

    async def check_connection(self) -> bool:
        """检查 API 连接"""
        try:
            session = await self._get_session()
            async with session.get("models") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def calibrate_tokens(self) -> Dict[str, Any]:
        """通过实际API调用校准token估算因子。

        发送一条校准文本，获取API返回的真实prompt_tokens，
        与估算token数对比，计算校准因子。
        后续所有token估算均乘以该因子。
        """
        payload = {
            "model": "loaded",
            "messages": [{"role": "user", "content": self.TOKEN_CALIBRATION_TEXT}],
            "max_tokens": 1,
            "temperature": 0.0,
            "stream": False
        }
        try:
            data = await self._request_with_retry("POST", "chat/completions", payload)
            usage = data.get("usage", {})
            actual_prompt_tokens = usage.get("prompt_tokens", 0)
            if actual_prompt_tokens <= 0:
                return {"actual_prompt_tokens": 0, "estimated_tokens": 0,
                        "calibration_factor": 1.0, "status": "no_usage_data"}
            estimated_tokens = _estimate_tokens(self.TOKEN_CALIBRATION_TEXT)
            self._token_calibration_factor = actual_prompt_tokens / estimated_tokens
            return {
                "actual_prompt_tokens": actual_prompt_tokens,
                "estimated_tokens": estimated_tokens,
                "calibration_factor": self._token_calibration_factor,
                "status": "calibrated"
            }
        except Exception as e:
            return {"actual_prompt_tokens": 0, "estimated_tokens": 0,
                    "calibration_factor": 1.0, "status": f"error: {str(e)[:80]}"}

    def estimate_tokens_calibrated(self, text: str) -> int:
        """使用校准因子估算token数量。"""
        base = _estimate_tokens(text)
        if self._token_calibration_factor is not None:
            return max(1, int(base * self._token_calibration_factor))
        return base

    async def list_models(self) -> List[ModelInfo]:
        """获取可用模型列表"""
        data = await self._request_with_retry("GET", "models")
        models = []
        for m in data.get("data", []):
            models.append(ModelInfo(
                id=m.get("id", "unknown"),
                owner=m.get("owned_by", "local"),
                object=m.get("object", "model")
            ))
        return models

    async def get_loaded_model(self) -> Optional[ModelInfo]:
        """获取当前已加载的模型"""
        models = await self.list_models()
        return models[0] if models else None

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False
    ) -> CompletionResult:
        """发送聊天补全请求"""
        payload: Dict[str, Any] = {
            "model": model or "loaded",
            "messages": [self._serialize_message(m) for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if tools:
            payload["tools"] = [
                {"type": t.type, "function": t.function} for t in tools
            ]
        if tool_choice:
            payload["tool_choice"] = tool_choice

        start_time = time.perf_counter()

        if stream:
            return await self._stream_chat(payload, start_time)
        else:
            return await self._non_stream_chat(payload, start_time)

    async def _non_stream_chat(self, payload: Dict, start_time: float) -> CompletionResult:
        """非流式请求 (使用 requests 库通过 run_in_executor 执行，避免 aiohttp 超时问题)"""
        import requests as _requests
        loop = asyncio.get_event_loop()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        def _sync_request():
            resp = _requests.post(url, headers=headers, json=payload, timeout=self.timeout.total if hasattr(self.timeout, 'total') else 3600)
            if resp.status_code != 200:
                raise ConnectionError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()

        try:
            data = await loop.run_in_executor(None, _sync_request)
        except _requests.exceptions.Timeout:
            raise ConnectionError(f"API 请求超时 (total={self.timeout.total if hasattr(self.timeout, 'total') else 3600}s)")
        except _requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"API 连接失败: {e}")

        latency = (time.perf_counter() - start_time) * 1000

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        # Handle reasoning models (content may be empty, use reasoning_content instead)
        content = message.get("content", "")
        reasoning_content = _sanitize_content(message.get("reasoning_content", ""))

        if not content.strip() and reasoning_content:
            content = reasoning_content

        if not content.strip():
            full_msg = str(message)
            think_patterns = [
                r' thinking(.*?) response',
                r'<thinking>(.*?)</thinking>',
                r'\[thinking\](.*?)\[/thinking\]',
            ]
            for pattern in think_patterns:
                think_match = re.search(pattern, full_msg, re.DOTALL)
                if think_match:
                    content = think_match.group(1).strip()
                    break

        content = _sanitize_content(content.strip())

        tool_calls_data = message.get("tool_calls")

        if (not tool_calls_data or len(tool_calls_data) == 0) and content:
            text_to_scan = reasoning_content if reasoning_content else content
            tool_calls_data = self._extract_tool_calls_from_text(text_to_scan)

        return CompletionResult(
            content=content,
            model=data.get("model", ""),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            tool_calls=tool_calls_data,
            latency_ms=latency,
            ttft_ms=latency
        )

    @staticmethod
    def _extract_tool_calls_from_text(text: str) -> Optional[List[Dict]]:
        """从推理文本中提取 tool_calls 描述。

        推理模型可能将 tool_calls 写在 reasoning_content 中:
        - "I'll use the get_weather function with {city: '北京'}"
        - JSON 片段: {"name": "get_weather", "arguments": {"city": "北京"}}
        """
        if not text or len(text) < 20:
            return None

        tool_calls = []

        json_pattern = r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*"arguments"\s*:\s*(\{[^{}]*\})[^{}]*\}'
        for match in re.finditer(json_pattern, text, re.DOTALL):
            try:
                name = match.group(1)
                args = json.loads(match.group(2))
                tool_calls.append({
                    "function": {"name": name, "arguments": args},
                    "type": "function"
                })
            except (json.JSONDecodeError, IndexError):
                continue

        if tool_calls:
            return tool_calls

        func_call_pattern = r'(?:call|use|invoke|execute)\s+(?:function\s+)?["\']?(\w+)["\']?\s*(?:with|using|having)?\s*(?:arguments?\s*)?(?:\[|\{|"|\')'
        found_names = set()
        for match in re.finditer(func_call_pattern, text, re.IGNORECASE):
            name = match.group(1)
            if name and name not in found_names and not name.startswith(('the', 'a ', 'an ')):
                found_names.add(name)
                tool_calls.append({
                    "function": {"name": name, "arguments": {}},
                    "type": "function"
                })

        return tool_calls if tool_calls else None

    @staticmethod
    def _serialize_message(m: ChatMessage) -> Dict[str, Any]:
        msg = {"role": m.role, "content": _sanitize_content(m.content)}
        if m.tool_calls:
            msg["tool_calls"] = m.tool_calls
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        return msg

    async def _stream_chat(self, payload: Dict, start_time: float) -> CompletionResult:
        """流式请求 (用于测量 TTFT)"""
        session = await self._get_session()
        full_content = ""
        reasoning_content = ""
        first_token_time = None
        tool_calls_data = []
        finish_reason = ""

        async with session.post("chat/completions", json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ConnectionError(f"流式请求失败 HTTP {resp.status}: {text}")

            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line or not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})

                    if first_token_time is None:
                        first_token_time = time.perf_counter()

                    if delta.get("content"):
                        full_content += delta["content"]

                    if delta.get("reasoning_content"):
                        reasoning_content += delta["reasoning_content"]

                    if delta.get("tool_calls"):
                        tool_calls_data.extend(delta["tool_calls"])

                    fr = chunk.get("choices", [{}])[0].get("finish_reason")
                    if fr:
                        finish_reason = fr

                except json.JSONDecodeError:
                    continue

        if not full_content and reasoning_content:
            full_content = reasoning_content

        full_content = _sanitize_content(full_content)

        latency = (time.perf_counter() - start_time) * 1000
        ttft = (first_token_time - start_time) * 1000 if first_token_time else latency

        return CompletionResult(
            content=full_content,
            model=payload.get("model", ""),
            prompt_tokens=0,
            completion_tokens=_estimate_tokens(full_content),
            total_tokens=_estimate_tokens(full_content),
            finish_reason=finish_reason,
            tool_calls=tool_calls_data if tool_calls_data else None,
            latency_ms=latency,
            ttft_ms=ttft
        )

    async def measure_ttft(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        runs: int = 3
    ) -> Dict[str, float]:
        """测量首 token 延迟 (TTFT)"""
        ttft_values = []
        for _ in range(runs):
            result = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            ttft_values.append(result.ttft_ms)

        return {
            "ttft_avg_ms": sum(ttft_values) / len(ttft_values),
            "ttft_min_ms": min(ttft_values),
            "ttft_max_ms": max(ttft_values),
            "ttft_p50_ms": sorted(ttft_values)[len(ttft_values) // 2],
            "runs": runs
        }

    async def measure_throughput(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        runs: int = 3
    ) -> Dict[str, float]:
        """测量吞吐量 (tokens/second)"""
        tps_values = []
        total_tokens_values = []
        latency_values = []

        for _ in range(runs):
            result = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            if result.completion_tokens > 0 and result.latency_ms > 0:
                tps = (result.completion_tokens / result.latency_ms) * 1000
                tps_values.append(tps)
                total_tokens_values.append(result.completion_tokens)
                latency_values.append(result.latency_ms)

        if not tps_values:
            return {"tps_avg": 0, "tps_min": 0, "tps_max": 0, "avg_total_tokens": 0}

        return {
            "tps_avg": sum(tps_values) / len(tps_values),
            "tps_min": min(tps_values),
            "tps_max": max(tps_values),
            "avg_total_tokens": sum(total_tokens_values) / len(total_tokens_values),
            "avg_latency_ms": sum(latency_values) / len(latency_values),
            "runs": runs
        }

    async def measure_concurrent_throughput(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        concurrency: int = 5,
        temperature: float = 0.0,
        max_tokens: int = 1024
    ) -> Dict[str, float]:
        """测量并发吞吐量"""
        start_time = time.perf_counter()
        tasks = [
            self.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for _ in range(concurrency)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = (time.perf_counter() - start_time) * 1000

        successful = [r for r in results if isinstance(r, CompletionResult)]
        failed = len(results) - len(successful)

        total_tokens = sum(r.completion_tokens for r in successful)
        total_latency = sum(r.latency_ms for r in successful)

        return {
            "concurrency": concurrency,
            "successful_requests": len(successful),
            "failed_requests": failed,
            "total_time_ms": total_time,
            "requests_per_second": (len(successful) / total_time) * 1000,
            "total_tokens": total_tokens,
            "overall_tps": (total_tokens / total_time) * 1000 if total_time > 0 else 0,
            "avg_latency_ms": total_latency / len(successful) if successful else 0
        }
