"""
Document Clustering - 主题聚合模块
将相关短文档合并、多篇文档总结、追加到已有笔记，同时保留关联关系
"""

import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class ClusterStrategy(Enum):
    """聚合策略"""
    COMBINE_SHORT_DOCS = "combine_short_docs"  # 短文档合并
    SUMMARIZE_MULTIPLE = "summarize_multiple"  # 多篇文档总结
    APPEND_TO_EXISTING = "append_to_existing"  # 追加到已有笔记


@dataclass
class DocumentCluster:
    """文档簇"""
    cluster_id: str
    files: List[Path]
    strategy: ClusterStrategy
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClusterResult:
    """聚合格式化结果"""
    cluster: DocumentCluster
    title: str
    content: str
    sources: List[str]  # 源文件列表，保留关联关系
    tags: List[str]
    metadata: Dict[str, Any]


class DocumentClusterer:
    """
    文档聚合器
    
    策略：
    1. 短文档合并 - 将同一目录下的短文档（<10KB）合并为一篇笔记
    2. 主题聚类 - 基于语义相似度将相关文档聚合并总结
    3. 追加模式 - 当检测到与已有笔记主题相同时，追加而非新建
    """
    
    # 短文档阈值
    SHORT_DOC_THRESHOLD = 10 * 1024  # 10KB
    
    # 每个簇最多包含的文档数
    MAX_FILES_PER_CLUSTER = 10
    
    def __init__(self):
        self.stats = {
            "total_files": 0,
            "created_clusters": 0,
            "combined_files": 0,
            "individual_files": 0,
        }
    
    def cluster(
        self,
        files: List[Path],
        existing_notes: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[DocumentCluster], List[Path]]:
        """
        将文档聚合为簇
        
        Args:
            files: 待处理的文件列表
            existing_notes: 已有的笔记列表（用于追加模式）
            
        Returns:
            (clusters, individual_files) - 文档簇列表和独立处理的文件列表
        """
        self.stats["total_files"] = len(files)
        
        # 1. 分离短文档和长文档
        short_docs, long_docs = self._split_by_size(files)
        
        # 2. 对短文档按目录聚类
        clusters = self._cluster_by_directory(short_docs)
        
        # 3. 检查是否有可以追加到已有笔记的文档
        if existing_notes:
            clusters, remaining_long_docs = self._match_to_existing(long_docs, existing_notes)
        else:
            remaining_long_docs = long_docs
        
        # 4. 剩余的长文档独立处理
        self.stats["individual_files"] = len(remaining_long_docs)
        
        return clusters, remaining_long_docs
    
    def _split_by_size(self, files: List[Path]) -> Tuple[List[Path], List[Path]]:
        """按文件大小分离"""
        short_docs = []
        long_docs = []
        
        for file in files:
            try:
                size = file.stat().st_size
                if size < self.SHORT_DOC_THRESHOLD:
                    short_docs.append(file)
                else:
                    long_docs.append(file)
            except Exception:
                long_docs.append(file)
        
        return short_docs, long_docs
    
    def _cluster_by_directory(self, files: List[Path]) -> List[DocumentCluster]:
        """按目录聚类短文档"""
        clusters = []
        
        # 按父目录分组
        dir_groups = defaultdict(list)
        for file in files:
            parent = str(file.parent)
            dir_groups[parent].append(file)
        
        # 创建目录簇
        for dir_path, dir_files in dir_groups.items():
            if len(dir_files) >= 2:  # 至少2个文件才合并
                # 按文件数量分批（不超过MAX_FILES_PER_CLUSTER）
                for i in range(0, len(dir_files), self.MAX_FILES_PER_CLUSTER):
                    batch = dir_files[i:i + self.MAX_FILES_PER_CLUSTER]
                    
                    cluster_id = hashlib.md5(f"{dir_path}:{i}".encode()).hexdigest()[:8]
                    dir_name = Path(dir_path).name or "cluster"
                    
                    cluster = DocumentCluster(
                        cluster_id=f"dir_{cluster_id}",
                        files=batch,
                        strategy=ClusterStrategy.COMBINE_SHORT_DOCS,
                        title=f"Collection: {dir_name}",
                        description=f"Combined from {len(batch)} short documents",
                        metadata={
                            "directory": dir_path,
                            "file_count": len(batch)
                        }
                    )
                    clusters.append(cluster)
                    self.stats["created_clusters"] += 1
                    self.stats["combined_files"] += len(batch)
            elif len(dir_files) == 1:
                # 单个短文档独立处理，不算入cluster
                self.stats["individual_files"] += 1
        
        return clusters
    
    def _match_to_existing(
        self,
        files: List[Path],
        existing_notes: List[Dict[str, Any]]
    ) -> Tuple[List[DocumentCluster], List[Path]]:
        """匹配到已有笔记（追加模式）"""
        clusters = []
        unmatched = []
        
        # 简化实现：只做文件名匹配
        # 实际应该用向量相似度
        existing_titles = {note.get('title', '').lower() for note in existing_notes}
        
        for file in files:
            file_name = file.stem.lower()
            
            # 检查文件名是否与已有标题匹配
            matched = False
            for title in existing_titles:
                if file_name in title or title in file_name:
                    # 创建追加模式的簇
                    cluster = DocumentCluster(
                        cluster_id=f"append_{hashlib.md5(str(file).encode()).hexdigest()[:8]}",
                        files=[file],
                        strategy=ClusterStrategy.APPEND_TO_EXISTING,
                        title=f"Append to: {title}",
                        description=f"Append to existing note: {title}",
                        metadata={
                            "append_to": title,
                            "source_file": str(file)
                        }
                    )
                    clusters.append(cluster)
                    self.stats["created_clusters"] += 1
                    self.stats["combined_files"] += 1
                    matched = True
                    break
            
            if not matched:
                unmatched.append(file)
        
        return clusters, unmatched
    
    def format_cluster(
        self,
        cluster: DocumentCluster,
        file_contents: Dict[str, str]
    ) -> ClusterResult:
        """
        将文档簇格式化为聚合内容
        
        Args:
            cluster: 文档簇
            file_contents: 文件内容字典 {file_path: content}
            
        Returns:
            ClusterResult 聚合格式化结果
        """
        if cluster.strategy == ClusterStrategy.COMBINE_SHORT_DOCS:
            return self._format_combined(cluster, file_contents)
        elif cluster.strategy == ClusterStrategy.SUMMARIZE_MULTIPLE:
            return self._format_summarized(cluster, file_contents)
        elif cluster.strategy == ClusterStrategy.APPEND_TO_EXISTING:
            return self._format_append(cluster, file_contents)
        else:
            # 默认合并
            return self._format_combined(cluster, file_contents)
    
    def _format_combined(
        self,
        cluster: DocumentCluster,
        file_contents: Dict[str, str]
    ) -> ClusterResult:
        """格式化合并的短文档"""
        parts = []
        sources = []
        tags = []
        
        for file in cluster.files:
            file_path = str(file)
            content = file_contents.get(file_path, "")
            sources.append(file_path)
            
            # 提取文档标题
            title = self._extract_title(content) or file.stem
            
            # 构建章节
            parts.append(f"\n---\n\n# {title}\n\n")
            parts.append(content)
            
            # 尝试提取标签
            file_tags = self._extract_tags(content)
            tags.extend(file_tags)
        
        # 去重标签
        tags = list(set(tags))
        
        combined_title = cluster.title or f"Combined Notes ({len(cluster.files)} files)"
        combined_content = f"# {combined_title}\n\n"
        combined_content += f"_Combined from {len(cluster.files)} documents_\n"
        combined_content += "".join(parts)
        
        return ClusterResult(
            cluster=cluster,
            title=combined_title,
            content=combined_content,
            sources=sources,
            tags=tags,
            metadata={
                "cluster_id": cluster.cluster_id,
                "strategy": cluster.strategy.value,
                "file_count": len(cluster.files)
            }
        )
    
    def _format_summarized(
        self,
        cluster: DocumentCluster,
        file_contents: Dict[str, str]
    ) -> ClusterResult:
        """格式化多篇文档总结（调用LLM）"""
        # 这个方法应该被LLM调用，这里只做简单拼接
        # 实际实现应该把内容传给LLM生成总结
        sources = [str(file) for file in cluster.files]
        
        combined_content = f"# {cluster.title or 'Summary'}\n\n"
        combined_content += f"_Summary of {len(cluster.files)} related documents_\n\n"
        combined_content += "## Source Files\n"
        for src in sources:
            combined_content += f"- {Path(src).name}\n"
        combined_content += "\n---\n\n"
        combined_content += "(Summary to be generated by LLM...)\n"
        
        return ClusterResult(
            cluster=cluster,
            title=cluster.title or "Document Summary",
            content=combined_content,
            sources=sources,
            tags=["summary"],
            metadata={
                "cluster_id": cluster.cluster_id,
                "strategy": cluster.strategy.value,
                "requires_llm_summary": True
            }
        )
    
    def _format_append(
        self,
        cluster: DocumentCluster,
        file_contents: Dict[str, str]
    ) -> ClusterResult:
        """格式化为追加内容"""
        file = cluster.files[0]
        file_path = str(file)
        content = file_contents.get(file_path, "")
        
        append_content = f"\n---\n\n## Appendix: {file.name}\n\n{content}\n"
        
        return ClusterResult(
            cluster=cluster,
            title=cluster.title or f"Append: {file.name}",
            content=append_content,
            sources=[file_path],
            tags=["appendix"],
            metadata={
                "cluster_id": cluster.cluster_id,
                "strategy": cluster.strategy.value,
                "append_to": cluster.metadata.get("append_to"),
                "is_append": True
            }
        )
    
    def _extract_title(self, content: str) -> Optional[str]:
        """从内容中提取标题"""
        # 尝试从第一行提取
        first_line = content.strip().splitlines()[0] if content.strip() else ""
        
        # Markdown标题
        md_title = re.match(r'^#+\s*(.+)$', first_line)
        if md_title:
            return md_title.group(1).strip()
        
        # 纯文本标题（第一行较短）
        if 0 < len(first_line) < 100 and not first_line.startswith('>'):
            return first_line
        
        return None
    
    def _extract_tags(self, content: str) -> List[str]:
        """从内容中提取标签"""
        # 查找 #tag 格式的标签
        tags = re.findall(r'#(\w+)', content)
        return list(set(tags))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取聚合统计"""
        return {
            **self.stats,
            "clustering_rate": self.stats["combined_files"] / max(self.stats["total_files"], 1),
        }
