# Task / 子任务 T01：后台调度与小事务边界
最后修改时间: 2026-11-16 20:32:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261116-reliable-message-delivery.md)；权威总计划：`D:/SourceCodes/mywork/conflua/docs/plan/20261116-reliable-message-delivery.md`。
- 任务 ID：T01；方案修订：2。依赖、分配和执行状态由总计划唯一维护。

## Handoff basis / 交接依据

执行者：高级开发 `member-076ee1012fab`；分配编号 `RMD-T01-20261116-a6d2bced`；用户授权 `msg-0311`。基线为 `4564339` 加总计划列明的六处暂停试改，共享代码／权威根 `D:/SourceCodes/mywork/conflua`。无前置任务。协议入口、P01–P07、旧试改清理范围见总计划。执行者可写本文 Reception and progress、Delivery and review 及最后修改时间，先接收再实施，通过 Conflua 定向回报架构师。此前暂停试改不构成有效交付。

## Goal and acceptance / 目标与验收

交付复用请求事务、后台领取和小事务的调度链路，满足 A01–A05：消息入库无额外锁、提交后可见、RPC 无房间长锁、同目标有序及多目标正常推进。

## Inputs and eligibility / 输入与可开始条件

依据总计划的直接前置与版本要求；开工前核对方案、阶段授权、当前工作区和暂停试改。现有消息受理、请求事务、后台执行器和仓储为输入，已有正确逻辑无需重写。

## Scope and files / 范围与文件

主要涉及 runner、delivery service/ports/store/repository、必要 guard 装配与相邻测试；只读核对消息服务和请求事务。共享文件按总计划串行整合，外部依赖不变。

## Technical decisions / 局部技术设计

- 路由及投递任务与消息同事务提交；后台只领取已提交数据，不延长发布请求等待 Codex。
- 领取／保存各用短事务，外部 RPC 在事务外执行。移除投递及启动的房间级文件长锁；确有业务协调需求时说明频道键、用途和时间边界。
- 同 session 的提交作业覆盖准备、输入提交及必要启动阶段；数据库已写 queued 不等于调度占用已结束。
- 按持久化投递顺序调度目标队首；后续重试接口须允许 T02 表达“队首等待、其他目标可运行”，不通过房间异常模拟队列。

## Implementation outline / 实施安排

1. 固定基线，核对并清除总计划列明的旧试改，记录逐项结果；核对现有受理事务与全部投递／启动 RPC 持锁位置。
2. 实现目标调度及频道范围、小事务领取／完成装配。
3. 完成相邻检查，固定调度与状态接口供 T02 接入。

## Checks and delivery / 检查与交付

使用既有后端检查，验证受理原子性、目标串行和不同目标推进，不调用真实成员会话。交付写明实际 diff、版本、A01–A05 证据、检查结果及未运行项，由架构师审查后放行下游。

## Risks / 风险

需同时检查提交及启动两条 RPC 路径；仅移除 submit 外层锁会遗漏后续启动的调度边界。频道协调与目标顺序分别表达，不能重新引入房间范围耦合。

## Reception and progress / 接收与进展

- 2026-11-16 20:22 接收：高级开发 `member-076ee1012fab`，编号 `RMD-T01-20261116-a6d2bced`，方案修订 2；授权来源用户 `msg-0311`，派发 `msg-0314`。实际 HEAD 为 `4564339`，暂存区为空；此前前端 6 文件已提交，不再描述为待保护暂存。
- 接收时已存在本会话依据用户开工指令开展的在途实现，按架构师要求保留并纳入审查，不重做。总计划六处旧试改已移除／替换：删除 DeliveryOperationBusy、ExitStack busy 分支、房间冷却状态及过滤；旧 defer 改为持久时间条件更新；旧应用 busy 测试替换；旧仓储测试已删除，正在按新机制重写。
- 已完成投递／启动房间锁移除、runner session 在途归属及待保存结果保留、短事务领取；正在处理 R01 有效队首资格并补确定性测试。T02 的持久退避／错误分类与队列核验已有在途代码，尚不算 T02 交付，待前置审查后顺序继续。
- 用户随后明确优先恢复开发库：补齐模型 Integer 导入，备份开发库并执行迁移，revision 与字段核对成功，9081/openapi.json 返回 200；恢复证据见 msg-0316。不重建数据、不恢复历史投递，不管理服务进程。

