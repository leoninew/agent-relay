# Task / 子任务 T01：频道存储与数据迁移
最后修改时间: 2026-11-14 12:30:00

## Review status / 审查状态

Draft，未分配。

## Parent and authority / 父任务与权威记录

- [意图](../../intent/20261113-channels-worktrees.md)；[总计划](../../plan/20261113-channels-worktrees.md)，协调根 `D:\SourceCodes\mywork\agent-relay`，T01，修订 3。

## Goal and acceptance / 目标与验收

- A01、A05、A08：交付频道模型、存储作用域及旧库前滚；旧数据和投递事实完整保留，原默认频道用例仍可运行通过，不能只交付破坏原仓储的 DDL。
- 原 ID、seq、幂等键、软删除、订阅、引用、位置、事件及所有投递状态/回执可往返；跨频道关联被约束拒绝。

## Scope and files / 范围与文件

- 领域/DTO/ports 的频道基础契约、ORM、mapper、资源仓储的频道过滤、SQL-first revision、迁移指南与测试；不实施 Git 或客户端。

## Inputs / 输入

- 无直接前置；以总计划固定的频道字段、房间全局消息 seq 和频道作用域为输入。

## Technical decisions / 局部技术设计

- 默认频道 ID 为 `channel-default`，在 room_id 下唯一；固定用户可按 room/channel 使用相同 `user`，sessions 仍为房间级元数据。频道业务属性为名称和描述，内部保留路径与归档时间，不维护频道状态。
- 活动目录和名称唯一；房间/频道软归档保留历史，消息 ID/seq 继续房间全局，幂等键增加频道。定义频道查找、创建和归档端口，归档与创建共用 guard，检查 submitting 并停止后续 claim，pending 软移出而 queued/unknown 保持观察。
- 仓储构造显式绑定 `channel_id`，不设置省略时的默认值；所有关联查询和写入在仓储内落实同作用域。全局投递调度/回执观察、房间列表等全局操作单独处理。
- 定义并交付跨进程 `ChannelOperationGuard`，按现有文件锁方式实现；创建/归档/会话输入与 activation 共用。多频道按稳定顺序非阻塞获取，禁止持 DB 事务等锁。归档 retire Agent 但保留固定用户和旧目标，释放活动 session 唯一约束。
- revision `channels_20261113` 接当前 head，事务内新表复制、旧表按依赖删除、新表重命名及外键检查。迁移仅回填已有规范路径，不依赖文件系统实际解析，不调用 Git/Codex。运行期目录占用核验由 T02/T04 执行。
- 重建完整 FK 图包括需要替换 UNIQUE 的 rooms；保留 rowid 相对顺序/投递 FIFO 和事件 sqlite_sequence 高水位，覆盖最大事件原属于已删除房间的情形。

## Implementation outline / 实施安排

1. 固定频道模型、DTO/ports 与归档存储契约，复用请求事务切面，创建房间时建立默认频道及原有初始资源。
2. 增加迁移并回填关联，更新 ORM、mapper、索引及显式频道仓储。
3. 纯规则检查留在 unit；在 integration 临时库验证全表升级、非法关联与失败回滚，交付稳定存储给 T02/T03。

## Checks and risks / 检查与风险

- `uv run --locked pytest tests/unit/infrastructure/persistence tests/unit/application tests/unit/domain`，默认频道用例应通过；定向运行新增 `tests/integration` 迁移检查。
- 覆盖自引用、软删除、所有投递状态/回执、事件、位置、幂等及 FK 检查；故障注入确认数据与 revision 回滚。当前 mock 型 `test_migrations.py` 不证明升级正确，离线 SQL 也不能替代真实临时库检查。

## Handoff basis / 交接依据

- 未分配；协议入口为 `C:/Users/leon/.codex/plugins/cache/specflow-local/specflow/0.2.1/skills/specflow/SKILL.md` 及 `references/task-coordination.md`。
- 分配、授权、基线和前置以总计划为准；接收和交付只写本文下列章节，主会话读取；默认输出可复制摘要。

## Reception and progress / 接收与进展

- 未接收。

## Delivery and review / 交付与审查

- 尚无交付；执行时记录验收、版本、检查、未完成项与风险，审查结论以总计划为准。
