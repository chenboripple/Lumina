"""
测试新模块
- 异常体系
- 熔断器
- 事件总线
- Prompt 管理
- 异步 LLM
- 健康检查
"""
import pytest
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock

# 测试异常体系
def test_custom_exceptions():
    """测试自定义异常"""
    from lumina.exceptions import (
        LuminaError,
        LLMError,
        LLMRateLimitError,
        LLMTimeoutError,
        LLMAuthenticationError,
        FileReadError,
        SensitiveContentError,
        ErrorContext,
        rate_limit_error,
    )
    
    # 测试异常创建
    error = LuminaError("Test error")
    assert str(error) == "Test error"
    
    # 测试带 context 的异常
    context = ErrorContext(
        file_path="/test/file.txt",
        operation="read",
        provider="openai",
        model="gpt-4",
    )
    error = LLMError("Test LLM error", context=context)
    assert error.context.file_path == "/test/file.txt"
    
    # 测试便捷函数
    error = rate_limit_error("Too many requests", retry_after=60)
    assert isinstance(error, LLMRateLimitError)
    assert error.retry_after == 60
    
    print("✅ Custom exceptions work correctly")


def test_error_context():
    """测试错误上下文"""
    from lumina.exceptions import ErrorContext, LLMError
    
    context = ErrorContext(
        file_path="/test/file.txt",
        operation="generate",
        provider="openai",
        model="gpt-4",
        retries=3,
        metadata={"key": "value"},
    )
    
    error = LLMError("Test error", context=context)
    
    assert error.context.file_path == "/test/file.txt"
    assert error.context.operation == "generate"
    assert error.context.provider == "openai"
    assert error.context.model == "gpt-4"
    assert error.context.retries == 3
    assert error.context.metadata["key"] == "value"
    
    # 测试 to_dict
    error_dict = error.to_dict()
    assert error_dict["type"] == "LLMError"
    assert error_dict["message"] == "Test error"
    assert error_dict["context"]["file_path"] == "/test/file.txt"
    
    print("✅ Error context works correctly")


# 测试熔断器
def test_circuit_breaker_init():
    """测试熔断器初始化"""
    from lumina.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState
    
    config = CircuitBreakerConfig(
        failure_threshold=3,
        open_timeout_seconds=10.0,
    )
    
    cb = CircuitBreaker("test", config=config)
    
    assert cb.name == "test"
    assert cb.state == CircuitState.CLOSED
    assert cb.config.failure_threshold == 3
    
    print("✅ CircuitBreaker initialization works")


def test_circuit_breaker_success():
    """测试成功场景"""
    from lumina.circuit_breaker import CircuitBreaker, CircuitState
    
    cb = CircuitBreaker("test-success")
    
    result = cb.execute(lambda: "success")
    
    assert result == "success"
    assert cb.state == CircuitState.CLOSED
    assert cb.metrics.success_count == 1
    assert cb.metrics.consecutive_failures == 0
    
    print("✅ CircuitBreaker success flow works")


