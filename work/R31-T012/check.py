#!/usr/bin/env python3
"""Verify that git update-ref moves a branch without changing the index or worktree."""

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
    with tempfile.TemporaryDirectory(prefix="R31-T012-") as directory:
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

        head_before = git(repo, "symbolic-ref", "HEAD").strip()
        main_before = git(repo, "rev-parse", "main").strip()
        topic_before = git(repo, "rev-parse", "topic").strip()
        index_before = git(repo, "write-tree").strip()
        tree_c = git(repo, "rev-parse", f"{commit_c}^{{tree}}").strip()
        files_before = {
            "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        }
        log_before = git(repo, "log", "--pretty=oneline", "main")

        assert head_before == "refs/heads/main"
        assert main_before == commit_c
        assert topic_before == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert index_before == tree_c
        assert log_before.splitlines() == [
            f"{commit_c} C: add todo",
            f"{commit_b} B: append beta",
            f"{commit_a} A: create notes",
        ]

        git(repo, "update-ref", "refs/heads/main", commit_b, commit_c)

        head_after = git(repo, "symbolic-ref", "HEAD").strip()
        main_after = git(repo, "rev-parse", "main").strip()
        topic_after = git(repo, "rev-parse", "topic").strip()
        index_after = git(repo, "write-tree").strip()
        status_after = git(repo, "status", "--short", "--branch")
        cached_names = git(repo, "diff", "--cached", "--name-status")
        worktree_names = git(repo, "diff", "--name-status")
        log_after = git(repo, "log", "--pretty=oneline", "main")
        commit_c_type = git(repo, "cat-file", "-t", commit_c).strip()
        files_after = {
            "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        }
        tree_after = git(repo, "rev-parse", f"{commit_c}^{{tree}}").strip()

        assert head_after == head_before
        assert main_after == commit_b
        assert topic_after == topic_before == commit_b
        assert git(repo, "rev-parse", "HEAD").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert commit_c_type == "commit"
        assert index_after == index_before == tree_after
        assert files_after == files_before == {
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
        }
        assert status_after == "## main\nA  todo.txt\n"
        assert cached_names == "A\ttodo.txt\n"
        assert worktree_names == ""
        assert log_after.splitlines() == [
            f"{commit_b} B: append beta",
            f"{commit_a} A: create notes",
        ]
        git(repo, "diff", "--exit-code")

        stale_update = subprocess.run(
            ["git", "update-ref", "refs/heads/main", commit_c, commit_c],
            cwd=repo,
            env={**os.environ, **BASE_ENV},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert stale_update.returncode != 0
        assert git(repo, "rev-parse", "main").strip() == commit_b

        actual = [
            f"commit A: {commit_a}",
            f"commit B: {commit_b}",
            f"commit C: {commit_c}",
            f"HEAD before: {head_before}",
            f"main before: {main_before}",
            f"topic before: {topic_before}",
            f"index tree before: {index_before}",
            "log main before:",
            log_before.rstrip(),
            "operation: git update-ref refs/heads/main <B> <C>",
            f"HEAD after: {head_after}",
            f"main after: {main_after}",
            f"topic after: {topic_after}",
            f"index tree after: {index_after}",
            f"C object type: {commit_c_type}",
            f"stale expected-old update return code: {stale_update.returncode}",
            "status after:",
            status_after.rstrip(),
            "cached name-status:",
            cached_names.rstrip(),
            "worktree name-status:",
            worktree_names.rstrip(),
            "log main after:",
            log_after.rstrip(),
            "files after:",
            f"notes.txt={files_after['notes.txt']!r}",
            f"todo.txt={files_after['todo.txt']!r}",
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: git update-ref moved main from C to B without changing HEAD's symbolic target, index, or worktree.")


if __name__ == "__main__":
    main()
