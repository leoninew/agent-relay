# Windows 制品发布指南

## 本地构建

在 Windows x64 的 GNU Make/Git Bash 环境中运行 `make binary`，生成完整桌面目录和版本化 ZIP。包内容与运行要求见[桌面使用指南](windows-desktop.md)。

## 版本计算与更新

使用本项目的 `scripts/version-calc.py`，默认定位脚本所属仓库。先预览，确认后应用：

```bash
uv run --locked --no-sync python scripts/version-calc.py
uv run --locked --no-sync python scripts/version-calc.py --no-dry-run
```

版本从执行时 `HEAD` 可达的全部提交计算，按从旧到新的顺序处理：主版本固定为 `0`，提交标题以 `feat` 开头时次版本加一、修订号归零，其他提交使修订号加一。计算不依赖已有 tag，也不计入未提交修改；默认只输出结果。

应用命令统一更新 `pyproject.toml` 的项目版本、`src/agent_relay/__init__.py` 的静态 `__version__` 和 `uv.lock`。`uv lock` 失败时恢复更新前的这三份文件；脚本不提交或创建 tag，也不更新已安装环境。

“关于”通过 `/api/app` 读取当前服务代码的 `__version__`。源码运行、wheel 安装和 WebView EXE 使用同一规则，版本随代码发布；本机另一个 tool 或虚拟环境的安装元数据不参与取值。`make binary` 会校验运行版本与项目版本、发布 tag 一致，ZIP 文件名沿用项目版本。

## GitHub Release

[Build Windows desktop](../../.github/workflows/build-desktop.yml) 支持 `v*` tag push 自动发布，或手动 `workflow_dispatch` 并填写已有版本 tag。工作流检出该 tag，执行 `make deps`、`make check`、`make test`、`make binary`，再将同一个 ZIP 上传到 GitHub Release 的 **Assets**；对应 run 的 **Artifacts** 也保留下载。

tag 必须等于 `pyproject.toml` 的版本前加 `v`。首次创建 Release，重跑时复用该 Release 并覆盖同名 ZIP。通用 ZIP 在仓库页的 **Releases** 下载，**Packages** 用于独立的包仓库。

## GitLab 项目准备

[.gitlab-ci.yml](../../.gitlab-ci.yml) 使用两个 runner：

| Runner tag     | 配置与工具                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `windows-bash` | Windows x64，Shell executor，`shell = "pwsh"`；将 Git Bash 的 `bash.exe`、GNU Make、Python、Node.js、uv、Corepack 和 `curl.exe` 放入 runner 服务账户的 `PATH` |
| `linux-docker` | Linux Docker executor，可拉取 `registry.gitlab.com/gitlab-org/cli:latest` 镜像执行 Release job                                                                |

Windows runner 的 Python 与 Node.js 版本分别按 `.python-version`、`.node-version` 准备；pnpm 版本按 `web/package.json` 的 `packageManager` 准备。可先在 `web/` 中执行 `corepack.cmd enable` 和 `corepack.cmd pnpm --version`。`PATH` 中 Git Bash 的 `bash.exe` 应排在 WSL 的同名入口之前；构建 job 通过 PowerShell 调用 Git Bash 执行现有 Makefile。Release job 使用支持 glab 发布的 GitLab 与 GitLab Runner 18.4+ 环境。

在 GitLab 项目中启用 **Package Registry**。上传与 Release 创建使用自动提供的 `CI_JOB_TOKEN`，无需另设个人访问令牌。将 `v*` 配置为 protected tags，并允许负责发布的成员和 runner 执行。

## 触发 GitLab Release

先按上述流程同步并提交项目版本、运行版本和锁文件，再向 GitLab 仓库推送对应 tag。例如，项目版本为 `0.23.1`、GitLab remote 名为 `gitlab`：

```bash
git tag -a v0.23.1 -m "Release v0.23.1"
git push gitlab v0.23.1
```

仅 `vMAJOR.MINOR.PATCH` 格式的 tag 创建 pipeline；分支 push 不触发发布。tag 与项目版本不一致时，版本检查失败。tag 指向的提交须包含 `.gitlab-ci.yml`。若从 GitHub 镜像到 GitLab，需确认镜像同步了 tag。

pipeline 依次执行：

1. `package_windows` 检查版本，执行现有依赖安装、静态检查、单元测试和 `make binary`，将完整 ZIP 上传至 Generic Package Registry。
2. `create_release` 在上传成功后创建该 tag 的 GitLab Release，添加 **Windows x64 desktop package** 下载链接。

## 下载与保留

Release 链接指向以下持久文件：

```text
<GitLab API>/projects/<project-id>/packages/generic/agent-relay/<tag>/agent-relay-windows-x64.zip
```

在项目的 Release 页面或 **Packages and registries → Package Registry** 下载。私有项目下载需要相应访问权限。Package Registry 的文件独立于 pipeline artifact；保留发布版本时，不要通过清理策略删除这些包。

pipeline artifact 保留一周，用于临时下载。重复运行已发布 tag 不会更新已有 Release，创建 job 会失败；发布新版本应使用新的版本号与 tag。GitHub Actions 构建成功后，仍需把版本 tag 推到 GitLab 才会触发这条发布链。
