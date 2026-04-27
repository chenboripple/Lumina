# Lumina 本地测试指南

## 🚀 快速启动

### 1. 安装依赖

```bash
cd workspace/Lumina
pip install -r requirements.txt
pip install pytest pyyaml watchdog flask flask-cors
```

### 2. 运行基础测试

```bash
# 测试模块导入
python3 -c "
import sys
sys.path.insert(0, 'src')

# 测试基础模块
from lumina.config import LuminaConfig
from lumina.cache import CacheManager
from lumina.history import HistoryManager
from lumina.harness import Harness, HarnessConfig

# 测试 v1.0 新增模块
from lumina.utils.progress import ProgressTracker
from lumina.utils.error_handler import ErrorHandler, ErrorSeverity
from lumina.config.hot_reload import ConfigWatcher

# 测试 v2.0 新增模块
from lumina.tag_recommender import TagRecommender
from lumina.smart_link_generator import SmartLinkGenerator
from lumina.multi_device_sync import SyncManager
from lumina.batch_repair import BatchRepairManager

print('✅ 所有模块导入成功!')
"
```

### 3. 创建测试文件

```bash
mkdir -p test_input
echo "# Python 机器学习指南

Python 是机器学习的首选语言。

## 常用库

- scikit-learn: 经典机器学习
- TensorFlow: 深度学习框架
- PyTorch: 动态神经网络
- Pandas: 数据处理
- NumPy: 数值计算

## 应用场景

1. 图像识别
2. 自然语言处理
3. 推荐系统
4. 预测分析
" > test_input/ml_guide.md

echo "# Docker 容器化部署

Docker 简化了应用部署流程。

## 核心概念

- 镜像 (Image)
- 容器 (Container)
- 仓库 (Registry)

## 常用命令

```bash
docker build -t myapp .
docker run -d -p 8080:8080 myapp
docker-compose up -d
```

## Kubernetes 编排

Kubernetes 是容器编排的事实标准。
" > test_input/docker_guide.md
```

### 4. 运行完整流程

```python
from lumina.harness import Harness, HarnessConfig

# 配置
config = HarnessConfig(
    max_iterations=2,
    quality_threshold=0.6,
    output_dir="./test_output",
    enable_vector_store=False,  # 如果没有 chromadb
    enable_progress=True,
    enable_error_handler=True
)

# 创建 Harness
harness = Harness(config)

# 处理文件
report = harness.run("./test_input")

# 查看结果
print(f"处理文件数: {report['statistics']['total_files']}")
print(f"平均质量: {report['statistics']['avg_score']:.2f}")
print(f"通过率: {report['statistics']['pass_rate']:.1%}")
```

### 5. 启动 Web 界面

```python
from lumina.harness import Harness, HarnessConfig
from lumina.web_interface import WebInterface

config = HarnessConfig(
    output_dir="./test_output",
    enable_vector_store=False
)

harness = Harness(config)

# 启动 Web 界面
web = WebInterface(harness=harness, host='127.0.0.1', port=5000)
web.run(debug=True)
```

访问 http://127.0.0.1:5000 查看 Web 界面。

### 6. 测试标签推荐

```python
from lumina.tag_recommender import TagRecommender

recommender = TagRecommender()

content = """
Python machine learning tutorial with scikit-learn and TensorFlow.
Deep learning neural networks for image recognition.
"""

tags = recommender.recommend_tags(
    content=content,
    title="ML Tutorial",
    max_tags=5
)

print("推荐标签:")
for tag in tags:
    print(f"  - {tag.tag} ({tag.score:.2f}): {tag.reason}")
```

### 7. 测试智能链接

