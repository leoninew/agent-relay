# Task / 子任务 T02：重试恢复与回执核验
最后修改时间: 2026-11-16 20:57:00

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261116-reliable-message-delivery.md)；权威总计划：`D:/SourceCodes/mywork/conflua/docs/plan/20261116-reliable-message-delivery.md`。
- 任务 ID：T02；方案修订：4。依赖、有效分配及前置版本以总计划为准。

## Handoff basis / 交接依据

执行者：高级开发 `member-076ee1012fab`；编号 `RMD-T02-20261116-dab315f4`；用户授权 `msg-0311`，方案修订4。前置 T01 已接受：HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb` 加其20:32交付快照，五文件 SHA256 和检查见 T01，主会话20:35审查一致。共享代码／权威根 `D:/SourceCodes/mywork/conflua`；已有 T02 在途范围见 T01 记录，仍须完成当前交付，不重做已接受基础。高级开发负责实现和测试设计，中级开发仅执行精确检查命令。协议入口及 P01–P08 见总计划。允许写本文 Reception and progress、Delivery and review 及最后修改时间，先接收再实施，通过 Conflua 定向回报架构师。

## Goal and acceptance / 目标与验收

交付可恢复的投递状态处理，满足 A06–A08：准确分类、持久退避、成功回执保存重试及真实不确定结果核验。

## Inputs and eligibility / 输入与可开始条件

输入为总计划指定的已接受调度／事务接口与固定版本，以及 `msg-0296` 的前置错误与协议证据。不得把旧版去重实验解释为新版支持幂等。

## Scope and files / 范围与文件

driver、delivery service/ports/dto/domain、持久化仓储／模型／映射，以及必要 SQLite 迁移和相邻单测。具体字段名和参数在实施时统一；不修改运行数据库或历史投递。

## Technical decisions / 局部技术设计

- 将断连／超时等明确未发输入的暂时故障与确定绑定／配置错误分开；错误类型保留阶段和安全诊断，不靠宽泛异常推断是否发送。
- 保存重试时间与必要原因，恢复原任务及关联标识；退避按目标队首生效，不能让同目标后项越序，不冻结房间。
- 成功外部回执保存失败只重试写库；状态更新受原任务及已有状态约束，避免重复调用输入 RPC。
- queue/list 分页命中证明入队，完整输入记录证明 received；空页、缺页、不可用不证明未发送。没有去重契约时不自动重发不确定输入。
- 重启恢复区分可重试等待与可能已发送，禁止将所有中断项批量变成 pending。
- 新尝试 `unknown` 且 `attempt_count > 0` 的有效较早任务作为同 session 后项屏障；取得队列／输入正向事实后放行，未命中继续观察。迁移前历史 unknown 的计数默认为 0，保持原有处理，不新增屏障或补投。资格检查与 R01 一致，测试须同时证明新／历史区分。
- 按 P08 持久化新机制原队列项的首次启动检查；observer 不直接 start，runner 与 submit 共用 session 归属；idle／精确原队首／未尝试启动才可一次 claim 后 start。领取／重启不丢标记，原 start 结果未知不重试；不扩展为历史 queued 通用启动重试。覆盖新回执已保存后、首次启动前的崩溃间隙。

## Implementation outline / 实施安排

1. 核对前置版本与真实输入写入边界，定义可重试分类及状态接口。
2. 接入持久化等待、必要迁移、回执保存重试和原请求核验。
3. 完成相邻确定性检查及迁移验证，交付实际证据供 T03 集成。

## Checks and delivery / 检查与交付

使用假 RPC、假时钟与临时仓储，区分准备调用和真实输入写入次数。沿用总计划的后端检查；若有迁移，验证旧库升级及默认值。交付记录包含 A06–A08 证据、实际版本／前置版本、命令及未运行项。

## Risks / 风险

steer 已尝试后的 queue 回退路径不能误判为从未发过输入。上游错误码、回执缺失及输入历史缺页必须按证据保守分类；不通过增加重发次数掩盖协议缺口。

## Reception and progress / 接收与进展

- 2026-11-16 20:38 接收：高级开发 `member-076ee1012fab`，编号 `RMD-T02-20261116-dab315f4`，方案修订4；用户授权 `msg-0311`，派发 `msg-0334`。权威根与总计划已核对，前置为 T01 accepted 的 HEAD `45643391`＋20:32 五哈希快照；沿用在途代码，不重做已通过基础。
- 继续修正 R02／R03，新增本轮 unknown 队首屏障及 P08 的持久首次启动检查，验证迁移旧值与新任务恢复边界。高级开发负责失败分析与代码，中级开发只运行精确检查。
- 2026-11-16 20:53：R04 完成两层公平性修正。写任务种类与待保存结果／观察轮换；首次检查按持久到期时间再插入顺序领取。慢检查、并发1／4、持续保存失败的滑动窗口推进和两个慢检查目标的轮流领取均通过，中级开发回报 `msg-0346`。架构师 `msg-0347` 已审实际 diff，要求整理正式交付后审查接受。

## Delivery and review / 交付与审查

### 2026-11-16 20:57 交付待审查

- 执行者：高级开发 `member-076ee1012fab`；有效编号 `RMD-T02-20261116-dab315f4`，局部方案修订4，授权 `msg-0311`，派发 `msg-0334`。前置版本为 T01 accepted 的 HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb`＋20:32交付快照；实际交付为同一权威根下当前工作区 diff 及下表 SHA256。没有执行 Git 写操作。
- 实际范围：扩展 delivery ports／dto／service、Codex driver、runner、DeliveryStore／仓储／模型，增量 SQLite 迁移及迁移说明；更新相邻 application、driver、submission、runner、store、migration 六组测试。与 T01 共用接口的扩展已按影响回归。`web/src/style.css` 为无关既有修改，未纳入交付。
- A06／R02：以输入写入阶段区分 `SubmissionDeferred`、确定拒绝和未知；前置断连／超时、目标暂未加载、MCP starting／暂时 runtime unavailable 可退避，缺失／禁用／认证和 FileNotFoundError／PermissionError／无效 shim 保留准确拒绝。持久化 attempt_count 与 next_attempt_at，1秒起、上限30秒退避，保留原任务和 client 标识；同目标有效退避队首阻挡后项，其他目标继续。假 ProxyRpc、临时库及新 store 实例验证，没有真实输入实验。
- A07：`DeliveryOutcome` 保留原回执或原退避结果，写库异常由 runner 延后重试保存；session 在准备、提交、原结果待保存及必要 activation 全部结束前保持占用。条件更新 false 直接结束，不当成写库异常，不覆盖已 received／已删除记录，也不启动。真实输入只写一次；仓储／runner 用例覆盖 queued 已保存但 activation 未结束、保存失败跨 Future 返回及其他目标推进。
- A08／R03：add 已调用后的内部错误（含 -32603）、断连、错回执保留 unknown；已尝试 steer 的回退不重置写入事实。observer 分页核验原 queue 与输入历史，只接受正向精确关联事实；queue 命中仅证明 queued，历史命中才证明 received，未命中不重发。有效较早 unknown 且 count>0 阻挡同 session 后项，历史 count0 保持原处理，不新增屏障、补投或启动。
- P08 首次恢复：新 queued 回执保存和新 unknown 精确找回原 queue 时均持久安排首次检查；observer 不 start。runner 的检查作业沿用 submit 的 session 归属，仅 idle＋精确原队首＋原回执下 claim_activation 后首次 start。领取检查只推进检查时间，不丢标记；记录启动尝试与清标记原子完成。重启可恢复保存后／首次启动前间隙；已记录尝试的成功、拒绝、未知均不再次 start。临时库参数化覆盖直接回执／找回回执以及新 store 重建，start 超时后只调用一次。
- R04：调度交替偏好 submit／首次检查，并为待保存结果和 observation 保留有界推进。并发1／4、慢检查持续到期、其他目标 pending、可选持续保存失败的假时钟／Future 用例，逐个12 tick滑动窗口要求全部持续任务类型出现；session 排除沿用占用用例。仓储按 next_attempt_at、rowid 领取，两目标慢检查按 first／second／first／second 推进。首轮绝对交替断言不适用于并发4排除在途 session，已按 `msg-0344` 改为可衡量的持续推进断言，未删除公平性用例。

