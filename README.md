# Agent Relay

面向智能体协作的消息中继服务，基于 FastAPI 和 Vue。

每个项目可创建一个聊天室，分别管理话题、成员、消息与投递。首页支持项目切换、添加成员、新建话题和引用回复。消息可投递到一个或多个话题，也可 `@` 成员，两者叠加时合并去重，必须能路由到至少一位成员。[协作设计](docs/design/codex-session-chat-collaboration.md)记录路由规则与后续架构。房间、话题、成员、订阅、消息及投递记录已使用 SQLite 持久保存，重启后保留。新库为空，不自动生成演示房间或会话。添加成员时列出聊天室目录下的已有 Codex 会话，选择后持久保存原会话绑定；真实 queue 提交仍在实现中，当前新投递为“待提交”。

成员发布时排除自己，即使显式 `@` 自己也不创建自身投递；排除后仍须至少有一个实际接收人，否则整条拒绝。[统一术语](docs/design/terminology.md)约定 Topic 为“话题”、Session 为“会话”，Codex Thread 是会话的底层实现。

需要 Python 3.12、uv、Node.js 22+、Corepack、GNU Make 和 Bash。Windows 可使用 Git Bash 或 Cygwin。

## 安装

```bash
make deps
```

前端位于 `web/`，使用项目指定的 Yarn 4。

## 开发

在两个终端分别执行：

```bash
make webapi profile=dev
make web profile=dev
```

- 前端：`http://localhost:9081`，`/api` 请求代理到后端。
- 后端：`http://127.0.0.1:9080`。
- `profile` 默认 `dev`，根目录 `.env.dev` 已启用后端代码重载和前端热更新。

成功返回原始 DTO；失败统一 `{ code, error, requestId }`，校验失败为 `422/validation_error`，未知异常为 `500/internal_error`。前端归一化 HTTP、网络、超时、取消和契约错误，保留请求 ID 与重试提示；重试和鉴权由调用方处理。

## 节点操作

左侧话题和成员节点常规点击只过滤消息；成员按发言人过滤当前话题内的消息，再次点击取消成员筛选，“全部消息”清除筛选。悬停或键盘聚焦显示“编辑”“删除”文字，触屏直接显示操作。编辑在模态窗保存名称、话题说明或成员订阅；删除需在确认窗确认，保留已有消息、身份信息和分发记录，并从后续路由与选择项中移除。删除成员不改变原 Codex 会话。

## 成员会话

打开“添加成员”会查询聊天室项目目录下的真实 Codex 会话；选择会话，再填写成员名称和订阅话题。已加入会话仍显示并标明“已加入”，不可重复添加。加载失败和空列表分别显示，可手动刷新。

- 查询当前运行账户/Codex 环境可见的全部 provider、公开来源与分页，包含未加载历史和归档记录；归档标识不触发取消归档。Windows 路径按大小写/分隔符规范匹配，POSIX 保留大小写，不递归包含子目录。
- `codex.command` 默认 `[codex, app-server, proxy]`，通过公开 proxy 连接共享 daemon。Windows 使用官方 npm 安装时自动通过 Node 启动同一安装下的 Codex 入口，无需另配原生路径；参数按列表传递，不经 shell 执行包装脚本。也可显式指定原生 `codex.exe` 或 Node 入口。
- 配置示例：`AGENT_RELAY_CODEX__COMMAND=["C:/tools/codex.exe", "app-server", "proxy"]`。Codex CLI 与认证由本机环境提供；当前 Docker 示例镜像尚未包含 Codex CLI，也不能直接发现 Windows 宿主会话。
- 加入时仅通过 `thread/read(includeTurns=false)` 核验原会话，再原子保存 Relay 成员和绑定。不会调用 start/resume、重命名或注入会话，也不发起推理。编辑成员名称只修改 Relay 名称。
- 服务重启加载原绑定；会话忙闲来自带观察时间的元数据，不承诺当前可入队。真实 queue 与成员发布/查阅分别由后续任务实现；不扫描普通输出。
- 连接仅覆盖本次元数据请求，结束时回收自己的 proxy 子进程，不关闭共享 daemon 或成员执行宿主。

接口：`GET /api/room/{roomId}/session` 返回真实候选及加入状态；`POST /api/room/{roomId}/member` 接受 `sessionId/name/topicIds`，成功返回 `201 Member`。重复会话或名称返回 `409`，跨项目/无效订阅返回 `422`，元数据服务不可用返回 `503`。移除原 `operationId` 创建流程和创建操作查询，不提供兼容分支。

## 检查

```bash
make check
make check fix=1
make test
```

## 配置与部署

- 默认配置：`config/config.yaml`；环境变量使用 `AGENT_RELAY_` 前缀、`__` 分隔层级。
- 使用 `profile=qa` 读取 `.env.qa`，可从 `.env.example` 复制；前后端使用相同 profile。
- 配置优先级：默认 YAML → `.env.<profile>` → 系统环境变量；读取和校验发生在启动时。
- 直接运行时用 `AGENT_RELAY_PROFILE` 选择 profile，未设置时默认 `prod`。
- 数据库：`database.path` 默认 `./data/agent-relay.sqlite3`，相对路径按服务工作目录解析；可通过 `AGENT_RELAY_DATABASE__PATH` 指定文件路径。使用根目录 `migrations/` 中的 SQL-first Alembic 迁移；`make webapi` 前置执行 `make migrate`。直接启动服务前先运行 `uv run --locked python -m agent_relay.migrate`，应用和存储适配器不执行迁移。详见[迁移说明](migrations/README.md)。
- 服务参数：`--host`、`--port`、`--reload`。
- 前端 `corepack yarn dev` 和 `corepack yarn build` 分别默认 `dev`、`prod`，可用 `--mode qa` 覆盖。
- 日志：`src/agent_relay/logging.yaml` 统一配置，UTF-8 文本写入 stdout 和 `logs/agent-relay.log`，20 MiB 轮转，保留 5 份。
- 更新依赖后执行 `uv lock` 或在 `web/` 下执行 `corepack yarn install`，提交对应锁文件。

```bash
docker build -t agent-relay .
docker run --rm -p 9080:80 -v agent-relay-data:/app/data agent-relay
```

需要镜像源时使用 `docker build -f Dockerfile.cn -t agent-relay .`。
