#!/usr/bin/env python3
"""Integration check for adding a forgotten file with git commit --amend."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


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


def create_fixture(repo):
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

    (repo / "forgotten_file").write_text("remember this\n", encoding="utf-8")
    git(repo, "add", "forgotten_file")
    return {"A": commit_a, "B": commit_b, "C": commit_c}


def observe(repo, original, amended):
    head = git(repo, "rev-parse", "HEAD").strip()
    main = git(repo, "rev-parse", "refs/heads/main").strip()
    topic = git(repo, "rev-parse", "refs/heads/topic").strip()
    parent = git(repo, "rev-parse", "HEAD^").strip()
    history = git(repo, "rev-list", "--reverse", "main").splitlines()
    paths = git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    head_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    index_tree = git(repo, "write-tree").strip()
    status = git(repo, "status", "--short", "--branch")
    files = {
        "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
        "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        "forgotten_file": (repo / "forgotten_file").read_text(encoding="utf-8"),
    }
    return {
        "head": head,
        "main": main,
        "topic": topic,
        "parent": parent,
        "history": history,
        "paths": paths,
        "head_tree": head_tree,
        "index_tree": index_tree,
        "status": status,
        "files": files,
        "old_tip_reachable": original["C"] in history,
        "amend_requested": amended,
    }


def is_amended(state, original):
    return (
        state["amend_requested"]
        and state["head"] != original["C"]
        and state["main"] == state["head"]
        and state["topic"] == original["B"]
        and state["parent"] == original["B"]
        and len(state["history"]) == 3
        and not state["old_tip_reachable"]
        and "forgotten_file" in state["paths"]
        and state["head_tree"] == state["index_tree"]
        and state["status"] == "## main\n"
        and state["files"]
        == {
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
            "forgotten_file": "remember this\n",
        }
    )


def run_scenario(amend):
    with tempfile.TemporaryDirectory(prefix="undoing-amend-") as directory:
        repo = Path(directory)
        original = create_fixture(repo)
        if amend:
            git(repo, "commit", "--amend", extra_env={"GIT_EDITOR": "true"})
        state = observe(repo, original, amend)
        if amend:
            assert is_amended(state, original)
        else:
            assert state["head"] == original["C"]
            assert state["main"] == original["C"]
            assert state["topic"] == original["B"]
            assert len(state["history"]) == 3
            assert "forgotten_file" not in state["paths"]
            assert state["index_tree"] != state["head_tree"]
            assert state["status"] == "## main\nA  forgotten_file\n"
            assert not is_amended(state, original)
        return {"original": original, "state": state}


def main():
    amended = run_scenario(amend=True)
    omitted = run_scenario(amend=False)
    assert is_amended(amended["state"], amended["original"])
    assert not is_amended(omitted["state"], omitted["original"])
    print(
        json.dumps(
            {
                "result": "PASS",
                "amended_scenario": amended,
                "omitted_amend_control": omitted,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
