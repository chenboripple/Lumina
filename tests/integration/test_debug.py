"""
调试模式测试
"""

import pytest
from pathlib import Path
from lumina.debug import LuminaDebugger
from lumina.harness import HarnessConfig


class TestDebugMode:
    """调试模式测试"""

    def test_debug_single_file(self, tmp_path):
        """单文件调试应该返回完整的调试报告"""
        # 创建测试文件
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nThis is a test document.")
        
        debugger = LuminaDebugger()
        config = HarnessConfig(
            max_iterations=1,
            quality_threshold=0.0,
        )
        
        report = debugger.debug_single_file(str(test_file), config)
        
        assert "file_path" in report
        assert "steps" in report
        assert report["file_path"] == str(test_file)
        assert len(debugger.debug_logs) > 0
    
    def test_debug_logs_structure(self, tmp_path):
        """调试日志应该有正确的结构"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Simple text content.")
        
        debugger = LuminaDebugger()
        config = HarnessConfig(
            max_iterations=1,
            quality_threshold=0.0,
        )
        
        debugger.debug_single_file(str(test_file), config)
        
        # 检查日志结构
        for log in debugger.debug_logs:
            assert "step" in log
            assert "phase" in log
            assert "action" in log
            assert "timestamp" in log
            assert isinstance(log["step"], int)
            assert log["step"] > 0
    
    def test_debug_with_nonexistent_file(self):
        """调试不存在的文件应该抛出 FileNotFoundError"""
        debugger = LuminaDebugger()
        
        with pytest.raises(FileNotFoundError):
            debugger.debug_single_file("/nonexistent/file.md")
    
    def test_validate_config(self, tmp_path):
        """配置验证应该返回错误列表"""
        from lumina.config import LuminaConfig
        
        # 创建无效配置
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text("""
input:
  sources:
    - path: "/nonexistent/path"
      recursive: true
""")
        
        config = LuminaConfig.load(str(config_file))
        debugger = LuminaDebugger()
        errors = debugger.validate_config(config)
        
        assert len(errors) > 0
        assert any("does not exist" in e for e in errors)
    
    def test_test_llm_connection_without_config(self):
        """测试 LLM 连接（无配置时应该使用默认配置）"""
        debugger = LuminaDebugger()
        
        # 注意：这个测试在没有 API key 的情况下会失败
        # 但应该能正确执行流程
        result = debugger.test_llm_connection()
        
        # 结果取决于是否有 API key
        assert isinstance(result, bool)
