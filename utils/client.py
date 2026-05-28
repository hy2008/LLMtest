"""
LM Studio API 客户端模块
负责与 LM Studio 的 OpenAI 兼容 API 交互
"""

import time
import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field


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


class LMStudioClient:
    """LM Studio API 客户端"""

    def __init__(self, base_url: str = "http://localhost:1234/v1",
                 api_key: str = "lm-studio", timeout: int = 120,
                 max_retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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
            async with session.get("/models") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def list_models(self) -> List[ModelInfo]:
        """获取可用模型列表"""
        data = await self._request_with_retry("GET", "/models")
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
            "messages": [{"role": m.role, "content": m.content} for m in messages],
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
        """非流式请求"""
        data = await self._request_with_retry("POST", "/chat/completions", payload)
        latency = (time.perf_counter() - start_time) * 1000

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        # Handle reasoning models (content may be empty, use reasoning_content instead)
        content = message.get("content", "")
        reasoning_content = message.get("reasoning_content", "")
        if not content and reasoning_content:
            content = reasoning_content

        return CompletionResult(
            content=content,
            model=data.get("model", ""),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            tool_calls=message.get("tool_calls"),
            latency_ms=latency,
            ttft_ms=latency  # 非流式时 TTFT ≈ 总延迟
        )

    async def _stream_chat(self, payload: Dict, start_time: float) -> CompletionResult:
        """流式请求 (用于测量 TTFT)"""
        session = await self._get_session()
        full_content = ""
        first_token_time = None
        tool_calls_data = []
        finish_reason = ""

        async with session.post("/chat/completions", json=payload) as resp:
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

                    if delta.get("tool_calls"):
                        tool_calls_data.extend(delta["tool_calls"])

                    fr = chunk.get("choices", [{}])[0].get("finish_reason")
                    if fr:
                        finish_reason = fr

                except json.JSONDecodeError:
                    continue

        latency = (time.perf_counter() - start_time) * 1000
        ttft = (first_token_time - start_time) * 1000 if first_token_time else latency

        return CompletionResult(
            content=full_content,
            model=payload.get("model", ""),
            prompt_tokens=0,
            completion_tokens=len(full_content),
            total_tokens=len(full_content),
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
