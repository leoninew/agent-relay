# Verification / 验证：可靠的异步消息投递
最后修改时间: 2026-11-16 21:15:45

## Review status / 审查状态

Accepted

## Intent alignment / 意图对齐

依据 [总意图](../intent/20261116-reliable-message-delivery.md) 的 A01–A09。用户在本轮明确要求“完成验证文档，无须再运行测试”，据此进入整体 Verification，以已完成的代码审查、节点交付及最终冻结版本检查完成验收记录。本轮没有重新运行测试、类型检查、lint 或格式化。

实现满足请求事务原子受理、后台短事务投递、同目标有序调度、暂时故障持久退避及回执分层核验的目标。发送方不再因投递线程之间争抢房间业务锁而承担补发责任。真实输入结果不明仍按外部证据处理，不承诺上游未支持的幂等或恰好一次消费。

## Plan alignment / 计划对齐

实现符合 [总计划](../plan/20261116-reliable-message-delivery.md) 修订4及 P01–P08：保留现有正确请求事务，移除提交和启动期间的房间业务长锁，保留后台单实例选主；领取、结果保存与启动尝试分别使用短事务，外部 RPC 位于事务之外。

同 session 的在途归属覆盖准备、输入提交、原结果保存及必要启动；有效退避队首和本轮新 unknown 保持同目标顺序，其他目标按可用容量公平推进。回执保存失败只保存原结果；原队列精确命中仅确认 queued，完整输入历史才确认 received。首次启动检查采用持久标记并共用 session 占用，记录启动尝试后不重复 start。未增加投递业务文件锁，因此无需引入新的频道 guard。

## Task deliveries and integration / 子任务交付与集成

| ID | 当前有效交付版本 / 位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | HEAD `45643391` 加20:32工作区交付；[任务记录](../task/20261116-reliable-message-delivery/T01-async-dispatch.md)，编号 `RMD-T01-20261116-a6d2bced` | 定向36项、事务5项及静态检查通过；主会话20:35接受 | 调度／短事务接口由T02扩展，相关行为已在最终475项检查中回归；六处暂停试改已清除或替换 | A01–A05通过 |
| T02 | 同一HEAD加20:57交付；[八文件快照及检查](../task/20261116-reliable-message-delivery/T02-retry-and-receipts.md)，编号 `RMD-T02-20261116-dab315f4` | 基础142项、补充51项、最终调度／仓储32项及静态证据；R02／R03／R04、P08经实际diff审查，20:58接受 | T03未改变产品；七个关键文件哈希保持T02值，store测试仅增加集成用例和类型注解 | A06–A08通过 |
| T03 | 同一HEAD加21:05:12交付；[最终八文件快照及验收映射](../task/20261116-reliable-message-delivery/T03-regression-evidence.md)，编号 `RMD-T03-20261116-1c4fd60e` | 最终同一冻结版本475项、mypy、Ruff及格式检查全部通过；主会话21:07接受 | 本轮再次核对八个SHA256全部一致，T01／T02有效产品与最终检查没有失配 | A09及A01–A08集成回归通过 |

任务检查时基线为 `45643391bb464cca7d58a41ec8712d97ce2dd0eb` 加最终工作区。整理报告期间实现已提交为当前 HEAD `c8a438be7304a7aef69d36ecb6d2217c379fe1e1`（`fix(delivery): make message dispatch recoverable`）。提交后再次只读核对八个文件与T03记录全部一致，已有检查证据仍有效。执行顺序为 T01 → T02 → T03，均在同一权威根集成，执行登记均为 accepted；未发现上游变化使下游检查失效。本轮未执行Git写操作。

## Actual diff summary / 实际差异摘要

- 清除此前撞锁回pending／进程内房间冷却试改；投递与启动不再持房间锁跨越RPC，数据库仅在领取、保存和条件更新时进入短事务。
- runner保留session占用与原待保存结果，轮换投递、首次检查、保存重试和观察作业；首次检查按持久到期时间及插入顺序领取，避免慢检查持续到期导致其他目标饥饿。
- 驱动区分明确未输入的暂时故障、确定配置／绑定拒绝和可能已发送。add内部错误、断连、错回执及steer回退后的未知结果不会触发盲目重发。
- 新增内部 `attempt_count`、`next_attempt_at` 及增量迁移，保持公开Delivery DTO。历史行计数默认为0，不新增unknown屏障、自动补投或通用首次启动恢复。
- 新增队列分页精确核验、首次启动检查恢复及相邻确定性用例；真实SQLite事务与假驱动组合证明受理可见性、多目标恢复和输入写入次数。

## Expected vs actual changed files / 预期与实际修改文件对比

| 计划范围 | 实际修改或保留 | 对齐结果 |
| --- | --- | --- |
| 请求原子受理与事务边界 | `application/messages/service.py`、HTTP事务中间件及database／transaction保持原实现；新增真实连接可见性测试 | 正确路径保留，无附加入库锁 |
| 调度、错误分类及回执 | `src/conflua/application/delivery/{ports,service}.py`、`application/dto/delivery.py`、`infrastructure/codex/driver.py`、`infrastructure/dispatch/delivery.py` | 与计划一致 |
| 持久化及迁移 | `infrastructure/persistence/{delivery_store,migrations,models}.py`、`repositories/deliveries.py`；路径均相对 `src/conflua/`。新增 `migrations/sqlite/versions/0002_delivery_retry.py` 及配套SQL，更新 `migrations/README.md` | 两列增量升级；现有资源打包包含整个迁移目录，无新增依赖 |
| 相邻后端测试 | application的delivery actions、Codex driver／submission、dispatch runner、persistence store／migration六组测试 | 符合确定性后端检查边界 |
| 流程记录 | 本功能intent、plan、T01–T03及本文 | 文档标识和任务依赖一致 |
| 独立既有前端修改 | 实现提交另包含 `web/src/style.css` 变更 | 与消息投递任务无关，不纳入本报告功能验收 |

