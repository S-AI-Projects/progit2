import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []

def run(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)

def git(cwd, *args):
    return run(cwd, *args).stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def build_fixture(repo):
    """Same fixture for BOTH workflows: A, B, C on main, topic at B, plus the same dirty state."""
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
    # Dirty state, identical in both repos:
    with open(repo / "notes.txt", "a") as f: f.write("gamma\n")   # tracked file edited, NOT staged
    (repo / "new.txt").write_text("new\n")
    git(repo, "add", "new.txt")                                   # new file, staged
    (repo / "scratch.txt").write_text("scratch\n")                # untracked, never staged
    return b, c

def run_once():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        r1, r2 = root / "vscode_commit", root / "commit_a_flag"
        b1, c1 = build_fixture(r1)
        b2, c2 = build_fixture(r2)

        # Equivalent fixtures: same trees and same status before either workflow runs
        expect("fixtures: HEAD trees identical", git(r1, "rev-parse", "HEAD^{tree}"), git(r2, "rev-parse", "HEAD^{tree}"))
        expect("fixtures: status identical", git(r1, "status", "--short"), git(r2, "status", "--short"))
        expect("fixture status is: edit unstaged, new.txt staged, scratch.txt untracked",
               git(r1, "status", "--short"), "A  new.txt\n M notes.txt\n?? scratch.txt")

        # Workflow 1: what VS Code's Source Control "Commit" button does -> `git commit` (staged only)
        git(r1, "commit", "-m", "W")
        # Workflow 2: second command addressing the same situation -> `git commit -a`
        git(r2, "commit", "-a", "-m", "W")

        # Shared facts: the intended ref moved by exactly one commit; unrelated refs did not
        for name, r, b, c in (("commit", r1, b1, c1), ("commit -a", r2, b2, c2)):
            expect(f"[{name}] main advanced by one commit (parent is old main)", git(r, "rev-parse", "main^"), c)
            expect(f"[{name}] topic did not move (still at B)", git(r, "rev-parse", "topic"), b)
            expect(f"[{name}] new.txt (staged) is in the commit", git(r, "show", "HEAD:new.txt"), "new")
            expect(f"[{name}] untracked scratch.txt is NOT in the commit",
                   "scratch.txt" in git(r, "ls-tree", "-r", "--name-only", "HEAD").split("\n"), False)
            expect(f"[{name}] scratch.txt still untracked",
                   git(r, "status", "--short", "--", "scratch.txt"), "?? scratch.txt")

        # THE OBSERVABLE DIFFERENCE: the unstaged edit to a tracked file
        expect("[commit] notes.txt in the commit is still the OLD content",
               git(r1, "show", "HEAD:notes.txt"), "alpha\nbeta")
        expect("[commit -a] notes.txt in the commit has the NEW content (gamma)",
               git(r2, "show", "HEAD:notes.txt"), "alpha\nbeta\ngamma")
        expect("[commit] edit is left behind: status shows notes.txt modified + scratch untracked",
               git(r1, "status", "--short"), " M notes.txt\n?? scratch.txt")
        expect("[commit -a] edit was committed: only scratch.txt remains",
               git(r2, "status", "--short"), "?? scratch.txt")
        expect("[commit] unstaged diff still lists notes.txt", git(r1, "diff", "--name-only"), "notes.txt")
        expect("[commit -a] unstaged diff is empty", git(r2, "diff", "--name-only"), "")
        expect("the two commits have DIFFERENT trees",
               git(r1, "rev-parse", "HEAD^{tree}") != git(r2, "rev-parse", "HEAD^{tree}"), True)
        expect("but todo.txt is the same object in both (only notes.txt differs)",
               git(r1, "rev-parse", "HEAD:todo.txt"), git(r2, "rev-parse", "HEAD:todo.txt"))
        expect("notes.txt is stored as a DIFFERENT object in the two commits",
               git(r1, "rev-parse", "HEAD:notes.txt") != git(r2, "rev-parse", "HEAD:notes.txt"), True)
        return git(r1, "ls-tree", "-r", "--name-only", "HEAD")

if __name__ == "__main__":
    a, b = run_once(), run_once()
    assert a == b
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + "\n")
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)
