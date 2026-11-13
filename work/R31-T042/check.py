import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []

def run(repo, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, env=ENV,
                          capture_output=True, text=True, check=check)

def git(repo, *args):
    return run(repo, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def run_once():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()

        # BEFORE git init
        expect("no .git before init", (repo / ".git").exists(), False)

        # AFTER git init: refs, history, index, working tree
        git(repo, "init", "-b", "main")
        expect(".git directory created", (repo / ".git").is_dir(), True)
        expect("HEAD is a symbolic ref to main", git(repo, "symbolic-ref", "HEAD"), "refs/heads/main")
        expect("no branch refs yet (unborn branch)", git(repo, "for-each-ref"), "")
        expect("HEAD does not resolve to a commit",
               run(repo, "rev-parse", "--verify", "HEAD", check=False).returncode != 0, True)
        expect("index is empty", git(repo, "ls-files"), "")
        expect("status is clean", git(repo, "status", "--short"), "")

        # Commit A
        (repo / "notes.txt").write_text("alpha\n")
        expect("A: untracked (working tree only)", git(repo, "status", "--short"), "?? notes.txt")
        git(repo, "add", "notes.txt")
        expect("A: staged (index)", git(repo, "status", "--short"), "A  notes.txt")
        git(repo, "commit", "-m", "A")
        a = git(repo, "rev-parse", "HEAD")
        expect("A: branch ref main now equals HEAD", git(repo, "rev-parse", "refs/heads/main"), a)
        expect("A is a root commit (no parent)",
               run(repo, "rev-parse", "--verify", "HEAD^", check=False).returncode != 0, True)

        # Commit B
        with open(repo / "notes.txt", "a") as f:
            f.write("beta\n")
        expect("B: modified in working tree only", git(repo, "status", "--short"), " M notes.txt")
        git(repo, "commit", "-am", "B")
        b = git(repo, "rev-parse", "HEAD")
        expect("B's parent is A", git(repo, "rev-parse", "HEAD^"), a)

        # Commit C
        (repo / "todo.txt").write_text("one\n")
        expect("C: untracked (working tree only)", git(repo, "status", "--short"), "?? todo.txt")
        git(repo, "add", "todo.txt")
        expect("C: staged (index)", git(repo, "status", "--short"), "A  todo.txt")
        git(repo, "commit", "-m", "C")
        c = git(repo, "rev-parse", "HEAD")
        expect("C's parent is B", git(repo, "rev-parse", "HEAD^"), b)
        expect("3 commits in history", git(repo, "rev-list", "--count", "HEAD"), "3")

        # Branch topic at B
        git(repo, "branch", "topic", b)
        expect("topic points at B", git(repo, "rev-parse", "topic"), b)
        expect("main points at C", git(repo, "rev-parse", "main"), c)
        expect("HEAD still follows main", git(repo, "symbolic-ref", "HEAD"), "refs/heads/main")
        expect("files in HEAD tree", git(repo, "ls-tree", "-r", "--name-only", "HEAD"), "notes.txt\ntodo.txt")
        expect("final status is clean", git(repo, "status", "--short"), "")

        LOG.append(
            f"\nDIAGRAM\n"
            f" refs:           HEAD -> main ({c[:7]})    topic ({b[:7]})\n"
            f" history:        {a[:7]} <- {b[:7]} <- {c[:7]}\n"
            f" index (staged): notes.txt, todo.txt\n"
            f" working tree:   notes.txt, todo.txt  (matches index and HEAD)\n")
        return git(repo, "ls-tree", "-r", "--name-only", "HEAD")

if __name__ == "__main__":
    r1, r2 = run_once(), run_once()
    assert r1 == r2
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
    print(LOG[-1])
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)
