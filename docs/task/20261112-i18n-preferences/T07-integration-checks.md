# Task / 子任务 T07：集成核对、开发检查与使用说明
最后修改时间: 2026-11-13 10:10:50

## Review status / 审查状态

Accepted

局部方案随父级 Plan 修订 2 接受；等待前置交付后分配。本任务属于 Implementation 收口，不代替整体 Verification。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T07；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`。

## Goal and acceptance / 目标与验收

对齐所有开发交付、检查与使用说明，覆盖 A01–A09，形成可进入整体 Verification 的实现摘要。

- 核对实际 diff 中配置、偏好服务、HTTP、页面、错误与桌面是一套一致契约。
- 运行必要开发检查，修复既定方案内的集成缺陷并复验，不重复扩大无关测试。
- 文档说明语言默认／覆盖／系统判定、应用菜单入口、保存位置和首期原文边界；独立设置页为后续 TODO。
- 对真实 GUI、英文布局和冻结制品保留明确的已验证／未验证事实；未获整体授权时不宣布 Verification 完成。

## Scope and files / 范围与文件

- 集成版本的实际 diff、A01–A09 检查矩阵、各 task 交付证据。
- `README.md`、`docs/guide/windows-desktop.md`、`docs/design/terminology.md` 中与本功能直接相关的说明。
- 本文的接收／交付；所属产品文件如需修复，先由主会话明确责任和写入范围，并同步对应 task 版本。
- 主会话负责总计划登记，不由其他执行者自行修改审查结论。
- 不新增集成测试框架／smoke 脚本、不操作真实用户数据库／偏好，不触发 GitHub Actions 或真实 Codex 投递，不做 Git 提交。

## Inputs / 输入

- 直接前置 T05、T06 的交付均由主会话接受，实际版本可访问且已经合并为同一代码状态。
- T05 包含 T03／T04，T06 包含 T02／T01；核对最终修订和上游没有在已接受后发生未经复核的变化。
- 使用总计划的接口、DAG、文件安排和检查矩阵，不把本文变成补做设计调查的节点。

## Technical decisions / 局部技术设计

- 核对配置默认／用户覆盖／系统快照优先级只由应用服务决定；网页使用 resolvedLanguage，原生窗口使用同一服务，language 策略不被解析值替代。
- 核对偏好只写用户 JSON，不写安装 YAML／`.env`／localStorage／数据库；新增业务 code 不改变 HTTP 状态和错误结构。
- 核对 MessageDescriptor 和词典的一致性，以及固定用户身份、业务数据／原始诊断边界，不以“所有文本都必须英文”误改内容。
- 核对打开菜单、切换语言期间普通草稿、在途结果、待确认 publication 和订阅保持；独立设置页启用时再核对其往返生命周期。
- 开发检查复用 `make check`、`make test`、前端 production build；不新增“为验证而运行产品”的开关或后门。
- 文档明确当前 scope：系统指本机 Relay 用户的显示语言，进程启动重判；`system/zh-CN/en`，偏好文件位置，保存后立即生效；CLI 全量翻译和历史诊断迁移未纳入。
- 实现后具备环境时按授权观察 Web／源码桌面与英文布局；需启动窗口／构建制品且超出有效授权时仅登记未运行，不虚构结果或自行扩展阶段。
- 所有修复必须归属原 task，由主会话决定需返工的交付状态／执行者，修复后记录新版本和受影响下游复核。

## Implementation outline / 实施安排

1. 核对前置版本、工作区已有修改和最终 diff，建立 A01–A09 对应的开发证据清单。
2. 执行定向缺口检查、词典完整性、现有全量检查和前端构建；修复并复验相关问题。
3. 补充 README、桌面指南和固定用户显示术语，核对无新增启动参数及资源遗漏。
4. 输出实际变更、检查、风险、未验证项和 task 记录位置，供主会话进行 Implementation 交付审查。

## Checks and risks / 检查与风险

- `make check`：Python mypy／Ruff／format、前端 typecheck／lint／format，使用现有入口，不引入新检查体系。
- `make test`：Python 与前端现有单元；语言读写只用临时用户目录，GUI／Codex 采用 fake。
- 在 `web/` 运行 `corepack.cmd pnpm build`，检查两份词典随资源构建，以及 `/settings` 重定向首页。
- 核对默认 YAML 仍由现有 packaging spec 带入制品，Python 原生词典为正常 import，无额外资源文件遗漏。
- 确认 CLI／MCP 的结构与非桌面导入边界回归；可运行既有纯单元与无网络 `--help`，不新增语言参数或联网依赖。
- 英文布局、Windows 真正显示语言、源码窗口及冻结包如未观察，单列环境与解除条件，不将编译／fake 检查当作运行通过。
- 本 task 不生成已通过的 Verification 文档或 commit message；整体阶段在有效授权后由主会话进行。

## Handoff basis / 交接依据

- 未分配；无有效分配编号或 Implementation／Verification 授权。
- 协议入口、审查与返工规则见总计划“协调信息”和 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时记录 T05／T06 集成版本和实际修改清单。
- 可写回报位置：本文“接收与进展”“交付与审查”；默认由用户转交可复制摘要，主会话核对后同步总计划。

## Reception and progress / 接收与进展

2026-11-13 10:05:57：执行者 `independent-20261112-225606` 接收 `T07-20261113-100557`，方案修订 4。基线为 HEAD `e57ede1` 加已接受 T01–T06 工作区文件。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:36:25 | 无 / 无 | 已记录方案，等待 T05／T06 集成交付和授权 | 本文与总计划 |
| 2026-11-13 10:05:57 | T07-20261113-100557 / independent-20261112-225606 | 集成核对、全量检查和验证文档收口 | 后端 327 项、前端 76 项、mypy、Ruff、typecheck、lint、format、build 均通过；详见验证文档 |

## Delivery and review / 交付与审查

- 分配编号 T07-20261113-100557；交付为当前工作区集成版本、README／桌面指南／术语说明中的语言约定与 [整体验证](../verification/20261112-i18n-preferences.md)。
- A01–A09 逐项结果、实际 diff、检查与未验证项见验证文档；本轮修复 T04 测试的类型注解和 T06 桌面语言缺口。
- 全量检查：后端 327 项通过；前端 76 项通过；mypy 178 文件、Ruff、Ruff format、vue-tsc、ESLint（0 error／23 warning）、Prettier、production build 通过。
- 未运行真实 GUI、源码桌面、冻结制品及真实 Codex 投递；构建保留既有大 chunk 警告。无其他范围偏差。
