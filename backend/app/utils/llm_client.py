"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import logging
import re
import threading
import time
from typing import Optional, Dict, Any, List
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from ..config import Config

_budget_logger = logging.getLogger('mirofish.token_budget')


class TokenBudgetExhausted(Exception):
    """Raised when the global token budget has been exceeded."""
    pass


class TokenBudget:
    """
    Global token budget tracker with circuit breaker.

    Shared across all LLM calls in a pipeline run. Thread-safe.

    Usage:
        budget = TokenBudget(max_tokens=500_000)
        client = LLMClient(token_budget=budget)
        # ... all calls through client are tracked
        # Raises TokenBudgetExhausted if budget exceeded
    """

    def __init__(self, max_tokens: int = 500_000, max_consecutive_failures: int = 5):
        self.max_tokens = max_tokens
        self.max_consecutive_failures = max_consecutive_failures
        self._lock = threading.Lock()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_calls = 0
        self._consecutive_failures = 0

    @property
    def total_tokens(self) -> int:
        return self._total_input_tokens + self._total_output_tokens

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.total_tokens)

    @property
    def total_calls(self) -> int:
        return self._total_calls

    def record_usage(self, input_tokens: int, output_tokens: int):
        """Record token usage from a successful call. Resets failure counter."""
        with self._lock:
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._total_calls += 1
            self._consecutive_failures = 0
            if self.total_tokens > self.max_tokens:
                _budget_logger.error(
                    f"Token budget exhausted: {self.total_tokens}/{self.max_tokens} "
                    f"after {self._total_calls} calls"
                )
                raise TokenBudgetExhausted(
                    f"Token budget exhausted: {self.total_tokens:,} / {self.max_tokens:,}"
                )

    def record_failure(self):
        """Record a failed call. Raises if circuit breaker trips."""
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.max_consecutive_failures:
                _budget_logger.error(
                    f"Circuit breaker tripped: {self._consecutive_failures} "
                    f"consecutive failures after {self._total_calls} calls"
                )
                raise TokenBudgetExhausted(
                    f"Circuit breaker: {self._consecutive_failures} consecutive LLM failures"
                )

    def check_budget(self):
        """Pre-flight check before making a call."""
        if self.total_tokens >= self.max_tokens:
            raise TokenBudgetExhausted(
                f"Token budget exhausted: {self.total_tokens:,} / {self.max_tokens:,}"
            )

    def summary(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "total_calls": self._total_calls,
            "remaining": self.remaining,
        }


