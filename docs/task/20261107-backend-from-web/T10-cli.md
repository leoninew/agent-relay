# Task / 子任务 T10：Relay HTTP CLI 客户端
最后修改时间: 2026-11-08 16:25:58

## Review status / 审查状态

Accepted，方案修订 22。用户明确“cli 用 click”，入口 `agent-relay` 改用 Click 声明命令，HTTP 仍使用标准库 urllib；命令成功/失败结果输出稳定 JSON，`--help` 使用普通帮助文本。Click 列为直接依赖，复用锁内已有版本。

成员入口沿用项目目录会话发现、选择和持久绑定；没有 operationId 创建/结果查询协议。Relay CLI 只调用本机 HTTP 服务，不直连数据库或 Codex，不自动新建、恢复或关闭成员宿主。

## Parent and authority / 父任务与权威记录

- [总意图](../../intent/20261107-backend-from-web.md)、[权威总计划](../../plan/20261107-backend-from-web.md)。任务 ID：T10；当前 T10-20261108-N6，修订 22 Click 与零订阅交付 Accepted；修订 13 既有 CLI 交付保留。
- 协调根：`D:/SourceCodes/mywork/agent-relay`；任务定义及执行登记见总计划。

## Goal and acceptance / 目标与验收

G15，对应 A03、A15：CLI 与 Web 共享 Relay 的持久事实，覆盖资源管理、发布、结果找回与查询，网络/等待/取消不悄悄改写投递事实或重发。

## 本批与后续交付

修订 21 N6 与修订 22 Click 技术修正已交付：member add/update 的 --topic-id 可省略，不传时请求明确带 topicIds=[]；重复传入仍表示多个订阅。同步 T02 资源响应、服务端规则、帮助和正常流程检查；此前命令及客户端职责不变。

交付完整 HTTP 客户端。资源管理覆盖现有 API 的创建/读取/编辑/删除，发布、找回、历史页、单条、事件和投递查询复用 T02/T03/T08。成员命令与服务端使用同一规则，N6 同步已接受的零订阅契约。CLI 控制台发布身份为控制台，不等于 T05 的路径指定成员发布。

## Scope and files / 范围与文件

`cli.py`、`pyproject.toml` console entry/Click 依赖、锁文件、README/帮助说明和 CLI 测试。使用标准库 HTTP 客户端；不直接写数据库、不直连 Codex 队列、不创建另一套后台调度器。

## Inputs / 输入

见总计划 T10：T02 资源 API、T03 发布幂等、T08 查询/事件契约。本批使用控制台身份；成员自主创建话题/订阅的 D10 取舍不在本批。

## Technical decisions / 局部技术设计

- Click 原生 group/command/option/argument 定义命令，multiple 选项转为请求数组；Context 传递本次 HTTP 客户端，参数错误集中转现有 JSON/退出码，帮助仍由 Click 输出。移除 argparse，不保留双解析入口。
- 服务地址：`--base-url` 覆盖 `AGENT_RELAY_URL`，默认 `http://127.0.0.1:9080`；超时：`--timeout` 覆盖 `AGENT_RELAY_HTTP_TIMEOUT`，默认 10 秒。拒绝 URL 凭据、query 和 fragment。
- 成功输出 `{requestId, data}`；失败输出 `{requestId, error:{code,message,httpStatus?,outcome?}}`。命令结果在 stdout 输出 JSON，失败输出到 stderr；帮助单独输出文本。
- 退出码：0 成功；2 参数/配置错误；3 Relay 4xx 或本地记录未找到；4 Relay 5xx/重定向/响应格式不符；5 网络/超时；130 HTTP 请求被用户中断。
- 对写请求遇到 5xx、网络中断或用户中断时，`outcome` 为 `unknown`；4xx 为 `rejected`。CLI 不自动重试写请求、不跟随重定向；发布网络结果未知时用原 publicationId 只读找回。
- 命令表：`room list|create|get|metadata|events`；`topic list|create|update|delete`；`member list|sessions|add|update|delete`；`message list|get|publish|publication`；`delivery list|get`。列表/分页参数沿用 API；资源参数使用现有 DTO；发布必须传稳定 `--publication-id`，话题和 @ 分别允许重复传入。
- 成员会话列表/加入/编辑/删除走现有 HTTP API；加入使用明确 sessionId/name/topicIds，不创建成员宿主。N6 按 D04 允许零个或多个订阅，跟随服务端响应更新，无需额外写请求。

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
