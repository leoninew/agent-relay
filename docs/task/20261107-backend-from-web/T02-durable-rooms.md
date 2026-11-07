# Task / 子任务 T02：持久房间、会话发现与成员绑定
最后修改时间: 2026-11-07 19:46:18

## Review status / 审查状态

Accepted（修订 10）。执行为 accepted：用户追加移除角色、参考 K12 数据访问及迁移实现已完成并复核；既有发现/绑定和默认 Windows 启动修复保留。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T02；方案修订：10。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；执行者 /root，沿用 T02-20261107-01；基线 2cc4933 + 当前工作区，不创建提交。

## Goal and acceptance / 目标与验收

G01—G03、G16 和 G17 主路径基础，对应 A02、A09、A16 基础和 A17：资源持久化；真实列出项目目录会话，选择后原子保存成员与原会话绑定；重启记录不变。没有隐式新建或接管执行。

## Scope and files / 范围与文件

room_store.py / room_state.py、member_sessions.py、drivers/codex.py、资源 API/配置/依赖及 Web 添加成员表单、API client、测试与说明。T03 的发布幂等/事件、T04 的实际 queue、T05/T07 的成员发布/查阅和 T09 其余目标不在本次交付。

## Inputs / 输入

T01 真实协议证据与 D02 最新纠偏；现有持久资源及路由。D04 至少一个订阅、D05 内联话题独立提交暂沿用；不追加备份恢复、执行权限、普通输出观察或其他兼容路径。

## Technical decisions / 局部技术设计

- 根目录 migrations/sqlite 管理 Alembic revision 及同级 sql/ 文件；alembic.ini 位于根目录。显式 migrate 入口 upgrade head，Make/容器启动先迁移；存储只检查版本并管理资源事务。无旧结构探测、自动 stamp 或旧库接入参数。
- 用户取消角色字段；成员只编辑名称和订阅，会话原绑定不变。会话选择项移除模型提供方显示，驱动仍使用真实 provider 做元数据核验。迁移中的 SQL 清除成员 payload.role；不为已移除字段或旧协议新增反向测试。

- 使用共享 daemon 的 app-server proxy，WebSocket 帧经 stdio 转发；请求范围连接结束只关闭自身 proxy。没有独立执行宿主、启动自动 resume 或运行时锁。
- 默认 codex 命令支持 Windows 官方 npm 安装：定位同一安装的 node_modules/@openai/codex/bin/codex.js，使用相邻 node.exe 或 PATH 的 Node 直接启动，不解释 shell 包装脚本或回退到其他 Codex 安装。连接结束关闭标准输入，让 proxy 和 Node 正常退出，超时只结束自身子进程。
- thread/list 遍历全部分页，显式全部公开 sourceKinds、modelProviders=[]、archived=false/true、useStateDbOnly=true。按房间规范路径匹配返回元数据，不因上游精确 cwd 字符串漏掉 Windows 等价路径；不扩展符号链接或子目录。
- GET session 返回名称、原会话 ID、provider、presence、observedAt、archived、memberId；已加入与归档标明，不自动变更归档或按忙闲隐藏。
- POST member 仅接受 sessionId/name/topicIds。先校验资源，事务外 thread/read(includeTurns=false) 核验原 ID/cwd/provider，再写事务复核名称/会话唯一性和订阅，原子保存 Session/Member，返回 201。外部错误 503、重复 409、跨目录/订阅无效 422；失败不部分落库。
- 直接移除 operationId 创建协议、创建状态 UI、后台创建、身份注入与会话重命名。SQLite schema 3 删除废弃创建操作和托管索引/列，保留资源、已绑定成员和消息；没有旧业务接口兼容。
- 前端恢复 Reka 单选和清空、刷新、加载/错误/空态、重复禁选；字段级必选校验与其他表单错误独立，刷新失效选择清空。编辑名称只改成员业务字段。

## Implementation outline / 实施安排

