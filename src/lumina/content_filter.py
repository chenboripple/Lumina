"""
Content Filter - 内容前置过滤器
过滤无价值、重复、模板化的文档,减少无效 LLM 调用
"""

import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import math


@dataclass
class FilterResult:
    """过滤结果"""
    should_process: bool  # 是否应该处理
    reason: str  # 过滤原因(如果跳过)
    confidence: float  # 过滤决策置信度 0-1
    metadata: Dict[str, Any]  # 额外元数据


class ContentFilter:
    """
    内容前置过滤器

    过滤规则(按优先级):
    1. 文件大小检查 - 过小或过大的文件
    2. 空白/模板检测 - 空文件、纯模板文件
    3. 重复内容检测 - 与已有文件内容重复
    4. 内容价值评估 - 基于文本特征判断是否有笔记价值
    """

    # 文件大小阈值
    MIN_SIZE_BYTES = 50  # 小于50字节视为空文件
    MAX_SIZE_BYTES = 50 * 1024 * 1024  # 大于50MB可能不是文本

    # 内容价值评估阈值
    MIN_MEANINGFUL_WORDS = 10  # 最少有效词数
    MIN_CONTENT_ENTROPY = 1.5  # 最小内容熵(低于此值可能是重复/模板)
    MAX_DUPLICATE_RATIO = 0.85  # 最大重复比例(高于此值视为重复文件)

    # 模板检测模式
    TEMPLATE_PATTERNS = [
        r'^\s*$',  # 纯空白
        r'^#+\s*TODO\s*$',  # 空TODO模板
        r'^\s*template\s*$',  # 模板标记
        r'^\s*placeholder\s*$',  # 占位符
        r'^(\s*[\-\*]\s*)+$',  # 纯列表符号
        r'^(\s*\d+\.\s*)+$',  # 纯数字列表
    ]

    def __init__(self):
        self._fingerprint_file = Path("~/.lumina/fingerprints/content_fingerprints.json").expanduser()
        self._fingerprint_file.parent.mkdir(parents=True, exist_ok=True)

        # 已处理文件的内容指纹缓存(用于重复检测)
        self._content_fingerprints: Dict[str, str] = self._load_fingerprints()
        self.stats = {
            "total_checked": 0,
            "passed": 0,
            "filtered_empty": 0,
            "filtered_template": 0,
            "filtered_duplicate": 0,
            "filtered_low_value": 0,
        }

    def check(self, file_path: Path, content: Optional[str] = None) -> FilterResult:
        """
        检查文件是否应该被处理
        
        Args:
            file_path: 文件路径
            content: 文件内容（如果已读取）
        
        Returns:
            FilterResult 过滤结果
        """
        self.stats["total_checked"] += 1
        
        # 1. 文件大小检查（如果 content 未提供且文件存在）
        size = 0
        if content is not None:
            size = len(content.encode('utf-8'))
        else:
            try:
                size = file_path.stat().st_size
            except Exception:
                size = 0
        
        if size < self.MIN_SIZE_BYTES:
            self.stats["filtered_empty"] += 1
            return FilterResult(
                should_process=False,
                reason=f"文件过小 ({size} bytes)，可能为空文件",
                confidence=0.95,
                metadata={"size": size, "filter_type": "empty"}
            )
        
        if size > self.MAX_SIZE_BYTES:
            return FilterResult(
                should_process=False,
                reason=f"文件过大 ({size / 1024 / 1024:.1f} MB)，可能不是文本内容",
                confidence=0.9,
                metadata={"size": size, "filter_type": "too_large"}
            )
        
        # 读取内容（如果未提供）
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                return FilterResult(
                    should_process=False,
                    reason=f"无法读取文件内容: {e}",
                    confidence=1.0,
                    metadata={"error": str(e), "filter_type": "read_error"}
                )
        
        # 2. 空白/模板检测
        template_check = self._check_template(content)
        if not template_check.should_process:
            self.stats["filtered_template"] += 1
            return template_check
        
        # 3. 重复内容检测
        duplicate_check = self._check_duplicate(file_path, content)
        if not duplicate_check.should_process:
            self.stats["filtered_duplicate"] += 1
            return duplicate_check

        # 对 PDF 的降级提取文本（如扫描版提示）放宽低价值过滤，避免直接被跳过
        if file_path.suffix.lower() == ".pdf":
            pdf_marker = (
                content.startswith("[PDF appears to be scanned/image-based")
                or content.startswith("[PDF:")
            )
            if pdf_marker:
                self.stats["passed"] += 1
                return FilterResult(
                    should_process=True,
                    reason="PDF 降级提取内容，保留进入后续流程",
                    confidence=0.55,
                    metadata={"filter_type": "pdf_limited_text"}
                )
        
        # 4. 内容价值评估
        value_check = self._assess_value(content)
        if not value_check.should_process:
            self.stats["filtered_low_value"] += 1
            return value_check
        
        # 通过所有检查
        self.stats["passed"] += 1
        return FilterResult(
            should_process=True,
            reason="通过所有过滤检查",
            confidence=value_check.confidence,
            metadata={
                "filter_type": "passed",
                "content_entropy": value_check.metadata.get("entropy"),
                "word_count": value_check.metadata.get("word_count"),
                "meaningful_ratio": value_check.metadata.get("meaningful_ratio"),
            }
        )

    def _check_template(self, content: str) -> FilterResult:
        """检查是否为模板/空白文件"""
        stripped = content.strip()

        # 纯空白
        if not stripped:
            return FilterResult(
                should_process=False,
                reason="文件内容为空",
                confidence=1.0,
                metadata={"filter_type": "blank"}
            )

        # 检查模板模式
        for pattern in self.TEMPLATE_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                return FilterResult(
                    should_process=False,
                    reason="文件内容匹配模板模式",
                    confidence=0.9,
                    metadata={"filter_type": "template", "pattern": pattern}
                )

        # 检查是否主要是标点、空格、特殊字符
        total_chars = len(stripped)
        if total_chars > 0:
            meaningful_chars = len(re.findall(r'[\u4e00-\u9fff\w]', stripped))
            if meaningful_chars / total_chars < 0.1:  # 有意义字符少于10%
                return FilterResult(
                    should_process=False,
                    reason="文件内容有意义字符比例过低,可能是格式文件",
                    confidence=0.85,
                    metadata={
                        "filter_type": "low_meaningful_chars",
                        "meaningful_ratio": meaningful_chars / total_chars
                    }
                )

        return FilterResult(should_process=True, reason="非模板文件", confidence=0.9, metadata={})

    def _check_duplicate(self, file_path: Path, content: str) -> FilterResult:
        """检查是否与已有文件重复"""
        # 生成内容指纹（基于完整内容）
        fingerprint = hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()

        # 检查完全相同的指纹
        for existing_path, existing_fp in self._content_fingerprints.items():
            if existing_path == str(file_path):
                continue
            if existing_fp == fingerprint:
                return FilterResult(
                    should_process=False,
                    reason=f"与已有文件内容重复: {existing_path}",
                    confidence=0.95,
                    metadata={
                        "filter_type": "exact_duplicate",
                        "duplicate_of": existing_path,
                        "fingerprint": fingerprint[:8]
                    }
                )

        # 检查相似度(基于词频)
        similarity_check = self._check_similarity(file_path, content)
        if not similarity_check.should_process:
            return similarity_check

        # 记录指纹
        self._content_fingerprints[str(file_path)] = fingerprint
        self._save_fingerprints()

        return FilterResult(should_process=True, reason="非重复文件", confidence=0.9, metadata={})

    def _check_similarity(self, file_path: Path, content: str) -> FilterResult:
        """检查内容相似度"""
        # 预留扩展点：后续可接入向量或词频相似度
        return FilterResult(should_process=True, reason="", confidence=1.0, metadata={})

    def _load_fingerprints(self) -> Dict[str, str]:
        """加载持久化的内容指纹。"""
        if not self._fingerprint_file.exists():
            return {}
        try:
            data = json.loads(self._fingerprint_file.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _save_fingerprints(self):
        """保存内容指纹到磁盘。"""
        try:
            self._fingerprint_file.write_text(
                json.dumps(self._content_fingerprints, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception:
            # 保存失败不影响主流程
            pass

    def _assess_value(self, content: str) -> FilterResult:
        """评估内容是否有笔记价值"""
        # 计算内容熵
        entropy = self._calculate_entropy(content)

        # 统计有效词数
        words = re.findall(r'[\u4e00-\u9fff\w]+', content)
        meaningful_words = [w for w in words if len(w) > 1]
        word_count = len(meaningful_words)

        # 计算有意义内容比例
        total_chars = len(content.strip())
        meaningful_chars = len(re.findall(r'[\u4e00-\u9fff\w]', content))
        meaningful_ratio = meaningful_chars / total_chars if total_chars > 0 else 0

        metadata = {
            "entropy": entropy,
            "word_count": word_count,
            "meaningful_ratio": meaningful_ratio,
            "filter_type": "value_assessment"
        }

        # 检查有效词数
        if word_count < self.MIN_MEANINGFUL_WORDS:
            return FilterResult(
                should_process=False,
                reason=f"有效词数过少 ({word_count} < {self.MIN_MEANINGFUL_WORDS}),内容价值低",
                confidence=0.8,
                metadata=metadata
            )

        # 检查内容熵
        if entropy < self.MIN_CONTENT_ENTROPY:
            return FilterResult(
                should_process=False,
                reason=f"内容熵过低 ({entropy:.2f} < {self.MIN_CONTENT_ENTROPY}),可能是重复或模板内容",
                confidence=0.75,
                metadata=metadata
            )

        # 检查有意义内容比例
        if meaningful_ratio < 0.3:
            return FilterResult(
                should_process=False,
                reason=f"有意义内容比例过低 ({meaningful_ratio:.1%}),可能是格式/配置类文件",
                confidence=0.7,
                metadata=metadata
            )

        # 通过价值评估
        confidence = min(1.0, 0.5 + entropy / 5 + meaningful_ratio / 2)
        return FilterResult(
            should_process=True,
            reason="内容有价值",
            confidence=confidence,
            metadata=metadata
        )

    def _calculate_entropy(self, text: str) -> float:
        """计算文本信息熵"""
        if not text:
            return 0.0

        # 按字符计算频率
        char_counts = Counter(text)
        total = len(text)

        entropy = 0.0
        for count in char_counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def _extract_word_freq(self, text: str) -> Dict[str, int]:
        """提取词频"""
        words = re.findall(r'[\u4e00-\u9fff\w]+', text.lower())
        return Counter(words)

    def get_stats(self) -> Dict[str, Any]:
        """获取过滤统计"""
        return {
            **self.stats,
            "filter_rate": (self.stats["total_checked"] - self.stats["passed"]) / max(self.stats["total_checked"], 1),
            "cached_fingerprints": len(self._content_fingerprints),
        }

    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_checked": 0,
            "passed": 0,
            "filtered_empty": 0,
            "filtered_template": 0,
            "filtered_duplicate": 0,
            "filtered_low_value": 0,
        }
        self._content_fingerprints.clear()
        self._save_fingerprints()
