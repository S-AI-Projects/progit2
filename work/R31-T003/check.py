#!/usr/bin/env python3
"""Automated verification check for R31-T003: Recovery exercise in credentials."""

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
    with tempfile.TemporaryDirectory(prefix=f"R31-T003-run{run_index}-") as tmpdir:
        repo = Path(tmpdir) / "creds-recovery-demo"
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
        git(repo, "branch", "topic")

        # Commit C (recovery point)
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
        recovery_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()

        # Introduce reversible mistake: mistakenly write sensitive credential into notes.txt and stage it
        (repo / "notes.txt").write_text("alpha\nbeta\npassword=s3cre7\n", encoding="utf-8")
        git(repo, "add", "notes.txt")
        status_mistake = git(repo, "status", "--short", "--branch").strip()
        index_tree_mistake = git(repo, "write-tree").strip()

        # Execute recovery command
        git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", "notes.txt")

        # Capture state after recovery
        head_after = git(repo, "rev-parse", "HEAD").strip()
        head_ref_after = git(repo, "symbolic-ref", "HEAD").strip()
        main_after = git(repo, "rev-parse", "refs/heads/main").strip()
        topic_after = git(repo, "rev-parse", "refs/heads/topic").strip()
        tree_after = git(repo, "rev-parse", "HEAD^{tree}").strip()
        index_tree_after = git(repo, "write-tree").strip()
        status_after = git(repo, "status", "--short", "--branch").strip()
        files_after = {
            "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        }
        log_after = git(repo, "log", "--oneline", "--decorate", "--all", "--graph").strip()

        # Ensure working tree diff and cached diff are clean
        git(repo, "diff", "--exit-code")
        git(repo, "diff", "--cached", "--exit-code")

        return {
            "commits": {"A": commit_a, "B": commit_b, "C": commit_c},
            "recovery_tree": recovery_tree,
            "mistake": {
                "status": status_mistake,
                "index_tree": index_tree_mistake,
            },
            "after": {
                "head": head_after,
                "head_ref": head_ref_after,
                "main": main_after,
                "topic": topic_after,
                "tree": tree_after,
                "index_tree": index_tree_after,
                "status": status_after,
                "files": files_after,
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
        f"commit C / recovery commit: {first['commits']['C']}",
        f"recovery tree: {first['recovery_tree']}",
        "Mistake state:",
        f"  status: {first['mistake']['status']}",
        f"  index tree: {first['mistake']['index_tree']}",
        "Recovery command: git restore --source=HEAD --staged --worktree -- notes.txt",
        "Recovered state:",
        f"  HEAD: {first['after']['head']}",
        f"  HEAD ref: {first['after']['head_ref']}",
        f"  main ref: {first['after']['main']}",
        f"  topic ref: {first['after']['topic']}",
        f"  tree at HEAD: {first['after']['tree']}",
        f"  index tree: {first['after']['index_tree']}",
        f"  status: {first['after']['status']}",
        f"  files: {first['after']['files']}",
        "",
        "Run 2",
        f"commit A: {second['commits']['A']}",
        f"commit B: {second['commits']['B']}",
        f"commit C / recovery commit: {second['commits']['C']}",
        f"recovery tree: {second['recovery_tree']}",
        "Mistake state:",
        f"  status: {second['mistake']['status']}",
        f"  index tree: {second['mistake']['index_tree']}",
        "Recovery command: git restore --source=HEAD --staged --worktree -- notes.txt",
        "Recovered state:",
        f"  HEAD: {second['after']['head']}",
        f"  HEAD ref: {second['after']['head_ref']}",
        f"  main ref: {second['after']['main']}",
        f"  topic ref: {second['after']['topic']}",
        f"  tree at HEAD: {second['after']['tree']}",
        f"  index tree: {second['after']['index_tree']}",
        f"  status: {second['after']['status']}",
        f"  files: {second['after']['files']}",
        "",
    ]
    (ROOT / "actual.txt").write_text("\n".join(actual_lines), encoding="utf-8")

    for r in results:
        # Meaningful state facts:
        # 1. Mistake state changed index tree
        assert r["mistake"]["index_tree"] != r["recovery_tree"]
        assert "M  notes.txt" in r["mistake"]["status"]

        # 2. Recovered tree matches saved tree hash and clean working tree
        assert r["after"]["tree"] == r["recovery_tree"]
        assert r["after"]["index_tree"] == r["recovery_tree"]
        assert r["after"]["status"] == "## main"
        assert r["after"]["files"] == {
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
        }

        # 3. Preserved refs & HEAD
        assert r["after"]["head"] == r["commits"]["C"]
        assert r["after"]["main"] == r["commits"]["C"]
        assert r["after"]["topic"] == r["commits"]["B"]
        assert r["after"]["head_ref"] == "refs/heads/main"

        # 4. Preserved ancestry
        assert r["commits"]["B"] != r["commits"]["A"]
        assert r["commits"]["C"] != r["commits"]["B"]

    # Determinism across runs
    assert first["recovery_tree"] == second["recovery_tree"]
    assert first["after"] == second["after"]
    assert first["commits"] == second["commits"]

    print("PASS: restore returned the named file and index to the saved commit tree; HEAD and refs were preserved.")


if __name__ == "__main__":
    main()
