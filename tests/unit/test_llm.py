"""
LLM 模块单元测试
测试 LLMConfig、Provider 工厂、各种 LLM 提供程序
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestLLMConfig:
    """LLMConfig 配置类测试"""

    def test_default_config(self):
        """测试默认配置"""
        from lumina.llm import LLMConfig
        config = LLMConfig()

        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.api_key is None
        assert config.model == "gpt-4"
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_custom_config(self):
        """测试自定义配置"""
        from lumina.llm import LLMConfig
        config = LLMConfig(
            provider="anthropic",
            base_url="https://custom.example.com",
            api_key="test-key",
            model="claude-3-opus",
            temperature=0.5,
            max_tokens=4000,
            timeout=120,
            max_retries=5,
            retry_delay=2.0
        )

        assert config.provider == "anthropic"
        assert config.base_url == "https://custom.example.com"
        assert config.api_key == "test-key"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.5
        assert config.max_tokens == 4000
        assert config.timeout == 120
        assert config.max_retries == 5
        assert config.retry_delay == 2.0

    def test_to_dict(self):
        """测试转换为字典（排除敏感信息）"""
        from lumina.llm import LLMConfig
        config = LLMConfig(
            provider="openai",
            api_key="secret-key",
            model="gpt-4"
        )
        d = config.to_dict()

        assert "provider" in d
        assert "model" in d
        # api_key 不应该出现在字典中
        assert "api_key" not in d

    def test_provider_default_base_urls(self):
        """测试各个 provider 的默认 base_url"""
        from lumina.llm import LLMConfig

        providers = [
            ("openai", "https://api.openai.com/v1"),
            ("anthropic", "https://api.anthropic.com"),
            ("ollama", "http://localhost:11434/v1"),
            ("llamacpp", "http://localhost:8080/v1"),
            ("deepseek", "https://api.deepseek.com/v1"),
            ("bailian", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ("volcengine", "https://ark.cn-beijing.volces.com/api/v3"),
            ("kimi", "https://api.moonshot.cn/v1"),
            ("glm", "https://open.bigmodel.cn/api/paas/v4"),
        ]

        for provider, expected_url in providers:
            config = LLMConfig(provider=provider)
            assert config.base_url == expected_url


class TestLLMProviderFactory:
    """LLMProvider 工厂测试"""

    def test_create_provider_openai(self):
        """测试创建 OpenAI provider"""
        from lumina.llm import LLMProviderFactory, LLMConfig, OpenAIProvider
        config = LLMConfig(provider="openai", api_key="test-key")
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, OpenAIProvider)

    def test_create_provider_ollama(self):
        """测试创建 Ollama provider"""
        from lumina.llm import LLMProviderFactory, LLMConfig, OllamaProvider
        config = LLMConfig(provider="ollama", model="llama3")
        provider = LLMProviderFactory.create(config)
        assert isinstance(provider, OllamaProvider)

    def test_create_provider_unknown_raises(self):
        """测试未知 provider 抛异常"""
        from lumina.llm import LLMProviderFactory, LLMConfig
        config = LLMConfig(provider="unknown-provider")
        with pytest.raises(ValueError):
            LLMProviderFactory.create(config)


class TestOpenAICompatibleProvider:
    """OpenAI 兼容协议 Provider 测试"""

    @pytest.fixture
    def config(self):
        from lumina.llm import LLMConfig
        return LLMConfig(
            provider="ollama",
            base_url="http://localhost:11434/v1",
            api_key="dummy",
            model="llama3"
        )

    def test_provider_init(self, config):
        """测试 provider 初始化"""
        from lumina.llm import OpenAICompatibleProvider

        with patch('openai.OpenAI') as mock_openai_ctor:
            mock_client = MagicMock()
            mock_openai_ctor.return_value = mock_client

            provider = OpenAICompatibleProvider(config)

            mock_openai_ctor.assert_called_once()
            assert provider.config == config

    def test_complete_success(self, config):
        """测试成功完成请求"""
        from lumina.llm import OpenAICompatibleProvider

        with patch('openai.OpenAI') as mock_openai_ctor:
            # Setup mock response
            mock_client = MagicMock()
            mock_openai_ctor.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
            mock_client.chat.completions.create.return_value = mock_response

            provider = OpenAICompatibleProvider(config)
            result = provider.complete("Hello world")

            assert result == "Test response"

    def test_stream(self, config):
        """测试流式输出"""
        from lumina.llm import OpenAICompatibleProvider

        with patch('openai.OpenAI') as mock_openai_ctor:
            # Setup mock stream response
            mock_client = MagicMock()
            mock_openai_ctor.return_value = mock_client

            # Mock streaming chunks
            chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))])
            chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content="world"))])
            chunk3 = MagicMock(choices=[MagicMock(delta=MagicMock(content=None))])
            mock_client.chat.completions.create.return_value = [chunk1, chunk2, chunk3]

            provider = OpenAICompatibleProvider(config)
            chunks = list(provider.stream("Hello"))

            assert chunks == ["Hello ", "world"]

    def test_retry_logic(self, config):
        """测试重试逻辑"""
        from lumina.llm import OpenAICompatibleProvider

        with patch('openai.OpenAI') as mock_openai_ctor:
            mock_client = MagicMock()
            mock_openai_ctor.return_value = mock_client

            # First calls fail, last succeeds
            call_count = [0]
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise Exception("API timeout")
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Success"))]
                return mock_response

            mock_client.chat.completions.create.side_effect = side_effect

            provider = OpenAICompatibleProvider(config)
            result = provider.complete("Retry test")

            assert result == "Success"
            assert call_count[0] == 3

    def test_max_retries_exhausted(self, config):
        """测试重试耗尽"""
        from lumina.llm import OpenAICompatibleProvider

        with patch('openai.OpenAI') as mock_openai_ctor:
            mock_client = MagicMock()
            mock_openai_ctor.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("Always fails")

            provider = OpenAICompatibleProvider(config)
            with pytest.raises(RuntimeError):
                provider.complete("Will fail")


class TestUtils:
    """LLM 工具函数测试"""

    def test_backward_compatible_logging(self):
        """测试旧 _log_llm 函数（向后兼容）"""
        from lumina.llm import _log_llm

        # Just make sure it doesn't crash
        _log_llm("Test message")
        _log_llm("Test error", level="ERROR")

    def test_provider_labels_exist(self):
        """测试 provider 列表存在"""
        from lumina.llm import LLMProviderFactory

        providers = LLMProviderFactory.list_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "ollama" in providers
        assert "deepseek" in providers
