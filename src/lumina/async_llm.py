"""
Async LLM Provider - 异步 LLM 调用模块
基于 asyncio + aiohttp 实现高并发 LLM 调用
"""
import asyncio
import time
from typing import Dict, Any, Optional, Iterator, List, AsyncIterator
from dataclasses import dataclass
import json

from .exceptions import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMAPIError,
    LLMResponseError,
    ErrorContext,
)
from .utils.logging import get_logger
from .llm import LLMConfig, BaseLLMProvider

logger = get_logger("lumina.async_llm")


@dataclass
class AsyncLLMResult:
    """异步 LLM 调用结果"""
    text: str
    provider: str
    model: str
    duration: float
    tokens_used: int = 0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AsyncLLMProvider:
    """异步 LLM Provider 基类"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider_name = config.provider
        self.model = config.model
        self._session = None
        self._semaphore = None
    
    async def _get_session(self):
        """获取 aiohttp session（延迟初始化）"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session
    
    async def _get_semaphore(self):
        """获取信号量（限制并发）"""
        if self._semaphore is None:
            # 默认限制并发数为 5
            self._semaphore = asyncio.Semaphore(5)
        return self._semaphore
    
    async def complete(self, prompt: str, **kwargs) -> AsyncLLMResult:
        """异步完成请求"""
        raise NotImplementedError
    
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """异步流式请求"""
        raise NotImplementedError
    
    async def batch_complete(
        self,
        prompts: List[str],
        max_concurrent: int = 5,
        **kwargs
    ) -> List[AsyncLLMResult]:
        """
        批量异步完成请求
        
        Args:
            prompts: 提示词列表
            max_concurrent: 最大并发数
            **kwargs: 额外参数
            
        Returns:
            结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _single_call(prompt: str) -> AsyncLLMResult:
            async with semaphore:
                return await self.complete(prompt, **kwargs)
        
        tasks = [_single_call(p) for p in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Async batch call {i} failed: {result}")
                processed_results.append(AsyncLLMResult(
                    text=f"[Error: {str(result)}]",
                    provider=self.provider_name,
                    model=self.model,
                    duration=0.0,
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def close(self) -> None:
        """关闭 session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def __del__(self):
        """析构时关闭 session"""
        if self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass


class AsyncOpenAICompatibleProvider(AsyncLLMProvider):
    """异步 OpenAI 兼容协议 Provider"""
    
    async def complete(self, prompt: str, **kwargs) -> AsyncLLMResult:
        """异步调用 OpenAI 兼容 API"""
        start_time = time.time()
        
        try:
            import aiohttp
            
            session = await self._get_session()
            semaphore = await self._get_semaphore()
            
            async with semaphore:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key or 'dummy'}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    **kwargs
                }
                
                async with session.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 429:
                        raise LLMRateLimitError(
                            "Rate limit exceeded",
                            retry_after=60,
                            context=ErrorContext(
                                provider=self.provider_name,
                                model=self.model,
                                operation="complete",
                            )
                        )
                    
                    if response.status == 401:
                        raise LLMAuthenticationError(
                            "Authentication failed",
                            context=ErrorContext(
                                provider=self.provider_name,
                                model=self.model,
                                operation="complete",
                            )
                        )
                    
                    if response.status >= 400:
                        text = await response.text()
                        raise LLMAPIError(
                            f"API error: {response.status} - {text}",
                            status_code=response.status,
                            context=ErrorContext(
                                provider=self.provider_name,
                                model=self.model,
                                operation="complete",
                            )
                        )
                    
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        raise LLMResponseError(
                            "Empty response from API",
                            context=ErrorContext(
                                provider=self.provider_name,
                                model=self.model,
                                operation="complete",
                            )
                        )
                    
                    text = data["choices"][0].get("message", {}).get("content", "")
                    
                    usage = data.get("usage", {})
                    duration = time.time() - start_time
                    
                    return AsyncLLMResult(
                        text=text,
                        provider=self.provider_name,
                        model=self.model,
                        duration=duration,
                        tokens_used=usage.get("total_tokens", 0),
                        tokens_prompt=usage.get("prompt_tokens", 0),
                        tokens_completion=usage.get("completion_tokens", 0),
                        metadata={
                            "finish_reason": data["choices"][0].get("finish_reason"),
                            "response_id": data.get("id"),
                        }
                    )
        
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"LLM request timed out after {self.config.timeout}s",
                timeout_seconds=self.config.timeout,
                context=ErrorContext(
                    provider=self.provider_name,
                    model=self.model,
                    operation="complete",
                )
            )
        
        except (LLMRateLimitError, LLMAuthenticationError, LLMAPIError, LLMResponseError):
            raise
        
        except Exception as e:
            raise LLMError(
                f"Unexpected error: {str(e)}",
                context=ErrorContext(
                    provider=self.provider_name,
                    model=self.model,
                    operation="complete",
                )
            )
    
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """异步流式调用"""
        try:
            import aiohttp
            
            session = await self._get_session()
            semaphore = await self._get_semaphore()
            
            async with semaphore:
                headers = {
                    "Authorization": f"Bearer {self.config.api_key or 'dummy'}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                    "stream": True,
                    **kwargs
                }
                
                async with session.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise LLMAPIError(
                            f"Stream API error: {response.status} - {text}",
                            status_code=response.status,
                        )
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and data["choices"]:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"LLM stream timed out after {self.config.timeout}s",
                timeout_seconds=self.config.timeout,
            )
        
        except Exception as e:
            raise LLMError(f"Stream error: {str(e)}")