### 检查命令与时间

以下均由中级开发在 HEAD `45643391`＋各时点工作区执行，退出码除已注明首轮失败外均为0；时间为北京时间2026-11-16。

| 时间 | 命令／范围 | 结果及证据 |
| --- | --- | --- |
| 20:45:27–20:45:33 | `uv run --locked pytest tests/unit/application/test_delivery_actions.py tests/unit/infrastructure/persistence/test_delivery_store.py tests/unit/infrastructure/dispatch/test_delivery_runner.py tests/unit/infrastructure/codex/test_submission.py tests/unit/infrastructure/codex/test_driver.py tests/unit/infrastructure/persistence/test_migrations.py -q` | 142 passed，3.39s；msg-0337，R04修改前 |
| 20:45:36–20:45:37 | `uv run --locked mypy src tests` | 212 source files通过；msg-0337 |
| 20:47:24–20:47:26 | `uv run --locked pytest tests/unit/infrastructure/codex/test_submission.py tests/unit/infrastructure/persistence/test_migrations.py -q` | 51 passed，0.82s；新增认证状态及SQL修正后的影响回归，msg-0339 |
| 20:47:28 | `uv run --locked ruff check .` | 全部通过；msg-0339；原内嵌SQL E501已修正 |
| 20:47:32 | `uv run --locked ruff format --check .` | 362 files已格式化；msg-0339 |
| 20:51:08–20:51:09 | `uv run --locked pytest tests/unit/infrastructure/dispatch/test_delivery_runner.py -q` | 首轮1 failed／14 passed；并发4绝对交替断言失败，由高级开发分析修正，msg-0343 |
| 20:51:12–20:51:13 | `uv run --locked mypy src tests` | 212 source files通过；msg-0343 |
| 20:53:15–20:53:17 | `uv run --locked pytest tests/unit/infrastructure/dispatch/test_delivery_runner.py tests/unit/infrastructure/persistence/test_delivery_store.py -q` | R04最终影响回归32 passed，2.05s；msg-0346 |
| 20:53:21 | `uv run --locked ruff check .` | 全部通过；msg-0346 |

