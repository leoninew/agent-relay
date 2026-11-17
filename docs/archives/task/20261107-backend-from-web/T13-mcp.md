# Task / 子任务 T13：MCP 客户端入口

最后修改时间: 2026-11-08 22:41:18

## 目标与范围

用户要求“按此提交，然后我们要推进 cli 和 mcp 功能实现”。基线 `e40d313`，编号 T13-20261108-N8，由主会话串行实现，当前 Accepted。[总计划](../../plan/20261107-backend-from-web.md)继续记录其余整体目标。

通过 `agent-relay mcp` 提供 stdio MCP，连接已运行的 Relay HTTP 服务。T10 的共用 client.py 负责 API 映射；MCP 只负责协议、参数 schema、工具说明和结果转换。房间/成员路径为业务上下文，不增加认证或执行权限逻辑。

## 开发任务与结果

| 任务 | 结果 | 状态 |
| --- | --- | --- |
| 共用客户端 | CLI/MCP 复用资源、发布/找回、成员查阅/位置、事件和投递的 HTTP 请求及错误处理 | 完成 |
| stdio 入口 | Click mcp 子命令启动官方 MCP Python SDK，stdout 专用于协议 | 完成 |
| 全部业务工具 | 5 个聊天室、4 个话题、8 个成员、4 个消息、2 个投递工具，共 23 个 | 完成 |
| 类型及结果契约 | 从共用方法签名生成参数 schema；成功返回 requestId/data，错误保留 error/outcome 并标 isError | 完成 |
| 使用说明 | README 列工具、成员身份/发布编号、位置语义及 command/args 配置示例 | 完成 |
| 自动会话身份 | 每次调用从 Codex 请求元数据 threadId 解析房间成员；不读取 MCP 进程继承的父会话环境 | 完成 |
| 协作接入 | make install 发布 Codex 原生 MCP/skill 插件；最小正文投递附带实际发现的 skill | 完成 |

工具完整列表见 README。member_catalog/member_context/member_positions、message_publish/publication_get 根据每次调用的 threadId 自动定位自身成员，schema 不暴露自身成员参数。缺少调用会话时明确报错，不退回控制台身份。话题或 @ 显式选择、并集去重、自身排除、实际接收人非空和事务均由服务端处理。

member_context 保存提供记录并推进位置，member_sessions 保存真实观察，均标为写工具；member_positions 为只读。所有 HTTP 请求不自动重试或跟随重定向；未知发布结果先用原编号和相同成员找回。普通模型输出不会自动进入聊天室。

`plugins/agent-relay/` 同时提供 stdio MCP 声明和唯一的协作 skill 源码。投递正文只有 roomId、发送者和正文，原生 skill 输入引用 Codex 实际发现的插件路径；不传服务地址、命令模板或自身身份。skill 约定认领、实质进展、求助/交接和结果通过显式路由的普通成员消息表达，不引入任务锁或新任务系统。

## 验证

5 项 MCP 正常检查覆盖 typed 工具发现、资源生命周期、零订阅、控制台/成员发布与找回、投递查询、成员查阅和位置。联合 CLI/T05/T07 共 33 项通过；Mypy、Ruff/格式和锁文件检查通过。没有新增反向、故障注入或迁移功能测试。

先前已启动独立临时 HTTP 服务与 stdio MCP 子进程，SDK initialize/list_tools/call_tool、23 工具发现、成员发布/找回/查阅/位置和独立 CLI 读取均通过，当时队列为 fake。

本轮已实际完成 editable CLI 安装与 Codex 原生插件安装、重复刷新，插件 MCP connected 且提供 23 工具；清除探测专用 skill 搜索目录后仍只发现一份正式插件 skill。真实隔离会话验证自动 MCP/CLI 身份、最小消息正文附带已安装 skill、成员调用 MCP 发布认领和进度，目标会话均收到匹配原客户端编号的输入。164 项后端测试、Mypy、Ruff/格式与锁文件检查通过。没有新增反向或迁移功能测试；自有临时服务与会话负责清理，不操作用户开发服务器、原库和工作会话。
