import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "book/B-embedding-git/sections/libgit2.asc"


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def main():
    # Check that the decisive Libgit2 operations remain in the guide.
    guide = GUIDE.read_text()

    require("git_revparse_single" in guide,
            "Guide contains git_revparse_single")

    require('HEAD^{commit}' in guide,
            "Guide resolves HEAD to a commit")

    require("git_commit_message(commit)" in guide,
            "Guide reads the resolved commit message")

    # Create an isolated temporary Git repository.
    with tempfile.TemporaryDirectory(prefix="R31-T038-") as temp:
        repo = Path(temp)

        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.name", "Course Student")
        git(repo, "config", "user.email", "student@example.invalid")

        # Confirm failed Git commands are propagated by subprocess.run.
        try:
            git(repo, "rev-parse", "not-a-real-ref")
        except subprocess.CalledProcessError:
            require(True, "Failed Git commands propagate as errors")
        else:
            raise AssertionError("A failed Git command was not propagated")

        # Commit A
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt")
        git(repo, "commit", "-m", "Commit A: add notes")

        commit_a = git(repo, "rev-parse", "HEAD")

        # Commit B
        with (repo / "notes.txt").open("a") as file:
            file.write("beta\n")

        git(repo, "add", "notes.txt")
        git(repo, "commit", "-m", "Commit B: add beta")

        commit_b = git(repo, "rev-parse", "HEAD")

        # Create topic at commit B.
        git(repo, "branch", "topic", commit_b)

        # Commit C
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt")
        git(repo, "commit", "-m", "Commit C: add todo")

        commit_c = git(repo, "rev-parse", "HEAD")

        # Verify the commit resolved by HEAD^{commit}.
        resolved_head = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
        require(resolved_head == commit_c,
                "HEAD^{commit} resolves to commit C")

        # Verify the message returned for the resolved commit.
        message = git(repo, "show", "-s", "--format=%s", "HEAD")
        require(message == "Commit C: add todo",
                "HEAD commit message matches commit C")

        # Verify author information.
        author = git(repo, "show", "-s", "--format=%an <%ae>", "HEAD")
        require(author == "Course Student <student@example.invalid>",
                "HEAD author matches the configured author")

        # Verify topic still points to commit B.
        topic = git(repo, "rev-parse", "refs/heads/topic")
        require(topic == commit_b,
                "topic branch points to commit B")

        require(len({commit_a, commit_b, commit_c}) == 3,
                "The three commits have distinct object IDs")

        # Verify files in commit C.
        files = set(git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
        require(files == {"notes.txt", "todo.txt"},
                "Commit C contains notes.txt and todo.txt")

        notes = git(repo, "show", "HEAD:notes.txt")
        require(notes == "alpha\nbeta",
                "notes.txt contains alpha and beta")

        todo = git(repo, "show", "HEAD:todo.txt")
        require(todo == "one",
                "todo.txt contains one")

    require(not repo.exists(),
            "Temporary repository is removed after the check")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
