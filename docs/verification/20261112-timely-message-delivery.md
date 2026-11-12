# Verification / 验证：提高消息投递时效
最后修改时间: 2026-11-12 10:13:33

## Review status / 审查状态

Accepted

当前窗口完成技术验收。依据用户“进入验证，可以使用 jev-ultrafast-mcp 自测”的追加授权，使用隔离数据库、独立测试会话和真实 Codex daemon 检查；没有迁移原用户数据库、向原工作会话发送输入、暂存、提交或部署。

## Intent alignment / 意图对齐

- 对照[意图](../intent/20261112-timely-message-delivery.md) A01–A08：界面没有新增模式选项；空闲消息走 queue，忙碌消息走原活动轮次的 steer。实际历史保留客户端 ID、正文 envelope、必需 Relay Skill 及所选原生能力。
- 共创建 10 条 Relay 测试消息：8 条精确历史确认接收；1 条无效 Skill 在输入写入前拒绝；1 条成功 steer 后清空本地待办，其原生历史输入仍保留。9 次成功接纳各有且仅有一个对应客户端 ID 的历史输入。
- 忙碌场景的历史确认发生在同一个原轮次内。确认仍有数秒至数十秒延迟；本次不承诺或证明固定秒数内处理、停止工具或回复。
- A08 的 Implementation 检查限制保持历史有效；本阶段的浏览器、临时 SQLite 与链路检查依据追加 Verification 授权执行。未恢复测试支持目录，现场脚本仅在临时目录。

## Plan alignment / 计划对齐

- 与[计划](../plan/20261112-timely-message-delivery.md)的 submit 联合回执、共享 daemon proxy、当前轮次定位、queue-only 激活/删除、精确历史确认和公平调度一致。
- Codex CLI 为 `0.167.1`，运行使用 `codex app-server proxy`；没有改为 `codex exec`、模拟终端输入或替换产品执行宿主。
- 验证基线为 `a5c06099632f9ad1d17ecfbab3318fddea700666` 上当前工作区 diff。产品文件与已接受任务交付的 SHA-256 一致；本阶段仅补充流程文档，无产品代码修复。
- 隔离端口 `19080`，静态资源为现有 `web/dist` 生产构建；临时数据库 `C:/Users/leon/AppData/Local/Temp/agent-relay-verification-20261112-0954/verification.sqlite3`，启动从 baseline 前滚至 `delivery_steer_20261112`。

## Task deliveries and integration / 子任务交付与集成

| ID | 当前有效交付版本 / 位置 | 必要检查与审查证据 | 集成与基线核对 | 验收归属与结果 |
| --- | --- | --- | --- | --- |
| T01 | `TIMELY-T01-01`；ports SHA-256 `20f472debc23ce6e1bd5919d0da0e7eb8e68dd2b28c9b6b61295ede0f3b09b02` | 领域/mapper 单测；临时库启动；6 条旧记录前滚与 5 类非法组合拒绝 | 新 head 可运行；queue/steer 事实与 API 往返一致 | A02/A03/A06/A08 通过 |
| T02 | `TIMELY-T02-01`；driver SHA-256 `80924437a3035056fb9b9ee7d32225191778a8621eca9129d1b6676ea14cca4d` | 真实 idle/active、原生 Skill/MCP、无效能力零输入；异常/回退单层用例 | 消费已接受 T01，真实 proxy 与安装版本一致 | A01/A02/A04/A08 通过 |
| T03 | `TIMELY-T03-01`；service SHA-256 `fdcc5ca4aff17893f9787aec6e0449994fae993481d627a6136959d7147d8400`；runner SHA-256 `86615c7817ba81ec18184b9335b85f1f805e398042bc83690ab907826d09c21e` | 222 后端单测；连续 6 次真实发布；精确历史与清空不重投 | 接纳与接收分离；同目标串行提交；无额外轮次 | A01/A02/A03/A05/A06/A08 通过 |
| T04 | `TIMELY-T04-01`；当前 web/设计说明 diff，前置版本未变 | 32 项既有组件断言；jev 发送、Skill、状态、详情与清空说明 | 两类输入共用界面，失败详情和时间线一致 | A06/A07/A08 通过 |

## Corrections and scope / 修复与范围

| 对齐依据 | 发现的偏差 | 实际修复 | 复验结果与证据 |
| --- | --- | --- | --- |
| 意图 A01–A08、总计划及四项任务 | 未发现需要修改产品实现的偏差 | 无产品代码修复；同步验证授权、状态与证据 | 下述运行、历史、迁移、单测和静态检查通过 |