class LLMClient:
    """LLM客户端"""

    JSON_REASONING_MIN_TOKENS = 8192
    JSON_RETRY_TOKENS = 12000
    # Errors worth retrying on the SAME provider (transient)
    RETRYABLE_EXCEPTIONS = (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )
    # Errors that should skip to the NEXT provider immediately (no retry on same)
    FAILOVER_EXCEPTIONS = (
        AuthenticationError,
        NotFoundError,
        PermissionDeniedError,
    )
    MAX_REQUEST_RETRIES = 3
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        token_budget: Optional[TokenBudget] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        self.token_budget = token_budget
        # Failover chain: list of (api_key, base_url, model) to try on failure
        self._failover_chain: List[tuple] = []

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    @classmethod
    def from_task(cls, task_name: str, token_budget: Optional[TokenBudget] = None) -> "LLMClient":
        """Build a client for a specific task with full failover chain."""
        chain = Config.get_task_chain(task_name)
        client = cls._from_chain(chain, token_budget)
        return client or cls(token_budget=token_budget)

    @classmethod
    def from_boost_config(cls, token_budget: Optional[TokenBudget] = None) -> Optional["LLMClient"]:
        """Return a boost LLMClient with multi-provider failover."""
        chain = Config.get_boost_chain()
        return cls._from_chain(chain, token_budget)

    @classmethod
    def from_cheap_config(cls, token_budget: Optional[TokenBudget] = None) -> Optional["LLMClient"]:
        """Return a cheap LLMClient with multi-provider failover."""
        chain = Config.get_cheap_chain()
        return cls._from_chain(chain, token_budget)

    @classmethod
    def _from_chain(cls, chain: List[tuple], token_budget: Optional[TokenBudget] = None) -> Optional["LLMClient"]:
        """Build client from first available provider in chain, with failover list."""
        if not chain:
            return None
        api_key, base_url, model = chain[0]
        client = cls(api_key=api_key, base_url=base_url, model=model, token_budget=token_budget)
        # Attach remaining chain entries as failover targets
        client._failover_chain = chain[1:]
        return client

    def _uses_max_completion_tokens(self) -> bool:
        """GPT-5 and newer reasoning-style models expect max_completion_tokens."""
        prefixes = ('gpt-5', 'o1', 'o3', 'o4')
        return self.model.startswith(prefixes)

    def _build_chat_kwargs(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict] = None,
        reasoning_effort: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build request kwargs while keeping model-family quirks in one place."""
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if self._uses_max_completion_tokens():
            kwargs["max_completion_tokens"] = max_tokens
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
        else:
            kwargs["temperature"] = temperature
            kwargs["max_tokens"] = max_tokens

        if response_format:
            kwargs["response_format"] = response_format

        return kwargs

    def _create_completion(self, kwargs: Dict[str, Any]):
        """Submit a completion request with retries and multi-provider failover."""
        # Pre-flight budget check
        if self.token_budget:
            self.token_budget.check_budget()

        # Try primary provider first, then failover chain
        providers = [(self.client, self.model)] + [
            (OpenAI(api_key=ak, base_url=bu), m)
            for ak, bu, m in self._failover_chain
        ]

        last_exception = None
        for provider_idx, (client, model) in enumerate(providers):
            current_kwargs = dict(kwargs)
            current_kwargs["model"] = model
            retry_delay = 1.0

            for attempt in range(self.MAX_REQUEST_RETRIES):
                try:
                    result = client.chat.completions.create(**current_kwargs)
                    # Record token usage
                    if self.token_budget and result and hasattr(result, 'usage') and result.usage:
                        self.token_budget.record_usage(
                            input_tokens=result.usage.prompt_tokens or 0,
                            output_tokens=result.usage.completion_tokens or 0,
                        )
                    if provider_idx > 0:
                        _budget_logger.info(
                            f"Failover success: provider #{provider_idx + 1} ({model})"
                        )
                    return result
                except BadRequestError as exc:
                    message = str(exc)
                    updated_kwargs = None

                    if "max_tokens" in current_kwargs and "max_completion_tokens" in message:
                        updated_kwargs = dict(current_kwargs)
                        val = updated_kwargs.pop("max_tokens")
                        updated_kwargs["max_completion_tokens"] = val
                    elif "max_completion_tokens" in current_kwargs and "max_tokens" in message:
                        updated_kwargs = dict(current_kwargs)
                        updated_kwargs["max_tokens"] = updated_kwargs.pop("max_completion_tokens")
                    elif "temperature" in message and "supported" in message:
                        updated_kwargs = dict(current_kwargs)
                        updated_kwargs.pop("temperature", None)
                    elif "reasoning_effort" in message:
                        updated_kwargs = dict(current_kwargs)
                        updated_kwargs.pop("reasoning_effort", None)

                    if updated_kwargs is None:
                        last_exception = exc
                        break  # Non-fixable BadRequest — try next provider
                    current_kwargs = updated_kwargs
                except self.FAILOVER_EXCEPTIONS as exc:
                    # Auth/permission/model-not-found — no point retrying same provider
                    last_exception = exc
                    _budget_logger.warning(f"Provider #{provider_idx + 1} ({model}): {type(exc).__name__}")
                    break  # Skip to next provider immediately
                except self.RETRYABLE_EXCEPTIONS as exc:
                    last_exception = exc
                    if self.token_budget:
                        self.token_budget.record_failure()
                    if attempt >= self.MAX_REQUEST_RETRIES - 1:
                        break  # Exhausted retries — try next provider
                    time.sleep(retry_delay)
                    retry_delay *= 2

            # Log failover attempt
            if provider_idx < len(providers) - 1:
                _budget_logger.warning(
                    f"Provider #{provider_idx + 1} ({model}) failed, "
                    f"failing over to #{provider_idx + 2}..."
                )

        # All providers exhausted
        raise last_exception or RuntimeError("All LLM providers failed")

    def _clean_text_response(self, content: Optional[str]) -> str:
        content = content or ""
        # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
        return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

    def _clean_json_response(self, content: Optional[str]) -> str:
        cleaned_response = self._clean_text_response(content)
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        return cleaned_response.strip()

    def _preview_response(self, content: str, limit: int = 400) -> str:
        if len(content) <= limit:
            return content
        return content[:limit] + "..."
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
        reasoning_effort: Optional[str] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        kwargs = self._build_chat_kwargs(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            reasoning_effort=reasoning_effort
        )
        response = self._create_completion(kwargs)
        if not response or not response.choices:
            return None
        return self._clean_text_response(response.choices[0].message.content)
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            解析后的JSON对象
        """
        request_tokens = max_tokens
        reasoning_effort = None

        if self._uses_max_completion_tokens():
            request_tokens = max(request_tokens, self.JSON_REASONING_MIN_TOKENS)
            reasoning_effort = "low"

        last_error: Optional[Exception] = None

        for attempt in range(2):
            kwargs = self._build_chat_kwargs(
                messages=messages,
                temperature=temperature,
                max_tokens=request_tokens,
                response_format={"type": "json_object"},
                reasoning_effort=reasoning_effort
            )
            response = self._create_completion(kwargs)
            if not response or not response.choices:
                last_error = ValueError("LLM返回空响应（无choices）")
            else:
                choice = response.choices[0]
                cleaned_response = self._clean_json_response(choice.message.content)

                if cleaned_response:
                    try:
                        return json.loads(cleaned_response)
                    except json.JSONDecodeError:
                        last_error = ValueError(
                            f"LLM返回的JSON格式无效（finish_reason={choice.finish_reason}）: "
                            f"{self._preview_response(cleaned_response)}"
                        )
                else:
                    last_error = ValueError(f"LLM返回空响应（finish_reason={choice.finish_reason}）")

                should_retry = (
                    self._uses_max_completion_tokens()
                    and attempt == 0
                    and (choice.finish_reason == "length" or not cleaned_response)
                )
                if should_retry:
                    request_tokens = max(request_tokens * 2, self.JSON_RETRY_TOKENS)
                    continue

            raise last_error

        raise last_error or ValueError("LLM返回未知错误")
