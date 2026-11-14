import os, subprocess, sys, tempfile
from pathlib import Path

ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "Course Student", "GIT_AUTHOR_EMAIL": "student@example.invalid",
       "GIT_COMMITTER_NAME": "Course Student", "GIT_COMMITTER_EMAIL": "student@example.invalid"}
LOG = []

def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, env=ENV,
                       capture_output=True, text=True, check=True)
    return r.stdout.rstrip("\n")

def expect(label, actual, expected):
    LOG.append(f"{label}\n  expected: {expected!r}\n  actual:   {actual!r}")
    assert actual == expected, f"FAILED: {label}: expected {expected!r}, got {actual!r}"

def run_once():
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")

        # Setup: commits A, B, C and branch topic at B
        (repo / "notes.txt").write_text("alpha\n")
        git(repo, "add", "notes.txt"); git(repo, "commit", "-m", "A")
        with open(repo / "notes.txt", "a") as f: f.write("beta\n")
        git(repo, "commit", "-am", "B")
        b = git(repo, "rev-parse", "HEAD")
        (repo / "todo.txt").write_text("one\n")
        git(repo, "add", "todo.txt"); git(repo, "commit", "-m", "C")
        c = git(repo, "rev-parse", "HEAD")
        git(repo, "branch", "topic", b)
        saved_tree = git(repo, "rev-parse", "HEAD^{tree}")   # saved tree hash of C

        # An uncommitted edit that Git has NOT recorded anywhere
        with open(repo / "notes.txt", "a") as f: f.write("gamma\n")
        expect("uncommitted edit exists", git(repo, "status", "--short"), " M notes.txt")

        # THE MISTAKE: hard reset main back to topic (B)
        git(repo, "reset", "--hard", "topic")
        expect("mistake: main moved back to B", git(repo, "rev-parse", "main"), b)
        expect("mistake: C no longer in history", git(repo, "rev-list", "--count", "HEAD"), "2")
        expect("mistake: todo.txt vanished", (repo / "todo.txt").exists(), False)
        expect("mistake: uncommitted edit wiped", (repo / "notes.txt").read_text(), "alpha\nbeta\n")

        # RECOVERY: the commit object still exists, and the reflog remembers it
        expect("commit C object still exists", git(repo, "cat-file", "-t", c), "commit")
        expect("reflog remembers C as HEAD@{1}", git(repo, "rev-parse", "HEAD@{1}"), c)
        git(repo, "reset", "--hard", "HEAD@{1}")

        expect("recovered: main back at C", git(repo, "rev-parse", "main"), c)
        expect("recovered: tree hash matches the saved one", git(repo, "rev-parse", "HEAD^{tree}"), saved_tree)
        expect("recovered: todo.txt content", (repo / "todo.txt").read_text(), "one\n")
        expect("recovered: notes.txt content", (repo / "notes.txt").read_text(), "alpha\nbeta\n")
        expect("recovered: working tree clean", git(repo, "status", "--short"), "")
        expect("NOT recovered: uncommitted 'gamma' edit stays lost", "gamma" in (repo / "notes.txt").read_text(), False)
        return saved_tree

if __name__ == "__main__":
    t1, t2 = run_once(), run_once()
    assert t1 == t2, "tree hash differs between runs"
    ver = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
    notes = ("\nRECOVERY INSTRUCTIONS\n"
             "1. Run: git reflog          (find the entry from before the mistake)\n"
             "2. Run: git reset --hard HEAD@{1}   (or the exact reflog entry)\n"
             "WHAT CANNOT BE RECOVERED BY THIS METHOD:\n"
             "- Uncommitted edits to tracked files (they were never saved as a commit, so the reflog has no record).\n"
             "- Anything after the reflog entries expire or after git gc prunes unreachable objects.\n")
    out = Path(__file__).parent / "results.txt"
    out.write_text(f"Tools: {ver}; Python {sys.version.split()[0]}\n\n" + "\n".join(LOG) + notes)
    print(notes)
    print("ALL CHECKS PASSED (ran twice). Results saved to", out)
