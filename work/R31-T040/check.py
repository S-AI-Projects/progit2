from pathlib import Path
import subprocess
import tempfile
import platform
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

results = []


def record(condition, message):
    if not condition:
        raise AssertionError(message)
    results.append("PASS: " + message)


def run_git(cwd, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def main():
    with tempfile.TemporaryDirectory(prefix="R31-T040-") as temp:
        base = Path(temp)
        source = base / "source"
        remote = base / "remote.git"
        clone = base / "clone"

        # Create the three-commit source repository.
        run_git(base, "init", "-b", "main", str(source))
        run_git(source, "config", "user.name", "Course Student")
        run_git(source, "config", "user.email", "student@example.invalid")

        (source / "notes.txt").write_text("alpha\n")
        run_git(source, "add", "notes.txt")
        run_git(source, "commit", "-m", "A: add notes")
        commit_a = run_git(source, "rev-parse", "HEAD")

        with (source / "notes.txt").open("a") as file:
            file.write("beta\n")
        run_git(source, "add", "notes.txt")
        run_git(source, "commit", "-m", "B: append notes")
        commit_b = run_git(source, "rev-parse", "HEAD")

        run_git(source, "branch", "topic")
        (source / "todo.txt").write_text("one\n")
        run_git(source, "add", "todo.txt")
        run_git(source, "commit", "-m", "C: add todo")
        commit_c = run_git(source, "rev-parse", "HEAD")

        record(
            (source / "notes.txt").read_text() == "alpha\nbeta\n",
            "Commit C retains alpha and beta in notes.txt",
        )
        record(
            (source / "todo.txt").read_text() == "one\n",
            "Commit C contains todo.txt with one",
        )
        record(
            run_git(source, "rev-parse", "topic") == commit_b,
            "topic points to commit B",
        )
        record(
            run_git(source, "rev-parse", "main") == commit_c,
            "main points to commit C",
        )
        record(commit_a != commit_b and commit_b != commit_c,
               "A, B, and C are distinct commits")

        # Create a local bare remote and clone it using file://.
        subprocess.run(
            ["git", "clone", "--bare", str(source), str(remote)],
            text=True,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "clone", remote.as_uri(), str(clone)],
            text=True,
            capture_output=True,
            check=True,
        )

        record(
            run_git(clone, "branch", "--show-current") == "main",
            "clone checks out main",
        )
        record(
            run_git(clone, "rev-parse", "HEAD") == commit_c,
            "clone HEAD points to commit C",
        )
        record(
            run_git(clone, "rev-parse", "origin/topic") == commit_b,
            "cloned remote-tracking topic points to commit B",
        )
        record(
            run_git(clone, "status", "--porcelain") == "",
            "clone starts with a clean working tree",
        )

        # Create slow-blink and verify that no commit or file changes.
        run_git(clone, "checkout", "-b", "slow-blink")

        record(
            run_git(clone, "branch", "--show-current") == "slow-blink",
            "checkout -b switches to slow-blink",
        )
        record(
            run_git(clone, "rev-parse", "HEAD") == commit_c,
            "HEAD remains at commit C after branch creation",
        )
        record(
            run_git(clone, "rev-parse", "main") == commit_c,
            "main remains at commit C",
        )
        record(
            run_git(clone, "symbolic-ref", "HEAD") == "refs/heads/slow-blink",
            "HEAD symbolically references slow-blink",
        )
        record(
            run_git(clone, "status", "--porcelain") == "",
            "branch creation leaves the working tree clean",
        )

        # Modify only the working tree.
        (clone / "notes.txt").write_text("alpha\ngamma\n")

        record(
            run_git(clone, "show", "HEAD:notes.txt") == "alpha\nbeta",
            "committed notes.txt still contains alpha and beta",
        )
        record(
            run_git(clone, "show", ":notes.txt") == "alpha\nbeta",
            "index still contains alpha and beta",
        )
        record(
            (clone / "notes.txt").read_text() == "alpha\ngamma\n",
            "working tree contains alpha and gamma",
        )

        cached = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=clone,
            capture_output=True,
        )
        record(
            cached.returncode == 0,
            "staged diff is empty",
        )

        unstaged = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=clone,
            capture_output=True,
        )
        record(
            unstaged.returncode == 1,
            "unstaged diff detects the working-tree change",
        )

        word_diff = run_git(clone, "diff", "--word-diff")
        record(
            "[-beta-]{+gamma+}" in word_diff,
            "word diff identifies beta removal and gamma addition",
        )
        record(
            run_git(clone, "rev-parse", "HEAD") == commit_c,
            "HEAD remains at commit C after editing notes.txt",
        )

    # Verify that the guide contains the exercise and explanation.
    guide = (ROOT / "book/06-github/sections/2-contributing.asc").read_text()

    for phrase in [
        "Predicting and Verifying Git State",
        "git checkout -b slow-blink",
        "git diff --word-diff",
        "Answer and explanation",
        "&#123;+...+&#125;",
    ]:
        record(phrase in guide, f"guide contains: {phrase}")

    return len(results)


if __name__ == "__main__":
    try:
        count = main()
        actual = "\n".join(results) + f"\n\nTOTAL: {count} checks passed\n"
        (HERE / "actual.txt").write_text(actual)
        print(actual, end="")
    except Exception as error:
        actual = "\n".join(results)
        actual += f"\nFAIL: {type(error).__name__}: {error}\n"
        (HERE / "actual.txt").write_text(actual)
        print(actual, file=sys.stderr, end="")
        raise
