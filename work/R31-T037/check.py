import os
import subprocess
import tempfile
from pathlib import Path


def git(repo, *args, env=None, check=True):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result


def commit(repo, message, env):
    result = git(repo, "commit", "-m", message, env=env, check=False)
    assert result.returncode == 0, f"Commit failed: {message}"
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def main():
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Course Student",
        "GIT_AUTHOR_EMAIL": "student@example.invalid",
        "GIT_COMMITTER_NAME": "Course Student",
        "GIT_COMMITTER_EMAIL": "student@example.invalid",
    })

    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)

        git(repo, "init", "-b", "main")

        # Commit A: create notes.txt with alpha
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt")
        a = commit(repo, "A: create notes", env)

        # Commit B: append beta
        with (repo / "notes.txt").open("a") as file:
            file.write("beta\n")
        git(repo, "add", "notes.txt")
        b = commit(repo, "B: append beta", env)

        # Create topic at B
        git(repo, "branch", "topic")

        # Commit C on main: add todo.txt
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt")
        c = commit(repo, "C: add todo", env)

        assert git(repo, "rev-parse", "topic").stdout.strip() == b
        assert git(repo, "rev-parse", "main").stdout.strip() == c
        assert git(repo, "show", f"{a}:notes.txt").stdout == "alpha\n"
        assert git(repo, "show", f"{b}:notes.txt").stdout == "alpha\nbeta\n"
        assert git(repo, "show", f"{c}:todo.txt").stdout == "one\n"

        # Create an unstaged modification on main
        with (repo / "notes.txt").open("a") as file:
            file.write("gamma\n")

        # Bad case: commit without staging
        failed = git(
            repo, "commit", "-m", "Add gamma",
            env=env, check=False
        )

        assert failed.returncode != 0, "Unstaged commit unexpectedly succeeded"
        assert "no changes added to commit" in failed.stdout.lower()
        assert git(repo, "rev-parse", "HEAD").stdout.strip() == c
        assert git(repo, "status", "--short").stdout.strip() == "M notes.txt"
        assert git(repo, "show", ":notes.txt").stdout == "alpha\nbeta\n"

        # Correction: stage, then commit
        git(repo, "add", "notes.txt")
        d = commit(repo, "Add gamma", env)

        assert d != c
        assert git(repo, "show", "HEAD:notes.txt").stdout == (
            "alpha\nbeta\ngamma\n"
        )
        assert git(repo, "rev-parse", "topic").stdout.strip() == b
        assert git(repo, "status", "--short").stdout.strip() == ""

        authors = git(
            repo, "log", "--format=%an <%ae>", "main"
        ).stdout.splitlines()

        assert len(authors) == 4
        assert all(
            author == "Course Student <student@example.invalid>"
            for author in authors
        )

    print("PASS: Commits A, B and C created correctly.")
    print("PASS: topic branch points to commit B.")
    print("PASS: Commit without staging exits non-zero.")
    print("PASS: Failed commit leaves HEAD and index unchanged.")
    print("PASS: Staging allows the corrected commit.")
    print("PASS: Final working tree is clean.")
    print("PASS: All commits use the required author.")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
