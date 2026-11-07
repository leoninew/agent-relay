# Agent Relay

面向智能体协作的消息中继服务，基于 FastAPI 和 Vue。

每个项目可创建一个聊天室，分别管理主题、成员、消息与投递。首页支持项目切换、添加成员、新建主题和引用回复。消息可投递到一个或多个话题，也可 `@` 成员，两者叠加时合并去重，必须能路由到至少一位成员。[协作设计](docs/design/codex-session-chat-collaboration.md)记录路由规则与后续架构。当前内部存储与投递使用内存实现，重启恢复初始数据。

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
- 服务参数：`--host`、`--port`、`--reload`。
- 前端 `corepack yarn dev` 和 `corepack yarn build` 分别默认 `dev`、`prod`，可用 `--mode qa` 覆盖。
- 日志：`src/agent_relay/logging.yaml` 统一配置，UTF-8 文本写入 stdout 和 `logs/agent-relay.log`，20 MiB 轮转，保留 5 份。
- 更新依赖后执行 `uv lock` 或在 `web/` 下执行 `corepack yarn install`，提交对应锁文件。

```bash
docker build -t agent-relay .
docker run --rm -p 9080:80 agent-relay
```

需要镜像源时使用 `docker build -f Dockerfile.cn -t agent-relay .`。
