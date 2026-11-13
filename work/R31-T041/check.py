import os, subprocess, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}

def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, env=ENV,
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()

def run_once():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt"); git(repo, "commit", "-m", "A")
        with open(repo / "notes.txt", "a") as f: f.write("beta\n")
        git(repo, "commit", "-am", "B")
        b = git(repo, "rev-parse", "HEAD")
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt"); git(repo, "commit", "-m", "C")
        c = git(repo, "rev-parse", "HEAD")
        git(repo, "branch", "topic", b)

        print("HEAD tree:", git(repo, "ls-tree", "-r", "HEAD"))

        git(repo, "reset", "--soft", "topic")
        assert git(repo, "rev-parse", "HEAD") == b
        assert "todo.txt" in git(repo, "ls-files")
        assert (repo / "todo.txt").exists()
        assert git(repo, "status", "--short") == "A  todo.txt"
        git(repo, "reset", "--hard", c)

        git(repo, "reset", "topic")
        assert git(repo, "rev-parse", "HEAD") == b
        assert "todo.txt" not in git(repo, "ls-files")
        assert (repo / "todo.txt").exists()
        assert git(repo, "status", "--short") == "?? todo.txt"
        git(repo, "reset", "--hard", c)

        git(repo, "reset", "--hard", "topic")
        assert git(repo, "rev-parse", "HEAD") == b
        assert not (repo / "todo.txt").exists()
        assert git(repo, "ls-files") == "notes.txt"
        assert git(repo, "status", "--short") == ""

        return {"files_after_hard": git(repo, "ls-files")}

if __name__ == "__main__":
    r1, r2 = run_once(), run_once()
    assert r1["files_after_hard"] == r2["files_after_hard"]
    print("Tool versions:", subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip())
    print("ALL CHECKS PASSED (ran twice)")
