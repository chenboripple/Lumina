# Lumina 深度优化分析报告 (第二阶段)

## 📊 优化优先级矩阵

### 🔴 高优先级（立即执行）

#### 1. 整合新模块到现有代码库

**现状分析：**
- ✅ `exceptions.py` - 已创建，但未被现有模块使用
- ✅ `circuit_breaker.py` - 已创建，但 `llm.py` 未集成
- ✅ `event_bus.py` - 已创建，但 `harness.py` / `executor.py` 未集成
- ✅ `prompt_manager.py` - 已创建，但 `executor.py` 仍用硬编码模板
- ✅ `health_check.py` - 已创建，但 `web_interface.py` 无端点

**优化建议：**

```
src/lumina/llm.py
  ↓ 集成
    • CircuitBreaker 装饰器包装 complete() / stream()
    • 使用自定义异常替代 RuntimeError / ValueError
    • 发布 LLM 事件到 EventBus

src/lumina/executor.py
  ↓ 集成
    • 迁移硬编码 PROMPT_TEMPLATES 到 PromptManager
    • 使用新的异常类型
    • 发布 FILE_PROCESSED / LLM_SUCCESS 事件

src/lumina/harness.py
  ↓ 集成
    • 订阅/发布事件到 EventBus
    • 使用自定义异常替代通用异常
    • 集成 CircuitBreaker 到 LLM 调用流程

src/lumina/web_interface.py
  ↓ 集成
    • 添加 /health 端点调用 HealthChecker
    • WebSocket 实时事件流
```

---

#### 2. 统一错误处理体系

**问题分析：**

目前有两套错误处理：
1. `utils/error_handler.py` - 旧系统，处理通用异常
2. `exceptions.py` - 新系统，完整自定义异常体系

**架构冲突：**

```
ErrorHandler (utils/error_handler.py)
  • ErrorSeverity 枚举
  • ErrorRecord 数据类
  • with_retry() 方法
  • 与新 exceptions.py 无集成
    ↓
    重复功能！
    ↓
LuminaError (exceptions.py)
  • 20+ 具体异常类型
  • ErrorContext 上下文
  • 便捷工厂函数
```

**整合方案：**

```python
# 方案：增强 ErrorHandler，支持新异常体系

class EnhancedErrorHandler(ErrorHandler):
    """增强版错误处理器 - 整合新异常体系"""
    
    def __init__(self, event_bus: EventBus = None):
        super().__init__()
        self.event_bus = event_bus
        
        # 映射新异常到严重程度
        self._severity_map.update({
            LuminaError: ErrorSeverity.ERROR,
            LLMRateLimitError: ErrorSeverity.WARNING,
            LLMTimeoutError: ErrorSeverity.WARNING,
            CircuitOpenError: ErrorSeverity.WARNING,
            # ...
        })
    
    def handle_exception(
        self,
        exc: LuminaError,
        context: Optional[ErrorContext] = None,
        fallback: Any = None
    ) -> Any:
        """处理新异常体系的异常"""
        # 发布事件
        if self.event_bus:
            self.event_bus.publish(
                error_occurred_event(
                    error_type=type(exc).__name__,
                    message=str(exc),
                    context=context.to_dict() if context else {}
                )
            )
        
        # 调用父类处理
        return self.handle_error(
            exc,
            context=context.file_path if context else "",
            fallback=fallback
        )
```

---

#### 3. LLM 层全面改造

**现状问题：**
- `llm.py` 直接使用 `openai` / `anthropic` SDK，无 CircuitBreaker
- 异常都是 `RuntimeError` / `ValueError`，无细分
- 无重试之外的保护机制
- `async_llm.py` 是独立的，未集成到主流程

**改造方案：**

