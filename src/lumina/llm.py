"""
Lumina LLM Provider - 可配置的 LLM 集成（增强版）
支持 OpenAI、Anthropic、国内 API（DeepSeek、百炼、火山引擎、Kimi、智谱）及本地模型（Ollama/llama.cpp）

增强功能：
  • Circuit Breaker 保护
  • EventBus 事件发布
  • 自定义异常体系
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Iterator, List
from dataclasses import dataclass
import json
import requests


from .utils.logging import get_logger, timed
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, circuit_break
from .event_bus import (
    EventBus, get_global_event_bus,
    llm_success_event, llm_error_event
)
from .exceptions import (
    LuminaError, LLMError,
    LLMRateLimitError, LLMTimeoutError, LLMAuthenticationError, LLMAPIError, LLMResponseError,
    ErrorContext,
    rate_limit_error, timeout_error, auth_error, api_error
)

logger = get_logger("lumina.llm")

def _log_llm(message: str, level: str = "INFO"):
    """输出 LLM 请求日志（向后兼容）"""
    log_func = {
        "ERROR": logger.error,
        "WARNING": logger.warning,
        "INFO": logger.info,
        "DEBUG": logger.debug,
    }.get(level, logger.info)
    log_func(message)


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"  # openai | anthropic | ollama | deepseek | bailian | volcengine | kimi | glm
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_circuit_breaker: bool = True  # 是否启用 Circuit Breaker
    enable_events: bool = True  # 是否发布事件

    def __post_init__(self):
        if not self.base_url:
            self.base_url = self._get_default_base_url()

    def _get_default_base_url(self) -> str:
        """获取默认 base URL"""
        defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "ollama": "http://localhost:11434/v1",
            "llamacpp": "http://localhost:8080/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "bailian": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
            "kimi": "https://api.moonshot.cn/v1",
            "glm": "https://open.bigmodel.cn/api/paas/v4",
        }
        return defaults.get(self.provider, "")

    def validate(self) -> List[str]:
        """验证配置有效性"""
        errors = []
        # Ollama 和 llama.cpp 不需要 api_key
        if self.provider not in ["ollama", "llamacpp"]:
            if not self.api_key:
                env_key = self._get_env_key_name()
                if env_key and os.environ.get(env_key):
                    self.api_key = os.environ.get(env_key)
                else:
                    errors.append(f"Missing api_key for {self.provider} (set it in ~/.lumina/lumina.yaml or {env_key} env var)")
        if not self.base_url:
            errors.append(f"Missing base_url for {self.provider}")
        return errors

    def _get_env_key_name(self) -> Optional[str]:
        """获取对应 provider 的环境变量名称"""
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "bailian": "DASHSCOPE_API_KEY",
            "volcengine": "VOLCENGINE_API_KEY",
            "kimi": "MOONSHOT_API_KEY",
            "glm": "ZHIPU_API_KEY",
        }
        return env_map.get(self.provider)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（排除敏感信息）"""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
        }