- 最终产品 diff 与已接受实现相同：投递契约与存储及新增迁移、Codex 路由、服务/调度、前端状态和设计说明。验证没有扩大产品修改范围。
- 测试会话通过原生 RPC 新建，由测试连接保持加载；首次关闭连接后会话不能加入房间，是既有未加载保护，保持加载后成功加入。
- jev 自动任务入口缺少 decision-model key，改用同一 MCP 的 observe/act 循环；未修改工具配置。后台启动命令被自动审批拦截后，使用受控终端会话启动，验证未受阻。

## Acceptance results / 验收结果

| 验收 ID | 结果 | 证据或未满足原因 |
| --- | --- | --- |
| A01 | 通过 | #1 method=queue；#2–#8/#10 method=steer。总共仅 3 个轮次：空闲队列消费轮次与 2 个主动建立的忙碌测试轮次，steer 未创建轮次。idle 的原宿主自行消费队列；应用精确队首启动由既有单测覆盖。 |
| A02 | 通过 | #9 无效 Skill rejected，历史无其客户端 ID；9 条接纳输入各恰好一次。超时/断连、损坏回执、版本缺失与竞态由单层用例验证，未向真实 daemon 注入故障。 |
| A03 | 通过 | 8 条 received 的 item/turn/client ID 与独立读取的历史一致。#10 清空后保留 queued+deletedAt，不伪造 received。 |
| A04 | 通过 | 接纳输入均保留正文 envelope 与 Relay Skill；#4 有额外原生 `best-practices:check-acronym-casing` skill；#8 有 `mention(name=agent-relay,path=mcp://agent-relay)`；#9 零历史输入。 |
| A05 | 通过 | 并发 1/4 的公平性、容量与异常单测通过；真实短突发 #5–#8 全部得到核验。短突发不构成长期压力或固定时延证明。 |
| A06 | 通过 | 旧版临时库 6 条记录前滚后原字段逐一不变，5 条非 pending 回填 queue、pending 方法为空；5 类非法组合被拒绝。#10 removedMessages=1、codexQueue 全部计数=0，原输入仍在历史。最终原生队列与 Relay 待办均为空。 |
| A07 | 通过 | 浏览器实际出现发送中、接收中、已接收与预期能力失败；#9 时间线和详情均为发送失败，显示安全错误。无模式选择，清空说明不暗示撤回。待确认路径由既有断言与状态实现核对。 |
| A08 | 通过 | 当前版本 222 后端单测、32 前端断言、mypy、Ruff 和 diff 空白检查通过；沿用同版本前端静态检查/build 与离线 SQL 开发证据，增加隔离运行/迁移证据。 |

### Real delivery observations / 真实投递观察

下表日期均为 `2026-11-12`，时间为 UTC。接纳落库来自 queued 阶段本地 `updatedAt`，历史确认落库来自 `receivedAt`；不是服务端精确消费时刻，也不是模型处理/回复时刻。未采样到的接纳时间不反推。

| 消息 | 路径 / 结果 | 创建 | 接纳落库 | 历史确认落库 | 创建至确认 |
| --- | --- | --- | --- | --- | --- |
| #1 空闲 | queue / received | 01:58:53.791266 | 01:58:55.208553 | 01:58:57.926914 | 4.136 秒 |
| #2 忙碌 | steer / received | 02:00:03.713825 | 未采样 | 02:00:15.987467 | 12.274 秒 |
| #3 忙碌 | steer / received | 02:01:09.135380 | 02:01:10.645751 | 02:01:14.431516 | 5.296 秒 |
| #4 所选 Skill | steer / received | 02:04:29.116316 | 未采样 | 02:04:55.312573 | 26.196 秒 |
| #5 连续发布 | steer / received | 02:05:30.205993 | 02:05:31.872802 | 02:05:49.261322 | 19.055 秒 |
| #6 连续发布 | steer / received | 02:05:30.247690 | 02:05:33.228946 | 02:05:51.321373 | 21.074 秒 |
| #7 连续发布 | steer / received | 02:05:30.291601 | 02:05:34.551480 | 02:05:51.312349 | 21.021 秒 |
| #8 所选 MCP | steer / received | 02:05:30.335020 | 02:05:45.535901 | 02:05:51.300310 | 20.965 秒 |
| #10 清空待办 | steer / queued+deletedAt | 02:05:30.411047 | 02:05:48.645273 | 不再核验已删除待办，原生历史有唯一输入 | 不适用 |

