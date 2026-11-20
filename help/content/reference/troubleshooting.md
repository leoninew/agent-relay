# 附录：运行与排障

## 平台指南

- [Windows 桌面使用指南](./windows.md)
- [macOS 桌面使用指南](./macos.md)

## Codex 与共享 daemon

先在终端确认 `codex --version` 可运行。使用 `codex login status` 检查认证配置，按当前 Codex 的登录提示完成认证；能成功完成一轮简短 Codex 请求才说明凭据和网络都可用。

Conflua 默认通过 `codex app-server proxy` 连接共享 daemon。没有运行时，可用支持该子命令的 Codex 执行 `codex app-server daemon start`，再用 `codex app-server daemon version` 查看运行状态。随后在同一个 daemon 中打开需要加入的 Codex 会话。仅启动 daemon 不会自动加载所有旧会话；Conflua 的「刷新会话」能看到会话可用，才可以继续添加成员。

Agent 要从会话里调用 Conflua，可用包内 CLI，或把同一个 CLI 配成 `mcp` 的 stdio 命令。命令找不到时，按平台指南使用 CLI 的绝对路径；更改服务端口后，CLI 与启动 MCP 的进程要使用对应的 `CONFLUA_URL`。

## 配置和日志在哪里

桌面配置读 `~/.conflua/.env`，应用日志在 `~/.conflua/logs/conflua.log`，数据默认在 `~/.conflua/data/`。`~` 代表当前桌面用户的主目录。先看最近一次启动或该消息发送时间附近的日志；共享诊断前移除账号、路径、消息正文和凭据。

## 按症状恢复

| 症状 | 先做什么 | 恢复标志 |
| --- | --- | --- |
| 应用启动失败或窗口未打开 | 看原生错误及日志；按平台指南检查运行环境、包是否完整。提示端口冲突时给 Conflua 换一个可用的本地端口并重启，同步调整 CLI/MCP 地址。 | 应用打开并能看到聊天室列表；CLI 能连接同一实例。 |
| Codex 未认证，或原会话本身失败 | 检查 `codex login status`，按当前客户端提示完成认证，再回原会话试一轮简短请求。 | 原会话能收到新的模型回复。 |
| daemon 不可用或会话显示「未接入」 | 核对 daemon 正在运行、桌面能找到 Codex、会话在对应工作目录并已在同一共享 daemon 打开；macOS Finder 启动时核对平台指南的命令配置。 | 「刷新会话」后能选到正确会话。 |
| 发送后没回复 | 按[第 5 章](../guide/tracking.md)核对频道、目标和分发；在原 Codex 会话确认是否收到。Agent 只在 Codex 终端回答时，请它用 Conflua 显式发给「你」。 | 原消息有正确的分发证据，且时间线出现相关业务回复；不能只看队列为空。 |
