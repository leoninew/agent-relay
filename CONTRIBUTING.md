# 贡献指南

感谢参与 Agent Relay。提交较大的功能或行为变更前，建议先通过仓库 Issue 讨论需求和实现方向。

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

## 问题反馈

提交 Issue 时，请描述预期行为、实际行为、复现步骤、系统和相关版本。日志、截图或配置中不要包含密钥、私人消息、会话信息或其他敏感数据。
