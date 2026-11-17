# Task / 子任务 T01：app 配置与资源路径
最后修改时间: 2026-11-12 13:43:01

## Review status / 审查状态

Accepted

## Parent and authority / 父任务与权威记录

- 总意图：[浏览器与 WebView 双模式](../../intent/20261112-webview-desktop.md)。
- 权威总计划：[Plan](../../plan/20261112-webview-desktop.md)，方案修订 2，任务 T01。
- 依赖、分配和审查均以总计划为准，方案状态不表示实现完成。

## Handoff basis / 交接依据

- 当前分配：`WEBVIEW-T01-20261112-01`，执行者为当前架构师会话 (`member-d8bc7b2eec9a`)；当前方案修订 2，沿用有效分配。
- 实施授权：用户消息 `room-94f73433cde7-msg-0119` 授权五项任务开始 Implementation；本 task 限于配置、路径、资源定位及必要单层检查。
- 协议入口：SpecFlow skill 及 `references/task-coordination.md`，位置与仲裁会话见总计划。
- 工作区：`D:\SourceCodes\mywork\agent-relay`，参考基线 `0e12906`；派发时核对实际基线。
- 可写记录：本文“接收与进展”“交付与审查”；回报总计划仲裁会话。

## Goal and acceptance / 目标与验收

交付桌面运行所需的确定配置与路径契约，对应 A02、A03、A08。

- `app` profile 读取 `~/.agent-relay/.env`，覆盖内置默认配置，系统环境变量优先。
- 数据、日志、浏览器配置以用户根目录定位；默认配置、前端和迁移从包资源定位。
- 更换工作目录、继承开发 profile 或合法客户端环境变量，不破坏 app 配置加载。

## Inputs and eligibility / 输入与可开始条件

已核对总计划授权、当前分配和实际基线。输入为现有配置、日志、迁移加载代码及收敛后的评估；无前置 task。

## Scope and files / 范围与文件

- `src/agent_relay/bootstrap/config.py`、`settings.py`、新的路径解析模块和 `logging.py` 必要接线。
- 内置 app 默认配置、`infrastructure/persistence/migrations.py` 的资源定位及相关装配。
- `tests/unit/bootstrap/` 与迁移配置的单层测试；运行说明中的配置契约。
- 不修改已执行的迁移 revision/SQL，不操作现有用户数据库。

## Technical decisions / 局部技术设计

- 桌面调用显式指定 profile 与覆盖文件；独立 server 保留现有 profile 选择方式。
- 用户根为 `Path.home() / ".agent-relay"`，仅使用该目录的 `.env`，不创建 `.env.app`、LocalAppData 或 profile 子目录。
- 内置 app 默认值使用固定端口、关闭 reload，并使新用户数据库能够在服务启动前迁移；覆盖值继续通过统一 typed config 校验。
- 客户端已有 URL、HTTP timeout、session ID 等控制变量从服务字段加载中明确区分，保留真正未知字段报错。
- 将资源根传入 Alembic 配置并显式定位迁移树；通过绝对路径装配，不依靠更改进程工作目录。

## Implementation outline / 实施安排

1. 定义 app 默认配置、用户根、资源根及覆盖优先级，形成供下游使用的 typed 配置/路径契约。
2. 调整配置加载、日志和迁移定位，保持独立 HTTP/CLI 入口行为。
3. 单层验证缺省 `.env`、覆盖顺序、客户端变量、相对路径与冻结资源路径。

## Checks and delivery / 检查与交付

- 定向运行配置与路径单元测试，记录 mypy、Ruff 结果；更改依赖时同步锁文件。
- 交付默认资源清单、加载参数约定和可访问版本，供总计划审查及下游使用。
- 真实新库和冻结包验证在相应后续阶段执行，未运行项如实登记。

## Risks / 风险

缓存配置必须按实际输入区分，避免桌面与 server 混用配置。已复现的客户端变量 `extra_forbidden` 需要回归检查。

## Reception and progress / 接收与进展

| 时间 | 记录 |
| --- | --- |
| 2026-11-12 12:47:45 | 接收 `WEBVIEW-T01-20261112-01`，方案修订 1。执行者：当前架构师会话 (`member-d8bc7b2eec9a`)。授权依据：用户消息 `room-94f73433cde7-msg-0119`。基线：HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea`；工作区含本 SpecFlow 任务文档未跟踪变更，保留不覆盖。无前置 task；范围为 T01 配置、路径、资源定位和必要开发检查。不操作现有用户数据库。 |

## Delivery and review / 交付与审查

- 交付：2026-11-12 12:56，`WEBVIEW-T01-20261112-01`，当前共享工作区；基线 HEAD `0e12906754eb84e9dd0a3c09fd1d9849081fd4ea`，无前置任务。
- 变更：新增 `config/app.yaml` 与 `bootstrap/paths.py`；配置加载可显式固定 app profile、默认 YAML 和用户 `.env`，仅排除已定义的 CLI 客户端变量，仍拒绝未知服务字段。应用相对静态目录解析到资源根、数据库路径解析到 `~/.agent-relay`；冻结资源定位到 `_MEIPASS/resources`。Alembic ini 与 migration tree 由显式资源根确定，不依赖当前工作目录。
- 验收与检查：配置/路径/迁移定向测试 19 项通过；覆盖 app `.env` 与系统环境变量优先级、客户端变量隔离、未知变量拒绝、冻结资源路径，以及临时数据库从非项目 cwd 完整迁移。相关 5 个文件 mypy、Ruff check、Ruff format --check 通过；`git diff --check` 通过。
- 未运行：完整仓库检查及冻结制品 smoke 留待后续集成任务；未操作现有用户数据库。
- 主会话审查：实际 diff 与验收通过，交付接受；放行 T02。

修订 2 更新（2026-11-12 13:43:01）：按用户消息 0123 不保留集成测试；迁移定位检查改为 mock Alembic 调用，断言从无关 cwd 仍配置绝对资源路径，不创建 SQLite。资源根位于中立 `agent_relay/resources.py`。最终全库 259 项单元测试、mypy 及 Ruff 通过，沿用当前分配接受修订后代码；上面的真实迁移记录仅属于中间版本历史。