机械格式化范围与结果见 msg-0337、msg-0343、msg-0346；最后一次仅格式化已列明的 repository／runner test／store test 三文件，1文件改变、2文件未变。本节点没有重复全量；T03在冻结版本完成完整后端检查。

### 最终关键文件快照

SHA256 于20:56核对，路径相对权威根 `D:/SourceCodes/mywork/conflua`：

| 文件 | SHA256 |
| --- | --- |
| `src/conflua/application/delivery/service.py` | `B6181E606BDC2AEB90FAFBA9E9E33313698F52181101E40ACD46D6CD708A4BA6` |
| `src/conflua/infrastructure/codex/driver.py` | `BF60ABC62ADEAB87110F0A80D1360E3A442A9B5E5E5CB3A8CD285F95D180E9A5` |
| `src/conflua/infrastructure/dispatch/delivery.py` | `ACD9D44AE4EC1767B3BEF65CF4F565731219713CA72B15E437254452D9CEFF08` |
| `src/conflua/infrastructure/persistence/repositories/deliveries.py` | `CD2522561466075AEAE0230581C664DCFAF632FE2F611923BD244EDEB9089974` |
| `tests/unit/infrastructure/dispatch/test_delivery_runner.py` | `781007AF4E4856D4901F0DD83EE6B4CDCE5A281298B8E4F80FECBD858BB0BB2B` |
| `tests/unit/infrastructure/persistence/test_delivery_store.py` | `F79474F377B177F019EF15470F9F70E56B42A0D1C5A45C7FAFFC2285AF15EE9A` |
| `migrations/sqlite/versions/0002_delivery_retry.py` | `30640BF77674CF9413D3834308CA96EF23C9005031867E263C5FFD9EECD5AD66` |
| `migrations/sqlite/sql/0002_delivery_retry/01_retry.up.sql` | `0F3067281D176D090A39128032AF17B527E8EFB7704AB027A26E7D9329982311` |

### 迁移、未运行项与下游

- 新迁移 `delivery_retry_20261116` 从原 head增量增加两列；count默认0，历史unknown不被当成本轮尝试。临时旧库升级、外键检查及重复upgrade通过。迁移资源沿用已有整目录打包；说明已更新。本节点未再次操作开发库或服务，先前按用户优先要求恢复开发库和HTTP 200的事实见 T01，不作为本节点新操作。
- 未运行：冻结版本完整后端检查由 T03完成；真实Codex输入、UI、历史补投、服务管理均不在范围。未完成产品项：无。待仲裁：本次交付接受及 T03派发。
- 保留风险：上游无去重承诺，真正未知且没有正向证据的任务持续观察并阻挡其有效同目标后项；不会猜测未发送。进程崩溃丢失尚未持久化的回执时仍按unknown恢复观察。启动尝试记录之后即使进程崩溃也不自动重复start；不引入通用启动重试。以上为P05／P06／P08约定边界。
- 对下游影响：T03沿用本快照和有效 T01，核对A01–A09及迁移边界，执行完整后端检查；任何后续代码修正应更新受影响快照和检查证据，不以本节点的局部通过代替集成结果。
