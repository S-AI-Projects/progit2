#!/usr/bin/env python3
"""Verify that pushing the checked-out topic branch leaves main and remote HEAD fixed."""

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
    with tempfile.TemporaryDirectory(prefix="R31-T014-") as directory:
        root = Path(directory)
        repo = root / "work"
        repo.mkdir()
        remote = root / "remote.git"

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

        git(repo, "init", "--bare", "--initial-branch=main", str(remote))
        remote_url = remote.as_uri()
        git(repo, "remote", "add", "origin", remote_url)
        push_main = git(repo, "push", "-u", "origin", "main")
        main_local_before_topic = git(repo, "rev-parse", "refs/heads/main").strip()
        main_remote_before_topic = git(
            repo, "--git-dir", str(remote), "rev-parse", "refs/heads/main"
        ).strip()
        remote_head_before_topic = git(
            repo, "--git-dir", str(remote), "symbolic-ref", "HEAD"
        ).strip()
        remote_topic_before = git(
            repo,
            "--git-dir",
            str(remote),
            "for-each-ref",
            "--format=%(objectname)",
            "refs/heads/topic",
        )

        git(repo, "switch", "topic")
        push_topic = git(repo, "push", "-u", "origin", "topic")

        current_branch = git(repo, "branch", "--show-current").strip()
        head_target = git(repo, "symbolic-ref", "HEAD").strip()
        main_local_after = git(repo, "rev-parse", "refs/heads/main").strip()
        topic_local_after = git(repo, "rev-parse", "refs/heads/topic").strip()
        main_remote_after = git(
            repo, "--git-dir", str(remote), "rev-parse", "refs/heads/main"
        ).strip()
        topic_remote_after = git(
            repo, "--git-dir", str(remote), "rev-parse", "refs/heads/topic"
        ).strip()
        remote_head_after = git(
            repo, "--git-dir", str(remote), "symbolic-ref", "HEAD"
        ).strip()
        origin_main = git(repo, "rev-parse", "refs/remotes/origin/main").strip()
        origin_topic = git(repo, "rev-parse", "refs/remotes/origin/topic").strip()
        status = git(repo, "status", "--short", "--branch")
        local_branches = git(
            repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"
        )
        remote_branches = git(
            repo,
            "--git-dir",
            str(remote),
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/heads",
        )

        assert main_local_before_topic == commit_c
        assert main_remote_before_topic == commit_c
        assert remote_head_before_topic == "refs/heads/main"
        assert remote_topic_before == ""
        assert current_branch == "topic"
        assert head_target == "refs/heads/topic"
        assert main_local_after == commit_c
        assert main_remote_after == main_remote_before_topic == commit_c
        assert topic_local_after == commit_b
        assert topic_remote_after == commit_b
        assert remote_head_after == remote_head_before_topic
        assert origin_main == commit_c
        assert origin_topic == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert local_branches.splitlines() == [
            f"refs/heads/main {commit_c}",
            f"refs/heads/topic {commit_b}",
        ]
        assert remote_branches.splitlines() == [
            f"refs/heads/main {commit_c}",
            f"refs/heads/topic {commit_b}",
        ]
        assert status == "## topic...origin/topic\n"
        assert (repo / "notes.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"
        assert not (repo / "todo.txt").exists()
        git(repo, "diff", "--exit-code")
        git(repo, "diff", "--cached", "--exit-code")

        actual = [
            f"commit A: {commit_a}",
            f"commit B: {commit_b}",
            f"commit C: {commit_c}",
            f"local main before topic push: {main_local_before_topic}",
            f"remote main before topic push: {main_remote_before_topic}",
            f"remote topic before topic push: {remote_topic_before!r}",
            f"remote HEAD before topic push: {remote_head_before_topic}",
            "push main output:",
            push_main.rstrip(),
            "push topic output:",
            push_topic.rstrip(),
            f"current branch: {current_branch}",
            f"HEAD target: {head_target}",
            f"local main after topic push: {main_local_after}",
            f"local topic after topic push: {topic_local_after}",
            f"remote main after topic push: {main_remote_after}",
            f"remote topic after topic push: {topic_remote_after}",
            f"origin/main: {origin_main}",
            f"origin/topic: {origin_topic}",
            f"remote HEAD after topic push: {remote_head_after}",
            "local branch refs:",
            local_branches.rstrip(),
            "remote branch refs:",
            remote_branches.rstrip(),
            "status:",
            status.rstrip(),
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: pushing topic created only the remote topic ref; local/remote main and remote HEAD stayed fixed.")


if __name__ == "__main__":
    main()
