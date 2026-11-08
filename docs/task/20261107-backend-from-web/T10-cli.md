# Task / 子任务 T10：Relay HTTP CLI 客户端
最后修改时间: 2026-11-08 22:41:18

## Review status / 审查状态

Accepted，当前修订 27、编号 T10-20261108-N8。既有 Click、零订阅与资源响应交付保留；补齐成员发布/找回、目录/上下文/位置命令、CLI/MCP 共用 HTTP 客户端、自动会话身份及 make install 安装入口。

成员入口沿用项目目录会话发现、选择和持久绑定；没有 operationId 创建/结果查询协议。Relay CLI 只调用本机 HTTP 服务，不直连数据库或 Codex，不自动新建、恢复或关闭成员宿主。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T10；当前 T10-20261108-N8，既有交付保留。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；任务定义及执行登记见总计划。

## Goal and acceptance / 目标与验收

G15，对应 A03、A15：CLI 与 Web 共享 Relay 的持久事实，覆盖资源管理、发布、结果找回与查询，网络/等待/取消不悄悄改写投递事实或重发。

## 本批与后续交付

N8 基线为 `e40d313`：message publish/publication 新增 `--as-member`，复用 T05 的成员路径；member 新增 catalog/context/positions，复用 T07。共 23 个业务命令，另有 `mcp` 启动入口。HTTP 地址、请求/响应、错误与不重试规则集中在 client.py，CLI 只负责 Click 参数和输出；旧客户端内部实现直接迁出，不保留兼容别名。成员身份只用于业务路径，控制台默认身份保持。

修订 21 N6 与修订 22 Click 技术修正已交付：member add/update 的 --topic-id 可省略，不传时请求明确带 topicIds=[]；重复传入仍表示多个订阅。同步 T02 资源响应、服务端规则、帮助和正常流程检查；此前命令及客户端职责不变。

资源管理、发布、找回、消息/事件和投递查询复用现有 API；N8 以 `--as-member` 显式选择 T05 成员发布，省略时为控制台。成员上下文与位置使用 T07 的查询及记录规则。

## Scope and files / 范围与文件

`cli.py`、`client.py`、console entry/依赖、README/帮助说明和 CLI 测试。client.py 使用标准库 HTTP；CLI/MCP 共享请求映射，不直接访问数据库或 Codex 队列。

## Inputs / 输入

见总计划 T10：T02 资源 API、T03 发布幂等、T05 成员发布、T07 查阅/位置、T08 查询/事件契约。成员自主治理 D10 的产品取舍不由新增客户端入口改变。

## Technical decisions / 局部技术设计

- Click 原生 group/command/option/argument 定义命令，multiple 选项转为请求数组；Context 传递本次 HTTP 客户端，参数错误集中转现有 JSON/退出码，帮助仍由 Click 输出。移除 argparse，不保留双解析入口。
- 服务地址：`--base-url` 覆盖 `AGENT_RELAY_URL`，默认 `http://127.0.0.1:9080`；超时：`--timeout` 覆盖 `AGENT_RELAY_HTTP_TIMEOUT`，默认 10 秒。拒绝 URL 凭据、query 和 fragment。
- 成功输出 `{requestId, data}`；失败输出 `{requestId, error:{code,message,httpStatus?,outcome?}}`。命令结果在 stdout 输出 JSON，失败输出到 stderr；帮助单独输出文本。
- 退出码：0 成功；2 参数/配置错误；3 Relay 4xx 或本地记录未找到；4 Relay 5xx/重定向/响应格式不符；5 网络/超时；130 HTTP 请求被用户中断。
- 对写请求遇到 5xx、网络中断或用户中断时，`outcome` 为 `unknown`；4xx 为 `rejected`。CLI 不自动重试写请求、不跟随重定向；发布网络结果未知时用原 publicationId 只读找回。
- 命令表：`room list|create|get|metadata|events`；`topic list|create|update|delete`；`member list|sessions|add|update|delete|catalog|context|positions`；`message list|get|publish|publication`；`delivery list|get`；`mcp`。CLI 从 `CODEX_THREAD_ID` 解析当前会话，按房间查询自身成员，发布/找回及自身查阅不必传成员 ID；全局 `--session-id` 可显式配置会话，普通终端仍可使用 `--as-member`。查阅支持单条/话题/字面关键词及单方向游标，位置不表示已读。
- 成员会话列表/加入/编辑/删除走现有 HTTP API；加入使用明确 sessionId/name/topicIds，不创建成员宿主。N6 按 D04 允许零个或多个订阅，跟随服务端响应更新，无需额外写请求。
- `make install` 先预检 Codex 插件，再 editable 安装 CLI、检查帮助，最后通过原生 CLI 刷新 `agent-relay@agent-relay-local`。MCP/skill 共用一份插件源码；不另建独立 skill 镜像。

## Implementation outline / 实施安排

1. 实现单请求 HTTP 客户端与路径/query 编码，保留 requestId、HTTP 错误和写入结果未知语义。
2. 实现命令表中的资源、发布/找回、消息/事件与投递查询，所有业务沿用现有 API。
3. 安装 console entry，更新使用示例；正常流程检查覆盖命令、JSON/成功退出码和投递查询投影；未知结果不重试、错误及取消语义通过实现审查核对，不新增负向测试。

## Checks and risks / 检查与风险

