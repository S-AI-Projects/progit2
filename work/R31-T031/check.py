
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent


def run_git(repo, *args, env=None):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def create_example(run_number):
    with tempfile.TemporaryDirectory() as temp:
        repo = Path(temp) / "demo"
        repo.mkdir()

        env = os.environ.copy()
        env.update({
            "GIT_AUTHOR_NAME": "Course Student",
            "GIT_AUTHOR_EMAIL": "student@example.invalid",
            "GIT_COMMITTER_NAME": "Course Student",
            "GIT_COMMITTER_EMAIL": "student@example.invalid",
        })

        run_git(repo, "init", "-b", "main", env=env)

        def set_date(day):
            date = f"2026-01-0{day}T12:00:00+0000"
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date

        # Commit A
        (repo / "notes.txt").write_text("alpha\n")
        set_date(1)
        run_git(repo, "add", "notes.txt", env=env)
        run_git(repo, "commit", "-m", "A: add alpha", env=env)
        commit_a = run_git(repo, "rev-parse", "HEAD")

        # Commit B
        with (repo / "notes.txt").open("a") as file:
            file.write("beta\n")

        set_date(2)
        run_git(repo, "add", "notes.txt", env=env)
        run_git(repo, "commit", "-m", "B: append beta", env=env)
        commit_b = run_git(repo, "rev-parse", "HEAD")

        # Create topic at B
        run_git(repo, "branch", "topic", env=env)

        # Commit C on main
        (repo / "todo.txt").write_text("one\n")
        set_date(3)
        run_git(repo, "add", "todo.txt", env=env)
        run_git(repo, "commit", "-m", "C: add todo", env=env)
        commit_c = run_git(repo, "rev-parse", "HEAD")

        actual = {
            "current_branch": run_git(repo, "branch", "--show-current"),
            "main": run_git(repo, "rev-parse", "main"),
            "topic": run_git(repo, "rev-parse", "topic"),
            "parent_of_B": run_git(repo, "rev-parse", f"{commit_b}^"),
            "parent_of_C": run_git(repo, "rev-parse", f"{commit_c}^"),
            "notes.txt": (repo / "notes.txt").read_text(),
            "todo.txt": (repo / "todo.txt").read_text(),
            "status": run_git(repo, "status", "--short", "--branch"),
            "staged_files": run_git(repo, "diff", "--cached", "--name-only"),
            "commit_subjects": run_git(
                repo, "log", "--format=%s", "--reverse", "main"
            ).splitlines(),
        }

        expected = {
            "current_branch": "main",
            "main": commit_c,
            "topic": commit_b,
            "parent_of_B": commit_a,
            "parent_of_C": commit_b,
            "notes.txt": "alpha\nbeta\n",
            "todo.txt": "one\n",
            "status": "## main",
            "staged_files": "",
            "commit_subjects": [
                "A: add alpha",
                "B: append beta",
                "C: add todo",
            ],
        }

        assert actual == expected, (
            f"Run {run_number} failed.\n"
            f"Expected: {expected}\nActual: {actual}"
        )

        return {
            "run": run_number,
            "expected": expected,
            "actual": actual,
            "object_ids": {
                "A": commit_a,
                "B": commit_b,
                "C": commit_c,
            },
            "graph": run_git(
                repo, "log", "--oneline", "--decorate", "--all"
            ),
        }


def main():
    results = [
        create_example(1),
        create_example(2),
    ]

    assert results[0]["expected"] == results[1]["expected"]
    assert results[0]["actual"] == results[1]["actual"]

    evidence = {
        "python_version": platform.python_version(),
        "git_version": run_git(Path.cwd(), "--version"),
        "inputs": {
            "branch": "main",
            "author": "Course Student",
            "email": "student@example.invalid",
            "commit_A": 'Create notes.txt containing "alpha\\n"',
            "commit_B": 'Append "beta\\n" to notes.txt',
            "topic": "Create topic at commit B",
            "commit_C": 'Create todo.txt containing "one\\n"',
        },
        "runs": results,
        "result": "PASS",
    }

    output = OUTPUT / "evidence.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")

    print("PASS: Two independent temporary repositories verified.")
    print("PASS: Three commits and both branch references verified.")
    print("PASS: File contents and parent relationships verified.")
    print("PASS: Working tree and staging area are clean.")
    print(f"Evidence saved to: {output}")


if __name__ == "__main__":
    main()
