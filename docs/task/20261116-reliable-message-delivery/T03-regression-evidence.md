# Task / 子任务 T03：确定性回归与集成审查
最后修改时间: 2026-11-16 21:05:12

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261116-reliable-message-delivery.md)；权威总计划：`D:/SourceCodes/mywork/conflua/docs/plan/20261116-reliable-message-delivery.md`。
- 任务 ID：T03；方案修订：4。依赖、有效编号及阶段授权以总计划为准。

## Handoff basis / 交接依据

执行者：高级开发 `member-076ee1012fab`；有效编号 `RMD-T03-20261116-1c4fd60e`；方案修订4。用户 `msg-0311` 授权Implementation及必要开发检查与任务审查。基线为HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb`＋T02于20:57交付的八文件SHA256快照（主会话20:58全匹配并接受）及有效T01。代码及权威根为 `D:/SourceCodes/mywork/conflua`；协议入口见总计划Coordination，沿用P01–P08。高级开发负责测试设计、编写及失败分析；中级开发只运行精确命令。允许写本文Reception and progress、Delivery and review及更新时间，先落接收再实施／检查，通过Conflua定向回报架构师；不改总登记。

## Goal and acceptance / 目标与验收

交付可靠投递的确定性回归和集成证据，满足 A09 并回归 A01–A08。子任务开发检查不自动进入整体 Verification。

## Inputs and eligibility / 输入与可开始条件

依据总计划的直接前置要求核对有效实现和状态契约；参考 `msg-0297` 的 7 条故障证据及架构师 `msg-0298` 对测试口径的修正。

## Scope and files / 范围与文件

受影响的 `tests/unit/application/`、`infrastructure/dispatch/`、`infrastructure/persistence/`、Codex 驱动单测及本任务记录。发现实现缺陷回报主会话协调，不独自扩大产品范围。

## Technical decisions / 局部技术设计

- 使用现有 pytest、局部假驱动、假时钟及临时仓储，不引入真实成员会话、UI、性能或并发压测。
- 覆盖同频道多目标、同目标提交及队首退避顺序、其他目标调度、前置暂时故障恢复、明确配置失败、回执保存重试和未知结果核验。
- 入队成功断言回执，收到输入必须另外提供历史证据；同目标顺序使用持久化投递顺序，不比较跨房间 seq。
- 前置失败允许重复准备，但不应发生重复真实输入写入；既有已接受回执不触发再次提交。不把所有状态无条件断言为 received。
- 新增持久字段时核对迁移和重启恢复；日志中的 NULL 字段仅作辅助证据，不单独据此推断未发送。
- 核对新尝试 unknown 的同目标屏障、正向核验后的放行，以及迁移前历史 unknown 不新增阻塞或补投；覆盖无效目标资格，避免永久挡住其他有效任务。
- 核对原 queue 项精确恢复后的受控首次启动：准备失败／非 idle／非原队首只延后检查；启动尝试记录后不重复 start；新任务已保存回执后崩溃可恢复首次检查，历史项不被纳入新启动机制。回归 session 占用和既有观察公平性。

## Implementation outline / 实施安排

1. 对照实际实现和调用方精简既有测试漂移，固定关键业务断言。
2. 补齐确定性用例及适用迁移／仓储检查，不复制实现细节或旧错误设计。
3. 执行相关及完整后端检查，汇总验收映射、集成版本和剩余边界。

## Checks and delivery / 检查与交付

沿用总计划的 mypy、Ruff 和 pytest 入口。交付记录按 A01–A09 对应实际用例、版本、命令结果及未运行项；明确未运行 UI 或真实 Codex 测试。由架构师核对上游有效性和集成结果。

重点核对现有覆盖是否已能证明请求未提交不可见及同频道多目标完整推进；确有缺口时以临时库／假驱动补最少必要集成用例，覆盖单目标先暂时失败再恢复、其他目标继续、真实输入各一次，并分别断言queue回执和输入证据。已有充分覆盖不重复造测试。冻结产品／测试后由中级开发执行：`uv run --locked mypy src tests`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .`、`uv run --locked pytest tests/unit`。命令对应同一冻结版本；失败由高级开发分析，变更后补必要影响检查，交付不得把不同版本的局部通过合称全量通过。

## Risks / 风险

只断言“最终都 received”会掩盖证据层级；只断言一次 driver 调用会错误约束前置重试。测试应证明业务承诺，不以真实耗时或线程时序判断正确性。

## Reception and progress / 接收与进展

