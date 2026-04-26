
"""
增量更新演示脚本
展示 Lumina 增量更新引擎的使用方法
"""

import time
from pathlib import Path
from lumina import (
    IncrementalProcessor, FileChangeTracker, 
    DirectoryMonitor, MultimodalExtractor
)


def demo_incremental_processing():
    """演示增量处理"""
    print("🚀 Lumina 增量更新引擎演示\n")
    
    # 1. 初始化增量处理器
    print("1️⃣ 初始化增量处理器...")
    processor = IncrementalProcessor(
        planner=None,  # 简化演示
        executor=None,
        validator=None,
        max_workers=4
    )
    
    # 2. 创建测试文件
    print("\n2️⃣ 创建测试文件...")
    test_dir = Path("./test_incremental")
    test_dir.mkdir(exist_ok=True)
    
    test_file = test_dir / "test_doc.md"
    test_file.write_text("""# Test Document

This is the initial version.

## Section 1
Content of section 1.

## Section 2
Content of section 2.
""", encoding='utf-8')
    
    print(f"✅ Created: {test_file}")
    
    # 3. 首次处理（全量）
    print("\n3️⃣ 首次处理（全量）...")
    results = processor.process_files([test_file])
    print(f"✅ Processed: {results['processed']}, Skipped: {results['skipped']}")
    
    # 4. 再次处理（应该跳过）
    print("\n4️⃣ 再次处理（未修改，应该跳过）...")
    results = processor.process_files([test_file])
    print(f"✅ Processed: {results['processed']}, Skipped: {results['skipped']}")
    
    # 5. 修改文件
    print("\n5️⃣ 修改文件...")
    test_file.write_text("""# Test Document

This is the updated version with new content.

## Section 1
Content of section 1.

## Section 2
Content of section 2.

## Section 3
This is a new section added in the update.
""", encoding='utf-8')
    print("✅ File modified")
    
    # 6. 再次处理（应该检测到变化并处理）
    print("\n6️⃣ 再次处理（检测到变化，增量处理）...")
    results = processor.process_files([test_file])
    print(f"✅ Processed: {results['processed']}, Skipped: {results['skipped']}")
    
    # 7. 查看指纹信息
    print("\n7️⃣ 查看文件指纹信息...")
    tracker = FileChangeTracker()
    changed, fingerprint = tracker.has_file_changed(test_file)
    print(f"File changed: {changed}")
    print(f"Hash: {fingerprint.hash[:16]}...")
    print(f"Size: {fingerprint.size} bytes")
    print(f"Blocks: {len(fingerprint.block_hashes)}")
    
    # 8. 多模态提取演示
    print("\n8️⃣ 多模态内容提取演示...")
    extractor = MultimodalExtractor()
    
    # 测试代码文件提取
    code_file = test_dir / "test.py"
    code_file.write_text("""
import os
import sys

def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value

if __name__ == "__main__":
    hello_world()
    obj = MyClass()
    print(obj.get_value())
""", encoding='utf-8')
    
    extracted = extractor.extract(code_file)
    print(f"\nCode extraction:")
    print(f"  Type: {extracted.content_type}")
    print(f"  Confidence: {extracted.confidence}")
    print(f"  Metadata: {extracted.metadata}")
    print(f"  Text preview: {extracted.text[:200]}...")
    
    # 9. 支持的文件类型
    print("\n9️⃣ 支持的文件类型...")
    supported = extractor.get_supported_types()
    print(f"Total supported types: {len(supported)}")
    print(f"Types: {', '.join(supported[:20])}...")
    
    # 清理
    print("\n🧹 清理测试文件...")
    import shutil
    shutil.rmtree(test_dir)
    
    print("\n✅ 演示完成！")


def demo_directory_monitoring():
    """演示目录监控"""
    print("\n👀 目录监控演示\n")
    
    test_dir = Path("./test_monitor")
    test_dir.mkdir(exist_ok=True)
    
    def handle_changes(files):
        print(f"\n🔄 Detected changes in {len(files)} files:")
        for f in files:
            print(f"  - {f.name}")
    
    # 启动监控
    monitor = DirectoryMonitor(
        directories=[test_dir],
        callback=handle_changes,
        recursive=True,
        debounce_seconds=2.0
    )
    
    monitor.start()
    print(f"👀 Monitoring: {test_dir}")
    print("Create/modify files to see changes... (Ctrl+C to stop)")
    
    try:
        # 模拟文件变化
        time.sleep(1)
        (test_dir / "file1.txt").write_text("Hello")
        time.sleep(1)
        (test_dir / "file2.txt").write_text("World")
        time.sleep(3)  # 等待防抖处理
        
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        import shutil
        shutil.rmtree(test_dir)
        print("\n🛑 Monitoring stopped")


if __name__ == "__main__":
    demo_incremental_processing()
    # demo_directory_monitoring()  # 取消注释以测试目录监控
