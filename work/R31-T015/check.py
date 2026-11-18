#!/usr/bin/env python3
"""Verify rev-list path filtering for filenames and directories containing spaces."""

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
    with tempfile.TemporaryDirectory(prefix="R31-T015-") as directory:
        repo = Path(directory)
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
        (repo / "release notes.txt").write_text("Release one\n", encoding="utf-8")
        sample_data = repo / "sample data"
        sample_data.mkdir()
        (sample_data / "example.txt").write_text("example\n", encoding="utf-8")
        git(repo, "add", "todo.txt", "release notes.txt", "sample data")
        commit(repo, "C: add todo and release files", 3)
        commit_c = git(repo, "rev-parse", "HEAD").strip()

        oldrev = git(repo, "rev-parse", "topic").strip()
        newrev = git(repo, "rev-parse", "main").strip()
        all_commits = git(repo, "rev-list", f"{oldrev}..{newrev}").splitlines()
        matching_commits = git(
            repo,
            "rev-list",
            f"{oldrev}..{newrev}",
            "--",
            "release notes.txt",
            "sample data",
        ).splitlines()
        matching_paths = git(
            repo,
            "log",
            "-1",
            "--name-only",
            "--pretty=format:",
            newrev,
            "--",
            "release notes.txt",
            "sample data",
        ).splitlines()
        notes_only = git(
            repo,
            "rev-list",
            f"{oldrev}..{newrev}",
            "--",
            "release notes.txt",
        ).splitlines()
        directory_only = git(
            repo,
            "rev-list",
            f"{oldrev}..{newrev}",
            "--",
            "sample data",
        ).splitlines()

        assert git(repo, "rev-parse", "main").strip() == commit_c
        assert git(repo, "rev-parse", "topic").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_c}^").strip() == commit_b
        assert git(repo, "rev-parse", f"{commit_b}^").strip() == commit_a
        assert all_commits == [commit_c]
        assert matching_commits == [commit_c]
        assert notes_only == [commit_c]
        assert directory_only == [commit_c]
        assert matching_paths == ["release notes.txt", "sample data/example.txt"]
        assert (repo / "notes.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"
        assert (repo / "todo.txt").read_text(encoding="utf-8") == "one\n"
        assert (repo / "release notes.txt").read_text(encoding="utf-8") == "Release one\n"
        assert (sample_data / "example.txt").read_text(encoding="utf-8") == "example\n"
        assert git(repo, "status", "--porcelain") == ""

        actual = [
            f"commit A: {commit_a}",
            f"commit B / oldrev / topic: {commit_b}",
            f"commit C / newrev / main: {commit_c}",
            f"revision range: {oldrev}..{newrev}",
            "git rev-list range:",
            *all_commits,
            "git rev-list range -- 'release notes.txt' 'sample data':",
            *matching_commits,
            "git log path names:",
            *matching_paths,
            "file-only rev-list:",
            *notes_only,
            "directory-only rev-list:",
            *directory_only,
            f"notes.txt={(repo / 'notes.txt').read_text(encoding='utf-8')!r}",
            f"release notes.txt={(repo / 'release notes.txt').read_text(encoding='utf-8')!r}",
            f"sample data/example.txt={(sample_data / 'example.txt').read_text(encoding='utf-8')!r}",
            "",
        ]
        (ROOT / "actual.txt").write_text("\n".join(actual), encoding="utf-8")

    print("PASS: quoted pathspecs selected the expected commit and preserved both spaced paths.")


if __name__ == "__main__":
    main()
