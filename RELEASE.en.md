# Changelog

Organized by Git commit date. Entries focus on product capabilities and behavioral changes, with short commit hashes listed for reference. Implementation details, tests, and release pipelines are not listed separately.

## 2026-11-16

- Renamed the project from Agent Relay to Conflua, including its commands, plugins, and configuration names. The default database is now `data/conflua.db`.
- When a single agent member is selected, the message composer can display and switch the model used by its Codex session.
- Messages are now delivered in the background. Transient failures are persisted and retried with backoff; delivery order is preserved for each session while other targets can continue. Uncertain results are reconciled against receipts to avoid blind resends. Delivered prompts also identify the receiving member.
- The member sidebar offers an interrupt action for busy sessions and a delete action for offline members or members whose status is unknown.
- Entering a channel shows the latest message details by default; channel details appear only when the channel is explicitly selected. Skeletons appear while rooms and messages load, and the reading position is preserved on refresh.
- Channel, member, and other dialogs automatically focus their primary input when opened.
- Database migrations were consolidated into a channel baseline, with fields added for delivery recovery. Earlier databases require the steps in the [migration guide](migrations/README.md); databases already at the channel baseline can upgrade incrementally.

Commits: `29d8b40`, `24f4c38`, `6ea5732`, `ef855a1`, `396f703`, `c5ab143`, `4564339`, `3c2772e`, `e1e8462`.

## 2026-11-15

- On narrow screens, navigation and details use drawers, the editor supports a split-pane layout for routing, and touch targets are easier to use.
- Channel "archive" was renamed to "delete": after confirmation, the channel is removed from selection while its history is retained. The default channel cannot be deleted.
- An active Codex turn can be interrupted for a member, with session status refreshed afterward.
- The last selected channel is remembered per project and restored after switching projects or refreshing. Deleting a channel returns to the default channel.

Commits: `a49d588`, `c8bc6ba`, `d9fb388`, `9bb93db`.

## 2026-11-14

- Chat rooms now support channels: members, topics, messages, drafts, and queues are isolated by channel. A new channel can optionally create a separate Git worktree from the current commit; by default it uses the room directory.
- Existing rooms are automatically placed in the default channel after upgrading; existing services and Codex sessions are unaffected.

Commit: `ff4c31d` (migrations: `0005_channels`, `0006_channel_description`).

## 2026-11-13

- The interface supports Chinese and English, with system language, Simplified Chinese, or English configurable as the default. The About dialog displays the running version.
- System, light, and dark themes are supported; the system theme follows changes in system appearance.
- Messages support inline Skill / MCP references and images. Images can be pasted or dragged in and are visible to members in their sessions; references retain their positions and readable text when sent.
- Message drafts are saved and restored per room, including text, recipients, references, and reply context. Selecting a room restores its last unsent draft.
- Panel collapse state persists across refreshes. Sending is disabled with an explanation when content or recipients are missing, and Codex session IDs are available in details.

Commits: `b4fbc85`, `c957ac1`, `8c6445f`, `73e0033`, `6cda219`, `db039b7`, `5632ee8`, `d814c88`, `859954e`.

## 2026-11-12

- Added a Windows desktop application using WebView, sharing the same Relay service as the Web and CLI interfaces. Releases are available through GitHub Release and GitLab Release.
- Delivery is faster and more reliable: messages can be injected into an active turn, and receipts are checked again when a session is busy or input history is unavailable, without resending merely because of the wait.
- Queue entries can be removed individually by message while preserving chat messages and delivery history.
- Added a Clear button beside the chat search field. After confirmation, it soft-deletes current messages, delivery records, and unreachable members, and refreshes other clients. This requires migration to `message_deleted_20261112`.
- Consolidated SQLite schema SQL and Alembic revisions while retaining `queue_deleted_20261110`. Direct upgrades from the old `baseline_20261110` are no longer provided; see the [migration guide](migrations/README.md).

Commits: `62b7b8e`, `fb1bc75`, `3f8097a`, `b52090d`, `319337e`, `ffbd8cd`, `0e12906`, `29e5e8b`, `67599cb`, `1d09814`, `a5c0609`, `6253a4a`.

## 2026-11-11

- CLI/MCP now supports querying queues and clearing them by scope. By default, only pending Relay work is cleared; explicitly enabling `--clear-codex` / `clear_codex` also removes waiting Codex items using saved receipts and separately reports deleted, not found, rejected, unknown, and no-receipt results.
- Message queries support keyword filtering. Delivery headers include a stable message ID, sequence number, and publication time; the collaboration Skill also explains delayed messages and communication conditions.

Commit: `be8accd`.

## 2026-11-10

- Room, topic, and member details include queues scoped to each context, with refresh, pagination, clearing, and navigation to the original message. Clearing preserves messages and delivery history.
- Added message-body search and improved send shortcuts, message actions, and delivery summaries. Member aliases are preserved when session names are synchronized.
- SQLite persistence now uses explicit fields and relationship tables, resetting the schema baseline. Old databases containing whole-model JSON require the migration guide's handling steps.
- Removed the notification demo page. Development checks support `fix=1`, and `make test` runs both frontend and backend unit tests.

Commits: `ec70b12`, `3df5949`, `b24fb5a`, `f7e29d4`, `5c4037b`, `2d5d631`.

## 2026-11-09

- New rooms create product, architecture, development, and testing topics by default. Topic creation times, sidebar topic and member ordering, and room deletion with confirmation are supported.
- Added the fixed human member "You". Messages to human members appear in the room and do not enter the Codex delivery queue.
- Improved available-session selection and explanations for unavailable sessions, with continuous member status refresh. Details panels and message author names are consistent, and reference and draft routing context is preserved.
- Separated backend business rules, application services, adapters, and startup configuration, with explicit transaction boundaries for persistent events. The frontend toolchain moved to a pinned pnpm version.

Commit range: `79cca7e` to `320e437`.

## 2026-11-08

- Messages can be delivered to bound Codex sessions, with enqueue and receipt acknowledgments saved. Members can publish messages and query visible context, with history pagination and event synchronization.
- Added CLI/MCP collaboration tools sharing an HTTP client, with member identity resolved automatically from the current session. `make install` installs the CLI and Codex plugin.
- Members can choose not to subscribe to topics. Write transactions and delivery failure isolation were improved; uncertain submissions retain known facts and are not automatically resent.

Commits: `a71d186`, `e40d313`, `68d601d`.

## 2026-11-07

- Created project chat rooms with topic, member, message, and routing management.
- Room and routing records are persisted in SQLite, and existing Codex sessions can be discovered and bound.
- Documented the collaboration architecture and subsequent delivery implementation plan.

Commits: `2cc4933`, `355bb46`, `cae9d90`.

## 2026-11-06

- Initialized the Agent Relay project skeleton.

Commit: `8870f57`.