## Acceptance criteria checklist / 验收标准检查清单

测试名称及完整映射见T03交付，下列结果结合实际代码审查与已有最终检查确认。

| 验收 | 对应证据 | 结果 |
| --- | --- | --- |
| A01 原子受理 | 实际MessageService与请求事务测试同时核对message、publication、recipient和delivery；commit／rollback及同事务发布重放 | 通过 |
| A02 提交后后台可见 | 独立SQLite连接在提交前不可见，提交后可领取，回滚无残留；中间件提交先于成功响应；发布路径无driver依赖 | 通过 |
| A03 短事务与无长锁 | fake submit／activate调用中可取得同房间文件锁和独立数据库写事务；实际store调用边界位于RPC之外 | 通过 |
| A04 同目标顺序与占用 | 持久队首退避、无效旧目标资格、必要启动／原结果保存期间session排除及同目标后项不越序 | 通过 |
| A05 多目标推进 | 同频道多目标及其他房间在首目标暂时失败时推进；恢复后5个假外部输入各写一次；慢检查公平性覆盖容量1／4 | 通过 |
| A06 分类及持久恢复 | 假RPC覆盖超时／断连、目标未加载、MCP暂时状态与配置／认证失败；新store实例保留原任务和退避时间 | 通过 |
| A07 只保存原结果 | 回执保存异常后只重试finish，不再次提交；条件更新false直接结束，已received／删除记录不复活 | 通过 |
| A08 正向事实核验 | queue／输入历史分页、未命中不重发、新unknown屏障与历史count0隔离；首次检查标记跨实例恢复，未知start只尝试一次 | 通过 |
| A09 可复核检查 | 同一冻结版本475项后端测试及类型／lint／格式通过；版本、时间、失败修正和未运行边界均有记录 | 通过 |

## Test / command results / 测试 / 命令结果

项目使用Python3.12、uv、pytest、mypy及Ruff，命令沿用既有Makefile／pyproject入口。以下为中级开发已执行、主会话已接受的最终证据，来源为 `msg-0354` 及T03记录；本轮按用户要求不重跑。时间均为2026-11-16北京时间，退出码均为0。

| 执行时间 | 命令 | 已有实际结果 |
| --- | --- | --- |
| 21:04:06–21:04:07 | `uv run --locked mypy src tests` | 212个source files，无错误 |
| 21:04:10 | `uv run --locked ruff check .` | All checks passed! |
| 21:04:13 | `uv run --locked ruff format --check .` | 362 files already formatted |
| 21:04:17–21:04:25 | `uv run --locked pytest tests/unit` | 475 passed in 6.93s |

环境为Windows、Python3.12.12、pytest9.2.0。最终检查前后store测试SHA256均为 `132CB27ED94F97DAA35CBB57AC65553C1C954287F28CD309D6219C7A251829CC`；本轮复核与其余七项快照均一致。实现交付时的 `git diff --check` 已通过。

早期SQL E501、并发4时过严的绝对交替断言、测试字典类型推断错误均已修正并保留过程记录；本报告使用修正后的最终四项完整检查，没有合并不同版本的局部通过充当全量结果。

未运行UI、真实Codex投递、实际成员并发实验或压力测试，符合原意图边界。迁移检查来自临时旧库升级、默认值及外键验证；本轮未操作运行库、服务或历史投递。没有新增测试执行结果。

## Missed or expanded scope / 遗漏或扩大的范围

未发现功能遗漏或未协调的产品范围扩大。P08首次启动恢复和R04公平性在已接受修订4范围内完成。独立 `web/src/style.css` 变更排除在验收外。

实施中曾按用户优先要求由高级开发备份开发库、补齐模型导入并迁移恢复服务可用性，记录见T01及 `msg-0316`；这是既有实施插曲，本轮验证未执行相关操作，不将其作为真实投递实验的替代证据。

## Risks / 风险

- 上游无去重保证。真正unknown且没有队列／输入正向证据时，继续观察并维持有效同目标后项屏障，可能持续等待；未命中不证明安全重发。
- 尚未持久化的回执在进程崩溃后只能按unknown恢复；已记录启动尝试后即使start结果不明或进程崩溃，也不自动重复启动。
- 本报告确认后端确定性用例及代码契约，不扩展为真实Codex端到端、生产负载或UI实测结论。

## Incomplete items / 未完成事项

本功能实现及约定验证文档无未完成项，无新的待用户设计决定。历史投递补发、真实成员实验和独立前端改动属于原有范围之外。

## Conclusion / 结论

通过。意图A01–A09、总计划修订4、T01–T03有效交付与最终集成证据一致；当前八个关键文件与已通过检查的快照匹配。依用户要求复用既有证据完成整体Verification，本轮仅新增本文及更新总计划的验证记录，未重新运行测试或修改产品代码。
