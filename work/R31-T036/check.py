import os
import subprocess
import tempfile
from pathlib import Path


EVIDENCE = Path(__file__).resolve().parent
AUTHOR_ENV = os.environ.copy()
AUTHOR_ENV.update({
    "GIT_AUTHOR_NAME": "Course Student",
    "GIT_AUTHOR_EMAIL": "student@example.invalid",
    "GIT_COMMITTER_NAME": "Course Student",
    "GIT_COMMITTER_EMAIL": "student@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
})


def run(command, cwd, check=True):
    return subprocess.run(
        command,
        cwd=cwd,
        env=AUTHOR_ENV,
        text=True,
        capture_output=True,
        check=check,
    )


def git(repo, *args, check=True):
    return run(["git", *args], repo, check=check).stdout.rstrip("\n")


def make_fixture(path):
    path.mkdir()
    run(["git", "init", "-b", "main"], path)

    (path / "notes.txt").write_text("alpha\n")
    git(path, "add", "notes.txt")
    git(path, "commit", "-m", "A: add notes")

    with (path / "notes.txt").open("a") as file:
        file.write("beta\n")
    git(path, "add", "notes.txt")
    git(path, "commit", "-m", "B: append beta")
    commit_b = git(path, "rev-parse", "HEAD")

    git(path, "switch", "main")
    (path / "todo.txt").write_text("one\n")
    git(path, "add", "todo.txt")
    git(path, "commit", "-m", "C: add todo")

    git(path, "branch", "topic", commit_b)
    return commit_b, git(path, "rev-parse", "HEAD")


def clone_fixture(source, destination, commit_b):
    run(
        ["git", "clone", "--quiet", "--no-hardlinks",
         str(source), str(destination)],
        source.parent,
    )
    git(destination, "branch", "topic", commit_b)


def diff_status(repo, cached=False):
    args = ["diff", "--quiet"]
    if cached:
        args.append("--cached")
    args.extend(["--", "notes.txt"])
    return run(["git", *args], repo, check=False).returncode


def main():
    observations = []

    with tempfile.TemporaryDirectory(prefix="R31-T036-") as temp:
        root = Path(temp)
        fixture = root / "fixture"
        commit_b, commit_c = make_fixture(fixture)

        hash_repo = root / "hash-object"
        add_repo = root / "git-add"

        clone_fixture(fixture, hash_repo, commit_b)
        clone_fixture(fixture, add_repo, commit_b)

        for repo in (hash_repo, add_repo):
            assert git(repo, "branch", "--show-current") == "main"
            assert git(repo, "rev-parse", "HEAD") == commit_c
            assert git(repo, "rev-parse", "topic") == commit_b
            assert git(repo, "status", "--porcelain") == ""

        observations.append("Both test repositories start at commit C on main.")
        observations.append("In both repositories, topic points to commit B.")

        changed_content = "alpha\nbeta\ngamma\n"
        (hash_repo / "notes.txt").write_text(changed_content)
        (add_repo / "notes.txt").write_text(changed_content)

        original_blob = git(hash_repo, "rev-parse", "HEAD:notes.txt")
        assert git(add_repo, "rev-parse", "HEAD:notes.txt") == original_blob

        hash_blob = git(hash_repo, "hash-object", "-w", "notes.txt")
        git(add_repo, "add", "notes.txt")
        add_blob = git(add_repo, "ls-files", "--stage", "--", "notes.txt").split()[1]

        assert hash_blob == add_blob
        assert git(hash_repo, "cat-file", "-t", hash_blob) == "blob"
        assert git(add_repo, "cat-file", "-t", add_blob) == "blob"
        observations.append("Both commands store the same new blob object.")

        hash_index_blob = git(
            hash_repo, "ls-files", "--stage", "--", "notes.txt"
        ).split()[1]
        add_index_blob = git(
            add_repo, "ls-files", "--stage", "--", "notes.txt"
        ).split()[1]

        assert hash_index_blob == original_blob
        assert add_index_blob == hash_blob
        observations.append("hash-object leaves the index at the original blob.")
        observations.append("git add updates the index to the new blob.")

        assert git(hash_repo, "status", "--porcelain") == " M notes.txt"
        assert git(add_repo, "status", "--porcelain") == "M  notes.txt"
        observations.append("hash-object leaves notes.txt unstaged.")
        observations.append("git add stages notes.txt.")

        assert diff_status(hash_repo) == 1
        assert diff_status(hash_repo, cached=True) == 0
        assert diff_status(add_repo) == 0
        assert diff_status(add_repo, cached=True) == 1
        observations.append("Working-tree and staged diffs match the expected states.")

        for repo in (hash_repo, add_repo):
            assert git(repo, "rev-parse", "HEAD") == commit_c
            assert (repo / "notes.txt").read_text() == changed_content
        observations.append("Neither workflow creates a commit or changes file content.")

    expected = [
        "Two equivalent repositories begin at commit C.",
        "topic points to commit B in both repositories.",
        "Both commands create the same blob for identical file content.",
        "hash-object -w does not update the index.",
        "git add updates the index and stages the file.",
        "Neither command creates a commit or changes the working-tree content.",
    ]

    (EVIDENCE / "expected.txt").write_text(
        "\n".join(expected) + "\n"
    )
    (EVIDENCE / "actual.txt").write_text(
        "\n".join(observations) + "\n"
    )

    print("PASS: all Git object and index assertions passed.")
    print(f"Evidence saved in: {EVIDENCE}")


if __name__ == "__main__":
    main()
