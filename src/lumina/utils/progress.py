"""
Progress Tracker - 进度可视化模块
支持进度条、实时状态更新、ETA计算
"""

import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ProgressState:
    """进度状态"""
    total: int
    current: int = 0
    status: str = "initialized"
    start_time: float = field(default_factory=time.time)
    current_phase: str = ""
    current_file: str = ""
    errors: list = field(default_factory=list)
    
    @property
    def percentage(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100
    
    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time
    
    @property
    def eta(self) -> Optional[float]:
        if self.current == 0 or self.total == 0:
            return None
        avg_time = self.elapsed / self.current
        remaining = self.total - self.current
        return avg_time * remaining
    
    @property
    def rate(self) -> float:
        if self.elapsed == 0:
            return 0.0
        return self.current / self.elapsed


class ProgressTracker:
    """
    进度追踪器
    
    支持：
    1. 进度条显示（文本/图形）
    2. 实时状态更新
    3. 阶段跟踪
    4. ETA 计算
    5. 错误收集
    6. 回调通知
    """
    
    def __init__(
        self,
        total: int,
        description: str = "Processing",
        callback: Optional[Callable[[ProgressState], None]] = None,
        show_bar: bool = True,
        width: int = 40
    ):
        self.state = ProgressState(total=total)
        self.description = description
        self.callback = callback
        self.show_bar = show_bar
        self.width = width
        self._last_update = 0
        self._update_interval = 0.1  # 最小更新间隔（秒）
    
    def update(self, increment: int = 1, status: Optional[str] = None):
        """更新进度"""
        self.state.current += increment
        if status:
            self.state.status = status
        
        self._notify()
    
    def set_phase(self, phase: str, current_file: str = ""):
        """设置当前阶段"""
        self.state.current_phase = phase
        if current_file:
            self.state.current_file = current_file
        self._notify()
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.state.errors.append({
            "time": time.time(),
            "message": error
        })
        self._notify()
    
    def _notify(self):
        """通知回调（带节流）"""
        now = time.time()
        if now - self._last_update < self._update_interval:
            return
        self._last_update = now
        
        if self.callback:
            self.callback(self.state)
        
        if self.show_bar:
            self._print_bar()
    
    def _print_bar(self):
        """打印进度条"""
        pct = self.state.percentage
        filled = int(self.width * pct / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        
        # 计算 ETA
        eta_str = "N/A"
        if self.state.eta is not None:
            eta_mins = int(self.state.eta / 60)
            eta_secs = int(self.state.eta % 60)
            eta_str = f"{eta_mins}m{eta_secs}s"
        
        # 当前阶段信息
        phase_info = ""
        if self.state.current_phase:
            phase_info = f" | {self.state.current_phase}"
        if self.state.current_file:
            phase_info += f": {self.state.current_file[:30]}"
        
        # 错误统计
        error_info = ""
        if self.state.errors:
            error_info = f" | ⚠️ {len(self.state.errors)} errors"
        
        print(
            f"\r{self.description}: [{bar}] {pct:.1f}% "
            f"({self.state.current}/{self.state.total}) "
            f"ETA: {eta_str}{phase_info}{error_info}",
            end="",
            flush=True
        )
        
        if self.state.current >= self.state.total:
            print()  # 完成时换行
    
    def finish(self, message: Optional[str] = None):
        """完成进度"""
        self.state.current = self.state.total
        self.state.status = "completed"
        
        if self.callback:
            self.callback(self.state)
        
        if self.show_bar:
            self._print_bar()
        
        if message:
            print(f"✅ {message}")
    
    def get_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return {
            "total": self.state.total,
            "completed": self.state.current,
            "percentage": self.state.percentage,
            "elapsed_seconds": self.state.elapsed,
            "rate_per_second": self.state.rate,
            "errors_count": len(self.state.errors),
            "status": self.state.status
        }


class BatchProgressTracker:
    """
    批量进度追踪器
    支持多阶段、多文件的复杂批处理进度跟踪
    """
    
    def __init__(
        self,
        total_files: int,
        phases: list = None,
        callback: Optional[Callable[[Dict], None]] = None
    ):
        self.total_files = total_files
        self.phases = phases or ["scan", "plan", "execute", "validate", "output"]
        self.callback = callback
        self.current_file_idx = 0
        self.current_phase_idx = 0
        self.file_results = []
        self.start_time = time.time()
    
    def start_file(self, file_path: str):
        """开始处理新文件"""
        self.current_file_idx += 1
        self.current_phase_idx = 0
        
        if self.callback:
            self.callback({
                "type": "file_start",
                "file": file_path,
                "file_index": self.current_file_idx,
                "total_files": self.total_files,
                "phase": self.phases[0]
            })
    
    def next_phase(self):
        """进入下一阶段"""
        if self.current_phase_idx < len(self.phases) - 1:
            self.current_phase_idx += 1
            
            if self.callback:
                self.callback({
                    "type": "phase_change",
                    "phase": self.phases[self.current_phase_idx],
                    "progress": self._calculate_overall_progress()
                })
    
    def set_phase(self, phase: str):
        """设置当前阶段（通过名称）"""
        if phase in self.phases:
            self.current_phase_idx = self.phases.index(phase)
            
            if self.callback:
                self.callback({
                    "type": "phase_change",
                    "phase": phase,
                    "progress": self._calculate_overall_progress()
                })
    
    def file_complete(self, result: Dict[str, Any]):
        """文件处理完成"""
        self.file_results.append(result)
        
        if self.callback:
            self.callback({
                "type": "file_complete",
                "result": result,
                "progress": self._calculate_overall_progress()
            })
    
    def _calculate_overall_progress(self) -> float:
        """计算总体进度"""
        if self.total_files == 0:
            return 0.0
        
        file_progress = (self.current_file_idx - 1) / self.total_files
        phase_progress = self.current_phase_idx / len(self.phases)
        current_file_contribution = phase_progress / self.total_files
        
        return (file_progress + current_file_contribution) * 100
    
    def get_summary(self) -> Dict[str, Any]:
        """获取批处理摘要"""
        elapsed = time.time() - self.start_time
        success_count = sum(1 for r in self.file_results if r.get("success", False))
        
        return {
            "total_files": self.total_files,
            "processed_files": len(self.file_results),
            "success_count": success_count,
            "error_count": len(self.file_results) - success_count,
            "elapsed_seconds": elapsed,
            "average_time_per_file": elapsed / max(len(self.file_results), 1),
            "overall_progress": self._calculate_overall_progress()
        }
