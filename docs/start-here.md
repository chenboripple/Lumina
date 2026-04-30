# Lumina 文档导航

这份文档只做入口索引。当前实现已经从“脚本工具”演进为“常驻服务 + Web 仪表盘 + 增量处理 + 向量检索”的组合系统，所以优先按下面顺序阅读。

## 先看这些

1. [README.md](/Users/ripple/work%20space/Lumina/README.md)
2. [docs/installation.md](/Users/ripple/work%20space/Lumina/docs/installation.md)
3. [docs/lumina-yaml-demo.md](/Users/ripple/work%20space/Lumina/docs/lumina-yaml-demo.md)
4. [docs/usage/manual.md](/Users/ripple/work%20space/Lumina/docs/usage/manual.md)

## 如果你关心架构

- [docs/architecture/planner.md](/Users/ripple/work%20space/Lumina/docs/architecture/planner.md)
- [docs/architecture/harness.md](/Users/ripple/work%20space/Lumina/docs/architecture/harness.md)
- [docs/architecture/executor.md](/Users/ripple/work%20space/Lumina/docs/architecture/executor.md)
- [docs/architecture/validator.md](/Users/ripple/work%20space/Lumina/docs/architecture/validator.md)
- [docs/architecture/vector_store.md](/Users/ripple/work%20space/Lumina/docs/architecture/vector_store.md)

## 如果你关心产品能力

- [docs/advanced-features.md](/Users/ripple/work%20space/Lumina/docs/advanced-features.md)
- [docs/vector-integration.md](/Users/ripple/work%20space/Lumina/docs/vector-integration.md)
- [docs/test-guide.md](/Users/ripple/work%20space/Lumina/docs/test-guide.md)

## 当前推荐启动方式

```bash
lumina start
```

然后打开 `http://127.0.0.1:5088`。

如果只想做一次性处理：

```bash
lumina process
lumina process ~/Documents --no-incremental
```

如果要调试服务前台日志：

```bash
lumina serve
```