1. 同步总意图/总计划和 T04/T05/T07/T09/T10/T11/T12 的受影响前提。
2. 替换驱动和绑定用例，清理旧创建代码/配置/API/测试，保留持久存储与路由。
3. 恢复 Web 会话选择，移除创建操作状态和找回逻辑。
4. 运行现有后端/Web 检查及真实只读烟测，核验完整目标台账和本地链接。

## Checks and risks / 检查与风险

- 真实 WebSocket 子进程夹具校验分页、来源/provider/归档参数及只读方法；覆盖错误、超时、异常游标不返回部分成功与连接回收。
- 绑定测试覆盖 Windows 路径规范、POSIX 大小写、子目录/其他项目拒绝、重复/并发唯一性、失败回滚、空列表/上游失败、重启原绑定和错误契约。
- Web 轻量测试覆盖单选载荷、字段错误、已加入禁选、加载/空态/失败、手动刷新与编辑；不增加复杂整页生命周期测试。
- 真实烟测只读用户会话元数据，所有成员/房间写入临时 Relay DB，新进程核验同一原 ID；不向用户会话发消息或更改其配置/历史。
- 列表取当前 Codex 环境的状态库可见记录；额外宿主仍归 T12。已有会话的显式发布入口归 T05 待核验，发现/绑定通过不等于真实入队和发布已交付。

## Reception and progress / 接收与进展

- 2026-11-07 19:41:39：沿用 T02-20261107-01 收到移除角色及参考迁移实现要求，accepted → running；修订 10 保留既有职责和目标，按用户后续反馈撤去包内迁移目录、旧库接入参数及新增反向用例。

- 2026-11-07 19:01:08：用户“刷新会话出错，自己看日志”；/root 沿用 T02-20261107-01，accepted → running。日志确认默认 codex 解析为 npm codex.cmd 后被驱动拒绝；修复官方 npm 入口的直接启动，保留原生命令/显式 Node 命令。补回归测试并以默认配置复验运行中后端和 Web 代理，不更改用户会话。
- 2026-11-07 16:29:56：用户“纠偏”；/root 沿用原编号，T02 accepted → running。持久存储部分保留，强制新建方案撤回，受影响下游不派发。

## Delivery and review / 交付与审查

- 2026-11-07 19:46:18：修订 10 沿用 /root、T02-20261107-01，基线 2cc4933 + 工作区 diff，无 Git 提交。角色从模型、服务、请求、表单、缓存和有效文档契约删除；成员选择项只展示会话名称、ID 和事实标识。
- 迁移按 K12 拆为根目录 alembic.ini、migrations/sqlite/versions 和 sql/，独立 migrate 命令执行 upgrade head；Make/容器先迁移再启动。SQLiteRoomStore 只检查 revision 并处理数据事务，业务数据访问保留 sqlite3。包内迁移目录和旧库接入参数均撤掉；不保留迁移功能单元测试，也不以新增集成测试替代。
- 实际本地开发库已完成离线框架切换，完整资源行前后比较一致；1 房间、1 话题及其余空资源表保留，head 为 remove_member_role，外键检查为空。之后以最终显式 CLI 执行 head 成功。[执行记录](../../design/evidence/20261107-t02-migration.json)。
- 最终开发检查：Mypy 40 个源文件，Ruff check/format 66 个文件；Web typecheck/lint/format/build 均通过。按用户要求仅运行正常业务流程选择：后端 8 项（跨进程保存、跨实例提交、发布序号、成员添加/编辑与配置），前端 3 项（添加/编辑成员及话题选项），均通过；不声称当前全量测试通过。新增反向用例与全部迁移功能用例已移除。
- 最终默认命令只读烟测找到 2 个本项目会话；临时 Relay 库原绑定、加入标记和新进程原绑定通过。仅 initialize/thread/list/thread/read，模型消息、创建和恢复均为 0。[证据](../../design/evidence/20261107-t02-existing-session.json) 对应当前源码指纹。原 style.css SHA256 保持不变。
- 主会话按实际变更、检查及证据复核，running → submitted → accepted；其他任务和整体 Verification 不推进。当前 9080/9081 无监听，未另启服务做 HTTP 复验；未运行 Docker 构建。

