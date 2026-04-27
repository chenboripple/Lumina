#!/usr/bin/env python3
"""
Lumina 优化验证脚本
测试新增的模块是否能正常导入和运行
"""
import sys
import os
from pathlib import Path

# 添加 src 目录到路径
src_dir = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_dir))

print("=" * 60)
print("🧪 Lumina 优化验证")
print("=" * 60)

tests_passed = 0
tests_failed = 0

def test_import(module_name, description):
    """测试模块导入"""
    global tests_passed, tests_failed
    try:
        __import__(module_name)
        print(f"✅ {description}")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ {description}: {e}")
        tests_failed += 1
        return False

print("\n📦 测试模块导入...")

# 测试核心模块
test_import("lumina.config", "配置模块")
test_import("lumina.cache", "缓存模块")
test_import("lumina.history", "历史模块")
test_import("lumina.harness", "核心协调器")

# 测试新增的工具模块
test_import("lumina.utils.progress", "进度追踪器")
test_import("lumina.utils.error_handler", "错误处理器")
test_import("lumina.config.hot_reload", "配置热加载")

print("\n" + "=" * 60)

# 测试基础功能
print("\n🔧 测试进度追踪器功能...")
try:
    from lumina.utils.progress import ProgressTracker
    tracker = ProgressTracker(total=10, description="Test Progress")
    tracker.update(3, status="working")
    print(f"✅ 进度追踪器创建成功 - 当前进度: {tracker.state.percentage:.1f}%")
    tracker.finish(message="Test completed")
    print(f"✅ 进度追踪器完成功能正常")
    tests_passed += 1
except Exception as e:
    print(f"❌ 进度追踪器测试失败: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n🛡️ 测试错误处理器功能...")
try:
    from lumina.utils.error_handler import ErrorHandler, ErrorSeverity
    handler = ErrorHandler()
    
    # 测试错误处理
    result = handler.handle_error(
        ValueError("Test error"),
        severity=ErrorSeverity.WARNING,
        fallback="fallback value"
    )
    assert result == "fallback value"
    print(f"✅ 错误处理和降级功能正常")
    
    # 测试错误统计
    summary = handler.get_error_summary()
    assert summary["total_errors"] == 1
    print(f"✅ 错误统计功能正常: {summary}")
    tests_passed += 1
except Exception as e:
    print(f"❌ 错误处理器测试失败: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n🔄 测试配置热加载模块...")
try:
    from lumina.config.hot_reload import ConfigWatcher
    import tempfile
    import yaml
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml.dump({"test": "value", "version": 1}))
        temp_config_path = f.name
    
    try:
        # 测试 ConfigWatcher
        watcher = ConfigWatcher(temp_config_path, auto_reload=False)
        config = watcher.get_config()
        assert config["test"] == "value"
        print(f"✅ 配置热加载模块创建成功 - 初始配置: {config}")
        
        # 测试配置更新检测
        with open(temp_config_path, 'w') as f:
            f.write(yaml.dump({"test": "updated", "version": 2}))
        
        changed = watcher.has_changed()
        # 重新加载配置
        new_config = watcher.reload()
        assert new_config["test"] == "updated"
        print(f"✅ 配置热加载和更新检测功能正常 - 新配置: {new_config}")
        
        tests_passed += 1
    finally:
        os.unlink(temp_config_path)
except Exception as e:
    print(f"❌ 配置热加载测试失败: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n📊 测试缓存模块增强功能...")
try:
    from lumina.cache import CacheManager
    import tempfile
    import shutil
    
    cache_dir = tempfile.mkdtemp()
    cache = CacheManager(cache_dir=cache_dir)
    
    # 测试文件缓存
    cache.set_file("test_hash", {"data": "test_value"})
    result = cache.get_file("test_hash")
    assert result["data"] == "test_value"
    print(f"✅ 文件缓存功能正常")
    
    # 测试新的 processed_result 缓存
    cache.set_processed_result("file_hash", '{"score": 0.9, "output": {...}}')
    cached_result = cache.get_processed_result("file_hash")
    assert "score" in cached_result
    print(f"✅ 处理结果缓存功能正常")
    
    # 测试统计
    stats = cache.get_stats()
    assert stats["hits"] == 2
    print(f"✅ 缓存统计功能正常: {stats}")
    
    shutil.rmtree(cache_dir)
    tests_passed += 1
except Exception as e:
    print(f"❌ 缓存模块测试失败: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n" + "=" * 60)
print("📋 测试结果汇总")
print("=" * 60)
print(f"✅ 通过: {tests_passed}")
print(f"❌ 失败: {tests_failed}")
print(f"🎯 成功率: {tests_passed/(tests_passed+tests_failed)*100:.1f}%")

if tests_failed == 0:
    print("\n🎉 所有测试通过！")
    sys.exit(0)
else:
    print("\n⚠️ 部分测试失败，请检查相关模块")
    sys.exit(1)
