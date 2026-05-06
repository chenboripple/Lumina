"""
Lumina LLM Provider - 可配置的 LLM 集成
支持 OpenAI、Anthropic、国内 API（DeepSeek、百炼、火山引擎、Kimi、智谱）及本地模型（Ollama/llama.cpp）
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Iterator, List
from dataclasses import dataclass
import json
import requests


from .utils.logging import get_logger, timed

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
    """LLM Provider 抽象基类"""

    def __init__(self, config: LLMConfig):
        self.config = config
        # 如果 api_key 为空但有环境变量，尝试从环境变量加载
        if not self.config.api_key and self.config.provider not in ["ollama", "llamacpp"]:
            env_key = self.config._get_env_key_name()
            if env_key and os.environ.get(env_key):
                self.config.api_key = os.environ.get(env_key)
        errors = config.validate()
        if errors:
            raise ValueError(f"LLM config invalid: {'; '.join(errors)}")

    @abstractmethod
    @timed
    def complete(self, prompt: str, **kwargs) -> str:
        """同步完成请求"""
        pass

    @abstractmethod
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式完成请求"""
        pass

    def _retry_call(self, func, *args, **kwargs):
        """带重试机制的调用"""
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
        raise RuntimeError(f"LLM call failed after {self.config.max_retries} retries: {last_error}")


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI 兼容协议 Provider（支持 Ollama、llama.cpp、DeepSeek、百炼、火山引擎、Kimi、智谱 GLM 等）"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
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
        """调用 OpenAI 兼容 API"""
        def _call():
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            return response.choices[0].message.content

        return self._retry_call(_call)

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

        response = self._retry_call(_call)
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


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

    def __init__(self, config: LLMConfig):
        super().__init__(config)
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
        """调用 Anthropic API"""
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
                raise ValueError(f"Anthropic response missing text content: {response}")
            return text

        return self._retry_call(_call)

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
                raise ValueError(f"Anthropic response missing text content: {response}")
            return text

        return self._retry_call(_call)

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
        for event in stream:
            if event.type == 'content_block_delta':
                if hasattr(event.delta, 'text'):
                    yield event.delta.text

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
                except json.JSONDecodeError:
                    continue


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
    def create(cls, config: LLMConfig) -> BaseLLMProvider:
        """创建 Provider 实例"""
        if config.provider not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown LLM provider: {config.provider}. Available: {available}")

        return cls._providers[config.provider](config)

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


def get_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider:
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
    )
    return LLMProviderFactory.create(llm_config)