- 2026-11-07 19:05:29：/root 沿用 T02-20261107-01 完成刷新失败修复，基线仍为 2cc4933 + 当前工作区，无 Git 提交。日志中两次 503（req_57fe384885204ef3a400f5c190847644、req_6c2272807a4f4a7b986423b1413b909b）均来自驱动拒绝默认命令解析得到的 codex.cmd；此前烟测指定原生绝对路径，漏验默认启动方式。
- 启动修复：官方 npm codex.cmd/codex.ps1 通过同一安装的 codex.js 与 Node 直接启动，不经 shell；保留原参数、原生命令和显式 Node 入口，安装不完整时明确失败。关闭 WebSocket 和标准输入后等待 proxy/Node 正常退出，避免立即终止 Node 或等到强制结束。回归覆盖路径空格/特殊参数、相邻/PATH Node、原生/显式 Node、相对路径、缺失依赖及正常退出。
- 开发检查通过（根目录）：`uv run --locked --no-sync pytest -q` 为 107 项；`uv run --locked --no-sync mypy src tests` 为 37 个 source files；`uv run --locked --no-sync ruff check .`、`uv run --locked --no-sync ruff format --check .` 为 59 files。无 Web 代码改动，本次不重复前端检查。
- 默认配置真实复验：后端 `http://127.0.0.1:9080/api/room/room-af9aa6f789aa/session` 返回 200（req_85caa50a5df540b9a9e9f5baf2237505），Web 代理 `http://localhost:9081/api/room/room-af9aa6f789aa/session` 返回 200（req_0d9ae0b3d2c54a1992541cac41de2405）。均找到“提交代码”“梳理项目现状并推进实现”2 条本项目会话；最新日志无此失败链，请求结束后无残留 app-server proxy。
- 重新运行 `uv run --locked --no-sync python scripts/probes/member_session_smoke.py --output docs/design/evidence/20261107-t02-existing-session.json`，未传 --codex。证据已更新为当前源码指纹，configuredCommandUsed/defaultCodexCommandUsed 均为 true；原会话绑定、重复拒绝、加入标记与新进程原绑定通过。仅 initialize/thread/list/thread/read，全部写入临时 Relay DB，未投递消息或修改用户会话。
- 主会话核对实际源码、开发检查、真实 HTTP 日志及默认烟测后，running → submitted → accepted；不推进 T03 或整体 Verification。此前前端及其样式保持原状，未运行 Docker 或模型调用。

