#!/usr/bin/env python3
"""
Lumina 本地测试脚本 - v2.0
"""
import sys
from pathlib import Path

# 添加 src 目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

print("=" * 60)
print("🧪 Lumina 本地测试 - v2.0")
print("=" * 60)

# 测试计数器
tests_passed = 0
tests_failed = 0

def test_import(name, module_name):
    """测试模块导入"""
    global tests_passed, tests_failed
    try:
        __import__(module_name)
        print(f"✅ {name}")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        tests_failed += 1
        return False

print("\n📦 1. 测试基础模块导入")
print("-" * 60)

# v1.0 模块
test_import("配置模块", "lumina.config")
test_import("缓存模块", "lumina.cache")
test_import("历史模块", "lumina.history")
test_import("核心协调器", "lumina.harness")

# v2.0 模块
test_import("进度追踪", "lumina.utils.progress")
test_import("错误处理", "lumina.utils.error_handler")
test_import("配置热加载", "lumina.config.hot_reload")
test_import("自动标签推荐", "lumina.tag_recommender")
test_import("智能链接生成", "lumina.smart_link_generator")
test_import("多设备同步", "lumina.multi_device_sync")
test_import("批量修复", "lumina.batch_repair")

print("\n📦 2. 测试核心类")
print("-" * 60)

# 测试 HarnessConfig
try:
    from lumina.harness import HarnessConfig
    config = HarnessConfig()
    print(f"✅ HarnessConfig 创建成功")
    print(f"   - max_iterations: {config.max_iterations}")
    print(f"   - quality_threshold: {config.quality_threshold}")
    print(f"   - enable_progress: {config.enable_progress}")
    tests_passed += 1
except Exception as e:
    print(f"❌ HarnessConfig: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试进度追踪器
try:
    from lumina.utils.progress import ProgressTracker
    tracker = ProgressTracker(total=10, description="测试进度")
    print(f"✅ ProgressTracker 创建成功")
    tracker.update(3, status="进行中")
    print(f"   - 当前进度: {tracker.state.percentage:.1f}%")
    print(f"   - 当前状态: {tracker.state.status}")
    tracker.finish(message="完成!")
    tests_passed += 1
except Exception as e:
    print(f"❌ ProgressTracker: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试错误处理器
try:
    from lumina.utils.error_handler import ErrorHandler, ErrorSeverity, GracefulDegradation
    handler = ErrorHandler()
    print(f"✅ ErrorHandler 创建成功")
    
    # 测试错误处理
    result = handler.handle_error(
        ValueError("测试错误"),
        severity=ErrorSeverity.WARNING,
        fallback="fallback_value"
    )
    print(f"   - 错误处理结果: {result}")
    
    # 测试优雅降级
    with GracefulDegradation(fallback="default", severity=ErrorSeverity.WARNING, context="测试") as gd:
        raise ValueError("测试")
    print(f"   - GracefulDegradation 结果: {gd.result}")
    
    summary = handler.get_error_summary()
    print(f"   - 错误统计: {summary['total_errors']}")
    tests_passed += 1
except Exception as e:
    print(f"❌ ErrorHandler: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试标签推荐器
try:
    from lumina.tag_recommender import TagRecommender
    recommender = TagRecommender()
    print(f"✅ TagRecommender 创建成功")
    
    # 测试关键词提取
    tags = recommender._extract_keywords(
        "Python machine learning artificial intelligence", 
        "ML Guide"
    )
    print(f"   - 提取关键词: {tags[:5]}")
    
    # 测试技术栈识别
    tech_tags = recommender._detect_tech_stack(
        "Using Python, React, Docker, and Kubernetes",
        "Tech Stack"
    )
    print(f"   - 识别技术栈: {tech_tags[:5]}")
    tests_passed += 1
except Exception as e:
    print(f"❌ TagRecommender: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试智能链接生成器
try:
    from lumina.smart_link_generator import SmartLinkGenerator
    generator = SmartLinkGenerator(similarity_threshold=0.6)
    print(f"✅ SmartLinkGenerator 创建成功")
    
    # 测试关键词提取
    keywords = generator._extract_keywords("Python machine learning tutorial")
    print(f"   - 提取关键词: {keywords}")
    tests_passed += 1
except Exception as e:
    print(f"❌ SmartLinkGenerator: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试同步管理器
try:
    import tempfile
    from lumina.multi_device_sync import SyncManager
    sync_dir = tempfile.mkdtemp()
    sync = SyncManager(device_id="test_device", sync_dir=sync_dir)
    print(f"✅ SyncManager 创建成功")
    print(f"   - device_id: {sync.device_id}")
    print(f"   - sync_dir: {sync.sync_dir}")
    
    # 获取同步状态
    status = sync.get_sync_status()
    print(f"   - 同步状态: {status}")
    tests_passed += 1
except Exception as e:
    print(f"❌ SyncManager: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

# 测试批量修复管理器
try:
    from lumina.batch_repair import BatchRepairManager
    repair = BatchRepairManager(harness=None, max_workers=2)
    print(f"✅ BatchRepairManager 创建成功")
    print(f"   - max_workers: {repair.max_workers}")
    print(f"   - default_threshold: {repair.default_threshold}")
    tests_passed += 1
except Exception as e:
    print(f"❌ BatchRepairManager: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n📦 3. 测试完整功能")
print("-" * 60)

# 测试 Harness 创建
try:
    from lumina.harness import Harness, HarnessConfig
    config = HarnessConfig(
        max_iterations=2,
        quality_threshold=0.6,
        output_dir="./test_output",
        enable_vector_store=False,
        enable_progress=True,
        enable_error_handler=True
    )
    harness = Harness(config)
    print(f"✅ Harness 创建成功")
    print(f"   - session_id: {harness.state.session_id}")
    print(f"   - enable_progress: {harness.config.enable_progress}")
    print(f"   - enable_error_handler: {harness.config.enable_error_handler}")
    
    # 获取状态
    state = harness.get_state()
    print(f"   - 当前状态: {state}")
    tests_passed += 1
except Exception as e:
    print(f"❌ Harness 创建: {e}")
    import traceback
    traceback.print_exc()
    tests_failed += 1

print("\n" + "=" * 60)
print("📊 测试结果汇总")
print("=" * 60)
print(f"✅ 通过: {tests_passed}")
print(f"❌ 失败: {tests_failed}")

if tests_failed == 0:
    print(f"\n🎉 所有测试通过! Lumina 准备就绪!")
    sys.exit(0)
else:
    print(f"\n⚠️ 有 {tests_failed} 个测试失败，请检查相关模块")
    sys.exit(1)
