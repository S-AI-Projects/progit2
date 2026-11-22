#!/usr/bin/env python3
"""Automated verification check for R31-T001."""

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
    with tempfile.TemporaryDirectory(prefix=f"R31-T001-run{run_index}-") as tmpdir:
        repo = Path(tmpdir) / "env-diff-demo"
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

        # Execute diff with GIT_DIFF_OPTS
        diff_u0 = git(
            repo, "diff", "topic^", "topic", extra_env={"GIT_DIFF_OPTS": "-u0"}
        )
        diff_unified0 = git(
            repo,
            "diff",
            "topic^",
            "topic",
            extra_env={"GIT_DIFF_OPTS": "--unified=0"},
        )
        assert diff_u0 == diff_unified0

        # Execute diff with GIT_EXTERNAL_DIFF
        external_diff_out = git(
            repo,
            "diff",
            "topic^",
            "topic",
            extra_env={"GIT_EXTERNAL_DIFF": "echo"},
        ).strip()

        status = git(repo, "status", "--short", "--branch")
        log = git(repo, "log", "--oneline", "--decorate", "--all", "--graph")
        head = git(repo, "rev-parse", "HEAD").strip()
        head_ref = git(repo, "symbolic-ref", "HEAD").strip()
        main_ref = git(repo, "rev-parse", "refs/heads/main").strip()
        topic_ref = git(repo, "rev-parse", "refs/heads/topic").strip()
        head_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
        index_tree = git(repo, "write-tree").strip()

        # Ensure working tree diff and cached diff are clean
        git(repo, "diff", "--exit-code")
        git(repo, "diff", "--cached", "--exit-code")

        files = {
            "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        }

        return {
            "commits": {"A": commit_a, "B": commit_b, "C": commit_c},
            "blobs": {"A": blob_a, "B": blob_b},
            "refs": {"main": main_ref, "topic": topic_ref, "HEAD": head},
            "head_ref": head_ref,
            "head_tree": head_tree,
            "index_tree": index_tree,
            "files": files,
            "status": status,
            "diff": diff_u0,
            "external_diff": external_diff_out,
            "log": log,
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
        f"main: {first['refs']['main']}",
        f"topic: {first['refs']['topic']}",
        f"index tree: {first['index_tree']}",
        "status:",
        first["status"].rstrip(),
        "diff (GIT_DIFF_OPTS=\"--unified=0\"): ",
        first["diff"].rstrip(),
        "log:",
        first["log"].rstrip(),
        "",
        "Run 2",
        f"commit A: {second['commits']['A']}",
        f"commit B: {second['commits']['B']}",
        f"commit C: {second['commits']['C']}",
        f"main: {second['refs']['main']}",
        f"topic: {second['refs']['topic']}",
        f"index tree: {second['index_tree']}",
        "status:",
        second["status"].rstrip(),
        "diff (GIT_DIFF_OPTS=\"--unified=0\"): ",
        second["diff"].rstrip(),
        "log:",
        second["log"].rstrip(),
        "",
    ]
    (ROOT / "actual.txt").write_text("\n".join(actual_lines), encoding="utf-8")

    for r in results:
        # Meaningful state facts:
        # 1. File contents
        assert r["files"] == {
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
        }
        # 2. Branch refs and HEAD
        assert r["refs"]["main"] == r["commits"]["C"]
        assert r["refs"]["topic"] == r["commits"]["B"]
        assert r["refs"]["HEAD"] == r["commits"]["C"]
        assert r["head_ref"] == "refs/heads/main"
        assert r["commits"]["B"] != r["commits"]["A"]
        assert r["commits"]["C"] != r["commits"]["B"]
        # 3. Clean worktree and index
        assert r["head_tree"] == r["index_tree"]
        assert r["status"] == "## main\n"
        # 4. Correct diff output without context lines
        assert "diff --git a/notes.txt b/notes.txt" in r["diff"]
        assert "+beta" in r["diff"]
        assert "@@ -1,0 +2 @@" in r["diff"]
        # 5. Correct external diff invocation
        assert r["external_diff"].startswith("notes.txt")
        assert r["blobs"]["A"] in r["external_diff"]
        assert r["blobs"]["B"] in r["external_diff"]
        # 6. Correct log graph
        assert r["log"].splitlines() == [
            f"* {r['commits']['C'][:7]} (HEAD -> main) C: add todo",
            f"* {r['commits']['B'][:7]} (topic) B: append beta",
            f"* {r['commits']['A'][:7]} A: create notes",
        ]

    # Determinism / reproducibility across runs
    assert first["files"] == second["files"]
    assert first["status"] == second["status"]
    assert first["diff"] == second["diff"]
    assert first["log"] == second["log"]
    assert first["refs"] == second["refs"]
    assert first["index_tree"] == second["index_tree"]

    print("PASS: both temporary repositories match the documented files, refs, diff, log, and clean index.")


if __name__ == "__main__":
    main()
