"""
Content Analyzer - 内容预分析模块
轻量级 LLM 调用，生成文件简述用于 Planner 决策
支持缓存、批量处理、双模型路由
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .llm import get_llm_provider, LLMConfig, BaseLLMProvider
from .cache import CacheManager
from .utils.file_utils import get_file_hash


@dataclass
class ContentBrief:
    """文件内容简述"""
    file_path: str
    file_hash: str
    brief_summary: str  # 一句话简述
    content_type: str   # 内容类型：technical_doc, meeting_notes, code, etc.
    key_topics: List[str]  # 关键主题
    estimated_value: float  # 预估价值 0-1
    suggested_action: str  # 建议操作：process, skip, merge
    merge_candidates: List[str]  # 建议合并的文件
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchBriefResult:
    """批量简述结果"""
    briefs: List[ContentBrief]
    total_tokens: int
    total_cost: float
    cache_hits: int
    cache_misses: int
    duration: float


class ContentAnalyzer:
    """
    内容预分析器
    
    职责：
    1. 读取文件内容
    2. 调用轻量 LLM 生成简述
    3. 缓存结果避免重复分析
    4. 支持批量处理提高效率
    
    与 Planner 的关系：
    - Analyzer 提供 "what"（这是什么内容）
    - Planner 决定 "how"（如何处理）
    """
    
    # 提示词模板
    BRIEF_PROMPT_TEMPLATE = """You are a document analysis expert. Analyze the following document and provide a structured brief.

Document Path: {file_path}
Document Type: {file_type}
Content Preview (first 3000 chars):
```
{content_preview}
```

Provide a JSON response with these fields:
{{
    "brief_summary": "One sentence summary of the document",
    "content_type": "One of: technical_doc, meeting_notes, code, requirements, design_doc, knowledge_base, personal_notes, data, other",
    "key_topics": ["topic1", "topic2", "topic3"],
    "estimated_value": 0.0-1.0,  // How valuable is this content for knowledge management
    "suggested_action": "One of: process, skip, merge",  // Whether to generate a full note
    "reasoning": "Brief explanation of the suggested action"
}}

Guidelines:
- brief_summary: Maximum 100 characters, capture the essence
- content_type: Be specific, use the categories provided
- estimated_value: Consider uniqueness, actionable insights, long-term reference value
- suggested_action: 
  * "process" for high-value standalone documents
  * "skip" for trivial, duplicate, or low-value content
  * "merge" for short related documents that should be combined
