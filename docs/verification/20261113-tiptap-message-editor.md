# Verification / 验证：Tiptap 消息编辑器与图片引用

最后修改时间: 2026-11-13 17:02:00

## Scope / 范围

依据用户 `room-a2493e542ba3-msg-0162`、架构师 `0165` 和 [执行计划](../plan/20261113-tiptap-message-editor.md)，完成 W1→W2 的产品代码。用户 `0190` 已反馈“测试无问题”，并要求架构师完成验证及 `best-practices:dev-check`。最终检查已执行；应用项目显式类型检查仍有 14 条既有诊断，不能报告全部质量检查通过。用户没有逐项列举人工测试范围，以下人工清单保留为核对依据，不据此将每个浏览器、WebView 或异常场景标为通过。

用户 `0196` 后续要求给大模型的消息正文使用本地图片地址。本次已增量实现，独立记录于文末“Agent 本地图片地址”；用户 `0190` 的人工反馈不覆盖该后续改动。

原 HEAD 为 `73e0033bad1451d5a43c66f54e47ee7c6075e68e`。开发交付时保留原 14 文件的 Tagify 暂存快照；最终验证开始时用户已统一暂存 37 个文件，工作树没有额外未暂存差异。架构师保持该暂存内容，验证记录与计划更新仅留在工作树，未自动暂存、提交或回退。按用户要求没有新增或运行自动化测试，也没有自动打开浏览器、启动或重启服务器。

## Implementation / 实现事实

- Tiptap core、vue-3、pm、mention、suggestion、extensions 均锁定为 `3.33.1`。实际核对安装源码的 Mention 原子节点、删除行为、Suggestion 默认插件键与 ProseMirror Decoration 映射；Mention 使用显式共用键。删除 Tagify 及其类型依赖、packageExtensions、DOM Range adapter 和自建历史，移除失效实现对应的旧测试部分，保留既有文本识别与剪贴板用例。
- 编辑器只装配单一正文块、Text、保留原始换行的 HardBreak、Skill Mention、图片引用和 UndoRedo；不启用 StarterKit、Markdown input rules 或富文本粘贴。普通输入交给 ProseMirror；源文适配只替换需要转换的引用跨度，不通过 HTML 构造用户正文，也不在普通父模型回写时重建文档。
- Composer 使用 query、insertSkill、dismissQuery、focus 等业务接口。保留 content/capabilities、已绑定 ID、原始 marker、重复引用、身份去重、6000 序列化字符限制、仅 Skill 禁发、输入法与 ready/locked/sending、回复和草稿契约。内部剪贴板按当前目录/已绑定 ID 校验，外部 HTML 的属性不能建立身份，外部复制为可读文本与图片 Markdown。
- 按用户 `0172`，共享查询与 Tiptap matcher 统一复用 `isSkillTriggerPrefix`：`$` 前必须为开头、空白或 Unicode 标点/符号（P/S），普通中英文和数字后不触发。Unicode 正则按码点识别前置符号，包括 emoji；代码/转义排除与词中间查询完整后缀替换保留。仅调整既有断言，没有新增或运行测试。
- 图片使用一个 paste/drop 入口识别实际 image files；普通文字与内部 Skill 剪贴板走正文事务。同批文件并发上传、按添加顺序完成插入，位置来自 `DecorationSet.map`，没有保存上传前的裸字符下标。上传锚点与任务不保存到 content/草稿；取消、清空、删除覆盖锚点、外部正文恢复、冻结或销毁会失效任务。输入法组合期间保留上传结果，结束后重新核对锚点；完成时不聚焦编辑器。
- 上传中禁发，失败在输入处说明，可重新粘贴/拖入。上传完成用 API 返回的 Markdown 作为图片引用标签；标准消息 Markdown 在原位置显示图片，并限制宽高，加载失败显示本地化反馈。没有增加有序附件字段或保存 Tiptap JSON。

## Image API / 图片接口

| 请求                                     | 行为                                                                          |
| ---------------------------------------- | ----------------------------------------------------------------------------- |
| `POST /api/room/{roomId}/image`          | 单文件 multipart 字段 `file`；201 JSON，返回 `id/url/markdown/mediaType/size` |
| `GET /api/room/{roomId}/image/{imageId}` | 直接返回二进制与正确 Content-Type、nosniff、immutable 缓存头                  |

