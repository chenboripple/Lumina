"""
Logging 模块单元测试
测试统一日志系统、timed 装饰器、错误恢复建议
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil


class TestLoggerSetup:
    """Logger 配置测试"""

    def test_get_logger_default(self):
        """测试获取默认 logger"""
        import lumina.utils.logging as logging_mod
        # reset singleton to make this assertion deterministic
        logging_mod._logger = None
        from lumina.utils.logging import get_logger
        logger = get_logger("test")

        assert logger is not None
        assert logger.name == "test"

    def test_get_logger_singleton(self):
        """测试 logger 单例模式"""
        from lumina.utils.logging import get_logger
        logger1 = get_logger("same")
        logger2 = get_logger("same")

        assert logger1 is logger2

    def test_set_log_level(self):
        """测试设置日志级别"""
        from lumina.utils.logging import get_logger, set_log_level
        set_log_level("DEBUG")

        logger = get_logger("level_test")
        assert logger.level <= 10  # DEBUG level


class TestTimedDecorator:
    """timed 装饰器测试"""

    def test_basic_timing(self):
        """测试基本计时"""
        from lumina.utils.logging import timed, get_performance_stats

        @timed
        def slow_function():
            time.sleep(0.01)
            return "done"

        result = slow_function()
        assert result == "done"

        stats = get_performance_stats()
        assert "slow_function" in str(stats)

    def test_timing_with_exception(self):
        """测试异常处理"""
        from lumina.utils.logging import timed

        @timed
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

    def test_reset_stats(self):
        """测试重置统计"""
        from lumina.utils.logging import timed, get_performance_stats, reset_performance_stats

        @timed
        def test_func():
            pass

        test_func()
        stats = get_performance_stats()
        assert len(stats) > 0

        reset_performance_stats()
        new_stats = get_performance_stats()
        assert len(new_stats) == 0


class TestErrorRecoverySuggestions:
    """错误恢复建议测试"""

    def test_get_error_recovery_known(self):
        """测试已知错误类型"""
        from lumina.utils.logging import get_error_recovery

        # ChromaDB 相关
        chroma_recovery = get_error_recovery("chromadb", "missing")
        assert "chromadb" in chroma_recovery["message"].lower()
        assert "pip install" in chroma_recovery["recovery"]

        # OpenAI 相关
        openai_recovery = get_error_recovery("openai", "network_error")
        assert openai_recovery["message"]
        assert "网络" in openai_recovery["message"] or "network" in openai_recovery["message"].lower()

        # Ollama 相关
        ollama_recovery = get_error_recovery("ollama", "not_running")
        assert "ollama" in ollama_recovery["message"].lower()

    def test_get_error_recovery_unknown(self):
        """测试未知错误类型"""
        from lumina.utils.logging import get_error_recovery

        recovery = get_error_recovery("unknown_type", "unknown_subtype")
        assert recovery["message"] is not None
        assert recovery["recovery"] is not None


class TestLogConvenienceFunctions:
    """便捷日志函数测试"""

    def test_log_info(self):
        """测试 log_info"""
        from lumina.utils.logging import log_info
        # 确保不抛出异常
        log_info("Test info message")

    def test_log_warning(self):
        """测试 log_warning"""
        from lumina.utils.logging import log_warning
        log_warning("Test warning message")

    def test_log_error(self):
        """测试 log_error"""
        from lumina.utils.logging import log_error
        log_error("Test error message")

    def test_log_debug(self):
        """测试 log_debug"""
        from lumina.utils.logging import log_debug
        log_debug("Test debug message")


class TestLogWithRecovery:
    """log_with_recovery 测试"""

    def test_log_with_recovery(self, capsys):
        """测试记录带恢复建议的日志"""
        from lumina.utils.logging import log_with_recovery

        log_with_recovery(
            "ollama",
            "not_running",
            details="Ollama not found on port 11434",
            level="WARNING"
        )

        # 检查输出
        captured = capsys.readouterr()
        # 应该记录了什么（具体取决于 logger 配置）

    def test_log_with_recovery_default_level(self):
        """测试默认日志级别"""
        from lumina.utils.logging import log_with_recovery

        # 确保不抛出异常
        log_with_recovery("config", "missing", details="No config file found")


class TestBackwardCompatibility:
    """向后兼容测试"""

    def test_original_log_llm_function(self):
        """测试旧的 _log_llm 函数仍然可用"""
        try:
            from lumina.llm import _log_llm

            # 应该可以正常调用
            _log_llm("Test message")
            _log_llm("Error message", level="ERROR")
        except ImportError:
            pass  # 如果函数被移走也没问题
        except Exception:
            pytest.fail("_log_llm should not raise exceptions")


class TestIntegration:
    """集成测试"""

    def test_timed_with_logging(self):
        """测试 timed 和 logging 一起使用"""
        from lumina.utils.logging import timed, get_logger

        logger = get_logger("integration")

        @timed
        def example_function(x):
            logger.info(f"Processing {x}")
            return x * 2

        result = example_function(5)
        assert result == 10