- 2026-11-16 20:59:30 接收：高级开发 `member-076ee1012fab`，有效编号 `RMD-T03-20261116-1c4fd60e`，局部修订4；用户授权 `msg-0311`，派发 `msg-0349`。权威根／任务及总计划已核对；前置为 T02 accepted 的 HEAD `45643391`＋20:57八哈希快照和有效T01。
- 覆盖核对发现请求事务现有用例只检查提交／回滚调用，缺少真实SQLite连接未提交可见性断言；多目标领取与单目标恢复分别已有用例，但缺少同一消息的完整组合推进。将仅补这两类确定性证据，保留既有边界用例；产品代码不变，完成后冻结交中级开发运行指定完整后端检查。
- 2026-11-16 21:04:32：新增两类共3个参数化执行用例通过；首轮全量475通过但mypy发现既有R04测试receipt字典值类型推断过窄，高级开发仅增加 `dict[str, object]` 注解后重新冻结。中级开发 `msg-0354` 在最终相同快照执行完整四条命令，类型、lint、format和475项测试均通过。产品未修改。

## Delivery and review / 交付与审查

### 2026-11-16 21:05:12 交付待审查

- 任务／执行者：T03，高级开发 `member-076ee1012fab`，有效编号 `RMD-T03-20261116-1c4fd60e`，局部修订4。授权 `msg-0311`，派发 `msg-0349`，接收回报 `msg-0350`。
- 前置：T02 accepted 的 HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb`＋20:57八文件哈希快照及有效T01。交付为权威根当前工作区；T03只修改 `tests/unit/infrastructure/persistence/test_delivery_store.py` 和本文，产品代码与T02一致。`web/src/style.css` 为独立既有修改，未触碰或纳入。
- 新增：`test_request_message_and_routed_delivery_become_visible_only_after_commit[False/True]` 通过实际MessageService／RoomStore和SQLite两连接，核对消息、发布标识、接收人、delivery在请求未提交时均不可见，提交后一起可见且可领取，回滚后均无残留；同事务重放不重复创建。
- 新增：`test_multi_target_delivery_recovers_unsent_head_without_duplicate_inputs` 使用真实仓储与假driver。同频道同消息两目标中第一目标前置暂时失败，第二目标及另一房间照常入队；新store实例读取原持久退避，到期前不能领取后项，到期原标识重领，成功后才领取同目标后项。5个真实输入各写一次，失败目标准备2次；先断言全部queued且received_at为空，再提供原client输入历史并观察确认received，不以queue回执代替接收。
- 保留：T01／T02所有有意义用例，含无效旧队首、退避顺序、未知屏障、回执保存失败、session占用、一次启动及慢检查公平性；没有删除或放宽既有边界。唯一额外修正为R04仓储测试receipt字典的显式值类型注解，不改变运行行为或产品接口。

### A01–A09 验收映射

以下测试路径相对 `tests/unit/`，名称可在实际代码定位。完整后端运行包含所有列举用例。

| 验收 | 实际证据与结果 |
| --- | --- |
| A01 原子受理 | `infrastructure/persistence/test_delivery_store.py::test_request_message_and_routed_delivery_become_visible_only_after_commit` 的commit／rollback两种结果；`application/test_message_service.py` 的规范化路由、拒绝不保存和publication重放用例。真实请求事务保存消息／发布标识／接收人／delivery，未新增入库锁。 |
| A02 后台只读已提交 | 上述独立连接在请求提交前读不到新message／recipient／delivery，提交后claim成功、回滚后claim为空；`interfaces/test_transaction_middleware.py` 检查提交先于成功响应、异常回滚。MessageService仍只有事务写入，无driver依赖或RPC等待。 |
| A03 短事务与无长锁 | `test_submission_and_activation_hold_no_room_or_database_write_lock` 在外部submit／activate替身内，以新Context取得相同房间锁及数据库写事务；两次均成功。T01清理后旧busy／房间冷却／operation标识在目标路径无残留。 |
| A04 同目标顺序与占用 | `test_persistent_backoff_blocks_only_same_target_and_preserves_order`、`test_invalid_earlier_target_does_not_block_valid_same_session_work`、新组合推进用例，以及 `infrastructure/dispatch/test_delivery_runner.py::test_session_stays_owned_until_activation_or_original_result_save_finishes`；基于插入顺序，覆盖必要启动／保存重试仍持有归属。 |
| A05 多目标独立推进 | `test_different_targets_in_same_room_can_be_claimed_while_first_is_submitting` 和新组合推进用例；同频道另一目标和其他房间在原目标退避时正常推进，均以原回执／原历史确认。 |
| A06 准确分类与持久退避 | `infrastructure/codex/test_submission.py` 的前置错误、MCP暂时状态／配置／认证、未加载目标用例，`test_persistent_backoff_blocks_only_same_target_and_preserves_order` 及新组合推进的新store恢复；退避不改变原任务／client，真实写入次数与准备次数分开。 |
| A07 只保存原结果 | `application/test_delivery_actions.py::test_receipt_save_failure_retries_original_result_without_resubmitting`、`test_conditional_save_false_does_not_retry_or_start`，runner占用用例及仓储已received／删除后不复活用例；不再次add／steer。 |
| A08 未知按证据核验 | submission中输入后内部错误／断连／错回执／steer回退用例；application中的队列／历史分页及未命中不确认用例；仓储 `test_queue_evidence_and_input_history_record_distinct_facts`、新unknown屏障与历史count0区分、首次检查重启和未知start只尝试一次用例。 |
| A09 确定性集成检查 | 下面最终冻结快照完整475 passed，mypy／Ruff／format全部通过；runner容量1／4的滑动窗口持续推进、持久到期顺序的两个慢检查、公平观察和临时旧库增量迁移均包括在内。无真实Codex／UI依赖。 |

### 检查与同一冻结版本

最终命令由中级开发执行，原始回报 `msg-0354`。时间为北京时间2026-11-16；全部exit code 0。环境：Windows，Python3.12.12，pytest9.2.0，pluggy1.7.0，anyio4.16.0。

| 开始／结束 | 命令 | 实际结果 |
| --- | --- | --- |
| 21:04:06–21:04:07 | `uv run --locked mypy src tests` | Success: no issues found in 212 source files |
| 21:04:10 | `uv run --locked ruff check .` | All checks passed! |
| 21:04:13 | `uv run --locked ruff format --check .` | 362 files already formatted |
| 21:04:17–21:04:25 | `uv run --locked pytest tests/unit` | collected 475 items；475 passed in 6.93s |

首次检查 `msg-0352` 如实保留：21:02:04–21:02:07仓储定向20 passed；21:02:11–21:02:12 mypy有1处arg-type（R04测试局部dict值类型）；随后lint／format通过、21:02:22–21:02:34全量475 passed。高级开发补类型注解后，按新冻结快照完整重检，以上表最终结果为交付依据，没有把不同快照的局部结果拼成一次全量通过。最后 `git diff --check` 通过、暂存区为空。

最终快照为 HEAD `45643391bb464cca7d58a41ec8712d97ce2dd0eb` 加当前工作区。store测试文件SHA256在四条检查前后相同；高级开发21:04再次独立核对八文件：

| 文件 | SHA256 |
| --- | --- |
| `src/conflua/application/delivery/service.py` | `B6181E606BDC2AEB90FAFBA9E9E33313698F52181101E40ACD46D6CD708A4BA6` |
| `src/conflua/infrastructure/codex/driver.py` | `BF60ABC62ADEAB87110F0A80D1360E3A442A9B5E5E5CB3A8CD285F95D180E9A5` |
| `src/conflua/infrastructure/dispatch/delivery.py` | `ACD9D44AE4EC1767B3BEF65CF4F565731219713CA72B15E437254452D9CEFF08` |
| `src/conflua/infrastructure/persistence/repositories/deliveries.py` | `CD2522561466075AEAE0230581C664DCFAF632FE2F611923BD244EDEB9089974` |
| `tests/unit/infrastructure/dispatch/test_delivery_runner.py` | `781007AF4E4856D4901F0DD83EE6B4CDCE5A281298B8E4F80FECBD858BB0BB2B` |
| `tests/unit/infrastructure/persistence/test_delivery_store.py` | `132CB27ED94F97DAA35CBB57AC65553C1C954287F28CD309D6219C7A251829CC` |
| `migrations/sqlite/versions/0002_delivery_retry.py` | `30640BF77674CF9413D3834308CA96EF23C9005031867E263C5FFD9EECD5AD66` |
| `migrations/sqlite/sql/0002_delivery_retry/01_retry.up.sql` | `0F3067281D176D090A39128032AF17B527E8EFB7704AB027A26E7D9329982311` |

除store测试外其余七项与T02交付一致，T01／T02产品前置仍有效；T03没有产品范围偏差。

### 未运行项、风险与待处理

- 未运行UI、真实Codex提交、实际成员并发实验、历史补投或服务操作；均在既有范围之外。迁移测试只用临时库；没有再次操作开发库。未执行Git写操作。
- 未完成实施项：无。产品缺陷或新增范围：无。待仲裁：架构师核对当前交付版本、A01–A09及集成证据，接受T03。
- 风险／边界沿用P05／P06／P08：上游无幂等保证；真正不确定且无正向证据时持续观察，不猜测安全重发；新机制有效unknown保持同目标顺序屏障。记录过启动尝试后不重复start，不能承诺撤回已接受输入或外部恰好一次执行。
- 本文仅Implementation内开发检查与子任务交付，不创建整体Verification记录；本轮没有新的待用户设计决定。
