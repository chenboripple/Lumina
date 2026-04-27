#!/usr/bin/env python3
"""
简单的模块导入验证
"""
import sys
from pathlib import Path

# 添加 src 目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

print("🔍 测试模块导入...")

try:
    print("1. 测试 lumina.utils.progress...")
    from lumina.utils.progress import ProgressTracker, BatchProgressTracker
    print("   ✅ 进度模块导入成功")
    
    # 快速功能测试
    tracker = ProgressTracker(total=10, description="Test")
    tracker.update(5)
    print(f"   ✅ 进度追踪器功能正常: {tracker.state.percentage:.1f}%")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("2. 测试 lumina.utils.error_handler...")
    from lumina.utils.error_handler import ErrorHandler, ErrorSeverity, GracefulDegradation
    print("   ✅ 错误处理模块导入成功")
    
    handler = ErrorHandler()
    result = handler.handle_error(
        ValueError("test"),
        severity=ErrorSeverity.WARNING,
        fallback="fallback"
    )
    print(f"   ✅ 错误处理功能正常: {result}")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("3. 测试 lumina.config.hot_reload...")
    from lumina.config.hot_reload import ConfigWatcher
    print("   ✅ 配置热加载模块导入成功")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("4. 测试 lumina.cache...")
    from lumina.cache import CacheManager
    print("   ✅ 缓存模块导入成功")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

try:
    print("5. 测试 lumina.harness...")
    from lumina.harness import Harness, HarnessConfig
    print("   ✅ Harness 模块导入成功")
    
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ 验证完成!")
