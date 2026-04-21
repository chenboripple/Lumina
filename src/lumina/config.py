"""
Lumina Configuration Manager
处理输入/输出目录的配置和验证
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


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
        """
        根据配置生成输出路径
        
        Args:
            note_title: 笔记标题
            file_type: 原始文件类型（用于 by_type 分类）
            
        Returns:
            输出文件路径
        """
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
        # 替换非法字符
        text = re.sub(r'[^\w\s-]', '', text)
        # 替换空格为连字符
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-').lower()


@dataclass
class LuminaConfig:
    """Lumina 完整配置"""
    
    # 输入配置
    input_sources: List[InputSource] = field(default_factory=list)
    default_recursive: bool = True
    supported_extensions: List[str] = field(default_factory=lambda: [
        ".md", ".txt", ".pdf", ".py", ".js", ".ts", 
        ".json", ".yaml", ".yml", ".png", ".jpg"
    ])
    
    # 输出配置
    output: OutputConfig = field(default_factory=OutputConfig)
    
    # Harness 配置
    harness: Dict[str, Any] = field(default_factory=lambda: {
        "max_iterations": 3,
        "quality_threshold": 0.8,
    })
    
    # LLM 配置
    llm: Dict[str, Any] = field(default_factory=lambda: {
        "provider": "openai",
        "model": "gpt-4",
        "temperature": 0.3,
        "max_tokens": 2000,
    })
    
    @classmethod
    def from_yaml(cls, path: str) -> "LuminaConfig":
        """从 YAML 文件加载配置"""
        import yaml
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # 解析输入源
        sources = []
        for source in data.get("input", {}).get("sources", []):
            sources.append(InputSource(
                path=source["path"],
                recursive=source.get("recursive", True),
                filter=source.get("filter")
            ))
        
        # 解析输出配置
        output_data = data.get("output", {})
        output = OutputConfig(
            plugin=output_data.get("plugin", "obsidian"),
            base_dir=output_data.get("base_dir", "~/Lumina/Notes"),
            vault_path=output_data.get("vault_path"),
            structure=output_data.get("structure", {}),
            naming=output_data.get("naming", {}),
        )
        
        return cls(
            input_sources=sources,
            default_recursive=data.get("input", {}).get("default_recursive", True),
            supported_extensions=data.get("input", {}).get("supported_extensions", []),
            output=output,
            harness=data.get("harness", {}),
            llm=data.get("llm", {}),
        )
    
    def validate(self) -> List[str]:
        """
        验证配置有效性
        
        Returns:
            错误信息列表（空表示有效）
        """
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
        
        # 验证 Vault 路径（如果配置）
        if self.output.vault_path:
            vault = self.output.resolve_vault_path()
            if vault and not vault.exists():
                errors.append(f"Vault path does not exist: {vault}")
        
        return errors