- 2026-11-07 16:39:33：/root 沿用 T02-20261107-01 完成修订 9。基线 2cc4933 + 当前工作区 diff，无 Git 提交；状态 running → submitted，经实际源码、检查及证据复核后 accepted。
- 实际变更：member_sessions.py 提供只读发现/核验及原子绑定；CodexDriver 通过原生共享 daemon proxy 读取全部来源/provider/归档分页；恢复 Reka 会话单选、已加入禁选、加载/空态/错误/刷新和字段校验。删除后台新建/创建操作 API、独立运行时锁/进程树管理、自动 resume、身份注入/重命名与创建状态 UI。
- 持久记录：SQLite schema 3 移除旧创建操作及托管字段，保留已绑定成员和消息；测试验证旧结构迁移、事务失败回滚、并发同会话仅一个成员、重启保持原 ID。既有路由/订阅约束继续通过。
- 开发检查：后端 Mypy（37 个 source files）、Ruff check/format（59 files）、pytest 97 项通过；Web typecheck/lint/format、17 文件 56 项测试及 production build 通过，测试无警告输出。当前 PowerShell 未提供 make，使用 Makefile 对应工具命令。
- 真实烟测：[脚本](../../../scripts/probes/member_session_smoke.py)、[脱敏证据](../../design/evidence/20261107-t02-existing-session.json)。当前目录找到 2 条会话；临时 Relay 库加入原 ID、重复加入拒绝、刷新标明已加入，新进程仍为同一原绑定。仅 initialize/thread/list/thread/read，创建/恢复/提交消息均为 0；元数据源包含 284 条但只返回匹配目录的候选。
- 原始 style.css SHA256 仍为 DF4914CC319D7E3ECF1A58CC49088AAB44BDC3FF41513322BA1D6804C490C9E5。Web 样式未被本次纠偏覆盖。
- 限制与未运行：没有浏览器整页端到端、Docker 构建或真实 queue/模型调用。本交付仅接受 T02 纠偏；T04 原会话 queue 与 T05/T07 已有会话的显式入口仍按各自方案核验。整体 Verification 未启动。
- HTTP 契约复核：201/422/404/409/503、统一 code/error/requestId、5xx 不泄露上游 cause 已覆盖；未新增认证、限流或网关 owner，不扩大相应产品范围。

- 2026-11-07 16:41:48：文档与交付证据复核通过：18 份文档、83 个本地链接/锚点，17 目标、18 验收、12 任务修订 9、31 条 DAG 边一致且无环；本次烟测源文件指纹匹配，原 style.css 未变，git diff --check 通过。

## 历史交付（修订 7—8，旧创建主路径已撤回）

以下为先前实际工作记录，不能覆盖当前纠偏契约；旧 managed-session 证据仅说明当时的隔离创建/恢复能力。

### 先前交付记录

前次存储部分交付见以下历史记录。本次完成成员创建操作、原生 app-server 驱动、原会话恢复及必要 Web 同步；T02 当前交付 accepted，后续任务仍按独立范围交付。

- 实际版本：基线 `2cc4933` + 当前工作区 diff，无 Git 提交。新增 room_store.py / room_state.py、独立测试夹具与存储测试；集中数据库配置并接入应用，演示资源全部移入测试。既有 style.css SHA256 `DF4914CC319D7E3ECF1A58CC49088AAB44BDC3FF41513322BA1D6804C490C9E5` 不变。
- 数据库 schema 1。同一同步用例事务读取当前库，按变化保存实体；房间路径、成员名称/会话、话题名称、消息序号和逐成员投递有唯一约束；订阅与投递关联有同房间外键。现有显式目标/实际接收人按发布时 DTO 快照保存。
- 正式应用从空库启动，可创建房间/话题并重启查询；不会制造候选会话。目前成员创建/发送的完整用户流程仍待真实会话运行时接入。测试里的会话和成员来源明确为夹具，不作为产品接入证据。
- 新投递仅 pending，Web 增加“待提交”及原有秒级时间显示，统计增加 pendingCount；不按 presence 制造已入队记录。真实状态机与凭证由 T04 接入，旧状态兼容由 T09 清理。
- Docker 两个构建文件创建可写 data 目录；README 加数据库设置和持久卷示例，构建上下文排除 data。未运行 Docker 构建或容器检查。
- 开发检查：`uv run --locked --no-sync mypy src tests`、`ruff check .`、`ruff format --check .` 通过；`pytest -q` 为 78 项通过。web 下 `corepack yarn typecheck`、`lint`、`format` 通过，`test --reporter=default --silent=false --no-color` 为 17 文件/52 项通过。
- 覆盖证据：[存储测试](../../../tests/test_room_store.py)验证真实新进程重启、两个已创建应用读到彼此提交、12 条并发发送序号不重不丢、规范路径并发冲突、写入 Delivery 时失败回滚资源/订阅/消息、跨房间外键、并发及重复迁移、未知 schema 不重置库。原 API 路由测试继续验证无效目标拒绝和历史路由不被订阅编辑改写。
- 限制：当前事务承接全量快照接口，加载全部房间数据；规模化查询与分页尚未交付。发布键、事件、投递领取/凭证均未实现，不宣称完整 T03/T04。数据库备份恢复、输出观察仍后置。
- 仲裁：主会话已核对上述实际改动与检查，接受本次存储部分；当前授权和 T02-20261107-01 继续有效，下一步补会话运行时及成员创建操作。