上传首先确认房间存在；实际图片内容由 Pillow 解码核对，接受静态 PNG/JPEG/WebP，每张最大 10 MiB，空内容与格式错误返回 `image_invalid`，超限为 `image_too_large`。错误沿用既有 code/error/requestId 契约。客户端路径和上传文件名都不用于磁盘寻址。

按后续用户 `0218` 授权、架构师 `0220` 交接，存储根目录现为解析后的 `database.path.parent / "rooms"`，由 FileImageStore 集中拼出 `<roomId>/images`，最终文件为 `<database.path.parent>/rooms/<roomId>/images/img-<uuid32>.png/jpg/webp`。开发/桌面继续沿用已解析的数据库持久目录，格式、大小元数据由文件后缀及文件大小读取，不另建消息表附件字段。读取先确认房间存在，并核对 room/image ID，仅在该房间图片目录寻找文件。原 `data/images/<roomId>` 的三张测试原件已一次性复制到新布局，旧件保留，不引入双目录读取或自动文件清理；事实见文末“房间图片目录”。

Python 直接依赖新增 Pillow `>=12,<13`（本次锁定 12.3.0）及 python-multipart `>=0.0.22,<1`（锁定 0.0.33，原为间接依赖）。未运行数据库迁移，未做真实 HTTP 上传或 API 重启验证。已有 API 进程需要由用户重启以加载新增路由。

## Development checks / 开发阶段检查

已执行：

- `corepack.cmd pnpm install`：依赖安装成功。
- `corepack.cmd pnpm typecheck`：原脚本退出成功，但根 tsconfig 只有 references，`vue-tsc --noEmit` 并未有效检查引用项目。补充显式执行 `vue-tsc --noEmit -p tsconfig.app.json`，发现本轮图片 renderer 的 environment 类型过窄，已修复；该检查仍因未改动文件的既有问题失败，见下文。`vue-tsc --noEmit -p tsconfig.node.json` 通过。
- 改动范围 `pnpm exec eslint ...`：0 errors；MessageTimeline 原有 `vue/no-v-html` 1 条 warning，未改为忽略规则。
- 改动范围 `pnpm exec prettier --write ...` 与最终 `--check`：见交付记录。
- `corepack.cmd pnpm build`：通过；保留 Vite 主 chunk 超过 500 kB 的提示。
- `uv sync --group dev`：成功，更新 uv.lock。
- 改动 Python 文件 `uv run ruff check ...`、`ruff format --check ...`、`mypy ...` 和 `python -m compileall -q ...`：通过；mypy 提示既有 dynaconf override 未使用。
- `git diff --check`：通过。

第一轮 W1 构建产物：JS 1,048.99 kB / gzip 344.85 kB，CSS 60.63 kB / gzip 11.67 kB。W2 接通后的一轮构建：JS 1,056.32 kB / gzip 347.25 kB，CSS 61.30 kB / gzip 11.78 kB。这是本轮两个构建阶段的测量；没有重建暂存的 Tagify 基线，不能据此量化相对 Tagify 的包体增量。

开发阶段收尾（含 `0172` 修正）：改动的共享查询、编辑器及既有断言 ESLint 0 errors、0 warnings；应用项目显式类型检查仍为上述未改动文件中的 14 条诊断，本轮编辑器及图片实现文件无诊断。生产构建通过，JS 1,057.05 kB / gzip 347.42 kB，CSS 61.30 kB / gzip 11.78 kB；Vite 大 chunk 提示仍在。改动范围 Prettier 与 `git diff --check` 通过。当时暂存区仍为原 14 文件、1361 insertions / 86 deletions；这是历史交付状态，后续用户已统一暂存。

没有使用 Node 逻辑调用、临时脚本、测试框架或浏览器自动化替代用户要求的人工交互验证。

应用项目显式类型检查的既有失败涉及：AppCheckboxGroup 对泛型组件使用 InstanceType、useStoredOrder 的 ES2023 toSorted/toReversed 与隐式 any、MemberEditDialog 的 nullable 值、api/useRoomCapabilities 使用 Object.hasOwn 的类型库，以及 api/roomApi 测试中的 AxiosAdapter 类型。这些文件相应位置均不属于本次变更；按计划没有顺带修复组件或全局类型工具链。检查不执行测试，且没有将现有脚本的退出成功报告为应用项目完整类型通过。

## Final checks / 架构师最终检查

