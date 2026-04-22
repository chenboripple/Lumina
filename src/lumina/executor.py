"""
Executor - 执行模块
基于 LLM 生成结构化笔记
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json

from .llm import get_llm_provider, LLMConfig, BaseLLMProvider


@dataclass
class NoteOutput:
    """笔记输出"""
    title: str
    content: str
    tags: list
    links: list
    source: str
    metadata: Dict[str, Any]


class Executor:
    """
    执行器：调用 LLM 生成笔记
    
    职责：
    1. 读取文件内容
    2. 构建 LLM 提示词
    3. 生成结构化笔记
    4. 提取标签和链接
    """
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config or {}
        self.llm_provider: Optional[BaseLLMProvider] = None
        self.prompt_template = self._load_template()
    
    def _get_llm(self) -> BaseLLMProvider:
        """获取或创建 LLM Provider"""
        if self.llm_provider is None:
            self.llm_provider = get_llm_provider(self.llm_config)
        return self.llm_provider
    
    def execute(self, file_info, plan: Dict[str, Any]) -> NoteOutput:
        """
        执行笔记生成
        
        Args:
            file_info: 文件信息
            plan: 执行计划
            
        Returns:
            生成的笔记
        """
        # 读取内容
        content = self._read_file(file_info.path)
        
        # 构建提示词
        prompt = self._build_prompt(file_info, content, plan)
        
        # 调用 LLM
        raw_output = self._call_llm(prompt)
        
        # 解析输出
        note = self._parse_output(raw_output, file_info)
        
        return note
    
    def _read_file(self, path: Path) -> str:
        """读取文件内容"""
        try:
            if path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
                return "[Image file - use vision model]"
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"[Error reading file: {e}]"
    
    def _build_prompt(self, file_info, content: str, plan: Dict[str, Any]) -> str:
        """构建 LLM 提示词"""
        return f"""
You are a knowledge extraction expert. Analyze the following content and generate a structured note.

## Source Information
- File: {file_info.path.name}
- Type: {file_info.type}
- Size: {file_info.size} bytes

## Content
```
{content[:4000]}  # 限制长度
```

## Instructions
1. Extract key concepts and insights
2. Create a clear, structured summary
3. Identify potential links to other topics
4. Suggest relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Concise title",
    "summary": "Brief overview",
    "key_points": ["point 1", "point 2"],
    "tags": ["tag1", "tag2"],
    "suggested_links": ["Topic A", "Topic B"],
    "metadata": {{
        "complexity": "simple|moderate|complex",
        "confidence": 0.95
    }}
}}
"""
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        try:
            llm = self._get_llm()
            return llm.complete(prompt)
        except Exception as e:
            # 降级处理：返回错误信息
            return json.dumps({
                "title": "Error",
                "summary": f"LLM call failed: {str(e)}",
                "key_points": [],
                "tags": ["error"],
                "suggested_links": [],
                "metadata": {"complexity": "simple", "confidence": 0.0, "error": str(e)}
            })
    
    def _parse_output(self, raw_output: str, file_info) -> NoteOutput:
        """解析 LLM 输出"""
        try:
            data = json.loads(raw_output)
            
            # 构建 Markdown 内容
            content = self._to_markdown(data)
            
            return NoteOutput(
                title=data.get("title", file_info.path.stem),
                content=content,
                tags=data.get("tags", []),
                links=data.get("suggested_links", []),
                source=str(file_info.path),
                metadata=data.get("metadata", {})
            )
        except json.JSONDecodeError:
            return NoteOutput(
                title=file_info.path.stem,
                content=raw_output,
                tags=[],
                links=[],
                source=str(file_info.path),
                metadata={"error": "parse_failed"}
            )
    
    def _to_markdown(self, data: Dict[str, Any]) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# {data.get('title', 'Untitled')}\n",
            f"## Summary\n",
            f"{data.get('summary', '')}\n",
            f"## Key Points\n",
        ]
        
        for point in data.get("key_points", []):
            lines.append(f"- {point}\n")
        
        if data.get("suggested_links"):
            lines.extend([
                f"\n## Related Topics\n",
            ])
            for link in data["suggested_links"]:
                lines.append(f"- {link}\n")
        
        lines.extend([
            f"\n## Metadata\n",
            f"- Complexity: {data.get('metadata', {}).get('complexity', 'unknown')}\n",
            f"- Confidence: {data.get('metadata', {}).get('confidence', 0)}\n",
        ])
        
        return "".join(lines)
    
    def _load_template(self) -> str:
        """加载提示词模板"""
        return "default"