class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类（增强版）"""

    def __init__(
        self,
        config: LLMConfig,
        circuit_breaker: CircuitBreaker = None,
        event_bus: EventBus = None
    ):
        self.config = config
        self.event_bus = event_bus or get_global_event_bus()
        
        # 如果 api_key 为空但有环境变量，尝试从环境变量加载
        if not self.config.api_key and self.config.provider not in ["ollama", "llamacpp"]:
            env_key = self.config._get_env_key_name()
            if env_key and os.environ.get(env_key):
                self.config.api_key = os.environ.get(env_key)
        
        errors = config.validate()
        if errors:
            raise ValueError(f"LLM config invalid: {'; '.join(errors)}")
        
        # 初始化 Circuit Breaker
        if config.enable_circuit_breaker:
            self.circuit_breaker = circuit_breaker or CircuitBreaker(
                name=f"llm.{config.provider}",
                config=CircuitBreakerConfig(
                    failure_threshold=5,
                    timeout_threshold=3,
                    rate_limit_threshold=2,
                    open_timeout_seconds=60.0,
                    enable_fallback=False  # LLM 调用通常不降级
                )
            )
        else:
            self.circuit_breaker = None

    @abstractmethod
    @timed
    def complete(self, prompt: str, **kwargs) -> str:
        """同步完成请求"""
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式完成请求"""
        pass

    def _convert_exception(self, exc: Exception) -> LuminaError:
        """将通用异常转换为新异常体系"""
        exc_str = str(exc).lower()
        
        if "rate limit" in exc_str or "429" in exc_str:
            # 提取 retry_after 信息
            retry_after = 60
            if hasattr(exc, 'response'):
                retry_after = exc.response.headers.get('Retry-After', 60)
            return rate_limit_error(str(exc), retry_after=retry_after)
        
        elif "timeout" in exc_str or "timed out" in exc_str:
            return timeout_error(str(exc), timeout_seconds=self.config.timeout)
        
        elif "authentication" in exc_str or "401" in exc_str or "403" in exc_str:
            return auth_error(str(exc))
        
        elif any(code in exc_str for code in ["500", "502", "503", "504"]):
            status_code = 500
            if hasattr(exc, 'response'):
                status_code = exc.response.status_code
            return api_error(str(exc), status_code=status_code)
        
        else:
            return LLMError(str(exc))

    def _publish_success_event(
        self,
        duration: float,
        tokens_used: int = 0,
        **extra
    ):
        """发布 LLM 成功事件"""
        if self.config.enable_events and self.event_bus:
            self.event_bus.publish(
                llm_success_event(
                    provider=self.config.provider,
                    model=self.config.model,
                    tokens_used=tokens_used,
                    duration=duration,
                    **extra
                )
            )

    def _publish_error_event(
        self,
        error: str,
        error_type: str,
        **extra
    ):
        """发布 LLM 错误事件"""
        if self.config.enable_events and self.event_bus:
            self.event_bus.publish(
                llm_error_event(
                    provider=self.config.provider,
                    model=self.config.model,
                    error=error,
                    error_type=error_type,
                    **extra
                )
            )

    def _execute_with_protection(
        self,
        func,
        extract_tokens: callable = None
    ) -> Any:
        """带 Circuit Breaker 和事件发布的执行"""
        start_time = time.time()
        
        try:
            if self.circuit_breaker:
                result = self.circuit_breaker.execute(func)
            else:
                result = func()
            
            # 提取 token 数量（如果有回调）
            tokens = 0
            if extract_tokens and result:
                tokens = extract_tokens(result)
            
            # 发布成功事件
            self._publish_success_event(
                duration=time.time() - start_time,
                tokens_used=tokens
            )
            
            return result
            
        except Exception as e:
            # 转换异常
            if isinstance(e, LuminaError):
                converted = e
            else:
                converted = self._convert_exception(e)
            
            # 发布错误事件
            self._publish_error_event(
                error=str(converted),
                error_type=type(converted).__name__
            )
            
            raise converted

    def _retry_call(self, func, *args, **kwargs):
        """带重试机制的调用（增强异常）"""
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                _log_llm(
                    f"provider={self.config.provider} model={self.config.model} attempt={attempt + 1}/{self.config.max_retries} failed: {e}",
                    level="ERROR"
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        
        _log_llm(
            f"provider={self.config.provider} model={self.config.model} exhausted retries: {last_error}",
            level="ERROR"
        )
        
        # 使用新异常体系
        if isinstance(last_error, LuminaError):
            raise last_error
        
        raise self._convert_exception(last_error)


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容协议 Provider（支持 Ollama、llama.cpp、DeepSeek、百炼、火山引擎、Kimi、智谱 GLM 等）"""

    def __init__(
        self,
        config: LLMConfig,
        circuit_breaker: CircuitBreaker = None,
        event_bus: EventBus = None
    ):
        super().__init__(config, circuit_breaker, event_bus)
        try:
            import openai
            # 确保 base_url 以 /v1 结尾（对于兼容 API）
            base_url = config.base_url
            if base_url and not base_url.endswith("/v1"):
                # 对于 Ollama，我们需要保持原样，因为它的 /v1 是必需的
                # 对于其他 provider，如果没有 /v1，我们保留原样
                pass
            self.client = openai.OpenAI(
                api_key=config.api_key or "dummy",  # Ollama/llamacpp 不需要 key
                base_url=base_url,
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

    def complete(self, prompt: str, **kwargs) -> str:
        """调用 OpenAI 兼容 API（带 Circuit Breaker 保护）"""
        def _call():
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            return response
        
        def extract_tokens(response):
            try:
                return response.usage.total_tokens if hasattr(response, 'usage') else 0
            except Exception:
                return 0
        
        response = self._execute_with_protection(
            lambda: self._retry_call(_call),
            extract_tokens=extract_tokens
        )
        return response.choices[0].message.content

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式调用 OpenAI 兼容 API"""
        def _call():
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            return response
        
        # Stream 不经过 Circuit Breaker（因为是迭代器）
        response = self._retry_call(_call)
        
        start_time = time.time()
        tokens_used = 0
        content_chunks = []
        
        try:
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    content_chunks.append(text)
                    yield text
                    tokens_used += len(text) // 4  # 粗略估计
        finally:
            # 发布事件
            self._publish_success_event(
                duration=time.time() - start_time,
                tokens_used=tokens_used
            )


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI 协议 Provider"""
    pass


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama 本地模型 Provider"""
    pass


class LlamaCppProvider(OpenAICompatibleProvider):
    """llama.cpp 本地模型 Provider"""
    pass


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek Provider"""
    pass


class BailianProvider(OpenAICompatibleProvider):
    """阿里云百炼（DashScope）Provider"""
    pass


class VolcEngineProvider(OpenAICompatibleProvider):
    """火山引擎（火山方舟）Provider"""
    pass


class KimiProvider(OpenAICompatibleProvider):
    """Kimi（月之暗面）Provider"""
    pass


class GlmProvider(OpenAICompatibleProvider):
    """智谱 GLM Provider"""
    pass


class AnthropicProvider(BaseLLMProvider):
    """Anthropic 协议 Provider - 使用原生 SDK 以支持真正的流式"""

    def __init__(
        self,
        config: LLMConfig,
        circuit_breaker: CircuitBreaker = None,
        event_bus: EventBus = None
    ):
        super().__init__(config, circuit_breaker, event_bus)
        try:
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except ImportError:
            # 回退到 requests 实现
            _log_llm("Anthropic SDK not found, falling back to requests implementation", level="WARN")
            self.client = None
            self.base_url = config.base_url.rstrip("/")
            if not self.base_url.endswith("/v1"):
                self.base_url = f"{self.base_url}/v1"

    def complete(self, prompt: str, **kwargs) -> str:
        """调用 Anthropic API（带 Circuit Breaker 保护）"""
        if self.client:
            return self._complete_with_sdk(prompt, **kwargs)
        else:
            return self._complete_with_requests(prompt, **kwargs)

    def _complete_with_sdk(self, prompt: str, **kwargs) -> str:
        """使用官方 SDK 完成请求"""
        def _call():
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            content = response.content
            text = "".join(
                item.text for item in content if hasattr(item, 'text')
            ).strip()
            if not text:
                raise LLMResponseError(f"Anthropic response missing text content: {response}")
            
            # 返回 tuple (text, usage)
            usage = response.usage if hasattr(response, 'usage') else None
            return text, usage
        
        def extract_tokens(result):
            text, usage = result
            if usage and hasattr(usage, 'total_tokens'):
                return usage.total_tokens
            return 0
        
        text, _ = self._execute_with_protection(
            lambda: self._retry_call(_call),
            extract_tokens=extract_tokens
        )
        return text

    def _complete_with_requests(self, prompt: str, **kwargs) -> str:
        """使用 requests 完成请求（备用方案）"""
        def _call():
            response = self._request(prompt, **kwargs)
            content = response.get("content", [])
            text = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            ).strip()
            if not text:
                raise LLMResponseError(f"Anthropic response missing text content: {response}")
            return text
        
        return self._execute_with_protection(
            lambda: self._retry_call(_call)
        )

    def _request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """使用 requests 进行非流式请求"""
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        response = requests.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        return response.json()

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式调用 Anthropic API - 真正的流式实现"""
        if self.client:
            yield from self._stream_with_sdk(prompt, **kwargs)
        else:
            yield from self._stream_with_requests(prompt, **kwargs)

    def _stream_with_sdk(self, prompt: str, **kwargs) -> Iterator[str]:
        """使用官方 SDK 进行流式请求"""
        def _call():
            return self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                **kwargs
            )

        stream = self._retry_call(_call)
        
        start_time = time.time()
        tokens_used = 0
        
        try:
            for event in stream:
                if event.type == 'content_block_delta':
                    if hasattr(event.delta, 'text'):
                        text = event.delta.text
                        yield text
                        tokens_used += len(text) // 4
        finally:
            self._publish_success_event(
                duration=time.time() - start_time,
                tokens_used=tokens_used
            )

    def _stream_with_requests(self, prompt: str, **kwargs) -> Iterator[str]:
        """使用 requests 进行流式请求（备用方案）"""
        def _call():
            headers = {
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "accept": "text/event-stream",
            }
            payload = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **kwargs,
            }
            response = requests.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
                stream=True,
            )
            response.raise_for_status()
            return response

        response = self._retry_call(_call)
        
        start_time = time.time()
        tokens_used = 0
        
        try:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type")
                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield text
                                    tokens_used += len(text) // 4
                    except json.JSONDecodeError:
                        continue
        finally:
            self._publish_success_event(
                duration=time.time() - start_time,
                tokens_used=tokens_used
            )