2026-11-13，依据用户 `0190`，按仓库 Makefile 的 `check` 入口组织检查。本机没有 `make`，逐项执行该入口中的命令；Python 使用 `--locked --no-sync` 保持锁文件与已安装环境，不同步或安装依赖。以下均为只读检查，没有自动修复、格式化或改写配置。

| 目录       | 实际命令                                                        | 结果                                                |
| ---------- | --------------------------------------------------------------- | --------------------------------------------------- |
| 仓库根目录 | `uv run --locked --no-sync mypy src tests`                      | 通过，186 个源文件                                  |
| 仓库根目录 | `uv run --locked --no-sync ruff check .`                        | 通过                                                |
| 仓库根目录 | `uv run --locked --no-sync ruff format --check .`               | 通过，306 个文件已符合格式                          |
| `web`      | `corepack.cmd pnpm run typecheck`                               | 退出成功；根配置仅有 references，未有效覆盖引用项目 |
| `web`      | `corepack.cmd pnpm run lint`                                    | 通过，0 errors、20 warnings                         |
| `web`      | `corepack.cmd pnpm run format`                                  | 通过，仅执行 Prettier 检查                          |
| `web`      | `corepack.cmd pnpm exec vue-tsc --noEmit -p tsconfig.app.json`  | 失败，14 条既有诊断，见下表                         |
| `web`      | `corepack.cmd pnpm exec vue-tsc --noEmit -p tsconfig.node.json` | 通过                                                |
| 仓库根目录 | `git diff --check`                                              | 通过                                                |
| 仓库根目录 | `git diff --cached --check`                                     | 通过                                                |

应用项目的 14 条诊断分布如下。对所有涉及文件执行 `git diff HEAD -- <files>` 无差异，确认其与本轮基线相同；本轮未顺带修复。

| `web` 下文件及位置                                                        | 诊断                                              |
| ------------------------------------------------------------------------- | ------------------------------------------------- |
| `src/components/AppCheckboxGroup.vue:35`                                  | 1 条：泛型组件不能用于当前 `InstanceType` 约束    |
| `src/composables/useStoredOrder.ts:26`、`:27`                             | 3 条：`toSorted` 类型库缺失及两个隐式 any         |
| `src/domains/room/MemberEditDialog.vue:19`                                | 1 条：nullable 字符串                             |
| `src/domains/room/useRoomCapabilities.ts:95`、`src/services/api.ts:43`    | 2 条：`Object.hasOwn` 类型库缺失                  |
| `tests/composables/useStoredOrder.test.ts:46`、`:53`、`:66`、`:70`、`:78` | 5 条：两个隐式 any 及三个 `toReversed` 类型库缺失 |
| `tests/services/api.test.ts:49`、`tests/services/roomApi.test.ts:31`      | 2 条：AxiosAdapter 类型不匹配                     |

ESLint 的 20 条 warning 包括 19 条既有 Vue 模板格式提示（AppLoading、AppToasts、MemberEditDialog、RoomClearDialog、RoomDeleteDialog、RoomSetupDialog），以及 MessageTimeline 的 1 条既有 `vue/no-v-html`。没有扩大忽略规则。

本次未运行自动化测试、生产构建、浏览器或服务器；类型检查中包含测试源文件，不等于执行测试。上节构建结果属于高级开发此前的实现交付证据。

最终核对包含用户后续确认的展示调整：消息图片独占一行并保留正文位置和顺序；输入框、消息及旧引用列表的 Skill 统一为继承正文度量的彩色 icon 与名称；按当前房间 Skill ID 显示 description 提示，空描述回退名称；相关区域使用帮助光标。用户 `0190` 的人工反馈已记录，不扩大解释为全部边界或所有运行环境均已逐项验证。

验证开始时暂存区为 37 文件、2422 insertions / 165 deletions；暂存条目 SHA-256 为 `45C275E4AF42025FF71D670A2B31AAF7CD8F242C1A71EFD8EEAF378E1581665E`。架构师仅更新本文与执行计划，完成后再次核对暂存条目不变。

## Review / 交付审查

架构师 `0171` 完成只读源码核对；两项问题已修复：

- P1（0168→0169）：Mention 默认插件键与 getState/exitSuggestion 使用的键不同。已显式配置共用 SuggestionPluginKey，候选、插入和退出使用同一插件。
- P2（0170→0171）：compositionend 首个微任务可能早于 ProseMirror 的最终 DOM→state 提交。已保持 composing 保护到下一任务，并在重新组合、外部正文恢复和卸载时清理定时器；插入前重新检查实例与状态。

