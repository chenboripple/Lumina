#!/usr/bin/env python3
"""
Lumina 快速启动脚本 - v2.0
"""
import sys
from pathlib import Path

# 添加 src 目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

print("=" * 60)
print("🚀 Lumina v2.0 - 快速启动")
print("=" * 60)

def test_module_imports():
    """测试所有模块导入"""
    modules = [
        ("配置模块", "lumina.config"),
        ("缓存模块", "lumina.cache"),
        ("历史模块", "lumina.history"),
        ("核心协调器", "lumina.harness"),
        ("进度追踪", "lumina.utils.progress"),
        ("错误处理", "lumina.utils.error_handler"),
        ("配置热加载", "lumina.config.hot_reload"),
        ("标签推荐", "lumina.tag_recommender"),
        ("智能链接", "lumina.smart_link_generator"),
        ("多设备同步", "lumina.multi_device_sync"),
        ("批量修复", "lumina.batch_repair"),
    ]
    
    all_passed = True
    for name, module in modules:
        try:
            __import__(module)
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name}: {e}")
            all_passed = False
    
    return all_passed

def test_basic_functionality():
    """测试基础功能"""
    print("\n" + "=" * 60)
    print("📦 测试基础功能")
    print("=" * 60)
    
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
        print(f"   - status: {harness.state.status}")
        
        state = harness.get_state()
        print(f"   - get_state(): {list(state.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ 基础功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_progress_tracker():
    """测试进度追踪器"""
    try:
        from lumina.utils.progress import ProgressTracker
        
        tracker = ProgressTracker(total=10, description="测试进度")
        print(f"✅ ProgressTracker 创建成功")
        
        tracker.update(3, status="进行中")
        print(f"   - 当前进度: {tracker.state.percentage:.1f}%")
        print(f"   - 当前状态: {tracker.state.status}")
        print(f"   - 已用时间: {tracker.state.elapsed:.2f}s")
        
        tracker.finish(message="完成!")
        print(f"   - 完成进度: {tracker.state.percentage:.1f}%")
        
        return True
    except Exception as e:
        print(f"❌ 进度追踪器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handler():
    """测试错误处理器"""
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
            raise ValueError("测试异常")
        
        print(f"   - GracefulDegradation 结果: {gd.result}")
        
        # 测试统计
        summary = handler.get_error_summary()
        print(f"   - 总错误数: {summary['total_errors']}")
        
        return True
    except Exception as e:
        print(f"❌ 错误处理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tag_recommender():
    """测试标签推荐器"""
    try:
        from lumina.tag_recommender import TagRecommender
        
        recommender = TagRecommender()
        print(f"✅ TagRecommender 创建成功")
        
        # 测试关键词提取
        content = "Python machine learning with scikit-learn, TensorFlow, PyTorch, and Docker"
        tags = recommender._extract_keywords(content, "ML Guide")
        print(f"   - 关键词提取: {tags[:5]}")
        
        # 测试技术栈识别
        tech_tags = recommender._detect_tech_stack(content, "Tech Stack")
        print(f"   - 技术栈识别: {tech_tags[:5]}")
        
        # 测试概念识别
        concept_tags = recommender._detect_concepts(content, "Concepts")
        print(f"   - 概念识别: {concept_tags[:3]}")
        
        return True
    except Exception as e:
        print(f"❌ 标签推荐器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_smart_link_generator():
    """测试智能链接生成器"""
    try:
        from lumina.smart_link_generator import SmartLinkGenerator
        
        generator = SmartLinkGenerator(similarity_threshold=0.5)
        print(f"✅ SmartLinkGenerator 创建成功")
        
        # 测试关键词提取
        keywords = generator._extract_keywords("Python machine learning tutorial")
        print(f"   - 提取关键词: {keywords[:5]}")
        
        # 测试模糊匹配
        similarity = generator._fuzzy_match("Python machine learning guide", "Python ML tutorial")
        print(f"   - 模糊匹配相似度: {similarity:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ 智能链接生成器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sync_manager():
    """测试同步管理器"""
    try:
        import tempfile
        from lumina.multi_device_sync import SyncManager
        
        sync_dir = tempfile.mkdtemp()
        sync = SyncManager(device_id="test_device", sync_dir=sync_dir)
        print(f"✅ SyncManager 创建成功")
        print(f"   - device_id: {sync.device_id}")
        print(f"   - sync_dir: {sync.sync_dir}")
        
        # 添加同步项
        sync.queue_note_for_sync("/test/note.md", "测试笔记内容")
        print(f"   - 待同步队列: {len(sync.pending_queue)} 个")
        
        # 获取同步状态
        status = sync.get_sync_status()
        print(f"   - 同步状态: {list(status.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ 同步管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_batch_repair():
    """测试批量修复"""
    try:
        from lumina.batch_repair import BatchRepairManager
        
        repair = BatchRepairManager(harness=None, max_workers=2)
        print(f"✅ BatchRepairManager 创建成功")
        print(f"   - max_workers: {repair.max_workers}")
        print(f"   - default_threshold: {repair.default_threshold}")
        
        # 测试队列状态
        status = repair.get_queue_status()
        print(f"   - 队列状态: {list(status.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ 批量修复测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    # 1. 模块导入测试
    print("\n📦 1. 模块导入测试")
    print("-" * 60)
    imports_ok = test_module_imports()
    
    if not imports_ok:
        print("\n❌ 模块导入失败，请检查依赖")
        return 1
    
    # 2. 功能测试
    tests = [
        ("基础功能", test_basic_functionality),
        ("进度追踪器", test_progress_tracker),
        ("错误处理器", test_error_handler),
        ("标签推荐器", test_tag_recommender),
        ("智能链接", test_smart_link_generator),
        ("多设备同步", test_sync_manager),
        ("批量修复", test_batch_repair),
    ]
    
    passed = 0
    failed = 0
    
    for name, func in tests:
        print(f"\n📦 {passed+failed+2}. 测试 {name}")
        print("-" * 60)
        if func():
            passed += 1
        else:
            failed += 1
    
    # 3. 汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    
    if failed == 0:
        print(f"\n🎉 所有测试通过! Lumina v2.0 准备就绪!")
        print(f"\n📚 下一步:")
        print(f"   1. 查看 docs/test-guide.md 了解详细使用")
        print(f"   2. 运行 python3 lumina.py 启动命令行")
        print(f"   3. 编写测试文件并运行完整流程")
        return 0
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
