#!/usr/bin/env python3
"""
测试文件编辑工具系统
"""

import tempfile
import os
import sys
from pathlib import Path

# 添加 src 目录到路径
src_dir = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_dir))

# 导入工具系统
from lumina.tools import init_tools, get_tool, ToolContext, ToolResult


def test_file_edit_tool():
    """测试文件编辑工具"""
    
    # 初始化工具
    init_tools()
    
    # 获取文件编辑工具
    file_edit_tool = get_tool("file_edit")
    if not file_edit_tool:
        print("❌ FileEditTool not found")
        return False
    
    print(f"✅ Loaded tool: {file_edit_tool.display_name} v{file_edit_tool.version}")
    
    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        test_content = """# Test Document

This is a test file.

## Section 1
Content of section 1.

## Section 2
Content of section 2.

## Section 3
Content of section 3.
"""
        f.write(test_content)
        temp_file = f.name
    
    try:
        print(f"\n📝 Created test file: {temp_file}")
        
        # 测试1：基本替换
        print("\n🧪 Test 1: Basic replacement")
        context = ToolContext(session_id="test-session-1")
        result = file_edit_tool.execute(
            context=context,
            file_path=temp_file,
            old_string="Content of section 1.",
            new_string="Updated content of section 1 (modified by FileEditTool)."
        )
        
        if result.success:
            print(f"✅ {result.message}")
        else:
            print(f"❌ Failed: {result.error}")
            return False
        
        # 验证结果
        with open(temp_file, 'r') as f:
            content = f.read()
        if "Updated content of section 1" in content:
            print("✅ Content correctly updated")
        else:
            print("❌ Content not updated")
            return False
        
        # 测试2：多匹配检测
        print("\n🧪 Test 2: Multiple match detection")
        context = ToolContext(session_id="test-session-2")
        result = file_edit_tool.execute(
            context=context,
            file_path=temp_file,
            old_string="Content of section",
            new_string="Modified section content"
        )
        
        if not result.success and "Multiple matches" in result.error:
            print(f"✅ Correctly rejected multiple matches: {result.error}")
        else:
            print(f"❌ Should have rejected multiple matches")
            return False
        
        # 测试3：替换所有匹配
        print("\n🧪 Test 3: Replace all matches")
        context = ToolContext(session_id="test-session-3")
        result = file_edit_tool.execute(
            context=context,
            file_path=temp_file,
            old_string="Content of section",
            new_string="Modified section content",
            replace_all=True
        )
        
        if result.success:
            print(f"✅ {result.message}")
        else:
            print(f"❌ Failed: {result.error}")
            return False
        
        # 验证所有替换
        with open(temp_file, 'r') as f:
            content = f.read()
        if content.count("Modified section content") == 2:  # 有两个 section 被替换，section1 已经被修改过
            print("✅ All matches correctly replaced")
        else:
            print(f"❌ Unexpected number of matches: {content.count('Modified section content')}")
            return False
        
        # 测试4：相同内容检测
        print("\n🧪 Test 4: Identical content detection")
        context = ToolContext(session_id="test-session-4")
        result = file_edit_tool.execute(
            context=context,
            file_path=temp_file,
            old_string="# Test Document",
            new_string="# Test Document"
        )
        
        if not result.success and "identical" in result.error:
            print(f"✅ Correctly rejected identical content: {result.error}")
        else:
            print(f"❌ Should have rejected identical content")
            return False
        
        # 测试5：敏感内容检测
        print("\n🧪 Test 5: Sensitive content detection")
        context = ToolContext(session_id="test-session-5")
        result = file_edit_tool.execute(
            context=context,
            file_path=temp_file,
            old_string="## Section 3",
            new_string="## Section 3\nsk-abcdefghijklmnopqrstuvwxyz1234567890"
        )
        
        if not result.success and "Sensitive content detected" in result.error:
            print(f"✅ Correctly detected sensitive content: {result.error}")
        else:
            print(f"❌ Should have detected sensitive content")
            return False
        
        print("\n🎉 All tests passed! FileEditTool is working correctly.")
        return True
        
    finally:
        # 清理临时文件
        os.unlink(temp_file)
        print(f"\n🧹 Cleaned up test file: {temp_file}")


if __name__ == "__main__":
    success = test_file_edit_tool()
    exit(0 if success else 1)
