# Task T01：Codex 定向查询
最后修改时间: 2026-11-17 16:23:00

## 方案与权威记录

Accepted；父意图和权威计划为 docs/intent/20261117-query-scoping.md、docs/plan/20261117-query-scoping.md，方案修订 1。执行者架构师；编号 QS-T01-20261117-01；授权 0413 与 go on 的 Implementation。

## 目标、范围与检查

A01/A02：清空频道只查询所绑定 ID，查询失败中止；MCP 按名称查询并验证所选 ID；空目录跳过 loaded。修改 rooms/service、codex/driver 及相关单元测试。使用现有 RPC，不引入持久化字段。运行 room_service、Codex 测试和 Ruff/Mypy，记录工作区 diff。无直接前置。

## 接收与进展

2026-11-17 16:14:54 架构师接收 QS-T01-20261117-01，核对方案 1、用户授权及 d74f846 加当前工作区基线，记录可读写，开始实施。仅本会话写本文，以 Conflua 汇报必要共享结果。

## 交付与审查

QS-T01-20261117-01，方案 1：工作区已完成 connected_sessions（只读全局 loaded ID，详情仅查询绑定 ID，找齐即停止）、空目录早退、MCP serverName 查询和身份核对。原生 loaded/list 没有 ID 过滤，保留 ID 分页是必要协议限制。无其他范围偏差。

`uv run --locked --no-sync pytest tests/unit/application/test_room_service.py tests/unit/infrastructure/codex -q`：155 passed。A01/A02 回归通过，查询失败仍禁止清空。未运行迁移测试；静态检查随集成执行。主会话已审查实际 diff 和测试，接受此工作区交付供后续使用。
