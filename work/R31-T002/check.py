#!/usr/bin/env python3
"""Automated verification check for R31-T002: Command line state transitions."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

BASE_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
}


def git(repo: Path, *args: str, extra_env: dict | None = None) -> str:
    env = dict(BASE_ENV)
    if extra_env:
        env.update(extra_env)
    res = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout


def run_once(run_index: int) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"R31-T002-run{run_index}-") as tmpdir:
        repo = Path(tmpdir) / "cmdline-demo"
        repo.mkdir()

        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "Course Student")
        git(repo, "config", "user.email", "student@example.invalid")

        # Commit A
        (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
        git(repo, "add", "notes.txt")
        git(
            repo,
            "commit",
            "-m",
            "A: create notes",
            extra_env={
                "GIT_AUTHOR_DATE": "1000000000 +0000",
                "GIT_COMMITTER_DATE": "1000000000 +0000",
            },
        )
        commit_a = git(repo, "rev-parse", "HEAD").strip()
        blob_a = git(repo, "rev-parse", f"{commit_a}:notes.txt").strip()

        # Commit B
        with (repo / "notes.txt").open("a", encoding="utf-8") as f:
            f.write("beta\n")
        git(repo, "add", "notes.txt")
        git(
            repo,
            "commit",
            "-m",
            "B: append beta",
            extra_env={
                "GIT_AUTHOR_DATE": "1000000001 +0000",
                "GIT_COMMITTER_DATE": "1000000001 +0000",
            },
        )
        commit_b = git(repo, "rev-parse", "HEAD").strip()
        blob_b = git(repo, "rev-parse", f"{commit_b}:notes.txt").strip()
        git(repo, "branch", "topic")

        # Commit C
        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        git(repo, "add", "todo.txt")
        git(
            repo,
            "commit",
            "-m",
            "C: add todo",
            extra_env={
                "GIT_AUTHOR_DATE": "1000000002 +0000",
                "GIT_COMMITTER_DATE": "1000000002 +0000",
            },
        )
        commit_c = git(repo, "rev-parse", "HEAD").strip()
        blob_c_todo = git(repo, "rev-parse", f"{commit_c}:todo.txt").strip()

        # Capture state BEFORE checkout
        head_ref_before = git(repo, "symbolic-ref", "HEAD").strip()
        head_commit_before = git(repo, "rev-parse", "HEAD").strip()
        main_ref_before = git(repo, "rev-parse", "refs/heads/main").strip()
        topic_ref_before = git(repo, "rev-parse", "refs/heads/topic").strip()
        head_tree_before = git(repo, "rev-parse", "HEAD^{tree}").strip()
        index_tree_before = git(repo, "write-tree").strip()
        status_before = git(repo, "status", "--short", "--branch").strip()
        ls_files_before = git(repo, "ls-files").splitlines()
        worktree_files_before = sorted([p.name for p in repo.glob("*.txt")])
        notes_content_before = (repo / "notes.txt").read_text(encoding="utf-8")
        todo_content_before = (repo / "todo.txt").read_text(encoding="utf-8")
        log_before = git(repo, "log", "--oneline", "--decorate", "--all", "--graph").strip()

        # Execute the command-line operation
        git(repo, "checkout", "topic")

        # Capture state AFTER checkout
        head_ref_after = git(repo, "symbolic-ref", "HEAD").strip()
        head_commit_after = git(repo, "rev-parse", "HEAD").strip()
        main_ref_after = git(repo, "rev-parse", "refs/heads/main").strip()
        topic_ref_after = git(repo, "rev-parse", "refs/heads/topic").strip()
        head_tree_after = git(repo, "rev-parse", "HEAD^{tree}").strip()
        index_tree_after = git(repo, "write-tree").strip()
        status_after = git(repo, "status", "--short", "--branch").strip()
        ls_files_after = git(repo, "ls-files").splitlines()
        worktree_files_after = sorted([p.name for p in repo.glob("*.txt")])
        notes_content_after = (repo / "notes.txt").read_text(encoding="utf-8")
        todo_exists_after = (repo / "todo.txt").exists()
        log_after = git(repo, "log", "--oneline", "--decorate", "--all", "--graph").strip()

        # Ensure working tree diff and cached diff are clean
        git(repo, "diff", "--exit-code")
        git(repo, "diff", "--cached", "--exit-code")

        return {
            "commits": {"A": commit_a, "B": commit_b, "C": commit_c},
            "blobs": {"notes_A": blob_a, "notes_B": blob_b, "todo_C": blob_c_todo},
            "before": {
                "head_ref": head_ref_before,
                "head_commit": head_commit_before,
                "main_ref": main_ref_before,
                "topic_ref": topic_ref_before,
                "head_tree": head_tree_before,
                "index_tree": index_tree_before,
                "status": status_before,
                "ls_files": ls_files_before,
                "worktree_files": worktree_files_before,
                "notes": notes_content_before,
                "todo": todo_content_before,
                "log": log_before,
            },
            "after": {
                "head_ref": head_ref_after,
                "head_commit": head_commit_after,
                "main_ref": main_ref_after,
                "topic_ref": topic_ref_after,
                "head_tree": head_tree_after,
                "index_tree": index_tree_after,
                "status": status_after,
                "ls_files": ls_files_after,
                "worktree_files": worktree_files_after,
                "notes": notes_content_after,
                "todo_exists": todo_exists_after,
                "log": log_after,
            },
        }


def main() -> None:
    first = run_once(1)
    second = run_once(2)
    results = [first, second]

    actual_lines = [
        "Run 1",
        f"commit A: {first['commits']['A']}",
        f"commit B: {first['commits']['B']}",
        f"commit C: {first['commits']['C']}",
        "Before checkout topic:",
        f"  HEAD ref: {first['before']['head_ref']}",
        f"  HEAD commit: {first['before']['head_commit']}",
        f"  main ref: {first['before']['main_ref']}",
        f"  topic ref: {first['before']['topic_ref']}",
        f"  index tree: {first['before']['index_tree']}",
        f"  status: {first['before']['status']}",
        f"  index files: {first['before']['ls_files']}",
        f"  worktree files: {first['before']['worktree_files']}",
        "Operation: git checkout topic",
        "After checkout topic:",
        f"  HEAD ref: {first['after']['head_ref']}",
        f"  HEAD commit: {first['after']['head_commit']}",
        f"  main ref: {first['after']['main_ref']}",
        f"  topic ref: {first['after']['topic_ref']}",
        f"  index tree: {first['after']['index_tree']}",
        f"  status: {first['after']['status']}",
        f"  index files: {first['after']['ls_files']}",
        f"  worktree files: {first['after']['worktree_files']}",
        f"  todo.txt exists: {first['after']['todo_exists']}",
        "",
        "Run 2",
        f"commit A: {second['commits']['A']}",
        f"commit B: {second['commits']['B']}",
        f"commit C: {second['commits']['C']}",
        "Before checkout topic:",
        f"  HEAD ref: {second['before']['head_ref']}",
        f"  HEAD commit: {second['before']['head_commit']}",
        f"  main ref: {second['before']['main_ref']}",
        f"  topic ref: {second['before']['topic_ref']}",
        f"  index tree: {second['before']['index_tree']}",
        f"  status: {second['before']['status']}",
        f"  index files: {second['before']['ls_files']}",
        f"  worktree files: {second['before']['worktree_files']}",
        "Operation: git checkout topic",
        "After checkout topic:",
        f"  HEAD ref: {second['after']['head_ref']}",
        f"  HEAD commit: {second['after']['head_commit']}",
        f"  main ref: {second['after']['main_ref']}",
        f"  topic ref: {second['after']['topic_ref']}",
        f"  index tree: {second['after']['index_tree']}",
        f"  status: {second['after']['status']}",
        f"  index files: {second['after']['ls_files']}",
        f"  worktree files: {second['after']['worktree_files']}",
        f"  todo.txt exists: {second['after']['todo_exists']}",
        "",
    ]
    (ROOT / "actual.txt").write_text("\n".join(actual_lines), encoding="utf-8")

    for r in results:
        # State facts & assertions:
        # 1. Refs & HEAD transition
        assert r["before"]["head_ref"] == "refs/heads/main"
        assert r["before"]["head_commit"] == r["commits"]["C"]
        assert r["before"]["main_ref"] == r["commits"]["C"]
        assert r["before"]["topic_ref"] == r["commits"]["B"]

        assert r["after"]["head_ref"] == "refs/heads/topic"
        assert r["after"]["head_commit"] == r["commits"]["B"]
        assert r["after"]["main_ref"] == r["commits"]["C"]
        assert r["after"]["topic_ref"] == r["commits"]["B"]

        # 2. Ancestry facts
        assert r["commits"]["B"] != r["commits"]["A"]
        assert r["commits"]["C"] != r["commits"]["B"]

        # 3. Index & Worktree transitions
        assert r["before"]["head_tree"] == r["before"]["index_tree"]
        assert r["after"]["head_tree"] == r["after"]["index_tree"]
        assert r["before"]["head_tree"] != r["after"]["head_tree"]

        assert r["before"]["ls_files"] == ["notes.txt", "todo.txt"]
        assert r["before"]["worktree_files"] == ["notes.txt", "todo.txt"]

        assert r["after"]["ls_files"] == ["notes.txt"]
        assert r["after"]["worktree_files"] == ["notes.txt"]
        assert r["after"]["todo_exists"] is False

        # 4. Content assertions
        assert r["before"]["notes"] == "alpha\nbeta\n"
        assert r["before"]["todo"] == "one\n"
        assert r["after"]["notes"] == "alpha\nbeta\n"

        # 5. Status transitions
        assert r["before"]["status"] == "## main"
        assert r["after"]["status"] == "## topic"

    # Determinism across runs
    assert first["before"] == second["before"]
    assert first["after"] == second["after"]
    assert first["commits"] == second["commits"]

    print("PASS: command line state transition verified across refs, commit ancestry, index, and working tree.")


if __name__ == "__main__":
    main()
