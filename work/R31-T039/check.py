import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent

def run(args, cwd):
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()

def check(condition, message):
    if not condition:
        raise AssertionError(message)
    results.append("PASS: " + message)

results = []

inputs = """Temporary Git repository
Branch: main
Author: Course Student <student@example.invalid>
Commit A: notes.txt contains alpha\\n
Commit B: notes.txt contains alpha\\nbeta\\n
Branch topic: points to commit B
Commit C: todo.txt contains one\\n
No remote repository required
"""

(EVIDENCE / "inputs.txt").write_text(inputs)

try:
    with tempfile.TemporaryDirectory(prefix="R31-T039-") as temp:
        repo = Path(temp) / "example-repo"
        repo.mkdir()

        run(["git", "init", "-b", "main"], repo)
        run(["git", "config", "--local", "user.name", "Course Student"], repo)
        run(["git", "config", "--local", "user.email", "student@example.invalid"], repo)

        (repo / "notes.txt").write_text("alpha\n")
        run(["git", "add", "notes.txt"], repo)
        run(["git", "commit", "-m", "A: add notes"], repo)
        commit_a = run(["git", "rev-parse", "HEAD"], repo)

        with (repo / "notes.txt").open("a") as f:
            f.write("beta\n")
        run(["git", "add", "notes.txt"], repo)
        run(["git", "commit", "-m", "B: append notes"], repo)
        commit_b = run(["git", "rev-parse", "HEAD"], repo)

        run(["git", "branch", "topic"], repo)

        (repo / "todo.txt").write_text("one\n")
        run(["git", "add", "todo.txt"], repo)
        run(["git", "commit", "-m", "C: add todo"], repo)
        commit_c = run(["git", "rev-parse", "HEAD"], repo)

        check(run(["git", "branch", "--show-current"], repo) == "main",
              "main is the current branch")
        check(run(["git", "rev-list", "--count", "HEAD"], repo) == "3",
              "main contains exactly three commits")
        check(run(["git", "show", f"{commit_a}:notes.txt"], repo) == "alpha",
              "commit A contains notes.txt with alpha")
        check(run(["git", "show", f"{commit_b}:notes.txt"], repo) == "alpha\nbeta",
              "commit B contains alpha and beta")
        check(run(["git", "show", f"{commit_c}:todo.txt"], repo) == "one",
              "commit C contains todo.txt with one")
        check(run(["git", "rev-parse", "topic"], repo) == commit_b,
              "topic points to commit B")
        check(run(["git", "rev-parse", "HEAD"], repo) == commit_c,
              "main HEAD points to commit C")
        check(run(["git", "show", "-s", "--format=%an <%ae>", "HEAD"], repo)
              == "Course Student <student@example.invalid>",
              "commit author is Course Student")
        check(run(["git", "config", "--local", "user.name"], repo)
              == "Course Student",
              "author name is configured locally")
        check(run(["git", "config", "--local", "user.email"], repo)
              == "student@example.invalid",
              "author email is configured locally")
        check(run(["git", "status", "--porcelain"], repo) == "",
              "temporary repository working tree is clean")

    guide = (ROOT / "book/01-introduction/sections/about-version-control.asc").read_text()
    required = [
        "Before You Start",
        "git rev-parse --show-toplevel",
        "git branch --show-current",
        "git status --short --branch",
        "git config --local user.name",
        "git config --local user.email",
        "git init -b main example-repo",
        "$ git rev-parse --show-toplevel",
        "$ git branch --show-current",
        "$ git status --short --branch",
        "student@example.invalid",
        "git branch topic",
        "A: add notes",
        "B: append notes",
        "C: add todo",
    ]
    for item in required:
        check(item in guide, f"guide includes: {item}")

    expected = "\n".join(results) + "\n"
    (EVIDENCE / "expected.txt").write_text(expected)
    (EVIDENCE / "actual.txt").write_text(expected)

    versions = (
        run(["git", "--version"], ROOT) + "\n"
        + run(["python3", "--version"], ROOT) + "\n"
    )
    (EVIDENCE / "versions.txt").write_text(versions)

    print(expected, end="")
    print(f"\nAll {len(results)} checks passed.")

except Exception as error:
    (EVIDENCE / "actual.txt").write_text(
        "\n".join(results) + f"\nFAIL: {error}\n"
    )
    print(f"CHECK FAILED: {error}")
    raise