- #2/#3 提交与接收轮次均为 `01a1cd7b-40bc-7901-bc95-7ea24bb60eb8`，直到 `02:02:40Z` 才完成；#4–#8/#10 的原轮次为 `01a1cd7f-8a7e-7a63-948b-c4cb61c71048`，直到 `02:06:12Z` 才完成。确认发生在原活动轮次内。
- #3 创建至接纳落库约 1.510 秒。短突发中，#8 前序有串行提交并需原生 MCP 能力查询，创建至接纳 15.201 秒；#10 为 18.234 秒。本次未分离所有能力预检、工具、RPC 和观察耗时，不全部归因于工具等待。
- #10 在 `02:05:48.859646Z` 清空，后续独立读取历史仍有唯一 `clientId=f0e4f361-030a-4051-aabb-0b1519bd8a91`，没有重投或原生队列项。

## Check results / 检查结果

| 命令 / 检查 | 实际结果 | 未运行原因 |
| --- | --- | --- |
| `uv run --locked pytest tests/unit -q` | 222 passed，1.62 秒 | 不适用 |
| `uv run --locked mypy src tests` | 138 files，无错误 | 不适用 |
| `uv run --locked ruff check .` | 通过 | 不适用 |
| `uv run --locked ruff format --check .` | 229 files 通过 | 不适用 |
| `git diff --check` | 通过 | 不适用 |
| web：`corepack pnpm test tests/domains/room/MessageDetails.test.ts tests/domains/room/MessageQueue.test.ts tests/domains/room/MessageTimeline.test.ts` | 3 文件、32 tests 通过 | 不适用 |
| web：typecheck、lint、format、build | 同版本 Implementation 已通过；本阶段实际加载其生产构建，web 源码未改 | 未重复无改动构建，保留既有 v-html 与包体积 warning |
| Alembic 离线 SQL/history/heads | 同版本 Implementation 已通过，head 正确 | 本阶段进一步检查实际隔离库前滚 |
| 临时 `check_migration.py` | 旧记录保留/回填、完整性、5 类非法组合检查通过 | 不适用 |
| 临时 `check_burst.py`、`check_evidence.py` | 连续发布、能力、精确唯一关联、清空、轮次数与空队列断言通过 | 不适用 |
| jev-ultrafast-mcp | 空态、成员添加、4 次界面发布、Skill 选择、状态、失败详情与清空说明通过；额外 6 次由真实 HTTP 发布 | 建房由 API 设置；实际清空走同一 HTTP 入口，UI 按钮回调由既有组件断言覆盖 |
| 运行日志 | 只有主动构造的 #9 能力拒绝 ERROR，无未处理异常或 dispatcher 停止记录 | 不适用 |

### Evidence location / 证据位置

- 临时证据根：`C:/Users/leon/AppData/Local/Temp/agent-relay-verification-20261112-0954`，包含输入历史、轮次/队列快照、状态采样、迁移库与一次性脚本；未作为仓库测试设施加入。
- `evidence-summary.json` SHA-256：`b7e288ee396078bf1ff1b3485c4ec438b71bcc2ec8defdc787b3c72639ce7ea0`。
- `history-final.json` SHA-256：`433483f33962a3a807af33f0fd7da0e4482561a95dcf36c6d672496d0ef03e77`。
- `migration-summary.json` SHA-256：`cc8959f4f22e145491559dd91d61d83caaf508e230255e19d5f7df212182fb26`。
- 目视核对截图：`C:/Users/leon/.jev-ultrafast-mcp/shots/timely-rejected-details.jpg`，失败详情、时间线、清空说明及空队列一致；SHA-256 `cbd2082e96bf32191ea0415c4be385dd8e52c2890007d5815e579207c02bdaf3`。

## Risks and incomplete items / 风险与未完成项

- 无验收阻塞。未做生产积压清理、长期压力测试或真实 daemon 故障注入；异常边界依赖单层用例。本次样本不构成固定时延保证。
- 部署目标仍须按正式入口迁移数据库；临时库前滚不代表原用户库已升级。新旧程序不能混跑，历史已排队输入不会自动重投。
- 工具执行、能力预检和 RPC/观察仍可能延迟确认。steer 证明向当前轮次输入，不证明模型立即处理或回复。
- 临时服务与测试宿主连接已停止，端口 19080 不再监听；本次唯一测试会话 `01a1cd76-36ef-7dd0-8db8-f9c78a11cdb9` 已归档，测试浏览器标签已关闭。临时证据保留。

## Conclusion / 结论

- 当前交付通过整体验证，与已接受意图和方案对齐，无产品返工或遗留验收失败。
- 新消息在忙碌目标原轮次内确认接收，queue 兼容、能力引用、防重复、迁移和清空语义均有证据。技术验收完成，不表示已生产发布或处理用户现场积压。
