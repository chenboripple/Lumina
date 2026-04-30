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
    LOW_KNOWLEDGE_DENSITY_RATIO = 0.45
    SAMPLE_FACT_DOWNGRADE_RATIO = 0.25
    HIGH_NUMERIC_RATIO = 0.18

    ABSTRACTION_KEYWORDS = [
        "规则", "逻辑", "设计", "架构", "流程", "方案", "原因", "结论", "约束", "需求", "目标",
        "校验", "治理", "策略", "修复", "问题", "分析", "实现", "接口", "结构", "字段", "依赖",
        "原理", "方法", "建议", "最佳实践", "迁移", "优化", "异常", "根因", "验证", "scene",
        "rule", "logic", "design", "architecture", "workflow", "process", "constraint", "requirement",
        "goal", "validation", "strategy", "fix", "issue", "analysis", "implementation", "api",
        "schema", "field", "dependency", "principle", "method", "recommendation", "best practice",
        "migration", "optimization", "root cause", "query", "reporting",
    ]

    RAW_FACT_KEYWORDS = [
        "订单", "订单号", "金额", "价格", "单价", "税费", "人数", "人员", "员工", "员工号", "手机号",
        "电话", "邮箱", "地址", "票号", "酒店", "航班", "乘客", "入住", "离店", "成本中心", "企业id",
        "companyid", "order_id", "user_id", "employee", "customer", "address", "phone", "email",
        "price", "amount", "sku", "count", "quantity", "timestamp", "created_at", "updated_at",
        "statement_id", "batch", "invoice", "ticket", "passenger", "checkin", "checkout",
    ]

    REFERENCE_FILENAME_HINTS = [
        "list", "列表", "字典", "dictionary", "编码", "code", "id", "编号", "dataset", "数据集",
        "清单", "mapping", "名单", "全量", "原始", "详情", "record", "records",
        "invoice", "发票", "roster", "花名册", "城市", "city", "relation", "关系", "对应",
    ]

    OBJECTIVE_LIST_KEYWORDS = [
        "invoice", "发票", "mapping", "对应关系", "customer mapping", "customer_map", "roster",
        "花名册", "城市清单", "city list", "名单", "清单", "dictionary", "字典", "电子发票",
        "人员清单", "客户对应", "code list", "id list",
    ]

    SQL_HINTS = ["select", "from", "join", "where", "insert", "update", "delete", "create table", "left join"]

    SENSITIVE_PATTERNS = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
        "phone": re.compile(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)'),
        "long_id": re.compile(r'(?<![A-Za-z0-9])(?:[A-Z]{1,5}[-_])?[A-Za-z0-9]*\d{6,}[A-Za-z0-9]*(?![A-Za-z0-9])'),
        "money": re.compile(r'(?<!\w)(?:¥|\$)?\d+(?:,\d{3})*(?:\.\d{1,2})?\s*(?:元|usd|cny|rmb)?(?!\w)', re.IGNORECASE),
    }

    LABELED_ID_PATTERNS = [
        re.compile(r'(?i)(订单号|单号|票号|员工号|工号|编号|id|uid|user_id|order_id|statement_id|companyid)\s*[:：=]?\s*([A-Za-z0-9_-]{4,})'),
        re.compile(r'(?i)(手机号|电话|手机|email|邮箱|地址|乘客|预订人|客户)\s*[:：=]?\s*([^\n,，;；]+)'),
    ]

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
            "filtered_low_density": 0,
            "downgraded_sample_facts": 0,
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

        # 几乎不可读的 PDF 不应继续生成笔记
        if file_path.suffix.lower() == ".pdf":
            pdf_marker = (
                content.startswith("[PDF appears to be scanned/image-based")
                or content.startswith("[PDF:")
            )
            if pdf_marker:
                visible_text = re.sub(r'^\[[^\]]+\]\s*', '', content, count=1).strip()
                if len(visible_text) < 120 or self._looks_like_garbled_text(visible_text):
                    return FilterResult(
                        should_process=False,
                        reason="PDF 可提取文本过少或疑似乱码，跳过生成",
                        confidence=0.92,
                        metadata={"filter_type": "unreadable_pdf"}
                    )
        
        # 4. 内容价值评估
        value_check = self._assess_value(content, file_path)
        if not value_check.should_process:
            if value_check.metadata.get("filter_type") == "low_knowledge_density":
                self.stats["filtered_low_density"] += 1
            else:
                self.stats["filtered_low_value"] += 1
            return value_check

        if value_check.metadata.get("downgrade_sample_facts"):
            self.stats["downgraded_sample_facts"] += 1
        
        # 通过所有检查
        self.stats["passed"] += 1
        return FilterResult(
            should_process=True,
            reason="通过所有过滤检查",
            confidence=value_check.confidence,
            metadata={
                **value_check.metadata,
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

    def _assess_value(self, content: str, file_path: Optional[Path] = None) -> FilterResult:
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

        if self._looks_like_garbled_text(content):
            return FilterResult(
                should_process=False,
                reason="文本疑似乱码或提取噪声，缺少可读信息",
                confidence=0.88,
                metadata={
                    **metadata,
                    "filter_type": "garbled_text",
                    "garbled_text": True,
                }
            )

        density_profile = self._profile_knowledge_density(content, file_path)
        metadata.update(density_profile)

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

        if density_profile.get("low_knowledge_density"):
            return FilterResult(
                should_process=False,
                reason=density_profile.get("reason", "知识密度过低，偏原始记录/字典/样本数据"),
                confidence=density_profile.get("confidence", 0.82),
                metadata={
                    **metadata,
                    "filter_type": "low_knowledge_density",
                }
            )

        # 通过价值评估
        confidence = min(1.0, 0.5 + entropy / 5 + meaningful_ratio / 2)
        return FilterResult(
            should_process=True,
            reason="内容有价值",
            confidence=confidence,
            metadata=metadata
        )

    def _profile_knowledge_density(self, content: str, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """基于通用文本特征评估知识密度，而非依赖具体业务样本。"""
        text = content or ""
        lower_text = text.lower()
        nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
        total_lines = max(len(nonempty_lines), 1)

        abstraction_hits = sum(1 for kw in self.ABSTRACTION_KEYWORDS if kw.lower() in lower_text)
        raw_fact_hits = sum(1 for kw in self.RAW_FACT_KEYWORDS if kw.lower() in lower_text)
        sql_lines = sum(1 for line in nonempty_lines if any(hint in line.lower() for hint in self.SQL_HINTS))
        sql_operation_lines = sum(
            1
            for line in nonempty_lines
            if re.search(r'\b(update|insert\s+into|delete\s+from|alter\s+table|create\s+table|drop\s+table)\b', line.lower())
        )
        table_lines = sum(1 for line in nonempty_lines if line.count("|") >= 2)
        fact_lines = sum(1 for line in nonempty_lines if self._is_sample_fact_line(line))
        numeric_chars = sum(ch.isdigit() for ch in text)
        meaningful_chars = max(len(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text)), 1)
        numeric_ratio = numeric_chars / meaningful_chars
        sensitive_hits = self._count_sensitive_hits(text)

        filename = (file_path.name.lower() if file_path else "")
        reference_name_hits = sum(1 for hint in self.REFERENCE_FILENAME_HINTS if hint.lower() in filename)
        objective_list_hits = sum(1 for hint in self.OBJECTIVE_LIST_KEYWORDS if hint.lower() in f"{filename} {lower_text}")

        fact_line_ratio = fact_lines / total_lines
        table_line_ratio = table_lines / total_lines
        sql_operation_ratio = sql_operation_lines / total_lines

        looks_like_reference_list = (
            (reference_name_hits > 0 or objective_list_hits > 0)
            and abstraction_hits == 0
            and (numeric_ratio > self.HIGH_NUMERIC_RATIO or table_line_ratio > 0.2 or fact_line_ratio > 0.35)
        )
        looks_like_single_record = (
            fact_line_ratio > self.LOW_KNOWLEDGE_DENSITY_RATIO
            and raw_fact_hits >= 3
            and abstraction_hits < 2
            and sql_lines == 0
        )
        looks_like_sql_log = (
            sql_operation_ratio > 0.35
            and abstraction_hits < 2
            and raw_fact_hits < 4
        )

        low_knowledge_density = bool(looks_like_reference_list or looks_like_single_record or looks_like_sql_log)
        downgrade_sample_facts = bool(
            not low_knowledge_density
            and (
                fact_line_ratio > self.SAMPLE_FACT_DOWNGRADE_RATIO
                or sensitive_hits > 0
                or numeric_ratio > self.HIGH_NUMERIC_RATIO
            )
        )

        reason = ""
        if looks_like_reference_list:
            reason = "内容更像原始列表/字典/编码映射，缺少可复用规则与结论"
        elif looks_like_single_record:
            reason = "内容以样本事实和客观字段为主，知识密度过低"
        elif looks_like_sql_log:
            reason = "内容主要是 SQL 操作留痕，缺少规则解释或可复用结论"

        return {
            "abstraction_hits": abstraction_hits,
            "raw_fact_hits": raw_fact_hits,
            "sql_lines": sql_lines,
            "sql_operation_lines": sql_operation_lines,
            "fact_lines": fact_lines,
            "fact_line_ratio": round(fact_line_ratio, 3),
            "table_line_ratio": round(table_line_ratio, 3),
            "sql_operation_ratio": round(sql_operation_ratio, 3),
            "numeric_ratio": round(numeric_ratio, 3),
            "sensitive_hits": sensitive_hits,
            "reference_name_hits": reference_name_hits,
            "objective_list_hits": objective_list_hits,
            "low_knowledge_density": low_knowledge_density,
            "downgrade_sample_facts": downgrade_sample_facts,
            "mask_sensitive": sensitive_hits > 0 or raw_fact_hits > 0,
            "reason": reason,
            "confidence": 0.85 if low_knowledge_density else 0.68,
        }

    def _looks_like_garbled_text(self, content: str) -> bool:
        text = (content or "").strip()
        if not text:
            return False

        visible_chars = len(re.findall(r'\S', text))
        if visible_chars == 0:
            return False

        replacement_chars = text.count("\ufffd") + text.count("�")
        readable_chars = len(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text))
        symbol_chars = len(re.findall(r'[^\u4e00-\u9fffA-Za-z0-9\s]', text))

        replacement_ratio = replacement_chars / visible_chars
        readable_ratio = readable_chars / visible_chars
        symbol_ratio = symbol_chars / visible_chars

        if replacement_ratio > 0.05:
            return True
        if symbol_ratio > 0.55 and readable_ratio < 0.2:
            return True

        garbled_lines = 0
        nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in nonempty_lines[:20]:
            line_visible = len(re.findall(r'\S', line))
            if line_visible < 8:
                continue
            line_readable = len(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', line))
            if line_readable / max(line_visible, 1) < 0.2:
                garbled_lines += 1

        return garbled_lines >= 3 and garbled_lines >= max(2, len(nonempty_lines) // 3)

    def _is_sample_fact_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        lower = stripped.lower()
        if any(hint in lower for hint in self.SQL_HINTS):
            return False
        if stripped.count("|") >= 2:
            return True
        if re.match(r'^[\-*]\s*[^\n]{0,30}[:：].+', stripped):
            return True
        if re.match(r'^[\-*]\s*', stripped):
            fact_keyword_hits = sum(1 for kw in self.RAW_FACT_KEYWORDS if kw.lower() in lower)
            if fact_keyword_hits >= 2:
                return True
        sensitive_hits = self._count_sensitive_hits(stripped)
        return sensitive_hits >= 2

    def _count_sensitive_hits(self, text: str) -> int:
        hits = 0
        for pattern in self.SENSITIVE_PATTERNS.values():
            hits += len(pattern.findall(text))
        for pattern in self.LABELED_ID_PATTERNS:
            hits += len(pattern.findall(text))
        return hits

    def build_processing_guidance(self, metadata: Dict[str, Any]) -> str:
        """为后续抽取生成指导语，强调规则优先而非样本事实。"""
        if not metadata:
            return ""
        if metadata.get("downgrade_sample_facts"):
            return (
                "Focus on reusable rules, structures, constraints, and decisions. "
                "Do not preserve sample facts such as order numbers, person records, addresses, timestamps, "
                "or exact amounts unless they are necessary to explain a rule."
            )
        if metadata.get("mask_sensitive"):
            return "Mask sensitive identifiers and avoid reproducing personally identifiable or transaction-specific fields."
        return ""

    def sanitize_content(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """按通用规则对原文做脱敏和样本事实降级。"""
        metadata = metadata or {}
        result = content
        transform_meta = {
            "masked_sensitive": False,
            "collapsed_fact_lines": 0,
        }

        if metadata.get("mask_sensitive"):
            result = self.mask_sensitive_text(result)
            transform_meta["masked_sensitive"] = result != content

        if metadata.get("downgrade_sample_facts"):
            result, collapsed = self._collapse_sample_fact_lines(result)
            transform_meta["collapsed_fact_lines"] = collapsed

        return result, transform_meta

    def mask_sensitive_text(self, text: str) -> str:
        """对常见敏感字段做通用脱敏。"""
        masked = text
        masked = self.SENSITIVE_PATTERNS["email"].sub("[EMAIL]", masked)
        masked = self.SENSITIVE_PATTERNS["phone"].sub("[PHONE]", masked)

        for pattern in self.LABELED_ID_PATTERNS:
            masked = pattern.sub(lambda m: f"{m.group(1)}: [REDACTED]", masked)

        masked = self.SENSITIVE_PATTERNS["long_id"].sub(self._mask_long_token, masked)
        return masked

    def _mask_long_token(self, match: re.Match) -> str:
        token = match.group(0)
        lower = token.lower()
        if any(hint in lower for hint in self.SQL_HINTS):
            return token
        if len(token) <= 6:
            return "[ID]"
        return f"[ID:{token[-4:]}]"

    def _collapse_sample_fact_lines(self, text: str) -> Tuple[str, int]:
        """将连续样本事实行折叠成提示语，减少对客观数据的学习偏置。"""
        lines = text.splitlines()
        output_lines: List[str] = []
        collapsed = 0
        buffer_count = 0

        def flush_buffer():
            nonlocal buffer_count, collapsed
            if buffer_count > 0:
                output_lines.append(f"- [样本事实已折叠：{buffer_count} 行订单/人员/金额等客观字段]")
                collapsed += buffer_count
                buffer_count = 0

        for line in lines:
            stripped = line.strip()
            if self._is_sample_fact_line(line):
                buffer_count += 1
                continue

            if stripped.startswith("#") or any(kw in stripped.lower() for kw in self.SQL_HINTS) or stripped:
                flush_buffer()
                output_lines.append(line)
            else:
                flush_buffer()
                output_lines.append(line)

        flush_buffer()
        return "\n".join(output_lines), collapsed

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
            "filtered_low_density": 0,
            "downgraded_sample_facts": 0,
        }
        self._content_fingerprints.clear()
        self._save_fingerprints()
