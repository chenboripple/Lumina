"""
Lumina - 本地文件知识提取与结构化笔记生成系统

核心模块:
- exceptions: 自定义异常体系
- circuit_breaker: 熔断器模式
- event_bus: 事件总线
- prompt_manager: 提示词管理
- async_llm: 异步 LLM 调用
- health_check: 健康检查
"""
from .exceptions import (
    LuminaError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMAPIError,
    LLMResponseError,
    FileProcessingError,
    FileReadError,
    FileWriteError,
    FilePermissionError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ContentFilterError,
    SensitiveContentError,
    LowValueContentError,
    ConfigError,
    ConfigValidationError,
    ConfigMissingError,
    CacheError,
    CacheReadError,
    CacheWriteError,
    VectorStoreError,
    VectorIndexError,
    VectorSearchError,
    HistoryError,
    HistoryReadError,
    HistoryWriteError,
    TaskError,
    TaskQueueError,
    TaskTimeoutError,
    TaskCancelledError,
    CircuitBreakerError,
    CircuitOpenError,
    CircuitHalfOpenError,
    ErrorContext,
    rate_limit_error,
    timeout_error,
    auth_error,
    api_error,
    file_read_error,
    file_write_error,
    sensitive_content_error,
    config_error,
    missing_config_error,
    circuit_open_error,
)

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitMetrics,
    circuit_break,
    llm_circuit_break,
)

from .event_bus import (
    EventBus,
    Event,
    EventPriority,
    EventTypes,
    on,
    emit,
    publish,
    publish_async,
    subscribe,
    unsubscribe,
    start_worker,
    stop_worker,
    file_scanned_event,
    file_processed_event,
    file_failed_event,
    note_created_event,
    llm_success_event,
    llm_error_event,
    error_occurred_event,
    batch_progress_event,
)

from .prompt_manager import (
    PromptManager,
    PromptTemplate,
    PromptVariable,
    PromptVersion,
    PromptScore,
    get_prompt_manager,
    render_template,
    get_template,
    list_templates,
    save_template,
    score_template,
)

from .async_llm import (
    AsyncLLMProvider,
    AsyncLLMResult,
    AsyncOpenAICompatibleProvider,
    AsyncAnthropicProvider,
    AsyncLLMProviderFactory,
    get_async_llm_provider,
    async_complete,
    async_batch_complete,
)

from .health_check import (
    HealthChecker,
    HealthStatus,
    ComponentCheck,
    HealthReport,
    get_health_checker,
    get_health_report,
    get_health_status,
)

__version__ = "0.3.0"
__author__ = "Lumina Team"
