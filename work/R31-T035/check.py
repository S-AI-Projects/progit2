
import subprocess
import tempfile
import sys
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent


def git(args, cwd):
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True
    )
    return result.stdout.strip()


def main():
    actual = []
    expected = []

    git_version = subprocess.run(
        ["git", "--version"],
        text=True,
        capture_output=True,
        check=True
    ).stdout.strip()

    actual.append(git_version)
    actual.append(f"Python: {sys.version.split()[0]}")

    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        repo = base / "project"
        repo.mkdir()

        # Initialize repository
        git(["init", "-b", "main"], repo)
        git(["config", "user.name", "Course Student"], repo)
        git(["config", "user.email", "student@example.invalid"], repo)

        # Commit A: create notes.txt
        (repo / "notes.txt").write_text("alpha\n")
        git(["add", "notes.txt"], repo)
        git(["commit", "-m", "A: add notes"], repo)
        commit_a = git(["rev-parse", "HEAD"], repo)

        # Commit B: append beta
        with (repo / "notes.txt").open("a") as file:
            file.write("beta\n")

        git(["add", "notes.txt"], repo)
        git(["commit", "-m", "B: append beta"], repo)
        commit_b = git(["rev-parse", "HEAD"], repo)

        # Create topic branch at commit B
        git(["branch", "topic", commit_b], repo)

        # Commit C: add todo.txt and release notes.txt
        (repo / "todo.txt").write_text("one\n")
        (repo / "release notes.txt").write_text(
            "Release version one\n"
        )

        git(["add", "todo.txt", "release notes.txt"], repo)
        git(["commit", "-m", "C: add todo and release notes"], repo)
        commit_c = git(["rev-parse", "HEAD"], repo)

        # Check local branch and file states
        topic_commit = git(["rev-parse", "topic"], repo)
        main_commit = git(["rev-parse", "main"], repo)

        notes_content = (repo / "notes.txt").read_text()
        todo_content = (repo / "todo.txt").read_text()

        # -- separates revisions from paths
        path_history = git(
            ["log", "--format=%H", "--", "release notes.txt"],
            repo
        )

        path_show = git(
            ["show", "HEAD", "--", "release notes.txt"],
            repo
        )

        # Create a bare remote inside a directory with spaces
        remote_dir = base / "sample data"
        remote_dir.mkdir()

        remote = remote_dir / "remote.git"

        git(["init", "--bare", str(remote)], base)

        git(
            ["--git-dir", str(remote), "symbolic-ref", "HEAD",
             "refs/heads/main"],
            base
        )

        remote_url = remote.as_uri()

        git(["remote", "add", "origin", remote_url], repo)

        git(["push", "origin", "main"], repo)
        git(["push", "origin", "topic"], repo)

        remote_refs = git(["ls-remote", "origin"], repo)
        remote_info = git(["remote", "show", "origin"], repo)

        # Expected results
        expected.extend([
            f"Commit A exists: {commit_a}",
            f"Commit B exists: {commit_b}",
            f"Commit C exists: {commit_c}",
            "topic points to commit B",
            "main points to commit C",
            "notes.txt contains alpha and beta",
            "todo.txt contains one",
            "release notes.txt appears in path history",
            "remote contains main and topic"
        ])

        # Actual results
        actual.extend([
            f"Commit A: {commit_a}",
            f"Commit B: {commit_b}",
            f"Commit C: {commit_c}",
            f"topic points to B: {topic_commit == commit_b}",
            f"main points to C: {main_commit == commit_c}",
            f"notes.txt content: {notes_content!r}",
            f"todo.txt content: {todo_content!r}",
            f"Path history: {path_history}",
            f"Path show contains release text: "
            f"{'Release version one' in path_show}",
            f"Remote URL: {remote_url}",
            f"Remote refs:\n{remote_refs}",
            f"Remote information:\n{remote_info}"
        ])

        # Save evidence
        (EVIDENCE_DIR / "expected.txt").write_text(
            "\n".join(expected) + "\n"
        )

        (EVIDENCE_DIR / "actual.txt").write_text(
            "\n".join(actual) + "\n"
        )

        # Verify expected Git states
        assert topic_commit == commit_b, (
            "topic must point to commit B"
        )

        assert main_commit == commit_c, (
            "main must point to commit C"
        )

        assert notes_content == "alpha\nbeta\n"
        assert todo_content == "one\n"

        assert commit_c in path_history
        assert "Release version one" in path_show

        assert "refs/heads/main" in remote_refs
        assert "refs/heads/topic" in remote_refs

        assert "HEAD branch: main" in remote_info

    # Save tool versions
    (EVIDENCE_DIR / "versions.txt").write_text(
        "\n".join(actual[:2]) + "\n"
    )

    print("All R31-T035 checks passed!")
    print("Evidence saved in work/R31-T035/")


if __name__ == "__main__":
    main()
