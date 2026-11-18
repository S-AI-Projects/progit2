#!/usr/bin/env python3
"""Verify the repository prerequisites shown in the PowerShell guide."""

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


def verify_repository(root):
    repo = root / "repository"
    repo.mkdir()
    global_config = root / "global.gitconfig"
    global_config.write_text(
        "[user]\n\tname = Existing Global User\n\temail = global@example.invalid\n",
        encoding="utf-8",
    )
    global_before = global_config.read_bytes()
    env = {
        **os.environ,
        **IDENTITY,
        "GIT_CONFIG_GLOBAL": str(global_config),
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

    (repo / "draft.txt").write_text("in progress\n", encoding="utf-8")
    git(repo, "add", "draft.txt", env=env)

    branch = git(repo, "branch", "--show-current", env=env)
    status = git(repo, "status", "--short", "--branch", env=env)
    head = git(repo, "rev-parse", "HEAD", env=env)
    topic = git(repo, "rev-parse", "refs/heads/topic", env=env)
    history = git(repo, "rev-list", "--reverse", "main", env=env).splitlines()
    staged = git(repo, "diff", "--cached", "--name-status", env=env)
    staged_contents = git(repo, "show", ":draft.txt", env=env)
    local_name = git(repo, "config", "--local", "--get", "user.name", env=env)
    local_email = git(repo, "config", "--local", "--get", "user.email", env=env)
    config_origin = git(
        repo,
        "config",
        "--show-origin",
        "--get",
        "user.email",
        env=env,
    )

    assert branch == "main"
    assert status == "## main\nA  draft.txt"
    assert head == commit_c
    assert topic == commit_b
    assert history == [commit_a, commit_b, commit_c]
    assert staged == "A\tdraft.txt"
    assert staged_contents == "in progress"
    assert local_name == "Course Student"
    assert local_email == "student@example.invalid"
    assert ".git/config" in config_origin
    assert global_config.read_bytes() == global_before
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert (repo / "todo.txt").read_text(encoding="utf-8") == "one\n"

    return {
        "branch": branch,
        "head": head,
        "history": history,
        "topic": topic,
        "status": status,
        "staged_diff": staged,
        "staged_contents": staged_contents,
        "local_identity": {"name": local_name, "email": local_email},
        "identity_config_origin": config_origin,
        "global_config_unchanged": global_config.read_bytes() == global_before,
        "files": {
            "notes.txt": (repo / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (repo / "todo.txt").read_text(encoding="utf-8"),
        },
    }


def main():
    with tempfile.TemporaryDirectory(prefix="powershell-prerequisites-") as directory:
        state = verify_repository(Path(directory))
    print(json.dumps({"result": "PASS", "repository_state": state}, indent=2))


if __name__ == "__main__":
    main()
