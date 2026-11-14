import subprocess
from pathlib import Path

from agent_relay.domain.rooms.errors import RoomConflictError, RoomInputError
from agent_relay.domain.rooms.rules import normalize_project_path


class GitWorktrees:
    @staticmethod
    def run(source: str, *arguments: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", source, *arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RoomConflictError(
                "Git 操作超时，进程状态需要人工核对", code="worktree_operation_uncertain"
            ) from exc
        except OSError as exc:
            raise RoomInputError("无法完成 Git 操作", code="worktree_git_unavailable") from exc
        if result.returncode:
            raise RoomInputError("Git 操作失败，请核对仓库状态", code="worktree_git_failed")
        return result.stdout.strip()

    def inspect(self, source: str) -> str:
        root = self.run(source, "rev-parse", "--show-toplevel")
        if normalize_project_path(str(Path(root).resolve())) != normalize_project_path(
            str(Path(source).resolve())
        ):
            raise RoomInputError(
                "创建 worktree 需要仓库根目录", code="worktree_repository_root_required"
            )
        return self.run(source, "rev-parse", "--verify", "HEAD^{commit}")

    def available(self, source: str, path: str, branch: str) -> None:
        if Path(path).exists() or Path(path).is_symlink():
            raise RoomConflictError("Worktree 目录已存在", code="worktree_path_exists")
        branches = self.run(source, "for-each-ref", "--format=%(refname)", f"refs/heads/{branch}")
        if branches:
            raise RoomConflictError("Worktree 分支已存在", code="worktree_branch_exists")

    def create(self, source: str, path: str, branch: str, commit: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.run(source, "worktree", "add", "-b", branch, "--", path, commit)

    def verify(self, source: str, path: str, branch: str, commit: str) -> None:
        common = self.run(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
        target_common = self.run(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
        root = self.run(path, "rev-parse", "--show-toplevel")
        same = normalize_project_path(str(Path(common).resolve())) == normalize_project_path(
            str(Path(target_common).resolve())
        )
        if (
            not same
            or normalize_project_path(str(Path(root).resolve()))
            != normalize_project_path(str(Path(path).resolve()))
            or self.run(path, "rev-parse", "HEAD") != commit
            or self.run(path, "symbolic-ref", "--short", "HEAD") != branch
        ):
            raise RoomConflictError("Worktree 身份不匹配", code="worktree_identity_mismatch")
