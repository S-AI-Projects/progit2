#!/usr/bin/env python3
"""Verify the missing-local-repository failure and its path correction."""

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
    with tempfile.TemporaryDirectory(prefix="R31-T017-") as directory:
        root = Path(directory)
        repo = root / "work"
        repo.mkdir()
        remote = root / "project.git"

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
        git(repo, "remote", "add", "seed", remote.as_uri())
        git(repo, "push", "seed", "main", "topic")

        missing = root / "missing.git"
        bad_destination = root / "bad-clone"
        failed_clone = subprocess.run(
            ["git", "clone", str(missing), str(bad_destination)],
            cwd=root,
            env={**os.environ, **BASE_ENV},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        error_text = (failed_clone.stdout + failed_clone.stderr).lower()
        assert failed_clone.returncode != 0
        assert not missing.exists()
        assert "repository" in error_text
        assert any(
            phrase in error_text
            for phrase in (
                "does not exist",
                "does not appear to be a git repository",
                "not a git repository",
            )
        )

        good_destination = root / "good-clone"
        git(root, "clone", str(remote), str(good_destination))
        repaired_head = git(good_destination, "rev-parse", "HEAD").strip()
        repaired_main = git(good_destination, "rev-parse", "refs/heads/main").strip()
        repaired_topic = git(
            good_destination, "rev-parse", "refs/remotes/origin/topic"
        ).strip()
        repaired_tree = git(
            good_destination, "rev-parse", "HEAD^{tree}"
        ).strip()
        index_tree = git(good_destination, "write-tree").strip()
        status = git(good_destination, "status", "--short", "--branch")
        files = {
            "notes.txt": (good_destination / "notes.txt").read_text(encoding="utf-8"),
            "todo.txt": (good_destination / "todo.txt").read_text(encoding="utf-8"),
        }

        assert git(repo, "rev-parse", "main").strip() == commit_c
        assert git(repo, "rev-parse", "topic").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert repaired_head == repaired_main == commit_c
        assert repaired_topic == commit_b
        assert repaired_tree == index_tree
        assert status == "## main...origin/main\n"
        assert files == {"notes.txt": "alpha\nbeta\n", "todo.txt": "one\n"}
        git(good_destination, "diff", "--exit-code")
        git(good_destination, "diff", "--cached", "--exit-code")

        actual = [
            f"commit A: {commit_a}",
            f"commit B / topic: {commit_b}",
            f"commit C / main: {commit_c}",
            f"existing source path: {remote}",
            f"missing source path: {missing}",
            f"failed clone exit status: {failed_clone.returncode}",
            "failed clone diagnostic category:",
            failed_clone.stderr.rstrip(),
            "corrected command: git clone <existing local repository path> <destination>",
            f"repaired HEAD: {repaired_head}",
            f"repaired main: {repaired_main}",
            f"repaired origin/topic: {repaired_topic}",
            f"tree at HEAD: {repaired_tree}",
            f"index tree: {index_tree}",
            "status:",
            status.rstrip(),
            f"files: {files!r}",
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: missing source failed with a repository-path error; cloning the existing bare repository succeeded.")


if __name__ == "__main__":
    main()
