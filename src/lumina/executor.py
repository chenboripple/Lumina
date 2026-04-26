"""
Executor - 智能执行模块 (Agent 增强版)
基于 LLM 生成结构化笔记，支持缓存、分块、多策略执行
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterator
from dataclasses import dataclass, field
from datetime import datetime

from .llm import get_llm_provider, LLMConfig, BaseLLMProvider
from .cache import CacheManager
from .history import HistoryManager, ProcessingRecord


@dataclass
class NoteOutput:
    """笔记输出（增强版）"""
    title: str
    content: str
    tags: List[str]
    links: List[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_info: Dict[str, Any] = field(default_factory=dict)  # 处理过程信息


@dataclass
class ExecutionContext:
    """执行上下文"""
    session_id: str
    file_info: Any
    plan: Dict[str, Any]
    iteration: int = 0
    previous_output: Optional[NoteOutput] = None
    previous_validation: Optional[Any] = None


class Executor:
    """
    智能执行器（Agent 增强版）
    
    核心能力：
    1. 🧠 智能内容读取（支持大文件分块、图片OCR、PDF解析）
    2. 💾 LLM 响应缓存（避免重复调用，降低成本）
    3. 📝 多策略提示词（根据文件类型选择最佳策略）
    4. 🔄 迭代修复支持（基于验证反馈自动修复）
    5. 📊 执行过程记录（完整记录处理流程）
    6. ⚡ 流式输出支持（实时展示处理进度）
    """
    
    # 文件大小阈值
    SMALL_FILE_THRESHOLD = 100 * 1024  # 100KB
    MEDIUM_FILE_THRESHOLD = 1 * 1024 * 1024  # 1MB
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
    
    # 分块大小
    CHUNK_SIZE = 4000  # 每块最大字符数
    MAX_CHUNKS = 5  # 最多处理5块
    
    # 提示词模板
    PROMPT_TEMPLATES = {
        "markdown": "markdown_extractor",
        "text": "text_extractor",
        "code": "code_extractor",
        "pdf": "document_extractor",
        "image": "image_extractor",
        "data": "data_extractor",
        "default": "default_extractor",
    }
    
    def __init__(
        self, 
        llm_config: Dict[str, Any] = None,
        cache_manager: CacheManager = None,
        history_manager: HistoryManager = None
    ):
        self.llm_config = llm_config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.history_manager = history_manager
        
        # 提前初始化 LLM 提供者，启动时校验配置
        try:
            self.llm_provider = get_llm_provider(self.llm_config)
        except Exception as e:
            raise ValueError(f"LLM 配置无效: {str(e)}") from e
        
        # 统计信息
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }
    
    def _get_llm(self) -> BaseLLMProvider:
        """获取 LLM Provider（已预初始化）"""
        return self.llm_provider
    
    def execute(self, context: ExecutionContext) -> NoteOutput:
        """
        执行笔记生成（Agent 增强版）
        
        Args:
            context: 执行上下文
            
        Returns:
            生成的笔记
        """
        file_info = context.file_info
        
        # 1. 读取文件内容（智能分块）
        content_chunks = self._read_file_smart(file_info.path)
        
        # 2. 检查缓存
        cache_key = self._generate_cache_key(file_info, content_chunks)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            self.stats["cache_hits"] += 1
            return cached_result
        
        self.stats["cache_misses"] += 1
        
        # 3. 选择提示词策略
        prompt_strategy = self._select_prompt_strategy(file_info)
        
        # 4. 构建提示词
        if len(content_chunks) == 1:
            # 小文件：直接处理
            prompt = self._build_prompt_single(file_info, content_chunks[0], context)
        else:
            # 大文件：分块处理 + 汇总
            prompt = self._build_prompt_chunked(file_info, content_chunks, context)
        
        # 5. 调用 LLM
        raw_output = self._call_llm(prompt, context)
        
        # 6. 解析输出
        note = self._parse_output(raw_output, file_info, context)
        
        # 7. 记录处理过程
        note.processing_info = {
            "session_id": context.session_id,
            "iteration": context.iteration,
            "prompt_strategy": prompt_strategy,
            "chunks_processed": len(content_chunks),
            "cache_key": cache_key,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 8. 缓存结果
        self._cache_result(cache_key, note)
        
        return note
    
    def execute_with_stream(self, context: ExecutionContext) -> Iterator[str]:
        """
        流式执行笔记生成（实时展示进度）
        
        Yields:
            处理进度信息
        """
        file_info = context.file_info
        
        yield f"📖 读取文件: {file_info.path.name}..."
        content_chunks = self._read_file_smart(file_info.path)
        yield f"✅ 读取完成，共 {len(content_chunks)} 个分块"
        
        yield "🧠 构建提示词..."
        if len(content_chunks) == 1:
            prompt = self._build_prompt_single(file_info, content_chunks[0], context)
        else:
            prompt = self._build_prompt_chunked(file_info, content_chunks, context)
        
        yield "🤖 调用 LLM..."
        
        # 流式调用
        llm = self._get_llm()
        full_response = []
        for chunk in llm.stream(prompt):
            full_response.append(chunk)
            yield chunk  # 实时输出 LLM 生成的内容
        
        raw_output = "".join(full_response)
        
        yield "📝 解析输出..."
        note = self._parse_output(raw_output, file_info, context)
        
        yield f"✅ 完成: {note.title}"
        
        return note
    
    def revise(self, context: ExecutionContext) -> NoteOutput:
        """
        基于验证反馈修复笔记
        
        Args:
            context: 执行上下文（包含 previous_output 和 previous_validation）
            
        Returns:
            修复后的笔记
        """
        if not context.previous_output or not context.previous_validation:
            raise ValueError("Revision requires previous output and validation")
        
        # 构建修复提示词
        fix_prompt = self._build_fix_prompt(context)
        
        # 调用 LLM 修复
        raw_output = self._call_llm(fix_prompt, context)
        
        # 解析修复后的输出
        note = self._parse_output(raw_output, context.file_info, context)
        
        # 标记为修复版本
        note.processing_info["revision"] = True
        note.processing_info["prev_score"] = context.previous_validation.score
        
        return note
    
    def _read_file_smart(self, path: Path) -> List[str]:
        """
        智能读取文件，支持多模态内容提取
        使用 MultimodalExtractor 自动识别文件类型并提取内容
        """
        try:
            # 使用多模态提取器
            extractor = MultimodalExtractor()
            extracted = extractor.extract(path)
            
            if extracted.confidence > 0:
                # 提取成功，返回提取的内容
                return [extracted.text]
            
            # 如果提取器无法处理，回退到基本文本读取
            return self._read_text_file(path)
            
        except Exception as e:
            # 出错时回退到基本读取
            return self._read_text_file(path)
    
    def _read_text_file(self, path: Path) -> List[str]:
        """基础文本文件读取"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 小文件：直接返回
            if len(content) <= self.CHUNK_SIZE:
                return [content]
            
            # 大文件：智能分块
            return self._split_content(content)
            
        except Exception as e:
            return [f"[Error reading file: {e}]"]
    
    def _read_image(self, path: Path) -> str:
        """读取图片（已迁移到 MultimodalExtractor）"""
        # 保留此方法以兼容旧代码，实际逻辑在 MultimodalExtractor 中
        extractor = MultimodalExtractor()
        extracted = extractor.extract(path)
        return extracted.text
    
    def _read_pdf(self, path: Path) -> List[str]:
        """读取 PDF（已迁移到 MultimodalExtractor）"""
        # 保留此方法以兼容旧代码，实际逻辑在 MultimodalExtractor 中
        extractor = MultimodalExtractor()
        extracted = extractor.extract(path)
        return [extracted.text]
    
    def _split_content(self, content: str) -> List[str]:
        """智能分块内容"""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            if current_size + line_size > self.CHUNK_SIZE and current_chunk:
                # 保存当前块
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # 保存最后一块
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        # 限制最大块数
        if len(chunks) > self.MAX_CHUNKS:
            # 合并多余的块
            merged = '\n'.join(chunks[self.MAX_CHUNKS-1:])
            chunks = chunks[:self.MAX_CHUNKS-1] + [merged]
        
        return chunks
    
    def _generate_cache_key(self, file_info, content_chunks: List[str]) -> str:
        """生成缓存键"""
        # 基于文件哈希 + 提示词模板版本 + LLM 配置
        content_hash = hashlib.md5(
            (file_info.hash + str(self.llm_config)).encode()
        ).hexdigest()
        return content_hash
    
    def _check_cache(self, cache_key: str) -> Optional[NoteOutput]:
        """检查缓存"""
        if not self.cache_manager:
            return None
        
        cached = self.cache_manager.get_llm_response(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return NoteOutput(
                    title=data["title"],
                    content=data["content"],
                    tags=data.get("tags", []),
                    links=data.get("links", []),
                    source=data["source"],
                    metadata=data.get("metadata", {}),
                    processing_info={"cached": True, "cache_key": cache_key}
                )
            except Exception:
                pass
        return None
    
    def _cache_result(self, cache_key: str, note: NoteOutput):
        """缓存结果"""
        if not self.cache_manager:
            return
        
        data = {
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "links": note.links,
            "source": note.source,
            "metadata": note.metadata,
        }
        self.cache_manager.set_llm_response(cache_key, json.dumps(data))
    
    def _select_prompt_strategy(self, file_info) -> str:
        """选择提示词策略"""
        return self.PROMPT_TEMPLATES.get(file_info.type, "default")
    
    def _build_prompt_single(self, file_info, content: str, context: ExecutionContext) -> str:
        """构建单块提示词"""
        strategy = self._select_prompt_strategy(file_info)
        
        return f"""You are a knowledge extraction expert. Analyze the following content and generate a structured note.

## Source Information
- File: {file_info.path.name}
- Type: {file_info.type}
- Size: {file_info.size} bytes
- Strategy: {strategy}

## Content
```
{content[:self.CHUNK_SIZE]}
```

## Instructions
1. Extract key concepts and insights
2. Create a clear, structured summary
3. Identify potential links to other topics
4. Suggest relevant tags
5. Assess content complexity and confidence

## Output Format
Return JSON with this structure:
{{
    "title": "Concise, descriptive title",
    "summary": "Brief overview of the content",
    "key_points": ["point 1", "point 2", "point 3"],
    "tags": ["tag1", "tag2", "tag3"],
    "suggested_links": ["Topic A", "Topic B"],
    "metadata": {{
        "complexity": "simple|moderate|complex",
        "confidence": 0.95,
        "word_count": 150
    }}
}}
"""
    
    def _build_prompt_chunked(self, file_info, chunks: List[str], context: ExecutionContext) -> str:
        """构建分块提示词"""
        chunks_text = "\n\n".join([
            f"### Part {i+1}/{len(chunks)}\n```\n{chunk[:self.CHUNK_SIZE]}\n```"
            for i, chunk in enumerate(chunks)
        ])
        
        return f"""You are a knowledge extraction expert. This is a large document split into {len(chunks)} parts. Analyze all parts and generate a comprehensive structured note.

## Source Information
- File: {file_info.path.name}
- Type: {file_info.type}
- Size: {file_info.size} bytes
- Parts: {len(chunks)}

## Content Parts
{chunks_text}

## Instructions
1. Read all parts and understand the complete picture
2. Extract key concepts and insights from the entire document
3. Create a comprehensive, structured summary
4. Identify potential links to other topics
5. Suggest relevant tags
6. Assess overall complexity and confidence

## Output Format
Return JSON with this structure:
{{
    "title": "Comprehensive title reflecting full content",
    "summary": "Detailed overview covering all parts",
    "key_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],
    "tags": ["tag1", "tag2", "tag3", "tag4"],
    "suggested_links": ["Topic A", "Topic B", "Topic C"],
    "metadata": {{
        "complexity": "simple|moderate|complex",
        "confidence": 0.95,
        "parts_processed": {len(chunks)},
        "word_count": 500
    }}
}}
"""
    
    def _build_fix_prompt(self, context: ExecutionContext) -> str:
        """构建修复提示词"""
        current = context.previous_output
        validation = context.previous_validation
        
        issues_text = "\n".join([
            f"- [{i['severity']}] {i['type']}: {i['message']}"
            for i in validation.issues
        ])
        
        suggestions_text = "\n".join([
            f"- {s}"
            for s in validation.suggestions
        ])
        
        return f"""You are a content editor. Fix the following note based on quality feedback.

## Current Content
```
{current.content[:2000]}
```

## Quality Issues
{issues_text}

## Fix Suggestions
{suggestions_text}

## Instructions
1. Fix all issues listed above
2. Keep the core information intact
3. Improve structure and clarity
4. Maintain the same JSON output format
5. Increase quality score

## Output Format
Return JSON with this structure:
{{
    "title": "Improved title",
    "summary": "Improved summary",
    "key_points": ["improved point 1", "improved point 2"],
    "tags": ["tag1", "tag2"],
    "suggested_links": ["Topic A", "Topic B"],
    "metadata": {{
        "complexity": "simple|moderate|complex",
        "confidence": 0.95
    }}
}}
"""
    
    def _call_llm(self, prompt: str, context: ExecutionContext) -> str:
        """调用 LLM（带统计）"""
        self.stats["total_calls"] += 1
        
        try:
            llm = self._get_llm()
            response = llm.complete(prompt)
            
            # 估算 Token 和成本
            estimated_tokens = len(prompt) / 4 + len(response) / 4
            estimated_cost = estimated_tokens * 0.01 / 1000  # GPT-4 价格
            
            self.stats["total_tokens"] += estimated_tokens
            self.stats["total_cost"] += estimated_cost
            
            return response
            
        except Exception as e:
            # 降级处理
            return json.dumps({
                "title": "Error",
                "summary": f"LLM call failed: {str(e)}",
                "key_points": [],
                "tags": ["error"],
                "suggested_links": [],
                "metadata": {"complexity": "simple", "confidence": 0.0, "error": str(e)}
            })
    
    def _parse_output(self, raw_output: str, file_info, context: ExecutionContext) -> NoteOutput:
        """解析 LLM 输出"""
        try:
            # 提取 JSON 部分
            json_str = self._extract_json(raw_output)
            data = json.loads(json_str)
            
            # 构建 Markdown 内容
            content = self._to_markdown(data)
            
            return NoteOutput(
                title=data.get("title", file_info.path.stem),
                content=content,
                tags=data.get("tags", []),
                links=data.get("suggested_links", []),
                source=str(file_info.path),
                metadata=data.get("metadata", {}),
                processing_info={
                    "session_id": context.session_id,
                    "iteration": context.iteration,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # 解析失败，返回原始内容
            return NoteOutput(
                title=file_info.path.stem,
                content=raw_output,
                tags=["parse_error"],
                links=[],
                source=str(file_info.path),
                metadata={"error": "parse_failed", "error_detail": str(e)},
                processing_info={
                    "session_id": context.session_id,
                    "iteration": context.iteration,
                    "timestamp": datetime.now().isoformat(),
                }
            )
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json 代码块
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # 尝试提取花括号内容
        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            return brace_match.group(0)
        
        raise ValueError("No JSON found in response")
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return {
            **self.stats,
            "cache_hit_rate": self.stats["cache_hits"] / max(self.stats["total_calls"], 1),
            "avg_cost_per_call": self.stats["total_cost"] / max(self.stats["total_calls"], 1),
        }
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }
