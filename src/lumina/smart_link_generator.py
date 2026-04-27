"""
Smart Link Generator - 智能链接生成模块
自动识别相关笔记并生成双向链接
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class LinkSuggestion:
    """链接建议"""
    target_id: str
    target_title: str
    similarity: float
    reason: str
    link_type: str  # bidirectional, reference, related


class SmartLinkGenerator:
    """
    智能链接生成器
    
    基于多种策略自动识别相关笔记并生成链接：
    1. 向量相似度 - 语义相似性
    2. 标题匹配 - 标题关键词重叠
    3. 标签重叠 - 共享标签
    4. 内容引用 - 内容中提到的其他笔记
    5. 时间关联 - 同时期创建的笔记
    """
    
    def __init__(
        self,
        vector_store=None,
        similarity_threshold: float = 0.6,
        max_links: int = 10
    ):
        self.vector_store = vector_store
        self.similarity_threshold = similarity_threshold
        self.max_links = max_links
    
    def generate_links(
        self,
        note_id: str,
        note_title: str,
        note_content: str,
        note_tags: List[str],
        all_notes: List[Dict[str, Any]] = None
    ) -> List[LinkSuggestion]:
        """
        为笔记生成链接建议
        
        Args:
            note_id: 当前笔记 ID
            note_title: 笔记标题
            note_content: 笔记内容
            note_tags: 笔记标签
            all_notes: 所有笔记列表（可选）
            
        Returns:
            链接建议列表
        """
        suggestions = []
        
        # 1. 向量相似度搜索
        if self.vector_store:
            vector_links = self._find_by_vector_similarity(
                note_id, note_content, note_title
            )
            suggestions.extend(vector_links)
        
        # 2. 标题关键词匹配
        if all_notes:
            title_links = self._find_by_title_match(
                note_id, note_title, all_notes
            )
            suggestions.extend(title_links)
            
            # 3. 标签重叠
            tag_links = self._find_by_tag_overlap(
                note_id, note_tags, all_notes
            )
            suggestions.extend(tag_links)
            
            # 4. 内容引用检测
            reference_links = self._find_content_references(
                note_id, note_content, all_notes
            )
            suggestions.extend(reference_links)
        
        # 去重和排序
        seen = set()
        unique_suggestions = []
        for sug in sorted(suggestions, key=lambda x: x.similarity, reverse=True):
            if sug.target_id not in seen and sug.target_id != note_id:
                seen.add(sug.target_id)
                unique_suggestions.append(sug)
        
        return unique_suggestions[:self.max_links]
    
    def _find_by_vector_similarity(
        self,
        note_id: str,
        content: str,
        title: str
    ) -> List[LinkSuggestion]:
        """基于向量相似度查找相关笔记"""
        suggestions = []
        
        try:
            # 使用向量存储搜索
            query = f"{title}\n{content[:500]}"
            results = self.vector_store.search(query, n_results=self.max_links * 2)
            
            for result in results:
                if result.document.id != note_id:
                    suggestions.append(LinkSuggestion(
                        target_id=result.document.id,
                        target_title=result.document.metadata.get("title", "Unknown"),
                        similarity=result.score,
                        reason=f"语义相似度: {result.score:.2f}",
                        link_type="related"
                    ))
        except Exception:
            pass
        
        return suggestions
    
    def _find_by_title_match(
        self,
        note_id: str,
        note_title: str,
        all_notes: List[Dict[str, Any]]
    ) -> List[LinkSuggestion]:
        """基于标题关键词匹配"""
        suggestions = []
        
        # 提取标题关键词
        keywords = self._extract_keywords(note_title)
        
        for other in all_notes:
            if other.get("id") == note_id:
                continue
            
            other_title = other.get("title", "")
            other_keywords = self._extract_keywords(other_title)
            
            # 计算关键词重叠
            overlap = set(keywords) & set(other_keywords)
            if overlap:
                similarity = len(overlap) / max(len(keywords), len(other_keywords))
                if similarity >= self.similarity_threshold:
                    suggestions.append(LinkSuggestion(
                        target_id=other.get("id", ""),
                        target_title=other_title,
                        similarity=similarity,
                        reason=f"标题关键词重叠: {', '.join(overlap)}",
                        link_type="related"
                    ))
        
        return suggestions
    
    def _find_by_tag_overlap(
        self,
        note_id: str,
        note_tags: List[str],
        all_notes: List[Dict[str, Any]]
    ) -> List[LinkSuggestion]:
        """基于标签重叠查找相关笔记"""
        suggestions = []
        
        if not note_tags:
            return suggestions
        
        note_tags_set = set(t.lower() for t in note_tags)
        
        for other in all_notes:
            if other.get("id") == note_id:
                continue
            
            other_tags = other.get("tags", [])
            other_tags_set = set(t.lower() for t in other_tags)
            
            overlap = note_tags_set & other_tags_set
            if overlap:
                similarity = len(overlap) / max(len(note_tags_set), len(other_tags_set))
                if similarity >= 0.3:  # 标签重叠阈值较低
                    suggestions.append(LinkSuggestion(
                        target_id=other.get("id", ""),
                        target_title=other.get("title", ""),
                        similarity=similarity,
                        reason=f"共享标签: {', '.join(overlap)}",
                        link_type="related"
                    ))
        
        return suggestions
    
    def _find_content_references(
        self,
        note_id: str,
        note_content: str,
        all_notes: List[Dict[str, Any]]
    ) -> List[LinkSuggestion]:
        """检测内容中引用的其他笔记"""
        suggestions = []
        
        for other in all_notes:
            if other.get("id") == note_id:
                continue
            
            other_title = other.get("title", "")
            other_id = other.get("id", "")
            
            # 检查内容中是否提到其他笔记的标题
            if other_title and len(other_title) > 3:
                # 使用模糊匹配
                similarity = self._fuzzy_match(note_content, other_title)
                if similarity > 0.7:
                    suggestions.append(LinkSuggestion(
                        target_id=other_id,
                        target_title=other_title,
                        similarity=similarity,
                        reason=f"内容引用: 提到 '{other_title}'",
                        link_type="reference"
                    ))
            
            # 检查是否提到笔记 ID
            if other_id in note_content:
                suggestions.append(LinkSuggestion(
                    target_id=other_id,
                    target_title=other_title,
                    similarity=0.9,
                    reason=f"直接引用笔记 ID",
                    link_type="reference"
                ))
        
        return suggestions
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        words = re.findall(r'\b[A-Za-z\u4e00-\u9fff]{2,}\b', text.lower())
        
        # 过滤常见停用词
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                     'could', 'should', 'may', 'might', 'must', 'shall', 'can',
                     'need', 'dare', 'ought', 'used', 'to', 'of', 'in', 'for',
                     'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
                     'during', 'before', 'after', 'above', 'below', 'between',
                     'under', 'again', 'further', 'then', 'once', 'here', 'there',
                     'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more',
                     'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
                     'own', 'same', 'so', 'than', 'too', 'very', 'just', 'and',
                     'but', 'if', 'or', 'because', 'until', 'while', 'this', 'that',
                     'these', 'those', 'am', 'are', 'was', 'were', 'being', 'been'}
        
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _fuzzy_match(self, text: str, pattern: str) -> float:
        """模糊匹配"""
        # 使用 SequenceMatcher
        matcher = SequenceMatcher(None, text.lower(), pattern.lower())
        return matcher.ratio()
    
    def generate_bidirectional_links(
        self,
        note_a_id: str,
        note_b_id: str,
        all_notes: List[Dict[str, Any]]
    ) -> Tuple[LinkSuggestion, LinkSuggestion]:
        """
        生成双向链接
        
        Returns:
            (A->B 的链接, B->A 的链接)
        """
        note_a = next((n for n in all_notes if n.get("id") == note_a_id), None)
        note_b = next((n for n in all_notes if n.get("id") == note_b_id), None)
        
        if not note_a or not note_b:
            return None, None
        
        link_a_to_b = LinkSuggestion(
            target_id=note_b_id,
            target_title=note_b.get("title", ""),
            similarity=0.8,
            reason="双向链接",
            link_type="bidirectional"
        )
        
        link_b_to_a = LinkSuggestion(
            target_id=note_a_id,
            target_title=note_a.get("title", ""),
            similarity=0.8,
            reason="双向链接",
            link_type="bidirectional"
        )
        
        return link_a_to_b, link_b_to_a
    
    def suggest_link_improvements(
        self,
        note_id: str,
        current_links: List[str],
        all_notes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        建议链接改进
        
        Args:
            note_id: 当前笔记 ID
            current_links: 当前已有的链接
            all_notes: 所有笔记
            
        Returns:
            改进建议
        """
        note = next((n for n in all_notes if n.get("id") == note_id), None)
        if not note:
            return {"error": "Note not found"}
        
        # 生成建议
        suggested = self.generate_links(
            note_id,
            note.get("title", ""),
            note.get("content", ""),
            note.get("tags", []),
            all_notes
        )
        
        # 找出缺失的链接
        current_link_ids = set(current_links)
        missing = [s for s in suggested if s.target_id not in current_link_ids]
        
        # 找出可能多余的链接
        suggested_ids = {s.target_id for s in suggested}
        potentially_redundant = [
            link_id for link_id in current_links
            if link_id not in suggested_ids
        ]
        
        return {
            "current_link_count": len(current_links),
            "suggested_link_count": len(suggested),
            "missing_links": [
                {
                    "target_id": s.target_id,
                    "target_title": s.target_title,
                    "reason": s.reason,
                    "similarity": s.similarity
                }
                for s in missing[:5]
            ],
            "potentially_redundant": potentially_redundant[:5],
            "recommendations": [
                f"建议添加 {len(missing)} 个新链接",
                f"当前链接质量: {len([s for s in suggested if s.target_id in current_link_ids])}/{len(current_links)}"
            ]
        }
    
    def format_link_for_plugin(
        self,
        suggestion: LinkSuggestion,
        plugin_name: str = "obsidian"
    ) -> str:
        """
        根据插件格式化链接
        
        Args:
            suggestion: 链接建议
            plugin_name: 插件名称
            
        Returns:
            格式化后的链接字符串
        """
        if plugin_name == "obsidian":
            return f"[[{suggestion.target_title}]]"
        elif plugin_name == "plain":
            return f"[{suggestion.target_title}]({suggestion.target_id})"
        else:
            return f"[{suggestion.target_title}]"
