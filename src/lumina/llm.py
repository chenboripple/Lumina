"""
Lumina LLM Provider - 可配置的 LLM 集成
支持 OpenAI 和 Anthropic 协议
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Iterator, List
from dataclasses import dataclass
import json
import requests


def _log_llm(message: str, level: str = "INFO"):
    """输出 LLM 请求日志"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] LLM: {message}")


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = "openai"  # openai | anthropic
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
        }
        return defaults.get(self.provider, "")
    
    def validate(self) -> List[str]:
        """验证配置有效性"""
        errors = []
        if not self.api_key:
            errors.append(f"Missing api_key for {self.provider} (set it in ~/.lumina/lumina.yaml)")
        if not self.base_url:
            errors.append(f"Missing base_url for {self.provider}")
        return errors
    
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
        errors = config.validate()
        if errors:
            raise ValueError(f"LLM config invalid: {'; '.join(errors)}")
    
    @abstractmethod
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


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 协议 Provider"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout,
            )
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    def complete(self, prompt: str, **kwargs) -> str:
        """调用 OpenAI API"""
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
        """流式调用 OpenAI API"""
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
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicProvider(BaseLLMProvider):
    """Anthropic 协议 Provider"""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

    def _request(self, prompt: str, **kwargs) -> Dict[str, Any]:
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
    
    def complete(self, prompt: str, **kwargs) -> str:
        """调用 Anthropic API"""
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
    
    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """流式调用 Anthropic API"""
        yield self.complete(prompt, **kwargs)


class LLMProviderFactory:
    """LLM Provider 工厂"""
    
    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
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
        return {
            name: provider.__doc__ or name
            for name, provider in cls._providers.items()
        }


def get_llm_provider(config: Dict[str, Any]) -> BaseLLMProvider:
    """便捷函数：从配置字典创建 Provider"""
    llm_config = LLMConfig(
        provider=config.get("provider", "openai"),
        base_url=config.get("base_url"),
        api_key=config.get("api_key"),
        model=config.get("model", "gpt-4"),
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 2000),
        timeout=config.get("timeout", 60),
        max_retries=config.get("max_retries", 3),
        retry_delay=config.get("retry_delay", 1.0),
    )
    return LLMProviderFactory.create(llm_config)