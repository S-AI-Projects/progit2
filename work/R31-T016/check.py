#!/usr/bin/env python3
"""Compare checked-out and bare clones of the same local repository."""

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


def git(cwd, *args, extra_env=None):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env={**os.environ, **BASE_ENV, **(extra_env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def git_bare(git_dir, *args):
    return git(git_dir.parent, "--git-dir", str(git_dir), *args)


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
    with tempfile.TemporaryDirectory(prefix="R31-T016-") as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        remote = root / "remote.git"
        working = root / "working"
        bare = root / "bare.git"

        git(source, "init", "--initial-branch=main")
        git(source, "config", "user.name", "Course Student")
        git(source, "config", "user.email", "student@example.invalid")

        (source / "notes.txt").write_text("alpha\n", encoding="utf-8")
        git(source, "add", "notes.txt")
        commit(source, "A: create notes", 1)
        commit_a = git(source, "rev-parse", "HEAD").strip()

        with (source / "notes.txt").open("a", encoding="utf-8") as notes:
            notes.write("beta\n")
        git(source, "add", "notes.txt")
        commit(source, "B: append beta", 2)
        commit_b = git(source, "rev-parse", "HEAD").strip()
        git(source, "branch", "topic")

        (source / "todo.txt").write_text("one\n", encoding="utf-8")
        git(source, "add", "todo.txt")
        commit(source, "C: add todo", 3)
        commit_c = git(source, "rev-parse", "HEAD").strip()
        tree_c = git(source, "rev-parse", f"{commit_c}^{{tree}}").strip()

        git(source, "init", "--bare", "--initial-branch=main", str(remote))
        remote_url = remote.as_uri()
        git(source, "remote", "add", "origin", remote_url)
        git(source, "push", "origin", "main", "topic")

        remote_main_before = git(
            source, "--git-dir", str(remote), "rev-parse", "refs/heads/main"
        ).strip()
        remote_topic_before = git(
            source, "--git-dir", str(remote), "rev-parse", "refs/heads/topic"
        ).strip()
        remote_head_before = git(
            source, "--git-dir", str(remote), "symbolic-ref", "HEAD"
        ).strip()

        git(root, "clone", remote_url, str(working))
        git(root, "clone", "--bare", remote_url, str(bare))

        working_head = git(working, "symbolic-ref", "HEAD").strip()
        working_main = git(working, "rev-parse", "refs/heads/main").strip()
        working_origin_main = git(working, "rev-parse", "refs/remotes/origin/main").strip()
        working_origin_topic = git(working, "rev-parse", "refs/remotes/origin/topic").strip()
        working_head_tree = git(working, "rev-parse", "HEAD^{tree}").strip()
        working_index_tree = git(working, "write-tree").strip()
        working_status = git(working, "status", "--short", "--branch")
        working_files = {
            "notes.txt": (working / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (working / "todo.txt").read_text(encoding="utf-8"),
        }
        working_has_topic_head = git(
            working, "for-each-ref", "--format=%(objectname)", "refs/heads/topic"
        ).strip()

        bare_state = git_bare(bare, "rev-parse", "--is-bare-repository").strip()
        bare_head = git_bare(bare, "symbolic-ref", "HEAD").strip()
        bare_main = git_bare(bare, "rev-parse", "refs/heads/main").strip()
        bare_topic = git_bare(bare, "rev-parse", "refs/heads/topic").strip()
        bare_heads = git_bare(
            bare,
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/heads",
        )
        bare_remote_refs = git_bare(
            bare,
            "for-each-ref",
            "--format=%(refname)",
            "refs/remotes",
        )
        bare_index_exists = (bare / "index").exists()
        bare_has_worktree_files = (bare / "notes.txt").exists() or (bare / "todo.txt").exists()

        assert remote_main_before == commit_c
        assert remote_topic_before == commit_b
        assert remote_head_before == "refs/heads/main"
        assert working_head == "refs/heads/main"
        assert working_main == commit_c
        assert working_origin_main == commit_c
        assert working_origin_topic == commit_b
        assert working_head_tree == tree_c
        assert working_index_tree == tree_c
        assert working_status == "## main...origin/main\n"
        assert working_files == {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"}
        assert working_has_topic_head == ""
        assert bare_state == "true"
        assert bare_head == "refs/heads/main"
        assert bare_main == commit_c
        assert bare_topic == commit_b
        assert bare_heads.splitlines() == [
            f"refs/heads/main {commit_c}",
            f"refs/heads/topic {commit_b}",
        ]
        assert bare_remote_refs == ""
        assert not bare_index_exists
        assert not bare_has_worktree_files
        for repository in (working, bare):
            for commit_id in (commit_a, commit_b, commit_c):
                if repository == bare:
                    git_bare(repository, "cat-file", "-e", commit_id)
                else:
                    git(repository, "cat-file", "-e", commit_id)

        actual = [
            f"commit A: {commit_a}",
            f"commit B: {commit_b}",
            f"commit C: {commit_c}",
            f"tree C: {tree_c}",
            f"remote HEAD: {remote_head_before}",
            f"remote main: {remote_main_before}",
            f"remote topic: {remote_topic_before}",
            "normal clone:",
            f"HEAD target: {working_head}",
            f"main: {working_main}",
            f"origin/main: {working_origin_main}",
            f"origin/topic: {working_origin_topic}",
            f"HEAD tree: {working_head_tree}",
            f"index tree: {working_index_tree}",
            f"status: {working_status.rstrip()}",
            f"files: {working_files!r}",
            f"local topic branch ref: {working_has_topic_head!r}",
            "bare clone:",
            f"is bare: {bare_state}",
            f"HEAD target: {bare_head}",
            f"main: {bare_main}",
            f"topic: {bare_topic}",
            f"branch refs:\n{bare_heads.rstrip()}",
            f"remote-tracking refs: {bare_remote_refs!r}",
            f"index exists: {bare_index_exists}",
            f"worktree files exist: {bare_has_worktree_files}",
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: both clone modes retained the same commits while differing in refs, index, and worktree as expected.")


if __name__ == "__main__":
    main()
