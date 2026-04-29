"""
Lumina Configuration Manager
处理配置加载、验证和优先级

配置优先级（从高到低）：
1. 指定配置文件（命令行传入 config_path）
2. 用户配置文件 ~/.lumina/lumina.yaml
3. 代码默认值

注意：LLM 配置已迁移到 llm.py，使用 LLMConfig 和 get_llm_provider
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .llm import LLMConfig as LLMProviderConfig


# 配置路径常量
USER_CONFIG_DIR = Path.home() / ".lumina"
USER_CONFIG_FILE = USER_CONFIG_DIR / "lumina.yaml"
DEFAULT_SUPPORTED_EXTENSIONS = [
    ".md", ".txt", ".sql", ".pdf", ".py", ".js", ".ts",
    ".json", ".yaml", ".yml", ".png", ".jpg"
]


@dataclass
class InputSource:
    """输入源配置"""
    path: str
    recursive: bool = True
    filter: Optional[str] = None

    def resolve_path(self) -> Path:
        """解析路径（支持 ~ 展开）"""
        return Path(os.path.expanduser(self.path))


@dataclass
class OutputConfig:
    """输出配置"""
    plugin: str = "obsidian"
    base_dir: str = "~/Lumina/Notes"
    vault_path: Optional[str] = None

    # 目录结构
    structure: Dict[str, bool] = field(default_factory=lambda: {
        "by_date": False,
        "by_type": True,
        "flat": False,
    })

    # PARA 知识分类目录映射（para_key -> 目录名），覆盖 Planner 默认映射
    categories: Dict[str, str] = field(default_factory=dict)

    # 生活场景列表（第一层目录）。格式：
    # - name: "工作"
    #   keywords: ["项目", "需求", "会议"]
    # 空列表＝不设场景层，直接使用 PARA单层
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    default_scene: str = ""  # 关键词匹配失败时的默认场景名

    # 命名约定
    naming: Dict[str, bool] = field(default_factory=lambda: {
        "prefix_date": False,
        "slugify": True,
    })

    def resolve_base_dir(self) -> Path:
        """解析输出根目录"""
        return Path(os.path.expanduser(self.base_dir))

    def resolve_vault_path(self) -> Optional[Path]:
        """解析 Vault 路径"""
        if self.vault_path:
            return Path(os.path.expanduser(self.vault_path))
        return None

    def get_output_path(self, note_title: str, file_type: str = "") -> Path:
        """根据配置生成输出路径"""
        base = self.resolve_base_dir()

        # 按类型分目录
        if self.structure.get("by_type") and file_type:
            base = base / file_type

        # 按日期分目录
        if self.structure.get("by_date"):
            from datetime import datetime
            today = datetime.now()
            base = base / f"{today.year}/{today.month:02d}"

        # 确保目录存在
        base.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        filename = note_title
        if self.naming.get("prefix_date"):
            from datetime import datetime
            today = datetime.now()
            filename = f"{today.strftime('%Y-%m-%d')}-{filename}"

        if self.naming.get("slugify"):
            filename = self._slugify(filename)

        return base / f"{filename}.md"

    def _slugify(self, text: str) -> str:
        """转义文件名"""
        import re
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-').lower()


@dataclass
class LuminaConfig:
    """Lumina 完整配置"""

    # 输入配置
    input_sources: List[InputSource] = field(default_factory=list)
    default_recursive: bool = True
    supported_extensions: List[str] = field(default_factory=lambda: DEFAULT_SUPPORTED_EXTENSIONS.copy())

    # 输出配置
    output: OutputConfig = field(default_factory=OutputConfig)

    # Harness 配置
    harness: Dict[str, Any] = field(default_factory=lambda: {
        "max_iterations": 3,
        "quality_threshold": 0.8,
    })

    # 服务配置
    service: Dict[str, Any] = field(default_factory=lambda: {
        "log_retention_days": 15,
    })

    # LLM 配置（使用 llm.py 中的 LLMConfig）
    llm: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    llm_planner: Optional[Dict[str, Any]] = None  # Planner 专用配置
    llm_executor: Optional[Dict[str, Any]] = None  # Executor 专用配置
    llm_validator: Optional[Dict[str, Any]] = None  # Validator 专用配置

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "LuminaConfig":
        """
        加载配置（按优先级合并）

        优先级：
        1. 指定配置文件（config_path）
        2. 用户配置文件 ~/.lumina/lumina.yaml
        3. 代码默认值

        Args:
            config_path: 指定用户配置文件路径（可选，覆盖默认路径）

        Returns:
            合并后的配置
        """
        import yaml

        # 收集配置
        user_config = {}

        # 1. 选择配置文件路径
        target_config_file = Path(config_path) if config_path else USER_CONFIG_FILE

        # 2. 首次使用时自动创建空白用户配置文件
        if not config_path and not target_config_file.exists():
            target_config_file.parent.mkdir(parents=True, exist_ok=True)
            target_config_file.write_text("", encoding="utf-8")

        # 3. 加载用户配置
        if target_config_file.exists():
            with open(target_config_file, 'r') as f:
                user_config = yaml.safe_load(f) or {}

        # 4. 用用户配置覆盖默认值创建配置
        return cls._from_dict(user_config)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "LuminaConfig":
        """从字典创建配置（未提供的字段使用默认值）"""
        input_data = data.get("input", {})

        # 解析输入源
        sources = []
        for source in input_data.get("sources", []):
            sources.append(InputSource(
                path=source["path"],
                recursive=source.get("recursive", True),
                filter=source.get("filter")
            ))

        # 输出配置
        output_data = data.get("output", {})
        output_config = OutputConfig(
            plugin=output_data.get("plugin", "obsidian"),
            base_dir=output_data.get("base_dir", "~/Lumina/Notes"),
            vault_path=output_data.get("vault_path"),
            structure=output_data.get("structure", {}),
            naming=output_data.get("naming", {}),
            categories=output_data.get("categories", {}),
            scenes=output_data.get("scenes", []),
            default_scene=output_data.get("default_scene", ""),
        )

        # 解析 LLM 配置（使用 llm.py 中的 LLMConfig）
        llm_data = data.get("llm", {})
        llm_config = LLMProviderConfig(
            provider=llm_data.get("provider", "openai"),
            base_url=llm_data.get("base_url"),
            api_key=llm_data.get("api_key"),
            model=llm_data.get("model", "gpt-4"),
            temperature=llm_data.get("temperature", 0.3),
            max_tokens=llm_data.get("max_tokens", 2000),
            timeout=llm_data.get("timeout", 60),
            max_retries=llm_data.get("max_retries", 3),
            retry_delay=llm_data.get("retry_delay", 1.0),
        )

        # 解析各 Agent 的 LLM 配置
        planner_llm_data = data.get("llm_planner")
        executor_llm_data = data.get("llm_executor")
        validator_llm_data = data.get("llm_validator")

        service_data = {"log_retention_days": 15}
        service_data.update(data.get("service", {}))

        return cls(
            input_sources=sources,
            default_recursive=input_data.get("default_recursive", True),
            supported_extensions=input_data.get("supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS.copy()),
            output=output_config,
            harness=data.get("harness", {}),
            service=service_data,
            llm=llm_config,
            llm_planner=planner_llm_data,
            llm_executor=executor_llm_data,
            llm_validator=validator_llm_data,
        )

    def validate(self) -> List[str]:
        """验证配置有效性"""
        errors = []

        # 验证输入源
        for i, source in enumerate(self.input_sources):
            path = source.resolve_path()
            if not path.exists():
                errors.append(f"Input source {i+1} does not exist: {path}")

        # 验证输出目录
        output_base = self.output.resolve_base_dir()
        try:
            output_base.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            errors.append(f"Cannot create output directory: {output_base}")

        # 验证 Vault 路径
        if self.output.vault_path:
            vault = self.output.resolve_vault_path()
            if vault and not vault.exists():
                errors.append(f"Vault path does not exist: {vault}")

        # 验证 LLM 配置
        llm_errors = self.llm.validate()
        errors.extend(llm_errors)

        return errors

    def save_user_config(self):
        """保存当前配置到 ~/.lumina/lumina.yaml"""
        import yaml

        config_dict = {
            "input": {
                "sources": [
                    {
                        "path": s.path,
                        "recursive": s.recursive,
                        "filter": s.filter,
                    }
                    for s in self.input_sources
                ],
                "default_recursive": self.default_recursive,
                "supported_extensions": self.supported_extensions,
            },
            "output": {
                "plugin": self.output.plugin,
                "base_dir": self.output.base_dir,
                "vault_path": self.output.vault_path,
                "structure": self.output.structure,
                "naming": self.output.naming,
            },
            "llm": self.llm.to_dict(),
            "harness": self.harness,
            "service": self.service,
        }

        USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_CONFIG_FILE, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
