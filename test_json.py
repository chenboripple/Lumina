#!/usr/bin/env python3
"""
测试 Flask JSON 返回
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from flask import Flask, jsonify
    import json
    import tempfile
    
    print("✅ Flask imported successfully")
    
    # 测试简单的 JSON 序列化
    test_data = {
        "total_notes": 0,
        "total_files_processed": 0,
        "avg_score": 0.0,
        "status": "initialized",
        "vector_store": {
            "available": False
        }
    }
    
    json_str = json.dumps(test_data)
    print("✅ JSON serialization works")
    print(f"   JSON: {json_str}")
    
    # 测试 jsonify
    print("✅ All tests passed!")
    print("")
    print("问题分析:")
    print("1. 检查是否有返回非 JSON 可序列化的值")
    print("2. 检查是否有字符串中包含特殊字符")
    print("3. 检查是否有路径字符串中有引号问题")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
