#!/usr/bin/env python3
"""Verify recovery of a staged working-tree mistake from the saved commit."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
BASE_ENV = {
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(repo, *args, extra_env=None):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **BASE_ENV, **(extra_env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def commit(repo, message, day):
    date = f"2020-01-{day:02d}T00:00:00+0000"
    git(
        repo,
        "commit",
        "-m",
        message,
        extra_env={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
    )


def main():
    with tempfile.TemporaryDirectory(prefix="R31-T013-") as directory:
        repo = Path(directory)
        git(repo, "init", "--initial-branch=main")
        git(repo, "config", "user.name", "Course Student")
        git(repo, "config", "user.email", "student@example.invalid")

        (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
        git(repo, "add", "notes.txt")
        commit(repo, "A: create notes", 1)
        commit_a = git(repo, "rev-parse", "HEAD").strip()

        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        git(repo, "add", "notes.txt")
        commit(repo, "B: append beta", 2)
        commit_b = git(repo, "rev-parse", "HEAD").strip()
        git(repo, "branch", "topic")

        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        git(repo, "add", "todo.txt")
        commit(repo, "C: add todo", 3)
        commit_c = git(repo, "rev-parse", "HEAD").strip()
        recovery_tree = git(repo, "rev-parse", f"{commit_c}^{{tree}}").strip()
        topic_before = git(repo, "rev-parse", "topic").strip()

        (repo / "notes.txt").write_text("alpha\nmistake\n", encoding="utf-8")
        git(repo, "add", "notes.txt")
        grep_mistake = git(repo, "grep", "-n", "mistake")
        status_before_restore = git(repo, "status", "--short", "--branch")
        index_before_restore = git(repo, "write-tree").strip()
        assert grep_mistake == "notes.txt:2:mistake\n"
        assert status_before_restore == "## main\nM  notes.txt\n"
        assert index_before_restore != recovery_tree

        git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", "notes.txt")

        recovered_head = git(repo, "rev-parse", "HEAD").strip()
        recovered_tree = git(repo, "rev-parse", f"{recovered_head}^{{tree}}").strip()
        recovered_index = git(repo, "write-tree").strip()
        status_after_restore = git(repo, "status", "--short", "--branch")
        grep_beta = git(repo, "grep", "-n", "beta")
        final_log = git(repo, "log", "-1", "--pretty=oneline")
        final_notes = (repo / "notes.txt").read_text(encoding="utf-8")
        final_todo = (repo / "todo.txt").read_text(encoding="utf-8")
        main_after = git(repo, "rev-parse", "main").strip()
        topic_after = git(repo, "rev-parse", "topic").strip()

        assert recovered_head == commit_c
        assert main_after == commit_c
        assert topic_before == topic_after == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert recovered_tree == recovery_tree
        assert recovered_index == recovery_tree
        assert final_notes == "alpha\nbeta\n"
        assert final_todo == "one\n"
        assert status_after_restore == "## main\n"
        assert grep_beta == "notes.txt:2:beta\n"
        assert final_log == f"{commit_c} C: add todo\n"
        git(repo, "diff", "--exit-code")
        git(repo, "diff", "--cached", "--exit-code")

        actual = [
            f"commit A: {commit_a}",
            f"commit B: {commit_b}",
            f"commit C / recovery commit: {commit_c}",
            f"topic before/after: {topic_before} / {topic_after}",
            f"recovery tree: {recovery_tree}",
            "mistake search:",
            grep_mistake.rstrip(),
            "status before restore:",
            status_before_restore.rstrip(),
            f"index tree before restore: {index_before_restore}",
            "recovery command: git restore --source=HEAD --staged --worktree -- notes.txt",
            f"HEAD after: {recovered_head}",
            f"tree at HEAD after: {recovered_tree}",
            f"index tree after: {recovered_index}",
            "status after restore:",
            status_after_restore.rstrip(),
            "search after restore:",
            grep_beta.rstrip(),
            "final log:",
            final_log.rstrip(),
            f"notes.txt={final_notes!r}",
            f"todo.txt={final_todo!r}",
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: restore returned the named file and index to the saved commit tree; HEAD and refs were preserved.")


if __name__ == "__main__":
    main()