- 命令与 API 的请求映射通过隔离 TestClient/数据库正常流程检查；真实服务仅做只读 CLI 烟测，不向用户数据库或工作会话写测试数据。API 现有回归继续验证服务端行为。
- 检查请求/响应取消与未知结果语义，不新增自动重试或后台等待；没有成员创建 operationId/创建结果等待协议，CLI 不直接拥有 app-server 进程。
- 运行 CLI 与受影响 API 正常流程 pytest、mypy、ruff，以及 console entry help smoke。不为迁移功能写测试；无新增依赖时不改锁文件。
- Web/CLI 命名各异不改变共同事实；CLI 缓存不能成为资源或投递权威。

## Handoff basis / 交接依据

主会话串行实施，不启动子会话。T02/T03/T08 已接受，详细接口见当前 API 和 README；用户“完成后推进下一步实现”授权继续主线 T10。

## Reception and progress / 接收与进展

- 2026-11-08 16:16:12：用户明确 Click；修订 22 技术修正已接受，/root 沿 T10-20261108-N6 实施，既有命令行为与零订阅契约不变。

- 2026-11-08 16:13:00：/root 接收 T10-20261108-N6，基线 a71d186 + 已接受 T02 N6 工作区；沿用户“开始实现”授权同步零订阅参数和资源响应。前置资源/零订阅 43 项相关测试、mypy/Ruff 已通过；CLI 仍仅调用既有 HTTP API，不新增适配或重试。

2026-11-08 10:07:35 接收 T10-20261108-N4。命令、JSON/退出码、地址配置和未知写入语义已在本方案固定，方案 Accepted；从当前工作区的 T02/T03/T08 已接受版本实施。

2026-11-08 10:19:28 实现和开发检查完成，交付当前工作区版本。真实安装入口与正常 API 写/读流程均已核对；未新增负向或迁移功能测试。

## Delivery and review / 交付与审查

### N8 成员命令及共用客户端交付

完成成员身份发布/找回、目录/上下文/位置命令及 HTTP 客户端提取，并更新原运行探测的 import。13 项 CLI 正常检查通过；联合 MCP/成员发布/上下文共 33 项通过，Mypy（src/tests/受影响探测）、Ruff/格式及离线锁检查通过。真实 stdio MCP 写入后，独立 CLI 子进程经临时 HTTP 服务找回同一发布。HTTP/stdio 均已关闭；测试使用 fake 队列，不操作工作会话或开发服务器。

### N6 Click 与零订阅交付

/root，T10-20261108-N6；版本为 a71d186 上当前工作区 cli.py、pyproject.toml、uv.lock、README 与 CLI 测试。按用户要求移除 argparse，20 个子命令改用 Click 原生命令组、选项和位置参数；通过 Context 传递 HTTP 客户端，参数错误仍输出 JSON 和退出码 2，HTTP 错误/中断及不重发语义沿用。Click 声明为直接依赖，锁内 8.5.0 未升级；未安装或升级依赖。

成员加入/编辑允许不传 --topic-id，明确提交空数组，编辑帮助提示会清空订阅；资源写命令直接输出新响应。11 项 CLI 正常流程测试、mypy/Ruff、模块和 console help、离线锁文件一致性检查通过；新增零订阅加入/清空后直接 @ 正常流程。主会话按代码及检查局部接受；未向运行中用户服务发出请求，真实 Codex 与 T11 完整运行验证未重演。

### N4 历史交付

交付编号 T10-20261108-N4，前置为已接受 T02/T03/T08；版本为当时工作区 `src/agent_relay/cli.py`、`pyproject.toml`、`tests/test_cli.py` 及 README，未创建 Git 提交。

- 已交付：5 个命令组/20 个子命令，覆盖既有资源/会话管理、显式路由发布、原编号找回、消息页/单条、事件补取、投递查询；console entry 与 module entry 均可使用。
- 正常检查：10 项 CLI 检查覆盖资源生命周期、三种路由、发布重放/GET 找回、重开存储、分页事件、当前队列回执、配置优先级和 query 编码；联合成员发布/查阅、查询事件和投递回归共 32 passed。命令：`uv run --locked --no-sync pytest tests/test_cli.py tests/test_member_publish.py tests/test_member_context.py tests/test_room_queries.py tests/test_delivery_service.py -q`。
- 静态检查：`uv run --locked --no-sync mypy src tests` 为 57 文件通过；`ruff check .` 和 `ruff format --check .` 为 93 文件通过；`git diff --check` 通过。`uv run --locked --offline agent-relay --help` 只重装本项目；锁文件/依赖未变，module/console help 及真实 HTTP `room list` 只读烟测通过。
- 实现审查：按现有 `{code,error,requestId}` 严格读取 HTTP 错误，格式不符使用安全的 `invalid_response` 并保留状态/header ID；解析参数错误集中输出 JSON。客户端不生成请求 ID、不新增认证边界；服务端状态语义和 writer 继续由现有 API 负责。HTTPException/网络/取消路径保存 unknown，源码无重试循环且禁用重定向。未新增负向测试；这些分支不宣称已运行故障注入。
- 未覆盖/风险：没有重复真实模型或 Codex 入队实测，沿用 T04/T05 证据；业务测试用假队列，仅真实 HTTP 烟测读取用户服务。帮助输出文本；成员至少一个订阅沿用当前 API，零订阅 D04、成员管理 D10、输出观察及 T11 运行交付继续保留。无前端变更，style.css 指纹保持。

2026-11-08 10:19:28 主会话按实际代码和上述证据完成局部审查，running → submitted → accepted；仅接受本批 T10/G15 当前范围，不标记 T11 或整体后端完成。