```python
from lumina.smart_link_generator import SmartLinkGenerator

generator = SmartLinkGenerator(similarity_threshold=0.5)

# 模拟笔记数据
all_notes = [
    {"id": "note1", "title": "Python 基础", "content": "Python 入门教程", "tags": ["Python"]},
    {"id": "note2", "title": "机器学习", "content": "使用 Python 进行机器学习", "tags": ["Python", "ML"]},
    {"id": "note3", "title": "Docker 部署", "content": "容器化部署指南", "tags": ["Docker"]},
]

links = generator.generate_links(
    note_id="note2",
    note_title="机器学习",
    note_content="使用 Python 进行机器学习",
    note_tags=["Python", "ML"],
    all_notes=all_notes
)

print("相关笔记:")
for link in links:
    print(f"  → {link.target_title} (相似度: {link.similarity:.2f})")
```

### 8. 测试多设备同步

```python
from lumina.multi_device_sync import SyncManager
import tempfile

sync_dir = tempfile.mkdtemp()
sync = SyncManager(device_id="test_device", sync_dir=sync_dir)

# 添加同步项
sync.queue_note_for_sync("/path/to/note.md", "笔记内容")

# 执行同步
results = sync.sync()
print(f"同步结果: {results}")

# 查看状态
status = sync.get_sync_status()
print(f"同步状态: {status}")
```

### 9. 测试批量修复

```python
from lumina.batch_repair import BatchRepairManager

# 创建修复管理器
repair = BatchRepairManager(harness=None, max_workers=2)

# 扫描需要修复的笔记
tasks = repair.scan_for_repair(
    output_dir="./test_output",
    min_score=0.6
)

print(f"发现 {len(tasks)} 个需要修复的笔记")

# 查看队列状态
status = repair.get_queue_status()
print(f"队列状态: {status}")
```

### 10. 测试配置热加载

```python
from lumina.config.hot_reload import ConfigWatcher
import tempfile
import yaml

# 创建临时配置文件
config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
yaml.dump({"plugin": "obsidian", "max_iterations": 3}, config_file)
config_file.close()

# 创建监控器
watcher = ConfigWatcher(config_file.name, auto_reload=False)

# 获取配置
config = watcher.get_config()
print(f"当前配置: {config}")

# 修改配置文件
with open(config_file.name, 'w') as f:
    yaml.dump({"plugin": "plain", "max_iterations": 5}, f)

# 检查变更
changed = watcher.has_changed()
print(f"配置是否变更: {changed}")

# 重新加载
new_config = watcher.reload()
print(f"新配置: {new_config}")
```

## 📊 预期输出

### 基础测试
```
✅ 配置模块
✅ 缓存模块
✅ 历史模块
✅ 核心协调器
✅ 进度追踪
✅ 错误处理
✅ 配置热加载
✅ 自动标签推荐
✅ 智能链接生成
✅ 多设备同步
✅ 批量修复
```

### 功能测试
```
✅ HarnessConfig 创建成功
   - max_iterations: 3
   - quality_threshold: 0.8
   - enable_progress: True

✅ ProgressTracker 创建成功
   - 当前进度: 30.0%
   - 当前状态: 进行中

✅ ErrorHandler 创建成功
   - 错误处理结果: fallback_value
   - GracefulDegradation 结果: default
   - 错误统计: 2

✅ TagRecommender 创建成功
   - 提取关键词: [('python', 0.5), ('machine', 0.3)...]
   - 识别技术栈: [('Python', 0.3), ('React', 0.3)...]

✅ SmartLinkGenerator 创建成功
   - 提取关键词: ['python', 'machine', 'learning']

✅ SyncManager 创建成功
   - device_id: test_device
   - sync_dir: /tmp/...

✅ BatchRepairManager 创建成功
   - max_workers: 2
   - default_threshold: 0.7

✅ Harness 创建成功
   - session_id: session_...
   - enable_progress: True
   - enable_error_handler: True
```

## 🎉 总结

如果所有测试都通过，说明 Lumina v2.0 已经完全准备就绪！

可以开始使用：
1. 处理本地文件生成笔记
2. 通过 Web 界面管理笔记
3. 使用自动标签和智能链接
4. 多设备同步笔记数据
5. 批量修复低质量笔记
