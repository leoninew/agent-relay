# Task / 子任务 T01：语言配置与用户偏好基础
最后修改时间: 2026-11-12 21:32:46

## Review status / 审查状态

Draft

局部方案属于父级 Plan 修订 1。未接受、未分配，未授权实施。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T01；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`；依赖、分配与审查只以总计划为准。

## Goal and acceptance / 目标与验收

交付不依赖 HTTP、WebView、数据库或 Codex 的语言偏好基础，对应 A01、A02、A03。

- 配置允许 `system/zh-CN/en`，默认 `system`，无新增启动参数。
- 用户覆盖优先于配置，显式 `system` 与没有用户覆盖不同；解析值不写入文件。
- 系统语言按总计划 D01 判定，中文归简体中文，其他／失败归英文。
- 文件读写、重建服务后的持久化与失败保留行为可独立检查。

## Scope and files / 范围与文件

- `src/agent_relay/bootstrap/settings.py`、`config/config.yaml`、`config/app.yaml`、新 `bootstrap/preferences.py`；必要时复用／补充 `bootstrap/paths.py`。
- 新 `application/dto/preferences.py`、`application/preferences/ports.py`、`service.py` 及包入口。
- 新 `infrastructure/preferences/store.py`、`system_language.py` 及包入口。
- `tests/unit/bootstrap/test_config.py`、偏好配置／服务／存储／系统来源单元测试。
- 不修改 HTTP 路由、桌面启动器、前端、数据库或 Python 依赖；不覆盖已有 `pyproject.toml`、`uv.lock` 暂存修改。

## Inputs / 输入

- 无前置 task；使用总计划 D01／D02 及派发时核对的实际代码基线。
- 复用当前配置的不可变 typed Settings、YAML／`.env`／环境覆盖顺序和 `user_data_root()`，不创建另一套环境变量加载器。
- 需要提供给 T02／T06 的契约在本 task 中实现，不将接口设计留给后续节点。

## Technical decisions / 局部技术设计

- DTO 定义 `LanguagePreference = Literal['system','zh-CN','en']`、`ResolvedLanguage = Literal['zh-CN','en']`、包含 `language/resolvedLanguage` 的结果与只含 language 的更新请求。显式 JSON alias，拒绝更新请求的额外字段。
- 存储端口提供 `load() -> LanguagePreference | None`、`save(language) -> None`；定义 `PreferenceReadError`、`PreferenceWriteError`，不携带对外暴露的文件路径。
- 服务接收配置默认策略、存储端口和进程系统语言快照；`get()` 每次读取文件覆盖，`update()` 完成写入后再返回有效结果。读取失败不伪装成无覆盖，写失败不更新有效值。
- 工厂从 `Settings.preferences` 和注入的 `user_root` 装配；默认用户根为 `~/.agent-relay`，文件名固定 `preferences.json`。应用／基础设施不反向导入 bootstrap。
- Windows 适配使用用户 UI language，中文主语言覆盖各区域；非 Windows 按 D01 的环境顺序规范化。识别只发生在工厂创建进程实例时，失败归英文并记录诊断；OS 接口和环境可替换。
- 文件格式只有 language。缺文件返回 None；损坏或非法结构记录警告并返回 None，不改写文件；读权限／I/O 失败转为读异常。
- 临时文件建立在目标同目录，完整写入后原子替换；同一实例用锁保护写操作，失败只清理本次临时文件。跨进程不做实时同步或分布式锁，每次 load 读取当前有效文件。

## Implementation outline / 实施安排

1. 增加策略类型与配置默认值，覆盖旧配置缺省和非法值的行为。
2. 实现系统来源适配与归一规则，产出可注入的进程语言快照。
3. 实现文件适配、应用服务和 bootstrap 工厂；明确读／写失败的异常边界。
4. 在临时用户目录和替身 OS 中完成检查，交付 DTO、异常、工厂签名和可访问版本供 T02 消费。

## Checks and risks / 检查与风险

- Python 定向单元：配置三值及非法值、已保存 system 覆盖固定配置、缺文件、乱码／损坏／额外字段、原子替换失败、权限失败、重新创建服务读回。
- 系统用例：`zh-CN`、`zh-TW`、`zh-HK`、`zh_Hans_CN`、`zh_CN.UTF-8`、英文／日文、`C/POSIX`、未知及 OS 调用异常；首选非中文时不因其他来源中文而覆盖。
- 使用 `tmp_path`、fake／monkeypatch，不读写真实用户偏好，不建立数据库或启动任何服务。
- 定向运行新增单元，按实际文件运行 mypy／Ruff／format；最终全量入口由 T07 汇总。
- 风险是误用区域格式、把 `system` 解析结果持久化或读取时覆盖损坏文件；必须提供行为证据。

## Handoff basis / 交接依据

- 未分配；无有效分配编号、执行者或 Implementation 授权。
- 协议入口：总计划“协调信息”中的 SpecFlow SKILL.md 及 `references/task-coordination.md`。
- 工作区参考：`D:\SourceCodes\mywork\agent-relay`，HEAD `3f8097a`；派发时填写真实基线及有效授权。
- 可写回报位置：本文“接收与进展”“交付与审查”；主会话读取本文，默认由用户转交执行者的可复制摘要。
- 不因任务文件存在而自动开始产品修改。

## Reception and progress / 接收与进展

尚无接收记录。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:32:46 | 无 / 无 | 已完成任务方案记录，等待方案接受与实施授权 | 本文与总计划 |

## Delivery and review / 交付与审查

- 尚未交付产品代码；执行者、编号、交付版本和前置核对均未产生。
- 实际变更、逐项验收、检查命令／修复／复验及未完成项在正式交付时填写；当前没有实施检查结果。
- 主会话尚未接受交付，不满足 T02 放行条件。