```python
# 在现有 llm.py 中集成新模块

from .circuit_breaker import circuit_break, CircuitBreaker
from .event_bus import EventBus, llm_success_event, llm_error_event
from .exceptions import (
    LLMRateLimitError, LLMTimeoutError, LLMAuthenticationError,
    rate_limit_error, timeout_error, auth_error
)

class CircuitBreakerProtectedProvider(BaseLLMProvider):
    """带 Circuit Breaker 保护的 Provider 包装器"""
    
    def __init__(
        self,
        inner_provider: BaseLLMProvider,
        circuit_breaker: CircuitBreaker = None,
        event_bus: EventBus = None
    ):
        self.inner = inner_provider
        self.config = inner_provider.config
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            f"llm.{inner_provider.config.provider}"
        )
        self.event_bus = event_bus
    
    def complete(self, prompt: str, **kwargs) -> str:
        """带 Circuit Breaker 保护的 complete"""
        start_time = time.time()
        try:
            result = self.circuit_breaker.execute(
                lambda: self.inner.complete(prompt, **kwargs)
            )
            
            # 发布成功事件
            if self.event_bus:
                self.event_bus.publish(
                    llm_success_event(
                        provider=self.config.provider,
                        model=self.config.model,
                        tokens_used=0,  # 需要从 response 提取
                        duration=time.time() - start_time
                    )
                )
            
            return result
            
        except Exception as e:
            # 转换到新异常体系
            if "rate limit" in str(e).lower():
                converted = rate_limit_error(str(e), retry_after=60)
            elif "timeout" in str(e).lower():
                converted = timeout_error(str(e), timeout_seconds=self.config.timeout)
            elif "authentication" in str(e).lower():
                converted = auth_error(str(e))
            else:
                converted = LLMError(str(e))
            
            # 发布错误事件
            if self.event_bus:
                self.event_bus.publish(
                    llm_error_event(
                        provider=self.config.provider,
                        model=self.config.model,
                        error=str(e),
                        error_type=type(converted).__name__
                    )
                )
            
            raise converted
```

---

### 🟡 中优先级（近期优化）

#### 4. 迁移 Executor 的 Prompt 管理

**现状：** `executor.py` 中有硬编码模板字典

```python
# 当前（需要迁移）
PROMPT_TEMPLATES = {
    "markdown": "markdown_extractor",
    "text": "text_extractor",
    "code": "code_extractor",
    "pdf": "document_extractor",
    "image": "image_extractor",
    "data": "data_extractor",
    "default": "default_extractor",
}
```

**迁移计划：**

```python
# 迁移到 PromptManager
from .prompt_manager import PromptManager, get_prompt_manager

class PromptIntegratedExecutor(Executor):
    """使用 PromptManager 的 Executor"""
    
    def __init__(self, ..., prompt_manager: PromptManager = None):
        self.prompt_manager = prompt_manager or get_prompt_manager()
        
        # 注册默认模板（一次性）
        self._register_default_templates()
    
    def _register_default_templates(self):
        """从旧代码迁移模板到 PromptManager"""
        # 可以从旧的字符串模板中提取并注册
        # 或者让用户使用 PromptManager 的内置模板
        
        # 例如：如果之前有硬编码的模板字符串
        for file_type, template_name in self.PROMPT_TEMPLATES.items():
            # 检查是否已存在
            if not self.prompt_manager.get(template_name):
                # 可以加载默认模板
                # 或者提示用户使用 prompt_manager 的内置模板
                pass
    
    def _get_prompt_for(self, file_type: str, **kwargs) -> str:
        """使用 PromptManager 获取提示词"""
        template_name = self.PROMPT_TEMPLATES.get(file_type, "default_extractor")
        return self.prompt_manager.render(template_name, **kwargs)
    
    def record_feedback(
        self,
        template_name: str,
        score: float,
        feedback: str,
        is_positive: bool
    ):
        """记录用户反馈到 PromptManager"""
        self.prompt_manager.score_template(
            name=template_name,
            score=score,
            feedback=feedback,
            is_positive=is_positive
        )
```

---

#### 5. 事件总线深度集成

**在 Harness 中集成：**