### 本次存储局部方案

- SQLite schema 1：rooms、topics、sessions、members、member_topics、messages、deliveries。资源身份/唯一性/同房间外键由数据库约束；非索引 DTO 字段保存 JSON，消息显式目标和历史接收人保存发布时快照。不是整房间单 JSON 持久化。
- 每次同步用例一个数据库事务；写操作 BEGIN IMMEDIATE，从当前库加载，再只写变化的实体。连接随操作关闭；迁移同样加写锁和显式关闭，无常驻连接需要 lifespan 清理。当前全量读取承接旧快照接口，有界查询优化保留 T08。
- Settings.database.path 集中配置文件位置；初始化失败直接失败，不删除或重建损坏/未知版本库。生产不含演示资源，测试显式注入夹具和临时文件库。
- 新投递均 pending，页面显示“待提交”；不声称有真实入队回执。旧 delivered/queued 字段兼容留待 T04/T09 正式状态替换。
- 检查覆盖跨实例/进程重启、并发迁移及写入、事务中途失败回滚、唯一约束和跨房间外键、订阅变化不改历史、独立测试数据库。

- 2026-11-07 14:42:53：Web `corepack yarn build`（web 工作目录、项目指定 Yarn）通过。文档检查通过：18 份文档、78 个本地链接/锚点、17 目标、18 验收、12 任务修订 7、31 条 DAG 边一致且无环。`git diff --check` 通过；未执行 Docker 构建、真实 Codex 会话创建或入队验证。

### 本次会话局部方案与接收

- 2026-11-07 14:52:21：/root 沿用 T02-20261107-01 接收修订 8。授权为“继续”及“不做兼容或适配”；按总计划修订 8 替换旧成员创建契约，删除候选会话接口，Web 同步必要入口。
- 创建操作先持久化，随后服务线程池执行；操作键按房间唯一，参数规范化指纹校验，未决操作保留成员名称；已拒绝操作可另发新操作，同一操作从不重新 start。
- 管理会话驱动为独立 stdio JSON-RPC 进程，支持并发请求关联、服务端工具回调及无处理器显式失败；进程/连接错误唤醒所有等待者，关闭回收自有进程和线程。
- 数据库迁移 1→2 无旧请求/旧会话接入兼容分支；schema 迁移保存用户已有资源数据。session 记录托管标记、工具指纹、连接结果与观察时间；provisioning/ready/rejected/unknown 独立于成员忙闲和投递状态。
- 应用 lifespan 恢复已记录 thread，校验原身份/cwd/provider/工具清单，绝不创建替代会话或主动 queue/start。当前没有创建过托管数据时不启动 Codex。关闭等待创建任务收尾并退出自有进程，连接状态保存为断开。
- 检查：创建前记录可见、重复/冲突、无效/跨房间订阅、明确拒绝/未知、响应后绑定落库失败、HTTP 断开、进程退出、原会话恢复、工具清单/上下文不一致、运行时独占、RPC 回调/乱序响应/超时及应用关闭。

### 本次完整交付与审查