用户 `0172` 对 `$` 前置边界的最新修正覆盖旧的“中文/英文后紧接 `$` 也触发”行为。共享查询和 Mention matcher 已同步到同一边界函数，既有断言改为合法标点、emoji 与普通正文不触发的预期。架构师 `0177` 已完成本次修正的只读源码复核，确认与执行计划及人工步骤一致，未发现遗留问题；该结论不视为交互验证通过。

以上架构审查核对源码，不代替交互验证；用户后续的人工测试反馈与最终静态检查分别记录在前文。

## Manual verification / 人工步骤

1. 用户更新依赖并自行重启 API，进入原房间。输入普通文字、emoji、HTML 字面量、空白和连续空行，确认清空按钮位置稳定，输入不增高一行；Shift+Enter 换行、Enter 发送。
2. 在开头、空格、换行或符号后输入 `$`，例如 `$dev`、`消息 $dev`、`（$dev`、`消息，$dev`、`+$dev`、`😀$dev`，候选应展开；`中文$dev`、`message$dev`、`123$dev`、代码和转义示例不展开。筛选并点击候选；在 `正文：$dev-check 后面的消息` 中把光标移到 `dev` 后再选中，确认替换整个 `$dev-check` 且保留两侧正文。检查上下键、Tab、Enter、Escape；候选 Enter 与中文输入法确认均不能误发。
3. 同一 Skill 插入两次，整体删除一处、最后一处，查看 capabilities 同步。检查光标移动、跨节点拖选、删除、撤销/重做；内部复制保留身份，对外复制为 `$名称`，外部 HTML 或同名文本不建立身份。
4. 恢复带原始名称/转义 marker、CR/LF、首尾空白、反引号与围栏/缩进代码的草稿；不编辑时比较原正文。编辑代码分隔符后，原引用应在文本与节点之间协调，撤销仍可恢复。普通模型回写不跳光标。
5. 在正文中间粘贴实际截图，拖入多张 PNG/JPEG/WebP。确认真实 POST 返回 201，输入框显示原位图片标签，纯图片能发送，只有 Skill 不能发送；消息显示位置、顺序与 Markdown 一致。
6. 给上传增加网络延迟：期间在锚点前后输入、移动标签、先后粘贴、让同批后图先完成，确认图片顺序和正文不被覆盖。中文输入法组合期间让上传完成，结束后应原位插入且不抢焦点。
7. 上传中分别清空、点锚点取消、删除覆盖锚点的正文、切房间或冻结；回调不能复活图片或写入另一房间。撤销/重做已完成的图片时，不复活失去任务的上传占位。
8. 尝试空文件、伪装图片、动画图、SVG、超过 10 MiB 图片和上传失败，核对字段反馈与 requestId，失败后能重新粘贴。尝试不存在或不匹配房间的图片 ID，确认读取 404。
9. 发送图文后刷新页面、用户自行重启 API，再读取同一 URL；检查草稿中的图片引用、图片大小限制和加载失败提示。确认原消息、回复、目标和冻结发布规则仍可用。
10. 在实际 WebView 重复截图粘贴、文件拖入、中文输入法与剪贴板步骤。用户 `0190` 没有单独列出这些环境与步骤的结果，本文不追加逐项通过结论。

## Limits / 本轮边界

MCP/CLI 图片上传、Codex queue/steer 原生图像输入和返回实际图像的历史读取工具留在后续范围。用户 `0196` 要求的消息本地图片地址已接通，发送给 Agent 的仍为 Markdown 字符串，不能据此报告 Agent 已自动识图。没有用户真实交互验证的项目不标为通过。

用户 `0192` 新增 WebView/app 图片存储与 Agent 本地图片读取评估，架构师通过 `0193` 交高级开发只读核对，结果见 `0194`：

