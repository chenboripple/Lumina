"""
Scene Detector - 文档场景识别与场景化提取模板
根据内容特征识别文档场景（会议/技术/需求/笔记等），匹配不同的提取策略
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class DocumentScene(Enum):
    """文档场景类型"""
    MEETING_NOTES = "meeting_notes"  # 会议纪要
    TECHNICAL_DOC = "technical_doc"  # 技术文档
    REQUIREMENTS = "requirements"  # 需求文档
    ACADEMIC_PAPER = "academic_paper"  # 学术论文
    PRD = "prd"  # 产品需求文档
    DESIGN_DOC = "design_doc"  # 设计文档
    TEST_REPORT = "test_report"  # 测试报告
    OPS_DOC = "ops_doc"  # 运维文档
    EMAIL = "email"  # 邮件
    CHAT_LOG = "chat_log"  # 聊天记录
    BOOK_NOTES = "book_notes"  # 读书笔记
    CODE_EXPLANATION = "code_explanation"  # 代码说明
    DIARY = "diary"  # 日记
    TASK_LIST = "task_list"  # 任务列表
    KNOWLEDGE_ESSAY = "knowledge_essay"  # 知识随笔
    GENERIC_NOTES = "generic_notes"  # 通用笔记
    UNKNOWN = "unknown"  # 未知场景


@dataclass
class SceneDetectionResult:
    """场景检测结果"""
    scene: DocumentScene
    confidence: float  # 置信度 0-1
    keywords: List[str]  # 匹配到的关键词
    metadata: Dict[str, Any]  # 额外元数据


@dataclass
class SceneTemplate:
    """场景化提取模板"""
    scene: DocumentScene
    name: str
    description: str
    
    # 提示词模板
    prompt_template: str
    
    # 期望的输出字段
    output_fields: List[str]
    
    # Markdown 格式化函数
    formatter: Any = None


class SceneDetector:
    """
    文档场景识别器
    
    通过以下特征识别场景：
    1. 文件名特征
    2. 内容关键词
    3. 文档结构特征
    """
    
    # 场景关键词配置
    SCENE_KEYWORDS = {
        DocumentScene.MEETING_NOTES: [
            "会议", "meeting", "会议纪要", "会议记录", "会议主题", "参会", "讨论", "决议", "todo",
            "行动项", "决策", "议题", "议程", "纪要", "minutes", "agenda", "attendee"
        ],
        DocumentScene.TECHNICAL_DOC: [
            "技术", "technical", "架构", "设计", "文档", "api", "接口", "实现", "代码", "开发",
            "部署", "配置", "说明", "架构图", "system", "design", "architecture", "implementation"
        ],
        DocumentScene.REQUIREMENTS: [
            "需求", "requirements", "功能", "功能点", "验收", "验收标准", "用户故事", "story",
            "must-have", "should-have", "优先级", "feature", "spec", "specification"
        ],
        DocumentScene.ACADEMIC_PAPER: [
            "论文", "paper", "abstract", "introduction", "method", "experiment", "result",
            "conclusion", "reference", "doi", "研究", "方法", "实验", "结论", "引用"
        ],
        DocumentScene.PRD: [
            "prd", "产品需求", "产品文档", "目标用户", "用户画像", "用户旅程", "需求背景",
            "功能范围", "里程碑", "验收标准", "上线计划", "product requirement"
        ],
        DocumentScene.DESIGN_DOC: [
            "设计文档", "设计说明", "design doc", "设计目标", "交互", "视觉", "ui", "ux",
            "信息架构", "组件规范", "设计原则", "wireframe", "原型"
        ],
        DocumentScene.TEST_REPORT: [
            "测试报告", "test report", "测试结果", "用例", "通过率", "缺陷", "bug", "回归",
            "测试范围", "测试环境", "风险", "结论"
        ],
        DocumentScene.OPS_DOC: [
            "运维", "ops", "devops", "部署", "监控", "告警", "故障", "排障", "应急", "值班",
            "发布", "回滚", "runbook", "slo", "sla"
        ],
        DocumentScene.EMAIL: [
            "邮件", "email", "主题", "subject", "收件人", "发件人", "抄送", "cc", "回复",
            "regards", "best", "dear", "re:"
        ],
        DocumentScene.CHAT_LOG: [
            "聊天记录", "chat", "im", "群聊", "私聊", "消息", "回复", "已读", "对话",
            "timestamp", "@", "emoji", "thread"
        ],
        DocumentScene.BOOK_NOTES: [
            "读书", "笔记", "读后感", "读书笔记", "book", "chapter", "章节", "摘录", "读后感",
            "reading", "notes", "summary", "quote", "思考"
        ],
        DocumentScene.CODE_EXPLANATION: [
            "代码", "code", "函数", "function", "class", "类", "方法", "method", "实现", "逻辑",
            "注释", "comment", "usage", "示例", "example", "snippet"
        ],
        DocumentScene.DIARY: [
            "日记", "diary", "日志", "log", "今天", "昨天", "tomorrow", "date", "日期", "天气",
            "心情", "感受", "记录"
        ],
        DocumentScene.TASK_LIST: [
            "任务", "task", "todo", "待办", "to-do", "清单", "checklist", "完成", "done",
            "进行中", "in-progress", "deadline", "截止日期", "优先级"
        ],
        DocumentScene.KNOWLEDGE_ESSAY: [
            "随笔", "杂谈", "浅谈", "初探", "漫谈", "感悟", "心得", "体会", "想法", "碎片",
            "观点", "看法", "思考", "essay", "thoughts", "reflection", "insight", "musing",
            "知识", "学习笔记", "总结",
        ],
    }
    
    # 文件名模式
    FILENAME_PATTERNS = {
        DocumentScene.MEETING_NOTES: [
            r'(?i).*meeting.*',
            r'(?i).*会议.*',
            r'(?i).*纪要.*',
            r'(?i).*minutes.*',
        ],
        DocumentScene.TECHNICAL_DOC: [
            r'(?i).*design.*',
            r'(?i).*架构.*',
            r'(?i).*api.*',
            r'(?i).*readme.*',
        ],
        DocumentScene.REQUIREMENTS: [
            r'(?i).*requirement.*',
            r'(?i).*需求.*',
            r'(?i).*spec.*',
        ],
        DocumentScene.ACADEMIC_PAPER: [
            r'(?i).*paper.*',
            r'(?i).*论文.*',
            r'(?i).*research.*',
        ],
        DocumentScene.PRD: [
            r'(?i).*prd.*',
            r'(?i).*product.*requirement.*',
            r'(?i).*产品需求.*',
        ],
        DocumentScene.DESIGN_DOC: [
            r'(?i).*design.*doc.*',
            r'(?i).*设计文档.*',
            r'(?i).*ui.*spec.*',
        ],
        DocumentScene.TEST_REPORT: [
            r'(?i).*test.*report.*',
            r'(?i).*测试报告.*',
            r'(?i).*qa.*report.*',
        ],
        DocumentScene.OPS_DOC: [
            r'(?i).*runbook.*',
            r'(?i).*ops.*',
            r'(?i).*运维.*',
            r'(?i).*incident.*',
        ],
        DocumentScene.EMAIL: [
            r'(?i).*mail.*',
            r'(?i).*email.*',
            r'(?i).*邮件.*',
        ],
        DocumentScene.CHAT_LOG: [
            r'(?i).*chat.*',
            r'(?i).*conversation.*',
            r'(?i).*聊天记录.*',
            r'(?i).*群聊.*',
        ],
        DocumentScene.BOOK_NOTES: [
            r'(?i).*reading.*',
            r'(?i).*读书笔记.*',
            r'(?i).*读书.*',
        ],
        DocumentScene.TASK_LIST: [
            r'(?i).*todo.*',
            r'(?i).*task.*',
            r'(?i).*任务.*',
        ],
        DocumentScene.KNOWLEDGE_ESSAY: [
            r'(?i).*随笔.*',
            r'(?i).*杂谈.*',
            r'(?i).*感悟.*',
            r'(?i).*心得.*',
            r'(?i).*浅谈.*',
            r'(?i).*漫谈.*',
        ],
    }
    
    def __init__(self):
        self._init_templates()
    
    def detect(self, file_path: Path, content: str) -> SceneDetectionResult:
        """
        检测文档场景
        
        Args:
            file_path: 文件路径
            content: 文件内容
            
        Returns:
            SceneDetectionResult 检测结果
        """
        filename = file_path.name.lower()
        results: Dict[DocumentScene, Tuple[float, List[str]]] = {}
        
        # 1. 文件名模式匹配
        for scene, patterns in self.FILENAME_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, filename):
                    conf = 0.3  # 文件名贡献30%置信度
                    if scene not in results:
                        results[scene] = (0.0, [])
                    current_conf, keywords = results[scene]
                    results[scene] = (current_conf + conf, keywords + [f"filename:{pattern}"])
        
        # 2. 内容关键词匹配
        content_lower = content.lower()
        for scene, keywords in self.SCENE_KEYWORDS.items():
            matches = []
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    matches.append(keyword)
            
            if matches:
                # 关键词数量决定置信度
                conf = min(0.7, len(matches) * 0.05)  # 每个关键词贡献5%，最高70%
                if scene not in results:
                    results[scene] = (0.0, [])
                current_conf, existing_keywords = results[scene]
                results[scene] = (current_conf + conf, existing_keywords + matches)
        
        # 3. 结构特征检测
        structure_result = self._detect_structure(content)
        if structure_result:
            scene, conf, keywords = structure_result
            if scene not in results:
                results[scene] = (0.0, [])
            current_conf, existing_keywords = results[scene]
            results[scene] = (current_conf + conf, existing_keywords + keywords)
        
        # 4. 选择最佳匹配
        if results:
            best_scene = max(results.keys(), key=lambda s: results[s][0])
            best_conf, best_keywords = results[best_scene]
            
            if best_conf >= 0.2:  # 置信度阈值
                return SceneDetectionResult(
                    scene=best_scene,
                    confidence=min(1.0, best_conf),
                    keywords=list(set(best_keywords)),
                    metadata={"method": "hybrid"}
                )
        
        # 默认返回通用笔记
        return SceneDetectionResult(
            scene=DocumentScene.GENERIC_NOTES,
            confidence=0.5,
            keywords=[],
            metadata={"method": "fallback"}
        )
    
    def _detect_structure(self, content: str) -> Optional[Tuple[DocumentScene, float, List[str]]]:
        """通过文档结构特征识别场景"""
        structure_keywords = []
        
        # 检测会议结构特征
        if re.search(r'(?i)参会|attendee|议题|决议|行动项', content):
            structure_keywords.append("structure:meeting_format")
            return (DocumentScene.MEETING_NOTES, 0.4, structure_keywords)
        
        # 检测任务列表特征
        if re.search(r'(?i)-\s*\[\s*x\s*\]|-\s*\[\s*\]|\*\s*todo|##\s*todo', content):
            structure_keywords.append("structure:checklist")
            return (DocumentScene.TASK_LIST, 0.45, structure_keywords)

        # 检测邮件结构特征
        if re.search(r'(?i)^\s*(from|to|subject|cc)\s*:', content, re.MULTILINE):
            structure_keywords.append("structure:email_header")
            return (DocumentScene.EMAIL, 0.45, structure_keywords)

        # 检测聊天记录结构特征
        if re.search(r'\d{1,2}:\d{2}(:\d{2})?\s+.+?:|\[\d{4}[-/]\d{1,2}[-/]\d{1,2}.*?\]', content):
            structure_keywords.append("structure:chat_timeline")
            return (DocumentScene.CHAT_LOG, 0.45, structure_keywords)

        # 检测学术论文结构特征
        if re.search(r'(?i)abstract|introduction|methodology|experiment|references', content):
            structure_keywords.append("structure:academic_sections")
            return (DocumentScene.ACADEMIC_PAPER, 0.4, structure_keywords)
        
        # 检测技术文档结构
        if re.search(r'(?i)##\s*api|##\s*实现|##\s*设计|###\s*function|```', content):
            structure_keywords.append("structure:technical_format")
            return (DocumentScene.TECHNICAL_DOC, 0.35, structure_keywords)
        
        return None
    
    def get_template(self, scene: DocumentScene) -> SceneTemplate:
        """获取场景对应的提取模板"""
        if scene not in self._templates:
            scene = DocumentScene.GENERIC_NOTES
        return self._templates[scene]
    
    def _init_templates(self):
        """初始化场景模板"""
        self._templates: Dict[DocumentScene, SceneTemplate] = {
            DocumentScene.MEETING_NOTES: SceneTemplate(
                scene=DocumentScene.MEETING_NOTES,
                name="会议纪要提取",
                description="专注于提取会议信息、决议、行动项",
                prompt_template=self._meeting_prompt_template(),
                output_fields=["title", "attendees", "agenda", "decisions", "action_items", "tags"],
                formatter=self._format_meeting_notes
            ),
            DocumentScene.TECHNICAL_DOC: SceneTemplate(
                scene=DocumentScene.TECHNICAL_DOC,
                name="技术文档提取",
                description="提取架构、设计、API、实现细节",
                prompt_template=self._technical_doc_prompt_template(),
                output_fields=["title", "overview", "architecture", "api_spec", "implementation", "tags"],
                formatter=self._format_technical_doc
            ),
            DocumentScene.REQUIREMENTS: SceneTemplate(
                scene=DocumentScene.REQUIREMENTS,
                name="需求文档提取",
                description="提取功能需求、验收标准、优先级",
                prompt_template=self._requirements_prompt_template(),
                output_fields=["title", "overview", "features", "acceptance_criteria", "priority", "tags"],
                formatter=self._format_requirements
            ),
            DocumentScene.ACADEMIC_PAPER: SceneTemplate(
                scene=DocumentScene.ACADEMIC_PAPER,
                name="学术论文提取",
                description="提取研究问题、方法、实验结果与结论",
                prompt_template=self._academic_paper_prompt_template(),
                output_fields=["title", "abstract", "research_problem", "methodology", "findings", "limitations", "references", "tags"],
                formatter=self._format_academic_paper
            ),
            DocumentScene.PRD: SceneTemplate(
                scene=DocumentScene.PRD,
                name="PRD提取",
                description="提取产品目标、用户需求、功能范围与验收标准",
                prompt_template=self._prd_prompt_template(),
                output_fields=["title", "background", "target_users", "goals", "requirements", "acceptance_criteria", "milestones", "tags"],
                formatter=self._format_prd
            ),
            DocumentScene.DESIGN_DOC: SceneTemplate(
                scene=DocumentScene.DESIGN_DOC,
                name="设计文档提取",
                description="提取设计目标、交互流程、视觉规范与组件设计",
                prompt_template=self._design_doc_prompt_template(),
                output_fields=["title", "design_goals", "user_flow", "ui_spec", "components", "risks", "tags"],
                formatter=self._format_design_doc
            ),
            DocumentScene.TEST_REPORT: SceneTemplate(
                scene=DocumentScene.TEST_REPORT,
                name="测试报告提取",
                description="提取测试范围、结果统计、缺陷风险与结论",
                prompt_template=self._test_report_prompt_template(),
                output_fields=["title", "scope", "environment", "summary", "defects", "risks", "conclusion", "tags"],
                formatter=self._format_test_report
            ),
            DocumentScene.OPS_DOC: SceneTemplate(
                scene=DocumentScene.OPS_DOC,
                name="运维文档提取",
                description="提取部署步骤、监控告警、故障处置与回滚策略",
                prompt_template=self._ops_doc_prompt_template(),
                output_fields=["title", "system", "deployment_steps", "monitoring", "incident_response", "rollback", "tags"],
                formatter=self._format_ops_doc
            ),
            DocumentScene.EMAIL: SceneTemplate(
                scene=DocumentScene.EMAIL,
                name="邮件提取",
                description="提取邮件主题、参与方、核心事项与待办",
                prompt_template=self._email_prompt_template(),
                output_fields=["title", "from", "to", "cc", "summary", "action_items", "deadline", "tags"],
                formatter=self._format_email
            ),
            DocumentScene.CHAT_LOG: SceneTemplate(
                scene=DocumentScene.CHAT_LOG,
                name="聊天记录提取",
                description="提取对话背景、关键结论、待办与争议点",
                prompt_template=self._chat_log_prompt_template(),
                output_fields=["title", "participants", "context", "key_points", "decisions", "action_items", "open_questions", "tags"],
                formatter=self._format_chat_log
            ),
            DocumentScene.BOOK_NOTES: SceneTemplate(
                scene=DocumentScene.BOOK_NOTES,
                name="读书笔记提取",
                description="提取核心观点、摘录、个人思考",
                prompt_template=self._book_notes_prompt_template(),
                output_fields=["title", "book_info", "key_insights", "quotes", "reflections", "tags"],
                formatter=self._format_book_notes
            ),
            DocumentScene.CODE_EXPLANATION: SceneTemplate(
                scene=DocumentScene.CODE_EXPLANATION,
                name="代码说明提取",
                description="提取函数、类、API、使用示例",
                prompt_template=self._code_explanation_prompt_template(),
                output_fields=["title", "overview", "functions", "classes", "usage_examples", "tags"],
                formatter=self._format_code_explanation
            ),
            DocumentScene.TASK_LIST: SceneTemplate(
                scene=DocumentScene.TASK_LIST,
                name="任务清单提取",
                description="提取任务、优先级、截止日期、状态",
                prompt_template=self._task_list_prompt_template(),
                output_fields=["title", "tasks", "priorities", "deadlines", "status", "tags"],
                formatter=self._format_task_list
            ),
            DocumentScene.DIARY: SceneTemplate(
                scene=DocumentScene.DIARY,
                name="日记提取",
                description="提取日期、心情、事件、感受",
                prompt_template=self._diary_prompt_template(),
                output_fields=["title", "date", "mood", "events", "reflections", "tags"],
                formatter=self._format_diary
            ),
            DocumentScene.KNOWLEDGE_ESSAY: SceneTemplate(
                scene=DocumentScene.KNOWLEDGE_ESSAY,
                name="知识随笔提取",
                description="提取核心观点、关键洞见、延伸思考、关联概念",
                prompt_template=self._knowledge_essay_prompt_template(),
                output_fields=["title", "core_idea", "key_insights", "extended_thinking", "related_concepts", "notable_quotes", "tags"],
                formatter=self._format_knowledge_essay
            ),
            DocumentScene.GENERIC_NOTES: SceneTemplate(
                scene=DocumentScene.GENERIC_NOTES,
                name="通用笔记提取",
                description="通用知识提取模板",
                prompt_template=self._generic_prompt_template(),
                output_fields=["title", "summary", "key_points", "suggested_links", "tags"],
                formatter=self._format_generic_notes
            ),
        }
    
    # === 各场景的提示词模板 ===
    
    def _meeting_prompt_template(self) -> str:
        return """你是一位会议纪要整理专家。请分析以下会议内容，生成结构化的会议纪要。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取会议标题、日期、参会人员
