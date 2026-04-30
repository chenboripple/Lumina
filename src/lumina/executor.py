"""
Executor - 智能执行模块 (Agent 增强版)
基于 LLM 生成结构化笔记，支持缓存、分块、多策略执行
"""

import os
import json
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterator
from dataclasses import dataclass, field
from datetime import datetime

from .llm import get_llm_provider, LLMConfig, BaseLLMProvider
from .cache import CacheManager
from .history import HistoryManager, ProcessingRecord
from .core.multimodal_extractor import MultimodalExtractor
from .scene_detector import SceneDetector, DocumentScene
from .content_filter import ContentFilter, FilterResult


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
        history_manager: HistoryManager = None,
        enable_content_filter: bool = True,
        enable_scene_detection: bool = True,
    ):
        self.llm_config = llm_config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.history_manager = history_manager
        
        # 初始化场景检测器和内容过滤器
        self.scene_detector = SceneDetector() if enable_scene_detection else None
        self.content_filter = ContentFilter() if enable_content_filter else None
        
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

    def _log(self, message: str, level: str = "info"):
        """输出执行器日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level.upper()}] Executor: {message}")
    
    def _get_llm(self) -> BaseLLMProvider:
        """获取 LLM Provider（已预初始化）"""
        return self.llm_provider
    
    def execute(self, context: ExecutionContext) -> NoteOutput:
        """
        执行笔记生成（Agent 增强版）
        
        增强功能：
        1. 内容过滤 - 跳过无价值文档
        2. 场景检测 - 识别文档场景并匹配提取模板
        
        Args:
            context: 执行上下文
            
        Returns:
            生成的笔记
        """
        file_info = context.file_info
        
        # 1. 读取文件内容（智能分块）
        content_chunks = self._read_file_smart(file_info.path)
        full_content = "\n".join(content_chunks)
        content_policy_metadata: Dict[str, Any] = {}
        
        # 2. 内容过滤检查
        if self.content_filter:
            filter_result = self.content_filter.check(file_info.path, full_content)
            if not filter_result.should_process:
                self._log(
                    f"Filtered {file_info.path}: {filter_result.reason}",
                    level="info"
                )
                return NoteOutput(
                    title=f"[FILTERED] {file_info.path.stem}",
                    content=f"_Content filtered: {filter_result.reason}_",
                    tags=["filtered"],
                    links=[],
                    source=str(file_info.path),
                    metadata={
                        "filtered": True,
                        "filter_reason": filter_result.reason,
                        "filter_confidence": filter_result.confidence,
                    },
                    processing_info={
                        "session_id": context.session_id,
                        "iteration": context.iteration,
                        "filtered": True,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            content_policy_metadata = dict(filter_result.metadata or {})
            sanitized_content, transform_meta = self.content_filter.sanitize_content(
                full_content,
                content_policy_metadata,
            )
            if sanitized_content != full_content:
                full_content = sanitized_content
                content_chunks = [full_content] if len(full_content) <= self.CHUNK_SIZE else self._split_content(full_content)
            content_policy_metadata.update(transform_meta)
            file_info.metadata["content_policy"] = content_policy_metadata

            guidance = self.content_filter.build_processing_guidance(content_policy_metadata)
            if guidance:
                file_info.metadata["content_guidance"] = guidance
        
        # 3. 场景检测
        detected_scene = None
        scene_confidence = 0.0
        if self.scene_detector:
            scene_result = self.scene_detector.detect(file_info.path, full_content)
            detected_scene = scene_result.scene
            scene_confidence = scene_result.confidence
            self._log(
                f"Detected scene for {file_info.path.name}: {detected_scene.value} "
                f"(confidence: {scene_confidence:.2f})"
            )
        
        # 4. 检查缓存
        cache_key = self._generate_cache_key(file_info, content_chunks, detected_scene)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            self.stats["cache_hits"] += 1
            return cached_result
        
        self.stats["cache_misses"] += 1
        
        # 5. 选择提示词策略
        prompt_strategy = self._select_prompt_strategy(file_info)
        
        # 6. 构建提示词（使用场景模板或默认模板）
        if detected_scene and self.scene_detector:
            # 使用场景化提示词
            template = self.scene_detector.get_template(detected_scene)
            if len(content_chunks) == 1:
                prompt = self._build_scene_prompt(
                    template, file_info, content_chunks[0], context
                )
            else:
                prompt = self._build_scene_prompt_chunked(
                    template, file_info, content_chunks, context
                )
        else:
            # 使用默认提示词
            if len(content_chunks) == 1:
                prompt = self._build_prompt_single(file_info, content_chunks[0], context)
            else:
                prompt = self._build_prompt_chunked(file_info, content_chunks, context)
        
        # 7. 调用 LLM
        raw_output = self._call_llm(prompt, context)
        
        # 8. 解析输出（使用场景化格式化）
        if detected_scene and self.scene_detector:
            template = self.scene_detector.get_template(detected_scene)
            note = self._parse_scene_output(raw_output, file_info, context, template)
        else:
            note = self._parse_output(raw_output, file_info, context)

        if self.content_filter and content_policy_metadata:
            note = self._apply_content_policy(note, content_policy_metadata)
        
        # 9. 记录处理过程
        note.processing_info = {
            "session_id": context.session_id,
            "iteration": context.iteration,
            "prompt_strategy": prompt_strategy,
            "detected_scene": detected_scene.value if detected_scene else None,
            "scene_confidence": scene_confidence,
            "chunks_processed": len(content_chunks),
            "cache_key": cache_key,
            "timestamp": datetime.now().isoformat(),
        }
        
        # 10. 缓存结果
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

            # 对二进制/多模态类型，始终使用提取器结果，避免回退到 UTF-8 文本读取导致解码错误
            if extracted.content_type in {"pdf", "image", "audio", "video", "code", "unknown"}:
                return [extracted.text]

            if extracted.confidence > 0:
                # 文本提取成功，返回提取的内容
                return [extracted.text]

            # 仅在可判定为普通文本文件时回退到基础文本读取
            return self._read_text_file(path)
            
        except Exception as e:
            # 出错时回退到基本读取
            self._log(f"Multimodal extraction failed for {path}: {e}", level="warning")
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
            self._log(f"Text read failed for {path}: {e}", level="error")
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
    
    def _generate_cache_key(self, file_info, content_chunks: List[str], scene: Optional[DocumentScene] = None) -> str:
        """生成缓存键"""
        # 基于文件哈希 + 提示词模板版本 + LLM 配置 + 场景
        scene_str = scene.value if scene else "default"
        content_hash = hashlib.md5(
            (file_info.hash + scene_str + str(self.llm_config)).encode()
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
            except Exception as e:
                self._log(f"Failed to deserialize cached LLM response for {cache_key}: {e}", level="warning")
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
    
    def _build_scene_prompt(self, template, file_info, content: str, context: ExecutionContext) -> str:
        """构建场景化单块提示词"""
        guidance = file_info.metadata.get("content_guidance", "")
        if guidance:
            content = f"[Extraction Guidance]\n{guidance}\n\n{content}"
        return template.prompt_template.format(
            filename=file_info.path.name,
            file_type=file_info.type,
            content=content[:self.CHUNK_SIZE]
        )
    
    def _build_scene_prompt_chunked(self, template, file_info, chunks: List[str], context: ExecutionContext) -> str:
        """构建场景化分块提示词"""
        guidance = file_info.metadata.get("content_guidance", "")
        chunks_text = "\n\n".join([
            f"### Part {i+1}/{len(chunks)}\n```\n{chunk[:self.CHUNK_SIZE]}\n```"
            for i, chunk in enumerate(chunks)
        ])
        if guidance:
            chunks_text = f"[Extraction Guidance]\n{guidance}\n\n{chunks_text}"
        
        # 在模板中替换内容部分
        prompt = template.prompt_template.format(
            filename=file_info.path.name,
            file_type=file_info.type,
            content=f"[This is a large document split into {len(chunks)} parts]\n\n{chunks_text}"
        )
        return prompt
    
    def _parse_scene_output(self, raw_output: str, file_info, context: ExecutionContext, template) -> NoteOutput:
        """解析场景化 LLM 输出"""
        try:
            # 提取 JSON 部分
            json_str = self._extract_json(raw_output)
            data = json.loads(json_str)
            
            # 使用场景化格式化函数
            if template.formatter:
                content = template.formatter(data)
            else:
                content = self._to_markdown(data)
            
            return NoteOutput(
                title=self._resolve_note_title(data.get("title", file_info.path.stem), file_info, data),
                content=content,
                tags=data.get("tags", []),
                links=data.get("suggested_links", []),
                source=str(file_info.path),
                metadata={
                    **data.get("metadata", {}),
                    "scene": template.scene.value,
                },
                processing_info={
                    "session_id": context.session_id,
                    "iteration": context.iteration,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            self._log(
                f"Failed to parse scene output for {file_info.path}: {e}",
                level="warning"
            )
            return NoteOutput(
                title=self._resolve_note_title(file_info.path.stem, file_info),
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
    
    def _build_prompt_single(self, file_info, content: str, context: ExecutionContext) -> str:
        """构建单块提示词"""
        strategy = self._select_prompt_strategy(file_info)
        guidance = file_info.metadata.get("content_guidance", "")
        guidance_block = f"6. {guidance}\n" if guidance else ""
        
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
{guidance_block}

## Output Format
Return JSON with this structure:
{{
    "title": "Clear topical title. Do not copy raw filenames, date folders, Collection, Append to, or generic placeholders.",
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
        guidance = file_info.metadata.get("content_guidance", "")
        guidance_block = f"7. {guidance}\n" if guidance else ""
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
{guidance_block}

## Output Format
Return JSON with this structure:
{{
    "title": "Clear topical title reflecting the document theme. Never reuse raw filenames or generic folder labels.",
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
            f"- [{i.severity}] {i.type}: {i.message}"
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
            self._log(
                f"LLM request failed for {context.file_info.path} round={context.iteration + 1}: {e}",
                level="error"
            )
            raise
    
    def _parse_output(self, raw_output: str, file_info, context: ExecutionContext) -> NoteOutput:
        """解析 LLM 输出"""
        try:
            # 提取 JSON 部分
            json_str = self._extract_json(raw_output)
            data = json.loads(json_str)
            
            # 构建 Markdown 内容
            content = self._to_markdown(data)
            
            return NoteOutput(
                title=self._resolve_note_title(data.get("title", file_info.path.stem), file_info, data),
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
            self._log(
                f"Failed to parse LLM output for {file_info.path} round={context.iteration + 1}: {e}",
                level="warning"
            )
            return NoteOutput(
                title=self._resolve_note_title(file_info.path.stem, file_info),
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

    def _apply_content_policy(self, note: NoteOutput, content_policy_metadata: Dict[str, Any]) -> NoteOutput:
        """在输出阶段执行兜底脱敏，并记录内容策略。"""
        if not self.content_filter:
            return note

        masked_content, transform_meta = self.content_filter.sanitize_content(
            note.content,
            {
                **content_policy_metadata,
                "downgrade_sample_facts": False,
                "mask_sensitive": content_policy_metadata.get("mask_sensitive", False),
            },
        )
        note.content = masked_content
        note.title = self._resolve_note_title(
            self.content_filter.mask_sensitive_text(note.title),
            None,
            {"metadata": note.metadata},
        )
        note.tags = [self.content_filter.mask_sensitive_text(tag) for tag in note.tags]
        note.links = [self.content_filter.mask_sensitive_text(link) for link in note.links]
        note.metadata = {
            **note.metadata,
            "content_policy": {
                key: value
                for key, value in {**content_policy_metadata, **transform_meta}.items()
                if key not in {"reason", "confidence"}
            },
        }
        return note

    def _resolve_note_title(self, candidate: str, file_info=None, parsed_data: Optional[Dict[str, Any]] = None) -> str:
        """规范化标题，避免落回文件名、目录名或占位词。"""
        parsed_data = parsed_data or {}
        metadata = dict(getattr(file_info, "metadata", {}) or {})
        extra_metadata = parsed_data.get("metadata", {}) if isinstance(parsed_data.get("metadata", {}), dict) else {}
        metadata.update(extra_metadata)

        title = re.sub(r'[_\-]+', ' ', str(candidate or '').strip())
        title = re.sub(r'\s+', ' ', title).strip(" :._-")
        preferred = str(metadata.get("title_hint") or metadata.get("cluster_title") or "").strip()

        if metadata.get("overview_scope") == "global":
            preferred = preferred or "全局知识地图"
        elif metadata.get("overview_scope") == "project":
            preferred = preferred or "项目总览"

        if self._is_generic_title(title, file_info):
            if preferred:
                return preferred
            derived = self._derive_title_from_data(parsed_data, metadata)
            if derived:
                return derived

        if preferred and title.lower().startswith(("collection", "append to", "cluster", "untitled")):
            return preferred

        return title or preferred or "主题笔记"

    def _is_generic_title(self, title: str, file_info=None) -> bool:
        normalized = str(title or "").strip().lower()
        if not normalized:
            return True
        if normalized.startswith(("collection", "append to", "cluster", "untitled", "summary")):
            return True
        if re.fullmatch(r'\d{4}([_-]?\d{2})?', normalized):
            return True
        if len(normalized) < 4:
            return True
        if file_info is not None:
            file_stem = re.sub(r'[_\-]+', ' ', file_info.path.stem.lower()).strip()
            if normalized == file_stem:
                return True
        return False

    def _derive_title_from_data(self, parsed_data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        scene = str(metadata.get("scene", "")).strip().lower()
        candidates: List[str] = []
        for key in ["summary", "abstract", "overview", "background", "research_problem", "context", "scope", "system"]:
            value = parsed_data.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        for key in ["key_points", "findings", "goals", "design_goals"]:
            value = parsed_data.get(key)
            if isinstance(value, list) and value:
                first = str(value[0]).strip()
                if first:
                    candidates.append(first)

        for raw in candidates:
            topic = re.split(r'[。；;:：\n,.，]', raw, maxsplit=1)[0].strip()
            topic = re.sub(r'^(本文|该文档|这个文档|本说明|该项目|主要|用于|关于)', '', topic).strip()
            topic = re.sub(r'\s+', ' ', topic)
            if len(topic) < 4:
                continue
            if scene in {"ops_doc", "technical_doc"} and not re.search(r'手册|指南|说明|规范|总览', topic):
                return f"{topic}操作手册"
            if scene in {"requirements", "prd", "design_doc"} and not re.search(r'需求|设计|方案|说明', topic):
                return f"{topic}设计说明"
            if scene in {"meeting_notes", "chat_log", "email"} and not re.search(r'纪要|沟通|讨论', topic):
                return f"{topic}沟通纪要"
            if re.search(r'数据|字段|表|sql|映射|订单', topic, re.IGNORECASE) and not re.search(r'解析|说明|总结', topic):
                return f"{topic}数据解析"
            return topic

        return str(metadata.get("title_hint") or metadata.get("cluster_title") or "").strip()
    
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
