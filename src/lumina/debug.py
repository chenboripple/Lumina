"""
Lumina 本地调试模式
提供交互式调试、单文件处理、详细日志输出等功能
"""

import json
import time
import sys
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from .harness import Harness, HarnessConfig
from .config import LuminaConfig
from .planner import FileInfo, ProcessingPlan
from .executor import NoteOutput, ExecutionContext
from .validator import ValidationResult
from .llm import get_llm_provider, LLMConfig


class LuminaDebugger:
    """
    Lumina 调试器
    
    功能：
    1. 🔍 单文件逐步调试 - 逐步执行 Planner/Executor/Validator
    2. 📊 详细日志输出 - 每个阶段的输入输出
    3. 🧪 交互式测试 - 手动输入内容测试各组件
    4. 📈 性能分析 - 各阶段耗时统计
    5. 🎯 配置验证 - 检查配置是否正确
    """
    
    def __init__(self, harness: Harness = None):
        self.harness = harness
        self.debug_logs: List[Dict[str, Any]] = []
        self.step_count = 0
    
    def log_step(self, phase: str, action: str, data: Any = None):
        """记录调试步骤"""
        self.step_count += 1
        log_entry = {
            "step": self.step_count,
            "timestamp": time.time(),
            "phase": phase,
            "action": action,
            "data": data,
        }
        self.debug_logs.append(log_entry)
        print(f"\n🔍 [Step {self.step_count}] {phase} - {action}")
        if data:
            print(f"   Data: {self._format_data(data)}")
    
    def _format_data(self, data: Any, max_length: int = 500) -> str:
        """格式化数据用于显示"""
        if isinstance(data, str):
            if len(data) > max_length:
                return data[:max_length] + "..."
            return data
        elif isinstance(data, (dict, list)):
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            if len(json_str) > max_length:
                return json_str[:max_length] + "..."
            return json_str
        elif hasattr(data, '__dataclass_fields__'):
            # dataclass
            return str(asdict(data))[:max_length]
        else:
            return str(data)[:max_length]
    
    def debug_single_file(self, file_path: str, config: HarnessConfig = None) -> Dict[str, Any]:
        """
        单文件逐步调试
        
        流程：
        1. 扫描文件
        2. 分析文件信息
        3. 规划处理策略
        4. 执行笔记生成
        5. 验证输出质量
        6. 输出结果
        
        Args:
            file_path: 文件路径
            config: Harness 配置（可选）
            
        Returns:
            完整的调试报告
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        print("=" * 60)
        print("🐛 Lumina 单文件调试模式")
        print("=" * 60)
        print(f"📄 目标文件: {file_path}")
        print(f"📏 文件大小: {file_path.stat().st_size} bytes")
        print()
        
        # 初始化 Harness
        if not self.harness:
            self.harness = Harness(config or HarnessConfig())
        
        debug_report = {
            "file_path": str(file_path),
            "start_time": time.time(),
            "steps": [],
        }
        
        try:
            # Step 1: 扫描文件
            self.log_step("Planner", "扫描文件")
            files = self.harness.planner.scan(str(file_path), recursive=False)
            
            if not files:
                print("❌ 未找到可处理的文件")
                return debug_report
            
            file_info = files[0]
            self.log_step("Planner", "文件分析完成", {
                "path": str(file_info.path),
                "type": file_info.type,
                "size": file_info.size,
                "hash": file_info.hash[:16] + "...",
                "estimated_cost": file_info.estimated_cost,
                "required_capabilities": file_info.required_capabilities,
            })
            
            # Step 2: 规划
            self.log_step("Planner", "制定处理计划")
            plan = self.harness.planner.plan([file_info])
            self.log_step("Planner", "处理计划", {
                "strategy": plan.strategy,
                "total_files": plan.total_files,
                "estimated_cost": plan.total_estimated_cost,
                "batches": len(plan.batches),
                "summary": plan.summary,
            })
            
            # Step 3: 执行
            self.log_step("Executor", "开始生成笔记")
            exec_start = time.time()
            
            context = ExecutionContext(
                session_id=f"debug_{int(time.time())}",
                file_info=file_info,
                plan={"strategy": plan.strategy},
            )
            
            output = self.harness.executor.execute(context)
            exec_duration = time.time() - exec_start
            
            self.log_step("Executor", "笔记生成完成", {
                "title": output.title,
                "content_length": len(output.content),
                "tags": output.tags,
                "links": output.links,
                "duration": f"{exec_duration:.2f}s",
                "strategy": output.processing_info.get("prompt_strategy", "unknown"),
            })
            
            # 显示生成的内容预览
            print(f"\n📝 生成内容预览:")
            print("-" * 40)
            preview = output.content[:500] + "..." if len(output.content) > 500 else output.content
            print(preview)
            print("-" * 40)
            
            # Step 4: 验证
            self.log_step("Validator", "开始质量验证")
            validation_start = time.time()
            
            validation = self.harness.validator.validate(output, file_info, context)
            validation_duration = time.time() - validation_start
            
            self.log_step("Validator", "验证完成", {
                "passed": validation.passed,
                "score": validation.score,
                "issues_count": len(validation.issues),
                "error_count": validation.metadata.get("error_count", 0),
                "warning_count": validation.metadata.get("warning_count", 0),
                "duration": f"{validation_duration:.2f}s",
            })
            
            # 显示问题详情
            if validation.issues:
                print(f"\n⚠️  发现的问题:")
                for i, issue in enumerate(validation.issues[:5], 1):
                    severity_emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "•")
                    print(f"   {severity_emoji} [{issue.severity.upper()}] {issue.type}: {issue.message}")
                    if issue.fix_suggestion:
                        print(f"      💡 建议: {issue.fix_suggestion}")
            
            # Step 5: 格式化输出
            self.log_step("Output", "格式化输出")
            formatted = self.harness._format_output(output, {
                "best_score": validation.score,
                "iterations": 1,
                "best_round": 1,
            })
            
            self.log_step("Output", "格式化完成", {
                "output_length": len(formatted),
                "plugin": self.harness.config.plugin,
            })
            
            # 显示最终输出预览
            print(f"\n📄 最终输出预览:")
            print("-" * 40)
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            print("-" * 40)
            
            # 生成完整报告
            debug_report.update({
                "success": True,
                "file_info": {
                    "path": str(file_info.path),
                    "type": file_info.type,
                    "size": file_info.size,
                },
                "plan": {
                    "strategy": plan.strategy,
                    "estimated_cost": plan.total_estimated_cost,
                },
                "output": {
                    "title": output.title,
                    "content_length": len(output.content),
                    "tags": output.tags,
                    "links": output.links,
                },
                "validation": {
                    "passed": validation.passed,
                    "score": validation.score,
                    "issues": [
                        {
                            "type": i.type,
                            "severity": i.severity,
                            "message": i.message,
                        }
                        for i in validation.issues
                    ],
                },
                "timings": {
                    "execution": exec_duration,
                    "validation": validation_duration,
                    "total": time.time() - debug_report["start_time"],
                },
            })
            
        except Exception as e:
            print(f"\n❌ 调试过程中出现错误:")
            traceback.print_exc()
            debug_report["success"] = False
            debug_report["error"] = str(e)
            debug_report["traceback"] = traceback.format_exc()
        
        # 输出总结
        print("\n" + "=" * 60)
        print("📊 调试总结")
        print("=" * 60)
        print(f"✅ 状态: {'成功' if debug_report.get('success') else '失败'}")
        if "timings" in debug_report:
            print(f"⏱️  总耗时: {debug_report['timings']['total']:.2f}s")
        if "validation" in debug_report:
            print(f"⭐ 质量得分: {debug_report['validation']['score']:.2f}")
            print(f"🎯 验证通过: {'是' if debug_report['validation']['passed'] else '否'}")
        print("=" * 60)
        
        return debug_report
    
    def test_llm_connection(self, llm_config: Dict[str, Any] = None) -> bool:
        """
        测试 LLM 连接
        
        Args:
            llm_config: LLM 配置（可选，使用默认配置）
            
        Returns:
            连接是否成功
        """
        print("🧪 测试 LLM 连接...")
        
        try:
            if not llm_config:
                llm_config = {"provider": "openai", "model": "gpt-3.5-turbo"}
            
            provider = get_llm_provider(llm_config)
            
            # 发送测试请求
            test_prompt = "Say 'Hello from Lumina' and nothing else."
            response = provider.complete(test_prompt)
            
            print(f"✅ LLM 连接成功!")
            print(f"   响应: {response[:100]}...")
            return True
            
        except Exception as e:
            print(f"❌ LLM 连接失败: {e}")
            return False
    
    def validate_config(self, config: LuminaConfig = None) -> List[str]:
        """
        验证配置
        
        Args:
            config: LuminaConfig 配置（可选）
            
        Returns:
            错误列表（空列表表示配置正确）
        """
        print("🔧 验证配置...")
        
        if not config:
            config = LuminaConfig.load()
        
        errors = config.validate()
        
        if errors:
            print(f"❌ 发现 {len(errors)} 个配置错误:")
            for error in errors:
                print(f"   - {error}")
        else:
            print("✅ 配置验证通过!")
        
        return errors
    
    def interactive_test(self):
        """交互式测试模式"""
        print("\n" + "=" * 60)
        print("🎮 Lumina 交互式测试模式")
        print("=" * 60)
        print("\n可用命令:")
        print("  1. test_llm     - 测试 LLM 连接")
        print("  2. test_file    - 测试单文件处理")
        print("  3. test_config  - 验证配置")
        print("  4. show_logs    - 显示调试日志")
        print("  5. clear_logs   - 清除调试日志")
        print("  6. quit         - 退出")
        print()
        
        while True:
            try:
                command = input("lumina-debug> ").strip().lower()
                
                if command in ("quit", "exit", "q"):
                    print("👋 再见!")
                    break
                
                elif command == "test_llm":
                    provider = input("提供商 (openai/anthropic) [openai]: ").strip() or "openai"
                    model = input("模型 [gpt-3.5-turbo]: ").strip() or "gpt-3.5-turbo"
                    self.test_llm_connection({"provider": provider, "model": model})
                
                elif command == "test_file":
                    file_path = input("文件路径: ").strip()
                    if file_path:
                        self.debug_single_file(file_path)
                
                elif command == "test_config":
                    config_path = input("配置文件路径 [~/.lumina.yaml]: ").strip()
                    if config_path:
                        config = LuminaConfig.load(config_path)
                    else:
                        config = LuminaConfig.load()
                    self.validate_config(config)
                
                elif command == "show_logs":
                    print(f"\n📋 调试日志 ({len(self.debug_logs)} 条):")
                    for log in self.debug_logs[-10:]:  # 显示最后10条
                        print(f"  Step {log['step']}: [{log['phase']}] {log['action']}")
                
                elif command == "clear_logs":
                    self.debug_logs.clear()
                    self.step_count = 0
                    print("🧹 日志已清除")
                
                else:
                    print("❓ 未知命令，输入 'help' 查看可用命令")
                    
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")


def run_debug_mode():
    """运行调试模式（入口函数）"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Lumina 调试模式")
    parser.add_argument("file", nargs="?", help="要调试的文件路径")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互式模式")
    parser.add_argument("--test-llm", action="store_true", help="测试 LLM 连接")
    parser.add_argument("--validate-config", action="store_true", help="验证配置")
    
    args = parser.parse_args()
    
    debugger = LuminaDebugger()
    
    if args.interactive:
        debugger.interactive_test()
    elif args.test_llm:
        debugger.test_llm_connection()
    elif args.validate_config:
        if args.config:
            config = LuminaConfig.load(args.config)
        else:
            config = LuminaConfig.load()
        debugger.validate_config(config)
    elif args.file:
        # 单文件调试
        harness_config = HarnessConfig()
        if args.config:
            lumina_config = LuminaConfig.load(args.config)
            harness_config = HarnessConfig(
                max_iterations=lumina_config.harness.get("max_iterations", 3),
                quality_threshold=lumina_config.harness.get("quality_threshold", 0.8),
                plugin=lumina_config.output.plugin,
                llm_config=lumina_config.llm.to_dict(),
            )
        
        debugger.debug_single_file(args.file, harness_config)
    else:
        # 默认进入交互式模式
        print("🐛 Lumina 调试模式")
        print("使用 --help 查看所有选项")
        print()
        debugger.interactive_test()


if __name__ == "__main__":
    run_debug_mode()
