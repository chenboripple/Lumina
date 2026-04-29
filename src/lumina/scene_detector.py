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
    BOOK_NOTES = "book_notes"  # 读书笔记
    CODE_EXPLANATION = "code_explanation"  # 代码说明
    DIARY = "diary"  # 日记
    TASK_LIST = "task_list"  # 任务列表
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
        return """You are a meeting notes expert. Analyze this meeting content and generate structured meeting notes.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract meeting title, date, and attendees
2. List agenda items covered
3. Summarize key decisions made
4. Identify action items with responsible persons and deadlines
5. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Meeting Title - YYYY-MM-DD",
    "meeting_date": "YYYY-MM-DD",
    "attendees": ["Person A", "Person B"],
    "agenda": ["Agenda Item 1", "Agenda Item 2"],
    "decisions": ["Decision 1", "Decision 2"],
    "action_items": [
        {{
            "task": "Task description",
            "owner": "Person responsible",
            "deadline": "YYYY-MM-DD"
        }}
    ],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _technical_doc_prompt_template(self) -> str:
        return """You are a technical documentation expert. Analyze this technical content and generate structured documentation.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract overview/summary of the system
2. Document architecture/design if mentioned
3. Extract API specifications (endpoints, parameters, responses)
4. Document implementation details
5. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Component/System Name",
    "overview": "Brief overview of the system",
    "architecture": ["Architecture point 1", "Architecture point 2"],
    "api_spec": [
        {{
            "endpoint": "/api/v1/resource",
            "method": "GET",
            "description": "What this API does"
        }}
    ],
    "implementation": ["Implementation detail 1"],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _requirements_prompt_template(self) -> str:
        return """You are a requirements engineering expert. Analyze this requirements content and generate structured requirements.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract requirements title and overview
2. List feature requirements
3. Define acceptance criteria
4. Set priorities (High/Medium/Low)
5. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Requirements Title",
    "overview": "Brief overview",
    "features": [
        {{
            "name": "Feature Name",
            "description": "What this feature does",
            "priority": "High|Medium|Low"
        }}
    ],
    "acceptance_criteria": ["Criterion 1", "Criterion 2"],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _book_notes_prompt_template(self) -> str:
        return """You are a book notes expert. Analyze this reading notes content and generate structured book notes.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract book title, author
2. List key insights
3. Capture important quotes
4. Record personal reflections
5. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Book Notes: Book Title",
    "book_info": {{
        "title": "Book Title",
        "author": "Author Name"
    }},
    "key_insights": ["Insight 1", "Insight 2"],
    "quotes": [
        {{
            "text": "Quote text",
            "page": "Page number (if available)"
        }}
    ],
    "reflections": ["Reflection 1"],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _code_explanation_prompt_template(self) -> str:
        return """You are a code documentation expert. Analyze this code content and generate structured code explanation.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract code overview/purpose
2. Document functions/methods with signatures and descriptions
3. Document classes with attributes and methods
4. Provide usage examples if present
5. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Component/File Name",
    "overview": "What this code does",
    "functions": [
        {{
            "name": "function_name",
            "signature": "def func_name(params)",
            "description": "What this function does"
        }}
    ],
    "classes": [
        {{
            "name": "ClassName",
            "description": "What this class does",
            "methods": ["method1", "method2"]
        }}
    ],
    "usage_examples": ["Code example 1"],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _task_list_prompt_template(self) -> str:
        return """You are a task management expert. Analyze this task list and generate structured tasks.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract task list title
