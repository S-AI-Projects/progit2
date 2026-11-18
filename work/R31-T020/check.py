#!/usr/bin/env python3
"""Verify the documented no-op merge when topic is already in main."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


IDENTITY = {
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
    "LC_ALL": "C",
    "TZ": "UTC",
}


def git(repo, *args, env):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def commit(repo, message, day, env):
    date = f"2020-01-{day:02d}T00:00:00+0000"
    git(
        repo,
        "commit",
        "-m",
        message,
        env={**env, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
    )


def snapshot(repo, env):
    return {
        "head": git(repo, "rev-parse", "HEAD", env=env),
        "head_ref": git(repo, "symbolic-ref", "HEAD", env=env),
        "main": git(repo, "rev-parse", "refs/heads/main", env=env),
        "topic": git(repo, "rev-parse", "refs/heads/topic", env=env),
        "branch_refs": git(repo, "show-ref", "--heads", env=env).splitlines(),
        "head_tree": git(repo, "rev-parse", "HEAD^{tree}", env=env),
        "index_tree": git(repo, "write-tree", env=env),
        "history": git(
            repo, "rev-list", "--reverse", "--oneline", "main", env=env
        ).splitlines(),
        "paths": git(
            repo, "ls-tree", "-r", "--name-only", "HEAD", env=env
        ).splitlines(),
        "status": git(repo, "status", "--short", "--branch", env=env),
        "notes": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo": (repo / "todo.txt").read_text(encoding="utf-8"),
    }


def main():
    with tempfile.TemporaryDirectory(prefix="R31-T020-") as directory:
        root = Path(directory)
        repo = root / "repository"
        repo.mkdir()
        env = {
            **os.environ,
            **IDENTITY,
            "GIT_CONFIG_GLOBAL": str(root / "global.gitconfig"),
        }

        git(repo, "init", env=env)
        git(repo, "checkout", "-b", "main", env=env)
        git(repo, "config", "--local", "user.name", "Course Student", env=env)
        git(
            repo,
            "config",
            "--local",
            "user.email",
            "student@example.invalid",
            env=env,
        )

        (repo / "notes.txt").write_text("alpha\n", encoding="utf-8")
        git(repo, "add", "notes.txt", env=env)
        commit(repo, "A: create notes", 1, env)
        commit_a = git(repo, "rev-parse", "HEAD", env=env)

        with (repo / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        git(repo, "add", "notes.txt", env=env)
        commit(repo, "B: append beta", 2, env)
        commit_b = git(repo, "rev-parse", "HEAD", env=env)
        git(repo, "branch", "topic", env=env)

        (repo / "todo.txt").write_text("one\n", encoding="utf-8")
        git(repo, "add", "todo.txt", env=env)
        commit(repo, "C: add todo", 3, env)
        commit_c = git(repo, "rev-parse", "HEAD", env=env)

        before = snapshot(repo, env)
        assert before["head"] == commit_c
        assert before["main"] == commit_c
        assert before["topic"] == commit_b
        assert before["head_ref"] == "refs/heads/main"
        assert len(before["history"]) == 3
        assert before["paths"] == ["notes.txt", "todo.txt"]
        assert before["status"] == "## main"
        assert before["notes"] == "alpha\nbeta\n"
        assert before["todo"] == "one\n"
        git(repo, "merge", "topic", env=env)
        after = snapshot(repo, env)

        assert after == before
        assert after["head"] == commit_c
        assert after["main"] == commit_c
        assert after["topic"] == commit_b
        assert after["head_tree"] == after["index_tree"]
        assert after["status"] == "## main"
        assert len(after["history"]) == 3

        output = json.dumps(
            {
                "result": "PASS",
                "merge": "git merge topic",
                "before": before,
                "after": after,
            },
            indent=2,
            sort_keys=True,
        )
        (Path(__file__).resolve().parent / "actual.txt").write_text(
            output + "\n", encoding="utf-8"
        )
        print(output)


if __name__ == "__main__":
    main()