- 图片始终位于已解析的 `database.path.parent / "images" / roomId`，与 WebView 浏览器数据目录独立。默认 app 路径为 `%USERPROFILE%\.agent-relay\data\images\<roomId>`；覆盖 `AGENT_RELAY_DATABASE__PATH` 后随数据库父目录变化。
- 本机当前运行 9080 API 与 9081 Vite，未发现桌面入口进程。已核对的实际原件为 `D:\SourceCodes\mywork\agent-relay\data\images\room-a2493e542ba3\img-e63b354c24dd479ab8f24f0cbd59d641.jpg`（4415 字节）。本机默认桌面数据库和图片目录尚不存在，不能把默认 app 路径报告为实机已运行存储。
- 当前 delivery/QueueRequest/driver 仅传正文与能力引用，未生成 `image/localImage`。此前手动下载 URL 到临时文件查看属于查看方式，不是已实现的原生图片投递。
- 最小后续方案是保留 Markdown URL，在服务端识别本房间受管图片并解析已有本地绝对路径，供 queue/steer 共用的输入转换投递 `localImage`，按正文首次出现顺序去重。代码与转义示例应排除，不接受客户端任意磁盘路径，不自动抓取外链；无需改编辑器、草稿或消息数据库结构。
- 本机 Windows 原生 Codex app-server 具备共享文件路径的条件；尚未对当前 daemon 实测原生图片投递及识图。远程、WSL 或容器需另行核对路径可达性。

以上为 `0194` 时的只读评估事实；用户 `0196` 随后收敛为消息正文提供本地地址，按下面的增量实施，不启动原生图片投递。

## Agent image paths / Agent 本地图片地址

依据用户 `0196`：“消息列表上用 url 展示并无问题，核心是我希望消息里是大模型本地可用的地址，而不是 web 地址”。高级开发 `0197` 接收实现，架构师 `0198/0199` 确认分工并补充统一核对各模型读取入口。实际基线仍为 HEAD `73e0033` 和现有 37 文件暂存快照；架构师 `0195` 的文档更新留在工作树，在其基础上追加本节。

实现：

- `application/images/message_text.py` 的 `ImageMessageText` 共用现有 `ImageStore.read`，将编辑器生成的真实图片引用目标由 `/api/room/<roomId>/image/<imageId>` 替换为原件绝对路径。通过 `Path.as_posix()` 输出正斜杠。用户在 `0207` 实测后要求去掉路径外的尖括号，按当前目录规则输出 `![image](D:/SourceCodes/mywork/agent-relay/data/rooms/room-xxx/images/img-xxx.jpg)`；alt、顺序、重复图片和其余正文原样保留。缺失原件时保留原引用，不虚构可用路径。
- 将原有 Skill 的代码/转义扫描逻辑抽到 `domain/rooms/markdown.py`，由 `inline_skills` 与新增 `inline_images` 共用。图片格式与当前编辑器的引用 codec 对齐，代码块、行内代码、转义示例和普通文字 URL 不转换。domain 不读取磁盘。
- 实时入口 `DeliveryService._submit` 保留 Skill 可读转换，再应用图片地址转换；dispatch 依据当前数据库父目录组装 FileImageStore。queue 与 steer 共用同一消息文本，仍是普通正文投递。
- CLI/MCP 共用的 `RelayClient` 请求携带 `X-Agent-Relay-Image-Paths: local`。HTTP 的 `MessageOutputDependency` 使用同一应用层转换；缺省为 `url`，浏览器请求继续得到原 Markdown URL。覆盖成员 context、消息发布响应、publication 查回，以及 room_get、message_list、queue_list、message_get；CLI/MCP 无需增加公开工具参数。
- 转换仅应用于返回对象的副本及即时投递文本，数据库保存的 content、发布重放校验、上下文查阅记录、分页与定位规则继续使用原消息。没有新增依赖、迁移、编辑器改动或文件下载流程。

静态检查在仓库根目录执行：

| 命令                                                                                                                                                          | 范围与结果                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `uv run --locked --no-sync mypy src tests`                                                                                                                    | 通过，190 个源文件；类型检查测试源不等于运行测试 |
| `uv run --locked --no-sync ruff check` + 本次 10 个 Python 文件                                                                                               | 通过                                             |
| `uv run --locked --no-sync ruff format --check` + 同一范围                                                                                                    | 通过                                             |
| `corepack.cmd pnpm exec prettier --check ../docs/plan/20261113-tiptap-message-editor.md ../docs/verification/20261113-tiptap-message-editor.md`（`web` 目录） | 通过；先整理本文新增内容的格式                   |
| `git diff --check`、`git diff --cached --check`                                                                                                               | 通过                                             |

