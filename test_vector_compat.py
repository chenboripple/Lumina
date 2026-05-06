#!/usr/bin/env python3
"""
测试 chromadb 版本兼容性
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 测试 1：检查当前 chromadb 版本
print("=" * 60)
print("测试 1：检查当前 chromadb 版本")
print("=" * 60)
try:
    import chromadb
    from chromadb.config import Settings
    print(f"chromadb version: {chromadb.__version__}")
    print(f"Has PersistentClient: {hasattr(chromadb, 'PersistentClient')}")
except Exception as e:
    print(f"chromadb import error: {e}")

# 测试 2：检查 numpy
print("\n" + "=" * 60)
print("测试 2：检查 numpy 版本")
print("=" * 60)
try:
    import numpy
    print(f"numpy version: {numpy.__version__}")
    # 检查 basic numpy 功能
    arr = numpy.array([1, 2, 3])
    print(f"numpy array: {arr}")
except Exception as e:
    print(f"numpy import error: {e}")

# 测试 3：VectorStore 初始化
print("\n" + "=" * 60)
print("测试 3：VectorStore 初始化")
print("=" * 60)
try:
    from lumina.vector_store import VectorStore, VectorDocument

    # 创建临时测试目录
    test_dir = Path(__file__).parent / ".lumina_test"
    test_dir.mkdir(exist_ok=True)

    # 初始化 VectorStore
    store = VectorStore(
        persist_directory=str(test_dir / "vector_store"),
        embedding_provider_config={"provider": "local"}
    )
    print(f"✅ VectorStore 初始化成功")
    print(f"   - client type: {type(store.client).__name__}")
    print(f"   - collection: {store.collection_name}")
    print(f"   - stats: {store.get_stats()}")

    # 测试添加文档
    print(f"\n测试 4：添加文档")
    print("=" * 60)
    doc1 = VectorDocument(
        id="test1",
        content="这是一个测试文档，关于 Python 编程",
        metadata={"source": "test", "title": "Python 测试"}
    )
    doc_id = store.add_document(doc1)
    print(f"✅ 添加文档成功，id={doc_id}")

    # 测试搜索
    print(f"\n测试 5：向量搜索")
    print("=" * 60)
    results = store.search("Python 编程", n_results=5)
    print(f"✅ 搜索完成，共 {len(results)} 个结果")
    for i, r in enumerate(results, 1):
        print(f"   {i}. {r.document.metadata.get('title')} (score: {r.score:.4f})")

    # 测试关联笔记
    print(f"\n测试 6：关联笔记")
    print("=" * 60)
    related = store.find_related_notes("test1", min_score=0.0)
    print(f"✅ 关联笔记功能正常，共 {len(related)} 个相关笔记")

    # 测试统计
    print(f"\n测试 7：获取统计")
    print("=" * 60)
    stats = store.get_stats()
    print(f"✅ 统计获取成功: {stats}")

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！新版 chromadb/numpy 兼容")
    print("=" * 60)

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

finally:
    # 清理测试数据
    import shutil
    test_dir = Path(__file__).parent / ".lumina_test"
    if test_dir.exists():
        try:
            shutil.rmtree(test_dir)
            print("\n🧹 测试目录已清理")
        except Exception:
            pass