class AsyncAnthropicProvider(AsyncLLMProvider):
    """异步 Anthropic Provider"""
    
    async def complete(self, prompt: str, **kwargs) -> AsyncLLMResult:
        """异步调用 Anthropic API"""
        start_time = time.time()
        
        try:
            import aiohttp
            
            session = await self._get_session()
            semaphore = await self._get_semaphore()
            
            async with semaphore:
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
                    **kwargs
                }
                
                async with session.post(
                    f"{self.config.base_url}/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status == 429:
                        raise LLMRateLimitError(
                            "Rate limit exceeded",
                            retry_after=60,
                        )
                    
                    if response.status == 401:
                        raise LLMAuthenticationError("Authentication failed")
                    
                    if response.status >= 400:
                        text = await response.text()
                        raise LLMAPIError(
                            f"API error: {response.status} - {text}",
                            status_code=response.status,
                        )
                    
                    data = await response.json()
                    
                    content = data.get("content", [])
                    text = "".join(
                        item.get("text", "")
                        for item in content
                        if isinstance(item, dict)
                    ).strip()
                    
                    if not text:
                        raise LLMResponseError("Empty response from Anthropic API")
                    
                    duration = time.time() - start_time
                    
                    return AsyncLLMResult(
                        text=text,
                        provider=self.provider_name,
                        model=self.model,
                        duration=duration,
                        tokens_used=data.get("usage", {}).get("input_tokens", 0) + 
                                       data.get("usage", {}).get("output_tokens", 0),
                        tokens_prompt=data.get("usage", {}).get("input_tokens", 0),
                        tokens_completion=data.get("usage", {}).get("output_tokens", 0),
                    )
        
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"LLM request timed out after {self.config.timeout}s",
                timeout_seconds=self.config.timeout,
            )
        
        except (LLMRateLimitError, LLMAuthenticationError, LLMAPIError, LLMResponseError):
            raise
        
        except Exception as e:
            raise LLMError(f"Unexpected error: {str(e)}")
    
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """异步流式调用"""
        try:
            import aiohttp
            
            session = await self._get_session()
            semaphore = await self._get_semaphore()
            
            async with semaphore:
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
                    **kwargs
                }
                
                async with session.post(
                    f"{self.config.base_url}/messages",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise LLMAPIError(
                            f"Stream API error: {response.status} - {text}",
                            status_code=response.status,
                        )
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
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
        
        except asyncio.TimeoutError:
            raise LLMTimeoutError(
                f"LLM stream timed out after {self.config.timeout}s",
                timeout_seconds=self.config.timeout,
            )
        
        except Exception as e:
            raise LLMError(f"Stream error: {str(e)}")


class AsyncLLMProviderFactory:
    """异步 LLM Provider 工厂"""
    
    _providers = {
        "openai": AsyncOpenAICompatibleProvider,
        "anthropic": AsyncAnthropicProvider,
        "ollama": AsyncOpenAICompatibleProvider,
        "llamacpp": AsyncOpenAICompatibleProvider,
        "deepseek": AsyncOpenAICompatibleProvider,
        "bailian": AsyncOpenAICompatibleProvider,
        "volcengine": AsyncOpenAICompatibleProvider,
        "kimi": AsyncOpenAICompatibleProvider,
        "glm": AsyncOpenAICompatibleProvider,
    }
    
    @classmethod
    def create(cls, config: LLMConfig) -> AsyncLLMProvider:
        """创建异步 Provider"""
        if config.provider not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider: {config.provider}. Available: {available}")
        
        return cls._providers[config.provider](config)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有可用 Provider"""
        return list(cls._providers.keys())


# ==================== 便捷函数 ====================

def get_async_llm_provider(config: Dict[str, Any]) -> AsyncLLMProvider:
    """从配置创建异步 Provider"""
    provider = config.get("provider", "openai")
    llm_config = LLMConfig(
        provider=provider,
        base_url=config.get("base_url"),
        api_key=config.get("api_key"),
        model=config.get("model", "gpt-4"),
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 2000),
        timeout=config.get("timeout", 60),
        max_retries=config.get("max_retries", 3),
        retry_delay=config.get("retry_delay", 1.0),
    )
    return AsyncLLMProviderFactory.create(llm_config)


async def async_complete(prompt: str, config: Dict[str, Any], **kwargs) -> AsyncLLMResult:
    """便捷函数：异步完成请求"""
    provider = get_async_llm_provider(config)
    try:
        result = await provider.complete(prompt, **kwargs)
        return result
    finally:
        await provider.close()


async def async_batch_complete(
    prompts: List[str],
    config: Dict[str, Any],
    max_concurrent: int = 5,
    **kwargs
) -> List[AsyncLLMResult]:
    """便捷函数：批量异步完成请求"""
    provider = get_async_llm_provider(config)
    try:
        results = await provider.batch_complete(prompts, max_concurrent=max_concurrent, **kwargs)
        return results
    finally:
        await provider.close()
