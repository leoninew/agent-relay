# 计划：在 Conflua CLI 查询 Codex 会话

最后修改时间: 2026-11-18 12:48:58

## 审查状态与依据

Accepted（依据用户实现请求及频道消息 #444），范围见[意图](../intent/20261118-codex-session-list.md)。

## 技术设计与实施

1. 在现有 Click CLI 接入 `codex session list`，绕过 HTTP 客户端，用规范化目录调用现有 `CodexDriver.list_sessions`。
2. 所有 Codex 查询子命令默认输出常规文本，显式 `-o json` 才输出 JSON。列表按 ID 倒序。详情复用 `thread/read` 和归档索引，核对 UUID 及可选目录；与列表共用状态映射，区分 daemon、当前会话和本机进程证据，缺少证据时保持 `unknown`。
3. 查询 Codex 等待队列时，先核对会话及可选目录，再沿 `thread/queue/list` 游标读取全部页面并保留 daemon 顺序。只输出队列条目 ID 和可空的关联消息 ID；不改变 Conflua 投递确认对关联消息 ID 的要求。协议不支持和分页失败均显式报错，不输出成功的部分列表。
4. 修改范围为 CLI、Codex 驱动、相关 DTO 与测试及原 SpecFlow 文档，不扩写 README。开发检查覆盖两种输出、目录不符、无关联 ID、空队列、分页和不支持场景；运行 pytest、Ruff、Mypy，并用现有 daemon 只读实测。

## 前次开发检查

- `uv run --locked --no-sync pytest tests/unit`：488 个测试通过。
- 变更文件通过 Ruff lint 和格式检查；对全部源码及相关 CLI/进程测试运行 Mypy，163 个 source files 无问题。
- `uv run --locked --no-sync conflua codex session list`：当前目录 8 个会话，运行态为 1 个 `active`、2 个 `idle`、5 个 `unknown`；后 5 个 daemon 状态为 `not_loaded`。新建的未交互会话以 `idle` 返回。
- 未同步安装 psutil 的环境中，进程扫描跳过且命令仍正常输出；完整安装包含锁定的 psutil 依赖。

## 本次实现与开发检查

- `session get ID` 与 `queue list ID` 默认输出常规文本；全部 Codex 查询子命令仅在指定 `-o json` 时输出 JSON，并且不依赖 Conflua HTTP 服务。
- `uv run --locked --no-sync pytest tests/unit`：501 项通过，覆盖归档索引、运行态证据、目录不匹配、无关联 ID、队列分页与协议不支持。
- `uv run --locked --no-sync ruff check .`、`uv run --locked --no-sync ruff format --check --no-cache .`、`uv run --locked --no-sync mypy src tests` 均通过。
- 现有 daemon 只读实测：活跃会话返回 `active` 和证据 `daemon`，未加载历史会话返回 `not_loaded / unknown`；真实队列为空，非空及分页由单测覆盖，未发送消息来制造样本。

## 风险与回滚

没有会话 ID 的 Codex 进程不按目录猜测归属。旧 daemon 可能不支持队列列表；真实队列在翻页期间可能变化，不承诺原子快照。回滚仅需撤销相关代码、测试和文档，无数据迁移。子任务与协调不适用。
