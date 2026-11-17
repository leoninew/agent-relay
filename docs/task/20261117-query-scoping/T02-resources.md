# Task T02：频道资源定向读取
最后修改时间: 2026-11-17 16:24:09

## 方案与权威记录

Accepted；父意图和权威计划为 docs/intent/20261117-query-scoping.md、docs/plan/20261117-query-scoping.md，方案修订 1。当前未分配，授权范围见总计划。

## 目标、范围与设计

A03：指定成员查询代替 resources；活跃绑定读取用于状态更新；Session 通过当前频道成员 EXISTS 关联，包含已删除成员以支持历史名称。仅修改 rooms ports、_room_reads、members/capabilities services 及应用测试，不改变存储结构或 save_resources 的增量语义。

## 检查与风险

检查跨频道隔离、删除成员历史展示、单成员不存在/已删除/人类分支和状态更新。运行应用测试、Ruff、Mypy；可在内存执行现有表模型的查询验证，不测试迁移。不恢复他人删除的 persistence 测试。

## 接收与进展

2026-11-17 16:23:00 架构师核对并接收 QS-T02-20261117-01，方案 1、0413 的 Implementation 授权、当前共享工作区及 T01 已审查版本均可访问；本文由本会话维护，开始产品修改。

## 交付与审查

QS-T02-20261117-01，方案 1：新增 member、active_bindings；中断/模型/MCP 和 observation 不再读取完整 resources；resources 的 sessions 通过当前频道成员 EXISTS 筛选，包含历史成员。save_resources 保持增量写入，无数据结构变化。

`uv run --locked --no-sync pytest tests/unit/application tests/unit/infrastructure/test_query_scoping.py -q`：95 passed；`uv run --locked --no-sync mypy src tests`：207 source files 通过。新的内存查询用例只检验查询范围，不调用迁移。主会话已审查跨频道/历史成员用例和实际 diff，接受当前工作区版本，未完成项无，静态格式随集成执行。
