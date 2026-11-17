# Task / 子任务 T01：会话模型接口
最后修改时间: 2026-11-16 07:44:00

## 审查状态与权威记录

Accepted；任务 T01，方案修订 5。父意图 `docs/intent/20261115-member-model-selection.md`，权威计划 `docs/plan/20261115-member-model-selection.md`，协调根 `D:/SourceCodes/mywork/agent-relay`。

## 目标、范围与输入

交付 A02–A04 及 A10 原始字段的频道范围模型接口。修改 application members DTO/port/service、Codex 目录解码与 driver、HTTP routes，新增后端单元测试。无前置；不涉及前端和持久化模型配置。

## 局部设计与实施安排

1. 定义目录/选项/更新 DTO 和端口，成员服务在离开数据库读 scope 后调用 RPC；PATCH 校验客户端 sessionId 等于当前绑定。
2. 按目标会话 provider 分页读取目录，Pydantic 校验所需字段，去隐藏，校验唯一模型与游标；当前模型从 thread/read 获取。
3. 核对目录和会话后只提交一次模型/兼容 effort 更新，重新读取确认配置，响应完整目录。读取失败、明确拒绝、写后未知分类并保留 cause。
4. 添加 HTTP 路由及测试。不得恢复会话、发送消息、触碰队列或打断轮次。

## 检查与风险

pytest 针对性测试覆盖 provider、分页、隐藏、空/未知当前模型、目标身份/路径、sessionId、effort、RPC 拒绝/未知及安全 HTTP code/requestId。schema 的 thread/read 语义足够用于配置确认；真实写入不实测。

## 交接依据

SpecFlow 协议入口为本机会话已读取的 `specflow/0.2.1/skills/specflow/SKILL.md` 与 `references/task-coordination.md`。分配 `model-T01-01`，用户授权“拆分任务，推进实现”；工作基线 HEAD `9bb93db0f6f0b05d00b6e493862e739dc81d6b3a`，产品文件无未提交修改。主会话执行并读取本文接收/交付，无跨会话交接。

## 接收与进展

- 2026-11-15 22:37:30：主会话核对有效编号 `model-T01-01`、方案修订 1、授权与无前置条件，完成接收；可写上述产品范围和本文记录。
- 2026-11-15 22:48：主会话接收同编号修订 2，兼容真实目录合法空 effort 列表；非空时继续校验默认 effort，空时使用实际默认值，不扩大产品范围。

## 交付与审查

- 修订 5 接收：`model-T01-01` 原执行者按 seq267 补充原始 model 字段并恢复原始目录 id，model 与 id 不相互替代；同工作区局部更新，无额外外部写入授权。对本次 DTO 变更复验后再次提交。

- 2026-11-15 22:42：主会话以 `model-T01-01`、修订 1 提交交付；实际范围与方案一致，无偏差。
- A02：按会话 provider 查询并分页、过滤隐藏、保留未知或目录外当前模型；测试覆盖坏目录和游标。
- A03：成员范围、绑定 ID、会话 ID、cwd 与可用状态校验后，只更新该会话；支持当前 effort 则保留，否则使用目录默认值。不涉及队列、输入或轮次。
- A04：显式拒绝 409，提交后无法确认 503/unknown；回执后读取并核对 provider/model/effort，不重试写入；HTTP 安全契约通过。
- 版本：基线 HEAD `9bb93db0f6f0b05d00b6e493862e739dc81d6b3a` 加本工作区 T01 diff，含 `application/dto/session_models.py`、成员端口/服务、Codex driver/catalog、routes 和三份后端测试。
- 检查：三份新增测试 34 passed；`uv run --locked mypy src tests`（213 files）、`ruff check src tests` 均通过。首次检查发现测试注解/格式问题，已修复并复验。
- 未完成/风险：真实会话切换未实测，不操作用户工作会话；UI 无关。主会话已据测试及实际调用链审查接受，供 T02 使用。
- 2026-11-15 22:50 修订 2 交付（`model-T01-01`）：兼容合法空 supportedReasoningEfforts，新增测试。三份后端测试 35 passed；实际使用新 `CodexDriver.model_catalog` 只读查询返回匹配会话、provider `magpie`、model `group/gpt-6.1` 和 13 个模型。主会话复审接受该工作区 diff；不再存在目录被空 effort 阻断的问题。
- 2026-11-16 07:44 修订 5 最终交付（`model-T01-01`）：保留目录原始 `id`、`model`、`displayName`、`description`，以 `model` 匹配/更新配置。适配及 HTTP 用例使用不同的目录 ID 和模型值，确认字段不混用且 HTTP 输出 camelCase。
- 最终版本为上述 HEAD + 本工作区 T01 修订 5 diff；2026-11-16 07:41 开发检查：后端全量 428 tests 通过，mypy 213 files、ruff check、ruff format 均通过，包含三份模型测试。较早针对性执行为 36 tests 通过。
- 主会话依据最新字段契约、单次写入/读取确认调用链及上述检查，将修订 5 交付 submitted → accepted，作为 T02 最新前置。没有实际写入真实会话；无新增未完成开发事项。