上述 10 文件为 `application/images/message_text.py`、`application/delivery/service.py`、`domain/rooms/markdown.py`、`domain/rooms/inline_images.py`、`domain/rooms/inline_skills.py`、`infrastructure/dispatch/dependencies.py`、`interfaces/client.py`、`interfaces/http/message_output.py`、`interfaces/http/rooms/routes.py` 和 `interfaces/http/members/routes.py`，均位于 `src/agent_relay/`。

本次 `.git/index` 文件 SHA-256 在修改前后均为 `89B3EAAC86178F95DBDDD1C71C93D0BB2D6D822B9D3898C934F2F2416D75D3B0`，未自动暂存、提交或回退。没有新增或运行自动化测试，没有启动浏览器/服务器，也未实施或验证原生识图。

架构师 `0201` 已只读复核本次产品差异，未发现阻止交付的问题：核对了扫描器复用、目标跨度替换、完整路径表达、返回副本、实时及各读取入口，以及相同图片根目录的依赖组装。其核对的暂存条目 SHA-256 仍为 `45C275E4AF42025FF71D670A2B31AAF7CD8F242C1A71EFD8EEAF378E1581665E`。这是源码审查，尚未实测新版 MCP 返回和模型按返回路径看图。

2026-11-13，用户 `0207` 发起真实消息测试：高级开发与架构师均收到 `best-practices:dev-check` 可读名称及完整 Skill 指令，图片目标已是本地绝对路径；双方直接用 `view_image` 打开 `D:/SourceCodes/mywork/agent-relay/data/images/room-a2493e542ba3/img-7f007b0cd5a342409dd87e56594247fd.jpg`，均看到纯红色小方块，未下载。该次测试使用的是带尖括号的旧输出，证明实时投递与本地看图成功；随后按用户最新要求移除输出尖括号，未重跑消息交互。

当前已连接 MCP 的 `member_context(message_id=0207)` 仍返回原 API 图片 URL，不能标为 MCP 历史链路通过。架构师 `0209` 进一步实际核对：同一消息的 HTTP 详情默认返回 URL，携带 `X-Agent-Relay-Image-Paths: local` 时返回本地路径；成员 context 带该头也正确返回本地路径。服务端这两条读取路径已验证，旧 MCP 进程仍需加载新版 RelayClient 后复测。此次只做引用与读取的实际验证，未重复运行全量项目质量检查、改暂存或重启进程。

人工步骤（待用户执行）：

1. 用户自行让 API 与 CLI/MCP 进程加载更新后的代码；旧 MCP 进程需重载新版 RelayClient，才能携带 `local` 请求头。发送已上传图片，确认新收到的模型消息中目标是现有原件绝对路径；用本地看图工具直接读取，不需先下载。
2. 对同一图片消息分别调用 member_context、message_get、message_list、publication_get，以及包含该消息的 room_get/queue_list，确认返回正文目标一致。未完成投递的队列才会出现在 queue_list，不据此要求已处理消息仍出现在队列。
3. 浏览器刷新消息列表、详情与图片，确认仍用 API URL 渲染；发布查回和再次读取不把本地路径写回原正文。更新代码之前已经投递的 Codex 历史输入保持原值，可通过新的历史读取取得本地地址。
4. 使用含空格的数据库目录，确认返回的路径完整；图文、重复图片及图片前后的文字顺序不变。代码与转义示例保持字面量。

## Room image storage / 房间图片目录

依据架构师 `0220` 转达的用户 `0218` 授权，目录统一为 `<database.path.parent>/rooms/<roomId>/images/<imageId>.<ext>`。高级开发 `0221` 接收，实际基线为已暂存的本地图片地址相关 12 文件，以及未暂存的成员 ID 复制功能 4 文件。本节只修改目录代码及本计划/验证记录，未改编辑器、API URL、消息正文存储、ID 生成或本地路径 Markdown 输出格式。

代码修改仅 3 文件：

- `bootstrap/dependencies.py`：HTTP 的 FileImageStore 注入 `database.path.parent / "rooms"`。
- `infrastructure/dispatch/dependencies.py`：实时投递的 FileImageStore 注入同一 `rooms` 根。
- `infrastructure/images/files.py`：`_directory(room_id)` 集中返回 `self.root / room_id / "images"`，上传保存、API 读取和 Agent 本地路径解析共用此规则。

