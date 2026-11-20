# 贡献指南

感谢参与 Conflua。提交较大的功能或行为变更前，建议先通过仓库 Issue 讨论需求和实现方向。

## 开发环境

准备 Python 3.12、uv、Node.js、Corepack、GNU Make 和 Bash；版本与平台要求见 [README](README.md#环境)。Windows 可使用 Git Bash。在仓库根目录安装锁定的依赖：

```bash
make deps
```

分别运行 `make webapi` 和 `make web` 启动后端和前端。使用 Codex 会话相关功能时，还需要安装并认证 Codex CLI；配置与运行方式见 [README](README.md#本地开发)。

## 提交变更

1. 为变更创建独立分支，保持修改范围与目标一致。
2. 根据变更补充或调整测试；涉及配置、使用方式或接口行为时同步更新文档。
3. 修改依赖后，更新对应的 `uv.lock` 或 `web/pnpm-lock.yaml`，并一同提交。
4. 提交前执行下面的检查，并在 Pull Request 中说明变更目的、主要内容和验证结果；未能执行的检查也请注明原因。

```bash
make check
make test
```

`make check fix=1` 会自动修复部分 lint 和格式问题；提交前请检查自动修改的内容。

在仓库根目录运行 `uv run pytest`，默认只运行 `tests/unit` 下的后端单元测试；`make test` 还会运行前端单元测试。后端集成用例放在 `tests/integration`，标记为 `integration`，默认使用内存 SQLite，只有跨连接事务隔离用例使用临时文件库，不运行数据库迁移。需要时显式运行 `uv run --locked pytest -m integration tests/integration`。

新增和整理测试时只覆盖正向业务场景，不专门构造无效输入、冲突或故障来断言拒绝和错误响应。

前端 Vue 单文件组件按 `<template>`、`<script>`（含 `<script setup>`）、`<style>` 排列。条件分支和循环即使只有一条语句，也使用大括号，块内语句另起一行。在 `web/` 中先运行 `pnpm lint:fix` 修复区块顺序并补齐大括号，再运行 `pnpm format:write` 统一换行和缩进。

## 问题反馈

提交 Issue 时，请描述预期行为、实际行为、复现步骤、系统和相关版本。日志、截图或配置中不要包含密钥、私人消息、会话信息或其他敏感数据。
