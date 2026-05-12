# 给 Lumina 贡献代码

感谢你愿意参与！本文记录开发环境搭建、常用验证命令，以及提交 PR 的基本约定。

## 1. 本地开发环境

```bash
# 1) 克隆仓库
git clone https://github.com/chenboripple/Lumina.git
cd Lumina

# 2) 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate

# 3) 安装可编辑模式 + 开发依赖
pip install -e .
pip install -r requirements.txt

# 4) 初始化配置
lumina init   # 或者手动写 ~/.lumina/lumina.yaml
```

需要本地跑前端 JSX 检查的话，建议在 `/tmp/jsx_check` 单独装一份 Babel：

```bash
npm install --prefix /tmp/jsx_check @babel/core @babel/preset-react
```

## 2. 常用验证命令

```bash
# 运行核心单测
python3 -m unittest tests.unit.test_content_policy tests.unit.test_planning_optimizations

# 运行全部测试
python3 -m unittest discover -s tests

# Python 语法检查
python3 -m py_compile src/lumina/web_interface.py src/lumina/executor.py

# JSX 语法检查
node /tmp/jsx_check/node_modules/@babel/core/lib/transform-file.js \
  src/lumina/web/static/js/react-app.jsx > /dev/null

# 启动前台调试服务
lumina serve --no-watch --no-initial-sync
```

## 3. 代码风格

- Python：尽量遵循 PEP 8，必要时使用 `black` / `ruff` 自动格式化
- 注释：只在 *为什么* 不直观时写注释；不重复代码已说明的 *做什么*
- 提交信息：使用约定式提交格式，如 `feat: ...`、`fix: ...`、`refactor: ...`、`docs: ...`

## 4. 提交 PR

1. 从 `main` 分支拉一个 feature 分支
2. 实现 + 写测试 + 自测通过
3. 在 commit message 里说明动机（“为什么”），diff 已经说明了“做什么”
4. PR 描述里附：
   - **改动概要**：1-3 条 bullet
   - **测试计划**：列出已经跑通的验证步骤
5. 等 review；如需求微调，新建 commit 而不是 amend，方便复 review

## 5. 模块速查

| 模块 | 文件 | 说明 |
|------|------|------|
| Planner | `src/lumina/planner.py` | 扫描、聚合、计划 |
| Executor | `src/lumina/executor.py` | LLM 调用、提示词渲染 |
| Validator | `src/lumina/validator.py` | 质量评分 |
| Harness | `src/lumina/harness.py` | 全流程调度、增量处理 |
| PromptManager | `src/lumina/prompt_manager.py` | 提示词模板 + 版本化 |
| CacheManager | `src/lumina/cache.py` | 三级缓存 |
| HistoryManager | `src/lumina/history.py` | SQLite 操作历史 |
| Web | `src/lumina/web_interface.py` | Flask 后端 |
| Web 前端 | `src/lumina/web/static/js/react-app.jsx` | React 主界面 |

## 6. 反馈渠道

- Issue：https://github.com/chenboripple/Lumina/issues
- 邮件：chenboripple@gmail.com

---

如有更详细的设计说明，参见 [docs/index.md](docs/index.md)。