def test_circuit_breaker_failure_then_open():
    """测试失败场景并打开熔断器"""
    from lumina.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig
    
    config = CircuitBreakerConfig(
        failure_threshold=2,
        open_timeout_seconds=60.0,
    )
    
    cb = CircuitBreaker("test-failure", config=config)
    
    # 第一次失败
    try:
        cb.execute(lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    
    assert cb.state == CircuitState.CLOSED
    assert cb.metrics.failure_count == 1
    assert cb.metrics.consecutive_failures == 1
    
    # 第二次失败，应该打开
    try:
        cb.execute(lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    
    assert cb.state == CircuitState.OPEN
    assert cb.metrics.failure_count == 2
    assert cb.metrics.consecutive_failures == 2
    
    # 现在快速失败
    try:
        cb.execute(lambda: print("should not reach here"))
    except Exception as e:
        from lumina.exceptions import CircuitOpenError
        assert isinstance(e, CircuitOpenError)
    
    print("✅ CircuitBreaker opens on multiple failures")


def test_circuit_breaker_fallback():
    """测试降级策略"""
    from lumina.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
    
    config = CircuitBreakerConfig(
        failure_threshold=1,
        open_timeout_seconds=0.1,  # 快速恢复
        enable_fallback=True,
    )
    
    def fallback():
        return "fallback result"
    
    cb = CircuitBreaker("test-fallback", config=config, fallback=fallback)
    
    # 先失败一次打开
    try:
        cb.execute(lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    
    # 应该走降级
    result = cb.execute(lambda: "should not reach")
    assert result == "fallback result"
    
    print("✅ CircuitBreaker fallback works")


def test_circuit_breaker_decorator():
    """测试装饰器用法"""
    from lumina.circuit_breaker import circuit_break
    
    @circuit_break("decorator-test")
    def test_func(x):
        return x * 2
    
    assert test_func(5) == 10
    assert test_func(10) == 20
    
    print("✅ CircuitBreaker decorator works")


# 测试事件总线
def test_event_creation():
    """测试事件创建"""
    from lumina.event_bus import Event, EventPriority, EventTypes
    
    event = Event(
        event_type=EventTypes.FILE_SCANNED,
        payload={"file_path": "/test.txt"},
        source="test",
        priority=EventPriority.NORMAL,
    )
    
    assert event.event_type == EventTypes.FILE_SCANNED
    assert event.payload["file_path"] == "/test.txt"
    assert event.source == "test"
    assert event.priority == EventPriority.NORMAL
    
    # 测试 to_dict
    data = event.to_dict()
    assert data["event_type"] == EventTypes.FILE_SCANNED
    assert data["payload"]["file_path"] == "/test.txt"
    
    print("✅ Event creation works")


def test_event_bus_subscribe_publish():
    """测试订阅和发布"""
    from lumina.event_bus import EventBus, Event, EventTypes
    
    bus = EventBus()
    
    received_events = []
    
    def handler(event):
        received_events.append(event)
    
    bus.subscribe(EventTypes.FILE_SCANNED, handler)
    
    event = Event(
        event_type=EventTypes.FILE_SCANNED,
        payload={"file_path": "/test.txt"},
    )
    
    bus.publish(event)
    
    assert len(received_events) == 1
    assert received_events[0].event_type == EventTypes.FILE_SCANNED
    
    print("✅ EventBus subscribe/publish works")


def test_event_bus_wildcard():
    """测试通配符订阅"""
    from lumina.event_bus import EventBus, Event, EventTypes
    
    bus = EventBus()
    
    received_events = []
    
    def handler(event):
        received_events.append(event)
    
    bus.subscribe("*", handler)
    
    event1 = Event(event_type=EventTypes.FILE_SCANNED, payload={})
    event2 = Event(event_type=EventTypes.NOTE_CREATED, payload={})
    
    bus.publish(event1)
    bus.publish(event2)
    
    assert len(received_events) == 2
    assert received_events[0].event_type == EventTypes.FILE_SCANNED
    assert received_events[1].event_type == EventTypes.NOTE_CREATED
    
    print("✅ EventBus wildcard subscription works")


def test_event_bus_decorator():
    """测试装饰器"""
    from lumina.event_bus import EventBus, Event, EventTypes, on
    
    received_events = []
    
    @on(EventTypes.FILE_SCANNED)
    def handle_file_scanned(event):
        received_events.append(event)
    
    bus = EventBus()
    event = Event(event_type=EventTypes.FILE_SCANNED, payload={})
    
    bus.publish(event)
    
    assert len(received_events) == 1
    
    print("✅ EventBus decorator works")


def test_convenience_event_functions():
    """测试便捷事件创建函数"""
    from lumina.event_bus import (
        file_scanned_event,
        file_processed_event,
        file_failed_event,
        note_created_event,
        llm_success_event,
        llm_error_event,
        error_occurred_event,
        batch_progress_event,
    )
    
    # 测试文件扫描事件
    event = file_scanned_event("/test.txt", "markdown")
    assert event.payload["file_path"] == "/test.txt"
    assert event.payload["file_type"] == "markdown"
    
    # 测试文件处理成功事件
    event = file_processed_event("/test.txt", "/notes/test.md", 0.85)
    assert event.payload["file_path"] == "/test.txt"
    assert event.payload["note_path"] == "/notes/test.md"
    assert event.payload["score"] == 0.85
    
    # 测试文件处理失败事件
    event = file_failed_event("/test.txt", "Test error", "test_error")
    assert event.payload["file_path"] == "/test.txt"
    assert event.payload["error"] == "Test error"
    assert event.payload["error_type"] == "test_error"
    
    # 测试笔记创建事件
    event = note_created_event("/notes/test.md", "Test Note", ["test"])
    assert event.payload["note_path"] == "/notes/test.md"
    assert event.payload["title"] == "Test Note"
    assert event.payload["tags"] == ["test"]
    
    # 测试 LLM 成功事件
    event = llm_success_event("openai", "gpt-4", 100, 2.5)
    assert event.payload["provider"] == "openai"
    assert event.payload["model"] == "gpt-4"
    assert event.payload["tokens_used"] == 100
    assert event.payload["duration"] == 2.5
    
    # 测试 LLM 错误事件
    event = llm_error_event("openai", "gpt-4", "API error", "api_error")
    assert event.payload["provider"] == "openai"
    assert event.payload["model"] == "gpt-4"
    assert event.payload["error"] == "API error"
    
    # 测试错误事件
    event = error_occurred_event("test_error", "Test error", {"key": "value"})
    assert event.payload["error_type"] == "test_error"
    assert event.payload["message"] == "Test error"
    assert event.payload["context"]["key"] == "value"
    
    # 测试批处理进度事件
    event = batch_progress_event("batch1", 5, 10, 50.0)
    assert event.payload["batch_id"] == "batch1"
    assert event.payload["current"] == 5
    assert event.payload["total"] == 10
    assert event.payload["percentage"] == 50.0
    
    print("✅ Convenience event functions work")


# 测试 Prompt 管理
def test_prompt_template():
    """测试提示词模板"""
    from lumina.prompt_manager import PromptTemplate, PromptVariable
    
    template = PromptTemplate(
        name="test_template",
        description="Test template",
        content="Hello, {{name}}! You are {{age}} years old.",
        variables=[
            PromptVariable(name="name", required=True),
            PromptVariable(name="age", required=True, default_value="20"),
        ],
    )
    
    # 测试变量提取
    assert len(template.variables) == 2
    
    # 测试渲染
    result = template.render(name="Alice", age="30")
    assert result == "Hello, Alice! You are 30 years old."
    
    # 测试验证
    errors = template.validate(name="Alice", age="30")
    assert errors == {}
    
    # 测试缺少变量
    errors = template.validate(age="30")
    assert "name" in errors
    
    print("✅ PromptTemplate works")


def test_prompt_manager():
    """测试提示词管理器"""
    from lumina.prompt_manager import PromptManager, PromptTemplate
    
    pm = PromptManager()
    
    # 测试获取内置模板
    template = pm.get("default_extractor")
    assert template is not None
    assert "content" in template.content
    
    # 测试 list
    templates = pm.list_templates()
    assert len(templates) > 0
    
    # 测试渲染
    content = pm.render(
        "content_analyzer",
        file_path="/test.txt",
        file_type="markdown",
        content_preview="Hello world",
    )
    assert "Hello world" in content
    
    print("✅ PromptManager works")


def test_prompt_manager_score():
    """测试评分功能"""
    from lumina.prompt_manager import PromptManager
    
    pm = PromptManager()
    
    pm.score_template("default_extractor", 0.9, "Good result", is_positive=True)
    pm.score_template("default_extractor", 0.8, "Also good", is_positive=True)
    pm.score_template("default_extractor", 0.3, "Bad result", is_positive=False)
    
    assert pm._scores is not None
    
    print("✅ PromptManager scoring works")


# 测试健康检查
def test_health_checker_init():
    """测试健康检查器初始化"""
    from lumina.health_check import HealthChecker, HealthStatus
    
    hc = HealthChecker()
    
    report = hc.check_all()
    assert report is not None
    assert hasattr(report, 'overall_status')
    assert hasattr(report, 'components')
    assert len(report.components) > 0
    
    print("✅ HealthChecker initialization works")


def test_health_report():
    """测试健康报告"""
    from lumina.health_check import HealthChecker, HealthStatus, HealthReport
    
    hc = HealthChecker()
    report = hc.check_all()
    
    data = report.to_dict()
    assert "status" in data
    assert "timestamp" in data
    assert "uptime" in data
    assert "components" in data
    assert len(data["components"]) > 0
    
    print("✅ HealthReport works")


def test_health_status_enum():
    """测试健康状态枚举"""
    from lumina.health_check import HealthStatus
    
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.WARNING.value == "warning"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    assert HealthStatus.UNKNOWN.value == "unknown"
    
    print("✅ HealthStatus enum works")


def test_component_check():
    """测试组件检查"""
    from lumina.health_check import ComponentCheck, HealthStatus
    
    check = ComponentCheck(
        name="test.component",
        status=HealthStatus.HEALTHY,
        message="OK",
        response_time=0.123,
    )
    
    data = check.to_dict()
    assert data["name"] == "test.component"
    assert data["status"] == "healthy"
    assert data["message"] == "OK"
    assert data["response_time"] == 0.123
    
    print("✅ ComponentCheck works")


# 测试异步 LLM（需要 mock）
def test_async_llm_config():
    """测试异步 LLM 配置"""
    from lumina.async_llm import AsyncLLMResult
    
    result = AsyncLLMResult(
        text="Hello world",
        provider="openai",
        model="gpt-4",
        duration=1.5,
        tokens_used=100,
    )
    
    assert result.text == "Hello world"
    assert result.provider == "openai"
    assert result.model == "gpt-4"
    assert result.duration == 1.5
    assert result.tokens_used == 100
    
    print("✅ AsyncLLMResult works")


@pytest.mark.asyncio
async def test_async_llm_factory():
    """测试异步 LLM 工厂"""
    from lumina.async_llm import AsyncLLMProviderFactory
    from lumina.llm import LLMConfig
    
    config = LLMConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="llama3",
    )
    
    # 测试工厂能创建
    provider_class = AsyncLLMProviderFactory._providers.get(config.provider)
    assert provider_class is not None
    
    print("✅ AsyncLLMProviderFactory works")


# 运行所有测试
if __name__ == "__main__":
    print("🧪 Running all new module tests...\n")
    
    test_custom_exceptions()
    test_error_context()
    test_circuit_breaker_init()
    test_circuit_breaker_success()
    test_circuit_breaker_failure_then_open()
    test_circuit_breaker_fallback()
    test_circuit_breaker_decorator()
    test_event_creation()
    test_event_bus_subscribe_publish()
    test_event_bus_wildcard()
    test_event_bus_decorator()
    test_convenience_event_functions()
    test_prompt_template()
    test_prompt_manager()
    test_prompt_manager_score()
    test_health_checker_init()
    test_health_report()
    test_health_status_enum()
    test_component_check()
    test_async_llm_config()
    
    print("\n✅ All tests passed!")