class LLMProviderFactory:
    """LLM Provider 工厂"""

    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "llamacpp": LlamaCppProvider,
        "deepseek": DeepSeekProvider,
        "bailian": BailianProvider,
        "volcengine": VolcEngineProvider,
        "kimi": KimiProvider,
        "glm": GlmProvider,
    }

    @classmethod
    def register(cls, name: str, provider_class: type):
        """注册自定义 Provider"""
        cls._providers[name] = provider_class

    @classmethod
    def create(
        cls,
        config: LLMConfig,
        circuit_breaker: CircuitBreaker = None,
        event_bus: EventBus = None
    ) -> BaseLLMProvider:
        """创建 Provider 实例"""
        if config.provider not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown LLM provider: {config.provider}. Available: {available}")

        return cls._providers[config.provider](config, circuit_breaker, event_bus)

    @classmethod
    def list_providers(cls) -> Dict[str, str]:
        """列出所有可用的 Provider"""
        descriptions = {
            "openai": "OpenAI (GPT-4, GPT-3.5)",
            "anthropic": "Anthropic (Claude 3, Claude 2)",
            "ollama": "Ollama - 本地模型 (Llama 3, Mistral, Gemma 等)",
            "llamacpp": "llama.cpp - 本地模型 (直接运行 gguf 模型)",
            "deepseek": "DeepSeek - 深度求索",
            "bailian": "百炼 - 阿里云 (Qwen 通义千问)",
            "volcengine": "火山引擎 - 火山方舟",
            "kimi": "Kimi - 月之暗面",
            "glm": "智谱 GLM - 智谱 AI",
        }
        return {
            name: descriptions.get(name, provider.__doc__ or name)
            for name, provider in cls._providers.items()
        }

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """获取 provider 的默认模型"""
        defaults = {
            "openai": "gpt-4",
            "anthropic": "claude-3-opus-20240229",
            "ollama": "llama3",
            "llamacpp": "llama-3-8b-instruct",
            "deepseek": "deepseek-chat",
            "bailian": "qwen-max",
            "volcengine": "ep-2024...",  # 用户需要创建自己的 endpoint
            "kimi": "moonshot-v1-8k",
            "glm": "glm-4",
        }
        return defaults.get(provider, "gpt-4")


def get_llm_provider(
    config: Dict[str, Any],
    circuit_breaker: CircuitBreaker = None,
    event_bus: EventBus = None
) -> BaseLLMProvider:
    """便捷函数：从配置字典创建 Provider"""
    provider = config.get("provider", "openai")
    # 如果只指定了 provider 但没指定 model，使用该 provider 的默认模型
    model = config.get("model")
    if not model:
        model = LLMProviderFactory.get_default_model(provider)

    llm_config = LLMConfig(
        provider=provider,
        base_url=config.get("base_url"),
        api_key=config.get("api_key"),
        model=model,
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 2000),
        timeout=config.get("timeout", 60),
        max_retries=config.get("max_retries", 3),
        retry_delay=config.get("retry_delay", 1.0),
        enable_circuit_breaker=config.get("enable_circuit_breaker", True),
        enable_events=config.get("enable_events", True),
    )
    return LLMProviderFactory.create(llm_config, circuit_breaker, event_bus)
