import subprocess
import tempfile
from pathlib import Path


EVIDENCE = Path(__file__).parent


def run(args, cwd=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def git(repo, *args):
    return run(["git", *args], cwd=repo)


def main():
    expected = [
        "topic points to commit B",
        "recovered tree matches the saved tree hash",
        "notes.txt contains alpha and beta",
        "todo.txt is absent on recovered topic",
        "topic tracks origin/topic and working tree is clean",
    ]

    actual = []

    with tempfile.TemporaryDirectory(prefix="R31-T033-") as temp:
        root = Path(temp)
        repo = root / "project"
        remote = root / "remote.git"

        run(["git", "init", "-b", "main", str(repo)])
        git(repo, "config", "user.name", "Course Student")
        git(repo, "config", "user.email", "student@example.invalid")

        notes = repo / "notes.txt"
        notes.write_text("alpha\n")
        git(repo, "add", "notes.txt")
        git(repo, "commit", "-m", "A: create notes")
        commit_a = git(repo, "rev-parse", "HEAD")

        with notes.open("a") as file:
            file.write("beta\n")
        git(repo, "add", "notes.txt")
        git(repo, "commit", "-m", "B: append beta")
        commit_b = git(repo, "rev-parse", "HEAD")

        git(repo, "branch", "topic", commit_b)
        saved_tree = git(repo, "rev-parse", "topic^{tree}")

        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt")
        git(repo, "commit", "-m", "C: add todo")
        commit_c = git(repo, "rev-parse", "HEAD")

        run(["git", "init", "--bare", str(remote)])
        git(repo, "remote", "add", "origin", remote.as_uri())
        git(repo, "push", "-u", "origin", "main", "topic")

        # The reversible mistake: delete the local topic branch.
        git(repo, "branch", "-D", "topic")

        branches = git(repo, "branch", "-a")
        assert "remotes/origin/topic" in branches

        # Recover the local branch from its remote-tracking branch.
        git(repo, "switch", "--track", "-c", "topic", "origin/topic")

        recovered_commit = git(repo, "rev-parse", "HEAD")
        recovered_tree = git(repo, "rev-parse", "HEAD^{tree}")
        recovered_notes = (repo / "notes.txt").read_text()
        upstream = git(repo, "rev-parse", "--abbrev-ref", "@{upstream}")
        status = git(repo, "status", "--porcelain")

        assert recovered_commit == commit_b
        actual.append("PASS: topic points to commit B")

        assert recovered_tree == saved_tree
        actual.append("PASS: recovered tree matches saved tree hash")

        assert recovered_notes == "alpha\nbeta\n"
        actual.append("PASS: notes.txt contains alpha and beta")

        assert not (repo / "todo.txt").exists()
        actual.append("PASS: todo.txt is absent on recovered topic")

        assert upstream == "origin/topic" and status == ""
        actual.append("PASS: topic tracks origin/topic and working tree is clean")

        (EVIDENCE / "inputs.txt").write_text(
            "Temporary repository: main\n"
            "Author: Course Student\n"
            "Email: student@example.invalid\n"
            "Commit A: notes.txt contains alpha\\n\n"
            "Commit B: append beta\\n to notes.txt\n"
            "Commit C: todo.txt contains one\\n\n"
            "Branch topic is created at commit B.\n"
            "A local bare remote is used.\n"
        )

        (EVIDENCE / "expected.txt").write_text(
            "\n".join(expected) + "\n"
        )
        (EVIDENCE / "actual.txt").write_text(
            "\n".join(actual) + "\n"
        )
        (EVIDENCE / "commit-ids.txt").write_text(
            f"A: {commit_a}\nB: {commit_b}\nC: {commit_c}\n"
            f"Saved tree: {saved_tree}\n"
            f"Recovered commit: {recovered_commit}\n"
            f"Recovered tree: {recovered_tree}\n"
        )

    versions = (
        run(["git", "--version"]) + "\n"
        + run(["python3", "--version"]) + "\n"
    )
    (EVIDENCE / "tool-versions.txt").write_text(versions)

    print("\n".join(actual))
    print("\nAll 5 recovery checks passed.")


if __name__ == "__main__":
    main()
