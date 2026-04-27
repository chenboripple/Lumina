"""
Tag Recommender - 自动标签推荐模块
基于语义分析自动为笔记推荐标签
"""

import json
import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from collections import Counter


@dataclass
class TagRecommendation:
    """标签推荐结果"""
    tag: str
    score: float  # 0-1 的置信度
    reason: str   # 推荐理由
    source: str   # 来源：semantic, keyword, category, pattern


class TagRecommender:
    """
    智能标签推荐器
    
    基于多种策略自动推荐标签：
    1. 语义分析 - 基于内容语义提取主题
    2. 关键词提取 - TF-IDF 风格的关键词
    3. 模式匹配 - 基于预定义模式识别
    4. 分类推断 - 基于内容类型推断
    """
    
    # 预定义标签分类
    CATEGORY_TAGS = {
        '技术': ['编程', '算法', '架构', '数据库', '前端', '后端', 'DevOps', 'AI', '机器学习'],
        '产品': ['需求', '设计', '用户体验', '原型', '竞品分析', '产品策略'],
        '管理': ['项目管理', '团队协作', '敏捷', '流程', 'OKR', '会议'],
        '学习': ['读书笔记', '教程', '总结', '概念', '方法论'],
        '生活': ['健康', '旅行', '美食', '理财', '效率'],
    }
    
    # 技术栈关键词映射
    TECH_KEYWORDS = {
        'python': 'Python',
        'javascript': 'JavaScript',
        'typescript': 'TypeScript',
        'react': 'React',
        'vue': 'Vue',
        'angular': 'Angular',
        'docker': 'Docker',
        'kubernetes': 'Kubernetes',
        'aws': 'AWS',
        'gcp': 'GCP',
        'azure': 'Azure',
        'sql': 'SQL',
        'nosql': 'NoSQL',
        'mongodb': 'MongoDB',
        'redis': 'Redis',
        'elasticsearch': 'Elasticsearch',
        'graphql': 'GraphQL',
        'rest': 'REST API',
        'microservices': '微服务',
        'serverless': 'Serverless',
        'git': 'Git',
        'ci/cd': 'CI/CD',
        'terraform': 'Terraform',
        'ansible': 'Ansible',
        'prometheus': 'Prometheus',
        'grafana': 'Grafana',
        'kafka': 'Kafka',
        'rabbitmq': 'RabbitMQ',
        'nginx': 'Nginx',
        'linux': 'Linux',
        'bash': 'Bash',
        'shell': 'Shell',
        'go': 'Go',
        'rust': 'Rust',
        'java': 'Java',
        'kotlin': 'Kotlin',
        'swift': 'Swift',
        'flutter': 'Flutter',
        'react native': 'React Native',
        'tensorflow': 'TensorFlow',
        'pytorch': 'PyTorch',
        'scikit-learn': 'Scikit-learn',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
        'jupyter': 'Jupyter',
        'fastapi': 'FastAPI',
        'django': 'Django',
        'flask': 'Flask',
        'spring': 'Spring',
        'laravel': 'Laravel',
        'rails': 'Rails',
    }
    
    # 概念关键词映射
    CONCEPT_KEYWORDS = {
        'design pattern': '设计模式',
        'algorithm': '算法',
        'data structure': '数据结构',
        'system design': '系统设计',
        'distributed system': '分布式系统',
        'high availability': '高可用',
        'scalability': '可扩展性',
        'performance': '性能优化',
        'security': '安全',
        'testing': '测试',
        'debugging': '调试',
        'refactoring': '重构',
        'clean code': '代码规范',
        'agile': '敏捷开发',
        'scrum': 'Scrum',
        'kanban': '看板',
        'okr': 'OKR',
        'kpi': 'KPI',
        'leadership': '领导力',
        'communication': '沟通',
        'negotiation': '谈判',
        'time management': '时间管理',
        'deep work': '深度工作',
        'pomodoro': '番茄工作法',
        'gtd': 'GTD',
        'mind map': '思维导图',
        'flow': '心流',
        'habit': '习惯养成',
        'meditation': '冥想',
        'exercise': '运动',
        'nutrition': '营养',
        'sleep': '睡眠',
        'stress': '压力管理',
        'productivity': '生产力',
        'creativity': '创造力',
        'critical thinking': '批判性思维',
        'problem solving': '问题解决',
        'decision making': '决策',
        'learning': '学习',
        'memory': '记忆',
        'focus': '专注力',
        'motivation': '动机',
        'goal': '目标设定',
        'planning': '规划',
        'review': '复盘',
        'feedback': '反馈',
        'mentorship': '导师制',
        'coaching': '教练技术',
        'team building': '团队建设',
        'culture': '文化',
        'hiring': '招聘',
        'interview': '面试',
        'career': '职业发展',
        'salary': '薪资',
        'promotion': '晋升',
        'resignation': '离职',
        'onboarding': '入职',
        'offboarding': '离职',
    }
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        self.llm_config = llm_config or {}
        self._llm_provider = None
        
        # 初始化 LLM（用于语义分析）
        if self.llm_config:
            try:
                from .llm import get_llm_provider
                self._llm_provider = get_llm_provider(self.llm_config)
            except Exception:
                pass
    
    def recommend_tags(
        self,
        content: str,
        title: str = "",
        existing_tags: List[str] = None,
        max_tags: int = 8,
        min_confidence: float = 0.3
    ) -> List[TagRecommendation]:
        """
        为笔记推荐标签
        
        Args:
            content: 笔记内容
            title: 笔记标题
            existing_tags: 已有标签（避免重复）
            max_tags: 最大推荐数量
            min_confidence: 最小置信度
            
        Returns:
            标签推荐列表
        """
        existing_tags = set(existing_tags or [])
        recommendations = []
        
        # 1. 关键词匹配
        keyword_tags = self._extract_keywords(content, title)
        for tag, score in keyword_tags:
            if tag not in existing_tags and score >= min_confidence:
                recommendations.append(TagRecommendation(
                    tag=tag,
                    score=score,
                    reason=f"关键词匹配 (出现在内容中 {int(score * 100)}% 的位置)",
                    source="keyword"
                ))
        
        # 2. 技术栈识别
        tech_tags = self._detect_tech_stack(content, title)
        for tag, score in tech_tags:
            if tag not in existing_tags and score >= min_confidence:
                recommendations.append(TagRecommendation(
                    tag=tag,
                    score=score,
                    reason="技术栈识别",
                    source="pattern"
                ))
        
        # 3. 概念识别
        concept_tags = self._detect_concepts(content, title)
        for tag, score in concept_tags:
            if tag not in existing_tags and score >= min_confidence:
                recommendations.append(TagRecommendation(
                    tag=tag,
                    score=score,
                    reason="概念识别",
                    source="pattern"
                ))
        
        # 4. 语义分析（如果有 LLM）
        if self._llm_provider:
            semantic_tags = self._semantic_analysis(content, title)
            for tag, score in semantic_tags:
                if tag not in existing_tags and score >= min_confidence:
                    recommendations.append(TagRecommendation(
                        tag=tag,
                        score=score,
                        reason="语义分析",
                        source="semantic"
                    ))
        
        # 5. 分类推断
        category_tags = self._infer_category(content, title)
        for tag, score in category_tags:
            if tag not in existing_tags and score >= min_confidence:
                recommendations.append(TagRecommendation(
                    tag=tag,
                    score=score,
                    reason="分类推断",
                    source="category"
                ))
        
        # 去重并排序
        seen = set()
        unique_recommendations = []
        for rec in sorted(recommendations, key=lambda x: x.score, reverse=True):
            if rec.tag not in seen:
                seen.add(rec.tag)
                unique_recommendations.append(rec)
        
        return unique_recommendations[:max_tags]
    
    def _extract_keywords(self, content: str, title: str) -> List[tuple]:
        """提取关键词"""
        text = f"{title} {content}".lower()
        
        # 简单的词频统计
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{2,}\b', text)
        word_freq = Counter(words)
        
        # 计算 TF 分数
        total_words = len(words)
        keywords = []
        for word, freq in word_freq.most_common(20):
            if len(word) > 2:  # 过滤短词
                tf_score = freq / total_words
                keywords.append((word, min(tf_score * 10, 1.0)))  # 归一化
        
        return keywords[:10]
    
    def _detect_tech_stack(self, content: str, title: str) -> List[tuple]:
        """检测技术栈"""
        text = f"{title} {content}".lower()
        matches = []
        
        for keyword, tag in self.TECH_KEYWORDS.items():
            count = text.count(keyword.lower())
            if count > 0:
                score = min(count * 0.3, 1.0)
                matches.append((tag, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _detect_concepts(self, content: str, title: str) -> List[tuple]:
        """检测概念"""
        text = f"{title} {content}".lower()
        matches = []
        
        for keyword, tag in self.CONCEPT_KEYWORDS.items():
            count = text.count(keyword.lower())
            if count > 0:
                score = min(count * 0.3, 1.0)
                matches.append((tag, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def _semantic_analysis(self, content: str, title: str) -> List[tuple]:
        """语义分析（使用 LLM）"""
        if not self._llm_provider:
            return []
        
        try:
            prompt = f"""Analyze the following content and suggest 5 relevant tags.
            Return ONLY a JSON array of objects with 'tag' and 'confidence' fields.
            
            Title: {title}
            Content: {content[:2000]}
            
            Example output:
            [{{"tag": "machine-learning", "confidence": 0.95}}]
            """
            
            response = self._llm_provider.generate(prompt, max_tokens=500)
            tags_data = json.loads(response)
            
            return [
                (item['tag'], item.get('confidence', 0.5))
                for item in tags_data
            ]
        except Exception:
            return []
    
    def _infer_category(self, content: str, title: str) -> List[tuple]:
        """推断内容分类"""
        text = f"{title} {content}".lower()
        scores = {}
        
        for category, tags in self.CATEGORY_TAGS.items():
            score = 0
            for tag in tags:
                if tag.lower() in text:
                    score += 0.3
            
            if score > 0:
                scores[category] = min(score, 1.0)
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    def suggest_related_tags(self, tags: List[str]) -> List[str]:
        """
        基于已有标签推荐相关标签
        
        Args:
            tags: 已有标签列表
            
        Returns:
            相关标签建议
        """
        related = set()
        
        # 查找同类别标签
        for category, category_tags in self.CATEGORY_TAGS.items():
            for tag in tags:
                if tag in category_tags:
                    # 添加同类别的其他标签
                    related.update(t for t in category_tags if t != tag)
        
        # 查找技术栈相关
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in self.TECH_KEYWORDS:
                # 添加相关技术
                related.add(self.TECH_KEYWORDS[tag_lower])
        
        return list(related - set(tags))
    
    def validate_tags(self, tags: List[str]) -> Dict[str, Any]:
        """
        验证标签质量
        
        Args:
            tags: 标签列表
            
        Returns:
            验证结果
        """
        issues = []
        
        # 检查重复
        if len(tags) != len(set(tags)):
            issues.append("存在重复标签")
        
        # 检查空标签
        if any(not tag.strip() for tag in tags):
            issues.append("存在空标签")
        
        # 检查标签长度
        for tag in tags:
            if len(tag) > 50:
                issues.append(f"标签过长: {tag[:20]}...")
        
        # 检查标签数量
        if len(tags) > 15:
            issues.append("标签数量过多（建议不超过15个）")
        
        if len(tags) < 2:
            issues.append("标签数量过少（建议至少2个）")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggestions": self._get_tag_suggestions(tags)
        }
    
    def _get_tag_suggestions(self, tags: List[str]) -> List[str]:
        """获取标签改进建议"""
        suggestions = []
        
        # 建议统一大小写
        mixed_case = any(tag != tag.lower() and tag != tag.upper() for tag in tags)
        if mixed_case:
            suggestions.append("建议统一标签大小写格式")
        
        # 建议添加分类标签
        has_category = any(
            tag in self.CATEGORY_TAGS.get(cat, [])
            for cat in self.CATEGORY_TAGS
            for tag in tags
        )
        if not has_category:
            suggestions.append("建议添加分类标签（如：技术、产品、管理等）")
        
        return suggestions