```python
from .event_bus import (
    EventBus, Event, EventTypes,
    file_scanned_event, file_processed_event, file_failed_event,
    note_created_event, batch_progress_event,
    subscribe
)

class EventBusIntegratedHarness(Harness):
    """带 EventBus 集成的 Harness"""
    
    def __init__(self, config: HarnessConfig = None, event_bus: EventBus = None):
        super().__init__(config)
        self.event_bus = event_bus or EventBus()
        
        # 订阅自己的事件（可选，用于内部处理）
        self._subscribe_internal_events()
        
        # 启动异步事件处理 worker
        self.event_bus.start_worker()
    
    def _subscribe_internal_events(self):
        """订阅内部事件用于统计等"""
        
        @subscribe(EventTypes.FILE_PROCESSED)
        def on_file_processed(event):
            with self._state_lock:
                self.state.processed_files += 1
        
        @subscribe(EventTypes.FILE_FAILED)
        def on_file_failed(event):
            with self._state_lock:
                self.state.failed_files += 1
                self.state.errors.append({
                    "file": event.payload.get("file_path"),
                    "error": event.payload.get("error"),
                    "timestamp": event.timestamp
                })
    
    def scan(self, ...):
        """增强版 scan，发布事件"""
        # 发布开始事件
        self.event_bus.publish(
            Event(
                type=EventTypes.SYSTEM_STARTED,
                payload={"sources": sources},
                source="harness"
            )
        )
        
        for file_info in files:
            # 发布文件扫描事件
            self.event_bus.publish(
                file_scanned_event(
                    file_path=str(file_info.path),
                    file_type=file_info.file_type
                )
            )
        
        # ... 其余逻辑
    
    def process_single_file(self, file_info: FileInfo):
        """处理单个文件，发布流程事件"""
        try:
            result = self._process(file_info)
            
            # 发布成功事件
            self.event_bus.publish(
                file_processed_event(
                    file_path=str(file_info.path),
                    note_path=str(result.note_path),
                    score=result.score,
                    success=True
                )
            )
            
            self.event_bus.publish(
                note_created_event(
                    note_path=str(result.note_path),
                    title=result.title,
                    tags=result.tags
                )
            )
            
            return result
            
        except Exception as e:
            # 发布失败事件
            self.event_bus.publish(
                file_failed_event(
                    file_path=str(file_info.path),
                    error=str(e),
                    error_type=type(e).__name__
                )
            )
            raise
```

---

#### 6. Web 界面增强

**新增端点：**

```python
# 在 web_interface.py 中添加

from .health_check import get_health_checker, get_health_status

# 在 _register_routes() 中添加

@self.app.route('/health')
def health():
    """健康检查端点（支持 Docker HEALTHCHECK）"""
    try:
        status = get_health_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503

@self.app.route('/api/events')
def api_events():
    """获取事件流（轮询）或 WebSocket"""
    # 简单版本：返回最近的事件
    from .event_bus import get_global_event_bus
    
    event_bus = get_global_event_bus()
    recent = event_bus.get_recent_events(limit=100)
    
    return jsonify({
        "events": [ev.to_dict() for ev in recent],
        "total": len(recent)
    })

@self.app.route('/api/circuit-breaker')
def api_circuit_breaker():
    """Circuit Breaker 状态"""
    from .circuit_breaker import CircuitBreakerRegistry
    
    registry = CircuitBreakerRegistry()
    return jsonify({
        "circuit_breakers": [
            {
                "name": cb.name,
                "state": cb.state.value,
                "metrics": cb.metrics.to_dict()
            }
            for cb in registry.list()
        ]
    })

@self.app.route('/api/prompts')
def api_prompts():
    """Prompt 管理 API"""
    from .prompt_manager import get_prompt_manager
    
    pm = get_prompt_manager()
    templates = pm.list_templates()
    
    return jsonify({
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "avg_score": t.avg_score,
                "use_count": t.use_count
            }
            for t in templates
        ]
    })
```

---

#### 7. Cache 优化

**现状问题：**
- 纯同步实现
- 每个缓存操作都是单独文件 IO
- 无批量操作
- 无缓存预热

**优化方案：**

