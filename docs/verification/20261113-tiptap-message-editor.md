# Verification / 验证：Tiptap 消息编辑器与图片引用

最后修改时间: 2026-11-13 15:10:00

## Scope / 范围

依据用户 `room-a2493e542ba3-msg-0162`、架构师 `0165` 和 [执行计划](../plan/20261113-tiptap-message-editor.md)，完成 W1→W2 的产品代码。当前为实现与静态检查交付，浏览器、WebView、真实上传和发布交互仍待用户人工验证。

原 HEAD 为 `73e0033bad1451d5a43c66f54e47ee7c6075e68e`。原 14 个文件的暂存区作为 Tagify 试切前快照保留，本轮改动全部在工作树，未重新暂存、提交或回退。按用户要求没有新增或运行自动化测试，也没有自动打开浏览器、启动或重启服务器。

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

存储根目录为解析后的 `database.path.parent / "images"`，沿用开发/桌面已解析的数据库持久目录。房间目录下保存 API 生成的 `img-<uuid32>.png/jpg/webp`，格式、大小元数据由受管文件后缀及文件大小读取，不另建消息表附件字段。读取先确认房间存在，并严格核对 room/image ID，仅在该房间目录寻找文件。文件保留供刷新、重启及消息重读；本轮没有自动文件清理。

Python 直接依赖新增 Pillow `>=12,<13`（本次锁定 12.3.0）及 python-multipart `>=0.0.22,<1`（锁定 0.0.33，原为间接依赖）。未运行数据库迁移，未做真实 HTTP 上传或 API 重启验证。已有 API 进程需要由用户重启以加载新增路由。

## Static checks / 静态检查

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

最终收尾（含 `0172` 修正）：改动的共享查询、编辑器及既有断言 ESLint 0 errors、0 warnings；最终应用项目显式类型检查仍为上述未改动文件中的 14 条诊断，本轮编辑器及图片实现文件无诊断。生产构建通过，JS 1,057.05 kB / gzip 347.42 kB，CSS 61.30 kB / gzip 11.78 kB；Vite 大 chunk 提示仍在。改动范围 Prettier 与 `git diff --check` 通过。最终暂存区仍为原 14 文件、1361 insertions / 86 deletions，本轮未自动暂存或提交。

没有使用 Node 逻辑调用、临时脚本、测试框架或浏览器自动化替代用户要求的人工交互验证。

应用项目显式类型检查的既有失败涉及：AppCheckboxGroup 对泛型组件使用 InstanceType、useStoredOrder 的 ES2023 toSorted/toReversed 与隐式 any、MemberEditDialog 的 nullable 值、api/useRoomCapabilities 使用 Object.hasOwn 的类型库，以及 api/roomApi 测试中的 AxiosAdapter 类型。这些文件相应位置均不属于本次变更；按计划没有顺带修复组件或全局类型工具链。检查不执行测试，且没有将现有脚本的退出成功报告为应用项目完整类型通过。

## Review / 交付审查

架构师 `0171` 完成只读源码核对；两项问题已修复：

- P1（0168→0169）：Mention 默认插件键与 getState/exitSuggestion 使用的键不同。已显式配置共用 SuggestionPluginKey，候选、插入和退出使用同一插件。
- P2（0170→0171）：compositionend 首个微任务可能早于 ProseMirror 的最终 DOM→state 提交。已保持 composing 保护到下一任务，并在重新组合、外部正文恢复和卸载时清理定时器；插入前重新检查实例与状态。

用户 `0172` 对 `$` 前置边界的最新修正覆盖旧的“中文/英文后紧接 `$` 也触发”行为。共享查询和 Mention matcher 已同步到同一边界函数，既有断言改为合法标点、emoji 与普通正文不触发的预期。架构师 `0177` 已完成本次修正的只读源码复核，确认与执行计划及人工步骤一致，未发现遗留问题；该结论不视为交互验证通过。

该审查核对源码，不代表浏览器、WebView 或实际上传/重读已经验证通过。

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
10. 在实际 WebView 重复截图粘贴、文件拖入、中文输入法与剪贴板步骤。当前没有该环境的通过结论。

## Limits / 本轮边界

MCP/CLI 图片上传、Codex queue/steer 原生图像输入和历史按需看图留在后续范围。当前发送给 Agent 的仍为 Markdown 字符串，不能据此报告 Agent 已识图。没有用户真实交互验证的项目不标为通过。