- 版本：基线 `2cc4933` + 当前工作区，无 Git 提交；当前执行编号 T02-20261107-01。源代码、测试及本次真实证据可核对。
- 新增 `managed_members.py` 管理持久创建操作、`drivers/codex.py` 原生 stdio JSON-RPC 与工具注册表，`runtime_lock.py` 保证同一库只有一个托管运行时，`process_scope.py` 关闭自有进程树。应用 lifespan 恢复和关闭自有会话运行时，空库不创建 Codex 进程。
- SQLite schema 2：增加创建操作与托管 thread 唯一性。创建记录先提交，再执行外部请求；得到 thread ID 后先存入原操作，再初始化身份上下文，最终原子保存 Session/Member/ready。已明确拒绝才标 rejected；请求、初始化或最终本地提交不明均 unknown，不另建。创建中断在下次获得运行时所有权后标 unknown。
- 原生创建契约为 thread/start（ephemeral=false）、thread/inject_items（成员身份初始化上下文）、thread/name/set（成员名称）。本机构建只得到 start 回应不足以证明空历史可恢复；初始化上下文持久化后已实测新进程恢复同一 thread。初始化不创建 turn、不 queue/add、不触发模型推理，初始化文本也不作为房间消息路由。没有通过旧格式兼容或宿主适配替代。
- 重启先 thread/read 验证持久元数据，再 thread/resume 原 thread；cwd/provider/工具指纹失败保留原绑定和安全诊断。会话连接状态与来源时间独立保存，不能当入队回执。关闭或断连更新连接事实。当前工具注册表为空；未来工具定义/处理器与已有会话工具变化由 T05/T07 落实，不宣称已具备成员发布。
- 删除候选会话 HTTP 接口和旧 sessionId 创建格式；POST /member 直接接受 operationId/name/role/topicIds 并返回 202 操作，GET /member-operation/{id} 找回结果。同键参数冲突 409；运行时占用 503，均沿用 code/error/requestId，不泄露原始上游错误。
- Web 删除会话选择，使用稳定操作键；请求响应不明时只查询同一次操作，不重发创建。未完成操作从房间快照显示并带秒级时间，刷新后仍可见。原 API 错误归一化沿用，409 不转换成“查询旧结果成功”。T09 的分页/事件/完整状态等其他目标未因此交付。
- 检查通过：后端 Mypy/Ruff/格式，107 项 pytest；前端 typecheck/lint/format，17 文件 56 项测试及 production build。新增测试覆盖 RPC 乱序/回调/超时/退出、自有子进程回收、持久操作重放/冲突、明确拒绝/未知、绑定提交失败、初始化失败、HTTP 客户端关闭、原会话恢复和不匹配、运行时互斥及 503 契约、表单稳定操作键和响应丢失找回。
- 真实检查：旧产品烟测脚本 `scripts/probes/managed_session_smoke.py`（已移除）与[脱敏证据](../../design/evidence/20261107-t02-managed-session.json)。本机原生 Codex 0.167.0，新建测试工作区和测试 thread；关闭第一进程后由第二进程恢复原 ID，queue/list 为空，无推理和业务消息，测试 thread 已归档，自有进程均退出。未触碰已有工作会话。
- HTTP 错误契约按 check-http-error-contract skill 检查：新入口的 422/404/409/503 与 requestId/安全摘要通过；异步创建失败属于 GET 可查询的操作结果，不伪装为 HTTP 层已创建成员。鉴权、限流及外部网关不在本次新增 owner 范围，未新增相应策略。
- 仲裁：主会话核对实现、开发检查、真实证据和边界后接受 T02 当前交付。后续 T03 负责发布幂等/原子事件/结果找回，T04 负责真实 queue；无自动超时重发、输出观察、备份恢复或成员执行策略。

- 2026-11-07 15:29:16：最终文档/证据检查通过：18 文档、82 个本地链接与锚点、17 目标、18 验收、12 任务修订 8、31 条 DAG 边一致且无环；真实证据断言和对应源文件指纹一致。既有 style.css 指纹不变，git diff --check 通过；未创建提交或运行 Docker 构建。

- 用户追加明确：不为数据迁移功能做单元测试。已删除迁移功能测试，不以新增集成测试替代；业务测试中的数据库初始化仅为测试准备。迁移结果核对使用本次实际本地执行记录。