2. 整理议题/议程
3. 归纳决议事项
4. 提取行动项（负责人、截止日期）
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言填充所有字段值，若源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "会议标题 - 日期",
    "meeting_date": "YYYY-MM-DD",
    "attendees": ["张三", "李四"],
    "agenda": ["议题1", "议题2"],
    "decisions": ["决议1", "决议2"],
    "action_items": [
        {{
            "task": "任务描述",
            "owner": "负责人",
            "deadline": "YYYY-MM-DD"
        }}
    ],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _technical_doc_prompt_template(self) -> str:
        return """你是一位技术文档整理专家。请分析以下技术内容，生成结构化的技术文档笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取系统/组件概述
2. 整理架构设计要点
3. 提取接口规范（如有）
4. 记录实现细节
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "组件/系统名称",
    "overview": "系统概述",
    "architecture": ["架构要点1", "架构要点2"],
    "api_spec": [
        {{
            "endpoint": "/api/v1/resource",
            "method": "GET",
            "description": "接口描述"
        }}
    ],
    "implementation": ["实现细节1", "实现细节2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _requirements_prompt_template(self) -> str:
        return """你是一位需求分析专家。请分析以下需求内容，生成结构化的需求文档笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取需求标题和背景概述
2. 整理功能需求列表
3. 归纳验收标准
4. 标注优先级（高/中/低）
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "需求标题",
    "overview": "需求背景与概述",
    "features": [
        {{
            "name": "功能名称",
            "description": "功能描述",
            "priority": "高|中|低"
        }}
    ],
    "acceptance_criteria": ["验收标准1", "验收标准2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _academic_paper_prompt_template(self) -> str:
        return """你是一位学术论文分析专家。请分析以下论文内容，生成结构化论文笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取论文标题与摘要要点
2. 归纳研究问题与研究目标
3. 总结方法论与实验设置
4. 提炼核心结果、贡献与局限性
5. 整理参考文献线索（如出现）
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "论文标题",
    "abstract": "摘要提炼",
    "research_problem": "研究问题",
    "methodology": ["方法要点1", "方法要点2"],
    "findings": ["结论1", "结论2"],
    "limitations": ["局限1", "局限2"],
    "references": ["参考线索1", "参考线索2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _prd_prompt_template(self) -> str:
        return """你是一位产品经理。请分析以下 PRD/产品需求内容，生成结构化 PRD 笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取背景问题与产品目标
2. 识别目标用户与核心场景
3. 梳理需求列表（含优先级）
4. 归纳验收标准与里程碑
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "PRD标题",
    "background": "背景与问题陈述",
    "target_users": ["用户类型1", "用户类型2"],
    "goals": ["目标1", "目标2"],
    "requirements": [
        {{
            "name": "需求名称",
            "description": "需求描述",
            "priority": "高|中|低"
        }}
    ],
    "acceptance_criteria": ["标准1", "标准2"],
    "milestones": ["里程碑1", "里程碑2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _design_doc_prompt_template(self) -> str:
        return """你是一位设计文档分析专家。请分析以下设计文档，生成结构化设计说明笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取设计目标与约束
2. 归纳核心用户流程
3. 提炼 UI/交互规范
4. 梳理关键组件与设计决策
5. 标注风险与待确认项
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "设计文档标题",
    "design_goals": ["目标1", "目标2"],
    "user_flow": ["流程步骤1", "流程步骤2"],
    "ui_spec": ["交互规范1", "视觉规范2"],
    "components": ["组件1", "组件2"],
    "risks": ["风险1", "待确认项2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _test_report_prompt_template(self) -> str:
        return """你是一位测试分析专家。请分析以下测试报告内容，生成结构化测试报告笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取测试范围与环境
2. 归纳测试结果统计（通过/失败/阻塞）
3. 整理主要缺陷与严重程度
4. 识别风险项与建议
5. 给出测试结论
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "测试报告标题",
    "scope": "测试范围",
    "environment": "测试环境",
    "summary": {{
        "passed": 0,
        "failed": 0,
        "blocked": 0
    }},
    "defects": [
        {{
            "id": "BUG-123",
            "severity": "严重|高|中|低",
            "description": "缺陷描述"
        }}
    ],
    "risks": ["风险1", "风险2"],
    "conclusion": "测试结论",
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _ops_doc_prompt_template(self) -> str:
        return """你是一位运维文档整理专家。请分析以下运维内容，生成结构化运维笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取系统/服务信息
2. 梳理部署与发布步骤
3. 归纳监控指标与告警策略
4. 整理故障处置流程
5. 提取回滚方案与注意事项
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "运维文档标题",
    "system": "系统/服务名称",
    "deployment_steps": ["步骤1", "步骤2"],
    "monitoring": ["监控项1", "告警策略2"],
    "incident_response": ["处理步骤1", "处理步骤2"],
    "rollback": ["回滚步骤1", "回滚步骤2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _email_prompt_template(self) -> str:
        return """你是一位商务沟通整理专家。请分析以下邮件内容，生成结构化邮件笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取主题、发件人与收件方
2. 总结邮件核心事项
3. 提取待办项与责任人
4. 标注截止时间（如有）
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "邮件主题",
    "from": "发件人",
    "to": ["收件人1", "收件人2"],
    "cc": ["抄送1", "抄送2"],
    "summary": "核心事项",
    "action_items": [
        {{
            "task": "任务描述",
            "owner": "负责人"
        }}
    ],
    "deadline": "YYYY-MM-DD（如有）",
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    def _chat_log_prompt_template(self) -> str:
        return """你是一位对话纪要专家。请分析以下聊天记录，生成结构化对话笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取参与者与对话背景
2. 归纳关键讨论点
3. 提炼已达成结论/决策
4. 提取待办事项与负责人
5. 标注未决问题
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "对话主题",
    "participants": ["参与者1", "参与者2"],
    "context": "对话背景",
    "key_points": ["讨论点1", "讨论点2"],
    "decisions": ["结论1", "结论2"],
    "action_items": [
        {{
            "task": "任务描述",
            "owner": "负责人",
            "deadline": "YYYY-MM-DD（如有）"
        }}
    ],
    "open_questions": ["未决问题1", "未决问题2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _book_notes_prompt_template(self) -> str:
        return """你是一位读书笔记整理专家。请分析以下读书笔记内容，生成结构化的书摘笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取书名、作者
2. 整理核心观点/论点
3. 摘录精彩句子/段落
4. 记录个人感悟与思考
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "读书笔记：书名",
    "book_info": {{
        "title": "书名",
        "author": "作者"
    }},
    "key_insights": ["核心观点1", "核心观点2"],
    "quotes": [
        {{
            "text": "摘录原文",
            "page": "页码（如有）"
        }}
    ],
    "reflections": ["感悟1", "感悟2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _code_explanation_prompt_template(self) -> str:
        return """你是一位代码文档整理专家。请分析以下代码内容，生成结构化的代码说明笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 概述代码/模块的功能与用途
2. 记录函数/方法（签名、功能描述）
3. 记录类（属性、方法列表）
4. 整理使用示例
5. 添加相关标签
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "组件/文件名",
    "overview": "代码用途概述",
    "functions": [
        {{
            "name": "函数名",
            "signature": "def func_name(params)",
            "description": "功能描述"
        }}
    ],
    "classes": [
        {{
            "name": "类名",
            "description": "类的功能",
            "methods": ["方法1", "方法2"]
        }}
    ],
    "usage_examples": ["示例代码1"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _task_list_prompt_template(self) -> str:
        return """你是一位任务管理专家。请分析以下任务清单内容，生成结构化的任务笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取任务清单标题
2. 整理所有任务（描述、优先级、截止日期、状态）
3. 添加相关标签
4. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "任务清单标题",
    "tasks": [
        {{
            "task": "任务描述",
            "priority": "高|中|低",
            "deadline": "YYYY-MM-DD（如有）",
            "status": "待办|进行中|已完成|阻塞"
        }}
    ],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _diary_prompt_template(self) -> str:
        return """你是一位日记整理专家。请分析以下日记内容，生成结构化的日记笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提取日期、心情状态
2. 记录关键事件
3. 整理感悟与反思
4. 添加相关标签
5. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "日记 - YYYY-MM-DD",
    "date": "YYYY-MM-DD",
    "mood": "心情描述",
    "events": ["事件1", "事件2"],
    "reflections": ["感悟1", "感悟2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _generic_prompt_template(self) -> str:
        return """你是一位知识提取专家。请分析以下内容，生成结构化的知识笔记。

## 来源信息
- 文件：{filename}
- 类型：{file_type}

## 内容
```
{content}
```

## 提取要求
1. 提炼核心概念与洞见
2. 生成清晰的结构化摘要
3. 识别可能关联的主题
4. 推荐相关标签
5. 评估内容复杂度与可信度
6. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "简洁描述性标题",
    "summary": "内容概述",
    "key_points": ["要点1", "要点2", "要点3"],
    "tags": ["标签1", "标签2"],
    "suggested_links": ["关联主题A", "关联主题B"],
    "metadata": {{
        "complexity": "simple|moderate|complex",
        "confidence": 0.95,
        "word_count": 150
    }}
}}
"""
    
    def _knowledge_essay_prompt_template(self) -> str:
        return """你是一位知识整理专家。请分析以下随笔/感悟/思考类内容，生成结构化的知识随笔笔记。

## 来源信息
- 文件：{filename}

## 内容
```
{content}
```

## 提取要求
1. 提炼核心论点/中心思想
2. 整理关键洞见（具体观点、发现）
3. 归纳延伸思考（从内容引申出的思考）
4. 识别关联概念（相关知识领域、术语）
5. 摘录金句（精彩表达）
6. 添加相关标签
7. **语言要求**：使用与源内容相同的语言，源文为中文则全部用中文

## 输出格式
返回如下 JSON 结构：
{{
    "title": "随笔标题",
    "core_idea": "核心论点/中心思想（一两句话概括）",
    "key_insights": ["洞见1", "洞见2", "洞见3"],
    "extended_thinking": ["延伸思考1", "延伸思考2"],
    "related_concepts": ["关联概念1", "关联概念2"],
    "notable_quotes": ["金句1", "金句2"],
    "tags": ["标签1", "标签2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""

    # === Markdown 格式化函数 ===
    
    def _format_meeting_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '会议纪要')}\n"]
        
        if data.get('meeting_date'):
            lines.append(f"**日期：** {data['meeting_date']}\n\n")
        
        if data.get('attendees'):
            lines.append("## 参会人员\n")
            for attendee in data['attendees']:
                lines.append(f"- {attendee}\n")
            lines.append("\n")
        
        if data.get('agenda'):
            lines.append("## 议题\n")
            for item in data['agenda']:
                lines.append(f"- {item}\n")
            lines.append("\n")
        
        if data.get('decisions'):
            lines.append("## 决议事项\n")
            for decision in data['decisions']:
                lines.append(f"- {decision}\n")
            lines.append("\n")
        
        if data.get('action_items'):
            lines.append("## 行动项\n")
            for item in data['action_items']:
                task = item.get('task', '')
                owner = item.get('owner', '')
                deadline = item.get('deadline', '')
                line = f"- [ ] {task}"
                if owner:
                    line += f"（负责人：{owner}）"
                if deadline:
                    line += f" @{deadline}"
                lines.append(line + "\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_technical_doc(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '技术文档')}\n"]
        
        if data.get('overview'):
            lines.extend(["## 概述\n", data['overview'] + "\n\n"])
        
        if data.get('architecture'):
            lines.append("## 架构设计\n")
            for point in data['architecture']:
                lines.append(f"- {point}\n")
            lines.append("\n")
        
        if data.get('api_spec'):
            lines.append("## 接口说明\n")
            for api in data['api_spec']:
                method = api.get('method', 'GET')
                endpoint = api.get('endpoint', '')
                desc = api.get('description', '')
                lines.append(f"### `{method} {endpoint}`\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('implementation'):
            lines.append("## 实现要点\n")
            for detail in data['implementation']:
                lines.append(f"- {detail}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_requirements(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '需求文档')}\n"]
        
        if data.get('overview'):
            lines.extend(["## 概述\n", data['overview'] + "\n\n"])
        
        if data.get('features'):
            lines.append("## 功能需求\n")
            for feature in data['features']:
                name = feature.get('name', '')
                desc = feature.get('description', '')
                priority = feature.get('priority', '中')
                lines.append(f"### {name}（优先级：{priority}）\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('acceptance_criteria'):
            lines.append("## 验收标准\n")
            for criterion in data['acceptance_criteria']:
                lines.append(f"- [ ] {criterion}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)

    def _format_academic_paper(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '学术论文')}\n"]

        if data.get('abstract'):
            lines.extend(["## 摘要\n", data['abstract'] + "\n\n"])

        if data.get('research_problem'):
            lines.extend(["## 研究问题\n", data['research_problem'] + "\n\n"])

        if data.get('methodology'):
            lines.append("## 方法\n")
            for item in data['methodology']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('findings'):
            lines.append("## 研究结果\n")
            for item in data['findings']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('limitations'):
            lines.append("## 局限性\n")
            for item in data['limitations']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('references'):
            lines.append("## 参考线索\n")
            for ref in data['references']:
                lines.append(f"- {ref}\n")
            lines.append("\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_prd(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'PRD')}\n"]

        if data.get('background'):
            lines.extend(["## 背景\n", data['background'] + "\n\n"])

        if data.get('target_users'):
            lines.append("## 目标用户\n")
            for user in data['target_users']:
                lines.append(f"- {user}\n")
            lines.append("\n")

        if data.get('goals'):
            lines.append("## 产品目标\n")
            for goal in data['goals']:
                lines.append(f"- {goal}\n")
            lines.append("\n")

        if data.get('requirements'):
            lines.append("## 需求列表\n")
            for req in data['requirements']:
                name = req.get('name', '')
                desc = req.get('description', '')
                priority = req.get('priority', '中')
                lines.append(f"### {name}（优先级：{priority}）\n")
                lines.append(f"{desc}\n\n")

        if data.get('acceptance_criteria'):
            lines.append("## 验收标准\n")
            for criterion in data['acceptance_criteria']:
                lines.append(f"- [ ] {criterion}\n")
            lines.append("\n")

        if data.get('milestones'):
            lines.append("## 里程碑\n")
            for milestone in data['milestones']:
                lines.append(f"- {milestone}\n")
            lines.append("\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_design_doc(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '设计文档')}\n"]

        if data.get('design_goals'):
            lines.append("## 设计目标\n")
            for goal in data['design_goals']:
                lines.append(f"- {goal}\n")
            lines.append("\n")

        if data.get('user_flow'):
            lines.append("## 用户流程\n")
            for step in data['user_flow']:
                lines.append(f"- {step}\n")
            lines.append("\n")

        if data.get('ui_spec'):
            lines.append("## 交互与视觉规范\n")
            for spec in data['ui_spec']:
                lines.append(f"- {spec}\n")
            lines.append("\n")

        if data.get('components'):
            lines.append("## 关键组件\n")
            for component in data['components']:
                lines.append(f"- {component}\n")
            lines.append("\n")

        if data.get('risks'):
            lines.append("## 风险与待确认项\n")
            for risk in data['risks']:
                lines.append(f"- {risk}\n")
            lines.append("\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_test_report(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '测试报告')}\n"]

        if data.get('scope'):
            lines.extend(["## 测试范围\n", data['scope'] + "\n\n"])

        if data.get('environment'):
            lines.extend(["## 测试环境\n", data['environment'] + "\n\n"])

        summary = data.get('summary', {})
        if summary:
            lines.append("## 结果统计\n")
            lines.append(f"- 通过：{summary.get('passed', 0)}\n")
            lines.append(f"- 失败：{summary.get('failed', 0)}\n")
            lines.append(f"- 阻塞：{summary.get('blocked', 0)}\n\n")

        if data.get('defects'):
            lines.append("## 缺陷列表\n")
            for defect in data['defects']:
                defect_id = defect.get('id', 'N/A')
                severity = defect.get('severity', '中')
                desc = defect.get('description', '')
                lines.append(f"- [{severity}] {defect_id} - {desc}\n")
            lines.append("\n")

        if data.get('risks'):
            lines.append("## 风险\n")
            for risk in data['risks']:
                lines.append(f"- {risk}\n")
            lines.append("\n")

        if data.get('conclusion'):
            lines.extend(["## 测试结论\n", data['conclusion'] + "\n\n"])

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_ops_doc(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '运维文档')}\n"]

        if data.get('system'):
            lines.extend(["## 系统信息\n", data['system'] + "\n\n"])

        if data.get('deployment_steps'):
            lines.append("## 部署步骤\n")
            for step in data['deployment_steps']:
                lines.append(f"- {step}\n")
            lines.append("\n")

        if data.get('monitoring'):
            lines.append("## 监控与告警\n")
            for item in data['monitoring']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('incident_response'):
            lines.append("## 故障处置\n")
            for item in data['incident_response']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('rollback'):
            lines.append("## 回滚方案\n")
            for item in data['rollback']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_email(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '邮件纪要')}\n"]

        sender = data.get('from')
        to_list = data.get('to', [])
        cc_list = data.get('cc', [])

        if sender or to_list or cc_list:
            lines.append("## 邮件头信息\n")
            if sender:
                lines.append(f"- **发件人：** {sender}\n")
            if to_list:
                lines.append(f"- **收件人：** {'、'.join(to_list)}\n")
            if cc_list:
                lines.append(f"- **抄送：** {'、'.join(cc_list)}\n")
            lines.append("\n")

        if data.get('summary'):
            lines.extend(["## 核心事项\n", data['summary'] + "\n\n"])

        if data.get('action_items'):
            lines.append("## 待办事项\n")
            for item in data['action_items']:
                task = item.get('task', '')
                owner = item.get('owner', '')
                line = f"- [ ] {task}"
                if owner:
                    line += f"（负责人：{owner}）"
                lines.append(line + "\n")
            lines.append("\n")

        if data.get('deadline'):
            lines.append(f"**截止时间：** {data['deadline']}\n\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)

    def _format_chat_log(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '聊天纪要')}\n"]

        if data.get('participants'):
            lines.append("## 参与者\n")
            for person in data['participants']:
                lines.append(f"- {person}\n")
            lines.append("\n")

        if data.get('context'):
            lines.extend(["## 对话背景\n", data['context'] + "\n\n"])

        if data.get('key_points'):
            lines.append("## 关键讨论点\n")
            for point in data['key_points']:
                lines.append(f"- {point}\n")
            lines.append("\n")

        if data.get('decisions'):
            lines.append("## 已达成结论\n")
            for item in data['decisions']:
                lines.append(f"- {item}\n")
            lines.append("\n")

        if data.get('action_items'):
            lines.append("## 待办事项\n")
            for item in data['action_items']:
                task = item.get('task', '')
                owner = item.get('owner', '')
                deadline = item.get('deadline', '')
                line = f"- [ ] {task}"
                if owner:
                    line += f"（负责人：{owner}）"
                if deadline:
                    line += f" @{deadline}"
                lines.append(line + "\n")
            lines.append("\n")

        if data.get('open_questions'):
            lines.append("## 未决问题\n")
            for question in data['open_questions']:
                lines.append(f"- {question}\n")
            lines.append("\n")

        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")

        return "".join(lines)
    
    def _format_book_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '读书笔记')}\n"]
        
        book_info = data.get('book_info', {})
        if book_info:
            lines.append("## 书籍信息\n")
            if book_info.get('title'):
                lines.append(f"- **书名：** {book_info['title']}\n")
            if book_info.get('author'):
                lines.append(f"- **作者：** {book_info['author']}\n")
            lines.append("\n")
        
        if data.get('key_insights'):
            lines.append("## 核心观点\n")
            for insight in data['key_insights']:
                lines.append(f"- {insight}\n")
            lines.append("\n")
        
        if data.get('quotes'):
            lines.append("## 精彩摘录\n")
            for quote in data['quotes']:
                text = quote.get('text', '')
                page = quote.get('page', '')
                lines.append(f"> {text}\n")
                if page:
                    lines.append(f"> （第 {page} 页）\n")
                lines.append("\n")
        
        if data.get('reflections'):
            lines.append("## 感悟与思考\n")
            for reflection in data['reflections']:
                lines.append(f"- {reflection}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_code_explanation(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '代码说明')}\n"]
        
        if data.get('overview'):
            lines.extend(["## 概述\n", data['overview'] + "\n\n"])
        
        if data.get('functions'):
            lines.append("## 函数/方法\n")
            for func in data['functions']:
                name = func.get('name', '')
                signature = func.get('signature', '')
                desc = func.get('description', '')
                lines.append(f"### `{signature}`\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('classes'):
            lines.append("## 类\n")
            for cls in data['classes']:
                name = cls.get('name', '')
                desc = cls.get('description', '')
                methods = cls.get('methods', [])
                lines.append(f"### {name}\n")
                lines.append(f"{desc}\n")
                if methods:
                    lines.append("**方法：** " + "、".join(methods) + "\n")
                lines.append("\n")
        
        if data.get('usage_examples'):
            lines.append("## 使用示例\n")
            for example in data['usage_examples']:
                lines.append(f"```\n{example}\n```\n\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_task_list(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '任务清单')}\n\n"]
        
        if data.get('tasks'):
            lines.append("## 任务清单\n")
            for task in data['tasks']:
                task_desc = task.get('task', '')
                priority = task.get('priority', '中')
                deadline = task.get('deadline', '')
                status = task.get('status', '待办')
                
                check_box = "[x]" if status in ("已完成", "Done") else "[ ]"
                line = f"- {check_box} {task_desc}（优先级：{priority}"
                if deadline:
                    line += f"，@{deadline}"
                line += "）\n"
                lines.append(line)
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_diary(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '日记')}\n"]
        
        if data.get('date'):
            lines.append(f"**日期：** {data['date']}\n")
        if data.get('mood'):
            lines.append(f"**心情：** {data['mood']}\n\n")
        
        if data.get('events'):
            lines.append("## 事件记录\n")
            for event in data['events']:
                lines.append(f"- {event}\n")
            lines.append("\n")
        
        if data.get('reflections'):
            lines.append("## 感悟\n")
            for reflection in data['reflections']:
                lines.append(f"- {reflection}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_generic_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '笔记')}\n"]
        
        if data.get('summary'):
            lines.extend(["## 摘要\n", data['summary'] + "\n\n"])
        
        if data.get('key_points'):
            lines.append("## 要点\n")
            for point in data['key_points']:
                lines.append(f"- {point}\n")
            lines.append("\n")
        
        if data.get('suggested_links'):
            lines.extend(["## 相关主题\n"])
            for link in data['suggested_links']:
                lines.append(f"- {link}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)

    def _format_knowledge_essay(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', '知识随笔')}\n"]
        
        if data.get('core_idea'):
            lines.extend(["## 核心观点\n", data['core_idea'] + "\n\n"])
        
        if data.get('key_insights'):
            lines.append("## 关键洞见\n")
            for insight in data['key_insights']:
                lines.append(f"- {insight}\n")
            lines.append("\n")
        
        if data.get('extended_thinking'):
            lines.append("## 延伸思考\n")
            for thought in data['extended_thinking']:
                lines.append(f"- {thought}\n")
            lines.append("\n")
        
        if data.get('related_concepts'):
            lines.append("## 关联概念\n")
            for concept in data['related_concepts']:
                lines.append(f"- {concept}\n")
            lines.append("\n")
        
        if data.get('notable_quotes'):
            lines.append("## 金句\n")
            for quote in data['notable_quotes']:
                lines.append(f"> {quote}\n\n")
        
        if data.get('tags'):
            lines.append("## 标签\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