2. List all tasks with descriptions
3. Capture priorities, deadlines, status
4. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Task List Title",
    "tasks": [
        {{
            "task": "Task description",
            "priority": "High|Medium|Low",
            "deadline": "YYYY-MM-DD (if available)",
            "status": "Todo|In Progress|Done|Blocked"
        }}
    ],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _diary_prompt_template(self) -> str:
        return """You are a journaling expert. Analyze this diary content and generate structured diary entry.

## Source Information
- File: {filename}

## Content
```
{content}
```

## Instructions
1. Extract date, mood
2. Record key events
3. Capture reflections/feelings
4. Add relevant tags

## Output Format
Return JSON with this structure:
{{
    "title": "Diary - YYYY-MM-DD",
    "date": "YYYY-MM-DD",
    "mood": "Mood description",
    "events": ["Event 1", "Event 2"],
    "reflections": ["Reflection 1"],
    "tags": ["tag1", "tag2"],
    "metadata": {{
        "confidence": 0.95
    }}
}}
"""
    
    def _generic_prompt_template(self) -> str:
        return """You are a knowledge extraction expert. Analyze the following content and generate a structured note.

## Source Information
- File: {filename}
- Type: {file_type}

## Content
```
{content}
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
    
    # === Markdown 格式化函数 ===
    
    def _format_meeting_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Meeting Notes')}\n"]
        
        if data.get('meeting_date'):
            lines.append(f"**Date:** {data['meeting_date']}\n\n")
        
        if data.get('attendees'):
            lines.append("## Attendees\n")
            for attendee in data['attendees']:
                lines.append(f"- {attendee}\n")
            lines.append("\n")
        
        if data.get('agenda'):
            lines.append("## Agenda\n")
            for item in data['agenda']:
                lines.append(f"- {item}\n")
            lines.append("\n")
        
        if data.get('decisions'):
            lines.append("## Decisions\n")
            for decision in data['decisions']:
                lines.append(f"- {decision}\n")
            lines.append("\n")
        
        if data.get('action_items'):
            lines.append("## Action Items\n")
            for item in data['action_items']:
                task = item.get('task', '')
                owner = item.get('owner', '')
                deadline = item.get('deadline', '')
                line = f"- [ ] {task}"
                if owner:
                    line += f" (Owner: {owner})"
                if deadline:
                    line += f" @{deadline}"
                lines.append(line + "\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_technical_doc(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Technical Documentation')}\n"]
        
        if data.get('overview'):
            lines.extend(["## Overview\n", data['overview'] + "\n\n"])
        
        if data.get('architecture'):
            lines.append("## Architecture\n")
            for point in data['architecture']:
                lines.append(f"- {point}\n")
            lines.append("\n")
        
        if data.get('api_spec'):
            lines.append("## API Specification\n")
            for api in data['api_spec']:
                method = api.get('method', 'GET')
                endpoint = api.get('endpoint', '')
                desc = api.get('description', '')
                lines.append(f"### `{method} {endpoint}`\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('implementation'):
            lines.append("## Implementation\n")
            for detail in data['implementation']:
                lines.append(f"- {detail}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_requirements(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Requirements')}\n"]
        
        if data.get('overview'):
            lines.extend(["## Overview\n", data['overview'] + "\n\n"])
        
        if data.get('features'):
            lines.append("## Features\n")
            for feature in data['features']:
                name = feature.get('name', '')
                desc = feature.get('description', '')
                priority = feature.get('priority', 'Medium')
                lines.append(f"### {name} (Priority: {priority})\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('acceptance_criteria'):
            lines.append("## Acceptance Criteria\n")
            for criterion in data['acceptance_criteria']:
                lines.append(f"- [ ] {criterion}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_book_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Book Notes')}\n"]
        
        book_info = data.get('book_info', {})
        if book_info:
            lines.append("## Book Information\n")
            if book_info.get('title'):
                lines.append(f"- **Title:** {book_info['title']}\n")
            if book_info.get('author'):
                lines.append(f"- **Author:** {book_info['author']}\n")
            lines.append("\n")
        
        if data.get('key_insights'):
            lines.append("## Key Insights\n")
            for insight in data['key_insights']:
                lines.append(f"- {insight}\n")
            lines.append("\n")
        
        if data.get('quotes'):
            lines.append("## Quotes\n")
            for quote in data['quotes']:
                text = quote.get('text', '')
                page = quote.get('page', '')
                lines.append(f"> {text}\n")
                if page:
                    lines.append(f"> (Page {page})\n")
                lines.append("\n")
        
        if data.get('reflections'):
            lines.append("## Reflections\n")
            for reflection in data['reflections']:
                lines.append(f"- {reflection}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_code_explanation(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Code Documentation')}\n"]
        
        if data.get('overview'):
            lines.extend(["## Overview\n", data['overview'] + "\n\n"])
        
        if data.get('functions'):
            lines.append("## Functions\n")
            for func in data['functions']:
                name = func.get('name', '')
                signature = func.get('signature', '')
                desc = func.get('description', '')
                lines.append(f"### `{signature}`\n")
                lines.append(f"{desc}\n\n")
        
        if data.get('classes'):
            lines.append("## Classes\n")
            for cls in data['classes']:
                name = cls.get('name', '')
                desc = cls.get('description', '')
                methods = cls.get('methods', [])
                lines.append(f"### {name}\n")
                lines.append(f"{desc}\n")
                if methods:
                    lines.append("**Methods:** " + ", ".join(methods) + "\n")
                lines.append("\n")
        
        if data.get('usage_examples'):
            lines.append("## Usage Examples\n")
            for example in data['usage_examples']:
                lines.append(f"```\n{example}\n```\n\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_task_list(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Tasks')}\n\n"]
        
        if data.get('tasks'):
            lines.append("## Task List\n")
            for task in data['tasks']:
                task_desc = task.get('task', '')
                priority = task.get('priority', 'Medium')
                deadline = task.get('deadline', '')
                status = task.get('status', 'Todo')
                
                check_box = "[x]" if status == "Done" else "[ ]"
                line = f"- {check_box} {task_desc} (Priority: {priority}"
                if deadline:
                    line += f", @{deadline}"
                line += ")\n"
                lines.append(line)
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_diary(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Diary Entry')}\n"]
        
        if data.get('date'):
            lines.append(f"**Date:** {data['date']}\n")
        if data.get('mood'):
            lines.append(f"**Mood:** {data['mood']}\n\n")
        
        if data.get('events'):
            lines.append("## Events\n")
            for event in data['events']:
                lines.append(f"- {event}\n")
            lines.append("\n")
        
        if data.get('reflections'):
            lines.append("## Reflections\n")
            for reflection in data['reflections']:
                lines.append(f"- {reflection}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
    
    def _format_generic_notes(self, data: Dict[str, Any]) -> str:
        lines = [f"# {data.get('title', 'Untitled')}\n"]
        
        if data.get('summary'):
            lines.extend(["## Summary\n", data['summary'] + "\n\n"])
        
        if data.get('key_points'):
            lines.append("## Key Points\n")
            for point in data['key_points']:
                lines.append(f"- {point}\n")
            lines.append("\n")
        
        if data.get('suggested_links'):
            lines.extend(["## Related Topics\n"])
            for link in data['suggested_links']:
                lines.append(f"- {link}\n")
            lines.append("\n")
        
        if data.get('tags'):
            lines.append("## Tags\n")
            tags_str = " ".join([f"#{tag}" for tag in data['tags']])
            lines.append(tags_str + "\n")
        
        return "".join(lines)
