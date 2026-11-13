# Task / 子任务 T06：桌面原生提示与语言联动
最后修改时间: 2026-11-13 10:07:54

## Review status / 审查状态

Accepted

局部方案随父级 Plan 修订 2 接受；等待前置交付后分配，实施交付另行审查。

## Parent and authority / 父任务与权威记录

- 总意图：[中英多语言与用户偏好设置](../../intent/20261112-i18n-preferences.md)。
- 权威总计划：[Plan](../../plan/20261112-i18n-preferences.md)；任务 ID：T06；方案修订：1。
- 权威协调根：`D:\SourceCodes\mywork\agent-relay`。

## Goal and acceptance / 目标与验收

交付与页面使用相同偏好的原生提示和新离线通知，对应 A02、A07。

- 设置页保存后，退出确认立即使用当前语言；原生窗口不另做不同语言判定。
- 启动失败阶段也提供本地化摘要／日志路径标签，原始异常保留作诊断。
- 离线通知仅新发布正文按当前语言生成，取消关闭和既有通知／投递规则不变。

## Scope and files / 范围与文件

- `src/agent_relay/bootstrap/desktop.py` 和新 `bootstrap/desktop_messages.py`。
- `application/desktop/service.py` 的显式消息正文参数。
- `tests/unit/bootstrap/test_desktop.py`、`tests/unit/application/test_desktop_exit.py` 和必要原生词典单元。
- 只消费 T02 的 bootstrap HTTP 注入参数，不并发修改 `bootstrap/http.py`、HTTP 异常处理或前端。
- 不新增启动参数、原生 JS bridge、桌面依赖或独立语言资源打包机制；不改历史通知数据。

## Inputs / 输入

- 直接前置 T02：已接受的 `preferences_service` 注入契约和服务实例获取方式；包含 T01 的配置／工厂／系统快照。
- 当前桌面 LocalApiServer 生命周期、关闭确认与 `_publish_exit_notifications` 提交等待边界。
- 当前 `DesktopExitNotificationService.publish(started_at,run_id)` 的幂等标识和通知范围。

## Technical decisions / 局部技术设计

- `run_desktop` 在 active user root／settings 确定后创建偏好服务，将同一对象通过 LocalApiServer 传入 HTTP factory；API 与窗口读到相同策略、系统快照和用户文件。
- `LocalApiServer` 新增可选实例参数并转交 app_factory；缺省保留非桌面调用者行为，相关 fake 签名同步。
- 退出事件每次通过共享服务取当前语言。偏好读取失败时记录日志并回退配置／系统语言，保持仍可确认或取消关闭，不额外终止用户流程。
- 原生词条是 Python 模块中的少量中英静态映射，覆盖退出标题、确认正文、启动失败摘要、日志文件标签和离线通知；不建立后台全业务翻译系统。
- PyWebView 6.2.1 的 WinForms 确认框调用系统 `MessageBoxButtons.OKCancel`；标题／正文按设置翻译，系统按钮保留 Windows 自身语言，不扩展自定义确认窗或 JS bridge。
- main 异常路径在 HTTP／WebView 尚未就绪时，使用能读取的偏好／配置和系统默认解析；任何二次读取失败都不掩盖原异常。既有 stderr／MessageBox 路径保留，原始异常与日志供诊断。
- `_publish_exit_notifications` 显式传入当前语言的 content；应用用例 publish 新增可选 content，缺省仍为原 `OFFLINE_MESSAGE`，不导入 GUI／翻译代码。
- 离线中文“管理端已离线。”，英文“The management app is offline.”。保持请求 ID 生成、目标筛选、正常提交机会及超时／失败继续退出，不等待 Agent 回复。
- Python 词典通过正常 import 自动进入 PyInstaller Analysis；现有 Vue build 继续提供页面资源，不新增 spec 数据项，除非检查发现实际遗漏并按职责回报。

## Implementation outline / 实施安排

1. 共享服务注入桌面与 LocalApiServer，建立原生词典和安全语言读取路径。
2. 本地化退出确认与早期启动失败提示，保留既有错误诊断和资源收尾。
3. 显式传递离线正文到应用用例，不改变范围、幂等或投递控制。
4. 用 fake WebView／server／通知服务检查语言变更及关闭边界，交付与 T05 并行修改的文件清单。

## Checks and risks / 检查与风险

- 同一 fake 偏好服务从中文改为英文后，下一次关闭确认立即使用英文，无需重新创建窗口。
- 覆盖 system 中文／非中文、固定覆盖、读取失败、取消、确认一次、重复 closing 回调和通知异常仍退出。
- 启动配置失败、缺前端资源等异常路径不依赖已启动 API；本地化摘要与原始诊断并存，日志路径正确。
- 离线中文／英文正文、无目标跳过、多房间一次通知、publication ID／目标／超时语义保持；旧默认调用单元仍通过。
- 只使用临时用户根与 fake，不打开真实窗口、不启动真实 Codex、不向聊天室发测试通知。
- 定向运行桌面／应用单元及 mypy／Ruff；真实 WebView／冻结包结果留待实际环境检查并如实记录。

## Handoff basis / 交接依据

- 未分配；无有效分配编号或实施授权。
- 协议入口与回报规则见总计划“协调信息”和 SpecFlow 协作契约。
- 工作区：`D:\SourceCodes\mywork\agent-relay`；派发时填写包含 T01／T02 的已接受版本。
- 可写回报位置：本文“接收与进展”“交付与审查”；默认由用户转交可复制摘要。

## Reception and progress / 接收与进展

2026-11-13 10:05:57：执行者 `independent-20261112-225606` 接收 `T06-20261113-100557`，方案修订 4。基线为 HEAD `e57ede1` 加已接受 T01–T05 工作区文件；T02 偏好注入契约可访问。

| 时间 | 分配编号 / 执行者 | 接收、进展或阻塞 | 证据 / 回报位置 |
| --- | --- | --- | --- |
| 2026-11-12 21:36:25 | 无 / 无 | 已记录方案，等待 T02 交付接受和授权 | 本文与总计划 |
| 2026-11-13 10:05:57 | T06-20261113-100557 / independent-20261112-225606 | 用户确认 i18n 后审查发现桌面原生文案仍为硬编码；补共享偏好实例、原生中英词条、退出确认、启动错误摘要与离线通知 | 当前工作区 `bootstrap/desktop.py`、`bootstrap/desktop_messages.py`、`application/desktop/service.py`；16 项定向 pytest 通过 |

## Delivery and review / 交付与审查

- 分配编号 T06-20261113-100557；方案修订 4；交付为当前工作区上的 `bootstrap/desktop.py`、新增 `bootstrap/desktop_messages.py`、`application/desktop/service.py` 及两份定向测试。
- A02：通过（替身）。`run_desktop` 创建并注入同一偏好服务；关闭确认每次重读，偏好文件从英文改为中文后下一次确认即时使用中文；读取失败回退配置的 `zh-CN`／`system` 解析。
- A07：通过（替身）。fake WebView／通知服务覆盖中英标题正文、取消不通知、确认一次、重复 closing、通知异常仍退出；启动失败摘要保留原始异常并本地化标签；离线中英正文和既有默认正文均验证，不向真实 Agent 发送。
- 检查：`uv run --locked pytest tests/unit/bootstrap/test_desktop.py tests/unit/application/test_desktop_exit.py -q` → 16 passed；全量后端 327 项、mypy、Ruff、format 通过。
- 未验证：真实 PyWebView／WebView2 窗口、Windows 实际显示语言、系统 MessageBox 按钮语言及冻结制品。未完成项无；范围偏差无。