## Delivery and review / 交付与审查

2026-11-16 20:32，编号 `RMD-T01-20261116-a6d2bced`，高级开发提交 T01 待审查；无前置版本，基线 HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb` 加共享工作区 diff，不创建提交。记录和代码均位于权威根。

实际变更：runner 保留 session 占用，Future 返回待保存结果时转入带延迟的待保存集合，重新调度只保存原结果；占用到保存及必要启动结束才释放。仓储用短 IMMEDIATE 事务领取，用同一可调度资格判断目标与更早 pending 队首；已在提交中的 session 继续被排除，其他 session 可领取。投递／启动两条 RPC 不再持房间 guard 或数据库写事务，保留后台单实例锁。

旧六处清理结果：ports 删除旧 busy 异常，service 删除 ExitStack/busy 分支，store 删除 busy 转译、claim 线程锁及房间冷却表，repository 删除 deferred_rooms 并替换旧无持久时间的 defer，应用旧 busy 测试替换为明确未发送暂时故障测试，旧仓储测试整体重写。对这些路径搜索旧标识均无残留。

| 验收 | 实际证据 |
| --- | --- |
| A01 | 只读核对 MessageService.post_message、message repository、请求事务中间件：同事务插入消息／路由／delivery，无新增消息入库锁；保留既有正确代码。 |
| A02 | Database.write 的 IMMEDIATE 事务提交后释放；请求事务在响应发出前完成；事务／中间件 5 项测试通过。发布方不调用本次提交 RPC。 |
| A03 | test_submission_and_activation_hold_no_room_or_database_write_lock 在两条 fake 外部调用中以独立 Context 获取房间锁及数据库写事务，均可正常执行；RPC 全程不在 store 的 write/read 上下文内。 |
| A04 | 同 session submitting 不重复领取；有效退避队首阻止后项；runner 参数化 activation／save-retry 场景验证等待期间 target 始终被排除，别的目标可调度，最后才放行后项。 |
| A05 | 同房间不同接收人可同时领取；有效目标统一资格过滤。R01 用合法跨 room 同真实 session 夹具验证 deleted-member／rebound／archived-channel 的无效旧队首不阻塞后项；没有放宽唯一索引。 |

检查：中级开发 msg-0323 的三组定向 pytest 为 36 passed；msg-0326 的 mypy 为 212 source files 无错误、ruff format --check 为 362 files 已格式化；当轮 ruff 唯一未使用 import 已由高级开发移除，msg-0330 复查 ruff check 全通过，事务检查 5 passed。`git diff --check` 通过。未运行全量 pytest，留 T03 冻结版本执行；未做 UI、真实成员提交实验或历史补投。

可核对 SHA256（本次交付快照）：runner `DC0CBF7156CB68CF94B44CB590FCC736C86F02D66B9DD70A329DB6FF9D01A339`；service `C940ED0201BF3ABC600F5B79524AF1A7B513FAD3BD2C027F9B21BACE3E179BC3`；repository `996E9661AA2229E702E8E5BB79BB80C3DD28EA219A28DF88DC1C82219C254F0B`；runner tests `454BD84965A0CC6B2C8C1F4C2B8EBB62121997B2FEEA4E247B929E23CCAF8515`；store tests `A7E8EB2D298446D1A9905E3AECF25AC7F48F2365F3867175A1564F8EBB23380E`。

范围偏差／T02 在途：共享接口联动已包含 DeliveryOutcome、内部 attempt_count/next_attempt_at、迁移 0002、service 的 defer/保存重试及 queue evidence、driver 的初步分类和队列分页。它们尚非 T02 已验收交付；R02（确定启动配置）和 R03（add 内部错误）仍待 T02 修正。未知队首屏障提案见 msg-0327，等待架构师协议审查；不在 T01 宣称该边界已解决。无其他 T01 未完成项。独立 web/src/style.css 变更未触碰。
