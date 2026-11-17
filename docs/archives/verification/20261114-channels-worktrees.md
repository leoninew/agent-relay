# 频道与 Worktree 验证

日期：2026-11-14。

用户反馈频道功能实测无问题；未提供逐项实测清单。

## 自动检查

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| 后端单元与频道集成 | `uv run --locked pytest tests/unit tests/integration/test_channel_persistence_integration.py -q --tb=short` | 379 项通过 |
| 后端类型、静态检查和格式 | `uv run --locked mypy src tests`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .` | 通过 |
| 前端单元 | 在 `web` 执行 `corepack pnpm test --reporter=default --silent=false --no-color` | 143 项通过，无测试警告 |
| 前端类型、静态检查和格式 | 在 `web` 执行 `corepack pnpm typecheck --force`、`corepack pnpm lint`、`corepack pnpm format` | 通过 |

频道集成测试使用临时 SQLite 数据库和 Git 仓库，覆盖数据迁移、频道资源隔离、显式频道接口、当前 HEAD 创建 worktree、会话绑定及请求事务回滚。前端单测覆盖频道创建、草稿隔离、面板状态和请求契约。