"""

    def __init__(
        self,
        llm_config: Dict[str, Any] = None,
        cache_manager: CacheManager = None,
        max_content_length: int = 3000,
    ):
        self.llm_config = llm_config or {}
        self.cache = cache_manager or CacheManager()
        self.max_content_length = max_content_length
        
        # 初始化轻量 LLM（使用配置中的轻量模型）
        try:
            self.llm_provider = get_llm_provider(self.llm_config)
        except Exception as e:
            raise ValueError(f"LLM 配置无效: {str(e)}") from e
        
        # 统计
        self.stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    def analyze_file(self, file_path: Path, file_type: str = "unknown", max_length: Optional[int] = None) -> ContentBrief:
        """
        分析单个文件，返回内容简述
        
        Args:
            file_path: 文件路径
            file_type: 文件类型（用于提示词）
            
        Returns:
            ContentBrief 对象
        """
        # 计算文件哈希用于缓存
        file_hash = get_file_hash(file_path)
        
        # 检查缓存
        cached = self._get_cached_brief(file_hash)
        if cached:
            self.stats["cache_hits"] += 1
            cached.file_path = str(file_path)  # 更新路径（可能移动过）
            return cached
        
        self.stats["cache_misses"] += 1
        
        # 读取文件内容
        effective_max = max_length if max_length is not None else self.max_content_length
        content = self._read_file_content(file_path, effective_max)
        if not content:
            # 空文件或读取失败
            return ContentBrief(
                file_path=str(file_path),
                file_hash=file_hash,
                brief_summary="[Empty or unreadable file]",
                content_type="other",
                key_topics=[],
                estimated_value=0.0,
                suggested_action="skip",
                merge_candidates=[],
                metadata={"error": "empty_or_unreadable"}
            )
        
        # 生成简述
        brief = self._generate_brief(file_path, file_type, content, file_hash)
        
        # 缓存结果
        self._cache_brief(file_hash, brief)
        
        return brief

    def analyze_batch(self, file_infos: List[Any]) -> BatchBriefResult:
        """
        批量分析文件
        
        Args:
            file_infos: FileInfo 对象列表
            
        Returns:
            BatchBriefResult 包含所有简述和统计
        """
        import time
        start_time = time.time()
        
        briefs = []
        for file_info in file_infos:
            try:
                brief = self.analyze_file(file_info.path, file_info.type)
                briefs.append(brief)
            except Exception as e:
                # 单个文件失败不影响整体
                briefs.append(ContentBrief(
                    file_path=str(file_info.path),
                    file_hash=file_info.hash,
                    brief_summary=f"[Analysis failed: {str(e)}]",
                    content_type="other",
                    key_topics=[],
                    estimated_value=0.0,
                    suggested_action="skip",
                    merge_candidates=[],
                    metadata={"error": str(e)}
                ))
        
        duration = time.time() - start_time
        
        return BatchBriefResult(
            briefs=briefs,
            total_tokens=self.stats["total_tokens"],
            total_cost=self.stats["total_cost"],
            cache_hits=self.stats["cache_hits"],
            cache_misses=self.stats["cache_misses"],
            duration=duration
        )

    def _read_file_content(self, file_path: Path, max_length: Optional[int] = None) -> str:
        """读取文件内容，限制长度"""
        limit = max_length if max_length is not None else self.max_content_length
        try:
            # 根据文件类型选择读取方式
            suffix = file_path.suffix.lower()
            
            if suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                # 图片文件返回标记
                return "[Image file - visual content]"
            
            if suffix == '.pdf':
                # PDF 尝试提取文本
                try:
                    from .core.multimodal_extractor import MultimodalExtractor
                    extractor = MultimodalExtractor()
                    result = extractor.extract(file_path)
                    return result.text[:limit] if result.text else "[PDF - no extractable text]"
                except:
                    return "[PDF file]"
            
            # 文本文件直接读取
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read(limit)
                
        except Exception as e:
            return f"[Error reading file: {str(e)}]"

    def _generate_brief(self, file_path: Path, file_type: str, content: str, file_hash: str) -> ContentBrief:
        """调用 LLM 生成简述"""
        # 截取内容预览
        content_preview = content[:self.max_content_length]
        if len(content) > self.max_content_length:
            content_preview += "\n... [truncated]"
        
        # 构建提示词
        prompt = self.BRIEF_PROMPT_TEMPLATE.format(
            file_path=file_path,
            file_type=file_type,
            content_preview=content_preview
        )
        
        # 调用 LLM
        response_text = self.llm_provider.complete(prompt)
        self.stats["total_calls"] += 1

        # 解析响应
        try:
            result = self._parse_response(response_text)
        except Exception as e:
            # 解析失败返回默认值
            result = {
                "brief_summary": f"[Parse error: {str(e)}]",
                "content_type": "other",
                "key_topics": [],
                "estimated_value": 0.5,
                "suggested_action": "process",
                "reasoning": "Default to process due to parse error"
            }
        
        return ContentBrief(
            file_path=str(file_path),
            file_hash=file_hash,
            brief_summary=result.get("brief_summary", ""),
            content_type=result.get("content_type", "other"),
            key_topics=result.get("key_topics", []),
            estimated_value=result.get("estimated_value", 0.5),
            suggested_action=result.get("suggested_action", "process"),
            merge_candidates=[],  # 由 Planner 填充
            metadata={
                "reasoning": result.get("reasoning", ""),
                "analyzed_at": datetime.now().isoformat(),
            }
        )

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        # 尝试直接解析 JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json 代码块
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # 尝试提取花括号内容
        brace_match = re.search(r'\{.*\}', content, re.DOTALL)
        if brace_match:
            return json.loads(brace_match.group(0))
        
        raise ValueError("No valid JSON found in response")

    def _get_cached_brief(self, file_hash: str) -> Optional[ContentBrief]:
        """从缓存获取简述"""
        if not self.cache:
            return None
        
        cache_key = hashlib.md5(f"content_brief:{file_hash}".encode()).hexdigest()
        cached_data = self.cache.get_llm_response(cache_key)
        
        if cached_data:
            try:
                data = json.loads(cached_data)
                return ContentBrief(**data)
            except Exception:
                return None
        
        return None

    def _cache_brief(self, file_hash: str, brief: ContentBrief):
        """缓存简述结果"""
        if not self.cache:
            return
        
        cache_key = hashlib.md5(f"content_brief:{file_hash}".encode()).hexdigest()
        cache_data = {
            "file_path": brief.file_path,
            "file_hash": brief.file_hash,
            "brief_summary": brief.brief_summary,
            "content_type": brief.content_type,
            "key_topics": brief.key_topics,
            "estimated_value": brief.estimated_value,
            "suggested_action": brief.suggested_action,
            "merge_candidates": brief.merge_candidates,
            "metadata": brief.metadata,
        }
        self.cache.set_llm_response(cache_key, json.dumps(cache_data), ttl_days=30)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "cache_hit_rate": self.stats["cache_hits"] / max(self.stats["total_calls"], 1),
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
