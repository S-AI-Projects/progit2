#!/usr/bin/env python3
"""Verify the word-diff walkthrough in isolated temporary Git repositories."""

from pathlib import Path
import os
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


def git(repo, *args, env=None):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **BASE_ENV, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def make_repository(path):
    git(path, "init", "--initial-branch=main")
    git(path, "config", "user.name", "Course Student")
    git(path, "config", "user.email", "student@example.invalid")

    (path / "notes.txt").write_text("alpha\n", encoding="utf-8")
    git(path, "add", "notes.txt")
    git(
        path,
        "commit",
        "-m",
        "A: create notes",
        env={
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+0000",
        },
    )

    with (path / "notes.txt").open("a", encoding="utf-8") as notes:
        notes.write("beta\n")
    git(path, "add", "notes.txt")
    git(
        path,
        "commit",
        "-m",
        "B: append beta",
        env={
            "GIT_AUTHOR_DATE": "2020-01-02T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2020-01-02T00:00:00+0000",
        },
    )
    git(path, "branch", "topic")

    (path / "todo.txt").write_text("one\n", encoding="utf-8")
    git(path, "add", "todo.txt")
    git(
        path,
        "commit",
        "-m",
        "C: add todo",
        env={
            "GIT_AUTHOR_DATE": "2020-01-03T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2020-01-03T00:00:00+0000",
        },
    )

    diff = git(path, "diff", "--word-diff", "topic^", "topic")
    status = git(path, "status", "--short", "--branch")
    log = git(path, "log", "--oneline", "--decorate", "--all", "--graph")
    refs = {
        "main": git(path, "rev-parse", "main").strip(),
        "topic": git(path, "rev-parse", "topic").strip(),
    }
    commits = {
        "A": git(path, "rev-parse", "main~2").strip(),
        "B": git(path, "rev-parse", "main~1").strip(),
        "C": git(path, "rev-parse", "main").strip(),
    }
    head_tree = git(path, "rev-parse", "HEAD^{tree}").strip()
    index_tree = git(path, "write-tree").strip()
    files = {
        "notes.txt": (path / "notes.txt").read_text(encoding="utf-8"),
        "todo.txt": (path / "todo.txt").read_text(encoding="utf-8"),
    }

    git(path, "diff", "--exit-code")
    git(path, "diff", "--cached", "--exit-code")

    return {
        "diff": diff,
        "status": status,
        "log": log,
        "refs": refs,
        "commits": commits,
        "head_tree": head_tree,
        "index_tree": index_tree,
        "files": files,
    }


def main():
    results = []
    for _ in range(2):
        with tempfile.TemporaryDirectory(prefix="R31-T011-") as directory:
            results.append(make_repository(Path(directory)))

    first, second = results
    actual = [
        "Run 1",
        f"commit A: {first['commits']['A']}",
        f"commit B: {first['commits']['B']}",
        f"commit C: {first['commits']['C']}",
        f"main: {first['refs']['main']}",
        f"topic: {first['refs']['topic']}",
        f"index tree: {first['index_tree']}",
        "status:",
        first["status"].rstrip(),
        "word diff:",
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
        "word diff:",
        second["diff"].rstrip(),
        "log:",
        second["log"].rstrip(),
        "",
    ]
    (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    for result in results:
        assert result["files"] == {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"}
        assert result["refs"]["main"] == result["commits"]["C"]
        assert result["refs"]["topic"] == result["commits"]["B"]
        assert result["commits"]["B"] != result["commits"]["A"]
        assert result["commits"]["C"] != result["commits"]["B"]
        assert result["status"] == "## main\n"
        assert result["head_tree"] == result["index_tree"]
        assert "alpha\n{+beta+}" in result["diff"]
        assert result["log"].splitlines() == [
            f"* {result['commits']['C'][:7]} (HEAD -> main) C: add todo",
            f"* {result['commits']['B'][:7]} (topic) B: append beta",
            f"* {result['commits']['A'][:7]} A: create notes",
        ]

    assert first["files"] == second["files"]
    assert first["status"] == second["status"]
    assert first["diff"] == second["diff"]
    assert first["log"] == second["log"]
    assert first["refs"] == second["refs"]
    assert first["index_tree"] == second["index_tree"]
    print("PASS: both temporary repositories match the documented files, refs, diff, log, and clean index.")


if __name__ == "__main__":
    main()