```python
# src/lumina/async_cache.py (新建)

import aiofiles
import asyncio
from typing import Any, Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta
import hashlib
import json


class AsyncCacheManager:
    """异步版本缓存管理器"""
    
    def __init__(self, cache_dir: str = "~/.lumina/cache"):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存层（LRU）
        self._llm_cache: Dict[str, tuple[str, float]] = {}
        self._max_memory_cache = 1000  # 最多缓存 1000 项
    
    async def get_llm_response_async(self, prompt_hash: str) -> Optional[str]:
        """异步获取 LLM 响应缓存"""
        # 先查内存
        if prompt_hash in self._llm_cache:
            response, expires_at = self._llm_cache[prompt_hash]
            if time.time() < expires_at:
                return response
        
        # 再查磁盘
        cache_file = self.cache_dir / "llm" / f"{prompt_hash}.json"
        if cache_file.exists():
            try:
                async with aiofiles.open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                
                if self._is_valid(data):
                    # 回写到内存
                    self._llm_cache[prompt_hash] = (
                        data["response"],
                        datetime.fromisoformat(data["expires_at"]).timestamp()
                    )
                    return data["response"]
            except Exception:
                pass
        
        return None
    
    async def set_llm_response_async(
        self,
        prompt_hash: str,
        response: str,
        ttl_days: int = 7
    ):
        """异步设置 LLM 响应缓存"""
        # 写内存
        expires_at = time.time() + (ttl_days * 86400)
        self._llm_cache[prompt_hash] = (response, expires_at)
        
        # 内存 LRU 淘汰
        if len(self._llm_cache) > self._max_memory_cache:
            # 简单实现：删除最旧的一半
            items = sorted(self._llm_cache.items(), key=lambda x: x[1][1])
            for k, _ in items[:len(items) // 2]:
                del self._llm_cache[k]
        
        # 异步写磁盘
        cache_file = self.cache_dir / "llm" / f"{prompt_hash}.json"
        data = {
            "response": response,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=ttl_days)).isoformat(),
        }
        
        async with aiofiles.open(cache_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))
    
    def _is_valid(self, data: Dict[str, Any]) -> bool:
        if "expires_at" in data:
            expires = datetime.fromisoformat(data["expires_at"])
            return datetime.now() < expires
        return True
```

---

### 🟢 低优先级（长期优化）

#### 8. 统一配置管理

**问题：**
- `config.py` 和 `config_core.py` 重复
- 配置分散在多个文件
- 无统一配置验证

#### 9. Vector Store 异步化

**优化点：**
- 向量索引操作通常耗时
- 添加异步接口
- 批量索引支持

#### 10. 插件系统增强

**现状：** `plugins.py` 已有基础，但可扩展
- 支持更多输出格式
- 插件热加载
- 插件配置化

---

## 🎯 优化实施路线图

### 第一阶段（1-2天）- 核心集成
1. ✅ 整合 CircuitBreaker 到 `llm.py`
2. ✅ 整合 EventBus 到 `harness.py`
3. ✅ 迁移 Executor 的 Prompt 管理
4. ✅ 添加 Web 健康检查端点

### 第二阶段（2-3天）- 深度优化
1. ✅ 统一异常处理体系
2. ✅ 增强 ErrorHandler
3. ✅ Async Cache
4. ✅ 完善事件发布

### 第三阶段（1周）- 高级特性
1. ✅ WebSocket 事件流
2. ✅ Prometheus 指标导出
3. ✅ 配置管理统一
4. ✅ Vector Store 异步化

---

## 📝 关键改造点总结

| 模块 | 改造内容 | 优先级 |
|------|---------|--------|
| `llm.py` | 集成 CircuitBreaker + EventBus | 🔴 高 |
| `harness.py` | 集成 EventBus + 异常体系 | 🔴 高 |
| `executor.py` | 迁移 PromptManager | 🔴 高 |
| `web_interface.py` | 添加 /health + 事件 API | 🔴 高 |
| `error_handler.py` | 整合新异常体系 | 🟡 中 |
| `cache.py` | 添加 AsyncCacheManager | 🟡 中 |
| `vector_store.py` | 异步接口 | 🟢 低 |
| `config.py` | 统一配置管理 | 🟢 低 |
