"""
Harness - 核心协调器
整合 Planner + Executor + Validator，实现迭代优化
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from .planner import Planner, FileInfo
from .executor import Executor, NoteOutput
from .validator import Validator, ValidationResult


@dataclass
class HarnessConfig:
    """Harness 配置"""
    max_iterations: int = 3
    quality_threshold: float = 0.8
    output_dir: str = "./output"
    vault_path: Optional[str] = None


class Harness:
    """
    Harness - 知识萃取的核心控制器
    
    职责：
    1. 协调 Planner/Executor/Validator 三元组
    2. 管理迭代优化循环
    3. 处理质量阈值和终止条件
    4. 输出最终笔记到指定位置
    
    工作流程：
    ```
    扫描 → 规划 → 执行 → 验证 → [修复] → 输出
              ↑_________________↓
              (最多3轮迭代)
    ```
    """
    
    def __init__(self, config: HarnessConfig = None):
        self.config = config or HarnessConfig()
        
        # 初始化三元组
        self.planner = Planner()
        self.executor = Executor()
        self.validator = Validator()
        
        # 运行状态
        self.iteration_count = 0
        self.best_output: Optional[NoteOutput] = None
        self.best_score = 0.0
        self.history: List[Dict[str, Any]] = []
    
    def run(self, input_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        执行完整 Harness 流程
        
        Args:
            input_path: 输入文件或目录
            recursive: 是否递归扫描
            
        Returns:
            执行结果报告
        """
        print(f"🔍 Lumina Harness v0.1.0")
        print(f"📂 Scanning: {input_path}")
        
        # Phase 1: 规划
        files = self.planner.scan(input_path, recursive)
        plan = self.planner.plan(files)
        
        print(f"📊 Found {plan['total_files']} files")
        print(f"🎯 Strategy: {plan['strategy']}")
        
        # Phase 2-4: 执行 → 验证 → 迭代
        results = []
        for batch_idx, batch in enumerate(plan['batches']):
            print(f"\n📦 Processing batch {batch_idx + 1}/{len(plan['batches'])}")
            
            for file_info in batch:
                result = self._process_single(file_info, plan)
                results.append(result)
        
        # Phase 5: 输出
        output_report = self._generate_report(results)
        self._save_outputs(results)
        
        return output_report
    
    def _process_single(self, file_info: FileInfo, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个文件，包含迭代优化
        
        Returns:
            处理结果（含迭代历史）
        """
        self.iteration_count = 0
        current_output = None
        
        iteration_history = []
        
        for iteration in range(self.config.max_iterations):
            self.iteration_count += 1
            
            # 执行
            if iteration == 0:
                current_output = self.executor.execute(file_info, plan)
            else:
                # 基于反馈修复
                current_output = self._revise_output(
                    current_output, 
                    iteration_history[-1]['validation']
                )
            
            # 验证
            validation = self.validator.validate(current_output)
            
            # 记录
            iteration_history.append({
                "round": iteration + 1,
                "output": {
                    "title": current_output.title,
                    "content_length": len(current_output.content),
                    "tags": current_output.tags,
                },
                "validation": {
                    "score": validation.score,
                    "passed": validation.passed,
                    "issues": len(validation.issues),
                }
            })
            
            print(f"  Round {iteration + 1}: score={validation.score:.2f}, passed={validation.passed}")
            
            # 检查终止条件
            if validation.passed and validation.score >= self.config.quality_threshold:
                print(f"  ✅ Quality threshold reached!")
                break
            
            if not validation.suggestions:
                print(f"  ⚠️  No suggestions for improvement, stopping")
                break
        
        # 选择最佳输出
        best_iteration = max(iteration_history, key=lambda x: x['validation']['score'])
        
        return {
            "source": str(file_info.path),
            "iterations": len(iteration_history),
            "best_round": best_iteration['round'],
            "best_score": best_iteration['validation']['score'],
            "final_output": current_output,
            "history": iteration_history,
        }
    
    def _revise_output(self, current: NoteOutput, prev_validation: Dict) -> NoteOutput:
        """
        基于验证反馈修复输出
        
        这是 Harness 的核心：根据 Evaluator 反馈改进 Generator 输出
        """
        # TODO: 实现基于反馈的修复逻辑
        # 当前简化：直接返回（实际应调用 LLM 修复）
        return current
    
    def _generate_report(self, results: List[Dict]) -> Dict[str, Any]:
        """生成执行报告"""
        total_files = len(results)
        avg_iterations = sum(r['iterations'] for r in results) / total_files if total_files else 0
        avg_score = sum(r['best_score'] for r in results) / total_files if total_files else 0
        
        return {
            "total_files": total_files,
            "avg_iterations": avg_iterations,
            "avg_score": avg_score,
            "threshold": self.config.quality_threshold,
            "results": [
                {
                    "source": r['source'],
                    "iterations": r['iterations'],
                    "best_score": r['best_score'],
                }
                for r in results
            ]
        }
    
    def _save_outputs(self, results: List[Dict]):
        """保存输出到文件"""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for result in results:
            output = result['final_output']
            if not output:
                continue
            
            # 生成文件名
            safe_title = "".join(c if c.isalnum() or c in (' ', '-') else '_' for c in output.title)
            filename = f"{safe_title}.md"
            filepath = output_dir / filename
            
            # 写入文件
            content = self._format_output(output, result)
            filepath.write_text(content, encoding='utf-8')
            
            print(f"  💾 Saved: {filepath}")
    
    def _format_output(self, output: NoteOutput, result: Dict) -> str:
        """格式化输出内容"""
        lines = [
            f"---",
            f"title: {output.title}",
            f"tags: {json.dumps(output.tags)}",
            f"source: {output.source}",
            f"lumina_score: {result['best_score']}",
            f"lumina_iterations: {result['iterations']}",
            f"---",
            f"",
            output.content,
            f"",
            f"## Lumina Metadata",
            f"- Generated by: Lumina v0.1.0",
            f"- Best iteration: {result['best_round']}/{result['iterations']}",
            f"- Quality score: {result['best_score']:.2f}",
            f"",
        ]
        
        if output.links:
            lines.extend([
                f"## Related",
            ])
            for link in output.links:
                lines.append(f"- [[{link}]]")
        
        return "\n".join(lines)