开发目录现为 `D:/SourceCodes/mywork/agent-relay/data/rooms/room-a2493e542ba3/images/`。默认桌面目录对应 `%USERPROFILE%\.agent-relay\data\rooms\<roomId>\images\`，覆盖数据库位置时继续随数据库父目录变化；本次没有启动桌面实例。

一次性复制：从现有 `data/images/room-a2493e542ba3/` 复制到 `data/rooms/room-a2493e542ba3/images/`。执行前核对来源与目标为工作区内的绝对路径，逐个确认目标不存在；使用禁止覆盖的文件复制操作。3 个旧文件均保留，复制后逐文件 SHA-256 相同，合计 17,855 字节：

| 文件                                       | 字节数 | SHA-256（新旧一致）                                                |
| ------------------------------------------ | -----: | ------------------------------------------------------------------ |
| `img-1d3326d586164d8f980b73e255243409.png` | 13,112 | `C6063FB3FB9E48B94CDDEA1F1930049001A504E5BFC386524E2493F52E3AA762` |
| `img-7f007b0cd5a342409dd87e56594247fd.jpg` |    328 | `904987AFF95CF141E07A828C1AE7FFDB5B8F462DEEFCB052AC9AF26123216DBA` |
| `img-e63b354c24dd479ab8f24f0cbd59d641.jpg` |  4,415 | `9D494F16D7EC9D0AAB164CB15EF518A4B05D3EB91CA51CD2E3001CC08D693665` |

这是本次一次性整理实际测试文件，没有新增启动迁移、长期双目录读取、删除或覆盖逻辑。旧原件保留，已有会话里的旧绝对路径仍有对应文件。

运行加载观察：未启动或重启服务，仅对同一现有消息 `room-a2493e542ba3-msg-0207` 的 HTTP 详情携带 `X-Agent-Relay-Image-Paths: local` 做只读查询。

- 2026-11-13 16:53:10，修改前返回 `D:/SourceCodes/mywork/agent-relay/data/images/room-a2493e542ba3/img-7f007b0cd5a342409dd87e56594247fd.jpg`。
- 2026-11-13 16:55:00，修改后返回 `D:/SourceCodes/mywork/agent-relay/data/rooms/room-a2493e542ba3/images/img-7f007b0cd5a342409dd87e56594247fd.jpg`，保留无尖括号格式。监听 9080 的进程仍为 PID 33288，当前 HTTP 图片路径解析已加载新布局；未据此宣称新上传、实时投递或已连接 MCP 的新目录交互全部通过。

静态检查（仓库根目录）：

```powershell
uv run --locked --no-sync mypy src/agent_relay/infrastructure/images/files.py src/agent_relay/bootstrap/dependencies.py src/agent_relay/infrastructure/dispatch/dependencies.py
uv run --locked --no-sync ruff check src/agent_relay/infrastructure/images/files.py src/agent_relay/bootstrap/dependencies.py src/agent_relay/infrastructure/dispatch/dependencies.py
uv run --locked --no-sync ruff format --check src/agent_relay/infrastructure/images/files.py src/agent_relay/bootstrap/dependencies.py src/agent_relay/infrastructure/dispatch/dependencies.py
```

三项均通过，Mypy 范围为 3 文件；保留既有 dynaconf override 未使用提示。两份文档执行 Prettier 检查，双份 `git diff --check` 通过。未新增或运行测试，没有新增/升级依赖，本 Agent 未执行暂存或提交。

架构师 `0223` 已完成最终独立核对：3 文件源码无阻止项；新旧目录的 3 文件大小与 SHA-256 相同；直接 `view_image` 打开新目录红色小图成功，同一消息的 HTTP local 响应也已返回无尖括号的新目录路径。未将这些事实扩大为新上传、实时投递或 MCP 读图全部通过。

架构师对最终目录代码重跑仓库根目录的 `uv run --locked --no-sync mypy src tests`、`ruff check .`、`ruff format --check .`：全量 Mypy 190 文件、Ruff lint、Ruff 格式 310 文件均通过。其 `0215` 前端检查继续适用：全量 lint 0 errors / 20 条既有 warning、格式和显式 node 项目类型检查通过；显式 app 项目仍有 14 条既有诊断，涉及文件未改动。根 typecheck 脚本的 references 漏检限制保留；最终复制按钮 CSS 已单独补查 Prettier 通过。没有运行测试、构建或重启进程。

暂存状态分时记录：本节开始时为已暂存 12 文件，`.git/index` 文件 SHA-256 为 `80C90113172E84E77F2FFFB85CB9C8298A270920A3D21F400351DB5BEE913623`。验证期间 4 个 UI 文件进入暂存区，当前为 16 文件；架构师 `0223` 核对的暂存条目 SHA-256 为 `54C35DD78D767568A661F6C8439C987EF0F8CB004E2DCA3137F4301BB4568B40`，高级开发随后核对的 `.git/index` 文件 SHA-256 为 `B5A93C1F3570D522BC2B39AFE4C4894CD13F49CF1BEDB0F47725A4AC5814A08E`。本次目录代码 3 文件及文档 2 文件留在工作树，不声称整个验证期间暂存状态从未变化。

## Final lint and format / 最终检查与格式修正

用户 `0215` 要求执行 `best-practices:dev-check`，期间 `0218` 要求先实施房间资源目录；目录完成后，用户追加“lint/format 问题一并修正”。架构师依据该追加授权修改 `web/eslint.config.js`，不再将早先的 20 条 lint warning 作为最终遗留结果。

- 19 条格式 warning 来自 `vue/html-closing-bracket-newline`、`vue/html-indent`、`vue/multiline-html-element-content-newline` 与既有 Prettier 排版冲突。配置关闭这 3 条重复格式约束，沿用 Prettier 检查，没有为 lint 重排业务模板。
- 另 1 条 `vue/no-v-html` 来自 MessageTimeline 的现有 Markdown 展示入口。核对 `messageMarkdown.ts`：MarkdownIt 默认不接受原始 HTML，动态 Skill 名称、title 与图片失败文案均转义。仅对 `src/domains/room/MessageTimeline.vue` 配置该规则例外，其他组件继续保留 warning；没有移除 Markdown 展示或新增 HTML 注入入口。
- 保留既有 ESLint 9、Vue/TypeScript 配置及依赖，没有升级工具链、增加 import resolver 或变更 import 检查范围。未执行 import 正反例验证，不据此宣称新增 import 解析能力。

本机缺少 make，按 Makefile `check` 逐项执行。最终实际命令与结果如下；目录代码修改后重跑全部 Python 检查，lint 配置修改后重跑前端 lint/格式。

| 目录       | 实际命令                                                                                                                                        | 最终结果                                                 |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 仓库根目录 | `uv run --locked --no-sync mypy src tests`                                                                                                      | 通过，190 个源文件                                       |
| 仓库根目录 | `uv run --locked --no-sync ruff check .`                                                                                                        | 通过                                                     |
| 仓库根目录 | `uv run --locked --no-sync ruff format --check .`                                                                                               | 通过，310 个文件                                         |
| `web`      | `corepack.cmd pnpm run typecheck`                                                                                                               | 退出成功；保留根 references 配置漏检说明                 |
| `web`      | `corepack.cmd pnpm exec vue-tsc --noEmit -p tsconfig.app.json`                                                                                  | 失败，14 条既有诊断，分布同前文；相关文件与 HEAD 无差异  |
| `web`      | `corepack.cmd pnpm exec vue-tsc --noEmit -p tsconfig.node.json`                                                                                 | 通过                                                     |
| `web`      | `corepack.cmd pnpm run lint`                                                                                                                    | 通过，0 errors、0 warnings                               |
| `web`      | `corepack.cmd pnpm run format`                                                                                                                  | 通过                                                     |
| `web`      | `corepack.cmd pnpm exec prettier --check ../docs/plan/20261113-tiptap-message-editor.md ../docs/verification/20261113-tiptap-message-editor.md` | 通过                                                     |
| `web`      | `corepack.cmd pnpm exec eslint --print-config src/domains/room/MessageTimeline.vue` 及相同命令检查 `src/domains/room/RoomPage.vue`              | 前者 `vue/no-v-html` 为 off，后者仍为 warn，组件范围生效 |
| 仓库根目录 | `git diff --check`、`git diff --cached --check`                                                                                                 | 通过                                                     |

未新增或运行自动化测试、生产构建，没有启动或重启服务。14 条应用类型错误不属于本次 lint/format 修复，未自动改动类型配置或相关组件；不能报告全部检查通过。当前 16 文件暂存快照由用户保留，架构师的配置和验证记录修改仅留工作树，未执行暂存、提交或回退。
